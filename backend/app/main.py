from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
import logging
import uuid
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

logger = logging.getLogger(__name__)

# Sentry — initialise before the app starts so all errors are captured
# Set SENTRY_DSN in .env. Without DSN, this is a no-op (safe to leave in).
def _sentry_before_send(event, hint):
    """
    Filter out non-actionable events before they reach Sentry.

    KeyboardInterrupt  — user pressed Ctrl+C (normal shutdown, not a bug)
    CancelledError     — asyncio task cancelled during shutdown (normal)
    SystemExit         — process exit (normal)
    """
    exc_info = hint.get("exc_info")
    if exc_info:
        exc_type = exc_info[0]
        if exc_type in (KeyboardInterrupt, SystemExit):
            return None  # Drop — don't send to Sentry
        # asyncio.CancelledError
        if exc_type.__name__ in ("CancelledError", "asyncio.CancelledError"):
            return None
    return event


if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        integrations=[
            FastApiIntegration(),
            AsyncioIntegration(),
            LoggingIntegration(level=logging.WARNING, event_level=logging.ERROR),
        ],
        traces_sample_rate=0.1,   # 10% of requests traced (low overhead)
        profiles_sample_rate=0.0,  # profiling off for now
        send_default_pii=False,    # no personal data in error reports
        before_send=_sentry_before_send,
    )
    logger.info("Sentry initialised")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up TradeMentor AI Backend...")

    # Start retention scheduler
    from app.tasks.retention_tasks import start_scheduler
    start_scheduler()
    logger.info("Retention scheduler started")

    # Reconnect KiteTicker for all accounts that had open positions
    # before the server restarted (prevents stale prices after deploys).
    try:
        from app.services.price_stream_service import price_stream
        from app.core.database import SessionLocal
        async with SessionLocal() as db:
            await price_stream.restart_all(db)
    except Exception as e:
        logger.error(f"Price stream restart failed on startup: {e}")

    yield

    # Shutdown logic
    logger.info("Shutting down...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan
)

# CORS Middleware
# Security guard: allow_credentials=True + wildcard origins = XSS escalation risk.
# This assertion prevents a misconfigured production deploy from being exploitable.
# On localhost BACKEND_CORS_ORIGINS is ["http://localhost:8080"] so this never fires.
_cors_origins = settings.BACKEND_CORS_ORIGINS
if "*" in _cors_origins and settings.ENVIRONMENT != "development":
    raise RuntimeError(
        "SECURITY: allow_credentials=True cannot be used with allow_origins=['*'] "
        "in non-development environments. Set BACKEND_CORS_ORIGINS to explicit domains."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request-ID middleware
# Generates a unique ID per request, injects into logs, returns in header.
# Every log line during a request now includes the request_id, making it
# trivial to trace all log output for a single API call in Sentry/CloudWatch.
# ---------------------------------------------------------------------------
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    # Store on request state so route handlers can access it if needed
    request.state.request_id = request_id

    # Inject into the logging context for this request
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.request_id = request_id
        return record

    logging.setLogRecordFactory(record_factory)
    try:
        response = await call_next(request)
    finally:
        logging.setLogRecordFactory(old_factory)

    response.headers["X-Request-ID"] = request_id
    return response


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error"},
    )

# Health Check
# Returns 200 only when DB and Redis are reachable.
# Returns 503 if either dependency is down — lets load balancers / uptime
# monitors detect infrastructure failures automatically.
@app.get("/health")
async def health_check():
    from app.core.database import SessionLocal
    from sqlalchemy import text

    checks = {"db": "error", "redis": "error"}
    healthy = True

    # DB check
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:
        logger.error(f"Health check DB failed: {e}")
        healthy = False

    # Redis check
    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=2)
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        logger.error(f"Health check Redis failed: {e}")
        healthy = False

    # Circuit breaker summary (informational only — never makes health degraded)
    try:
        from app.services.circuit_breaker_service import circuit_breaker, CircuitState
        from app.models.broker_account import BrokerAccount
        from sqlalchemy import select as sa_select
        async with SessionLocal() as session:
            result = await session.execute(
                sa_select(BrokerAccount.id).where(BrokerAccount.status == "connected")
            )
            account_ids = result.scalars().all()
        open_circuits = []
        for aid in account_ids:
            state = await circuit_breaker.get_state(aid)
            if state != CircuitState.CLOSED:
                open_circuits.append(str(aid)[:8])
        checks["circuit_breakers"] = "all_closed" if not open_circuits else f"open:{open_circuits}"
    except Exception:
        checks["circuit_breakers"] = "unknown"

    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if healthy else "degraded", **checks},
    )

@app.get("/")
async def root():
    return {"message": "Welcome to TradeMentor AI API"}

from app.api import zerodha
app.include_router(zerodha.router, prefix="/api/zerodha", tags=["zerodha"])

from app.api import trades
app.include_router(trades.router, prefix="/api/trades", tags=["trades"])

from app.api import positions, webhooks, risk, alerts, settings as settings_api, analytics
app.include_router(positions.router, prefix="/api/positions", tags=["positions"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(risk.router, prefix="/api/risk", tags=["risk"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])

from app.api import behavioral
app.include_router(behavioral.router, prefix="/api/behavioral", tags=["behavioral"])

from app.api import coach
app.include_router(coach.router, prefix="/api/coach", tags=["coach"])

from app.api import reports
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])

from app.api import goals
app.include_router(goals.router, prefix="/api/goals", tags=["goals"])

from app.api import websocket
app.include_router(websocket.router, prefix="/api", tags=["websocket"])

from app.api import notifications
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])

from app.api import journal
app.include_router(journal.router, prefix="/api/journal", tags=["journal"])

from app.api import profile
app.include_router(profile.router, prefix="/api/profile", tags=["profile"])

from app.api import cooldown
app.include_router(cooldown.router, prefix="/api/cooldown", tags=["cooldown"])

from app.api import personalization
app.include_router(personalization.router, prefix="/api/personalization", tags=["personalization"])

from app.api import danger_zone
app.include_router(danger_zone.router, prefix="/api/danger-zone", tags=["danger-zone"])

from app.api import shield
app.include_router(shield.router, prefix="/api/shield", tags=["shield"])

