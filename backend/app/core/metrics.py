"""
Engine metrics — P1 observability baseline (Principal Engineer review S9:
"the system cannot tell you it is failing").

Redis-backed, daily-bucketed counters and timing aggregates. Deliberately
NOT Prometheus at this tier — one dependency-free module, one admin
endpoint, 7-day retention. Migrate to a real TSDB when there is a real
fleet to watch.

Counters   metrics:c:{name}:{YYYYMMDD}            -> int
Timings    metrics:t:{name}:{YYYYMMDD}:sum|cnt|max -> ms aggregates

All writes are best-effort: metrics must never break the pipeline.
"""
import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict

logger = logging.getLogger(__name__)

_TTL = 7 * 86400

# Registry of known metric names (admin endpoint iterates this — a counter
# nobody registered is a typo, not a signal).
COUNTERS = (
    "behavior_lock_exhausted",
    "behavior_bulk_lock_abort",
    "behavior_requeued",
    "trades_analyzed",
    "trades_skipped_idempotent",
    "events_written",
    "events_conflict_skipped",
    "alerts_created",
    "alerts_deduped",
    "notifications_dispatched",
    "notifications_stale_suppressed",
)
TIMINGS = (
    "alert_e2e_lag_ms",      # trade exit -> detection persisted (the SLO)
    "analyze_ms",            # context load + detectors
    "persist_ms",            # alerts + events write
    "death_spiral_ms",
)


def _r():
    from app.core.redis_pool import get_sync_redis
    return get_sync_redis()


def _day() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def incr(name: str, n: int = 1) -> None:
    try:
        key = f"metrics:c:{name}:{_day()}"
        r = _r()
        pipe = r.pipeline()
        pipe.incrby(key, n)
        pipe.expire(key, _TTL)
        pipe.execute()
    except Exception:
        pass  # never break the pipeline for a counter


def observe_ms(name: str, ms: float) -> None:
    try:
        day = _day()
        r = _r()
        pipe = r.pipeline()
        pipe.incrbyfloat(f"metrics:t:{name}:{day}:sum", ms)
        pipe.incrby(f"metrics:t:{name}:{day}:cnt", 1)
        pipe.expire(f"metrics:t:{name}:{day}:sum", _TTL)
        pipe.expire(f"metrics:t:{name}:{day}:cnt", _TTL)
        pipe.execute()
        # max: read-modify-write race acceptable for an ops max
        cur = r.get(f"metrics:t:{name}:{day}:max")
        if cur is None or ms > float(cur):
            r.set(f"metrics:t:{name}:{day}:max", ms, ex=_TTL)
    except Exception:
        pass


@contextmanager
def timer(name: str):
    start = time.monotonic()
    try:
        yield
    finally:
        observe_ms(name, (time.monotonic() - start) * 1000)


def snapshot(days: int = 2) -> Dict:
    """Today (+ yesterday) readout for the admin endpoint."""
    from datetime import timedelta
    out: Dict = {}
    try:
        r = _r()
        for offset in range(days):
            day = (datetime.now(timezone.utc) - timedelta(days=offset)).strftime("%Y%m%d")
            counters = {}
            for name in COUNTERS:
                v = r.get(f"metrics:c:{name}:{day}")
                if v is not None:
                    counters[name] = int(v)
            timings = {}
            for name in TIMINGS:
                cnt = r.get(f"metrics:t:{name}:{day}:cnt")
                if cnt and int(cnt) > 0:
                    total = float(r.get(f"metrics:t:{name}:{day}:sum") or 0)
                    mx = float(r.get(f"metrics:t:{name}:{day}:max") or 0)
                    timings[name] = {
                        "count": int(cnt),
                        "avg_ms": round(total / int(cnt), 1),
                        "max_ms": round(mx, 1),
                    }
            out[day] = {"counters": counters, "timings": timings}
    except Exception as e:
        out["error"] = str(e)
    return out


def health_flags(snap: Dict) -> Dict:
    """
    Poor-man's alarms: threshold evaluation over today's snapshot.
    Surfaced in the admin endpoint; a real alerting pipe replaces this later.
    """
    day = _day()
    today = snap.get(day, {})
    c = today.get("counters", {})
    t = today.get("timings", {})
    flags = {}
    if c.get("behavior_lock_exhausted", 0) > 0:
        flags["detection_skips"] = f"{c['behavior_lock_exhausted']} lock exhaustions today (requeued)"
    if c.get("behavior_bulk_lock_abort", 0) > 0:
        flags["bulk_aborts"] = f"{c['behavior_bulk_lock_abort']} bulk sync aborts"
    lag = t.get("alert_e2e_lag_ms", {})
    if lag and lag.get("avg_ms", 0) > 3000:
        flags["slo_breach"] = f"avg e2e lag {lag['avg_ms']}ms exceeds 3s SLO"
    written = c.get("events_written", 0)
    conflicts = c.get("events_conflict_skipped", 0)
    if written + conflicts > 0 and conflicts > written:
        flags["reprocessing_heavy"] = f"{conflicts} conflict-skips vs {written} writes (retries/syncs dominating)"
    return flags
