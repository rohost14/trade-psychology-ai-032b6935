"""
Trade Desk server — its own FastAPI app, its own port.

Deliberately not a router on `app/main.py`, for the same reason the Alert Lab is
not: this mints trades and alerts with no authentication, and that must never be
reachable from the production surface by a config mistake. A separate process on
a separate port has to be started on purpose.

    python tradedesk/server.py     → http://127.0.0.1:8901

One terminal. No Celery worker, no Redis, no broker session, no OAuth.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from fastapi import FastAPI, HTTPException          # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from pydantic import BaseModel                      # noqa: E402

from tradedesk.desk import Desk                     # noqa: E402
from alertlab.runner.probe import probe             # noqa: E402

app = FastAPI(title="Trade Desk", docs_url=None, redoc_url=None)
UI = Path(__file__).parent / "ui" / "index.html"

#: One desk per process. It holds the clock and the order list; everything else
#: lives in the database where the engine can see it.
DESK = Desk()


def _guard() -> None:
    env = (os.getenv("ENV") or os.getenv("ENVIRONMENT") or "").lower()
    if env in ("production", "prod"):
        raise HTTPException(status_code=403, detail="Trade Desk cannot run in production")


class Order(BaseModel):
    symbol: str
    side: str
    qty: int
    price: float
    product: str = "MIS"
    exchange: str = "NFO"
    advance_minutes: int = 0
    note: str = ""


class Settings(BaseModel):
    capital: float | None = None
    profile: dict | None = None
    clock: str | None = None      # "YYYY-MM-DD HH:MM" in IST


@app.get("/")
async def index():
    return FileResponse(UI)


@app.get("/api/state")
async def state():
    _guard()
    return JSONResponse(await DESK.state())


@app.post("/api/order")
async def order(body: Order):
    _guard()
    if body.qty <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")
    if body.price <= 0:
        raise HTTPException(status_code=400, detail="price must be positive")
    if body.side.upper() not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="side must be BUY or SELL")
    return JSONResponse(await DESK.place(**body.model_dump()))


@app.post("/api/advance")
async def advance(minutes: int = 15):
    _guard()
    return JSONResponse(await DESK.advance(minutes))


@app.post("/api/settings")
async def settings(body: Settings):
    _guard()
    from datetime import datetime

    from alertlab.runner.harness import IST

    if body.clock:
        try:
            DESK.clock = datetime.strptime(body.clock, "%Y-%m-%d %H:%M").replace(tzinfo=IST)
        except ValueError:
            raise HTTPException(status_code=400, detail="clock must be 'YYYY-MM-DD HH:MM'")
    # Capital and rules apply WITHOUT clearing the session, so a threshold can be
    # moved and the same trades looked at again.
    await DESK.apply_settings(capital=body.capital, profile=body.profile)
    return JSONResponse(await DESK.state())


@app.post("/api/reset")
async def reset(body: Settings):
    _guard()
    from datetime import datetime

    from alertlab.runner.harness import IST

    clock = None
    if body.clock:
        try:
            clock = datetime.strptime(body.clock, "%Y-%m-%d %H:%M").replace(tzinfo=IST)
        except ValueError:
            raise HTTPException(status_code=400, detail="clock must be 'YYYY-MM-DD HH:MM'")
    deleted = await DESK.reset(capital=body.capital, profile=body.profile, clock=clock)
    return JSONResponse({"deleted": deleted, **await DESK.state()})


@app.get("/api/probe")
async def why():
    """Every detector's verdict on the session as it stands, with the inputs."""
    _guard()
    return JSONResponse(await probe())


@app.post("/api/wipe")
async def wipe():
    """
    Delete every row this desk created.

    Scoped to the desk's own account, so it cannot touch the scenario suite's
    data or anything real.
    """
    _guard()
    return JSONResponse({"deleted": await DESK.wipe()})


@app.get("/api/rules")
async def rules():
    """The constitution fields, so the UI does not hard-code its own list."""
    _guard()
    from app.services.constitution_service import RULE_FIELDS
    return {"rule_fields": list(RULE_FIELDS)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8901, log_level="warning")
