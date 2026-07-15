"""
Market Data Token Refresh Task

Runs daily at 8:45 AM IST Mon-Fri to refresh the dedicated market-data
Zerodha account's access_token. SharedPriceStream picks this up automatically
when building/rebuilding the KiteTicker.

Zerodha access_tokens expire daily (~6 AM). Market opens at 9:15 AM.
8:45 AM gives a 30-minute window before market open to ensure the shared
KiteTicker is ready with a fresh token.

If the refresh fails, SharedPriceStream falls back to any connected user's
token (same behavior as when ZERODHA_MD_* credentials are not set).
"""

import logging
from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.market_data_tasks.refresh_market_data_token",
    max_retries=3,
    default_retry_delay=120,  # retry after 2 min if TOTP window missed
)
def refresh_market_data_token():
    """
    Refresh the shared KiteTicker access_token.
    Stores the new token in Redis (key: zerodha_md:access_token, TTL: 27h).
    """
    from app.services.zerodha_auth_service import refresh_market_data_token as _refresh

    try:
        token = _refresh()
        if token:
            logger.info("[market_data_task] Token refreshed successfully.")
        else:
            logger.info(
                "[market_data_task] No ZERODHA_MD_* credentials configured — "
                "skipping. SharedPriceStream uses user token fallback."
            )
    except Exception as exc:
        logger.error(f"[market_data_task] Refresh failed: {exc}")
        raise refresh_market_data_token.retry(exc=exc)
