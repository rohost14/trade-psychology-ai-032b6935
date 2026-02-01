from sqlalchemy import String, TIMESTAMP, text, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from cryptography.fernet import Fernet
import uuid
from datetime import datetime
from app.core.database import Base
from app.core.config import settings

class BrokerAccount(Base):
    __tablename__ = "broker_accounts"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    broker_name: Mapped[str] = mapped_column(String, default="zerodha")
    access_token: Mapped[str] = mapped_column(String, nullable=True) # Encrypted
    refresh_token: Mapped[str] = mapped_column(String, nullable=True) # Encrypted
    api_key: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String)
    connected_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_sync_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    broker_user_id: Mapped[str] = mapped_column(String, nullable=True)
    broker_email: Mapped[str] = mapped_column(String, nullable=True)
    guardian_phone: Mapped[str] = mapped_column(String, nullable=True)  # Risk guardian's phone number
    guardian_name: Mapped[str] = mapped_column(String, nullable=True)   # Guardian's name
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    @staticmethod
    def _get_fernet():
        return Fernet(settings.ENCRYPTION_KEY.encode())

    def encrypt_token(self, token: str) -> str:
        f = self._get_fernet()
        return f.encrypt(token.encode()).decode()

    def decrypt_token(self, encrypted_token: str) -> str:
        f = self._get_fernet()
        return f.decrypt(encrypted_token.encode()).decode()
    
    @classmethod
    async def get_by_user_id(cls, session: AsyncSession, user_id: uuid.UUID) -> "BrokerAccount | None":
        stmt = select(cls).where(cls.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalars().first()
