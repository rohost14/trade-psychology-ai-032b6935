from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base
from datetime import datetime

class Journal(Base):
    __tablename__ = "journals"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    content: Mapped[str]
    created_at: Mapped[datetime]
