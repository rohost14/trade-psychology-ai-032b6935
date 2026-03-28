"""
StrategyGroup — Multi-Leg Strategy Tracking

One StrategyGroup = one trading decision expressed as multiple legs
(e.g. straddle = CE leg + PE leg).

The group is created when the last leg closes (when we have all completed trades
to compute net P&L). Open legs are linked retroactively once their trade closes.

Why this matters
----------------
Without strategy awareness, the BehaviorEngine fires false alerts:
  - consecutive_loss_streak on a single losing leg of a profitable straddle
  - revenge_trade when adjusting a position (closing one strike, opening another)
  - size_escalation when adding a hedge leg (which REDUCES risk, not increases it)

With StrategyGroup, BehaviorEngine uses net_pnl instead of per-leg pnl and
suppresses structurally invalid alerts.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Numeric, TIMESTAMP, ForeignKey, Index, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class StrategyGroup(Base):
    __tablename__ = "strategy_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Classification
    strategy_type = Column(String(50), nullable=False)   # straddle_buy | strangle_sell | iron_condor | …
    underlying = Column(String(50), nullable=False)      # NIFTY | BANKNIFTY | RELIANCE …
    expiry_key = Column(String(20))                      # "2025-03" | "2025-03-20" (from instrument_parser)

    # Lifecycle
    status = Column(String(20), default="open")          # open | partially_closed | closed
    net_pnl = Column(Numeric(15, 4))                     # sum of all leg realized_pnl

    opened_at = Column(TIMESTAMP(timezone=True))         # earliest entry_time across legs
    closed_at = Column(TIMESTAMP(timezone=True))         # latest exit_time across legs

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # Relationships
    legs = relationship(
        "StrategyGroupLeg",
        back_populates="strategy_group",
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "broker_account_id": str(self.broker_account_id),
            "strategy_type": self.strategy_type,
            "underlying": self.underlying,
            "expiry_key": self.expiry_key,
            "status": self.status,
            "net_pnl": float(self.net_pnl) if self.net_pnl is not None else None,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class StrategyGroupLeg(Base):
    __tablename__ = "strategy_group_legs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_group_id = Column(
        UUID(as_uuid=True),
        ForeignKey("strategy_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    completed_trade_id = Column(
        UUID(as_uuid=True),
        ForeignKey("completed_trades.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,          # one CompletedTrade can only belong to one strategy group
        index=True,
    )

    # Role this leg plays in the strategy
    # Options: long_call | short_call | long_put | short_put | long_futures | short_futures | unknown
    leg_role = Column(String(30))

    leg_pnl = Column(Numeric(15, 4))

    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    # Relationships
    strategy_group = relationship("StrategyGroup", back_populates="legs")
    completed_trade = relationship("CompletedTrade")


# ---------------------------------------------------------------------------
# Strategy type constants (for reference / type-safety in code)
# ---------------------------------------------------------------------------

class StrategyType:
    STRADDLE_BUY    = "straddle_buy"
    STRADDLE_SELL   = "straddle_sell"
    STRANGLE_BUY    = "strangle_buy"
    STRANGLE_SELL   = "strangle_sell"
    BULL_CALL_SPREAD = "bull_call_spread"
    BEAR_PUT_SPREAD  = "bear_put_spread"
    BULL_PUT_SPREAD  = "bull_put_spread"
    BEAR_CALL_SPREAD = "bear_call_spread"
    IRON_CONDOR      = "iron_condor"
    IRON_BUTTERFLY   = "iron_butterfly"
    FUTURES_HEDGE_BULLISH = "futures_hedge_bullish"   # Long FUT + Buy PE
    FUTURES_HEDGE_BEARISH = "futures_hedge_bearish"   # Short FUT + Buy CE
    CALENDAR_SPREAD  = "calendar_spread"              # Same strike, different expiry
    SYNTHETIC_LONG   = "synthetic_long"               # Buy CE + Sell PE (same strike)
    SYNTHETIC_SHORT  = "synthetic_short"              # Sell CE + Buy PE (same strike)
    MULTI_LEG_UNKNOWN = "multi_leg_unknown"
