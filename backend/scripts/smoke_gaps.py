"""
Gap-fixes smoke test (user's 9-point review). DB-free.

Run:  python scripts/smoke_gaps.py
"""
import sys
import types
import uuid
import inspect
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.behavior_engine import behavior_engine, EngineContext
from app.core.trading_defaults import get_thresholds
from app.tasks.trade_tasks import _worsened, _WORSEN_METRIC

failures = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def make_ct(symbol, entry_min, exit_min, qty, pnl):
    base = datetime.now(timezone.utc).replace(hour=4, minute=0, second=0, microsecond=0)
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
    ct.pnl_pct = None
    ct.duration_minutes = exit_min - entry_min
    return ct


def make_ctx(current, priors, session_pnl=0):
    session = types.SimpleNamespace()
    session.session_pnl = Decimal(str(session_pnl))
    session.peak_pnl = Decimal("0")
    session.risk_score = Decimal("0")
    session.peak_risk_score = Decimal("0")
    session.id = uuid.uuid4()
    return EngineContext(
        broker_account_id=uuid.uuid4(), session=session, completed_trade=current,
        session_trades=priors, active_cooldowns=[], thresholds=get_thresholds(None),
        strategy_group=None, exit_order_types=["MKT"],
    )


# ── 1. Green-to-red tier (gap #2) ─────────────────────────────────────────
print("1. Green-to-red")
# peak +12000 (2 wins), then losses drive session to -4000
priors = [make_ct("NIFTY25JUL25000CE", 0, 10, 75, 7000),
          make_ct("NIFTY25JUL25100CE", 15, 25, 75, 5000),
          make_ct("NIFTY25JUL25200CE", 30, 40, 75, -9000)]
cur = make_ct("NIFTY25JUL25300CE", 50, 60, 75, -7000)
ev = behavior_engine._detect_profit_giveaway(make_ctx(cur, priors))
check("sign flip fires danger", ev is not None and ev.severity == "danger",
      "none" if ev is None else ev.severity)
check("distinct narrative (turned from profit to loss)",
      ev is not None and "turned from profit to loss" in ev.message, ev.message if ev else "")
check("sign_flip flag in context", ev is not None and ev.context.get("sign_flip") is True)

# plain 60% giveback still uses the original message
priors2 = [make_ct("A25JUL100CE", 0, 10, 75, 10000)]
cur2 = make_ct("B25JUL100CE", 20, 30, 75, -6000)
ev2 = behavior_engine._detect_profit_giveaway(make_ctx(cur2, priors2))
check("plain giveback keeps original message", ev2 is not None and "given back" in ev2.message
      and not ev2.context.get("sign_flip"), ev2.message if ev2 else "none")

# ── 2. Giveaway re-arm (gap #1 nit) ───────────────────────────────────────
print("2. Giveaway worsening re-arm")
check("profit_giveaway in worsen map", _WORSEN_METRIC.get("profit_giveaway") == "erosion_pct")
check("0.5 -> 0.75 erosion re-fires", _worsened("profit_giveaway",
      {"erosion_pct": 0.5}, {"erosion_pct": 0.75}))
check("0.5 -> 0.55 stays deduped", not _worsened("profit_giveaway",
      {"erosion_pct": 0.5}, {"erosion_pct": 0.55}))

# ── 3. Notification merge (gap #4) ────────────────────────────────────────
print("3. Cross-pattern notification merge")
from app.tasks import trade_tasks as tt
src = inspect.getsource(tt.run_risk_detection_async)
check("merged push path exists", "merged_alerts" in src and "notifications_merged" in src)
check("guardian-eligible still individual", "guardian_alerts" in src
      and "send_danger_alert.delay" in src)
check("fallback to individual on merge failure", "falling back" in src)

# ── 4. Capital reality task (the capital gap) ─────────────────────────────
print("4. Capital-vs-margin validation")
from app.tasks import maintenance_tasks as mt
csrc = inspect.getsource(mt._capital_reality)
check("compares declared vs snapshot deployable", "equity_available" in csrc and "equity_used" in csrc)
check("persistence streak, not single reading", "STREAK_NEEDED" in csrc and "incr(streak_key)" in csrc)
check("never auto-overwrites (nudge alert only)", "capital_mismatch" in csrc
      and "trading_capital =" not in csrc.replace("prof.trading_capital or", ""))
check("7-day nudge dedup", "days=7" in csrc)
from app.core.celery_app import celery_app
check("nightly beat registered", "check-capital-reality" in celery_app.conf.beat_schedule)

# ── 5. Tilt recovery (gap #3) ─────────────────────────────────────────────
print("5. Tilt recovery recognition")
tsrc = inspect.getsource(mt._tilt_recovery)
check("requires zero trades after alert", "entry_time > last_alert.detected_at" in tsrc)
check("skips if trader kept trading", "kept trading" in tsrc)
check("once per day", 'detector == "tilt_recovery"' in tsrc)
check("evidence row + push, NOT a score credit", "BehaviorEvent" in tsrc
      and "push_service" in tsrc and "score" not in tsrc.lower().replace("scores always", ""))
check("EOD beat registered (16:00 IST)", "recognize-tilt-recovery" in celery_app.conf.beat_schedule)

# ── 6. Frontend + endpoint (gaps #5, #8) ──────────────────────────────────
print("6. Evidence rendering + response stats")
sheet = Path("../src/components/alerts/AlertDetailSheet.tsx").read_text(encoding="utf-8")
check("Why-this-fired block renders signals", "Why this fired" in sheet and "d.signals" in sheet)
risk_src = Path("app/api/risk.py").read_text(encoding="utf-8")
check("alert-response-stats endpoint", "alert-response-stats" in risk_src and '"ignored"' in risk_src)

print()
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("RESULT: ALL PASS")
