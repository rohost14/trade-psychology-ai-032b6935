"""
Integration Tests — Phase B

Three critical integration scenarios identified in PRODUCTION_READINESS_AUDIT.md:
  1. Concurrent webhooks with same order_id → only one processed (idempotency)
  2. Circuit breaker state transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
  3. Out-of-order PositionLedger fills (late fill triggers full replay)

These tests require a live Supabase DB connection.
Run with: pytest tests/test_integration.py -m integration -v

In CI without DB access, skip with:
  pytest ... -m "not integration"
"""

import pytest
import asyncio
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select

from app.models.trade import Trade
from app.models.broker_account import BrokerAccount
from app.models.user import User
from tests.helpers import now_utc, make_email

pytestmark = pytest.mark.integration


# =============================================================================
# 1. Concurrent Webhook Idempotency
#    Risk: Two Zerodha retries for the same order both complete → double P&L,
#    double behavioral alerts, wrong CompletedTrade.
# =============================================================================

class TestConcurrentWebhookIdempotency:

    async def test_concurrent_fills_same_order_id_only_one_processed(self, db, broker):
        """
        Two simultaneous webhook tasks for the same order_id must result in
        exactly one processed trade (processed_at set) and one skipped (no-op).

        Simulates: Zerodha sends a duplicate postback while the first is in-flight.
        """
        order_id = f"ORD_{uuid4().hex[:8]}"

        # Pre-insert the trade (as the webhook handler does before queuing Celery)
        trade = Trade(
            broker_account_id=broker.id,
            order_id=order_id,
            tradingsymbol="NIFTY24JANFUT",
            exchange="NFO",
            transaction_type="BUY",
            order_type="MARKET",
            product="MIS",
            quantity=50,
            price=Decimal("22000.00"),
            average_price=Decimal("22000.00"),
            status="COMPLETE",
            asset_class="FNO",
            instrument_type="FUTURE",
            product_type="MIS",
        )
        db.add(trade)
        await db.flush()

        # Simulate the idempotency guard: atomically claim processed_at
        from sqlalchemy import update
        from app.models.trade import Trade as TradeModel

        async def try_claim(t_id):
            """Returns True if this caller won the race."""
            result = await db.execute(
                update(TradeModel)
                .where(TradeModel.id == t_id, TradeModel.processed_at.is_(None))
                .values(processed_at=datetime.now(timezone.utc))
                .returning(TradeModel.processed_at)
            )
            row = result.fetchone()
            await db.flush()
            return row is not None

        # Run both claims concurrently (simulates race condition)
        winner1, winner2 = await asyncio.gather(
            try_claim(trade.id),
            try_claim(trade.id),
        )

        # Exactly one must win
        assert winner1 != winner2, (
            "Both concurrent claims succeeded — idempotency guard is broken"
        )
        assert winner1 or winner2, "Neither claim succeeded — something is wrong"

    async def test_already_processed_trade_skips_on_second_webhook(self, db, broker):
        """
        A trade with processed_at already set must be skipped immediately
        without any re-processing.
        """
        order_id = f"ORD_{uuid4().hex[:8]}"

        trade = Trade(
            broker_account_id=broker.id,
            order_id=order_id,
            tradingsymbol="BANKNIFTY24JANFUT",
            exchange="NFO",
            transaction_type="SELL",
            order_type="MARKET",
            product="MIS",
            quantity=25,
            status="COMPLETE",
            processed_at=datetime.now(timezone.utc),  # already processed
            asset_class="FNO",
            instrument_type="FUTURE",
            product_type="MIS",
        )
        db.add(trade)
        await db.flush()

        # The guard query: tries to claim processed_at where it IS NULL
        from sqlalchemy import update
        result = await db.execute(
            update(Trade)
            .where(Trade.id == trade.id, Trade.processed_at.is_(None))
            .values(processed_at=datetime.now(timezone.utc))
            .returning(Trade.processed_at)
        )
        row = result.fetchone()

        assert row is None, (
            "Claim succeeded on already-processed trade — idempotency guard is broken"
        )


# =============================================================================
# 2. Circuit Breaker State Transitions
#    Risk: Wrong state causes all requests to fail permanently or never recover.
# =============================================================================

