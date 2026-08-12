"""
Is the engine reproducible? Diff two replay sidecars.

    python tradedesk/scripts/replay_diff.py run_A.json run_B.json

Every threshold experiment from here measures a difference against a baseline.
If the baseline moves on its own, the experiment measures nothing. So before
calibrating anything, run the same tradebook twice and prove the output is
identical — and re-prove it after each change, because a fix that quietly
introduces order-dependence looks exactly like a fix that worked.

Reports three kinds of difference, deliberately separated:

  COUNT     a day produced a different number of alerts        — real defect
  PATTERN   same count, different patterns                     — real defect
  ORDER     same alerts, listed in a different sequence        — cosmetic

ORDER alone is not a reproducibility failure. Alerts raised by one trade all
share that trade's exit_time as detected_at, and the tiebreaker is created_at,
which is real wall-clock. Two runs will legitimately sequence them differently.
It is reported so it cannot be mistaken for the other two.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def load(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    days = {}
    for day, payload in data["days"].items():
        if isinstance(payload, dict):
            alerts = payload.get("alerts", [])
            days[day] = [(a["pattern_type"], a["severity"], a["detected_at"])
                         for a in alerts]
        else:                       # first-generation sidecar: names only
            days[day] = [(p, None, None) for p in payload]
    return days


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: replay_diff.py <A.json> <B.json>", file=sys.stderr)
        return 2
    a, b = load(Path(sys.argv[1])), load(Path(sys.argv[2]))

    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    if only_a or only_b:
        print(f"Sessions differ: {len(only_a)} only in A, {len(only_b)} only in B")
        for d in (only_a + only_b)[:10]:
            print(f"  {d}")

    shared = sorted(set(a) & set(b))
    count_diff, pattern_diff, order_diff = [], [], []
    for day in shared:
        ea, eb = a[day], b[day]
        if len(ea) != len(eb):
            count_diff.append((day, len(ea), len(eb)))
        elif Counter(x[:2] for x in ea) != Counter(x[:2] for x in eb):
            pattern_diff.append((day, ea, eb))
        elif ea != eb:
            order_diff.append(day)

    ta = sum(len(v) for v in a.values())
    tb = sum(len(v) for v in b.values())
    print(f"A: {ta} alerts / {len(a)} sessions")
    print(f"B: {tb} alerts / {len(b)} sessions")
    print(f"shared sessions: {len(shared)}\n")

    if count_diff:
        print(f"COUNT differs on {len(count_diff)} day(s) — REAL:")
        for day, na, nb in count_diff[:20]:
            print(f"  {day}  A={na}  B={nb}")
            for label, rows in (("A", a[day]), ("B", b[day])):
                print(f"    {label}: " + ", ".join(f"{p}/{s}" for p, s, _ in rows))
    if pattern_diff:
        print(f"\nPATTERN differs on {len(pattern_diff)} day(s) — REAL:")
        for day, ea, eb in pattern_diff[:20]:
            sa, sb = Counter(x[:2] for x in ea), Counter(x[:2] for x in eb)
            print(f"  {day}")
            print(f"    only A: {sorted((sa - sb).elements())}")
            print(f"    only B: {sorted((sb - sa).elements())}")
    if order_diff:
        print(f"\nORDER differs on {len(order_diff)} day(s) — cosmetic "
              f"(created_at tiebreak is wall-clock): "
              f"{', '.join(order_diff[:8])}"
              + (f" (+{len(order_diff) - 8} more)" if len(order_diff) > 8 else ""))

    real = len(count_diff) + len(pattern_diff)
    if real == 0 and not only_a and not only_b:
        print("\nREPRODUCIBLE — identical alerts on every shared session."
              + (" Ordering varies; that is expected." if order_diff else ""))
        return 0
    print(f"\nNOT REPRODUCIBLE — {real} session(s) differ in what fired.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
