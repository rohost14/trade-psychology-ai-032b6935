from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base
from datetime import datetime

class Notification(Base):
    __tablename__ = "notifications"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    message: Mapped[str]
    is_read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime]
