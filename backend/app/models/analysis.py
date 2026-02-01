from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base
from datetime import datetime

class Analysis(Base):
    __tablename__ = "analyses"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    trade_id: Mapped[int]
    ai_feedback: Mapped[str]
    score: Mapped[float]
    created_at: Mapped[datetime]
