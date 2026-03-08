"""
Behavioral Detection Test Suite
================================

Tests every pattern detector in the TradeMentor backend:

  RiskDetector (5 patterns — fire RiskAlert objects)
    RD-01 .. RD-05  consecutive_loss
    RD-06 .. RD-09  revenge_sizing
    RD-10 .. RD-13  overtrading (burst)
    RD-14 .. RD-18  fomo_entry (opening + chasing)
    RD-19 .. RD-22  tilt_loss_spiral

  BehavioralEvaluator (5 patterns — fire BehavioralEvent objects, confidence-gated)
    BE-01 .. BE-05  REVENGE_TRADING
    BE-06 .. BE-09  OVERTRADING
    BE-10 .. BE-13  TILT_SPIRAL
    BE-14 .. BE-18  FOMO_ENTRY (opening + chasing)
    BE-19 .. BE-22  LOSS_CHASING

  Threshold System (3-tier)
    TH-01 .. TH-04  profile overrides / floors

  Deduplication
    DD-01 .. DD-02

Tests call the private detection methods directly (unit tests) using
in-memory model objects — no HTTP, no Celery, no Kite API.
The DB fixture is used only where the full detect_patterns() pipeline is tested.

Default thresholds (COLD_START_DEFAULTS):
  burst_trades_per_15min   = 6
  revenge_window_min       = 10
  consecutive_loss_caution = 3
  consecutive_loss_danger  = 5
"""

import pytest
import asyncio
from uuid import uuid4
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.models.trade import Trade
from app.models.completed_trade import CompletedTrade
from app.models.risk_alert import RiskAlert
from app.models.behavioral_event import BehavioralEvent
from app.services.risk_detector import RiskDetector
from app.services.behavioral_evaluator import BehavioralEvaluator
from app.core.trading_defaults import get_thresholds

IST = ZoneInfo("Asia/Kolkata")


# =============================================================================
# TEST HELPERS — build in-memory objects (no DB required for unit tests)
# =============================================================================

BROKER_ID = uuid4()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def minutes_ago(n: float) -> datetime:
    return utc_now() - timedelta(minutes=n)


def ist_market_open(minute_offset: int = 0) -> datetime:
    """Return a datetime that is IST 09:15 + offset minutes (timezone-aware, stored as UTC)."""
    today_ist = datetime.now(IST).date()
    base = datetime(
        today_ist.year, today_ist.month, today_ist.day,
        9, 15, 0,
        tzinfo=IST,
    ) + timedelta(minutes=minute_offset)
    return base.astimezone(timezone.utc)


def make_completed_trade(
    pnl: float,
    exit_time: datetime = None,
    qty: int = 10,
    avg_entry_price: float = 1000.0,
    tradingsymbol: str = "INFY",
    broker_account_id=None,
) -> CompletedTrade:
    if exit_time is None:
        exit_time = utc_now()
    if broker_account_id is None:
        broker_account_id = BROKER_ID

    direction = "LONG" if pnl >= 0 else "LONG"  # direction doesn't change pnl sign for us
    avg_exit = avg_entry_price + (pnl / qty) if qty > 0 else avg_entry_price

    return CompletedTrade(
        id=uuid4(),
        broker_account_id=broker_account_id,
        tradingsymbol=tradingsymbol,
        exchange="NSE",
        instrument_type="EQ",
        product="MIS",
        direction=direction,
        total_quantity=qty,
        num_entries=1,
        num_exits=1,
        avg_entry_price=Decimal(str(avg_entry_price)),
        avg_exit_price=Decimal(str(round(avg_exit, 2))),
        realized_pnl=Decimal(str(pnl)),
        entry_time=exit_time - timedelta(minutes=30),
        exit_time=exit_time,
        duration_minutes=30,
        status="closed",
    )


def make_trade(
    qty: int = 10,
    order_time: datetime = None,
    transaction_type: str = "BUY",
    tradingsymbol: str = "INFY",
    broker_account_id=None,
) -> Trade:
    if order_time is None:
        order_time = utc_now()
    if broker_account_id is None:
        broker_account_id = BROKER_ID

    return Trade(
        id=uuid4(),
        broker_account_id=broker_account_id,
        order_id=f"TEST_{uuid4().hex[:8]}",
        tradingsymbol=tradingsymbol,
        exchange="NSE",
        transaction_type=transaction_type,
        order_type="MARKET",
        product="MIS",
        quantity=qty,
        filled_quantity=qty,
        pending_quantity=0,
        status="COMPLETE",
        asset_class="EQUITY",
        instrument_type="EQ",
        product_type="MIS",
        order_timestamp=order_time,
    )


def default_thresholds() -> dict:
    return get_thresholds(None)


# =============================================================================
# RISK DETECTOR TESTS — consecutive_loss
# =============================================================================

