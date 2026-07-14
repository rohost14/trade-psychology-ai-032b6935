"""
Phase 5 smoke test — driver scores, headline, death spiral. DB-free.

Run:  python scripts/smoke_phase5.py
"""
import sys
import types
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.behavior_scores_service import compute_scores, evaluate_death_spiral

failures = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def ev(detector, severity, minutes_ago=5, confidence=100.0):
    e = types.SimpleNamespace()
    e.detector = detector
    e.severity = severity
    e.confidence = confidence
    e.detected_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    e.evidence = {}
    return e


# ── 1. Empty session ──────────────────────────────────────────────────────
print("1. Quiet session")
s = compute_scores([])
check("all zeros, normal band", s["behavior_risk"] == 0 and s["band"] == "normal", str(s))

# ── 2. Driver mapping via nature ──────────────────────────────────────────
print("2. Nature -> driver mapping")
s = compute_scores([ev("revenge_trade", "danger", 5)])
check("revenge feeds tilt only", s["drivers"]["tilt"] > 0 and s["drivers"]["risk"] == 0,
      str(s["drivers"]))
s = compute_scores([ev("session_meltdown", "danger", 5)])
check("meltdown feeds risk", s["drivers"]["risk"] > 0 and s["drivers"]["tilt"] == 0)
s = compute_scores([ev("constitution_violation", "danger", 5)])
check("constitution feeds discipline", s["drivers"]["discipline"] > 0)
s = compute_scores([ev("time_of_day_bias", "caution", 5)])
check("tod bias feeds strategy", s["drivers"]["strategy"] > 0)

# ── 3. Decay (single aging mechanism, V4) ─────────────────────────────────
print("3. Exponential decay")
fresh = compute_scores([ev("martingale_behaviour", "danger", 0)])["drivers"]["risk"]
old90 = compute_scores([ev("martingale_behaviour", "danger", 90)])["drivers"]["risk"]
old270 = compute_scores([ev("martingale_behaviour", "danger", 270)])["drivers"]["risk"]
check("90min = half-life halves it", abs(old90 - fresh / 2) < 1, f"{fresh} -> {old90}")
check("270min nearly gone", old270 < fresh * 0.15, f"{old270}")

# ── 4. Suppressed events still count (§1C.8) ──────────────────────────────
print("4. Evidence never suppressed")
e = ev("revenge_trade", "danger", 5)
e.evidence = {"_suppressed": "constitution_breach"}
s = compute_scores([e])
check("suppressed revenge still raises tilt", s["drivers"]["tilt"] > 0)

# ── 5. Headline: dominant-driver, never a mean (V4) ───────────────────────
print("5. Headline aggregation")
events = [ev("revenge_trade", "critical", 1, 100),
          ev("martingale_behaviour", "critical", 1, 100),
          ev("post_loss_recovery_bet", "critical", 1, 100),
          ev("consecutive_loss_streak", "critical", 1, 100)]  # tilt+risk mix
s = compute_scores(events)
dom = max(s["drivers"].values())
check("headline >= dominant driver", s["behavior_risk"] >= dom, str(s))
check("headline <= dominant + 15% others", s["behavior_risk"] <= min(100, dom + 0.15 * 100 + 1))

# tilt 95-ish alone -> headline ~95 not average
s2 = compute_scores([ev("revenge_trade", "critical", 1), ev("martingale_behaviour", "critical", 1),
                     ev("same_symbol_obsession", "critical", 1), ev("size_escalation", "critical", 1)])
check("tilt-heavy day: headline tracks tilt, not mean of 4",
      s2["behavior_risk"] >= s2["drivers"]["tilt"], str(s2["behavior_risk"]))

# ── 6. Death spiral: state-based levels ───────────────────────────────────
print("6. Death spiral levels")
# one domain only -> None
check("1 domain -> none", evaluate_death_spiral([ev("revenge_trade", "danger", 10)]) is None)

# 2 domains, no risk domain -> warning(caution)
v = evaluate_death_spiral([ev("revenge_trade", "danger", 10),
                           ev("constitution_violation", "danger", 8)])
check("2 domains no capital risk -> warning", v is not None and v["severity"] == "caution",
      str(v and v["severity"]))

# 2 domains incl. risk -> danger
v = evaluate_death_spiral([ev("revenge_trade", "danger", 10),
                           ev("session_meltdown", "danger", 8)])
check("emotional+risk -> danger", v is not None and v["severity"] == "danger")

# 3 domains + continued escalation (later event) -> critical
v = evaluate_death_spiral([
    ev("revenge_trade", "danger", 60),
    ev("session_meltdown", "danger", 50),
    ev("constitution_violation", "danger", 45),
    ev("martingale_behaviour", "danger", 10),   # kept trading AFTER the breach
])
check("3 domains + continued escalation -> critical", v is not None and v["severity"] == "critical",
      str(v and v["severity"]))
check("evidence lists domains", v is not None and set(v["context"]["domains"]) ==
      {"emotional", "risk", "discipline"})

# trader STOPPED after breach (no later events) -> stays danger, no guardian (user V3)
v = evaluate_death_spiral([
    ev("revenge_trade", "danger", 60),
    ev("session_meltdown", "danger", 50),
    ev("constitution_violation", "danger", 45),
])
check("trader stopped -> NOT critical (the system worked)", v is not None and v["severity"] == "danger",
      str(v and v["severity"]))

# time compression: same 3 domains + escalation but spread over 5 hours -> not critical
v = evaluate_death_spiral([
    ev("revenge_trade", "danger", 340),
    ev("session_meltdown", "danger", 200),
    ev("constitution_violation", "danger", 30),
    ev("martingale_behaviour", "danger", 5),
])
check("uncompressed (5h spread) -> not critical", v is not None and v["severity"] != "critical",
      str(v and v["severity"]))

# caution-only events never form a spiral
v = evaluate_death_spiral([ev("revenge_trade", "caution", 10),
                           ev("session_meltdown", "caution", 8),
                           ev("constitution_violation", "caution", 5)])
check("caution-only -> none", v is None)

print()
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("RESULT: ALL PASS")
