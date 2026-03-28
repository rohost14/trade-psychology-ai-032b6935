"""
Celery Configuration for Async Task Processing

Uses Redis as message broker for:
- Trade processing from webhooks
- Risk detection
- Alert notifications
- Scheduled reports
"""

from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# NOTE: Do NOT install asyncioreactor here.
#
# celery_app.py is imported by both Celery workers AND the FastAPI process
# (indirectly via task modules that call .delay()). Installing asyncioreactor
# in the FastAPI process crashes KiteTicker: when KiteTicker starts its
# Twisted reactor in a background thread, asyncioreactor tries to call
# event_loop.run_forever() on uvicorn's already-running loop →
# RuntimeError: This event loop is already running.
#
# Celery workers don't use KiteTicker directly (only get_cached_ltp from Redis),
# so there is no ReactorNotRestartable risk in workers. KiteTicker's SelectReactor
# runs isolated in its own daemon thread in the FastAPI process and does not
# interfere with asyncio at all.

# celery-redbeat: Beat schedule stored in Redis, survives worker restarts.
# Without this, Beat state is in-memory and all scheduled tasks are lost
# when the worker restarts (e.g. deploy, crash, OOM).
REDBEAT_REDIS_URL = settings.REDIS_URL

# Create Celery app
# No result backend — all tasks are fire-and-forget.
# Using Redis as result backend causes data loss on restart and wastes memory.
# Task results are stored in Postgres for any task that needs them (none currently do).
celery_app = Celery(
    "tradementor",
    broker=settings.celery_broker,
    include=[
        "app.tasks.trade_tasks",
        "app.tasks.alert_tasks",
        "app.tasks.report_tasks",
        "app.tasks.checkpoint_tasks",
        "app.tasks.reconciliation_tasks",
        "app.tasks.position_monitor_tasks",
        "app.tasks.portfolio_radar_tasks",
        "app.tasks.guardrail_tasks",
        "app.tasks.portfolio_sync_tasks",
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,

    # Ignore task results — no result backend needed.
    # Individual tasks can override with @task(ignore_result=False) if they ever need results.
    task_ignore_result=True,

    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time per worker
    worker_concurrency=100,  # 100 concurrent workers — handles peak load; use --pool=gevent

    # Task routing
    task_routes={
        "app.tasks.trade_tasks.*": {"queue": "trades"},
        "app.tasks.alert_tasks.*": {"queue": "alerts"},
        "app.tasks.report_tasks.*": {"queue": "reports"},
        "app.tasks.checkpoint_tasks.*": {"queue": "alerts"},
        "app.tasks.reconciliation_tasks.*": {"queue": "trades"},
        "app.tasks.position_monitor_tasks.*": {"queue": "trades"},
        "app.tasks.portfolio_radar_tasks.*": {"queue": "trades"},
        "app.tasks.guardrail_tasks.*": {"queue": "alerts"},
        "app.tasks.portfolio_sync_tasks.*": {"queue": "trades"},
    },

    # Rate limiting (prevent overwhelming Zerodha API)
    task_annotations={
        "app.tasks.trade_tasks.sync_trades_for_account": {
            "rate_limit": "10/m"  # Max 10 syncs per minute
        },
        # Portfolio sync: max 5/min to stay within KiteConnect 10 req/sec shared limit
        "app.tasks.portfolio_sync_tasks.sync_portfolio_for_account": {
            "rate_limit": "5/m"
        },
    },

    # Retry settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Graceful shutdown: on SIGTERM, wait up to 30s for in-flight tasks to finish
    # before killing the worker. Prevents cut-off mid-task (trade saved but alerts never sent).
    worker_shutdown_timeout=30,

    # celery-redbeat: persist Beat schedule in Redis so it survives restarts.
    # Run Beat with: celery -A app.core.celery_app beat -S redbeat.RedBeatScheduler
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=settings.REDIS_URL,

    # Beat schedule for periodic tasks (uses crontab)
    #
    # NOTE: EOD reports and morning briefs are NOT here.
    # They are dispatched by APScheduler (retention_tasks.py) running inside the
    # FastAPI app process, which fires every minute and respects each user's
    # configured delivery time. Duplicating them here would cause double-sends.
    beat_schedule={
        # Commodity market close report - 11:45 PM IST (not in APScheduler)
        "commodity-eod": {
            "task": "app.tasks.report_tasks.generate_commodity_eod",
            "schedule": crontab(hour=23, minute=45),
        },
        # Weekly performance summary - every Sunday at 8:00 PM IST
        "weekly-summary": {
            "task": "app.tasks.report_tasks.send_weekly_summaries_batch",
            "schedule": crontab(hour=20, minute=0, day_of_week=0),
        },
        # EOD sync — 3:35 PM IST Mon–Fri (5 min after NSE close).
        # Catches missed webhooks + creates CompletedTrades for overnight positions
        # before Zerodha clears the day's position data.
        "eod-sync": {
            "task": "app.tasks.trade_tasks.eod_sync_all_accounts",
            "schedule": crontab(hour=15, minute=35, day_of_week="1-5"),
        },
        # EOD reconciliation — runs once daily at 4:00 AM IST (off-peak).
        "eod-reconcile": {
            "task": "app.tasks.reconciliation_tasks.reconcile_trades",
            "schedule": crontab(hour=4, minute=0),
        },
        # Guardrail rule monitor — every 60s during market hours (09:15–15:25 IST Mon–Fri)
        # Internal market-hours check inside the task body (beat doesn't support time ranges).
        "check-guardrails": {
            "task": "app.tasks.guardrail_tasks.check_guardrail_rules",
            "schedule": 60.0,  # every 60 seconds
        },
        # NOTE: position-monitor and portfolio-radar are NOT beat tasks.
        # They are triggered per-trade fill in trade_tasks.py:
        #   check_position_overexposure    — immediately after every COMPLETE fill
        #   check_holding_loser_scheduled  — 30 min after BUY fill (self-reschedules)
        #   run_portfolio_radar_for_account — immediately after behavior detection
    },
)


# Optional: Configure for Upstash Redis (TLS required)
def configure_for_upstash():
    """
    Call this if using Upstash Redis which requires TLS.
    Upstash URL format: rediss://default:PASSWORD@HOST:PORT
    """
    if settings.REDIS_URL.startswith("rediss://"):
        import ssl
        celery_app.conf.update(
            broker_use_ssl={
                "ssl_cert_reqs": ssl.CERT_NONE   # integer constant, not the string
            }
            # No redis_backend_use_ssl — result backend is disabled
        )


# Auto-configure for Upstash if URL starts with rediss://
if settings.REDIS_URL.startswith("rediss://"):
    configure_for_upstash()