class TestCircuitBreakerTransitions:

    async def test_circuit_opens_after_failure_threshold(self, db, broker):
        """
        Circuit breaker must move to OPEN after the failure rate threshold
        is exceeded (50% failures over the window).
        """
        from app.services.circuit_breaker_service import CircuitBreaker, CircuitState

        cb = CircuitBreaker(
            name=f"test_{uuid4().hex[:6]}",
            failure_threshold=0.5,
            recovery_timeout=60,
            min_calls=4,
        )

        # Simulate: 3 failures out of 4 calls (75% — above 50% threshold)
        with patch.object(cb, "_get_state") as mock_get, \
             patch.object(cb, "_save_state") as mock_save:

            mock_get.return_value = {
                "state": CircuitState.CLOSED,
                "failure_count": 3,
                "total_count": 4,
                "last_failure_time": None,
                "last_state_change": datetime.now(timezone.utc).isoformat(),
            }
            mock_save.return_value = None

            should_open = cb._should_open(failure_count=3, total_count=4)
            assert should_open, (
                "Circuit should open at 75% failure rate (threshold: 50%)"
            )

    async def test_circuit_stays_closed_below_threshold(self):
        """Circuit must stay CLOSED when failure rate is below threshold."""
        from app.services.circuit_breaker_service import CircuitBreaker

        cb = CircuitBreaker(
            name=f"test_{uuid4().hex[:6]}",
            failure_threshold=0.5,
            recovery_timeout=60,
            min_calls=4,
        )

        # 1 failure out of 4 calls = 25% — below 50% threshold
        should_open = cb._should_open(failure_count=1, total_count=4)
        assert not should_open, (
            "Circuit opened at 25% failure rate (threshold: 50%) — too aggressive"
        )

    async def test_circuit_enters_half_open_after_timeout(self):
        """
        Circuit must transition from OPEN to HALF_OPEN once recovery_timeout
        seconds have elapsed since the last failure.
        """
        from app.services.circuit_breaker_service import CircuitBreaker, CircuitState

        cb = CircuitBreaker(
            name=f"test_{uuid4().hex[:6]}",
            failure_threshold=0.5,
            recovery_timeout=60,
            min_calls=4,
        )

        # Simulate: circuit has been OPEN for 90 seconds (past the 60s timeout)
        last_failure = datetime.now(timezone.utc) - timedelta(seconds=90)

        with patch.object(cb, "_get_state") as mock_get:
            mock_get.return_value = {
                "state": CircuitState.OPEN,
                "failure_count": 3,
                "total_count": 4,
                "last_failure_time": last_failure.isoformat(),
                "last_state_change": last_failure.isoformat(),
            }

            next_state = cb._compute_next_state()
            assert next_state == CircuitState.HALF_OPEN, (
                f"Expected HALF_OPEN after timeout, got {next_state}"
            )

    async def test_circuit_closes_after_successful_probe(self):
        """
        In HALF_OPEN state, a successful probe call must close the circuit.
        """
        from app.services.circuit_breaker_service import CircuitBreaker, CircuitState

        cb = CircuitBreaker(
            name=f"test_{uuid4().hex[:6]}",
            failure_threshold=0.5,
            recovery_timeout=60,
            min_calls=4,
        )

        with patch.object(cb, "_get_state") as mock_get, \
             patch.object(cb, "_save_state") as mock_save:

            mock_get.return_value = {
                "state": CircuitState.HALF_OPEN,
                "failure_count": 0,
                "total_count": 1,
                "last_failure_time": None,
                "last_state_change": datetime.now(timezone.utc).isoformat(),
            }
            saved_states = []
            mock_save.side_effect = lambda s: saved_states.append(s)

            cb._record_success()

            assert any(
                s.get("state") == CircuitState.CLOSED
                for s in saved_states
            ), "Circuit did not close after successful probe in HALF_OPEN state"


# =============================================================================
# 3. Out-of-Order PositionLedger Fills (Late Fill Replay)
#    Risk: Late fills corrupt P&L — exit_price wrong, CompletedTrade wrong.
# =============================================================================

