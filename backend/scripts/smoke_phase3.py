"""
Phase 3 smoke test — baseline confidence blend math, DB-free.

Run:  python scripts/smoke_phase3.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.trading_defaults import get_thresholds, COLD_START_DEFAULTS

failures = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


class P:
    """Profile stub with a Phase 3 baseline."""
    daily_loss_limit = None
    daily_trade_limit = None
    max_position_size = None
    cooldown_after_loss = None
    max_consecutive_losses = None
    restricted_windows = []
    trading_capital = None
    sl_percent_futures = None
    sl_percent_options = None
    risk_tolerance = "moderate"
    detected_patterns: dict = {}


# ── 1. Full-confidence scalper: thresholds follow THEIR normal ────────────
print("1. Scalper, confidence 1.0 (their numbers win)")
p = P()
p.detected_patterns = {"baseline": {"metrics": {
    "avg_daily_trades": {"value": 25.0, "confidence": 1.0, "n": 60},
    "median_reentry_after_loss_min": {"value": 4.0, "confidence": 1.0, "n": 200},
}}}
t = get_thresholds(p)
check("daily limit = 25*1.5 = 38", t["daily_trade_limit"] == 38, str(t["daily_trade_limit"]))
check("danger = limit*1.5 = 57", t["daily_trade_danger"] == 57, str(t["daily_trade_danger"]))
check("burst caution = 25/4 ~ 6", t["burst_trades_per_30min_caution"] == 6, str(t["burst_trades_per_30min_caution"]))
check("revenge window = max(5, 4*0.5) = 5", t["revenge_window_caution_min"] == 5.0, str(t["revenge_window_caution_min"]))

# ── 2. Zero confidence: pure defaults ─────────────────────────────────────
print("2. Confidence 0 (defaults win)")
p2 = P()
p2.detected_patterns = {"baseline": {"metrics": {
    "avg_daily_trades": {"value": 25.0, "confidence": 0.0, "n": 1},
}}}
t2 = get_thresholds(p2)
check("daily limit stays default 7", t2["daily_trade_limit"] == COLD_START_DEFAULTS["daily_trade_limit"], str(t2["daily_trade_limit"]))
check("burst stays default 5", t2["burst_trades_per_30min_caution"] == 5, str(t2["burst_trades_per_30min_caution"]))

# ── 3. Half confidence: midpoint blend ────────────────────────────────────
print("3. Confidence 0.5 (blend)")
p3 = P()
p3.detected_patterns = {"baseline": {"metrics": {
    "avg_daily_trades": {"value": 25.0, "confidence": 0.5, "n": 15},
}}}
t3 = get_thresholds(p3)
# 0.5*37.5 + 0.5*7 = 22.25 -> 22
check("daily limit ~ 22 (0.5*37.5 + 0.5*7)", t3["daily_trade_limit"] == 22, str(t3["daily_trade_limit"]))

# ── 4. Positional trader: thresholds tighten below default? No — floors ──
print("4. Positional trader (2/day, full conf)")
p4 = P()
p4.detected_patterns = {"baseline": {"metrics": {
    "avg_daily_trades": {"value": 2.0, "confidence": 1.0, "n": 60},
    "median_reentry_after_loss_min": {"value": 90.0, "confidence": 1.0, "n": 120},
}}}
t4 = get_thresholds(p4)
check("daily limit = 3 (2*1.5)", t4["daily_trade_limit"] == 3, str(t4["daily_trade_limit"]))
check("burst floor holds at 3 (universal floor)", t4["burst_trades_per_30min_caution"] == 3, str(t4["burst_trades_per_30min_caution"]))
check("revenge window widens to 45 (90*0.5)", t4["revenge_window_caution_min"] == 45.0, str(t4["revenge_window_caution_min"]))

# ── 5. Legacy flat baseline still honored ─────────────────────────────────
print("5. Legacy flat baseline fallback")
p5 = P()
p5.detected_patterns = {"baseline": {"daily_trade_limit": 12}}
t5 = get_thresholds(p5)
check("flat key applied directly", t5["daily_trade_limit"] == 12, str(t5["daily_trade_limit"]))

# ── 6. Constitution still beats baseline (hierarchy) ──────────────────────
print("6. Constitution > baseline")
p6 = P()
p6.daily_trade_limit = 10
p6.detected_patterns = {"baseline": {"metrics": {
    "avg_daily_trades": {"value": 25.0, "confidence": 1.0, "n": 60},
}}}
t6 = get_thresholds(p6)
# user declared 10; baseline said 38; min(user, current) -> 10
check("user-declared 10 caps the adaptive 38", t6["daily_trade_limit"] == 10, str(t6["daily_trade_limit"]))

# ── 7. Giveaway floor scales with capital ─────────────────────────────────
print("7. profit_giveaway_min_peak capital scaling")
p7 = P()
p7.trading_capital = 1000000.0
t7 = get_thresholds(p7)
check("Rs10L capital -> floor 2000 (0.2%)", t7["profit_giveaway_min_peak"] == 2000.0, str(t7["profit_giveaway_min_peak"]))
p8 = P()
p8.trading_capital = 200000.0
t8 = get_thresholds(p8)
check("Rs2L capital -> floor stays 1000 (default higher)", t8["profit_giveaway_min_peak"] == 1000, str(t8["profit_giveaway_min_peak"]))

print()
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("RESULT: ALL PASS")