class TestConsecutiveLoss:
    """RiskDetector._detect_consecutive_losses"""

    det = RiskDetector()

    async def test_RD01_no_trades_returns_none(self):
        """RD-01: No completed trades -> no alert."""
        result = await self.det._detect_consecutive_losses([], None, default_thresholds())
        assert result is None

    async def test_RD02_two_losses_below_caution(self):
        """RD-02: 2 consecutive losses (threshold=3) -> no alert."""
        trades = [
            make_completed_trade(-500, minutes_ago(2)),
            make_completed_trade(-300, minutes_ago(5)),
        ]
        result = await self.det._detect_consecutive_losses(trades, None, default_thresholds())
        assert result is None

    async def test_RD03_three_losses_triggers_caution(self):
        """RD-03: Exactly 3 consecutive losses -> caution alert."""
        trades = [
            make_completed_trade(-500, minutes_ago(2)),
            make_completed_trade(-300, minutes_ago(5)),
            make_completed_trade(-200, minutes_ago(10)),
        ]
        result = await self.det._detect_consecutive_losses(trades, None, default_thresholds())
        assert result is not None
        assert result.severity == "caution"
        assert result.pattern_type == "consecutive_loss"

    async def test_RD04_five_losses_triggers_danger(self):
        """RD-04: 5 consecutive losses -> danger alert."""
        trades = [make_completed_trade(-100, minutes_ago(i * 5)) for i in range(5)]
        result = await self.det._detect_consecutive_losses(trades, None, default_thresholds())
        assert result is not None
        assert result.severity == "danger"
        assert "5" in result.message

    async def test_RD05_win_breaks_streak(self):
        """RD-05: Win after losses breaks the streak -> no alert for 2 consecutive before win."""
        trades = [
            make_completed_trade(-100, minutes_ago(2)),   # loss (most recent)
            make_completed_trade(-100, minutes_ago(5)),   # loss
            make_completed_trade(+500, minutes_ago(10)),  # WIN — breaks streak
            make_completed_trade(-100, minutes_ago(15)),  # loss (doesn't count — streak broken)
            make_completed_trade(-100, minutes_ago(20)),  # loss
        ]
        # Only 2 consecutive losses from the top (before the win)
        result = await self.det._detect_consecutive_losses(trades, None, default_thresholds())
        assert result is None

    async def test_RD05b_total_loss_amount_in_message(self):
        """RD-04b: Alert message includes total loss amount."""
        trades = [make_completed_trade(-1000, minutes_ago(i * 5)) for i in range(5)]
        result = await self.det._detect_consecutive_losses(trades, None, default_thresholds())
        assert result is not None
        assert "5,000" in result.message or "5000" in result.message  # ₹5,000 total loss


# =============================================================================
# RISK DETECTOR TESTS — revenge_sizing
# =============================================================================

class TestRevengeSizing:
    """RiskDetector._detect_revenge_sizing"""

    det = RiskDetector()

    async def test_RD06_no_trigger_trade_returns_none(self):
        """RD-06: No trigger_trade -> no alert (method requires trigger_trade)."""
        trades = [make_trade(qty=10)]
        completed = [make_completed_trade(-500, minutes_ago(5))]
        result = await self.det._detect_revenge_sizing(trades, completed, None, default_thresholds())
        assert result is None

    async def test_RD07_no_recent_loss_returns_none(self):
        """RD-07: Only profitable completed trades -> no revenge alert."""
        trigger = make_trade(qty=20, order_time=utc_now())
        completed = [make_completed_trade(+500, minutes_ago(5), qty=10)]
        trades = [trigger, make_trade(qty=10, order_time=minutes_ago(5))]
        result = await self.det._detect_revenge_sizing(trades, completed, trigger, default_thresholds())
        assert result is None

    async def test_RD08_small_size_increase_no_alert(self):
        """RD-08: Size increases by 1.3x within window -> no alert (threshold is 1.5x)."""
        loss_time = minutes_ago(5)
        trigger = make_trade(qty=13, order_time=utc_now())  # 13 vs 10 = 1.3x
        completed = [make_completed_trade(-500, loss_time, qty=10)]
        trades = [trigger, make_trade(qty=10, order_time=loss_time)]
        result = await self.det._detect_revenge_sizing(trades, completed, trigger, default_thresholds())
        assert result is None

    async def test_RD09_large_size_within_window_fires_danger(self):
        """RD-09: Size 2x within 5 minutes of loss -> danger alert."""
        loss_time = minutes_ago(5)
        trigger = make_trade(qty=20, order_time=utc_now())  # 20 vs 10 = 2x
        completed = [make_completed_trade(-1000, loss_time, qty=10)]
        trades = [trigger, make_trade(qty=10, order_time=loss_time)]
        result = await self.det._detect_revenge_sizing(trades, completed, trigger, default_thresholds())
        assert result is not None
        assert result.severity == "danger"
        assert result.pattern_type == "revenge_sizing"

    async def test_RD09b_outside_window_no_alert(self):
        """RD-09b: 2x size but 15 minutes after loss (outside 10-min window) -> no alert."""
        loss_time = minutes_ago(15)  # 15 min ago — outside the 10-min revenge window
        trigger = make_trade(qty=20, order_time=utc_now())
        completed = [make_completed_trade(-1000, loss_time, qty=10)]
        trades = [trigger, make_trade(qty=10, order_time=loss_time)]
        result = await self.det._detect_revenge_sizing(trades, completed, trigger, default_thresholds())
        assert result is None


