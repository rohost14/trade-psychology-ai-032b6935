"""
Admin task status — query RedBeat Redis keys to show Celery beat schedule health.
Returns last run time, next run time, and status for each scheduled task.
Exposes manual trigger for safe one-off task execution.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api.admin.deps import get_current_admin, require_role
from app.core.database import get_db
from app.core.config import settings
from app.core.market_hours import market_minutes
from app.models.completed_trade import CompletedTrade
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# All beat schedule entries — keys must match celery_app.py beat_schedule exactly
BEAT_TASKS = [
    {"key": "retention-reports-tick",  "name": "Retention Reports Tick",        "schedule": "Every 60s"},
    {"key": "morning-intent",          "name": "Morning Intent Push",            "schedule": "Mon–Fri 08:30 IST"},
    {"key": "eod-sync",               "name": "EOD Trade Sync",                 "schedule": "Mon–Fri 15:35 IST"},
    {"key": "eod-comparison",         "name": "EOD Comparison Push",            "schedule": "Mon–Fri 15:35 IST"},
    {"key": "daily-score",            "name": "Daily Discipline Score Push",    "schedule": "Daily 18:00 IST"},
    {"key": "personalization-refresh", "name": "Personalization Pattern Refresh","schedule": "Daily 18:15 IST"},
    {"key": "commodity-eod",          "name": "Commodity EOD Report",           "schedule": "Daily 23:45 IST"},
    {"key": "commodity-weekly",       "name": "Commodity Weekly Summary",       "schedule": "Fri 12:00 IST"},
    {"key": "weekly-summary",         "name": "Weekly Performance Summary",     "schedule": "Sun 20:00 IST"},
    {"key": "eod-reconcile",          "name": "EOD Trade Reconciliation",       "schedule": "Daily 04:00 IST"},
    {"key": "check-guardrails",       "name": "Guardrail Rule Monitor",         "schedule": "Every 60s (market hours)"},
]

# Tasks safe to manually trigger from admin (excludes frequent polling tasks)
TRIGGERABLE_TASKS = {
    "eod-reconcile":           "app.tasks.reconciliation_tasks.reconcile_trades",
    "personalization-refresh": "app.tasks.intent_tasks.refresh_personalization_patterns",
    "commodity-eod":           "app.tasks.report_tasks.generate_commodity_eod",
    "weekly-summary":          "app.tasks.report_tasks.send_weekly_summaries_batch",
    "eod-sync":                "app.tasks.trade_tasks.eod_sync_all_accounts",
    "morning-intent":          "app.tasks.intent_tasks.send_morning_intent_push",
    "daily-score":             "app.tasks.intent_tasks.send_daily_score_push",
}


def _get_redbeat_info(r, task_key: str) -> dict:
    try:
        import json
        raw = r.get(f"redbeat:{task_key}")
        if not raw:
            return {"status": "no_data", "last_run_at": None, "next_run_at": None}
        data = json.loads(raw)
        return {
            "status":      "scheduled",
            "last_run_at": data.get("last_run_at"),
            "next_run_at": data.get("next_run_at"),
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)[:80], "last_run_at": None, "next_run_at": None}


@router.get("/tasks")
async def get_task_status(_: dict = Depends(get_current_admin)):
    """Return beat schedule status + queue depths + recent failures for all Celery tasks."""
    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=3)
        r.ping()
        connected = True
    except Exception as e:
        return {"redis_connected": False, "error": str(e)[:120], "tasks": []}

    tasks = []
    for t in BEAT_TASKS:
        info = _get_redbeat_info(r, t["key"])
        tasks.append({
            "key":          t["key"],
            "name":         t["name"],
            "schedule":     t["schedule"],
            "triggerable":  t["key"] in TRIGGERABLE_TASKS,
            **info,
        })

    queues = {}
    for q_name in ["celery", "ai_worker"]:
        try:
            queues[q_name] = r.llen(q_name)
        except Exception:
            queues[q_name] = None

    failed_tasks = []
    try:
        import json as _json
        scan_count = 0
        for key in r.scan_iter("celery-task-meta-*", count=200):
            if scan_count >= 200:
                break
            scan_count += 1
            try:
                raw = r.get(key)
                if not raw:
                    continue
                meta = _json.loads(raw)
                if meta.get("status") == "FAILURE":
                    failed_tasks.append({
                        "task_id":   key.replace("celery-task-meta-", ""),
                        "traceback": (meta.get("traceback") or "")[:200],
                        "result":    str(meta.get("result", ""))[:100],
                    })
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Failed task scan error: {e}")

    return {
        "redis_connected": connected,
        "tasks":           tasks,
        "queue_depths":    queues,
        "failed_tasks":    failed_tasks,
        "failed_count":    len(failed_tasks),
    }


@router.post("/tasks/{task_key}/trigger")
async def trigger_task(
    task_key: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("superadmin", "ops")),
):
    """
    Manually trigger a Celery task by beat schedule key.
    Only tasks in TRIGGERABLE_TASKS can be triggered from admin.
    Audited with the triggering admin's email.
    """
    from app.api.admin.audit_writer import audit
    if task_key not in TRIGGERABLE_TASKS:
        raise HTTPException(
            status_code=404,
            detail=f"Task '{task_key}' is not manually triggerable. "
                   f"Triggerable: {list(TRIGGERABLE_TASKS.keys())}"
        )

    task_path = TRIGGERABLE_TASKS[task_key]
    module_path, func_name = task_path.rsplit(".", 1)

    try:
        import importlib
        module    = importlib.import_module(module_path)
        task_func = getattr(module, func_name)
        result    = task_func.delay()
    except Exception as e:
        logger.error(f"Admin task trigger failed: {task_key} — {e}")
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {e}")

    await audit(db, admin["email"], "trigger_task",
                target_type="task", target_id=task_key,
                details={"celery_id": result.id, "task_path": task_path})

    logger.info(f"Admin {admin['email']} triggered task: {task_key} → {result.id}")
    return {"status": "queued", "task_key": task_key, "celery_id": result.id}


@router.post("/backfill-duration")
async def backfill_duration_minutes(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_role("superadmin")),
):
    """
    One-time maintenance: recalculate duration_minutes for all CompletedTrades.
    Safe to run multiple times.
    """
    result = await db.execute(
        select(CompletedTrade).where(
            CompletedTrade.entry_time.is_not(None),
            CompletedTrade.exit_time.is_not(None),
        )
    )
    trades = result.scalars().all()

    updated = already_correct = skipped = 0

    for trade in trades:
        try:
            new_duration = market_minutes(
                trade.entry_time,
                trade.exit_time,
                exchange=trade.exchange or "NFO",
            )
        except Exception as e:
            logger.warning(f"[backfill-duration] skipping {trade.id}: {e}")
            skipped += 1
            continue

        if new_duration != trade.duration_minutes:
            trade.duration_minutes = new_duration
            updated += 1
        else:
            already_correct += 1

    await db.commit()
    logger.info(f"[backfill-duration] done — updated={updated} already_correct={already_correct} skipped={skipped}")
    return {"status": "done", "total": len(trades), "updated": updated,
            "already_correct": already_correct, "skipped": skipped}
