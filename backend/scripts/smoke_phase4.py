"""
Phase 4 smoke test — merges, splits, confidence, analytics moves, dedup v2. DB-free.

Run:  python scripts/smoke_phase4.py
"""
import sys
import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.behavior_engine import behavior_engine, EngineContext
from app.services.detector_registry import REGISTRY, BY_NAME, ALIASES
from app.core.trading_defaults import get_thresholds
from app.tasks.trade_tasks import _worsened

failures = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def make_ct(symbol, entry_min, exit_min, qty, pnl, itype="CE", direction="LONG",
            price=100, product="MIS", pnl_pct=None):
    base = datetime.now(timezone.utc).replace(hour=4, minute=0, second=0, microsecond=0)
    ct = types.SimpleNamespace()
    ct.id = uuid.uuid4()
    ct.tradingsymbol = symbol
    ct.exchange = "NFO"
    ct.instrument_type = itype
    ct.product = product
    ct.direction = direction
    ct.total_quantity = qty
    ct.realized_pnl = Decimal(str(pnl))
    ct.entry_time = base + timedelta(minutes=entry_min)
    ct.exit_time = base + timedelta(minutes=exit_min)
    ct.avg_entry_price = Decimal(str(price))
    ct.avg_exit_price = Decimal(str(price + pnl / max(qty, 1)))
    ct.pnl_pct = pnl_pct
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


# ── 1. Registry shape ─────────────────────────────────────────────────────
print("1. Registry")
check("25 detectors (merged 2, added 2)", len(REGISTRY) == 25, str(len(REGISTRY)))
check("old names gone", all(n not in BY_NAME for n in
      ("rapid_flip", "options_direction_confusion", "iv_crush_behavior", "premium_destruction")))
check("new names present", all(n in BY_NAME for n in
      ("direction_instability", "premium_loss_event", "same_symbol_obsession", "time_of_day_bias")))
check("5 analytics dispositions (4 Phase 4 moves + cooldown_violation)",
      sum(1 for s in REGISTRY if s.disposition == "analytics") == 5,
      str([s.name for s in REGISTRY if s.disposition == "analytics"]))
check("daily_overtrading alias versioned", ALIASES.get("daily_overtrading") == "2.0.0")
check("version lookup via alias", behavior_engine._detector_version("daily_overtrading") == "2.0.0")

# ── 2. Revenge confidence ─────────────────────────────────────────────────
print("2. Revenge trade v2 (signal stacking)")
# weak: different underlying, slow-ish, session green, same size -> below gate -> info
priors = [make_ct("BANKNIFTY25JUL52000CE", 0, 10, 30, -900)]
cur = make_ct("NIFTY25JUL25000CE", 25, 40, 75, 100)
ev = behavior_engine._detect_revenge_trade(make_ctx(cur, priors, session_pnl=500))
check("weak signals -> info (recorded, no alert)", ev is not None and ev.severity == "info",
      "none" if ev is None else f"{ev.severity}/{ev.confidence}")
check("confidence stored", ev is not None and ev.confidence == 30.0,
      str(ev.confidence if ev else None))

# strong: same symbol, 2 min, bigger size, session red -> danger + high confidence
priors = [make_ct("NIFTY25JUL25000CE", 0, 10, 75, -900)]
cur = make_ct("NIFTY25JUL25000CE", 12, 30, 150, -100)
ev = behavior_engine._detect_revenge_trade(make_ctx(cur, priors, session_pnl=-1000))
check("strong signals -> danger", ev is not None and ev.severity == "danger",
      "none" if ev is None else ev.severity)
check("confidence 100 (all signals)", ev is not None and ev.confidence == 100.0,
      str(ev.confidence if ev else None))
check("evidence signals list present", ev is not None and len(ev.context.get("signals", [])) >= 5)

# ── 3. Direction instability ──────────────────────────────────────────────
print("3. Direction instability (merged)")
# L1: exact symbol reversal
priors = [make_ct("NIFTY25JULFUT", 0, 10, 50, -300, itype="FUT", direction="LONG")]
cur = make_ct("NIFTY25JULFUT", 15, 30, 50, 100, itype="FUT", direction="SHORT")
ev = behavior_engine._detect_direction_instability(make_ctx(cur, priors))
check("L1 exact reversal fires", ev is not None and ev.context.get("level") == 1,
      "none" if ev is None else str(ev.context.get("level")))
