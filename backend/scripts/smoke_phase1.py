"""
Phase 1 smoke test — registry, BehaviorEvent emission, SessionState, DB-free.

Run:  python scripts/smoke_phase1.py
"""
import sys
import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.behavior_engine import behavior_engine, EngineContext, DetectedEvent
from app.services.detector_registry import REGISTRY, BY_NAME
from app.services.state.session_state import SessionState
from app.core.trading_defaults import get_thresholds

failures = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def make_ct(symbol, entry_min, exit_min, qty, pnl):
    base = datetime.now(timezone.utc).replace(hour=3, minute=45, second=0, microsecond=0)
    ct = types.SimpleNamespace()
    ct.id = uuid.uuid4()
    ct.tradingsymbol = symbol
    ct.exchange = "NFO"
    ct.instrument_type = "CE"
    ct.product = "MIS"
    ct.direction = "LONG"
    ct.total_quantity = qty
    ct.realized_pnl = Decimal(str(pnl))
    ct.entry_time = base + timedelta(minutes=entry_min)
    ct.exit_time = base + timedelta(minutes=exit_min)
    ct.avg_entry_price = Decimal("100")
    ct.avg_exit_price = Decimal("100")
    ct.pnl_pct = 0
    ct.duration_minutes = exit_min - entry_min
    return ct


def make_ctx(current, priors, session_pnl=0, strategy_group=None):
    session = types.SimpleNamespace()
    session.session_pnl = Decimal(str(session_pnl))
    session.peak_pnl = Decimal("0")
    session.risk_score = Decimal("0")
    session.peak_risk_score = Decimal("0")
    session.id = uuid.uuid4()
    return EngineContext(
        broker_account_id=uuid.uuid4(),
        session=session,
        completed_trade=current,
        session_trades=priors,
        active_cooldowns=[],
        thresholds=get_thresholds(None),
        strategy_group=strategy_group,
        exit_order_types=["MKT"],
    )


# ── 1. Registry integrity ─────────────────────────────────────────────────
print("1. Detector registry")
check("25 detectors registered (24 + constitution_violation)", len(REGISTRY) == 25, f"got {len(REGISTRY)}")
check("all registry methods exist on engine",
      all(hasattr(behavior_engine, s.method) for s in REGISTRY),
      str([s.method for s in REGISTRY if not hasattr(behavior_engine, s.method)]))
check("names unique", len(BY_NAME) == len(REGISTRY))
check("natures valid", all(s.nature in ("emotional", "risk", "discipline", "performance") for s in REGISTRY))
check("dispositions valid", all(s.disposition in ("alerting", "analytics") for s in REGISTRY))
check("guardian only where level 4",
      all((s.notification_level == 4) == s.guardian_eligible for s in REGISTRY))
check("session_meltdown is guardian-eligible", BY_NAME["session_meltdown"].guardian_eligible)
check("cooldown_violation analytics/level 0",
      BY_NAME["cooldown_violation"].disposition == "analytics"
      and BY_NAME["cooldown_violation"].notification_level == 0)

# ── 2. Registry-driven loop fires detectors ───────────────────────────────
print("2. Registry-driven detector loop")
priors = [
    make_ct("NIFTY25JUL25000CE", 0, 10, 75, -500),
    make_ct("NIFTY25JUL25000CE", 15, 25, 75, -600),
]
cur = make_ct("NIFTY25JUL25100CE", 30, 40, 75, -700)
events = behavior_engine._run_all_detectors(make_ctx(cur, priors, session_pnl=-1800))
fired = {e.event_type for e in events}
check("consecutive_loss_streak fires via registry", "consecutive_loss_streak" in fired, str(fired))

# ── 3. Strategy suppression marks, not drops ──────────────────────────────
print("3. Suppression = flag, not drop (§1C.8)")
sg = types.SimpleNamespace()
sg.strategy_type = "straddle"
events_sg = behavior_engine._run_all_detectors(make_ctx(cur, priors, session_pnl=-1800, strategy_group=sg))
streak_events = [e for e in events_sg if e.event_type == "consecutive_loss_streak"]
check("suppressed event still present", len(streak_events) == 1, str(len(streak_events)))
if streak_events:
    check("suppressed_reason set", streak_events[0].suppressed_reason == "strategy_group:straddle",
          str(streak_events[0].suppressed_reason))

# ── 4. DetectedEvent new fields ───────────────────────────────────────────
print("4. DetectedEvent shape")
ev = DetectedEvent(event_type="x", severity="caution", message="m")
check("confidence defaults None", ev.confidence is None)
check("suppressed_reason defaults None", ev.suppressed_reason is None)

# ── 5. SessionState fold + rebuild parity ─────────────────────────────────
print("5. SessionState rebuild == incremental (§1B.1 property)")
trades = [
    make_ct("NIFTY25JUL25000CE", 0, 10, 75, -500),
    make_ct("NIFTY25JUL25000CE", 15, 25, 75, 800),
    make_ct("BANKNIFTY25JUL52000CE", 30, 45, 30, -300),
    make_ct("NIFTY25JUL25100CE", 50, 60, 75, -200),
]
incremental = SessionState()
for t in trades:
    incremental.update(t)
rebuilt = SessionState.rebuild(list(reversed(trades)))  # rebuild sorts internally
check("session_pnl identical", incremental.session_pnl == rebuilt.session_pnl == Decimal("-200"))
check("peak_pnl identical", incremental.peak_pnl == rebuilt.peak_pnl == Decimal("300"))
check("consecutive_losses identical", incremental.consecutive_losses == rebuilt.consecutive_losses == 2)
check("winners/losers identical",
      (incremental.winners, incremental.losers) == (rebuilt.winners, rebuilt.losers) == (1, 3))
check("drawdown identical", incremental.drawdown_from_peak == rebuilt.drawdown_from_peak == Decimal("500"))

# ── 6. Detector version resolution ────────────────────────────────────────
print("6. Detector versioning (A.2)")
check("registry version resolves", behavior_engine._detector_version("overtrading_burst") == "1.1.0")
check("unknown falls back to engine version",
      behavior_engine._detector_version("nonexistent") == "1.1.0")

# ── 7. BehaviorEvent model shape ──────────────────────────────────────────
print("7. BehaviorEvent model")
from app.models.behavior_event import BehaviorEvent
cols = {c.name for c in BehaviorEvent.__table__.columns}
required = {"detector", "detector_version", "severity", "confidence", "data_quality",
            "evidence", "input_snapshot", "trigger_completed_trade_id", "risk_alert_id", "detected_at"}
check("all v2 columns present", required <= cols, str(required - cols))
check("table name is behavior_events (not legacy)", BehaviorEvent.__tablename__ == "behavior_events")

print()
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("RESULT: ALL PASS")
