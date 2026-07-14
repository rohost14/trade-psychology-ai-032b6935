"""
Replay Parity Suite — the P2 migration gate (Principal Engineer review
addendum #1 + #5).

Runs the SAME historical trades through two context builders and asserts the
detector outputs are identical. No detector migrates to the state machine
until its parity here is clean.

Builders:
  rescan  — session context the way the LIVE engine builds it today:
            session_pnl = sum of prior trades + current (the CRIT-1 recompute),
            peak from the TradingSession row is NOT used by any detector, so
            peak is irrelevant to parity (profit_giveaway computes its own).
  state   — session context from SessionState.rebuild() (the P2 target):
            fold-derived session_pnl and peak_pnl.

Event fingerprint: (session_date, detector, severity, trigger_symbol, rule).
Suppression reasons compared separately (they must match too — §1C.8).

Usage:
    python scripts/replay_parity.py --account <id> --days 90
    python scripts/replay_parity.py --account <id> --days 90 --detector revenge_trade

Exit code 0 = parity clean. Non-zero = diffs printed, migration blocked.
"""
import argparse
import asyncio
import sys
import types
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, and_
from uuid import UUID

from app.core.database import SessionLocal
from app.models.completed_trade import CompletedTrade
from app.models.user_profile import UserProfile
from app.core.trading_defaults import get_thresholds
from app.services.behavior_engine import behavior_engine, EngineContext
from app.services.state.session_state import SessionState

IST_OFFSET = timedelta(hours=5, minutes=30)


def _session_rescan(priors, ct):
    """Live-engine semantics: recompute session_pnl from trades."""
    s = types.SimpleNamespace()
    s.session_pnl = (sum(Decimal(str(t.realized_pnl or 0)) for t in priors)
                     + Decimal(str(ct.realized_pnl or 0)))
    s.peak_pnl = Decimal("0")   # live row value unused by detectors
    s.risk_score = Decimal("0")
    s.peak_risk_score = Decimal("0")
    s.id = None
    s.market_open = None
    return s


def _session_state(priors, ct):
    """P2 target semantics: SessionState fold."""
    st = SessionState.rebuild(list(priors) + [ct])
    s = types.SimpleNamespace()
    s.session_pnl = st.session_pnl
    s.peak_pnl = st.peak_pnl
    s.risk_score = Decimal("0")
    s.peak_risk_score = Decimal("0")
    s.id = None
    s.market_open = None
    return s


BUILDERS = {"rescan": _session_rescan, "state": _session_state}


def _fingerprint(sd, ct, e):
    return (
        str(sd), e.event_type, e.severity,
        ct.tradingsymbol or "", (e.context or {}).get("rule", ""),
        e.suppressed_reason or "",
    )


async def run_parity(account_id: str, days: int, detector_filter):
    async with SessionLocal() as db:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await db.execute(
            select(CompletedTrade)
            .where(and_(
                CompletedTrade.broker_account_id == UUID(account_id),
                CompletedTrade.exit_time >= cutoff,
            ))
            .order_by(CompletedTrade.exit_time.asc())
        )
        trades = list(result.scalars().all())
        if not trades:
            print("No trades in window.")
            return 0
        prof = (await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == UUID(account_id))
        )).scalar_one_or_none()
        thresholds = get_thresholds(prof)

        by_session = defaultdict(list)
        for t in trades:
            by_session[(t.exit_time + IST_OFFSET).date()].append(t)

        outputs = {}
        for name, builder in BUILDERS.items():
            fps = set()
            for sd in sorted(by_session):
                day = sorted(by_session[sd], key=lambda t: t.exit_time)
                for i, ct in enumerate(day):
                    priors = day[:i]
                    ctx = EngineContext(
                        broker_account_id=UUID(account_id),
                        session=builder(priors, ct),
                        completed_trade=ct,
                        session_trades=priors,
                        active_cooldowns=[],
                        thresholds=thresholds,
                        strategy_group=None,
                        exit_order_types=[],
                    )
                    for e in behavior_engine._run_all_detectors(ctx):
                        if detector_filter and e.event_type != detector_filter:
                            continue
                        fps.add(_fingerprint(sd, ct, e))
            outputs[name] = fps

        rescan, state = outputs["rescan"], outputs["state"]
        only_rescan = rescan - state
        only_state = state - rescan

        print(f"Parity over {len(trades)} trades / {len(by_session)} sessions "
              f"({days} days)\n")
        print(f"  rescan events: {len(rescan)}")
        print(f"  state  events: {len(state)}")
        print(f"  matching:      {len(rescan & state)}")

        if not only_rescan and not only_state:
            print("\nPARITY: CLEAN — state-machine context reproduces the "
                  "rescan engine exactly on this history.")
            return 0

        print(f"\nPARITY: FAILED — {len(only_rescan)} rescan-only, "
              f"{len(only_state)} state-only\n")
        for fp in sorted(only_rescan)[:20]:
            print(f"  RESCAN-ONLY: {fp}")
        for fp in sorted(only_state)[:20]:
            print(f"  STATE-ONLY:  {fp}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay parity gate for the P2 migration")
    parser.add_argument("--account", required=True)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--detector", help="restrict to one pattern_type")
    args = parser.parse_args()
    sys.exit(asyncio.run(run_parity(args.account, args.days, args.detector)))
