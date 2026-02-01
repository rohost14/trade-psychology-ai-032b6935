from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base

class Settings(Base):
    __tablename__ = "settings"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int]
    theme: Mapped[str] = mapped_column(default="dark")
    notifications_enabled: Mapped[bool] = mapped_column(default=True)
