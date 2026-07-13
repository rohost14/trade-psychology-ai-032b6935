"""
Replay Harness — Engine v2 Appendix A.4 (mandatory validation gate).

Replays historical CompletedTrades through the BehaviorEngine detectors
WITHOUT side effects (no alerts saved, no events saved, no risk-score
updates, no notifications) and reports what would fire. Optionally diffs
against the alerts actually recorded in that window.

The context is synthesized per trade exactly the way the live engine builds
it (prior same-session trades, thresholds from profile, exit order types),
using SessionState.rebuild() for session P&L — demonstrating the
rebuild-from-DB property (§1B.1).

Usage:
    python scripts/replay_engine.py --account <broker_account_id> --days 30
    python scripts/replay_engine.py --account <id> --days 90 --diff
    python scripts/replay_engine.py --account <id> --days 30 --detector revenge_trade

Limitations (documented, acceptable for Phase 1):
  * cooldown_violation not replayed (historical Cooldown rows expire)
  * strategy_group suppression not replayed (groups may postdate trades)
  * session risk-score trajectory not simulated (needs TradingSession writes)
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
from app.models.risk_alert import RiskAlert
from app.models.user_profile import UserProfile
from app.core.trading_defaults import get_thresholds
from app.services.behavior_engine import behavior_engine, EngineContext
from app.services.state.session_state import SessionState


def _synth_session(state: SessionState):
    s = types.SimpleNamespace()
    s.session_pnl = state.session_pnl
    s.peak_pnl = state.peak_pnl
    s.risk_score = Decimal("0")
    s.peak_risk_score = Decimal("0")
    s.id = None
    s.market_open = None
    return s


async def replay(account_id: str, days: int, diff: bool, detector_filter: str | None):
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
            print(f"No CompletedTrades in the last {days} days for {account_id}.")
            return

        prof_result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == UUID(account_id))
        )
        profile = prof_result.scalar_one_or_none()
        thresholds = get_thresholds(profile)

        # Group by IST session date
        IST_OFFSET = timedelta(hours=5, minutes=30)
        by_session = defaultdict(list)
        for t in trades:
            by_session[(t.exit_time + IST_OFFSET).date()].append(t)

        print(f"Replaying {len(trades)} trades across {len(by_session)} sessions "
              f"({days} days) — dry run, zero writes\n")

        would_fire = []  # (session_date, trade, DetectedEvent)

        for session_date in sorted(by_session):
            day_trades = sorted(by_session[session_date], key=lambda t: t.exit_time)
            for i, ct in enumerate(day_trades):
                priors = day_trades[:i]
                state = SessionState.rebuild(priors + [ct])
                ctx = EngineContext(
                    broker_account_id=UUID(account_id),
                    session=_synth_session(state),
                    completed_trade=ct,
                    session_trades=priors,
                    active_cooldowns=[],       # limitation: not replayed
                    thresholds=thresholds,
                    strategy_group=None,       # limitation: not replayed
                    exit_order_types=[],       # limitation: order types not loaded
                )
                events = behavior_engine._run_all_detectors(ctx)
                for e in events:
                    if detector_filter and e.event_type != detector_filter:
                        continue
                    would_fire.append((session_date, ct, e))

        # ── Report ────────────────────────────────────────────────────────
        by_pattern = defaultdict(list)
        for sd, ct, e in would_fire:
            by_pattern[e.event_type].append((sd, ct, e))

        print(f"{'PATTERN':<34}{'FIRES':>6}  SEVERITIES")
        print("-" * 70)
        for pattern in sorted(by_pattern, key=lambda p: -len(by_pattern[p])):
            fires = by_pattern[pattern]
            sevs = defaultdict(int)
            for _, _, e in fires:
                sevs[e.severity] += 1
            sev_str = ", ".join(f"{k}:{v}" for k, v in sorted(sevs.items()))
            print(f"{pattern:<34}{len(fires):>6}  {sev_str}")
        print(f"\nTotal would-fire events: {len(would_fire)} "
              f"(pre-dedup; live dedup would reduce this)")

        if detector_filter:
            print(f"\nDetail for {detector_filter}:")
            for sd, ct, e in by_pattern.get(detector_filter, []):
                t_ist = (ct.exit_time + IST_OFFSET).strftime("%H:%M") if ct.exit_time else "--:--"
                sup = f" [suppressed:{e.suppressed_reason}]" if e.suppressed_reason else ""
                print(f"  {sd} {t_ist} {ct.tradingsymbol:<28} {e.severity:<8}{sup} {e.message[:80]}")

        # ── Diff vs recorded alerts ───────────────────────────────────────
        if diff:
            rec_result = await db.execute(
                select(RiskAlert).where(and_(
                    RiskAlert.broker_account_id == UUID(account_id),
                    RiskAlert.detected_at >= cutoff,
                ))
            )
            recorded = list(rec_result.scalars().all())
            rec_by_pattern = defaultdict(int)
            for a in recorded:
                rec_by_pattern[a.pattern_type] += 1

            print(f"\n{'PATTERN':<34}{'REPLAY':>7}{'RECORDED':>9}  NOTE")
            print("-" * 70)
            all_patterns = sorted(set(by_pattern) | set(rec_by_pattern))
            for p in all_patterns:
                r = len(by_pattern.get(p, []))
                rec = rec_by_pattern.get(p, 0)
                note = ""
                if r > rec:
                    note = "replay is pre-dedup (expected higher)"
                elif rec > r:
                    note = "CHECK: recorded more than replay found"
                print(f"{p:<34}{r:>7}{rec:>9}  {note}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay BehaviorEngine over historical trades (dry run)")
    parser.add_argument("--account", required=True, help="broker_account_id (UUID)")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--diff", action="store_true", help="diff against recorded alerts")
    parser.add_argument("--detector", help="filter to one pattern_type, prints per-fire detail")
    args = parser.parse_args()
    asyncio.run(replay(args.account, args.days, args.diff, args.detector))
