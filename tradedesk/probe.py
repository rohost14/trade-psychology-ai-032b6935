"""
Why a detector did not fire.

Every tool in this system answers "what fired". None answers the question a
sceptic actually asks, which is why something did not — and "no alert" is
indistinguishable from "detector broken" without it. Three of the bugs found
this week presented as silence.

The method matters more than the output. This does NOT re-implement any
detector's conditions in order to explain them: a second copy of "martingale
needs three prior trades" would drift from the first, and would then confidently
explain behaviour the engine no longer has. Instead it calls the real detector
functions against the real context, reports None as None, and separately shows
the facts and thresholds those functions read.

So the readout is: here is what the engine was looking at, here are the limits it
was checking against, and here is what each detector said when asked. Drawing the
conclusion is left to you, which is the point — you are checking my work, not
reading my summary of it.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List

from alertlab.runner.harness import IST, account_id, quiet_logs


def _db():
    from app.core.database import SessionLocal
    quiet_logs()
    return SessionLocal


async def probe() -> Dict[str, Any]:
    """Ask every detector about the session as it currently stands."""
    from sqlalchemy import and_, select

    from app.core.trading_defaults import get_thresholds
    from app.models.completed_trade import CompletedTrade
    from app.models.trading_session import TradingSession
    from app.models.user_profile import UserProfile
    from app.services.behavior_engine import BehaviorEngine, EngineContext
    from app.services.detector_registry import REGISTRY, pattern_copy

    factory = _db()
    async with factory() as db:
        trades = list((await db.execute(
            select(CompletedTrade)
            .where(CompletedTrade.broker_account_id == account_id())
            .order_by(CompletedTrade.exit_time)
        )).scalars().all())

        profile = (await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == account_id())
        )).scalar_one_or_none()

        session = (await db.execute(
            select(TradingSession)
            .where(TradingSession.broker_account_id == account_id())
            .order_by(TradingSession.session_date.desc())
        )).scalars().first()

        thresholds = get_thresholds(profile)

        if not trades:
            return {
                "ready": False,
                "reason": ("No completed trades yet. Most detectors compare the trade "
                           "that just closed against the ones before it, so there is "
                           "nothing for them to answer until a position closes."),
                "facts": _facts(trades),
                "thresholds": _relevant(thresholds),
                "detectors": [],
            }

        # The detectors are asked about the most recently closed trade, which is
        # what the live pipeline does on every fill that closes a position.
        engine = BehaviorEngine()
        ctx = EngineContext(
            broker_account_id=account_id(),
            session=session,
            completed_trade=trades[-1],
            session_trades=trades,
            active_cooldowns=[],
            thresholds=thresholds,
        )

        results: List[Dict[str, Any]] = []
        for spec in REGISTRY:
            fn = getattr(engine, spec.method, None)
            if fn is None:
                continue
            copy = pattern_copy(spec.name)
            row = {
                "detector": spec.name,
                "label": copy.label if copy else spec.name,
                "guardian_eligible": bool(spec.guardian_eligible),
            }
            try:
                event = fn(ctx)
            except Exception as exc:
                # A detector that raises is a finding in itself, and reporting it
                # as "did not fire" would hide it.
                row.update(verdict="error", detail=f"{type(exc).__name__}: {exc}")
                results.append(row)
                continue

            if event is None:
                row.update(verdict="silent",
                           detail="conditions not met for the trade that just closed")
            else:
                row.update(verdict="fires", severity=event.severity,
                           detail=event.message,
                           confidence=float(event.confidence or 0))
            results.append(row)

        order = {"fires": 0, "error": 1, "silent": 2}
        results.sort(key=lambda r: (order.get(r["verdict"], 3), r["detector"]))

        return {
            "ready": True,
            "evaluated_against": {
                "symbol": trades[-1].tradingsymbol,
                "pnl": float(trades[-1].realized_pnl or 0),
                "qty": trades[-1].total_quantity,
                "exit_ist": trades[-1].exit_time.astimezone(IST).strftime("%d %b %H:%M")
                            if trades[-1].exit_time else None,
            },
            "facts": _facts(trades),
            "thresholds": _relevant(thresholds),
            "detectors": results,
        }


def _facts(trades: List[Any]) -> Dict[str, Any]:
    """
    The session as the detectors see it.

    Read straight off the same CompletedTrade rows they are handed — not
    recomputed from orders — so a disagreement between this and a detector is a
    real disagreement rather than two different readings of the day.
    """
    if not trades:
        return {"completed_trades": 0}

    pnls = [float(t.realized_pnl or 0) for t in trades]
    losses = [p for p in pnls if p < 0]

    streak = 0
    for p in reversed(pnls):
        if p < 0:
            streak += 1
        else:
            break

    by_symbol: Dict[str, int] = {}
    for t in trades:
        by_symbol[t.tradingsymbol] = by_symbol.get(t.tradingsymbol, 0) + 1

    qtys = [t.total_quantity or 0 for t in trades]
    return {
        "completed_trades": len(trades),
        "losing_trades": len(losses),
        "current_loss_streak": streak,
        "session_pnl": round(sum(pnls), 2),
        "largest_loss": round(min(pnls), 2) if pnls else 0,
        "last_trade_pnl": round(pnls[-1], 2),
        "most_traded_symbol": max(by_symbol, key=by_symbol.get) if by_symbol else None,
        "most_traded_count": max(by_symbol.values()) if by_symbol else 0,
        "first_qty": qtys[0] if qtys else 0,
        "last_qty": qtys[-1] if qtys else 0,
        "size_ratio_last_vs_first": round(qtys[-1] / qtys[0], 2) if qtys and qtys[0] else 0,
    }


#: The thresholds worth putting next to the facts. The full set is large and most
#: of it is irrelevant to any given question; these are the ones that decide
#: whether the common detectors speak.
_SHOWN = (
    "consecutive_loss_caution", "consecutive_loss_danger",
    "revenge_min_loss_inr", "revenge_window_caution_min",
    "rapid_reentry_min",
    "martingale_min_losses", "martingale_caution_multiplier",
    "martingale_danger_multiplier",
    "recovery_bet_caution_mul", "recovery_bet_danger_mul",
    "size_escalation_pct",
    "obsession_min_losses", "obsession_min_reentries",
    "premium_avg_down_loss_pct",
    "overconfidence_win_streak_caution", "overconfidence_size_mul_caution",
    "opening_trap_window_end_min", "opening_trap_quick_exit_min",
    "fomo_window_min", "fomo_symbols_in_window",
    "daily_trade_limit", "daily_loss_limit", "max_position_size",
    "cooldown_after_loss", "max_consecutive_losses",
)


def _relevant(thresholds: Dict[str, Any]) -> Dict[str, Any]:
    return {k: thresholds.get(k) for k in _SHOWN if k in thresholds}
