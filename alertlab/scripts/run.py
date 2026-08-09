"""
Run scenarios from a terminal.

    python alertlab/scripts/run.py                 every scenario
    python alertlab/scripts/run.py K-01 B-05       named scenarios
    python alertlab/scripts/run.py --json          machine-readable (CI)
    python alertlab/scripts/run.py --teardown      just wipe the lab account

Same runner the UI uses, so a green terminal and a green page mean the same
thing.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


from alertlab.runner.harness import quiet_logs, teardown_lab           # noqa: E402
from alertlab.runner.scenario import run_scenario          # noqa: E402
from alertlab.scenarios.catalogue import ALL_SCENARIOS, BY_ID  # noqa: E402

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

    results = []
    for scenario in chosen:
        outcome = await run_scenario(scenario, _db_factory())
        results.append(outcome)
        if "--json" in flags:
            continue
        mark = f"{GREEN}pass{OFF}" if outcome["passed"] else f"{RED}FAIL{OFF}"
        print(f"{mark}  {scenario.id:<7} {scenario.title}"
              f"{DIM}  ({len(outcome['alerts'])} alerts, {outcome['elapsed_ms']}ms){OFF}")
        for check in outcome["checks"]:
            if not check["pass"]:
                kind = "must fire" if check["kind"] == "must_fire" else "must NOT fire"
                print(f"        {RED}·{OFF} {check['pattern']} [{kind}] — {check['detail']}")
                if check["reason"]:
                    print(f"          {DIM}{check['reason']}{OFF}")
        if outcome["error"]:
            print(f"        {RED}{outcome['error'].strip().splitlines()[-1]}{OFF}")

    if "--json" in flags:
        print(json.dumps([{
            "id": r["scenario"]["id"], "passed": r["passed"],
            "checks": r["checks"], "alerts": len(r["alerts"]),
        } for r in results], indent=2))
    else:
        passed = sum(1 for r in results if r["passed"])
        colour = GREEN if passed == len(results) else RED
        print(f"\n{colour}{passed}/{len(results)} scenarios passed{OFF}")

    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
