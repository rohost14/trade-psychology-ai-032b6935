from sqlalchemy import Column, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base


class AdminSetting(Base):
    """Runtime global setting (migration 074). key → value JSONB. Durable source of truth;
    admin_settings_service fronts it with a Redis cache for cheap sync reads."""
    __tablename__ = "admin_settings"

    key        = Column(Text, primary_key=True)
    value      = Column(JSONB, nullable=False)
    updated_by = Column(Text, nullable=True)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
