"""
Phase 2 smoke test — constitution service semantics + violation detector, DB-free.

Run:  python scripts/smoke_phase2.py
"""
import sys
import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.behavior_engine import behavior_engine, EngineContext
from app.services.constitution_service import classify_change, ConstitutionService
from app.services.detector_registry import REGISTRY, BY_NAME
from app.core.trading_defaults import get_thresholds
from app.tasks.trade_tasks import _pattern_dedup_key

failures = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def make_ct(symbol, entry_min, exit_min, qty, pnl, price=100):
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
    ct.avg_entry_price = Decimal(str(price))
    ct.avg_exit_price = Decimal(str(price))
    ct.pnl_pct = 0
    ct.duration_minutes = exit_min - entry_min
    return ct


class FakeProfile:
    daily_loss_limit = 5000.0
    daily_trade_limit = 10
    max_position_size = 5.0
    cooldown_after_loss = 15
    max_consecutive_losses = 3
    restricted_windows = ["13:00-14:00"]
    trading_capital = 500000.0
    sl_percent_futures = 1.0
    sl_percent_options = 50.0
    risk_tolerance = "moderate"
    detected_patterns = {}


def make_ctx(current, priors, session_pnl=0, profile=None):
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
        thresholds=get_thresholds(profile or FakeProfile()),
        strategy_group=None,
        exit_order_types=["MKT"],
    )


# ── 1. classify_change semantics ──────────────────────────────────────────
print("1. classify_change (§1C.3)")
check("lower loss limit = tighten", classify_change("daily_loss_limit", 5000, 3000) == "tighten")
check("higher loss limit = loosen", classify_change("daily_loss_limit", 5000, 8000) == "loosen")
check("longer cooldown = tighten", classify_change("cooldown_after_loss", 10, 20) == "tighten")
check("shorter cooldown = loosen", classify_change("cooldown_after_loss", 20, 10) == "loosen")
check("adding rule = tighten", classify_change("max_consecutive_losses", None, 3) == "tighten")
check("removing rule = loosen", classify_change("daily_loss_limit", 5000, None) == "loosen")
check("no change = None", classify_change("daily_trade_limit", 10, 10) is None)
check("adding window = tighten", classify_change("restricted_windows", ["13:00-14:00"], ["13:00-14:00", "09:15-09:30"]) == "tighten")
check("removing window = loosen", classify_change("restricted_windows", ["13:00-14:00"], []) == "loosen")

# ── 2. generate_defaults ──────────────────────────────────────────────────
print("2. Onboarding defaults (§1C.5)")
d = ConstitutionService.generate_defaults("beginner", 100000)
check("beginner: 2% loss, 5 trades, 15min cd, 3 consec, 1% risk",
      d == {"daily_loss_limit": 2000, "daily_trade_limit": 5, "cooldown_after_loss": 15,
            "max_consecutive_losses": 3, "max_position_size": 1.0, "restricted_windows": []}, str(d))
d2 = ConstitutionService.generate_defaults("professional", None)
check("no capital -> no loss limit, behavior defaults still set",
      d2["daily_loss_limit"] is None and d2["daily_trade_limit"] == 20, str(d2))

# ── 3. Registry ───────────────────────────────────────────────────────────
print("3. Registry")
check("27 detectors now (Phase 7 end-state)", len(REGISTRY) == 27, f"got {len(REGISTRY)}")
spec = BY_NAME["constitution_violation"]
check("constitution: discipline/alerting/level4/guardian",
      spec.nature == "discipline" and spec.disposition == "alerting"
      and spec.notification_level == 4 and spec.guardian_eligible)

# ── 4. Violation detector: ladder ─────────────────────────────────────────
print("4. Ladder (80/100/120 — §1C.4)")
# daily loss approaching: loss 4100 of 5000 = 82%
priors = [make_ct("NIFTY25JUL25000CE", 0, 10, 75, -4000)]
cur = make_ct("NIFTY25JUL25100CE", 60, 70, 75, -100)
events = behavior_engine._detect_constitution_violation(make_ctx(cur, priors, session_pnl=-4100)) or []
dl = [e for e in events if e.context.get("rule") == "daily_loss"]
check("approaching 82% -> caution", len(dl) == 1 and dl[0].severity == "caution",
      str([(e.context.get('rule'), e.severity) for e in events]))

events = behavior_engine._detect_constitution_violation(make_ctx(cur, priors, session_pnl=-5400)) or []
dl = [e for e in events if e.context.get("rule") == "daily_loss"]
check("breached 108% -> danger", len(dl) == 1 and dl[0].severity == "danger")

