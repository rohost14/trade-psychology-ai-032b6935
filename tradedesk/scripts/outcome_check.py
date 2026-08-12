"""
Label a year of alerts by what the trader did next — nothing asked, nothing typed.

    python tradedesk/scripts/outcome_check.py docs/tradebook-...-replay.json

Reads the replay sidecar and runs every alert through AlertOutcomeService. The
service is the same code the live product would use; running it here is the
only way to get a year of labels, because the replay tears down each day before
starting the next and the database only ever holds the last one.

Two questions are reported separately because they have different uses:

  heeded_rate    — did the behaviour change after the alert?  (product)
  warranted_rate — did the behaviour keep costing money?      (calibration)

An alert can be ignored and still be right, so a low heeded_rate is not
evidence a detector is wrong. Only warranted_rate speaks to the threshold.

READ THE EXCLUSIONS. Alerts fire when a position closes, so they cluster at the
end of the session, where "they stopped" means the market closed. Those are
labelled no_opportunity and dropped from the rates rather than counted as
successes. If no_opportunity dominates a pattern, that pattern has no usable
outcome data yet and its rates should be ignored, not read as good news.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.services.alert_outcome_service import (          # noqa: E402
    HEEDED, IGNORED, NO_OPPORTUNITY, observe_session, summarise,
)


def _dt(value):
    return datetime.fromisoformat(value) if value else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sidecar", type=Path, help="the -replay.json from replay_tradebook.py")
    ap.add_argument("--pattern", default=None, help="only this pattern")
    ap.add_argument("--show", type=int, default=0,
                    help="print N individual observations per pattern")
    args = ap.parse_args()

    data = json.loads(args.sidecar.read_text(encoding="utf-8"))
    days = data["days"]
    if days and not isinstance(next(iter(days.values())), dict):
        print("This sidecar predates outcome labelling — it has pattern names "
              "only. Re-run replay_tradebook.py to regenerate it.", file=sys.stderr)
        return 2

    all_obs = []
    for day, payload in sorted(days.items()):
        alerts = [{**a, "detected_at": _dt(a["detected_at"])}
                  for a in payload.get("alerts", [])]
        trades = [{**t,
                   "entry_time": _dt(t.get("entry_time")),
                   "exit_time": _dt(t.get("exit_time"))}
                  for t in payload.get("trades", [])]
        if args.pattern:
            alerts = [a for a in alerts if a["pattern_type"] == args.pattern]
        if not alerts:
            continue
        for o in observe_session(alerts, trades):
            o.notes.append(f"day={day}")
            all_obs.append(o)

    if not all_obs:
        print("No alerts to label.")
        return 0

    print(f"{len(all_obs)} alerts across {len(days)} sessions\n")
    rows = summarise(all_obs)

    print(f"{'pattern':<32}{'alerts':>7}{'n_beh':>7}{'heeded':>8}"
          f"{'n_cost':>7}{'warranted':>11}{'no_opp':>8}{'med P&L after':>15}")
    print("-" * 105)
    for pattern, r in sorted(rows.items(), key=lambda kv: -kv[1]["alerts"]):
        hr = f"{r['heeded_rate']*100:.0f}%" if r["heeded_rate"] is not None else "—"
        wr = f"{r['warranted_rate']*100:.0f}%" if r["warranted_rate"] is not None else "—"
        mp = f"{r['median_pnl_after']:,.0f}" if r["median_pnl_after"] is not None else "—"
        print(f"{pattern:<32}{r['alerts']:>7}{r['n_behaviour']:>7}{hr:>8}"
              f"{r['n_cost']:>7}{wr:>11}{r['no_opportunity']:>8}{mp:>15}")

    total = len(all_obs)
    no_opp = sum(1 for o in all_obs if o.behaviour == NO_OPPORTUNITY)
    decidable = sum(1 for o in all_obs if o.behaviour in (HEEDED, IGNORED))
    print(f"\n{decidable}/{total} alerts have a usable behaviour label "
          f"({no_opp} excluded — session ended too soon to tell).")

    thin = [p for p, r in rows.items() if r["n_behaviour"] < 5]
    if thin:
        print(f"\nToo few decidable alerts to read a rate ({', '.join(sorted(thin))}).")
        print("Their percentages above are noise, not findings.")

    if args.show:
        print("\nIndividual observations:")
        seen = {}
        for o in all_obs:
            n = seen.get(o.pattern_type, 0)
            if n >= args.show:
                continue
            seen[o.pattern_type] = n + 1
            print(f"\n  {o.pattern_type} · {o.severity} · {o.detected_at}")
            print(f"    behaviour={o.behaviour} warranted={o.warranted} "
                  f"trades_after={o.trades_after} pnl_after={o.pnl_after}")
            for note in o.notes:
                print(f"    - {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