# =============================================================================
# RISK DETECTOR TESTS — overtrading burst
# =============================================================================

class TestOvertradingBurst:
    """RiskDetector._detect_overtrading"""

    det = RiskDetector()

    async def test_RD10_five_trades_no_alert(self):
        """RD-10: 5 trades in 15 min (threshold=6) -> no alert."""
        trades = [make_trade(order_time=minutes_ago(i * 2)) for i in range(5)]
        result = await self.det._detect_overtrading(trades, None, default_thresholds())
        assert result is None

    async def test_RD11_six_trades_caution(self):
        """RD-11: Exactly 6 trades in 15 min -> caution alert."""
        trades = [make_trade(order_time=minutes_ago(i * 2)) for i in range(6)]
        result = await self.det._detect_overtrading(trades, None, default_thresholds())
        assert result is not None
        assert result.severity == "caution"
        assert result.pattern_type == "overtrading"

    async def test_RD12_nine_trades_danger(self):
        """RD-12: 9 trades in 15 min (danger threshold = int(6*1.4) = 8) -> danger alert."""
        trades = [make_trade(order_time=minutes_ago(i)) for i in range(9)]
        result = await self.det._detect_overtrading(trades, None, default_thresholds())
        assert result is not None
        assert result.severity == "danger"

    async def test_RD13_trades_spread_over_20min_no_alert(self):
        """RD-13: 6 trades but spread over 20 min — only 2 in last 15 min -> no alert."""
        trades = [
            make_trade(order_time=minutes_ago(1)),
            make_trade(order_time=minutes_ago(3)),
            make_trade(order_time=minutes_ago(17)),  # outside 15-min window
            make_trade(order_time=minutes_ago(19)),
            make_trade(order_time=minutes_ago(21)),
            make_trade(order_time=minutes_ago(23)),
        ]
        result = await self.det._detect_overtrading(trades, None, default_thresholds())
        assert result is None


# =============================================================================
# RISK DETECTOR TESTS — fomo_entry
# =============================================================================

class TestFomoEntry:
    """RiskDetector._detect_fomo_entry"""

    det = RiskDetector()

    async def test_RD14_no_trigger_trade_returns_none(self):
        """RD-14: No trigger_trade -> no alert."""
        result = await self.det._detect_fomo_entry([], None, default_thresholds())
        assert result is None

    async def test_RD15_two_opening_trades_no_alert(self):
        """RD-15: 2 trades at market open (threshold=3) -> no alert."""
        trigger = make_trade(order_time=ist_market_open(0))
        trades = [
            trigger,
            make_trade(order_time=ist_market_open(1)),
        ]
        result = await self.det._detect_fomo_entry(trades, trigger, default_thresholds())
        assert result is None

    async def test_RD16_three_opening_trades_caution(self):
        """RD-16: 3 trades in IST 9:15-9:20 -> FOMO opening alert."""
        trigger = make_trade(order_time=ist_market_open(2))
        trades = [
            trigger,
            make_trade(order_time=ist_market_open(1)),
            make_trade(order_time=ist_market_open(0)),
        ]
        result = await self.det._detect_fomo_entry(trades, trigger, default_thresholds())
        assert result is not None
        assert result.pattern_type == "fomo"
        assert result.severity == "caution"

    async def test_RD17_chasing_same_symbol_same_direction(self):
        """RD-17: 3 BUYs on same symbol in 5 min -> chasing alert."""
        trigger = make_trade(order_time=utc_now(), tradingsymbol="NIFTY", transaction_type="BUY")
        trades = [
            trigger,
            make_trade(order_time=minutes_ago(2), tradingsymbol="NIFTY", transaction_type="BUY"),
            make_trade(order_time=minutes_ago(4), tradingsymbol="NIFTY", transaction_type="BUY"),
        ]
        result = await self.det._detect_fomo_entry(trades, trigger, default_thresholds())
        assert result is not None
        assert result.pattern_type == "fomo"

    async def test_RD18_different_symbols_no_chasing_alert(self):
        """RD-18: 3 BUYs on different symbols in 5 min -> no chasing alert."""
        trigger = make_trade(order_time=utc_now(), tradingsymbol="INFY", transaction_type="BUY")
        trades = [
            trigger,
            make_trade(order_time=minutes_ago(2), tradingsymbol="TCS", transaction_type="BUY"),
            make_trade(order_time=minutes_ago(4), tradingsymbol="WIPRO", transaction_type="BUY"),
        ]
        result = await self.det._detect_fomo_entry(trades, trigger, default_thresholds())
        assert result is None  # Different symbols -> not chasing


