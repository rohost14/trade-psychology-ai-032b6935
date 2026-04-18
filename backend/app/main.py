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

    # Warn if ADMIN_JWT_SECRET is not set — admin panel will 404 silently without it.
    if not settings.ADMIN_JWT_SECRET:
        logger.warning(
            "ADMIN_JWT_SECRET is not set. All /api/admin/* endpoints will return 404. "
            "Set this env var to enable the admin panel."
        )
    else:
        logger.info("ADMIN_JWT_SECRET configured — admin panel enabled.")

    # Validate ENCRYPTION_KEY at startup — fail fast rather than breaking users at runtime.
    # A changed or invalid key makes all stored tokens undecryptable.
    try:
        from cryptography.fernet import Fernet
        Fernet(settings.ENCRYPTION_KEY.encode())
        logger.info("ENCRYPTION_KEY validated OK.")
    except Exception as e:
        raise RuntimeError(
            f"ENCRYPTION_KEY is invalid: {e}. "
            "Generate a valid key with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\". "
            "WARNING: changing this key will make all stored access tokens undecryptable — users must reconnect."
        ) from e

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

    # Start Redis event subscriber — bridges Celery → WebSocket in real-time.
    # When Celery processes a trade or creates an alert, it publishes to Redis.
    # This background task receives those events and pushes to connected browsers.
    _event_subscriber_task = None
    try:
        import asyncio as _asyncio
        from app.core.event_bus import start_event_subscriber

        def _on_subscriber_done(task):
            """Log if the subscriber dies unexpectedly (not a clean shutdown cancel)."""
            if task.cancelled():
                return  # Normal shutdown
            exc = task.exception()
            if exc:
                logger.critical(f"[event_bus] Event subscriber task died: {exc}", exc_info=exc)
                try:
                    import sentry_sdk
                    sentry_sdk.capture_exception(exc)
                except Exception:
                    pass

        _event_subscriber_task = _asyncio.create_task(start_event_subscriber())
        _event_subscriber_task.add_done_callback(_on_subscriber_done)
        logger.info("Redis event subscriber started.")
    except Exception as e:
        logger.error(f"Event subscriber failed to start: {e}")

    # One-time repair: fix CompletedTrades whose realized_pnl was overwritten by the
    # reconciliation bug introduced in session 33 (49ba0b8).  For NSE/NFO instruments
    # the FIFO engine is authoritative; Zerodha's pos.pnl diverges because it spans
    # all rounds of the symbol while FIFO creates per-round records.
    # This runs silently in the background — no user action required.
    async def _repair_nse_pnl():
        try:
            from app.core.database import SessionLocal
            from app.models.completed_trade import CompletedTrade
            from sqlalchemy import select
            from datetime import datetime, timezone, timedelta

            FIFO_ACCURATE = {"NSE", "BSE", "NFO", "BFO"}
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            repaired = 0

            async with SessionLocal() as db:
                result = await db.execute(
                    select(CompletedTrade).where(
                        CompletedTrade.exchange.in_(list(FIFO_ACCURATE)),
                        CompletedTrade.exit_time >= cutoff,
                        CompletedTrade.avg_entry_price.isnot(None),
                        CompletedTrade.avg_exit_price.isnot(None),
                    )
                )
                cts = result.scalars().all()
                for ct in cts:
                    entry = float(ct.avg_entry_price or 0)
                    exit_ = float(ct.avg_exit_price or 0)
                    qty = int(ct.total_quantity or 0)
                    if qty == 0:
                        continue
                    expected = (exit_ - entry) * qty if ct.direction == "LONG" else (entry - exit_) * qty
                    actual = float(ct.realized_pnl or 0)
                    if abs(expected - actual) > 0.5:
                        ct.realized_pnl = round(expected, 4)
                        repaired += 1
                if repaired:
                    await db.commit()
                    logger.info(f"[startup repair] Fixed {repaired} NSE/NFO CompletedTrade P&L records.")
        except Exception as e:
            logger.warning(f"[startup repair] P&L repair skipped: {e}")

    _asyncio.create_task(_repair_nse_pnl())

    # Backfill pnl_pct for CompletedTrades created before migration 055.
    async def _backfill_pnl_pct():
        try:
            from app.core.database import SessionLocal
            from app.models.completed_trade import CompletedTrade
            from app.services.position_ledger_service import _compute_pnl_pct
            from sqlalchemy import select

            async with SessionLocal() as db:
                result = await db.execute(
                    select(CompletedTrade).where(
                        CompletedTrade.pnl_pct.is_(None),
                        CompletedTrade.avg_entry_price.isnot(None),
                        CompletedTrade.avg_exit_price.isnot(None),
                    )
                )
                cts = result.scalars().all()
                filled = 0
                for ct in cts:
                    pct = _compute_pnl_pct(
                        float(ct.avg_entry_price),
                        float(ct.avg_exit_price),
                        ct.direction or "LONG",
                    )
                    if pct is not None:
                        ct.pnl_pct = pct
                        filled += 1
                if filled:
                    await db.commit()
                    logger.info(f"[startup backfill] Filled pnl_pct for {filled} CompletedTrade records.")
        except Exception as e:
            logger.warning(f"[startup backfill] pnl_pct backfill skipped: {e}")

    _asyncio.create_task(_backfill_pnl_pct())

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
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # CSP: allow same-origin scripts/styles + Sentry DSN reporting endpoint.
    # Tighten further in production by replacing 'unsafe-inline' with nonces.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self' https://*.sentry.io wss:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    )
    # Prevent browsers from caching dynamic API responses.
    # Without this, browsers apply heuristic caching to GET responses —
    # re-fetches after a sync serve stale data until a hard refresh.
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


