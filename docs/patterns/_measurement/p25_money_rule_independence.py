"""
Do the behavioural detectors still work when the trader sets NO money rules?

The product principle under test: user-configured money rules are optional
guardrails, NOT prerequisites for the rest of the engine.

Five configurations, every detector, the real 175-session book:

    A  no money rules at all          <- the default a new trader lands in
    B  only daily_loss_limit
    C  only per_trade_loss_limit
    D  only max_position_size (capital exposure)
    E  all three

Anything that moves between A and B/C/D/E is a dependency. Anything that moves
between B, C and D that should not have is a LEAK — one rule changing a
detector that has nothing to do with it.

`trading_capital` is deliberately held CONSTANT across all five. It is not one
of the three money rules — it is collected separately in onboarding — so
varying it would confound the question being asked.
"""
import sys
from collections import Counter

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

src = open("D:/trade-psychology-ai/docs/patterns/_measurement/p20_avgdown.py",
           encoding="utf-8").read()
src = src.replace("AVG = engine._detect_options_premium_avg_down\n", "")
exec(src.rsplit("\nmain()", 1)[0])

from app.core.trading_defaults import COLD_START_DEFAULTS   # noqa: E402

CAPITAL = 200_000        # held constant — not a money rule

CONFIGS = {
    "A none":        dict(daily_loss_limit=None, per_trade_loss_limit=None, max_position_size=None),
    "B daily only":  dict(daily_loss_limit=4000, per_trade_loss_limit=None, max_position_size=None),
    "C per-trade":   dict(daily_loss_limit=None, per_trade_loss_limit=4000, max_position_size=None),
    "D exposure":    dict(daily_loss_limit=None, per_trade_loss_limit=None, max_position_size=25.0),
    "E all three":   dict(daily_loss_limit=4000, per_trade_loss_limit=4000, max_position_size=25.0),
}

DETS = [n for n in dir(engine) if n.startswith("_detect_")]


def thresholds(cfg):
    t = dict(COLD_START_DEFAULTS)
    # count/time rules held constant so only the money rules vary
    t["user_daily_trade_limit"] = 10
    t["user_cooldown_min"] = 15
    t["max_consecutive_losses"] = 3
    t["restricted_windows"] = []
    t["trading_capital"] = CAPITAL
    t.update(cfg)
    return t


def run(cfg):
    counts = Counter()
    rules = Counter()
    for _d, tr in sessions:
        for ct in tr:
            pool = [t for t in tr if t.id != ct.id and t.exit_time <= ct.exit_time]
            c = ctx_fills(ct, pool)
            c.thresholds = thresholds(cfg)
            for name in DETS:
                try:
                    r = getattr(engine, name)(c)
                except Exception:
                    continue
                if name == "_detect_constitution_violation":
                    for e in (r or []):
                        counts[name] += 1
                        rules[e.context["rule"]] += 1
                elif fired(r):
                    counts[name] += 1
    return counts, rules


sessions = load_with_fills()
trades = [t for _, ts in sessions for t in ts]
print(f"BOOK: {len(sessions)} sessions, {len(trades)} rounds")
print(f"trading_capital held constant at Rs {CAPITAL:,}\n")

results = {k: run(v) for k, v in CONFIGS.items()}

names = sorted({n for c, _ in results.values() for n in c})
print("=" * 92)
print("EVERY DETECTOR, EVERY CONFIGURATION")
print("=" * 92)
hdr = f"  {'detector':<30}" + "".join(f"{k:>13}" for k in CONFIGS)
print(hdr)
print("  " + "-" * (len(hdr) - 2))
moved = []
for n in names:
    row = [results[k][0][n] for k in CONFIGS]
    flag = ""
    if len(set(row)) > 1:
        flag = "   <-- MOVES"
        moved.append(n)
    print(f"  {n.replace('_detect_',''):<30}" + "".join(f"{v:>13}" for v in row) + flag)

print(f"\n  detectors that MOVE with money rules : {len(moved)}")
for n in moved:
    print(f"      {n.replace('_detect_','')}")
print(f"  detectors that are INDEPENDENT       : {len(names) - len(moved)}")

print("\n" + "=" * 92)
print("constitution_violation, BROKEN DOWN BY RULE")
print("=" * 92)
allrules = sorted({r for _, rr in results.values() for r in rr})
hdr2 = f"  {'rule':<26}" + "".join(f"{k:>13}" for k in CONFIGS)
print(hdr2)
print("  " + "-" * (len(hdr2) - 2))
for r in allrules:
    row = [results[k][1][r] for k in CONFIGS]
    print(f"  {r:<26}" + "".join(f"{v:>13}" for v in row))

print("\n" + "=" * 92)
print("LEAK CHECK — does one money rule change ANOTHER rule's firing?")
print("=" * 92)
base = results["A none"][1]
for k in ("B daily only", "C per-trade", "D exposure"):
    rr = results[k][1]
    expect = {"B daily only": "daily_loss", "C per-trade": "per_trade_loss",
              "D exposure": "max_trade_risk"}[k]
    leaks = {r: (base[r], rr[r]) for r in allrules
             if r != expect and base[r] != rr[r]}
    print(f"  {k:<14} expected to change only `{expect}`  ->  "
          f"{'NO LEAK' if not leaks else 'LEAK: ' + str(leaks)}")
