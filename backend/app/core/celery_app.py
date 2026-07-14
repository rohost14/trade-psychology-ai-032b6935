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
        "app.tasks.retention_tasks",
        "app.tasks.checkpoint_tasks",
        "app.tasks.reconciliation_tasks",
        "app.tasks.position_monitor_tasks",
        "app.tasks.portfolio_radar_tasks",
        "app.tasks.guardrail_tasks",
        "app.tasks.portfolio_sync_tasks",
        "app.tasks.intent_tasks",
        "app.tasks.maintenance_tasks",
        "app.tasks.market_data_tasks",
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
    worker_concurrency=4,  # 4 prefork workers — safe for 512MB Render free tier (~100MB each)
    # Heartbeat every 60s instead of default 2s — reduces Redis command count ~30× on Upstash free tier.
    # Workers are still detected as "lost" after 3 missed heartbeats (= 3 minutes), acceptable.
    worker_heartbeat=60,

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
    # Redbeat checks schedule every 5s by default → ~1M Redis commands/month.
    # 60s interval is sufficient: our shortest beat task fires every 60s anyway.
    redbeat_lock_timeout=90,  # seconds (must be > max_loop_interval)
    beat_max_loop_interval=60,  # seconds between schedule checks (default: 5s)

    # Beat schedule for periodic tasks (uses crontab)
    #
    beat_schedule={
        # Fires every 60s. Each user's configured delivery time is checked inside
        # the task — reports only send to users whose time matches the current IST minute.
        # Single Celery beat process means no N× duplication (replaces APScheduler).
        "retention-reports-tick": {
            "task": "app.tasks.retention_tasks.dispatch_reports_tick",
            "schedule": 60.0,
        },
        # Commodity daily EOD report - 11:45 PM IST (after MCX close at 11:30 PM)
        "commodity-eod": {
            "task": "app.tasks.report_tasks.generate_commodity_eod",
            "schedule": crontab(hour=23, minute=45),
        },
        # Commodity weekly summary - every Friday at 12:00 PM IST
        # Gives commodity traders a midday Friday snapshot of the week.
        # Stored as GeneratedReport(report_type='commodity_weekly') — in-app only.
        "commodity-weekly": {
            "task": "app.tasks.report_tasks.generate_commodity_weekly_report",
            "schedule": crontab(hour=12, minute=0, day_of_week=5),
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
        # Morning intent push — 8:30 AM IST Mon–Fri.
        # Sends pre-market reminder with user's configured limits.
        "morning-intent": {
            "task": "app.tasks.intent_tasks.send_morning_intent_push",
            "schedule": crontab(hour=8, minute=30, day_of_week="1-5"),
        },
        # EOD comparison push — 3:35 PM IST Mon–Fri.
        # Compares planned intent limits vs actual session metrics.
        "eod-comparison": {
            "task": "app.tasks.intent_tasks.send_eod_comparison_push",
            "schedule": crontab(hour=15, minute=35, day_of_week="1-5"),
        },
        # Daily discipline score push — 6:00 PM IST daily (including weekends for swing traders).
        # Single score + streak to pull users back into the app.
        "daily-score": {
            "task": "app.tasks.intent_tasks.send_daily_score_push",
            "schedule": crontab(hour=18, minute=0),
        },
        # Personalization pattern refresh — 6:15 PM IST daily.
        # Keeps danger_days/danger_hours current so morning intent push can include context.
        # Runs 15 min after daily-score to avoid DB contention.
        "personalization-refresh": {
            "task": "app.tasks.intent_tasks.refresh_personalization_patterns",
            "schedule": crontab(hour=18, minute=15),
        },
        # behavior_events partition upkeep (P2): idempotently creates the next
        # 3 monthly partitions on the 1st and 15th (twice for redundancy) at
        # 02:00 IST. Nobody creates partitions by hand - ever.
        "ensure-behavior-event-partitions": {
            "task": "app.tasks.maintenance_tasks.ensure_behavior_event_partitions",
            "schedule": crontab(hour=2, minute=0, day_of_month="1,15"),
        },
        # Capital-vs-margin reality check (nightly 17:45 IST, after EOD sync):
        # nudges when declared capital persistently exceeds 1.5x the account.
        "check-capital-reality": {
            "task": "app.tasks.maintenance_tasks.check_capital_reality",
            "schedule": crontab(hour=17, minute=45, day_of_week="1-5"),
        },
        # Tilt recovery recognition (16:00 IST, after market + squareoff):
        # positive reinforcement for the trader who STOPPED after an alert.
        "recognize-tilt-recovery": {
            "task": "app.tasks.maintenance_tasks.recognize_tilt_recovery",
            "schedule": crontab(hour=16, minute=0, day_of_week="1-5"),
        },
        # Guardrail rule monitor — every 60s during market hours (09:15–15:25 IST Mon–Fri)
        # Internal market-hours check inside the task body (beat doesn't support time ranges).
        "check-guardrails": {
            "task": "app.tasks.guardrail_tasks.check_guardrail_rules",
            "schedule": 60.0,  # every 60 seconds
        },
        # Market-data token refresh — 8:45 AM IST Mon–Fri.
        # Refreshes the dedicated ZERODHA_MD_* account access_token before market open.
        # SharedPriceStream picks up the new token automatically on next ticker build.
        # No-op if ZERODHA_MD_* credentials are not configured.
        "refresh-market-data-token": {
            "task": "app.tasks.market_data_tasks.refresh_market_data_token",
            "schedule": crontab(hour=8, minute=45, day_of_week="1-5"),
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
