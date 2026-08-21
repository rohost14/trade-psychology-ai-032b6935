import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, Numeric, Integer, Date, TIMESTAMP, text, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class TradingSession(Base):
    """
    One row per (broker_account, trading_day).

    Tracks session P&L, risk score (0-100 internal), and state machine.
    Created on first trade of the day. Updated incrementally as trades arrive.

    risk_score, peak_risk_score and session_state are DORMANT as of 2026-08-13.
    The 40/70/90 ladder and update_risk_score were removed with the behaviour
    score (see trading_session_service). Nothing writes these three columns any
    more, so risk_score and peak_risk_score stay 0 and session_state stays
    "normal" — the CheckConstraint below still polices four values of which only
    one can now occur. Columns kept because dropping them needs a migration.
    """
    __tablename__ = "trading_sessions"

    __table_args__ = (
        CheckConstraint(
            "session_state IN ('normal', 'caution', 'danger', 'blowup')",
            name="chk_session_state"
        ),
        UniqueConstraint(
            'broker_account_id', 'session_date',
            name='uq_trading_session_account_date'
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    broker_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Session identity
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    market_open: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    market_close: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Equity snapshots
    opening_equity: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    closing_equity: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)

    # Aggregated session metrics
    session_pnl: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("0"))
    trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    alerts_fired: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Risk tracking (internal)
    risk_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0"))
    peak_risk_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("0"))

    # State machine
    session_state: Mapped[str] = mapped_column(String(10), nullable=False, default="normal")

    # Morning intent
    intent_acknowledged: Mapped[bool] = mapped_column(nullable=False, default=False)
    intent_max_trades: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    intent_max_loss: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    intent_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    # Relationships
    broker_account = relationship("BrokerAccount")