# =============================================================================
# RISK DETECTOR TESTS — tilt_loss_spiral
# =============================================================================

class TestTiltLossSpiral:
    """RiskDetector._detect_tilt_spiral"""

    det = RiskDetector()

    async def test_RD19_insufficient_completed_trades(self):
        """RD-19: Only 2 completed trades -> not enough data for tilt detection."""
        trades = [make_trade() for _ in range(5)]
        completed = [
            make_completed_trade(-100, minutes_ago(5), qty=10, avg_entry_price=100),
            make_completed_trade(-150, minutes_ago(10), qty=12, avg_entry_price=100),
        ]
        result = await self.det._detect_tilt_spiral(trades, completed, None, default_thresholds())
        assert result is None

    async def test_RD20_escalating_sizes_all_losses_triggers_danger(self):
        """RD-20: 4 completed trades with escalating sizes + all losses -> danger alert."""
        # Sizes increasing: 10, 15, 20, 25 (all at 100/unit = escalating notional)
        completed = [
            make_completed_trade(-200, minutes_ago(20), qty=10, avg_entry_price=100),
            make_completed_trade(-300, minutes_ago(15), qty=15, avg_entry_price=100),
            make_completed_trade(-400, minutes_ago(10), qty=20, avg_entry_price=100),
            make_completed_trade(-500, minutes_ago(5), qty=25, avg_entry_price=100),
        ]
        trades = [make_trade()]
        result = await self.det._detect_tilt_spiral(trades, completed, None, default_thresholds())
        assert result is not None
        assert result.pattern_type == "tilt_loss_spiral"
        assert result.severity == "danger"

    async def test_RD21_constant_sizes_no_alert(self):
        """RD-21: Multiple losses but constant position sizes -> no tilt alert."""
        completed = [
            make_completed_trade(-200, minutes_ago(20), qty=10, avg_entry_price=100),
            make_completed_trade(-200, minutes_ago(15), qty=10, avg_entry_price=100),
            make_completed_trade(-200, minutes_ago(10), qty=10, avg_entry_price=100),
            make_completed_trade(-200, minutes_ago(5), qty=10, avg_entry_price=100),
        ]
        trades = [make_trade()]
        result = await self.det._detect_tilt_spiral(trades, completed, None, default_thresholds())
        assert result is None  # Sizes not escalating

    async def test_RD22_net_positive_pnl_no_alert(self):
        """RD-22: Escalating sizes but net P&L positive -> no tilt alert."""
        completed = [
            make_completed_trade(-100, minutes_ago(20), qty=10, avg_entry_price=100),
            make_completed_trade(-200, minutes_ago(15), qty=15, avg_entry_price=100),
            make_completed_trade(-300, minutes_ago(10), qty=20, avg_entry_price=100),
            make_completed_trade(+5000, minutes_ago(5), qty=25, avg_entry_price=100),  # Big win
        ]
        trades = [make_trade()]
        result = await self.det._detect_tilt_spiral(trades, completed, None, default_thresholds())
        assert result is None  # Net P&L positive


# =============================================================================
# BEHAVIORAL EVALUATOR TESTS — REVENGE_TRADING
# =============================================================================

class TestBERevengeTradng:
    """BehavioralEvaluator._detect_revenge_trading"""

    ev = BehavioralEvaluator()

    def test_BE01_no_completed_trades_returns_empty(self):
        """BE-01: No prior completed trades -> no revenge event."""
        fill = make_trade(qty=10, order_time=utc_now())
        events = self.ev._detect_revenge_trading(fill, [], [], BROKER_ID, default_thresholds())
        assert events == []

    def test_BE02_prior_win_not_revenge(self):
        """BE-02: Prior trade was profitable -> not revenge trading."""
        fill = make_trade(qty=20, order_time=utc_now())
        prior = make_completed_trade(+500, minutes_ago(5), qty=10)
        events = self.ev._detect_revenge_trading(fill, [prior], [], BROKER_ID, default_thresholds())
        assert events == []

    def test_BE03_loss_within_window_triggers_event(self):
        """BE-03: New entry within 10 min of loss -> REVENGE_TRADING event fired."""
        fill = make_trade(qty=15, order_time=utc_now())
        prior = make_completed_trade(-500, minutes_ago(5), qty=10)
        events = self.ev._detect_revenge_trading(fill, [prior], [], BROKER_ID, default_thresholds())
        assert len(events) == 1
        assert events[0].event_type == "REVENGE_TRADING"
        assert float(events[0].confidence) >= 0.70

    def test_BE04_high_severity_for_2x_size_in_short_gap(self):
        """BE-04: 2x size within 3 min (1/3 of 10-min window) -> HIGH severity."""
        fill = make_trade(qty=20, order_time=minutes_ago(2))
        prior = make_completed_trade(-1000, minutes_ago(4), qty=10)  # 2x size, 2-min gap
        events = self.ev._detect_revenge_trading(fill, [prior], [], BROKER_ID, default_thresholds())
        assert len(events) == 1
        assert events[0].severity == "HIGH"

    def test_BE05_outside_window_no_event(self):
        """BE-05: Entry 15 min after loss (outside 10-min window) -> no event."""
        fill = make_trade(qty=20, order_time=utc_now())
        prior = make_completed_trade(-500, minutes_ago(15), qty=10)  # 15 min ago
        events = self.ev._detect_revenge_trading(fill, [prior], [], BROKER_ID, default_thresholds())
        assert events == []