class TestOutOfOrderPositionLedger:

    async def test_late_fill_triggers_replay_from_correct_index(self, db, broker):
        """
        When a fill arrives out of order (earlier timestamp than the latest entry),
        PositionLedgerService must replay from the late fill's insertion index
        onward, not skip it.
        """
        from app.services.position_ledger_service import PositionLedgerService, FillData

        sym = f"TESTFUT{uuid4().hex[:4].upper()}"

        t0 = datetime.now(timezone.utc) - timedelta(minutes=10)
        t1 = datetime.now(timezone.utc) - timedelta(minutes=5)
        t_late = datetime.now(timezone.utc) - timedelta(minutes=8)  # between t0 and t1

        # Fill 1: Open a long position at t0
        fill_open = FillData(
            broker_account_id=broker.id,
            tradingsymbol=sym,
            exchange="NFO",
            fill_order_id=f"ORD_{uuid4().hex[:8]}",
            fill_qty=50,
            fill_price=Decimal("100.00"),
            occurred_at=t0,
            idempotency_key=f"{sym}:open",
        )
        entry_open, is_new_open = await PositionLedgerService.apply_fill(fill_open, db)
        assert is_new_open
        assert entry_open.net_qty == 50

        # Fill 2: Close the position at t1 (normal close)
        fill_close = FillData(
            broker_account_id=broker.id,
            tradingsymbol=sym,
            exchange="NFO",
            fill_order_id=f"ORD_{uuid4().hex[:8]}",
            fill_qty=-50,
            fill_price=Decimal("110.00"),
            occurred_at=t1,
            idempotency_key=f"{sym}:close",
        )
        entry_close, is_new_close = await PositionLedgerService.apply_fill(fill_close, db)
        assert is_new_close

        # Fill 3: Late partial fill arriving after the close (timestamp = t_late)
        # This is an additional +25 lot that arrived out of order.
        # Replay must re-sequence: open(50) → late_add(+25) → close(-50) → net +25 remaining
        fill_late = FillData(
            broker_account_id=broker.id,
            tradingsymbol=sym,
            exchange="NFO",
            fill_order_id=f"ORD_{uuid4().hex[:8]}",
            fill_qty=25,
            fill_price=Decimal("102.00"),
            occurred_at=t_late,
            idempotency_key=f"{sym}:late",
        )
        entry_late, is_new_late = await PositionLedgerService.apply_fill(fill_late, db)
        assert is_new_late, "Late fill was rejected as duplicate"

        # After replay: net position should reflect the correct re-sequenced state
        net_qty = await PositionLedgerService.get_net_qty(broker.id, sym, db)
        # After replay: open(50) + late(+25) + close(-50) = 25 remaining
        assert net_qty == 25, (
            f"Expected net_qty=25 after late fill replay, got {net_qty}"
        )

    async def test_idempotent_late_fill_not_double_applied(self, db, broker):
        """
        Resubmitting a late fill with the same idempotency_key must be a no-op.
        Prevents a Celery retry from double-applying the fill.
        """
        from app.services.position_ledger_service import PositionLedgerService, FillData

        sym = f"TESTFUT{uuid4().hex[:4].upper()}"
        idem_key = f"{sym}:open"

        fill = FillData(
            broker_account_id=broker.id,
            tradingsymbol=sym,
            exchange="NFO",
            fill_order_id=f"ORD_{uuid4().hex[:8]}",
            fill_qty=50,
            fill_price=Decimal("100.00"),
            occurred_at=datetime.now(timezone.utc),
            idempotency_key=idem_key,
        )

        # Apply once
        entry1, is_new1 = await PositionLedgerService.apply_fill(fill, db)
        assert is_new1

        # Apply again with same key — must return existing entry
        entry2, is_new2 = await PositionLedgerService.apply_fill(fill, db)
        assert not is_new2, "Duplicate fill was accepted — idempotency broken"
        assert entry1.id == entry2.id, "Duplicate fill returned different entry"


# =============================================================================
# 4. WebSocket JWT Auth
#    Risk: Expired or invalid JWT allows stale WS sessions.
# =============================================================================

