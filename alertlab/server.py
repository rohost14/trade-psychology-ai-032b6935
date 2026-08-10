"""
Alert Lab server — its own FastAPI app, on its own port.

Deliberately NOT a router bolted onto `app/main.py`. The lab mints trades and
alerts with no authentication; that must never be reachable from the production
surface by accident. A separate process on a separate port cannot be enabled by
a config mistake — it has to be started on purpose.

    python alertlab/server.py          → http://127.0.0.1:8900

Serves the UI and four endpoints. No auth, no tokens, no sessions: that is the
point, and it is why this refuses to run against a production database.
"""
from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from fastapi import FastAPI, HTTPException          # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402


from alertlab.runner.harness import (                            # noqa: E402
    quiet_logs, single_run_lock, teardown_lab,
)
from alertlab.runner.scenario import run_scenario    # noqa: E402
from alertlab.scenarios.catalogue import ALL_SCENARIOS, BY_ID  # noqa: E402

app = FastAPI(title="Alert Lab", docs_url=None, redoc_url=None)
UI = Path(__file__).parent / "ui" / "index.html"


def _guard() -> None:
    """
    Refuse to run anywhere that looks like production.

    An endpoint that fabricates trades and alerts without auth is genuinely
    dangerous. The guard is cheap and the failure mode it prevents is not.
    """
    env = (os.getenv("ENV") or os.getenv("ENVIRONMENT") or "").lower()
    if env in ("production", "prod"):
        raise HTTPException(status_code=403, detail="Alert Lab cannot run in production")


def _db_factory():
    from app.core.database import SessionLocal
    quiet_logs()
    return SessionLocal


@app.get("/")
async def index():
    return FileResponse(UI)


@app.get("/api/scenarios")
async def list_scenarios():
    """Everything the catalogue knows, grouped for the UI."""
    _guard()
    return {
        "scenarios": [s.as_dict() for s in ALL_SCENARIOS],
        "sections": sorted({s.section for s in ALL_SCENARIOS}),
    }


@contextlib.contextmanager
def _held():
    """Translate a busy lab into a 409 the UI can show, not a 500."""
    try:
        with single_run_lock(owner="server"):
            yield
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@app.post("/api/run/{scenario_id}")
async def run_one(scenario_id: str):
    """
    Replay one scenario and return the full timeline.

    The run itself takes milliseconds — eager Celery, no waiting on windows — so
    the response carries everything and the UI replays it at readable speed.
    That is more useful than watching real five-second gaps, and it is
    reproducible.
    """
    _guard()
    scenario = BY_ID.get(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"unknown scenario {scenario_id}")
    with _held():
        return JSONResponse(await run_scenario(scenario, _db_factory()))


@app.post("/api/run-all")
async def run_all():
    """The whole suite. Summary plus per-scenario pass/fail."""
    _guard()
    results = []
    with _held():
        for scenario in ALL_SCENARIOS:
            outcome = await run_scenario(scenario, _db_factory())
            results.append({
                "id": scenario.id, "title": scenario.title, "section": scenario.section,
                "passed": outcome["passed"], "error": outcome["error"],
                "alerts": len(outcome["alerts"]),
                "checks": outcome["checks"], "elapsed_ms": outcome["elapsed_ms"],
            })
    return {
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": [r["id"] for r in results if not r["passed"]],
        "results": results,
    }


@app.post("/api/teardown")
async def teardown():
    """
    Wipe the synthetic account.

    Not housekeeping: lab alerts live in the same `risk_alerts` table that
    /api/admin/detection-quality reads, so anything left behind distorts the
    metrics that measure the real engine.
    """
    _guard()
    async with _db_factory()() as db:
        return {"deleted": await teardown_lab(db)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8900, log_level="warning")