# =============================================================================
# BEHAVIORAL EVALUATOR TESTS — OVERTRADING
# =============================================================================

class TestBEOvertrading:
    """BehavioralEvaluator._detect_overtrading"""

    ev = BehavioralEvaluator()

    def test_BE06_five_trades_no_event(self):
        """BE-06: 5 trades in 15 min (threshold=6) -> no event."""
        fill = make_trade(order_time=utc_now())
        trades = [make_trade(order_time=minutes_ago(i * 2)) for i in range(5)]
        events = self.ev._detect_overtrading(fill, trades, [], BROKER_ID, default_thresholds())
        assert events == []

    def test_BE07_six_trades_fires_event(self):
        """BE-07: 6 trades in 15 min -> OVERTRADING event."""
        fill = make_trade(order_time=utc_now())
        trades = [make_trade(order_time=minutes_ago(i * 2)) for i in range(6)]
        events = self.ev._detect_overtrading(fill, trades, [], BROKER_ID, default_thresholds())
        assert len(events) == 1
        assert events[0].event_type == "OVERTRADING"
        assert float(events[0].confidence) >= 0.70

    def test_BE08_high_count_is_high_severity(self):
        """BE-08: int(6*1.4)=8+ trades -> HIGH severity."""
        fill = make_trade(order_time=utc_now())
        trades = [make_trade(order_time=minutes_ago(i)) for i in range(9)]
        events = self.ev._detect_overtrading(fill, trades, [], BROKER_ID, default_thresholds())
        assert len(events) == 1
        assert events[0].severity == "HIGH"

    def test_BE09_trades_outside_window_not_counted(self):
        """BE-09: 6 trades total but only 3 in last 15 min -> no event."""
        fill = make_trade(order_time=utc_now())
        trades = [
            make_trade(order_time=minutes_ago(2)),
            make_trade(order_time=minutes_ago(5)),
            make_trade(order_time=minutes_ago(8)),
            make_trade(order_time=minutes_ago(20)),  # outside window
            make_trade(order_time=minutes_ago(22)),
            make_trade(order_time=minutes_ago(25)),
        ]
        events = self.ev._detect_overtrading(fill, trades, [], BROKER_ID, default_thresholds())
        assert events == []


# =============================================================================
# BEHAVIORAL EVALUATOR TESTS — TILT_SPIRAL
# =============================================================================

class TestBETiltSpiral:
    """BehavioralEvaluator._detect_tilt_spiral"""

    ev = BehavioralEvaluator()

    def test_BE10_less_than_4_completed_trades_no_event(self):
        """BE-10: Only 3 completed trades (need 4 min) -> no event."""
        fill = make_trade()
        completed = [
            make_completed_trade(-100, minutes_ago(15), qty=10, avg_entry_price=100),
            make_completed_trade(-200, minutes_ago(10), qty=15, avg_entry_price=100),
            make_completed_trade(-300, minutes_ago(5), qty=20, avg_entry_price=100),
        ]
        events = self.ev._detect_tilt_spiral(fill, completed, [], BROKER_ID, default_thresholds())
        assert events == []

    def test_BE11_escalating_sizes_net_negative_fires_event(self):
        """BE-11: 4+ trades with escalating sizes + net negative P&L -> TILT_SPIRAL event."""
        fill = make_trade()
        completed = [
            make_completed_trade(-100, minutes_ago(20), qty=10, avg_entry_price=100),
            make_completed_trade(-200, minutes_ago(15), qty=15, avg_entry_price=100),
            make_completed_trade(-300, minutes_ago(10), qty=20, avg_entry_price=100),
            make_completed_trade(-400, minutes_ago(5), qty=25, avg_entry_price=100),
        ]
        events = self.ev._detect_tilt_spiral(fill, completed, [], BROKER_ID, default_thresholds())
        assert len(events) == 1
        assert events[0].event_type == "TILT_SPIRAL"
        assert float(events[0].confidence) >= 0.70

    def test_BE12_net_positive_pnl_no_event(self):
        """BE-12: Escalating sizes but net P&L positive -> no tilt event."""
        fill = make_trade()
        completed = [
            make_completed_trade(-100, minutes_ago(20), qty=10, avg_entry_price=100),
            make_completed_trade(-200, minutes_ago(15), qty=15, avg_entry_price=100),
            make_completed_trade(-300, minutes_ago(10), qty=20, avg_entry_price=100),
            make_completed_trade(+5000, minutes_ago(5), qty=25, avg_entry_price=100),  # big win
        ]
        events = self.ev._detect_tilt_spiral(fill, completed, [], BROKER_ID, default_thresholds())
        assert events == []

    def test_BE13_flat_sizes_no_event(self):
        """BE-13: All losses but constant position sizes -> no tilt event (not escalating)."""
        fill = make_trade()
        completed = [
            make_completed_trade(-100, minutes_ago(20), qty=10, avg_entry_price=100),
            make_completed_trade(-100, minutes_ago(15), qty=10, avg_entry_price=100),
            make_completed_trade(-100, minutes_ago(10), qty=10, avg_entry_price=100),
            make_completed_trade(-100, minutes_ago(5), qty=10, avg_entry_price=100),
        ]
        events = self.ev._detect_tilt_spiral(fill, completed, [], BROKER_ID, default_thresholds())
        assert events == []


