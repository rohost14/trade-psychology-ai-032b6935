"""
Run scenarios from a terminal.

    python alertlab/scripts/run.py                 every scenario
    python alertlab/scripts/run.py K-01 B-05       named scenarios
    python alertlab/scripts/run.py --json          machine-readable (CI)
    python alertlab/scripts/run.py --teardown      just wipe the lab account
    python alertlab/scripts/run.py --in-process    one process for all (faster, lies)

A suite runs each scenario in its own process. Sharing one changes the results —
63/70 against 70/70 on identical code. See runner/isolate.py.

Same runner the UI uses, so a green terminal and a green page mean the same
thing.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


from alertlab.runner.harness import (                                  # noqa: E402
    quiet_logs, single_run_lock, teardown_lab,
)
from alertlab.runner.isolate import (                      # noqa: E402
    RESULT_MARKER, run_suite_isolated,
)
from alertlab.runner.scenario import run_scenario          # noqa: E402
from alertlab.scenarios.catalogue import ALL_SCENARIOS, BY_ID  # noqa: E402

# Windows consoles default to cp1252, which cannot encode ₹ — and scenario
# titles are full of it. Without this the runner dies formatting its own output.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GREEN, RED, DIM, OFF = "\033[32m", "\033[31m", "\033[90m", "\033[0m"


def _db_factory():
    from app.core.database import SessionLocal
    quiet_logs()
    return SessionLocal


async def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}

    if "--teardown" in flags:
        async with _db_factory()() as db:
            print(json.dumps(await teardown_lab(db), indent=2))
        return 0

    chosen = [BY_ID[a] for a in args if a in BY_ID] if args else ALL_SCENARIOS
    unknown = [a for a in args if a not in BY_ID]
    if unknown:
        print(f"unknown scenario(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    def _report(row):
        """One scenario's verdict, in the shape both run modes share."""
        if "--json" in flags:
            return
        mark = f"{GREEN}pass{OFF}" if row["passed"] else f"{RED}FAIL{OFF}"
        title = BY_ID[row["id"]].title if row["id"] in BY_ID else ""
        print(f"{mark}  {row['id']:<7} {title}"
              f"{DIM}  ({row['alerts']} alerts, {row['elapsed_ms']}ms){OFF}", flush=True)
        for check in row["checks"]:
            if not check["pass"]:
                kind = {"must_fire": "must fire", "must_not_fire": "must NOT fire",
                        "must_record": "must be recorded"}.get(check["kind"], check["kind"])
                print(f"        {RED}·{OFF} {check['pattern']} [{kind}] — {check['detail']}")
                if check["reason"]:
                    print(f"          {DIM}{check['reason']}{OFF}")
        if row["error"]:
            print(f"        {RED}{row['error'].strip().splitlines()[-1]}{OFF}")

    def _flatten(outcome):
        return {"id": outcome["scenario"]["id"], "passed": outcome["passed"],
                "checks": outcome["checks"], "alerts": len(outcome["alerts"]),
                "elapsed_ms": outcome["elapsed_ms"], "error": outcome["error"],
                # Carried so an audit can ask how MANY alerts one trade produced,
                # which is the question every assertion in the suite skips.
                "alert_rows": [
                    {"pattern_type": a["pattern_type"], "severity": a["severity"],
                     "label": a["label"], "message": a["message"],
                     "trigger": a["trigger_completed_trade_id"],
                     "at": a["detected_at_ist"]}
                    for a in outcome["alerts"]
                ]}

    # `--no-lock` marks a child spawned by an isolated suite: the parent already
    # holds the lock, so a child taking it would deadlock every run.
    lock = (contextlib.nullcontext() if "--no-lock" in flags
            else single_run_lock(owner="cli"))

    with lock:
        if len(chosen) > 1 and "--in-process" not in flags:
            # A suite always isolates. See runner/isolate.py — sharing one
            # process across scenarios silently changes the results.
            results = await run_suite_isolated([s.id for s in chosen], on_result=_report)
        else:
            results = []
            for scenario in chosen:
                row = _flatten(await run_scenario(scenario, _db_factory()))
                results.append(row)
                _report(row)

    if "--json" in flags:
        # The marker lets an isolated parent find this payload without guessing
        # where the JSON starts. See runner/isolate.py.
        print(RESULT_MARKER)
        print(json.dumps(results, indent=2))
    else:
        passed = sum(1 for r in results if r["passed"])
        colour = GREEN if passed == len(results) else RED
        print(f"\n{colour}{passed}/{len(results)} scenarios passed{OFF}")

    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