class TestWebSocketJWTAuth:

    async def test_valid_token_returns_broker_account_id(self):
        """Valid unexpired JWT must return the broker_account_id UUID."""
        from app.api.deps import create_access_token, get_current_user_ws

        user_id = uuid4()
        account_id = uuid4()
        token = create_access_token(user_id=user_id, broker_account_id=account_id)

        result = await get_current_user_ws(token)
        assert result == account_id, f"Expected {account_id}, got {result}"

    async def test_expired_token_returns_none(self):
        """Expired JWT must return None so WebSocket is closed with 4001."""
        from app.api.deps import create_access_token, get_current_user_ws
        from datetime import timedelta

        token = create_access_token(
            user_id=uuid4(),
            broker_account_id=uuid4(),
            expires_delta=timedelta(hours=-1),
        )
        result = await get_current_user_ws(token)
        assert result is None, (
            "Expired JWT must return None — WS endpoint closes with 4001"
        )

    async def test_invalid_token_returns_none(self):
        """Garbage token string must return None without raising."""
        from app.api.deps import get_current_user_ws

        result = await get_current_user_ws("not.a.real.jwt")
        assert result is None

    async def test_token_missing_bid_claim_returns_none(self):
        """JWT without 'bid' claim returns None — bid is required for WS."""
        from jose import jwt as _jwt
        from app.core.config import settings

        payload = {
            "sub": str(uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(seconds=3600),
        }
        token = _jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        from app.api.deps import get_current_user_ws
        result = await get_current_user_ws(token)
        assert result is None, "Token without 'bid' claim must return None"


# =============================================================================
# 5. Event Bus Replay
#    Risk: On WS reconnect, missed events not replayed → stale UI state.
# =============================================================================

class TestEventBusReplay:

    async def test_replay_returns_events_after_cursor(self):
        """replay_events_for_account must return events after since_event_id."""
        from app.core.event_bus import replay_events_for_account

        mock_events = [
            ("1700000001-0", {"type": "trade_update", "account_id": "abc",
                              "data": '{"order_id":"1"}', "ts": "1700000001000"}),
            ("1700000002-0", {"type": "alert_update", "account_id": "abc",
                              "data": '{"alert_id":"2"}', "ts": "1700000002000"}),
        ]

        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.xread = AsyncMock(return_value=[("stream:abc", mock_events)])
            mock_from_url.return_value = mock_redis

            events = await replay_events_for_account("abc", "1699999999-0", limit=50)

        assert len(events) == 2
        assert events[0][0] == "1700000001-0"
        assert events[1][0] == "1700000002-0"
        assert events[0][1]["type"] == "trade_update"

    async def test_replay_returns_empty_on_redis_error(self):
        """Redis unavailability must return empty list — never raise."""
        from app.core.event_bus import replay_events_for_account

        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.xread = AsyncMock(side_effect=Exception("Redis down"))
            mock_from_url.return_value = mock_redis

            events = await replay_events_for_account("abc", "0-0", limit=50)

        assert events == [], "Redis error must not raise — return empty list"

    async def test_replay_returns_empty_when_no_events(self):
        """Empty stream returns empty list."""
        from app.core.event_bus import replay_events_for_account

        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.xread = AsyncMock(return_value=[])
            mock_from_url.return_value = mock_redis

            events = await replay_events_for_account("abc", "0-0")

        assert events == []


# =============================================================================
# 6. Position Monitor — Holding Loser Detection
#    Risk: Position held too long at a loss → no alert fired.
# =============================================================================

class TestPositionMonitorHoldingLoser:

    async def test_holding_loser_fires_after_threshold(self):
        """
        Position losing ≥0.5% for ≥30 minutes must generate a
        'holding_loser' behavioral event.
        """
        from app.tasks.position_monitor_tasks import _check_position
        from app.core.trading_defaults import COLD_START_DEFAULTS
        from unittest.mock import MagicMock, AsyncMock, patch

        mock_position = MagicMock()
        mock_position.tradingsymbol = "NIFTY24JANFUT"
        mock_position.total_quantity = 50
        mock_position.average_entry_price = 22000.0
        mock_position.instrument_token = 12345
        mock_position.last_entry_time = (
            datetime.now(timezone.utc) - timedelta(minutes=31)
        )

        thresholds = dict(COLD_START_DEFAULTS)

        with patch("app.tasks.position_monitor_tasks.get_cached_ltp", return_value=21780.0):
            db = AsyncMock()
            events = await _check_position(mock_position, thresholds, db)

        assert any(e["pattern"] == "holding_loser" for e in events), (
            "Expected holding_loser event: position down 1% for 31 minutes"
        )

    async def test_holding_loser_does_not_fire_before_threshold(self):
        """
        Position held for only 10 minutes must NOT fire a holding_loser event
        (threshold is 30 minutes).
        """
        from app.tasks.position_monitor_tasks import _check_position
        from app.core.trading_defaults import COLD_START_DEFAULTS
        from unittest.mock import MagicMock, AsyncMock, patch

        mock_position = MagicMock()
        mock_position.tradingsymbol = "BANKNIFTY24JANFUT"
        mock_position.total_quantity = 25
        mock_position.average_entry_price = 48000.0
        mock_position.instrument_token = 99999
        mock_position.last_entry_time = (
            datetime.now(timezone.utc) - timedelta(minutes=10)
        )

        thresholds = dict(COLD_START_DEFAULTS)

        with patch("app.tasks.position_monitor_tasks.get_cached_ltp", return_value=47520.0):
            db = AsyncMock()
            events = await _check_position(mock_position, thresholds, db)

        assert not any(e["pattern"] == "holding_loser" for e in events), (
            "Must NOT fire holding_loser after only 10 minutes (threshold: 30 min)"
        )

    async def test_holding_loser_no_price_no_event(self):
        """No live price available → no event must fire."""
        from app.tasks.position_monitor_tasks import _check_position
        from app.core.trading_defaults import COLD_START_DEFAULTS
        from unittest.mock import MagicMock, AsyncMock, patch

        mock_position = MagicMock()
        mock_position.tradingsymbol = "RELIANCE"
        mock_position.total_quantity = 10
        mock_position.average_entry_price = 2800.0
        mock_position.instrument_token = 54321
        mock_position.last_entry_time = (
            datetime.now(timezone.utc) - timedelta(minutes=60)
        )

        thresholds = dict(COLD_START_DEFAULTS)

        with patch("app.tasks.position_monitor_tasks.get_cached_ltp", return_value=None):
            db = AsyncMock()
            events = await _check_position(mock_position, thresholds, db)

        assert events == [], (
            "No live price → no event must fire (KiteTicker may not be running)"
        )


# =============================================================================
# 7. Circuit Breaker → Sentry alert on OPEN
#    Risk: Circuit opens silently — ops never knows Kite API is degraded.
# =============================================================================

class TestCircuitBreakerSentryAlert:

    async def test_sentry_captured_when_circuit_trips(self):
        """
        When the circuit breaker trips CLOSED → OPEN, Sentry must receive
        a capture_message call so ops is alerted.
        """
        from app.services.circuit_breaker_service import CircuitBreaker, CircuitState
        from unittest.mock import patch, MagicMock
        import time

        cb = CircuitBreaker()
        account_id = uuid4()

        keys = cb._keys(account_id)

        with patch.object(cb, "_get_redis") as mock_get_redis, \
             patch("sentry_sdk.capture_message") as mock_sentry:

            mock_r = MagicMock()
            mock_get_redis.return_value = mock_r
            mock_r.get.return_value = CircuitState.CLOSED

            # Simulate pipeline result: 3 failures out of 4 → 75% failure rate
            mock_r.pipeline.return_value.__enter__ = MagicMock(return_value=mock_r)
            mock_r.pipeline.return_value.__exit__ = MagicMock(return_value=False)
            mock_pipe = MagicMock()
            mock_pipe.execute.return_value = [3, None, 4, None]  # failures=3, total=4
            mock_r.pipeline.return_value = mock_pipe

            await cb.record_failure(account_id)

        assert mock_sentry.called, (
            "Sentry must receive capture_message when circuit trips to OPEN"
        )
        call_args = mock_sentry.call_args
        assert call_args[1].get("level") == "error" or (
            len(call_args[0]) > 1 and call_args[0][1] == "error"
        ), "Sentry message level must be 'error'"


# =============================================================================
# 8. Options Expiry — Position Cleanup
#    Risk: Expired contracts stay as "open" in the DB forever.
# =============================================================================

class TestOptionsExpiryCleanup:

    def test_weekly_option_expired_yesterday(self):
        """Weekly option with exact expiry_date < today must be marked expired."""
        from app.tasks.reconciliation_tasks import _is_contract_expired

        yesterday = date.today() - timedelta(days=1)
        assert _is_contract_expired(yesterday, date.today()) is True

    def test_weekly_option_expiry_today_not_expired(self):
        """Option expiring today is still live during market hours."""
        from app.tasks.reconciliation_tasks import _is_contract_expired

        today = date.today()
        assert _is_contract_expired(today, today) is False

    def test_monthly_option_proxy_date_same_month_not_expired(self):
        """
        Monthly option using day=1 proxy must NOT be marked expired mid-month.
        e.g. NIFTY25MAR25000CE → expiry_date=2025-03-01 (proxy).
        On 2025-03-15 this contract is still live — must not be zeroed.
        """
        from app.tasks.reconciliation_tasks import _is_contract_expired

        # Proxy date: first of the month
        proxy = date(2025, 3, 1)
        # Today is mid-month in the same expiry month
        mid_month = date(2025, 3, 15)
        assert _is_contract_expired(proxy, mid_month) is False, (
            "Monthly option must NOT be expired mid-month (proxy day=1 is conservative)"
        )

    def test_monthly_option_proxy_date_month_passed_is_expired(self):
        """
        Monthly option proxy (day=1) must be marked expired once the full
        expiry month has passed.
        e.g. NIFTY25MAR25000CE → proxy=2025-03-01 → expired on 2025-04-01+.
        """
        from app.tasks.reconciliation_tasks import _is_contract_expired

        proxy = date(2025, 3, 1)
        next_month = date(2025, 4, 1)
        assert _is_contract_expired(proxy, next_month) is True, (
            "Monthly option proxy must be expired once the full month has passed"
        )

    def test_futures_proxy_date_month_passed_is_expired(self):
        """Monthly futures (BANKNIFTY25APRFUT) use same proxy — expired after month ends."""
        from app.tasks.reconciliation_tasks import _is_contract_expired

        proxy = date(2025, 4, 1)
        may_start = date(2025, 5, 1)
        assert _is_contract_expired(proxy, may_start) is True

    async def test_expire_stale_positions_zeros_expired_ce(self):
        """
        _expire_stale_positions must zero out an open CE position whose
        expiry date has passed.
        """
        from app.tasks.reconciliation_tasks import _expire_stale_positions
        from unittest.mock import AsyncMock, MagicMock, patch

        account_id = uuid4()

        # Build a fake open CE position with yesterday's expiry
        yesterday = date.today() - timedelta(days=1)
        # Weekly CE symbol: NIFTY{yy}{m_char}{dd}{strike}CE
        # Use a date we can control — easier to use a mock symbol
        mock_position = MagicMock()
        mock_position.tradingsymbol = "NIFTY25131500CE"  # won't parse — use a parseable one below
        mock_position.total_quantity = 50
        mock_position.status = "open"

        # Patch parse_symbol to return a ParsedSymbol with yesterday's expiry
        from app.services.instrument_parser import ParsedSymbol
        fake_parsed = ParsedSymbol(
            raw="NIFTY25131500CE",
            underlying="NIFTY",
            instrument_type="CE",
            expiry_date=yesterday,
            strike=15000,
            expiry_key=yesterday.isoformat(),
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_position]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.reconciliation_tasks.SessionLocal", return_value=mock_db), \
             patch("app.tasks.reconciliation_tasks.parse_symbol", return_value=fake_parsed):
            expired = await _expire_stale_positions(account_id, date.today())

        assert expired == 1, f"Expected 1 expired position, got {expired}"
        assert mock_position.total_quantity == 0, "Position quantity must be zeroed"
        assert mock_position.status == "expired", "Position status must be 'expired'"
        mock_db.commit.assert_called_once()

    async def test_expire_stale_positions_skips_equity(self):
        """EQ positions (no expiry) must never be touched."""
        from app.tasks.reconciliation_tasks import _expire_stale_positions
        from unittest.mock import AsyncMock, MagicMock, patch
        from app.services.instrument_parser import ParsedSymbol

        account_id = uuid4()

        mock_position = MagicMock()
        mock_position.tradingsymbol = "RELIANCE"
        mock_position.total_quantity = 10

        fake_parsed = ParsedSymbol(
            raw="RELIANCE",
            underlying="RELIANCE",
            instrument_type="EQ",
            expiry_date=None,
            strike=None,
            expiry_key="",
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_position]
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=False)

        with patch("app.tasks.reconciliation_tasks.SessionLocal", return_value=mock_db), \
             patch("app.tasks.reconciliation_tasks.parse_symbol", return_value=fake_parsed):
            expired = await _expire_stale_positions(account_id, date.today())

        assert expired == 0, "EQ positions must never be expired"
        assert mock_position.total_quantity == 10, "EQ position quantity must be unchanged"
        mock_db.commit.assert_not_called()
