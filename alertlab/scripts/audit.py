"""
How many alerts does one trade produce?

Every assertion in the scenario suite asks whether the right pattern fired. None
asks how many fired, and a trade that produces seven correct alerts passes every
test in the suite while being unusable in the product. This measures the thing
the suite structurally cannot see.

    python alertlab/scripts/audit.py            # every scenario
    python alertlab/scripts/audit.py C-11a K-01 # named

Reports, per trigger trade: the alert count, whether a composite alert fired
alongside the alerts it summarises, whether several detectors described the same
underlying behaviour, and whether one trade broke several rules and got an alert
for each.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from alertlab.runner.harness import single_run_lock       # noqa: E402
from alertlab.runner.isolate import RESULT_MARKER          # noqa: E402
from alertlab.scenarios.catalogue import ALL_SCENARIOS, BY_ID  # noqa: E402

#: Detectors that describe the SAME underlying behaviour. More than one of a
#: family on one trade is one story told several times.
FAMILIES = {
    "sizing after losses": {
        "size_escalation", "martingale_behaviour", "post_loss_recovery_bet",
    },
    "going back to the same trade": {
        "same_symbol_obsession", "rapid_reentry", "revenge_trade",
    },
    "the position is too big": {
        "overexposure", "portfolio_concentration", "capital_mismatch",
    },
}

#: Alerts that are summaries of other alerts. Firing one ALONGSIDE what it
#: summarises is double-reporting by construction.
COMPOSITES = {"death_spiral", "session_meltdown"}

GREEN, RED, DIM, OFF = "\033[32m", "\033[31m", "\033[90m", "\033[0m"


def _run(scenario_id: str):
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(ROOT / "alertlab" / "scripts" / "run.py"),
         scenario_id, "--json", "--no-lock"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(ROOT),
    )
    _, sep, payload = (proc.stdout or "").partition(RESULT_MARKER)
    if not sep:
        return None
    try:
        rows = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return rows[0] if rows else None


def audit(row):
    """Findings for one scenario, grouped by the trade that triggered them."""
    by_trigger = defaultdict(list)
    for a in row.get("alert_rows", []):
        by_trigger[a["trigger"] or a["at"]].append(a)

    findings = []
    worst = 0
    for trigger, alerts in by_trigger.items():
        patterns = [a["pattern_type"] for a in alerts]
        worst = max(worst, len(alerts))

        for name, members in FAMILIES.items():
            overlap = [p for p in patterns if p in members]
            if len(overlap) > 1:
                findings.append(("family", f"{len(overlap)} alerts for one fact "
                                           f"({name}): {', '.join(sorted(set(overlap)))}"))

        composite = [p for p in patterns if p in COMPOSITES]
        if composite and len(patterns) > len(composite):
            others = [p for p in patterns if p not in COMPOSITES]
            findings.append(("composite", f"{composite[0]} fired alongside the "
                                          f"{len(others)} alerts it summarises"))

        rule_alerts = [p for p in patterns if p == "constitution_violation"]
        if len(rule_alerts) > 1:
            findings.append(("rules", f"{len(rule_alerts)} separate rule-breach alerts "
                                      f"on one trade"))

        if len(alerts) > 2:
            findings.append(("flood", f"{len(alerts)} alerts on one trade: "
                                      f"{', '.join(sorted(set(patterns)))}"))

    return worst, findings


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    chosen = [BY_ID[a] for a in args if a in BY_ID] if args else ALL_SCENARIOS

    total_alerts = 0
    worst_overall = 0
    flagged = []

    # The audit drives the same synthetic account the suite does, and every
    # scenario tears it down before it starts. Without this a second audit — or
    # a suite run — deletes rows from under this one, and the counts it reports
    # are quietly wrong rather than obviously broken. Measured 24, 43 and 63
    # alerts for the same three scenarios before this was added.
    with single_run_lock(owner="audit"):
      for scenario in chosen:
        row = _run(scenario.id)
        if row is None:
            print(f"{RED}skip{OFF}  {scenario.id:<7} runner produced no result", flush=True)
            continue
        worst, findings = audit(row)
        total_alerts += len(row.get("alert_rows", []))
        worst_overall = max(worst_overall, worst)

        if findings:
            flagged.append((scenario.id, scenario.title, worst, findings))
            print(f"{RED}{worst:>3} max{OFF}  {scenario.id:<7} {scenario.title}", flush=True)
            for kind, detail in findings:
                print(f"          {DIM}{kind:<10}{OFF} {detail}", flush=True)
        else:
            print(f"{GREEN}{worst:>3} max{OFF}  {scenario.id:<7} {scenario.title}", flush=True)

    print(f"\n{len(flagged)}/{len(chosen)} scenarios have an alert-quality finding")
    print(f"worst single trade: {worst_overall} alerts · {total_alerts} alerts total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
