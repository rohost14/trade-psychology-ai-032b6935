"""
Derive the global constants from the tradebook instead of citing them.

    python tradedesk/scripts/derive_constants.py docs/tradebook-...-replay.json

Reads the replay sidecar and answers four questions from the same year of real
trades. This is the script behind `docs/GLOBALS_DERIVATION.md`; it is kept so
the numbers in that document can be re-checked rather than trusted.

  Q1  Did the assigned pattern weights match what the patterns actually cost?
  Q2  Does `danger` predict a worse rest-of-session than `caution`?
  Q3  How long does an alert stay informative?
  Q4  Does the L2 premise hold — are 2+ domains worse than 1?

  C1  Confound: is the anti-signal just mean reversion after a loss?
  C2  Confound: do danger alerts simply fire later in the session?

WHY THE NULL MATTERS. A rate with no null is not a finding. On this tradebook
the rest of the session is negative 56% of the time at an arbitrary trade
boundary, 58% after a loss and 62% after two — so a detector that fires after
losses and is followed by a 57% loss rate has found nothing. Loss-triggered
detectors are scored against the loss-matched null for exactly that reason.

WHAT THIS CANNOT DO. n is 5-28 per pattern, one trader, one year, one regime.
It ranks detectors. It does not fit coefficients, and no number here should be
copied into a threshold.

Note the weights it compares against (RISK_DELTAS) were removed on 2026-08-13.
The Q1 column is retained because re-deriving it is how you would justify
reintroducing a weight, and because it is the evidence for not doing so.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.services.alert_outcome_service import observe_session, NO_OPPORTUNITY  # noqa: E402
from app.services.detector_registry import BY_NAME                              # noqa: E402

# The weights this script was written to test. Removed from the engine
# 2026-08-13; kept here as the historical record Q1 reports against.
RETIRED_RISK_DELTAS = {
    "consecutive_loss_streak": 20, "revenge_trade": 25, "overtrading_burst": 10,
    "size_escalation": 15, "rapid_reentry": 15, "panic_exit": 10,
    "martingale_behaviour": 20, "cooldown_violation": 25, "rapid_flip": 15,
    "excess_exposure": 15, "session_meltdown": 30, "fomo_entry": 15,
    "no_stoploss": 20, "early_exit": 10, "winning_streak_overconfidence": 15,
    "options_direction_confusion": 20, "options_premium_avg_down": 15,
    "iv_crush_behavior": 10, "expiry_day_overtrading": 20, "opening_5min_trap": 10,
    "end_of_session_mis_panic": 15, "post_loss_recovery_bet": 20,
    "profit_giveaway": 20, "constitution_violation": 25, "direction_instability": 15,
    "premium_loss_event": 15, "daily_overtrading": 10, "same_symbol_obsession": 20,
    "time_of_day_bias": 5, "death_spiral": 30, "overexposure": 15,
    "portfolio_concentration": 15, "holding_loser": 10, "win_rate_collapse": 10,
    "strategy_breakdown": 15, "premium_destruction": 25,
}

_ALIAS_NATURE = {
    "daily_overtrading": "emotional", "death_spiral": "emotional",
    "overexposure": "risk", "portfolio_concentration": "risk",
    "holding_loser": "emotional", "capital_mismatch": "risk",
}

# Detectors that require a loss to fire — judged against the loss-matched null.
LOSS_TRIGGERED = {
    "revenge_trade", "consecutive_loss_streak", "martingale_behaviour",
    "post_loss_recovery_bet", "death_spiral", "options_premium_avg_down",
    "size_escalation", "premium_loss_event",
}

IST_OFFSET_MIN = 330  # sidecar timestamps are UTC
HORIZONS = [15, 30, 45, 60, 90, 120, 180, 240]


def _dt(v):
    return datetime.fromisoformat(v) if v else None


def pct(x):
    return f"{x*100:.0f}%" if x is not None else "—"


def med(xs):
    return statistics.median(xs) if xs else None


def nature_of(pattern):
    spec = BY_NAME.get(pattern)
    return spec.nature if spec else _ALIAS_NATURE.get(pattern)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sidecar", type=Path, help="the -replay.json from replay_tradebook.py")
    args = ap.parse_args()

    data = json.loads(args.sidecar.read_text(encoding="utf-8"))
    days = data["days"]
    if days and not isinstance(next(iter(days.values())), dict):
        print("This sidecar predates outcome labelling — re-run replay_tradebook.py.",
              file=sys.stderr)
        return 2

    obs = []
    for day, payload in sorted(days.items()):
        alerts = [{**a, "detected_at": _dt(a["detected_at"])} for a in payload.get("alerts", [])]
        trades = [{**t, "entry_time": _dt(t.get("entry_time")), "exit_time": _dt(t.get("exit_time"))}
                  for t in payload.get("trades", [])]
        if not alerts:
            continue
        for o in observe_session(alerts, trades):
            if o.behaviour != NO_OPPORTUNITY and o.pnl_after is not None:
                obs.append((day, o))

    print(f"{len(obs)} alerts with a usable rest-of-session outcome, "
          f"{data['sessions']} sessions\n")

    # ---------------------------------------------------------- nulls
    null = {k: defaultdict(list) for k in ("any", "after_loss", "after_2loss")}
    for day, payload in days.items():
        ts = sorted([t for t in payload.get("trades", []) if t.get("exit_time")],
                    key=lambda t: t["exit_time"])
        pnls = [float(t.get("pnl") or 0) for t in ts]
        for i in range(len(ts) - 1):
            rest = sum(pnls[i + 1:])
            rem = min(len(pnls) - i - 1, 5)
            null["any"][rem].append(rest)
            if pnls[i] < 0:
                null["after_loss"][rem].append(rest)
            if i >= 1 and pnls[i] < 0 and pnls[i - 1] < 0:
                null["after_2loss"][rem].append(rest)

    def null_rate(kind, remaining):
        pool = null[kind].get(min(remaining, 5), [])
        if len(pool) < 15:
            pool = [v for vs in null[kind].values() for v in vs]
        return (sum(1 for v in pool if v < 0) / len(pool)) if pool else None

    print("MATCHED NULLS — rest-of-session outcome at a trade boundary")
    for kind in ("any", "after_loss", "after_2loss"):
        flat = [v for vs in null[kind].values() for v in vs]
        print(f"  {kind:<12} n={len(flat):>4}  negative {pct(sum(1 for v in flat if v<0)/len(flat))}"
              f"   median ₹{med(flat):,.0f}")

    by_pattern = defaultdict(list)
    for d, o in obs:
        by_pattern[o.pattern_type].append(o)

    # ---------------------------------------------------------- Q1
    print("\n" + "=" * 96)
    print("Q1 — ASSIGNED WEIGHT vs MEASURED COST  (weights retired 2026-08-13)")
    print("=" * 96)
    print(f"{'pattern':<32}{'n':>4}{'neg':>7}{'null':>7}{'lift':>7}"
          f"{'med ₹after':>12}{'old weight':>12}")
    print("-" * 96)
    rows = []
    for p, os_ in by_pattern.items():
        if len(os_) < 5:
            continue
        pnls = [o.pnl_after for o in os_]
        neg = sum(1 for v in pnls if v < 0) / len(pnls)
        kind = "after_loss" if p in LOSS_TRIGGERED else "any"
        matched = sum(null_rate(kind, o.trades_after) for o in os_) / len(os_)
        rows.append((p, len(os_), neg, matched, (neg - matched) * 100,
                     RETIRED_RISK_DELTAS.get(p)))
    for p, n, neg, nl, lift, w in sorted(rows, key=lambda r: -r[4]):
        pnls = [o.pnl_after for o in by_pattern[p]]
        print(f"{p:<32}{n:>4}{pct(neg):>7}{pct(nl):>7}{lift:>+6.0f}"
              f" {med(pnls):>11,.0f}{(str(w) if w else 'NONE'):>12}")

    ranked_lift = [r[0] for r in sorted(rows, key=lambda r: -r[4])]
    ranked_weight = [r[0] for r in sorted(rows, key=lambda r: -(r[5] or 0))]
    agree = sum(1 for i, p in enumerate(ranked_lift) if ranked_weight[i] == p)
    print(f"\nRank agreement weight vs lift: {agree}/{len(rows)} positions identical")
    pos = [r for r in rows if r[4] > 0]
    neg_ = [r for r in rows if r[4] <= 0]
    if pos and neg_:
        print(f"Mean old weight — predicts loss: {statistics.mean([r[5] or 0 for r in pos]):.1f}"
              f"  |  does not: {statistics.mean([r[5] or 0 for r in neg_]):.1f}")

    # ---------------------------------------------------------- Q2 + C2
    print("\n" + "=" * 96)
    print("Q2 — DOES SEVERITY PREDICT?   C2 — or does danger just fire later?")
    print("=" * 96)
    by_sev = defaultdict(list)
    for d, o in obs:
        by_sev[o.severity].append(o)

    print(f"{'severity':<10}{'n':>5}{'neg':>7}{'null':>7}{'lift':>7}"
          f"{'med IST':>10}{'med trades after':>18}")
    print("-" * 66)
    for sev in ("info", "caution", "danger", "critical"):
        os_ = by_sev.get(sev, [])
        if not os_:
            continue
        pnls = [o.pnl_after for o in os_]
        neg = sum(1 for v in pnls if v < 0) / len(pnls)
        nl = sum(null_rate("any", o.trades_after) for o in os_) / len(os_)
        times = [((o.detected_at.hour * 60 + o.detected_at.minute + IST_OFFSET_MIN) % 1440)
                 for o in os_]
        mt = med(times)
        print(f"{sev:<10}{len(os_):>5}{pct(neg):>7}{pct(nl):>7}{(neg-nl)*100:>+6.0f}"
              f"{f'{int(mt)//60:02d}:{int(mt)%60:02d}':>10}"
              f"{med([o.trades_after for o in os_]):>18.0f}")

    print("\nHorizon held fixed (only alerts with >=3 trades after) — the C2 control:")
    print(f"{'severity':<10}{'n':>5}{'neg':>7}{'null':>7}{'lift':>7}{'med ₹after':>14}")
    print("-" * 54)
    for sev in ("caution", "danger"):
        os_ = [o for o in by_sev.get(sev, []) if o.trades_after >= 3]
        if len(os_) < 5:
            print(f"{sev:<10}{len(os_):>5}   too few to read")
            continue
        pnls = [o.pnl_after for o in os_]
        neg = sum(1 for v in pnls if v < 0) / len(pnls)
        nl = sum(null_rate("any", o.trades_after) for o in os_) / len(os_)
        print(f"{sev:<10}{len(os_):>5}{pct(neg):>7}{pct(nl):>7}{(neg-nl)*100:>+6.0f}"
              f" {med(pnls):>13,.0f}")

    # ---------------------------------------------------------- Q3
    print("\n" + "=" * 96)
    print("Q3 — HOW LONG DOES AN ALERT STAY INFORMATIVE?")
    print("=" * 96)
    trades_by_day = {d: sorted([t for t in p.get("trades", []) if t.get("entry_time")],
                               key=lambda t: t["entry_time"])
                     for d, p in days.items()}
    null_h = defaultdict(list)
    for d, ts in trades_by_day.items():
        for i, anchor in enumerate(ts):
            a_t = _dt(anchor["entry_time"])
            for h in HORIZONS:
                w = [float(t.get("pnl") or 0) for t in ts[i + 1:]
                     if (_dt(t["entry_time"]) - a_t).total_seconds() / 60 <= h]
                if w:
                    null_h[h].append(sum(w))

    print(f"{'horizon':>9}{'n':>8}{'neg':>7}{'null':>7}{'lift':>7}{'median ₹':>12}")
    print("-" * 52)
    for h in HORIZONS:
        vals = []
        for d, o in obs:
            w = [float(t.get("pnl") or 0) for t in trades_by_day.get(d, [])
                 if o.detected_at < _dt(t["entry_time"])
                 and (_dt(t["entry_time"]) - o.detected_at).total_seconds() / 60 <= h]
            if w:
                vals.append(sum(w))
        if not vals or h not in null_h:
            continue
        neg = sum(1 for v in vals if v < 0) / len(vals)
        nn = sum(1 for v in null_h[h] if v < 0) / len(null_h[h])
        print(f"{h:>7}m{len(vals):>8}{pct(neg):>7}{pct(nn):>7}{(neg-nn)*100:>+6.0f}"
              f" {med(vals):>11,.0f}")

    # ---------------------------------------------------------- Q4
    print("\n" + "=" * 96)
    print("Q4 — THE L2 PREMISE: ARE MULTIPLE DOMAINS WORSE THAN ONE?")
    print("=" * 96)
    by_day_alerts = defaultdict(list)
    for d, o in obs:
        by_day_alerts[d].append(o)

    buckets = defaultdict(list)
    for d, os_ in by_day_alerts.items():
        ordered = sorted(os_, key=lambda o: o.detected_at)
        for i, o in enumerate(ordered):
            if o.pattern_type == "death_spiral":
                continue
            prior = [x for x in ordered[:i + 1]
                     if x.severity in ("danger", "critical") and x.pattern_type != "death_spiral"]
            domains = {nature_of(x.pattern_type) for x in prior if nature_of(x.pattern_type)}
            buckets[min(len(domains), 3)].append(o)

    print(f"{'danger+ domains open':>22}{'n':>6}{'neg':>7}{'null':>7}{'lift':>7}{'med ₹after':>14}")
    print("-" * 64)
    for k in sorted(buckets):
        os_ = buckets[k]
        pnls = [o.pnl_after for o in os_]
        neg = sum(1 for v in pnls if v < 0) / len(pnls)
        nl = sum(null_rate("any", o.trades_after) for o in os_) / len(os_)
        print(f"{(str(k) if k < 3 else '3+'):>22}{len(os_):>6}{pct(neg):>7}{pct(nl):>7}"
              f"{(neg-nl)*100:>+6.0f} {med(pnls):>13,.0f}")

    print("\nSame question by RAW alert count (the 'never raw counts' rule):")
    print(f"{'alerts so far':>22}{'n':>6}{'neg':>7}{'null':>7}{'lift':>7}{'med ₹after':>14}")
    print("-" * 64)
    cnt = defaultdict(list)
    for d, os_ in by_day_alerts.items():
        for i, o in enumerate(sorted(os_, key=lambda o: o.detected_at)):
            cnt[min(i + 1, 4)].append(o)
    for k in sorted(cnt):
        os_ = cnt[k]
        pnls = [o.pnl_after for o in os_]
        neg = sum(1 for v in pnls if v < 0) / len(pnls)
        nl = sum(null_rate("any", o.trades_after) for o in os_) / len(os_)
        print(f"{(str(k) if k < 4 else '4+'):>22}{len(os_):>6}{pct(neg):>7}{pct(nl):>7}"
              f"{(neg-nl)*100:>+6.0f} {med(pnls):>13,.0f}")

    print("\nn is 5-28 per pattern, one trader, one year. This ranks detectors.")
    print("It does not fit coefficients — do not copy a number here into a threshold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
