"""
Admin JWT dependency — used on every /api/admin/* endpoint.
Returns 404 (not 403) on failure so the endpoint appears to not exist.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from app.core.config import settings

_bearer = HTTPBearer(auto_error=False)


def _get_secret() -> str:
    secret = settings.ADMIN_JWT_SECRET
    if not secret:
        raise HTTPException(status_code=404)
    return secret


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """
    Validate admin JWT. Returns payload dict with {admin_id, email, name}.
    Raises 404 on any failure — admin routes appear to not exist for non-admins.
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
        return payload
    except JWTError:
        raise HTTPException(status_code=404)
