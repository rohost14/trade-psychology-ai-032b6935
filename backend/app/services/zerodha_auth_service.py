"""
Zerodha Auto-Login Service

Automates daily access_token refresh for the dedicated market-data Zerodha account
(ZERODHA_MD_* credentials in .env). Used exclusively by SharedPriceStream so the
shared KiteTicker never depends on any user's token.

Login flow (standard Kite Web flow — same steps a browser performs):
  1. POST /api/login          → request_id
  2. POST /api/twofa          → session cookie (2FA verified)
  3. GET  /connect/login      → redirect with request_token
  4. KiteConnect.generate_session() → access_token

This is the standard approach used by algo traders for daily token refresh.
Zerodha provides TOTP in their 2FA setup precisely to enable this automation.

Token stored in Redis: key = zerodha_md:access_token, TTL = 27 hours (covers the day
plus overnight; Zerodha invalidates old tokens when a new one is generated).
"""

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_KITE_BASE = "https://kite.zerodha.com"
_KITE_CONNECT = "https://kite.trade"
_TOKEN_REDIS_KEY = "zerodha_md:access_token"
_TOKEN_TTL_SECONDS = 27 * 3600  # 27 hours


def _generate_access_token(
    api_key: str,
    api_secret: str,
    user_id: str,
    password: str,
    totp_secret: str,
) -> str:
    """
    Full Zerodha login → TOTP → request_token → access_token.
    Returns access_token string. Raises on any failure.
    """
    import pyotp
    from urllib.parse import urlparse, parse_qs
    import hashlib

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "X-Kite-Version": "3",
    })

    # Step 1: Password login
    r = session.post(f"{_KITE_BASE}/api/login", data={
        "user_id": user_id,
        "password": password,
    }, timeout=15)
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "success":
        raise RuntimeError(f"Zerodha login failed: {body.get('message', body)}")
    request_id = body["data"]["request_id"]

    # Step 2: TOTP
    totp_value = pyotp.TOTP(totp_secret).now()
    r = session.post(f"{_KITE_BASE}/api/twofa", data={
        "user_id": user_id,
        "request_id": request_id,
        "twofa_value": totp_value,
        "twofa_type": "totp",
    }, timeout=15)
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "success":
        raise RuntimeError(f"Zerodha 2FA failed: {body.get('message', body)}")

    # Step 3: Kite Connect redirect → extract request_token
    r = session.get(
        f"{_KITE_CONNECT}/connect/login",
        params={"api_key": api_key, "v": "3"},
        allow_redirects=False,
        timeout=15,
    )
    location = r.headers.get("Location", "")
    if not location:
        raise RuntimeError("Zerodha Connect redirect did not return Location header.")
    params = parse_qs(urlparse(location).query)
    if "request_token" not in params:
        raise RuntimeError(f"No request_token in redirect: {location}")
    request_token = params["request_token"][0]

    # Step 4: Exchange request_token → access_token
    checksum = hashlib.sha256(
        f"{api_key}{request_token}{api_secret}".encode()
    ).hexdigest()
    r = requests.post(
        f"{_KITE_CONNECT}/session/token",
        data={
            "api_key": api_key,
            "request_token": request_token,
            "checksum": checksum,
        },
        headers={"X-Kite-Version": "3"},
        timeout=15,
    )
    r.raise_for_status()
    body = r.json()
    if body.get("status") != "success":
        raise RuntimeError(f"Token exchange failed: {body.get('message', body)}")

    return body["data"]["access_token"]


def refresh_market_data_token() -> Optional[str]:
    """
    Generate a fresh access_token for the market-data account and cache in Redis.
    Returns the new access_token, or None if credentials are not configured.

    Called by the daily Celery beat task at 8:45 AM IST Mon-Fri.
    Also callable manually: from app.services.zerodha_auth_service import refresh_market_data_token
    """
    from app.core.config import settings

    required = [
        settings.ZERODHA_MD_API_KEY,
        settings.ZERODHA_MD_API_SECRET,
        settings.ZERODHA_MD_USER_ID,
        settings.ZERODHA_MD_PASSWORD,
        settings.ZERODHA_MD_TOTP_SECRET,
    ]
    if not all(required):
        logger.info(
            "[md_auth] ZERODHA_MD_* credentials not fully configured — "
            "SharedPriceStream will use a connected user's token instead."
        )
        return None

    try:
        token = _generate_access_token(
            api_key=settings.ZERODHA_MD_API_KEY,
            api_secret=settings.ZERODHA_MD_API_SECRET,
            user_id=settings.ZERODHA_MD_USER_ID,
            password=settings.ZERODHA_MD_PASSWORD,
            totp_secret=settings.ZERODHA_MD_TOTP_SECRET,
        )

        from app.core.redis_pool import get_sync_redis
        r = get_sync_redis()
        r.set(_TOKEN_REDIS_KEY, token, ex=_TOKEN_TTL_SECONDS)
        logger.info("[md_auth] Market-data access_token refreshed and cached in Redis.")
        return token

    except Exception as e:
        logger.error(f"[md_auth] Token refresh failed: {e}")
        return None


def get_cached_market_data_token() -> Optional[str]:
    """
    Read the market-data access_token from Redis cache.
    Returns None if not set (credentials not configured, or token expired).
    """
    try:
        from app.core.redis_pool import get_sync_redis
        r = get_sync_redis()
        val = r.get(_TOKEN_REDIS_KEY)
        return val.decode() if val else None
    except Exception:
        return None
