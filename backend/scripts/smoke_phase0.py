"""
Phase 0 smoke test — validates detector changes without a DB connection.

Exercises:
  1. consecutive_loss_streak → losing_trades entries carry exit_time_ist
  2. martingale_behaviour     → trade_list present, same-underlying only
  3. post_loss_recovery_bet   → prior_trades present
  4. rapid_reentry            → prior_exit_time_ist / reentry_time_ist keys
  5. overtrading_burst        → burst_trades + window fields (regression)
  6. severity ranks include "critical" in engine options-dedup

Run:  python scripts/smoke_phase0.py
"""
import sys
import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.behavior_engine import behavior_engine, EngineContext, ENGINE_VERSION
from app.core.trading_defaults import get_thresholds

IST_OFFSET = timedelta(hours=5, minutes=30)


def make_ct(symbol, entry_min, exit_min, qty, pnl, base=None):
    """Fake CompletedTrade-like object. Times = minutes after 09:15 IST today."""
    base = base or datetime.now(timezone.utc).replace(hour=3, minute=45, second=0, microsecond=0)
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
    ct.avg_exit_price = Decimal("100") + (Decimal(str(pnl)) / max(qty, 1))
    ct.pnl_pct = float(pnl) / (100.0 * qty) * 100 if qty else 0
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
        broker_account_id=uuid.uuid4(),
        session=session,
        completed_trade=current,
        session_trades=priors,
        active_cooldowns=[],
        thresholds=get_thresholds(None),
        strategy_group=None,
        exit_order_types=["MKT"],
    )


failures = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


print(f"ENGINE_VERSION = {ENGINE_VERSION}\n")

# ── 1. consecutive_loss_streak ────────────────────────────────────────────
print("1. consecutive_loss_streak")
priors = [
    make_ct("NIFTY25JUL25000CE", 0, 10, 75, -500),
    make_ct("NIFTY25JUL25000CE", 15, 25, 75, -600),
]
cur = make_ct("NIFTY25JUL25100CE", 30, 40, 75, -700)
ev = behavior_engine._detect_consecutive_loss_streak(make_ctx(cur, priors))
check("fires at 3 losses", ev is not None and ev.severity == "caution")
if ev:
    lt = ev.context.get("losing_trades", [])
    check("losing_trades has 3 entries", len(lt) == 3, f"got {len(lt)}")
    check("entries carry exit_time_ist", all(e.get("exit_time_ist") for e in lt),
          str(lt))

# ── 2. martingale_behaviour ───────────────────────────────────────────────
print("2. martingale_behaviour")
priors = [
    make_ct("NIFTY25JUL25000CE", 0, 10, 75, -500),
    make_ct("NIFTY25JUL25000CE", 15, 25, 150, -900),
    make_ct("NIFTY25JUL25100CE", 30, 40, 300, -1500),
]
cur = make_ct("NIFTY25JUL25100CE", 45, 55, 300, -400)
ev = behavior_engine._detect_martingale_behaviour(make_ctx(cur, priors))
check("fires on 2x sizing after losses", ev is not None and ev.severity == "danger",
      "no event" if ev is None else ev.severity)
if ev:
    tl = ev.context.get("trade_list", [])
    check("trade_list present (4 entries: 3 prior + current)", len(tl) == 4, f"got {len(tl)}")
    check("trade_list entries carry pnl + exit_time_ist",
          all("pnl" in e and "exit_time_ist" in e for e in tl))

# cross-underlying control: BANKNIFTY priors must NOT count for NIFTY trade
priors_mixed = [
    make_ct("BANKNIFTY25JUL52000CE", 0, 10, 30, -500),
    make_ct("BANKNIFTY25JUL52000CE", 15, 25, 60, -900),
    make_ct("BANKNIFTY25JUL52000CE", 30, 40, 120, -1500),
]
cur = make_ct("NIFTY25JUL25100CE", 45, 55, 300, -400)
ev = behavior_engine._detect_martingale_behaviour(make_ctx(cur, priors_mixed))
check("does NOT fire cross-underlying", ev is None, f"fired: {ev.message if ev else ''}")

# ── 3. post_loss_recovery_bet ─────────────────────────────────────────────
print("3. post_loss_recovery_bet")
priors = [
    make_ct("BANKNIFTY25JUL52000CE", 0, 5, 30, 300),    # unrelated early trade (session count gate needs 3+)
    make_ct("NIFTY25JUL25000CE", 6, 12, 75, -800),
    make_ct("NIFTY25JUL25000CE", 15, 25, 75, -900),
]
cur = make_ct("NIFTY25JUL25100CE", 30, 40, 375, -100)   # 5x avg(75) after 2 NIFTY losses
ev = behavior_engine._detect_post_loss_recovery_bet(make_ctx(cur, priors))
check("fires on 5x recovery bet", ev is not None and ev.severity == "danger",
      "no event" if ev is None else ev.severity)
if ev:
    pt = ev.context.get("prior_trades", [])
    check("prior_trades present", len(pt) >= 2, f"got {len(pt)}")
    check("prior_trades carry exit_time_ist", all("exit_time_ist" in e for e in pt))

# ── 4. rapid_reentry ──────────────────────────────────────────────────────
print("4. rapid_reentry")
priors = [make_ct("NIFTY25JUL25000CE", 0, 10, 75, -600)]
cur = make_ct("NIFTY25JUL25000CE", 12, 30, 75, 200)   # re-entry 2 min after loss exit
ev = behavior_engine._detect_rapid_reentry(make_ctx(cur, priors))
check("fires on 2-min re-entry after loss", ev is not None)
if ev:
    check("context has prior_exit_time_ist + reentry_time_ist",
          ev.context.get("prior_exit_time_ist") and ev.context.get("reentry_time_ist"),
          str(ev.context))

# ── 5. overtrading_burst (regression from cd33514) ────────────────────────
print("5. overtrading_burst")
priors = [make_ct(f"NIFTY25JUL2500{i}CE", i * 4, i * 4 + 3, 75, -100) for i in range(4)]
cur = make_ct("NIFTY25JUL25050CE", 20, 24, 75, -100)
ev = behavior_engine._detect_overtrading_burst(make_ctx(cur, priors, session_pnl=-500))
check("fires at 5 trades in 30 min", ev is not None)
if ev:
    check("burst_trades list present", len(ev.context.get("burst_trades", [])) == 5,
          f"got {len(ev.context.get('burst_trades', []))}")
    check("window fields present",
          ev.context.get("window_start_ist") and ev.context.get("window_end_ist"))

# ── 6. severity rank includes critical ────────────────────────────────────
print("6. severity ranks")
import inspect
src = inspect.getsource(behavior_engine._run_all_detectors)
check("engine options-dedup ranks critical", '"critical": 0' in src)
from app.tasks import trade_tasks as tt
src2 = inspect.getsource(tt)
check("trade_tasks sev ranks include critical", src2.count('"critical": 3') == 2)
check("staleness gate present in both paths", src2.count("alert_stale_push_min") >= 2)

print()
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("RESULT: ALL PASS")