# =============================================================================
# BEHAVIORAL EVALUATOR TESTS — FOMO_ENTRY
# =============================================================================

class TestBEFomoEntry:
    """BehavioralEvaluator._detect_fomo_entry"""

    ev = BehavioralEvaluator()

    def test_BE14_opening_two_trades_no_event(self):
        """BE-14: 2 trades at IST 9:15-9:20 (threshold=3) -> no event."""
        fill = make_trade(order_time=ist_market_open(1))
        trades = [fill, make_trade(order_time=ist_market_open(0))]
        events = self.ev._detect_fomo_entry(fill, trades, [], BROKER_ID, default_thresholds())
        assert events == []

    def test_BE15_three_opening_trades_fires_event(self):
        """BE-15: 3 trades in IST 9:15-9:20 -> FOMO_ENTRY (market open)."""
        fill = make_trade(order_time=ist_market_open(3))
        trades = [
            fill,
            make_trade(order_time=ist_market_open(2)),
            make_trade(order_time=ist_market_open(0)),
        ]
        events = self.ev._detect_fomo_entry(fill, trades, [], BROKER_ID, default_thresholds())
        fomo_events = [e for e in events if e.event_type == "FOMO_ENTRY"]
        assert len(fomo_events) >= 1

    def test_BE16_trades_at_10am_ist_not_opening_fomo(self):
        """BE-16: 3 trades at IST 10:00 (not market opening) -> no opening FOMO."""
        # 10:00 IST = 04:30 UTC
        today_ist = datetime.now(IST).date()
        ts_10am = datetime(today_ist.year, today_ist.month, today_ist.day, 10, 0, 0, tzinfo=IST)
        fill = make_trade(order_time=ts_10am.astimezone(timezone.utc))
        trades = [
            fill,
            make_trade(order_time=(ts_10am - timedelta(minutes=2)).astimezone(timezone.utc)),
            make_trade(order_time=(ts_10am - timedelta(minutes=4)).astimezone(timezone.utc)),
        ]
        events = self.ev._detect_fomo_entry(fill, trades, [], BROKER_ID, default_thresholds())
        # Opening FOMO should NOT fire (trades at 10:00 IST, not 9:15-9:20)
        opening_fomo = [
            e for e in events
            if e.event_type == "FOMO_ENTRY" and "market_open" in str(e.context)
        ]
        assert opening_fomo == []

    def test_BE17_chasing_same_symbol_fires_event(self):
        """BE-17: 3 BUYs on BANKNIFTY in 5 min -> FOMO_ENTRY (chasing)."""
        fill = make_trade(order_time=utc_now(), tradingsymbol="BANKNIFTY", transaction_type="BUY")
        trades = [
            fill,
            make_trade(order_time=minutes_ago(2), tradingsymbol="BANKNIFTY", transaction_type="BUY"),
            make_trade(order_time=minutes_ago(4), tradingsymbol="BANKNIFTY", transaction_type="BUY"),
        ]
        events = self.ev._detect_fomo_entry(fill, trades, [], BROKER_ID, default_thresholds())
        chasing = [e for e in events if "chasing" in e.message.lower() or "rapid" in e.message.lower()]
        assert len(chasing) >= 1

    def test_BE18_chasing_different_symbols_no_event(self):
        """BE-18: 3 BUYs but different symbols -> no chasing event."""
        fill = make_trade(order_time=utc_now(), tradingsymbol="INFY", transaction_type="BUY")
        trades = [
            fill,
            make_trade(order_time=minutes_ago(2), tradingsymbol="TCS", transaction_type="BUY"),
            make_trade(order_time=minutes_ago(4), tradingsymbol="WIPRO", transaction_type="BUY"),
        ]
        events = self.ev._detect_fomo_entry(fill, trades, [], BROKER_ID, default_thresholds())
        chasing = [e for e in events if "rapid" in e.message.lower() or "chasing" in e.message.lower()]
        assert chasing == []


