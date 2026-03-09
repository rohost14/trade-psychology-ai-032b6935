"""
Circuit Breaker for Kite API (H-05)

Prevents cascading failures when Kite API is degraded.

States per broker_account_id:
  CLOSED     — normal operation, all API calls allowed
  OPEN       — tripped, API calls blocked, degraded mode active
  HALF_OPEN  — testing recovery, one probe allowed

Transition logic:
  CLOSED  → OPEN       when failure_rate > 50% in last 60s
  OPEN    → HALF_OPEN  after 60s cooldown
  HALF_OPEN → CLOSED   if probe call succeeds
  HALF_OPEN → OPEN     if probe call fails (reset cooldown)

Degraded mode (OPEN):
  - Live sync disabled
  - Real-time alerts disabled
  - Historical data + chat still work
  - Frontend shows "Kite connection issue" banner

Redis keys:
  circuit:{broker_account_id}:state     → CLOSED | OPEN | HALF_OPEN
  circuit:{broker_account_id}:failures  → int (failures in rolling 60s window)
  circuit:{broker_account_id}:total     → int (total calls in rolling 60s window)
  circuit:{broker_account_id}:opened_at → timestamp (when circuit opened)
"""

import logging
import time
from enum import Enum
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)

FAILURE_WINDOW_SECONDS = 60
FAILURE_RATE_THRESHOLD = 0.5   # >50% failures → trip
MIN_CALLS_TO_TRIP = 3          # Minimum calls before evaluating rate
OPEN_COOLDOWN_SECONDS = 60     # Wait 60s before attempting recovery


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Redis-backed circuit breaker for Kite API calls.

    Usage:
        cb = CircuitBreaker()

        if not await cb.allow_request(broker_account_id):
            raise DegradedModeError("Kite API unavailable")

        try:
            result = await kite_call()
            await cb.record_success(broker_account_id)
        except KiteAPIError:
            await cb.record_failure(broker_account_id)
            raise
    """

    def _get_redis(self):
        import redis as redis_lib
        from app.core.config import settings
        return redis_lib.from_url(settings.REDIS_URL, decode_responses=True)

    def _keys(self, broker_account_id: UUID):
        b = str(broker_account_id)
        return {
            "state":     f"circuit:{b}:state",
            "failures":  f"circuit:{b}:failures",
            "total":     f"circuit:{b}:total",
            "opened_at": f"circuit:{b}:opened_at",
        }

    async def get_state(self, broker_account_id: UUID) -> CircuitState:
        """Return current circuit state. CLOSED if no state recorded."""
        try:
            r = self._get_redis()
            keys = self._keys(broker_account_id)
            state = r.get(keys["state"])
            return CircuitState(state) if state else CircuitState.CLOSED
        except Exception:
            return CircuitState.CLOSED  # Fail open — don't block on Redis error

    async def allow_request(self, broker_account_id: UUID) -> bool:
        """
        Returns True if the request should proceed.
        Transitions OPEN → HALF_OPEN if cooldown has elapsed.
        """
        try:
            r = self._get_redis()
            keys = self._keys(broker_account_id)
            state = r.get(keys["state"])

            if not state or state == CircuitState.CLOSED:
                return True

            if state == CircuitState.HALF_OPEN:
                # Allow one probe request
                return True

            # OPEN: check if cooldown elapsed
            opened_at = r.get(keys["opened_at"])
            if opened_at and (time.time() - float(opened_at)) >= OPEN_COOLDOWN_SECONDS:
                # Transition to HALF_OPEN — allow one probe
                r.set(keys["state"], CircuitState.HALF_OPEN, ex=300)
                logger.info(f"[circuit:{broker_account_id}] OPEN → HALF_OPEN (cooldown elapsed)")
                return True

            return False  # Still OPEN

        except Exception as e:
            logger.warning(f"[circuit] allow_request failed (fail-open): {e}")
            return True  # Fail open — don't block on circuit breaker errors

    async def record_success(self, broker_account_id: UUID) -> None:
        """Record a successful Kite API call. Closes circuit if was HALF_OPEN."""
        try:
            r = self._get_redis()
            keys = self._keys(broker_account_id)
            state = r.get(keys["state"])

            if state == CircuitState.HALF_OPEN:
                # Probe succeeded — close circuit
                r.delete(keys["state"], keys["failures"], keys["total"], keys["opened_at"])
                logger.info(f"[circuit:{broker_account_id}] HALF_OPEN → CLOSED (probe succeeded)")
                return

            # Update rolling counters (total calls)
            pipe = r.pipeline()
            pipe.incr(keys["total"])
            pipe.expire(keys["total"], FAILURE_WINDOW_SECONDS)
            pipe.execute()

        except Exception as e:
            logger.warning(f"[circuit] record_success failed: {e}")

    async def record_failure(self, broker_account_id: UUID) -> None:
        """Record a failed Kite API call. May trip the circuit."""
        try:
            r = self._get_redis()
            keys = self._keys(broker_account_id)
            state = r.get(keys["state"])

            if state == CircuitState.HALF_OPEN:
                # Probe failed — reopen circuit
                r.set(keys["state"], CircuitState.OPEN, ex=300)
                r.set(keys["opened_at"], time.time(), ex=300)
                logger.warning(f"[circuit:{broker_account_id}] HALF_OPEN → OPEN (probe failed)")
                return

            # Increment both counters
            pipe = r.pipeline()
            pipe.incr(keys["failures"])
            pipe.expire(keys["failures"], FAILURE_WINDOW_SECONDS)
            pipe.incr(keys["total"])
            pipe.expire(keys["total"], FAILURE_WINDOW_SECONDS)
            results = pipe.execute()

            failures = results[0]
            total = results[2]

            # Evaluate whether to trip
            if total >= MIN_CALLS_TO_TRIP and failures / total > FAILURE_RATE_THRESHOLD:
                r.set(keys["state"], CircuitState.OPEN, ex=300)
                r.set(keys["opened_at"], time.time(), ex=300)
                logger.error(
                    f"[circuit:{broker_account_id}] CLOSED → OPEN "
                    f"(failure rate {failures}/{total} = {failures/total:.0%})"
                )

        except Exception as e:
            logger.warning(f"[circuit] record_failure failed: {e}")

    async def force_close(self, broker_account_id: UUID) -> None:
        """Manually reset circuit to CLOSED. For admin use."""
        try:
            r = self._get_redis()
            keys = self._keys(broker_account_id)
            r.delete(*keys.values())
            logger.info(f"[circuit:{broker_account_id}] Manually reset to CLOSED")
        except Exception as e:
            logger.warning(f"[circuit] force_close failed: {e}")

    async def get_status(self, broker_account_id: UUID) -> dict:
        """Return full circuit status for health checks / dashboard."""
        try:
            r = self._get_redis()
            keys = self._keys(broker_account_id)
            state = r.get(keys["state"]) or CircuitState.CLOSED
            failures = int(r.get(keys["failures"]) or 0)
            total = int(r.get(keys["total"]) or 0)
            opened_at = r.get(keys["opened_at"])

            return {
                "state": state,
                "failures_in_window": failures,
                "total_in_window": total,
                "failure_rate": round(failures / total, 2) if total > 0 else 0.0,
                "opened_at": float(opened_at) if opened_at else None,
                "seconds_until_probe": max(
                    0,
                    OPEN_COOLDOWN_SECONDS - (time.time() - float(opened_at))
                ) if opened_at and state == CircuitState.OPEN else 0,
            }
        except Exception:
            return {"state": CircuitState.CLOSED, "error": "Redis unavailable"}


# Singleton
circuit_breaker = CircuitBreaker()
