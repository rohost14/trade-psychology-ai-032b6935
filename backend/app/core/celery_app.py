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
        "app.tasks.reconciliation_tasks",
        "app.tasks.position_monitor_tasks",
        "app.tasks.guardrail_tasks",
        "app.tasks.portfolio_sync_tasks",
        "app.tasks.intent_tasks",
        "app.tasks.maintenance_tasks",
        "app.tasks.market_data_tasks",
        "app.tasks.admin_watchdog_tasks",
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
    #
    # NOTE the `bulk` queue. It has no route entry because nothing is routed there
    # by name — the EOD dispatcher sends to it explicitly per call
    # (sync_trades_for_account.apply_async(..., queue="bulk")). The same task is
    # latency-sensitive when a user presses Sync and pure batch when the 15:35 job
    # fans it out, so the queue is chosen at dispatch, not by task name.
    #
    # Why it exists: process_webhook_trade — the live path that produces real-time
    # behavioural alerts — runs on `trades`. When the EOD job queued thousands of
    # syncs onto that same queue, every live fill's alert waited behind the batch.
    # Alerts stopped being live at exactly the moment the market closed.
    # The worker must consume `bulk` (see Procfile) or EOD syncs will never run.
    task_routes={
        "app.tasks.trade_tasks.*": {"queue": "trades"},
        "app.tasks.alert_tasks.*": {"queue": "alerts"},
        "app.tasks.report_tasks.*": {"queue": "reports"},
        # checkpoint_tasks archived 2026-09-03: nothing invoked it. It took
        # required (alert_id, broker_account_id) args so it could not be put
        # on beat, but it made 2 Kite REST calls per alert plus one at T+30
        # and had no caller at all. Preserved in tasks/_archive/.
        "app.tasks.reconciliation_tasks.*": {"queue": "trades"},
        "app.tasks.position_monitor_tasks.*": {"queue": "trades"},
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
        # Admin infra watchdog — DB/Redis/error-spike check; emails superadmins on trouble
        # (self-cooldown prevents spam). Every 5 minutes.
        "admin-health-watchdog": {
            "task": "app.tasks.admin_watchdog_tasks.admin_health_watchdog",
            "schedule": 300.0,
        },
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
        # Live premium destruction (E4) — every 60s, market hours only.
        # "live-premium-monitor" was here until 2026-08-27 (Pattern #8 review).
        # It re-read every connected account's positions and profile once a
        # minute to check a number that only changes when a price does - roughly
        # 20,001 database round trips per minute at 10,000 users, in a serial
        # loop, which does not fit inside its own 60-second period. Premium-loss
        # crossings are now evaluated on the tick itself against in-memory state
        # (`services/live_risk_state.py`), with the database read only when a
        # position or a rule changes. Latency went from up to 60 seconds to
        # sub-second, and the hot path performs no I/O at all.
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

        # NOTE: position-monitor is NOT a beat task.
        # It is triggered per-trade fill in trade_tasks.py:
        #   check_position_overexposure    — immediately after every COMPLETE fill
        #   check_holding_loser_scheduled  — 30 min after BUY fill (self-reschedules)
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
                # F6: verify the broker's TLS cert (Upstash presents a valid one).
                # CERT_NONE disabled verification → MITM-able broker traffic.
                "ssl_cert_reqs": ssl.CERT_REQUIRED
            }
            # No redis_backend_use_ssl — result backend is disabled
        )


# Auto-configure for Upstash if URL starts with rediss://
if settings.REDIS_URL.startswith("rediss://"):
    configure_for_upstash()


# ── F1 regression guard ───────────────────────────────────────────────────────
# The worker (Procfile) consumes exactly these queues. Any beat-scheduled task
# whose routed queue is NOT in this set would silently never execute — the
# deep-review P0-F1 bug (report dispatch, intent pushes, behavior_events
# partition upkeep, market-data token refresh, watchdog all died this way).
# Keep this in sync with the Procfile `worker --queues=...`. Tasks with no
# task_routes entry fall through to Celery's default queue, "celery".
CONSUMED_QUEUES = {"celery", "trades", "alerts", "reports"}


def _resolve_task_queue(task_name: str) -> str:
    """Resolve the queue a task routes to via task_routes globs; default 'celery'."""
    routes = celery_app.conf.task_routes or {}
    for pattern, cfg in routes.items():
        prefix = pattern[:-1] if pattern.endswith("*") else pattern
        if task_name == pattern or task_name.startswith(prefix):
            queue = (cfg or {}).get("queue")
            if queue:
                return queue
    return "celery"  # Celery's default queue (task_default_queue is unset)


def _warn_orphaned_beat_tasks() -> None:
    """Log CRITICAL for any beat-scheduled task whose queue no worker consumes.
    Logging only (never raises) — surfaces the P0-F1 misconfiguration class at boot."""
    import logging as _logging
    _log = _logging.getLogger(__name__)
    orphaned = [
        f"{name} → {spec.get('task', '')} (queue={_resolve_task_queue(spec.get('task', ''))})"
        for name, spec in (celery_app.conf.beat_schedule or {}).items()
        if _resolve_task_queue(spec.get("task", "")) not in CONSUMED_QUEUES
    ]
    if orphaned:
        _log.critical(
            "[celery] %d scheduled task(s) route to a queue NO worker consumes — "
            "they will NEVER run. Fix task_routes or the worker --queues. "
            "Orphaned: %s. Consumed queues: %s",
            len(orphaned), "; ".join(orphaned), sorted(CONSUMED_QUEUES),
        )


_warn_orphaned_beat_tasks()


# ── R1: prefork worker DB-engine hygiene ──────────────────────────────────────
# The worker runs the prefork pool (see Procfile). asyncpg connections are NOT
# fork-safe, so each forked child must start with a clean async engine rather than
# inheriting the parent's pooled connections. Dispose on process init so the child
# lazily rebuilds its own. Best-effort; never blocks worker start.
#
# NOTE (deep-review R1, still open): tasks run `asyncio.run()` per call, creating a
# fresh event loop each time. asyncpg connections are loop-bound, so the pooled
# engine can still hand a child a connection from a previous loop. Switching off
# gevent (done) removes the unsupported gevent+asyncpg combo, but the loop-per-task
# vs connection-pool interaction must be validated under load (P14 Gate 4) and may
# need a NullPool engine in the worker or a persistent per-worker loop.
try:
    from celery.signals import worker_process_init as _worker_process_init

    @_worker_process_init.connect
    def _dispose_async_engine_on_fork(**_kwargs):
        try:
            import asyncio as _aio
            from app.core.database import engine as _engine
            _aio.run(_engine.dispose())
        except Exception:
            pass

    @_worker_process_init.connect
    def _setup_worker_logging(**_kwargs):
        # F2: wire our JSON logging + Redis error-feed handler in each worker child,
        # so Celery TASK errors reach the admin error-feed (previously only the web
        # process called setup_logging). Best-effort; runs once per forked child.
        try:
            from app.core.logging_config import setup_logging
            setup_logging()
        except Exception:
            pass
except Exception:
    pass
