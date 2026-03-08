"""
Behavioral Evaluator Service — Signal Pipeline

Event-driven behavioral signal detector. Runs AFTER data pipeline.
Reads trades, positions, and recent behavioral_events.
Emits BehavioralEvent records with confidence scores.

HARD RULES:
- MUST NOT mutate trades, positions, or P&L
- No event emitted below 0.70 confidence
- HIGH severity requires confidence >= 0.85
- MEDIUM severity requires confidence >= 0.75
- LOW severity requires confidence >= 0.70
- Events are persisted BEFORE any delivery
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from uuid import UUID
from decimal import Decimal
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
import logging

from app.models.trade import Trade
from app.models.completed_trade import CompletedTrade
from app.models.position import Position
from app.models.behavioral_event import BehavioralEvent
from app.core.trading_defaults import get_thresholds

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


class BehavioralEvaluator:
    """
    Event-driven behavioral signal detector.

    Confidence thresholds per severity:
    - HIGH: >= 0.85
    - MEDIUM: >= 0.75
    - LOW: >= 0.70
    """

    CONFIDENCE_THRESHOLDS = {
        "HIGH": Decimal("0.85"),
        "MEDIUM": Decimal("0.75"),
        "LOW": Decimal("0.70"),
    }

    # Dedup window: don't re-emit same (event_type, position_key) within this window
    DEDUP_WINDOW_MINUTES = 60

    async def evaluate(
        self,
        broker_account_id: UUID,
        new_fills: List[Trade],
        db: AsyncSession,
        profile=None,
    ) -> List[BehavioralEvent]:
        """
        Evaluate new fills for behavioral signals.

        Returns events that passed confidence threshold and dedup check.
        Events are NOT yet persisted — caller persists after validation.
        """
        if not new_fills:
            return []

        # Build thresholds from user profile (3-tier system)
        thresholds = get_thresholds(profile)

        # Load context (read-only)
        recent_trades = await self._get_recent_trades(broker_account_id, db)
        recent_completed = await self._get_recent_completed_trades(broker_account_id, db)
        open_positions = await self._get_open_positions(broker_account_id, db)
        recent_events = await self._get_recent_events(broker_account_id, db)

        events: List[BehavioralEvent] = []

        # Run detectors
        # P&L-dependent detectors use recent_completed (real P&L)
        # Count/time-based detectors use recent_trades (fills)
        for fill in new_fills:
            events.extend(self._detect_revenge_trading(fill, recent_completed, recent_events, broker_account_id, thresholds))
            events.extend(self._detect_overtrading(fill, recent_trades, recent_events, broker_account_id, thresholds))
            events.extend(self._detect_tilt_spiral(fill, recent_completed, recent_events, broker_account_id, thresholds))
            events.extend(self._detect_fomo_entry(fill, recent_trades, open_positions, broker_account_id, thresholds))
            events.extend(self._detect_loss_chasing(fill, recent_completed, recent_events, broker_account_id, thresholds))

        # Filter by confidence threshold
        validated = []
        for event in events:
            min_conf = self.CONFIDENCE_THRESHOLDS.get(event.severity, Decimal("0.70"))
            if event.confidence >= min_conf:
                # Dedup: check if same event_type + position_key was emitted recently
                if not self._is_duplicate(event, recent_events):
                    validated.append(event)

        return validated

    # ------------------------------------------------------------------
    # Context loaders (read-only)
    # ------------------------------------------------------------------

    async def _get_recent_trades(
        self, broker_account_id: UUID, db: AsyncSession
    ) -> List[Trade]:
        """Get trades from last 24 hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        result = await db.execute(
            select(Trade).where(
                and_(
                    Trade.broker_account_id == broker_account_id,
                    Trade.status == "COMPLETE",
                    Trade.order_timestamp >= cutoff,
                )
            ).order_by(desc(Trade.order_timestamp))
        )
        return result.scalars().all()

    async def _get_open_positions(
        self, broker_account_id: UUID, db: AsyncSession
    ) -> List[Position]:
        """Get currently open positions."""
        result = await db.execute(
            select(Position).where(
                and_(
                    Position.broker_account_id == broker_account_id,
                    Position.total_quantity != 0,
                )
            )
        )
        return result.scalars().all()

    async def _get_recent_events(
        self, broker_account_id: UUID, db: AsyncSession
    ) -> List[BehavioralEvent]:
        """Get behavioral events from last 4 hours for dedup and context."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=4)
        result = await db.execute(
            select(BehavioralEvent).where(
                and_(
                    BehavioralEvent.broker_account_id == broker_account_id,
                    BehavioralEvent.detected_at >= cutoff,
                )
            ).order_by(desc(BehavioralEvent.detected_at))
        )
        return result.scalars().all()

    async def _get_recent_completed_trades(
        self, broker_account_id: UUID, db: AsyncSession
    ) -> List[CompletedTrade]:
        """Get completed trades from last 24 hours (real P&L data)."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        result = await db.execute(
            select(CompletedTrade).where(
                and_(
                    CompletedTrade.broker_account_id == broker_account_id,
                    CompletedTrade.exit_time >= cutoff,
                )
            ).order_by(desc(CompletedTrade.exit_time))
        )
        return result.scalars().all()

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _is_duplicate(
        self, event: BehavioralEvent, recent_events: List[BehavioralEvent]
    ) -> bool:
        """Check if a similar event was already emitted recently."""
        window = datetime.now(timezone.utc) - timedelta(minutes=self.DEDUP_WINDOW_MINUTES)
        for existing in recent_events:
            if (
                existing.event_type == event.event_type
                and existing.trigger_position_key == event.trigger_position_key
                and existing.detected_at >= window
            ):
                return True
        return False

    # ------------------------------------------------------------------
    # Helper to build position key
    # ------------------------------------------------------------------

    def _position_key(self, trade: Trade) -> str:
        """Build position key from trade: SYMBOL:EXCHANGE:PRODUCT:DIRECTION"""
        direction = "LONG" if trade.transaction_type == "BUY" else "SHORT"
        return f"{trade.tradingsymbol}:{trade.exchange}:{trade.product or ''}:{direction}"

    # ------------------------------------------------------------------
    # Pattern Detectors
    # ------------------------------------------------------------------

    def _detect_revenge_trading(
        self,
        fill: Trade,
        recent_completed: List[CompletedTrade],
        recent_events: List[BehavioralEvent],
        broker_account_id: UUID,
        thresholds: dict,
    ) -> List[BehavioralEvent]:
        """
        Revenge trading: new entry within revenge_window_min of a completed loss, with increased size.
        Uses CompletedTrade.realized_pnl for real P&L (Trade.pnl is always 0).
        """
        if not recent_completed:
            return []

        revenge_window = thresholds.get('revenge_window_min', 10)

        # Find the most recent completed trade (loss) before this fill
        prev_losses = [
            ct for ct in recent_completed
            if ct.exit_time and fill.order_timestamp
            and ct.exit_time < fill.order_timestamp
            and (ct.realized_pnl or 0) < 0
        ]
        if not prev_losses:
            return []

        prev = prev_losses[0]  # Most recent (list is desc by exit_time)

        # Time gap: fill entry vs previous trade's exit
        if not fill.order_timestamp or not prev.exit_time:
            return []
        gap_minutes = (fill.order_timestamp - prev.exit_time).total_seconds() / 60
        if gap_minutes > revenge_window:
            return []

        # Size increase
        prev_qty = prev.total_quantity or 0
        fill_qty = fill.filled_quantity or fill.quantity or 0
        if prev_qty <= 0 or fill_qty <= 0:
            return []

        size_ratio = fill_qty / prev_qty

        # Confidence: based on time gap and size increase
        time_factor = max(0, 1 - (gap_minutes / revenge_window))
        size_factor = min(1, max(0, (size_ratio - 1) / 2))
        raw_confidence = 0.70 + (time_factor * 0.15) + (size_factor * 0.15)
        confidence = Decimal(str(min(0.99, raw_confidence)))

        # Severity
        if size_ratio >= 2.0 and gap_minutes <= (revenge_window / 3):
            severity = "HIGH"
        elif size_ratio >= 1.5 or gap_minutes <= (revenge_window / 3):
            severity = "MEDIUM"
        else:
            severity = "LOW"

        prev_pnl = float(prev.realized_pnl or 0)

        return [BehavioralEvent(
            broker_account_id=broker_account_id,
            event_type="REVENGE_TRADING",
            severity=severity,
            confidence=confidence,
            trigger_trade_id=fill.id,
            trigger_position_key=self._position_key(fill),
            message=(
                f"Entered {fill.tradingsymbol} ({fill_qty} qty) just {gap_minutes:.0f} min "
                f"after a loss of ₹{abs(prev_pnl):,.0f}, with {size_ratio:.1f}x the previous size"
            ),
            context={
                "time_since_loss_minutes": round(gap_minutes, 1),
                "size_ratio": round(size_ratio, 2),
                "previous_pnl": prev_pnl,
                "previous_qty": prev_qty,
                "current_qty": fill_qty,
                "revenge_window_min": revenge_window,
            },
            detected_at=datetime.now(timezone.utc),
        )]

    def _detect_overtrading(
        self,
        fill: Trade,
        recent_trades: List[Trade],
        recent_events: List[BehavioralEvent],
        broker_account_id: UUID,
        thresholds: dict,
    ) -> List[BehavioralEvent]:
        """
        Overtrading: burst_trades_per_15min+ trades in 15-min window.
        Confidence scales with count.
        """
        if not fill.order_timestamp:
            return []

        burst_threshold = thresholds.get('burst_trades_per_15min', 7)

        window_start = fill.order_timestamp - timedelta(minutes=15)
        trades_in_window = [
            t for t in recent_trades
            if t.order_timestamp and t.order_timestamp >= window_start
        ]
        count = len(trades_in_window)

        if count < burst_threshold:
            return []

        # Confidence scales from 0.70 at threshold to 0.95 at 2x threshold
        raw_conf = 0.70 + min(0.25, (count - burst_threshold) * 0.05)
        confidence = Decimal(str(min(0.99, raw_conf)))

        danger_threshold = int(burst_threshold * 1.4)
        if count >= danger_threshold:
            severity = "HIGH"
        elif count >= burst_threshold + 1:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        return [BehavioralEvent(
            broker_account_id=broker_account_id,
            event_type="OVERTRADING",
            severity=severity,
            confidence=confidence,
            trigger_trade_id=fill.id,
            trigger_position_key=self._position_key(fill),
            message=f"{count} trades in the last 15 minutes (threshold: {burst_threshold})",
            context={
                "trade_count_15min": count,
                "burst_threshold": burst_threshold,
                "trades_per_minute": round(count / 15, 2),
            },
            detected_at=datetime.now(timezone.utc),
        )]

    def _detect_tilt_spiral(
        self,
        fill: Trade,
        recent_completed: List[CompletedTrade],
        recent_events: List[BehavioralEvent],
        broker_account_id: UUID,
        thresholds: dict,
    ) -> List[BehavioralEvent]:
        """
        Tilt/loss spiral: escalating position sizes while cumulative P&L is negative.
        Uses CompletedTrade.realized_pnl for real P&L (Trade.pnl is always 0).
        """
        caution_threshold = thresholds.get('consecutive_loss_caution', 3)

        # Sort chronologically (oldest first)
        sorted_ct = sorted(
            [ct for ct in recent_completed if ct.exit_time],
            key=lambda ct: ct.exit_time
        )
        if len(sorted_ct) < 4:
            return []

        last_ct = sorted_ct[-6:]  # Last 6 completed trades
        total_pnl = sum(float(ct.realized_pnl or 0) for ct in last_ct)

        if total_pnl >= 0:
            return []  # Not losing overall

        # Check for escalating sizes (qty * avg_entry_price as notional)
        sizes = [
            (ct.total_quantity or 0) * float(ct.avg_entry_price or 0)
            for ct in last_ct
        ]
        if len(sizes) < 4:
            return []

        recent_sizes = sizes[-4:]
        increasing_count = sum(
            1 for i in range(len(recent_sizes) - 1)
            if recent_sizes[i + 1] > recent_sizes[i]
        )

        if increasing_count < 2:
            return []  # Sizes aren't consistently increasing

        # Count consecutive losses from the end
        losses_in_row = 0
        for ct in reversed(last_ct):
            if (ct.realized_pnl or 0) < 0:
                losses_in_row += 1
            else:
                break

        if losses_in_row < caution_threshold:
            return []

        # Confidence: more consecutive losses + bigger total loss = higher
        raw_conf = 0.70 + min(0.25, losses_in_row * 0.05 + (increasing_count / 3) * 0.10)
        confidence = Decimal(str(min(0.99, raw_conf)))

        danger_threshold = thresholds.get('consecutive_loss_danger', 5)
        if losses_in_row >= danger_threshold and increasing_count >= 3:
            severity = "HIGH"
        elif losses_in_row >= caution_threshold:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        return [BehavioralEvent(
            broker_account_id=broker_account_id,
            event_type="TILT_SPIRAL",
            severity=severity,
            confidence=confidence,
            trigger_trade_id=fill.id,
            trigger_position_key=self._position_key(fill),
            message=(
                f"Loss spiral: {losses_in_row} consecutive losses with increasing position sizes. "
                f"Session loss: ₹{abs(total_pnl):,.0f}"
            ),
            context={
                "consecutive_losses": losses_in_row,
                "total_session_loss": round(total_pnl, 2),
                "size_increasing_count": increasing_count,
                "caution_threshold": caution_threshold,
            },
            detected_at=datetime.now(timezone.utc),
        )]

    def _detect_fomo_entry(
        self,
        fill: Trade,
        recent_trades: List[Trade],
        open_positions: List[Position],
        broker_account_id: UUID,
        thresholds: dict,
    ) -> List[BehavioralEvent]:
        """
        FOMO entry: rapid entries in market opening (9:15-9:20 IST) or
        multiple same-direction trades on same symbol in 5 min.

        Uses IST timezone explicitly to avoid UTC-based false positives.
        """
        if not fill.order_timestamp:
            return []

        events = []

        # Check market opening FOMO using IST timezone (not UTC offset)
        fill_ist = fill.order_timestamp.astimezone(IST)
        if fill_ist.hour == 9 and fill_ist.minute < 20:
            opening_trades = [
                t for t in recent_trades
                if t.order_timestamp
                and t.order_timestamp.astimezone(IST).hour == 9
                and t.order_timestamp.astimezone(IST).minute < 20
                and t.order_timestamp.astimezone(IST).date() == fill_ist.date()
            ]
            if len(opening_trades) >= 3:
                raw_conf = 0.70 + min(0.25, (len(opening_trades) - 3) * 0.05)
                confidence = Decimal(str(min(0.99, raw_conf)))
                events.append(BehavioralEvent(
                    broker_account_id=broker_account_id,
                    event_type="FOMO_ENTRY",
                    severity="MEDIUM" if len(opening_trades) >= 4 else "LOW",
                    confidence=confidence,
                    trigger_trade_id=fill.id,
                    trigger_position_key=self._position_key(fill),
                    message=f"{len(opening_trades)} trades in first 5 minutes of market open",
                    context={
                        "opening_trade_count": len(opening_trades),
                        "window": "market_open_9:15-9:20_IST",
                    },
                    detected_at=datetime.now(timezone.utc),
                ))

        # Check chasing: 3+ same-direction trades on same symbol in 5 min
        window_start = fill.order_timestamp - timedelta(minutes=5)
        same_direction = [
            t for t in recent_trades
            if t.order_timestamp and t.order_timestamp >= window_start
            and t.transaction_type == fill.transaction_type
            and t.tradingsymbol == fill.tradingsymbol
        ]
        if len(same_direction) >= 3:
            raw_conf = 0.72 + min(0.23, (len(same_direction) - 3) * 0.06)
            confidence = Decimal(str(min(0.99, raw_conf)))
            events.append(BehavioralEvent(
                broker_account_id=broker_account_id,
                event_type="FOMO_ENTRY",
                severity="MEDIUM" if len(same_direction) >= 4 else "LOW",
                confidence=confidence,
                trigger_trade_id=fill.id,
                trigger_position_key=self._position_key(fill),
                message=(
                    f"{len(same_direction)} rapid {fill.transaction_type}s on "
                    f"{fill.tradingsymbol} in 5 minutes — chasing detected"
                ),
                context={
                    "rapid_same_direction_count": len(same_direction),
                    "direction": fill.transaction_type,
                    "symbol": fill.tradingsymbol,
                },
                detected_at=datetime.now(timezone.utc),
            ))

        return events

    def _detect_loss_chasing(
        self,
        fill: Trade,
        recent_completed: List[CompletedTrade],
        recent_events: List[BehavioralEvent],
        broker_account_id: UUID,
        thresholds: dict,
    ) -> List[BehavioralEvent]:
        """
        Loss chasing: re-entering the SAME symbol after a completed loss on it,
        within revenge_window_min. Uses CompletedTrade.realized_pnl for real P&L.
        """
        if not fill.order_timestamp:
            return []

        revenge_window = thresholds.get('revenge_window_min', 10)

        # Find recent completed trades on same symbol that were losses
        same_symbol_losses = [
            ct for ct in recent_completed
            if ct.tradingsymbol == fill.tradingsymbol
            and ct.exit_time
            and ct.exit_time < fill.order_timestamp
            and (ct.realized_pnl or 0) < 0
        ]
        if not same_symbol_losses:
            return []

        prev = same_symbol_losses[0]  # Most recent (desc sorted by exit_time)

        gap_minutes = (fill.order_timestamp - prev.exit_time).total_seconds() / 60
        if gap_minutes > revenge_window:
            return []

        prev_pnl = float(prev.realized_pnl or 0)

        # Confidence: shorter gap + bigger loss = higher
        time_factor = max(0, 1 - (gap_minutes / revenge_window))
        loss_factor = min(1, abs(prev_pnl) / 5000)  # Normalize around 5000
        raw_conf = 0.70 + (time_factor * 0.10) + (loss_factor * 0.15)
        confidence = Decimal(str(min(0.99, raw_conf)))

        severity = "MEDIUM" if gap_minutes <= (revenge_window / 3) else "LOW"

        return [BehavioralEvent(
            broker_account_id=broker_account_id,
            event_type="LOSS_CHASING",
            severity=severity,
            confidence=confidence,
            trigger_trade_id=fill.id,
            trigger_position_key=self._position_key(fill),
            message=(
                f"Re-entered {fill.tradingsymbol} just {gap_minutes:.0f} min after "
                f"losing ₹{abs(prev_pnl):,.0f} on it"
            ),
            context={
                "symbol": fill.tradingsymbol,
                "previous_loss": prev_pnl,
                "gap_minutes": round(gap_minutes, 1),
                "revenge_window_min": revenge_window,
            },
            detected_at=datetime.now(timezone.utc),
        )]