# =============================================================================
# BEHAVIORAL EVALUATOR TESTS — LOSS_CHASING
# =============================================================================

class TestBELossChasing:
    """BehavioralEvaluator._detect_loss_chasing"""

    ev = BehavioralEvaluator()

    def test_BE19_no_same_symbol_loss_returns_empty(self):
        """BE-19: Fill on INFY, prior loss was on TCS (different symbol) -> no loss-chasing event."""
        fill = make_trade(tradingsymbol="INFY", order_time=utc_now())
        prior = make_completed_trade(-500, minutes_ago(5), tradingsymbol="TCS")
        events = self.ev._detect_loss_chasing(fill, [prior], [], BROKER_ID, default_thresholds())
        assert events == []

    def test_BE20_same_symbol_within_window_fires_event(self):
        """BE-20: Re-entry on INFY within 5 min of losing INFY trade -> LOSS_CHASING event."""
        fill = make_trade(tradingsymbol="INFY", order_time=utc_now())
        prior = make_completed_trade(-500, minutes_ago(4), tradingsymbol="INFY")
        events = self.ev._detect_loss_chasing(fill, [prior], [], BROKER_ID, default_thresholds())
        assert len(events) == 1
        assert events[0].event_type == "LOSS_CHASING"
        assert float(events[0].confidence) >= 0.70

    def test_BE21_same_symbol_outside_window_no_event(self):
        """BE-21: Re-entry on same symbol but 15 min later (outside 10-min window) -> no event."""
        fill = make_trade(tradingsymbol="INFY", order_time=utc_now())
        prior = make_completed_trade(-500, minutes_ago(15), tradingsymbol="INFY")
        events = self.ev._detect_loss_chasing(fill, [prior], [], BROKER_ID, default_thresholds())
        assert events == []

    def test_BE22_prior_win_on_same_symbol_no_event(self):
        """BE-22: Re-entry on same symbol but prior was profitable -> no loss-chasing event."""
        fill = make_trade(tradingsymbol="INFY", order_time=utc_now())
        prior = make_completed_trade(+500, minutes_ago(4), tradingsymbol="INFY")
        events = self.ev._detect_loss_chasing(fill, [prior], [], BROKER_ID, default_thresholds())
        assert events == []


# =============================================================================
# THRESHOLD SYSTEM TESTS
# =============================================================================

class TestThresholdSystem:
    """3-tier threshold: profile > cold-start defaults > universal floors."""

    det = RiskDetector()
    ev = BehavioralEvaluator()

    async def test_TH01_default_thresholds_correct(self):
        """TH-01: Default thresholds match COLD_START_DEFAULTS."""
        th = get_thresholds(None)
        assert th['burst_trades_per_15min'] == 6
        assert th['revenge_window_min'] == 10
        assert th['consecutive_loss_caution'] == 3
        assert th['consecutive_loss_danger'] == 5

    async def test_TH02_profile_overrides_revenge_window(self):
        """TH-02: UserProfile.cooldown_after_loss=5 -> revenge_window_min=5 (not 10)."""
        class MockProfile:
            cooldown_after_loss = 5
            daily_trade_limit = None
            detected_patterns = {}
            trading_capital = None
            daily_loss_limit = None
            max_position_size = None
            sl_percent_futures = None
            sl_percent_options = None
            risk_tolerance = None

        th = get_thresholds(MockProfile())
        assert th['revenge_window_min'] == 5

    async def test_TH03_profile_narrows_window_alert_fires_at_new_threshold(self):
        """TH-03: With 5-min window, trade 12 min after loss -> outside window -> no alert."""
        class MockProfile:
            cooldown_after_loss = 5
            daily_trade_limit = None
            detected_patterns = {}
            trading_capital = None
            daily_loss_limit = None
            max_position_size = None
            sl_percent_futures = None
            sl_percent_options = None
            risk_tolerance = None

        th = get_thresholds(MockProfile())

        fill = make_trade(qty=20, order_time=utc_now())
        prior = make_completed_trade(-1000, minutes_ago(7), qty=10)  # 7 min ago > 5-min window
        events = self.ev._detect_revenge_trading(fill, [prior], [], BROKER_ID, th)
        assert events == []  # 7 min > 5 min window -> no event

    async def test_TH04_universal_floor_prevents_absurd_zero_window(self):
        """TH-04: Even if profile sets cooldown_after_loss=0, floor of 1 min applies."""
        class MockProfile:
            cooldown_after_loss = 0  # absurd config
            daily_trade_limit = None
            detected_patterns = {}
            trading_capital = None
            daily_loss_limit = None
            max_position_size = None
            sl_percent_futures = None
            sl_percent_options = None
            risk_tolerance = None

        th = get_thresholds(MockProfile())
        assert th['revenge_window_min'] >= 1  # floor applied


