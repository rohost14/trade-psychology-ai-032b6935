from sqlalchemy.orm import Mapped, mapped_column
from backend.app.core.database import Base
from datetime import datetime

class MarketData(Base):
    __tablename__ = "market_data"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str]
    price: Mapped[float]
    timestamp: Mapped[datetime]
