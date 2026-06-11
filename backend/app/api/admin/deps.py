"""
Admin JWT dependency — used on every /api/admin/* endpoint.
Returns 404 (not 403) on failure so the endpoint appears to not exist.
"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)

BLOCKLIST_PREFIX = "admin_jti_block:"


def _get_secret() -> str:
    secret = settings.ADMIN_JWT_SECRET
    if not secret:
        raise HTTPException(status_code=404)
    return secret


def _is_blocklisted(jti: str) -> bool:
    """Return True if this JWT has been invalidated (logged out)."""
    try:
        import redis as redis_lib
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1)
        result = r.exists(f"{BLOCKLIST_PREFIX}{jti}")
        r.close()
        return bool(result)
    except Exception as e:
        logger.warning(f"Blocklist check failed (failing open): {e}")
        return False  # Redis unavailable — fail open (don't lock out admin)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """
    Validate admin JWT. Returns payload dict with {admin_id, email, name}.
    Raises 404 on any failure — admin routes appear to not exist for non-admins.
    Checks Redis blocklist so logged-out tokens are rejected server-side.
    """
    if credentials is None:
        raise HTTPException(status_code=404)
    try:
        payload = jwt.decode(
            credentials.credentials,
            _get_secret(),
            algorithms=["HS256"],
        )
        admin_id = payload.get("sub")
        if not admin_id:
            raise HTTPException(status_code=404)
        jti = payload.get("jti")
        if jti and _is_blocklisted(jti):
            raise HTTPException(status_code=404)
        return payload
    except JWTError:
        raise HTTPException(status_code=404)
