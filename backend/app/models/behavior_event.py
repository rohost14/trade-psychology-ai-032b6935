"""
BehaviorEvent — the append-only evidence record (Engine v2, migration 064).

RiskAlert answers "what did we tell the user".
BehaviorEvent answers "what did the engine see".

Every detection is recorded here, INCLUDING:
  * info-severity events (analytics-only detectors)
  * events whose notification was suppressed (constitution wins, dedup, staleness)
Suppression happens at the notification layer only — never at the event layer
(master spec §1C.8). Behavioral state, scores, and analytics all read from
this table; hiding evidence here would corrupt them.

Not to be confused with the legacy `behavioral_events` table
(models/behavioral_event.py) — frozen since Session 21, kept for old rows.
"""
import uuid
from sqlalchemy import Column, String, Numeric, Text, TIMESTAMP, text, ForeignKey, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class BehaviorEvent(Base):
    __tablename__ = "behavior_events"
    __table_args__ = (
        Index("idx_behavior_events_broker_detected", "broker_account_id", "detected_at"),
        Index("idx_behavior_events_detector", "detector", "detected_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )

    detector = Column(String(60), nullable=False)          # pattern_type
    detector_version = Column(String(20), nullable=False)
    severity = Column(String(10), nullable=False)          # info | caution | danger | critical
    confidence = Column(Numeric(5, 2))                     # 0-100, independent of severity
    data_quality = Column(String(10), nullable=False, default="GOOD")

    message = Column(Text, nullable=False)
    evidence = Column(JSONB)          # detector context: trade lists, values, thresholds crossed
    input_snapshot = Column(JSONB)    # replayability: trade ids + thresholds used at detection

    trigger_completed_trade_id = Column(
        UUID(as_uuid=True),
        ForeignKey("completed_trades.id", ondelete="SET NULL"),
    )
    risk_alert_id = Column(
        UUID(as_uuid=True),
        ForeignKey("risk_alerts.id", ondelete="SET NULL"),
    )

    # Idempotency (migration 066): detector:trigger_trade_id:rule — makes
    # webhook retries and bulk-sync re-processing insert-safe (ON CONFLICT
    # DO NOTHING). NULL for events without a trigger trade (historical
    # death_spiral rows, retired 2026-09-02;
    # position monitor) which carry their own dedup.
    idempotency_key = Column(Text)

    # Feature-flag shadow marker (migration 068). True when the detector that
    # produced this event was running in shadow/canary-dark mode: the event is
    # recorded as evidence but must NOT alert and must NOT move any score.
    # Scoring reads WHERE shadow = false. Distinct from notification suppression,
    # which still feeds the score.
    shadow = Column(Boolean, nullable=False, server_default=text("false"), default=False)

    detected_at = Column(TIMESTAMP(timezone=True), nullable=False)  # trade time
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    broker_account = relationship("BrokerAccount")
