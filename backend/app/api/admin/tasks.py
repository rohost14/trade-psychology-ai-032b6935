"""
Admin task status — query RedBeat Redis keys to show Celery beat schedule health.
Returns last run time, next run time, and status for each scheduled task.
"""
from fastapi import APIRouter, Depends
from app.api.admin.deps import get_current_admin
from app.core.config import settings
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Known beat tasks — names must match celery_app.py beat_schedule keys
BEAT_TASKS = [
    {"key": "commodity-eod",  "name": "Commodity EOD Report",       "schedule": "Daily 23:45 IST"},
    {"key": "weekly-summary", "name": "Weekly Summary (all users)",  "schedule": "Sun 20:00 IST"},
    {"key": "eod-reconcile",  "name": "EOD Trade Reconciliation",    "schedule": "Daily 04:00 IST"},
]


def _get_redbeat_info(r, task_key: str) -> dict:
    """
    RedBeat stores task state under key: redbeat:<task_key>
    The value is a JSON blob with 'last_run_at' and 'next_run_at'.
    """
    try:
        import json
        raw = r.get(f"redbeat:{task_key}")
        if not raw:
            return {"status": "no_data", "last_run_at": None, "next_run_at": None}
        data = json.loads(raw)
        last = data.get("last_run_at")
        nxt  = data.get("next_run_at")
        return {
            "status":      "scheduled",
            "last_run_at": last,
            "next_run_at": nxt,
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)[:80], "last_run_at": None, "next_run_at": None}


@router.get("/tasks")
async def get_task_status(_: dict = Depends(get_current_admin)):
    """Return beat schedule status for all known Celery tasks."""
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
            **info,
        })

    # Also report Celery queue depth per queue (default + any named queues)
    queues = {}
    for q_name in ["celery", "ai_worker"]:
        try:
            queues[q_name] = r.llen(q_name)
        except Exception:
            queues[q_name] = None

    # Count recent Celery task failures from the result backend.
    # Scans up to 200 celery-task-meta-* keys — approximate, not exhaustive.
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
                        "task_id":    key.replace("celery-task-meta-", ""),
                        "traceback":  (meta.get("traceback") or "")[:200],
                        "result":     str(meta.get("result", ""))[:100],
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