# =============================================================================
# DEDUPLICATION TESTS
# =============================================================================

class TestDeduplication:
    """BehavioralEvaluator dedup: same (event_type, position_key) within 60 min -> blocked."""

    ev = BehavioralEvaluator()

    def test_DD01_no_recent_events_not_duplicate(self):
        """DD-01: No prior events -> _is_duplicate returns False."""
        fill = make_trade(qty=20, order_time=utc_now())
        prior_ct = make_completed_trade(-500, minutes_ago(5), qty=10)
        events = self.ev._detect_revenge_trading(fill, [prior_ct], [], BROKER_ID, default_thresholds())
        assert len(events) == 1
        # Simulate the dedup check
        event = events[0]
        is_dup = self.ev._is_duplicate(event, [])  # No prior events
        assert is_dup is False

    def test_DD02_recent_identical_event_is_duplicate(self):
        """DD-02: Same event_type + position_key emitted 30 min ago -> _is_duplicate returns True."""
        fill = make_trade(qty=20, order_time=utc_now(), tradingsymbol="INFY")
        prior_ct = make_completed_trade(-500, minutes_ago(5), qty=10)

        events = self.ev._detect_revenge_trading(fill, [prior_ct], [], BROKER_ID, default_thresholds())
        assert len(events) >= 1
        event = events[0]

        # Create a "prior" event with the same key, 30 minutes ago (within 60-min dedup window)
        prior_event = BehavioralEvent(
            id=uuid4(),
            broker_account_id=BROKER_ID,
            event_type=event.event_type,
            trigger_position_key=event.trigger_position_key,
            severity="HIGH",
            confidence=Decimal("0.90"),
            message="same event 30 min ago",
            context={},
            detected_at=utc_now() - timedelta(minutes=30),
        )

        is_dup = self.ev._is_duplicate(event, [prior_event])
        assert is_dup is True

    def test_DD03_old_event_beyond_dedup_window_not_duplicate(self):
        """DD-03: Same event_type + position_key but 90 min ago -> not a duplicate."""
        fill = make_trade(qty=20, order_time=utc_now(), tradingsymbol="INFY")
        prior_ct = make_completed_trade(-500, minutes_ago(5), qty=10)
        events = self.ev._detect_revenge_trading(fill, [prior_ct], [], BROKER_ID, default_thresholds())
        assert len(events) >= 1
        event = events[0]

        old_event = BehavioralEvent(
            id=uuid4(),
            broker_account_id=BROKER_ID,
            event_type=event.event_type,
            trigger_position_key=event.trigger_position_key,
            severity="HIGH",
            confidence=Decimal("0.90"),
            message="same event 90 min ago",
            context={},
            detected_at=utc_now() - timedelta(minutes=90),  # older than 60-min dedup window
        )

        is_dup = self.ev._is_duplicate(event, [old_event])
        assert is_dup is False  # expired dedup window


# =============================================================================
# CONFIDENCE THRESHOLD TESTS
# =============================================================================

class TestConfidenceThresholds:
    """BehavioralEvaluator hard rules: events below 0.70 confidence must be suppressed."""

    ev = BehavioralEvaluator()

    def test_CT01_revenge_confidence_at_least_0_70(self):
        """CT-01: All emitted REVENGE_TRADING events have confidence >= 0.70."""
        fill = make_trade(qty=12, order_time=minutes_ago(1))
        prior = make_completed_trade(-100, minutes_ago(9), qty=10)  # near boundary of window
        events = self.ev._detect_revenge_trading(fill, [prior], [], BROKER_ID, default_thresholds())
        for e in events:
            assert float(e.confidence) >= 0.70, f"Event confidence {e.confidence} is below 0.70"

    def test_CT02_overtrading_confidence_at_least_0_70(self):
        """CT-02: All emitted OVERTRADING events have confidence >= 0.70."""
        fill = make_trade(order_time=utc_now())
        trades = [make_trade(order_time=minutes_ago(i * 2)) for i in range(7)]
        events = self.ev._detect_overtrading(fill, trades, [], BROKER_ID, default_thresholds())
        for e in events:
            assert float(e.confidence) >= 0.70

    def test_CT03_high_severity_requires_0_85_confidence(self):
        """CT-03: No HIGH severity event has confidence below 0.85."""
        fill = make_trade(qty=20, order_time=minutes_ago(2))
        prior = make_completed_trade(-1000, minutes_ago(4), qty=10)  # 2x, 2-min gap -> HIGH
        events = self.ev._detect_revenge_trading(fill, [prior], [], BROKER_ID, default_thresholds())
        for e in events:
            if e.severity == "HIGH":
                assert float(e.confidence) >= 0.85, (
                    f"HIGH severity event has confidence {e.confidence} < 0.85"
                )
