"""
Admin JWT dependency — used on every /api/admin/* endpoint.
Returns 404 (not 403) on failure so the endpoint appears to not exist.
"""
import ipaddress
import logging
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from app.core.config import settings
import redis as redis_lib

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)

BLOCKLIST_PREFIX = "admin_jti_block:"

# Module-level Redis connection — reused across requests, not created per-call
_redis_conn: redis_lib.Redis | None = None


def _get_blocklist_redis() -> redis_lib.Redis:
    global _redis_conn
    if _redis_conn is None:
        _redis_conn = redis_lib.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    return _redis_conn


def _get_secret() -> str:
    secret = settings.ADMIN_JWT_SECRET
    if not secret:
        raise HTTPException(status_code=404)
    return secret


def _is_blocklisted(jti: str) -> bool:
    """Return True if this JWT has been revoked. Fails CLOSED — blocks on Redis error."""
    try:
        r = _get_blocklist_redis()
        return bool(r.exists(f"{BLOCKLIST_PREFIX}{jti}"))
    except Exception as e:
        logger.error(f"Admin blocklist check failed (failing CLOSED — token rejected): {e}")
        return True  # Fail closed: Redis down → treat all tokens as revoked


# ── IP Allowlist ──────────────────────────────────────────────────────────────

def _parse_allowlist() -> list[str]:
    raw = (settings.ADMIN_IP_ALLOWLIST or "").strip()
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


def _get_client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "0.0.0.0"


def _check_ip(request: Request) -> None:
    """Raise 404 if caller IP is not in ADMIN_IP_ALLOWLIST. No-op when list is empty (dev mode)."""
    allowlist = _parse_allowlist()
    if not allowlist:
        return
    client_ip = _get_client_ip(request)
    for entry in allowlist:
        try:
            if ipaddress.ip_address(client_ip) in ipaddress.ip_network(entry, strict=False):
                return
        except ValueError:
            if client_ip == entry:
                return
    logger.warning(f"Admin access denied — IP not in allowlist: {client_ip}")
    raise HTTPException(status_code=404)


# ── Auth dependency ───────────────────────────────────────────────────────────

async def get_current_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """
    Validate admin JWT. Returns payload dict with {sub, email, name, role}.
    Raises 404 on any failure — admin routes appear to not exist for non-admins.
    Checks IP allowlist (ADMIN_IP_ALLOWLIST) and Redis blocklist for revoked tokens.
    """
    _check_ip(request)
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


# ── Role-based access ─────────────────────────────────────────────────────────

def require_role(*roles: str):
    """
    Dependency factory: require admin JWT + one of the specified roles.

    Roles: superadmin | ops | support
      superadmin — full access
      ops        — can broadcast, trigger tasks, suspend; cannot delete/erase
      support    — read-only + per-user send message

    Usage:
        admin: dict = Depends(require_role("superadmin"))
        admin: dict = Depends(require_role("superadmin", "ops"))
    """
    async def _check(payload: dict = Depends(get_current_admin)) -> dict:
        if payload.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return payload
    return _check
