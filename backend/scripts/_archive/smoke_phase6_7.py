"""
Phase 6+7 smoke test — entry-time wiring, performance detectors, stats plumbing.

Run:  python scripts/smoke_phase6_7.py
"""
import sys
import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.behavior_engine import behavior_engine, EngineContext, RISK_DELTAS
from app.services.detector_registry import REGISTRY, BY_NAME, ALIASES
from app.services.behavior_scores_service import _driver_for, compute_scores
from app.core.trading_defaults import get_thresholds

failures = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def make_ct(pnl, entry_min=0, exit_min=10, qty=75):
    base = datetime.now(timezone.utc).replace(hour=4, minute=0, second=0, microsecond=0)
    ct = types.SimpleNamespace()
    ct.id = uuid.uuid4()
    ct.tradingsymbol = "NIFTY25JUL25000CE"
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


class PerfProfile:
    daily_loss_limit = None; daily_trade_limit = None; max_position_size = None
    cooldown_after_loss = None; max_consecutive_losses = None; restricted_windows = []
    trading_capital = None; sl_percent_futures = None; sl_percent_options = None
    risk_tolerance = "moderate"
    detected_patterns = {"baseline": {
        "sessions_analyzed": 40,
        "metrics": {
            "win_rate": {"value": 55.0, "confidence": 0.8, "n": 120},
            "profit_factor": {"value": 1.8, "confidence": 0.8, "n": 120},
        },
    }}


def make_ctx(current, priors, profile=None):
    session = types.SimpleNamespace()
    session.session_pnl = Decimal("0")
    session.peak_pnl = Decimal("0")
    session.risk_score = Decimal("0")
    session.peak_risk_score = Decimal("0")
    session.id = uuid.uuid4()
    return EngineContext(
        broker_account_id=uuid.uuid4(),
        session=session, completed_trade=current, session_trades=priors,
        active_cooldowns=[], thresholds=get_thresholds(profile or PerfProfile()),
        strategy_group=None, exit_order_types=["MKT"],
    )


# ── 1. Registry + wiring integrity ────────────────────────────────────────
print("1. Registry / wiring")
check("27 detectors", len(REGISTRY) == 27, str(len(REGISTRY)))
check("performance detectors analytics-only",
      BY_NAME["win_rate_collapse"].disposition == "analytics"
      and BY_NAME["strategy_breakdown"].disposition == "analytics")
check("position-monitor aliases versioned",
      all(k in ALIASES for k in ("overexposure", "portfolio_concentration", "holding_loser")))
check("all emitted patterns have deltas",
      all(k in RISK_DELTAS for k in ("overexposure", "portfolio_concentration",
                                     "win_rate_collapse", "strategy_breakdown", "death_spiral")))
check("entry-time patterns feed risk driver",
      _driver_for("overexposure") == "risk" and _driver_for("portfolio_concentration") == "risk")
check("performance patterns feed strategy driver",
      _driver_for("win_rate_collapse") == "strategy" and _driver_for("strategy_breakdown") == "strategy")

# ── 2. Win rate collapse (analytics-only, guarded) ────────────────────────
print("2. win_rate_collapse")
# 10 trades, 1 win = 10% vs 55% baseline -> 82% deterioration -> fires info
priors = [make_ct(-200, i * 20, i * 20 + 10) for i in range(9)]
cur = make_ct(300, 200, 210)
ev = behavior_engine._detect_win_rate_collapse(make_ctx(cur, priors))
check("collapse fires as info", ev is not None and ev.severity == "info",
      "none" if ev is None else ev.severity)
check("confidence from baseline", ev is not None and ev.confidence == 80.0)

# only 5 trades -> silent (sample guard)
ev = behavior_engine._detect_win_rate_collapse(make_ctx(make_ct(-200), priors[:4]))
check("under 8 trades -> silent", ev is None)

# low-confidence baseline -> silent
class LowConf(PerfProfile):
    detected_patterns = {"baseline": {"sessions_analyzed": 5, "metrics": {
        "win_rate": {"value": 55.0, "confidence": 0.2, "n": 15}}}}
ev = behavior_engine._detect_win_rate_collapse(make_ctx(cur, priors, LowConf()))
check("low-confidence baseline -> silent", ev is None)

# mild deterioration (55 -> 40 = 27%) -> silent (severe tier only)
priors_mild = [make_ct(-200 if i % 5 < 3 else 300, i * 20, i * 20 + 10) for i in range(10)]
# 4 wins of 10 = 40%
wins = sum(1 for t in priors_mild if float(t.realized_pnl) > 0)
ev = behavior_engine._detect_win_rate_collapse(make_ctx(priors_mild[-1], priors_mild[:-1]))
check("mild deterioration -> silent (noise guard)", ev is None, f"wins={wins}")

# ── 3. Strategy breakdown (needs BOTH signals) ────────────────────────────
print("3. strategy_breakdown")
# 10 trades: 1 small win 100, 9 losses of 300 -> WR 10%, PF 100/2700=0.04
priors = [make_ct(-300, i * 20, i * 20 + 10) for i in range(9)]
cur = make_ct(100, 200, 210)
ev = behavior_engine._detect_strategy_breakdown(make_ctx(cur, priors))
check("both signals collapsed -> fires info", ev is not None and ev.severity == "info",
      "none" if ev is None else ev.severity)
if ev:
    check("context carries both baselines",
          ev.context["baseline_win_rate"] == 55.0 and ev.context["baseline_profit_factor"] == 1.8)

# WR collapsed but PF fine (few huge wins) -> silent
priors = [make_ct(-100, i * 20, i * 20 + 10) for i in range(8)]
cur = make_ct(5000, 200, 210)  # PF = 5000/800 = 6.2
ev = behavior_engine._detect_strategy_breakdown(make_ctx(cur, priors))
check("PF healthy -> silent despite WR collapse", ev is None)

# ── 4. Scores integration: strategy driver now live ───────────────────────
print("4. Strategy driver end-to-end")
e = types.SimpleNamespace()
e.detector = "strategy_breakdown"; e.severity = "info"; e.confidence = 80.0
e.detected_at = datetime.now(timezone.utc) - timedelta(minutes=5); e.evidence = {}
s = compute_scores([e])
check("strategy_breakdown raises strategy driver", s["drivers"]["strategy"] > 0, str(s["drivers"]))

e2 = types.SimpleNamespace()
e2.detector = "portfolio_concentration"; e2.severity = "critical"; e2.confidence = 95.0
e2.detected_at = datetime.now(timezone.utc) - timedelta(minutes=2); e2.evidence = {}
s2 = compute_scores([e2])
check("concentration raises risk driver", s2["drivers"]["risk"] > 0, str(s2["drivers"]))

print()
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("RESULT: ALL PASS")
