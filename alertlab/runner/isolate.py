"""
One scenario, one process.

Teardown clears the database between scenarios. It cannot clear the process, and
that turned out to be the difference between a suite that means something and one
that does not: the same seventy scenarios scored 63/70 run sequentially in one
process and 70/70 with each in its own, against identical code and identical
assertions.

The leak is in-memory, not in rows. SQLAlchemy identity maps outlive the DELETE
that removed the rows behind them, so a later scenario can load a TradingSession
that no longer exists (`UPDATE on trading_sessions expected to update 1 row(s);
0 were matched`, which poisons that session and the rest of the scenario with
it), and completed trades from an earlier scenario can still answer a query that
builds `session_trades`. The visible symptoms were opposite and equally
misleading: some scenarios reported zero alerts, while "a clean, disciplined
session" reported nine — `overtrading_burst` and `revenge_trade` on trades that
belonged to a scenario that had already been torn down.

Chasing individual caches would not close this. Any service that memoises
anything rejoins the class later, silently, and the failure mode is a scenario
that lies rather than one that errors. A process boundary is the only guarantee
that survives someone adding a cache next month.

The cost is one interpreter start per scenario — roughly four seconds against a
scenario average near fifteen, so a full suite moves from about 15 minutes to
about 20. That is the right trade for a harness whose entire job is to be
believed.

Single-scenario runs from the UI were always already isolated: one request, one
run, one process that then goes back to serving. This module is what makes a
whole suite behave the same way.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
_RUN_PY = _ROOT / "alertlab" / "scripts" / "run.py"

#: Written by the child immediately before its JSON payload, so the parent can
#: find the result even if something else reached stdout first.
RESULT_MARKER = "@@ALERTLAB_RESULT@@"

#: A scenario that hangs must not hang the suite. The slowest real scenario runs
#: about 50s; this is generous enough not to fire on a slow database and short
#: enough that a wedged run is reported rather than waited on forever.
CHILD_TIMEOUT_S = 300


def _blank(scenario_id: str, error: str) -> Dict[str, Any]:
    return {"id": scenario_id, "passed": False, "checks": [], "alerts": 0,
            "elapsed_ms": 0, "error": error}


async def run_isolated(scenario_id: str) -> Dict[str, Any]:
    """
    Run one scenario in a fresh interpreter and return its verdict.

    The child is told not to take the run lock: the caller already holds it for
    the whole suite, and a child blocking on its parent's lock would deadlock
    every run.
    """
    env = dict(os.environ)
    env["CELERY_WORKER"] = "1"       # NullPool; asyncpg connections are loop-bound
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-X", "utf8", str(_RUN_PY),
            scenario_id, "--json", "--no-lock",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(_ROOT),
            env=env,
        )
    except OSError as exc:
        return _blank(scenario_id, f"could not start runner process: {exc}")

    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=CHILD_TIMEOUT_S)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return _blank(scenario_id, f"timed out after {CHILD_TIMEOUT_S}s")

    text = (out or b"").decode("utf-8", "replace")
    # The child marks where its JSON begins. Scanning for the last `[` instead
    # looks obvious and is wrong: the payload contains nested arrays, so the
    # search lands inside one and every scenario comes back "unparseable".
    # A sentinel also survives anything a library prints to stdout first.
    _, sep, payload = text.partition(RESULT_MARKER)
    if not sep:
        tail = (err or b"").decode("utf-8", "replace").strip().splitlines()
        return _blank(scenario_id, tail[-1] if tail else "runner produced no output")

    try:
        rows = json.loads(payload)
    except json.JSONDecodeError as exc:
        return _blank(scenario_id, f"unparseable runner output: {exc}")

    if not rows:
        return _blank(scenario_id, "runner returned no result")
    return rows[0]


async def run_suite_isolated(
    scenario_ids: List[str],
    on_result: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> List[Dict[str, Any]]:
    """
    Run scenarios one at a time, each in its own process.

    Sequential on purpose. Every scenario tears down the one shared lab account
    before it starts, so running two at once would reintroduce exactly the
    cross-contamination this module exists to remove — in a form that no lock
    could catch, because both would be children of the same run.
    """
    results: List[Dict[str, Any]] = []
    for scenario_id in scenario_ids:
        result = await run_isolated(scenario_id)
        results.append(result)
        if on_result is not None:
            on_result(result)
    return results