# L2: CE -> PE same underlying
priors = [make_ct("NIFTY25JUL25000CE", 0, 10, 75, -500)]
cur = make_ct("NIFTY25JUL25000PE", 14, 30, 75, 100, itype="PE")
ev = behavior_engine._detect_direction_instability(make_ctx(cur, priors))
check("L2 CE->PE flip fires", ev is not None and ev.context.get("level") == 2,
      "none" if ev is None else str(ev.context))
check("prior pnl in context", ev is not None and ev.context.get("prior_pnl") == -500.0)
# L3: 3+ flips -> danger
priors = [
    make_ct("NIFTY25JUL25000CE", 0, 5, 75, -200),
    make_ct("NIFTY25JUL25000PE", 8, 14, 75, -200, itype="PE"),
    make_ct("NIFTY25JUL25000CE", 16, 22, 75, -200),
]
cur = make_ct("NIFTY25JUL25000PE", 24, 30, 75, -200, itype="PE")
ev = behavior_engine._detect_direction_instability(make_ctx(cur, priors))
check("L3 whipsaw -> danger", ev is not None and ev.severity == "danger"
      and ev.context.get("session_flips", 0) >= 3,
      "none" if ev is None else str(ev.context.get("session_flips")))

# ── 4. Premium loss event ─────────────────────────────────────────────────
print("4. Premium loss event (merged, leveled)")
cur = make_ct("NIFTY25AUG25000CE", 0, 20, 75, -3750, pnl_pct=-50.0)  # 50% lost, fast
ev = behavior_engine._detect_premium_loss_event(make_ctx(cur, []))
check("50% -> caution + fast_collapse flag", ev is not None and ev.severity == "caution"
      and ev.context.get("fast_collapse") is True,
      "none" if ev is None else f"{ev.severity}/{ev.context.get('fast_collapse')}")
cur = make_ct("NIFTY25AUG25000CE", 0, 120, 75, -5250, pnl_pct=-70.0)
ev = behavior_engine._detect_premium_loss_event(make_ctx(cur, []))
check("70% -> danger, slow (no fast flag)", ev is not None and ev.severity == "danger"
      and ev.context.get("fast_collapse") is False)
cur = make_ct("NIFTY25AUG25000CE", 0, 60, 75, -6400, pnl_pct=-85.0)
ev = behavior_engine._detect_premium_loss_event(make_ctx(cur, []))
check("85% -> critical", ev is not None and ev.severity == "critical")
cur = make_ct("NIFTY25AUG25000CE", 0, 60, 75, -2000, pnl_pct=-30.0)
ev = behavior_engine._detect_premium_loss_event(make_ctx(cur, []))
check("30% -> no event", ev is None)

# ── 5. Daily overtrading split ────────────────────────────────────────────
print("5. daily_overtrading split")
# 10 trades spread hours apart (no burst), profitable burst suppression off via losses
priors = [make_ct(f"NIFTY25JUL2{i:02d}CE", i * 40, i * 40 + 10, 75, -100) for i in range(9)]
cur = make_ct("NIFTY25JUL2900CE", 400, 410, 75, -100)
ev = behavior_engine._detect_overtrading_burst(make_ctx(cur, priors, session_pnl=-1000))
check("daily path emits daily_overtrading", ev is not None and ev.event_type == "daily_overtrading",
      "none" if ev is None else ev.event_type)

# ── 6. Analytics moves -> info ────────────────────────────────────────────
print("6. Analytics-only severities")
priors = [make_ct("NIFTY25JUL25000CE", 0, 10, 75, -600)]
cur = make_ct("NIFTY25JUL25000CE", 12, 30, 75, 200)
ev = behavior_engine._detect_rapid_reentry(make_ctx(cur, priors))
check("rapid_reentry -> info", ev is not None and ev.severity == "info")
cur2 = make_ct("NIFTY25JUL25000CE", 0, 3, 75, -500)
ev = behavior_engine._detect_panic_exit(make_ctx(cur2, []))
check("panic_exit -> info", ev is not None and ev.severity == "info")

# ── 7. Same symbol obsession ──────────────────────────────────────────────
print("7. Same symbol obsession")
priors = [
    make_ct("BANKNIFTY25JUL52000CE", 0, 10, 30, -1500),
    make_ct("BANKNIFTY25JUL52100CE", 20, 30, 30, -2000),
    make_ct("BANKNIFTY25JUL52000CE", 40, 50, 30, -1800),
]
cur = make_ct("BANKNIFTY25JUL52200CE", 60, 70, 60, -3000)  # size doubled
ev = behavior_engine._detect_same_symbol_obsession(make_ctx(cur, priors))
check("4 losses same underlying + size rising -> danger",
      ev is not None and ev.severity == "danger" and ev.context.get("losses") == 4,
      "none" if ev is None else str(ev.context))
