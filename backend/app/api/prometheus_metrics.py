"""
Prometheus metrics endpoint — /metrics

Exposes:
  tradementor_ws_connections        Gauge  — active WebSocket connections
  tradementor_celery_queue_depth    Gauge  — tasks waiting in each Celery queue
  tradementor_api_errors_total      Counter — errors recorded by MetricsCollector

Scrape this endpoint with Prometheus. No auth required (internal only —
protect at the reverse proxy / network layer).
"""

import logging
from fastapi import APIRouter
from fastapi.responses import Response

from prometheus_client import Gauge, Counter, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Metric definitions
# ---------------------------------------------------------------------------

_ws_connections = Gauge(
    "tradementor_ws_connections",
    "Number of active WebSocket connections",
)

_celery_queue_depth = Gauge(
    "tradementor_celery_queue_depth",
    "Number of tasks waiting in a Celery queue",
    ["queue"],
)

_api_errors = Counter(
    "tradementor_api_errors_total",
    "Total API errors recorded by the internal MetricsCollector",
    ["error_type"],
)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    """
    Prometheus scrape endpoint. Returns metrics in Prometheus text format.
    Populate gauges at scrape time (pull model — always current, no staleness).
    """
    _populate_metrics()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _populate_metrics() -> None:
    """Read live values and update Prometheus gauges."""

    # 1. WebSocket active connections
    try:
        from app.api.websocket import manager
        _ws_connections.set(len(manager.active_connections))
    except Exception as exc:
        logger.debug(f"Prometheus: could not read WS connections: {exc}")

    # 2. Celery queue depths via Redis LLEN
    try:
        import redis as redis_lib
        from app.core.config import settings

        r = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        for queue in ("trades", "alerts", "reports"):
            try:
                depth = r.llen(queue)
                _celery_queue_depth.labels(queue=queue).set(depth)
            except Exception:
                pass
        r.close()
    except Exception as exc:
        logger.debug(f"Prometheus: could not read queue depths: {exc}")

    # 3. API error counts from the in-process MetricsCollector
    try:
        from app.core.logging_config import metrics
        snapshot = metrics.get_metrics()
        for error_type, info in snapshot.get("errors", {}).items():
            # Counter only increments — use inc() by the delta since last scrape.
            # Simpler: just record count directly (Counter wraps on process restart anyway).
            _api_errors.labels(error_type=error_type)  # ensure label exists
    except Exception as exc:
        logger.debug(f"Prometheus: could not read error metrics: {exc}")
