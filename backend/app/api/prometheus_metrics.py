"""
Prometheus metrics endpoint — /metrics

Infrastructure:
  tradementor_ws_connections            Gauge   — active WebSocket connections
  tradementor_celery_queue_depth        Gauge   — tasks waiting in each Celery queue
  tradementor_api_errors_total          Counter — errors from MetricsCollector

Behavioural engine — added 2026-08-23, because none of the above says anything
about the thing the product actually does:
  tradementor_engine_detection_lag_seconds  Gauge — trade close → alert written
  tradementor_alerts_today                  Gauge — today's alerts by severity
  tradementor_behavior_events_today         Gauge — today's events by data quality
  tradementor_session_denominator_quality   Gauge — sessions by account-risk quality
  tradementor_detectors_silent_today        Gauge — registry detectors that fired nothing

WHY THESE FIVE

Detection lag is the product metric. `detected_at` is the TRADE's exit time and
`created_at` is when the row was written, so their difference is how long after
the trade the engine spoke. "Mirror, not blocker" is a claim about that number:
an alert forty minutes late is a report. It is also the first symptom of worker
saturation (see docs/SCALABILITY_50K_ANALYSIS.md, ceiling 1), which currently has
no signal at all.

Denominator quality exists because of a gap found by reading code rather than by
monitoring: `margin_snapshots` has no scheduled producer, so the account-risk
denominator reaches its GOOD rung only when a trader happens to load a page that
fetches margins. A production instance would show that instantly as sessions
piling up under `unknown`. It should not have taken a code review.

Silent detectors matter for the same reason: a detector that stops firing for
everyone looks exactly like a quiet market. Three detectors were silent for 203
replayed sessions and nobody could say whether that was correct.

Scrape this endpoint with Prometheus. No auth (internal only — protect at the
reverse proxy / network layer).
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

# ── Behavioural engine ─────────────────────────────────────────────────────

_detection_lag = Gauge(
    "tradementor_engine_detection_lag_seconds",
    "Seconds between a trade closing and its alert being written",
    ["quantile"],
)

_alerts_today = Gauge(
    "tradementor_alerts_today",
    "Alerts raised in today's session, by severity",
    ["severity"],
)

_events_today = Gauge(
    "tradementor_behavior_events_today",
    "Behaviour events recorded today, by the data quality the engine had",
    ["data_quality"],
)

_denominator_quality = Gauge(
    "tradementor_session_denominator_quality",
    "Today's sessions by the quality of their account-risk denominator",
    ["quality"],
)

_detectors_silent = Gauge(
    "tradementor_detectors_silent_today",
    "Registry detectors that produced no event today",
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
    await _populate_engine_metrics()
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
        # All five queues the Procfile's worker consumes. `bulk` and `celery`
        # were missing, so an EOD backlog on `bulk` - the exact thing that queue
        # exists to keep off the live path - was invisible.
        for queue in ("celery", "trades", "alerts", "reports", "bulk"):
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


async def _populate_engine_metrics() -> None:
    """
    Aggregate today's engine activity.

    Five bounded aggregates against indexed columns, scoped to the current
    session. Every one is wrapped: a metrics endpoint that raises takes the
    monitoring down with it, which is worse than a missing series.
    """
    try:
        from sqlalchemy import func, select

        from app.core.database import SessionLocal
        from app.core.session_facts import session_date_now, session_start
        from app.models.behavior_event import BehaviorEvent
        from app.models.risk_alert import RiskAlert
        from app.models.trading_session import TradingSession

        today = session_date_now()
        since = session_start(today)

        async with SessionLocal() as db:
            # 1. Detection lag. detected_at is the trade's exit time; created_at
            #    is when we wrote the row. The gap is how late the engine spoke.
            try:
                lag = func.extract(
                    "epoch", RiskAlert.created_at - RiskAlert.detected_at
                )
                row = (
                    await db.execute(
                        select(
                            func.percentile_cont(0.5).within_group(lag.asc()),
                            func.percentile_cont(0.9).within_group(lag.asc()),
                        ).where(
                            RiskAlert.detected_at >= since,
                            RiskAlert.created_at.isnot(None),
                        )
                    )
                ).one_or_none()
                if row and row[0] is not None:
                    _detection_lag.labels(quantile="p50").set(float(row[0]))
                    _detection_lag.labels(quantile="p90").set(float(row[1] or row[0]))
            except Exception as exc:
                logger.debug(f"Prometheus: detection lag unavailable: {exc}")

            # 2. Alerts by severity. `critical` folding into `danger` on one path
            #    was a live bug; a per-severity series makes that visible.
            try:
                rows = (
                    await db.execute(
                        select(RiskAlert.severity, func.count(RiskAlert.id))
                        .where(RiskAlert.detected_at >= since)
                        .group_by(RiskAlert.severity)
                    )
                ).all()
                seen = {sev: n for sev, n in rows}
                for severity in ("info", "caution", "danger", "critical"):
                    _alerts_today.labels(severity=severity).set(seen.get(severity, 0))
            except Exception as exc:
                logger.debug(f"Prometheus: alert counts unavailable: {exc}")

            # 3. Data quality the engine actually had. A shift from GOOD to
            #    PARTIAL means order context stopped arriving, which degrades
            #    confidence silently.
            try:
                rows = (
                    await db.execute(
                        select(BehaviorEvent.data_quality, func.count(BehaviorEvent.id))
                        .where(BehaviorEvent.detected_at >= since)
                        .group_by(BehaviorEvent.data_quality)
                    )
                ).all()
                seen = {q: n for q, n in rows}
                for quality in ("GOOD", "PARTIAL", "UNKNOWN", "INVALID"):
                    _events_today.labels(data_quality=quality).set(seen.get(quality, 0))
            except Exception as exc:
                logger.debug(f"Prometheus: data quality unavailable: {exc}")

            # 4. Account-risk denominator quality. `unknown` piling up means the
            #    engine cannot make account-relative claims for those traders -
            #    today that is expected, because nothing populates
            #    margin_snapshots on a schedule.
            try:
                rows = (
                    await db.execute(
                        select(
                            TradingSession.risk_denominator_quality,
                            func.count(TradingSession.id),
                        )
                        .where(TradingSession.session_date == today)
                        .group_by(TradingSession.risk_denominator_quality)
                    )
                ).all()
                seen = {(q or "unset"): n for q, n in rows}
                for quality in ("good", "partial", "unknown", "unset"):
                    _denominator_quality.labels(quality=quality).set(seen.get(quality, 0))
            except Exception as exc:
                logger.debug(f"Prometheus: denominator quality unavailable: {exc}")

            # 5. Detectors that fired nothing. A detector silently dying looks
            #    exactly like a quiet market from every other angle.
            try:
                from app.services.detector_registry import REGISTRY

                fired = {
                    d for (d,) in (
                        await db.execute(
                            select(BehaviorEvent.detector)
                            .where(BehaviorEvent.detected_at >= since)
                            .distinct()
                        )
                    ).all()
                }
                _detectors_silent.set(
                    len({spec.name for spec in REGISTRY} - fired)
                )
            except Exception as exc:
                logger.debug(f"Prometheus: silent detectors unavailable: {exc}")

    except Exception as exc:
        logger.debug(f"Prometheus: engine metrics unavailable: {exc}")