events = behavior_engine._detect_constitution_violation(make_ctx(cur, priors, session_pnl=-6500)) or []
dl = [e for e in events if e.context.get("rule") == "daily_loss"]
check("severe 130% -> critical", len(dl) == 1 and dl[0].severity == "critical")

events = behavior_engine._detect_constitution_violation(make_ctx(cur, priors, session_pnl=-1000)) or []
dl = [e for e in events if e.context.get("rule") == "daily_loss"]
check("below 80% -> no daily_loss event", len(dl) == 0)

# ── 5. Cooldown rule (binary) ─────────────────────────────────────────────
print("5. Cooldown rule")
priors = [make_ct("NIFTY25JUL25000CE", 0, 10, 75, -1000)]
cur = make_ct("NIFTY25JUL25100CE", 15, 30, 75, 100)  # entered 5 min after loss, cooldown 15
events = behavior_engine._detect_constitution_violation(make_ctx(cur, priors)) or []
cd = [e for e in events if e.context.get("rule") == "cooldown"]
check("entry 5min after loss with 15min rule -> danger", len(cd) == 1 and cd[0].severity == "danger")

cur2 = make_ct("NIFTY25JUL25100CE", 30, 45, 75, 100)  # entered 20 min after -> ok
events = behavior_engine._detect_constitution_violation(make_ctx(cur2, priors)) or []
cd = [e for e in events if e.context.get("rule") == "cooldown"]
check("entry 20min after loss -> no violation", len(cd) == 0)

# ── 6. Multi-rule: consec losses + trade count together ───────────────────
print("6. Multi-rule list")
priors = [make_ct(f"NIFTY25JUL2{i}CE", i * 20, i * 20 + 10, 75, -500) for i in range(9)]
cur = make_ct("NIFTY25JUL25100CE", 200, 210, 75, -500)  # 10th trade, 10 consecutive losses
events = behavior_engine._detect_constitution_violation(make_ctx(cur, priors, session_pnl=-5000)) or []
rules = {e.context.get("rule") for e in events}
check("multiple rules fire in one pass",
      {"daily_trades", "max_consecutive_losses", "daily_loss"} <= rules, str(rules))

# ── 7. Constitution suppression of paired behavioral patterns ─────────────
print("7. Constitution breach suppresses paired notifications (§1C.8)")
all_events = behavior_engine._run_all_detectors(make_ctx(cur, priors, session_pnl=-5000))
streak = [e for e in all_events if e.event_type == "consecutive_loss_streak"]
check("consecutive_loss_streak event still recorded", len(streak) == 1)
if streak:
    check("...but suppressed by constitution breach",
          streak[0].suppressed_reason == "constitution_breach", str(streak[0].suppressed_reason))
cv = [e for e in all_events if e.event_type == "constitution_violation"
      and e.context.get("rule") == "max_consecutive_losses"]
check("constitution event NOT suppressed", len(cv) == 1 and not cv[0].suppressed_reason)

# ── 8. No profile -> no constitution events ───────────────────────────────
print("8. No declared rules -> silent")
class EmptyProfile:
    daily_loss_limit = None; daily_trade_limit = None; max_position_size = None
    cooldown_after_loss = None; max_consecutive_losses = None; restricted_windows = []
    trading_capital = None; sl_percent_futures = None; sl_percent_options = None
    risk_tolerance = "moderate"; detected_patterns = {}
events = behavior_engine._detect_constitution_violation(
    make_ctx(cur, priors, session_pnl=-50000, profile=EmptyProfile()))
check("no rules declared -> None", events is None)

# ── 9. Dedup key ──────────────────────────────────────────────────────────
print("9. Rule-aware dedup key")
check("constitution key includes rule",
      _pattern_dedup_key("constitution_violation", {"rule": "cooldown"}) == "constitution_violation:cooldown")
check("other patterns unchanged", _pattern_dedup_key("revenge_trade", {"x": 1}) == "revenge_trade")

# ── 10. Restricted window ─────────────────────────────────────────────────
print("10. Restricted window")
base = datetime.now(timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0)  # 13:30 IST
ct_w = make_ct("NIFTY25JUL25100CE", 0, 10, 75, 100)
ct_w.entry_time = base  # 13:30 IST inside 13:00-14:00
events = behavior_engine._detect_constitution_violation(make_ctx(ct_w, [])) or []
rw = [e for e in events if e.context.get("rule") == "restricted_window"]
check("entry inside declared window -> danger", len(rw) == 1 and rw[0].severity == "danger",
      str([(e.context.get('rule'), e.severity) for e in events]))

print()
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("RESULT: ALL PASS")
