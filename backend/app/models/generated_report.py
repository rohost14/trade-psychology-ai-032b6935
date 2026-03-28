import uuid
from datetime import datetime, date
from typing import Optional, Any
from sqlalchemy import String, TIMESTAMP, Date, text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class GeneratedReport(Base):
    """
    Saved copies of all generated reports for the Reports Hub.
    Stores morning briefs, EOD post-market reports, and weekly summaries.
    """
    __tablename__ = "generated_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("broker_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_type: Mapped[str] = mapped_column(String(30), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    report_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    sent_via: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    broker_account = relationship("BrokerAccount")

    def to_summary_dict(self) -> dict:
        """Return lightweight summary with key metrics extracted from report_data."""
        base = {
            "id": str(self.id),
            "broker_account_id": str(self.broker_account_id),
            "report_type": self.report_type,
            "report_date": self.report_date.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "sent_via": self.sent_via,
        }

        if self.report_type == "post_market":
            summary = self.report_data.get("summary", {})
            base["total_pnl"] = summary.get("total_pnl")
            base["total_trades"] = summary.get("total_trades")
            base["win_rate"] = summary.get("win_rate")

        elif self.report_type == "morning_briefing":
            base["readiness_score"] = self.report_data.get("readiness_score", {}).get("score")
            base["watch_out_count"] = len(self.report_data.get("watch_outs", []))

        elif self.report_type == "weekly_summary":
            this_week = self.report_data.get("this_week", {})
            base["total_pnl"] = this_week.get("total_pnl")
            base["win_rate"] = this_week.get("win_rate")

        return base

    def to_dict(self) -> dict:
        """Return full report including report_data."""
        return {
            "id": str(self.id),
            "broker_account_id": str(self.broker_account_id),
            "report_type": self.report_type,
            "report_date": self.report_date.isoformat(),
            "report_data": self.report_data,
            "generated_at": self.generated_at.isoformat(),
            "sent_via": self.sent_via,
        }
