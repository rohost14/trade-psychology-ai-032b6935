"""
Authentication dependencies for FastAPI endpoints.

JWT structure (after migration 032):
  sub  = user_id         (stable identity — survives broker reconnects)
  bid  = broker_account_id  (which broker session is active)

Issued at Zerodha OAuth callback, validated on every protected endpoint.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
import logging

logger = logging.getLogger(__name__)

# OAuth2 scheme - tokenUrl is informational only (for Swagger UI docs)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/zerodha/connect", auto_error=True)


def create_access_token(
    user_id: UUID,
    broker_account_id: UUID,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT.
      sub = user_id           — stable identity (users table)
      bid = broker_account_id — active broker session
    Default expiry: 24 hours (matches Zerodha token daily lifecycle).
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=24)
    )
    payload = {
        "sub": str(user_id),
        "bid": str(broker_account_id),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_user_id(
    token: Annotated[str, Depends(oauth2_scheme)]
) -> UUID:
    """Extract user_id from JWT sub claim."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        sub: Optional[str] = payload.get("sub")
        if sub is None:
            raise credentials_exception
        return UUID(sub)
    except (JWTError, ValueError):
        raise credentials_exception


async def get_current_broker_account_id(
    token: Annotated[str, Depends(oauth2_scheme)]
) -> UUID:
    """
    Core auth dependency for all protected endpoints.
    Extracts broker_account_id from the JWT 'bid' claim.
    Raises 401 if token is missing, expired, or invalid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        bid: Optional[str] = payload.get("bid")
        if bid is None:
            raise credentials_exception
        return UUID(bid)
    except (JWTError, ValueError):
        raise credentials_exception


async def get_verified_broker_account_id(
    broker_account_id: UUID = Depends(get_current_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> UUID:
    """
    Strict auth dependency that verifies the broker account is still active.

    Use this instead of get_current_broker_account_id for sensitive operations
    (sync, disconnect, write operations). It checks:
    1. JWT is valid (via get_current_broker_account_id)
    2. Account still exists in DB
    3. Token has not been revoked (prevents use of old JWTs after disconnect)

    Adds one lightweight DB query per request.
    """
    from app.models.broker_account import BrokerAccount

    result = await db.execute(
        select(BrokerAccount).where(BrokerAccount.id == broker_account_id)
    )
    account = result.scalars().first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Broker account not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if account.token_revoked_at:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked — please reconnect",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return broker_account_id


async def get_current_user_ws(token: str) -> Optional[UUID]:
    """
    Validate JWT for WebSocket connections.
    Returns broker_account_id or None if invalid.

    WebSocket connections pass token as query param since headers are harder.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        bid: Optional[str] = payload.get("bid")
        if bid:
            return UUID(bid)
        return None
    except (JWTError, ValueError):
        logger.warning("WebSocket token validation failed")
        return None
