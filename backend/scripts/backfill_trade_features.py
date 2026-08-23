"""
Recompute stored per-trade features under the canonical session definitions.

WHY THIS IS NEEDED

`completed_trade_features.consecutive_loss_count` and `entry_after_loss` used to
be counted across every prior round-trip in a 50-trade window, with no session
boundary — while `session_pnl_at_entry`, in the same row, was session-scoped. As
of 2026-08-23 all three come from `app/core/session_facts` and are session-scoped.

Rows written before that keep the old meaning. Left alone, one column would hold
two definitions and `my_record`'s "your record after 2+ losses in a row" would be
computed over a mixture of them. This script rewrites the old rows.

WHAT IT DOES

Deletes and recomputes feature rows for one account or for all of them. Features
are derived data — `_compute_features_for_new_rounds` rebuilds them from
`completed_trades`, which is the source of truth — so this is safe to re-run and
loses nothing. It does not touch trades, positions, P&L or alerts.

USAGE

    python -m scripts.backfill_trade_features --dry-run
    python -m scripts.backfill_trade_features --account <broker_account_id>
    python -m scripts.backfill_trade_features --all

Always run --dry-run first: it reports how many rows would be rewritten and how
many of them would actually change value.
"""
import argparse
import asyncio
import sys
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.models.completed_trade import CompletedTrade
from app.models.completed_trade_feature import CompletedTradeFeature
from app.services.pnl_calculator import pnl_calculator

# Far enough back to cover every stored trade.
EPOCH = datetime(2000, 1, 1, tzinfo=timezone.utc)


async def _accounts(db, account: str = None):
    """
    Accounts to process, sourced from COMPLETED TRADES rather than from existing
    features.

    The obvious source is the features table, and it is the wrong one: the
    original defect was that production had no feature rows at all, so an account
    list built from them is empty exactly when the work is most needed.
    """
    if account:
        return [UUID(account)]
    rows = await db.execute(select(CompletedTrade.broker_account_id).distinct())
    return [r[0] for r in rows.all()]


async def _compare(db, broker_account_id) -> dict:
    """
    What would change, without writing anything.

    Recomputes each feature in memory and counts the rows whose streak or
    after-loss flag would move.
    """
    existing = {
        f.completed_trade_id: f
        for f in (
            await db.execute(
                select(CompletedTradeFeature).where(
                    CompletedTradeFeature.broker_account_id == broker_account_id
                )
            )
        ).scalars()
    }
    missing = (
        await db.execute(
            select(CompletedTrade.id)
            .outerjoin(
                CompletedTradeFeature,
                CompletedTradeFeature.completed_trade_id == CompletedTrade.id,
            )
            .where(
                CompletedTrade.broker_account_id == broker_account_id,
                CompletedTradeFeature.id.is_(None),
            )
        )
    ).all()

    if not existing:
        return {
            "rows": 0,
            "missing": len(missing),
            "streak_changes": 0,
            "flag_changes": 0,
        }

    trades = list(
        (
            await db.execute(
                select(CompletedTrade)
                .where(CompletedTrade.broker_account_id == broker_account_id)
                .order_by(CompletedTrade.exit_time.asc())
            )
        ).scalars()
    )
    by_id = {t.id: t for t in trades}

    streak_changes = flag_changes = 0
    for ct_id, old in existing.items():
        ct = by_id.get(ct_id)
        if ct is None or not ct.entry_time:
            continue
        prev = [
            t for t in trades
            if t.exit_time and t.exit_time < ct.entry_time
        ][-50:]
        new = pnl_calculator._build_feature(ct, prev, broker_account_id)
        if (old.consecutive_loss_count or 0) != (new.consecutive_loss_count or 0):
            streak_changes += 1
        if bool(old.entry_after_loss) != bool(new.entry_after_loss):
            flag_changes += 1

    return {
        "rows": len(existing),
        "missing": len(missing),
        "streak_changes": streak_changes,
        "flag_changes": flag_changes,
    }


async def _rewrite(db, broker_account_id) -> int:
    await db.execute(
        delete(CompletedTradeFeature).where(
            CompletedTradeFeature.broker_account_id == broker_account_id
        )
    )
    await db.flush()
    n = await pnl_calculator._compute_features_for_new_rounds(
        broker_account_id, db, EPOCH
    )
    await db.commit()
    return n


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--account", help="one broker_account_id")
    ap.add_argument("--all", action="store_true", help="every account with features")
    ap.add_argument("--dry-run", action="store_true", help="report, write nothing")
    args = ap.parse_args()

    if not (args.account or args.all or args.dry_run):
        ap.error("pass --account, --all, or --dry-run")

    async with SessionLocal() as db:
        accounts = await _accounts(db, args.account)
        if not accounts:
            print("No stored features. Nothing to do.")
            return 0

        total = 0
        for acc in accounts:
            if args.dry_run:
                d = await _compare(db, acc)
                print(
                    f"{acc}: {d['rows']} existing feature rows, "
                    f"{d['missing']} trades with NO feature row, "
                    f"{d['streak_changes']} streak values would change, "
                    f"{d['flag_changes']} after-loss flags would change"
                )
            else:
                n = await _rewrite(db, acc)
                print(f"{acc}: recomputed {n} feature rows")
                total += n

        if not args.dry_run:
            print(f"Done. {total} rows rewritten under the session-scoped definitions.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
