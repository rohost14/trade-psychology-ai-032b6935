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
    worker_concurrency=4,  # 4 concurrent workers

    # Task routing
    task_routes={
        "app.tasks.trade_tasks.*": {"queue": "trades"},
        "app.tasks.alert_tasks.*": {"queue": "alerts"},
        "app.tasks.report_tasks.*": {"queue": "reports"},
        "app.tasks.checkpoint_tasks.*": {"queue": "alerts"},
        "app.tasks.reconciliation_tasks.*": {"queue": "trades"},
    },

    # Rate limiting (prevent overwhelming Zerodha API)
    task_annotations={
        "app.tasks.trade_tasks.sync_trades_for_account": {
            "rate_limit": "10/m"  # Max 10 syncs per minute
        },
    },

    # Retry settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Beat schedule for periodic tasks (uses crontab)
    beat_schedule={
        # End of day report - 4:00 PM IST (after equity market close)
        "eod-report": {
            "task": "app.tasks.report_tasks.generate_eod_reports",
            "schedule": crontab(hour=16, minute=0),
        },
        # Morning prep - 8:30 AM IST (before market open)
        "morning-prep": {
            "task": "app.tasks.report_tasks.send_morning_prep",
            "schedule": crontab(hour=8, minute=30),
        },
        # Commodity market close report - 11:45 PM IST
        "commodity-eod": {
            "task": "app.tasks.report_tasks.generate_commodity_eod",
            "schedule": crontab(hour=23, minute=45),
        },
        # Reconciliation poller — every 3 minutes, all day.
        # The task itself skips outside 09:14–15:31 IST on weekdays.
        # Catches trades missed by webhooks (network blips, Celery downtime).
        "reconcile-trades": {
            "task": "app.tasks.reconciliation_tasks.reconcile_trades",
            "schedule": crontab(minute="*/3"),
        },
    },
)


# Optional: Configure for Upstash Redis (TLS required)
def configure_for_upstash():
    """
    Call this if using Upstash Redis which requires TLS.
    Upstash URL format: rediss://default:PASSWORD@HOST:PORT
    """
    if settings.REDIS_URL.startswith("rediss://"):
        celery_app.conf.update(
            broker_use_ssl={
                "ssl_cert_reqs": "CERT_NONE"
            }
            # No redis_backend_use_ssl — result backend is disabled
        )


# Auto-configure for Upstash if URL starts with rediss://
if settings.REDIS_URL.startswith("rediss://"):
    configure_for_upstash()
