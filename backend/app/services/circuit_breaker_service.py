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
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
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

    Constructor params are optional — production code uses module-level constants.
    Params exist so tests can inject specific thresholds and mock _get_state/_save_state.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        failure_threshold: Optional[float] = None,
        recovery_timeout: Optional[int] = None,
        min_calls: Optional[int] = None,
    ):
        self._name = name or "default"
        self._failure_threshold = failure_threshold if failure_threshold is not None else FAILURE_RATE_THRESHOLD
        self._recovery_timeout = recovery_timeout if recovery_timeout is not None else OPEN_COOLDOWN_SECONDS
        self._min_calls = min_calls if min_calls is not None else MIN_CALLS_TO_TRIP

    # ── Testable helper methods ────────────────────────────────────────────

    def _should_open(self, failure_count: int, total_count: int) -> bool:
        """Return True if the circuit should trip based on failure rate."""
        if total_count < self._min_calls:
            return False
        return (failure_count / total_count) > self._failure_threshold

    def _get_state(self) -> Dict[str, Any]:
        """Return current circuit state dict. Override or mock in tests."""
        raise NotImplementedError("_get_state must be mocked in tests or overridden in subclass")

    def _save_state(self, state_dict: Dict[str, Any]) -> None:
        """Persist circuit state dict. Override or mock in tests."""
        raise NotImplementedError("_save_state must be mocked in tests or overridden in subclass")

    def _compute_next_state(self) -> CircuitState:
        """
        Compute the next circuit state based on current state and elapsed time.
        Reads via _get_state() — mock that in tests to control input.
        """
        state_dict = self._get_state()
        state = state_dict.get("state", CircuitState.CLOSED)

        if state == CircuitState.OPEN:
            last_failure_time = state_dict.get("last_failure_time")
            if last_failure_time:
                last_dt = datetime.fromisoformat(last_failure_time)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
                if elapsed >= self._recovery_timeout:
                    return CircuitState.HALF_OPEN
            return CircuitState.OPEN

        return state

    def _record_success(self) -> None:
        """
        Record a successful probe call. If HALF_OPEN, transitions to CLOSED.
        Writes via _save_state() — mock that in tests to capture the result.
        """
        state_dict = self._get_state()
        state = state_dict.get("state", CircuitState.CLOSED)
        if state == CircuitState.HALF_OPEN:
            self._save_state({"state": CircuitState.CLOSED})

    # ── Redis-backed production methods ───────────────────────────────────

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
                try:
                    import sentry_sdk
                    sentry_sdk.capture_message(
                        f"Circuit breaker OPEN: account {str(broker_account_id)[:8]}... "
                        f"({failures}/{total} Kite API failures = {failures/total:.0%}). "
                        f"Live sync + real-time alerts disabled for this account.",
                        level="error",
                    )
                except Exception:
                    pass

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
