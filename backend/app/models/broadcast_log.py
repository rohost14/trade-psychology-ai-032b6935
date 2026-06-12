from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid


class BroadcastLog(Base):
    __tablename__ = "broadcast_logs"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_by  = Column(String(255), nullable=False)
    segment     = Column(String(50), nullable=False)
    message     = Column(Text, nullable=False)
    total       = Column(Integer, nullable=False, default=0)
    sent        = Column(Integer, nullable=False, default=0)
    failed      = Column(Integer, nullable=False, default=0)
    created_at  = Column(DateTime(timezone=True))


class BroadcastReceipt(Base):
    __tablename__ = "broadcast_receipts"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broadcast_id = Column(UUID(as_uuid=True), nullable=False)
    phone        = Column(String(20), nullable=False)
    status       = Column(String(20), nullable=False, default="queued")
    error        = Column(Text, nullable=True)
    sent_at      = Column(DateTime(timezone=True), nullable=True)