@app.middleware("http")
async def maintenance_mode_middleware(request: Request, call_next):
    """Return 503 for all non-health API requests when MAINTENANCE_MODE is true.
    The /health endpoint always passes through so load balancers can still check.
    """
    if settings.MAINTENANCE_MODE and request.url.path not in ("/health", "/"):
        return JSONResponse(
            status_code=503,
            content={"detail": settings.MAINTENANCE_MESSAGE},
            headers={"Retry-After": "300"},
        )
    return await call_next(request)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    from app.core.request_context import request_id_var

    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id

    # Set ContextVar so all log records in this request carry request_id
    # (works via RequestIdFilter registered in setup_logging)
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)

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

from app.api import portfolio_radar
app.include_router(portfolio_radar.router)

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

from app.api import prometheus_metrics
app.include_router(prometheus_metrics.router, tags=["monitoring"])

from app.api import guardrails
app.include_router(guardrails.router, prefix="/api/guardrails", tags=["guardrails"])

from app.api import portfolio_chat
app.include_router(portfolio_chat.router, prefix="/api/portfolio-chat", tags=["portfolio-chat"])

# Admin panel — separate JWT auth, returns 404 for non-admins
from app.api.admin import auth as admin_auth, overview as admin_overview
from app.api.admin import users as admin_users, system as admin_system
from app.api.admin import insights as admin_insights, config_api as admin_config
from app.api.admin import audit as admin_audit, broadcast as admin_broadcast
from app.api.admin import tasks as admin_tasks
app.include_router(admin_auth.router,      prefix="/api/admin/auth", tags=["admin"])
app.include_router(admin_overview.router,  prefix="/api/admin",      tags=["admin"])
app.include_router(admin_users.router,     prefix="/api/admin",      tags=["admin"])
app.include_router(admin_system.router,    prefix="/api/admin",      tags=["admin"])
app.include_router(admin_insights.router,  prefix="/api/admin",      tags=["admin"])
app.include_router(admin_config.router,    prefix="/api/admin",      tags=["admin"])
app.include_router(admin_audit.router,     prefix="/api/admin",      tags=["admin"])
app.include_router(admin_broadcast.router, prefix="/api/admin",      tags=["admin"])
app.include_router(admin_tasks.router,     prefix="/api/admin",      tags=["admin"])