# different underlyings -> silent
priors2 = [make_ct("NIFTY25JUL25000CE", 0, 10, 75, -500)]
cur2 = make_ct("BANKNIFTY25JUL52000CE", 20, 30, 30, -500)
check("cross-underlying silent",
      behavior_engine._detect_same_symbol_obsession(make_ctx(cur2, priors2)) is None)

# ── 8. Time-of-day bias ───────────────────────────────────────────────────
print("8. Time-of-day bias")
class TodProfile:
    daily_loss_limit = None; daily_trade_limit = None; max_position_size = None
    cooldown_after_loss = None; max_consecutive_losses = None; restricted_windows = []
    trading_capital = None; sl_percent_futures = None; sl_percent_options = None
    risk_tolerance = "moderate"
    detected_patterns = {
        "time_patterns": {"danger_hours": [{"hour": 13, "win_rate": 22.0, "trades": 18, "avg_pnl": -840.0}]},
        "baseline": {"sessions_analyzed": 45, "metrics": {}},
    }
base = datetime.now(timezone.utc).replace(hour=7, minute=45, second=0, microsecond=0)  # 13:15 IST
ct_tod = make_ct("NIFTY25JUL25000CE", 0, 20, 75, -300)
ct_tod.entry_time = base
ctx_tod = make_ctx(ct_tod, [])
ctx_tod.thresholds = get_thresholds(TodProfile())
ev = behavior_engine._detect_time_of_day_bias(ctx_tod)
check("entry in danger hour fires with history", ev is not None and
      ev.context.get("entry_hour_ist") == 13, "none" if ev is None else str(ev.context))
TodProfile.detected_patterns = {**TodProfile.detected_patterns,
                                "baseline": {"sessions_analyzed": 10, "metrics": {}}}
ctx_tod2 = make_ctx(ct_tod, [])
ctx_tod2.thresholds = get_thresholds(TodProfile())
check("under 30 sessions -> silent", behavior_engine._detect_time_of_day_bias(ctx_tod2) is None)

# ── 9. MIS panic profitable suppression ───────────────────────────────────
print("9. MIS panic suppression")
base_1502 = datetime.now(timezone.utc).replace(hour=9, minute=32, second=0, microsecond=0)  # 15:02 IST
p1 = make_ct("NIFTY25JUL25000CE", 0, 5, 75, 400)
p1.entry_time = base_1502
p1.exit_time = base_1502 + timedelta(minutes=5)
c1 = make_ct("NIFTY25JUL25100CE", 0, 6, 75, 300)
c1.entry_time = base_1502 + timedelta(minutes=6)
c1.exit_time = base_1502 + timedelta(minutes=12)
ev = behavior_engine._detect_end_of_session_mis_panic(make_ctx(c1, [p1], session_pnl=700))
check("all late MIS profitable + green session -> suppressed", ev is None,
      "none" if ev is None else f"{ev.severity}")
c2 = make_ct("NIFTY25JUL25100CE", 0, 6, 75, -300)
c2.entry_time = base_1502 + timedelta(minutes=6)
c2.exit_time = base_1502 + timedelta(minutes=12)
ev = behavior_engine._detect_end_of_session_mis_panic(make_ctx(c2, [p1], session_pnl=-200))
check("losing late MIS still fires", ev is not None and ev.severity == "caution")

# ── 10. Dedup v2 worsening re-arm ─────────────────────────────────────────
print("10. Dedup v2 re-arm")
check("martingale 1.5x -> 2.0x re-arms", _worsened("martingale_behaviour",
      {"max_ratio": 1.5}, {"max_ratio": 2.0}))
check("martingale 1.5x -> 1.6x stays deduped", not _worsened("martingale_behaviour",
      {"max_ratio": 1.5}, {"max_ratio": 1.6}))
check("unlisted pattern never re-arms", not _worsened("revenge_trade",
      {"gap_minutes": 5}, {"gap_minutes": 1}))
check("constitution ratio worsening re-arms", _worsened("constitution_violation",
      {"ratio": 0.85}, {"ratio": 1.1}))

print()
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("RESULT: ALL PASS")
