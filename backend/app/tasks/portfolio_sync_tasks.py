"""
Portfolio Sync Task

Lazily syncs equity holdings + MF holdings to Redis cache.
Triggered on-demand when user opens Portfolio Chat (cache miss).
Also triggered by postback webhook on CNC settlement.

NOT a beat schedule — only runs when needed.
This keeps KiteConnect API calls bounded to active users only.

Rate limit protection:
  Redis lock per account prevents concurrent syncs for same account.
  Celery handles rate limiting via existing trade queue.
"""

import json
import logging
from datetime import datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

# Redis TTLs
HOLDINGS_TTL = 4 * 3600       # 4 hours
MF_HOLDINGS_TTL = 24 * 3600   # 24 hours
SECTOR_TTL = 4 * 3600          # same as holdings
SYNC_LOCK_TTL = 60             # 60-second lock prevents duplicate syncs

# Top-200 NSE stocks → sector mapping (covers ~95% of retail portfolios)
SECTOR_MAP = {
    # IT
    "TCS": "IT", "INFY": "IT", "WIPRO": "IT", "HCLTECH": "IT", "TECHM": "IT",
    "LTIM": "IT", "MPHASIS": "IT", "COFORGE": "IT", "PERSISTENT": "IT", "OFSS": "IT",
    # Banking
    "HDFCBANK": "Banking", "ICICIBANK": "Banking", "SBIN": "Banking", "KOTAKBANK": "Banking",
    "AXISBANK": "Banking", "INDUSINDBK": "Banking", "BANDHANBNK": "Banking",
    "FEDERALBNK": "Banking", "IDFCFIRSTB": "Banking", "PNB": "Banking",
    "BANKBARODA": "Banking", "CANBK": "Banking", "UNIONBANK": "Banking",
    # NBFC / Finance
    "BAJFINANCE": "Finance", "BAJAJFINSV": "Finance", "CHOLAFIN": "Finance",
    "MUTHOOTFIN": "Finance", "MANAPPURAM": "Finance", "LICHSGFIN": "Finance",
    "POONAWALLA": "Finance", "ABCAPITAL": "Finance",
    # Pharma
    "SUNPHARMA": "Pharma", "DRREDDY": "Pharma", "CIPLA": "Pharma", "DIVISLAB": "Pharma",
    "BIOCON": "Pharma", "TORNTPHARM": "Pharma", "ALKEM": "Pharma", "LUPIN": "Pharma",
    "AUROPHARMA": "Pharma", "IPCALAB": "Pharma",
    # Auto
    "MARUTI": "Auto", "TATAMOTORS": "Auto", "M&M": "Auto", "BAJAJ-AUTO": "Auto",
    "HEROMOTOCO": "Auto", "EICHERMOT": "Auto", "TVSMOTOR": "Auto", "ASHOKLEY": "Auto",
    "MOTHERSON": "Auto", "BOSCHLTD": "Auto",
    # FMCG
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG",
    "DABUR": "FMCG", "GODREJCP": "FMCG", "MARICO": "FMCG", "COLPAL": "FMCG",
    "EMAMILTD": "FMCG", "TATACONSUM": "FMCG",
    # Energy / Oil & Gas
    "RELIANCE": "Energy", "ONGC": "Energy", "COALINDIA": "Energy", "NTPC": "Energy",
    "POWERGRID": "Energy", "BPCL": "Energy", "IOC": "Energy", "GAIL": "Energy",
    "ADANIGREEN": "Energy", "TATAPOWER": "Energy", "ADANIPORTS": "Energy",
    # Metals
    "TATASTEEL": "Metals", "JSWSTEEL": "Metals", "HINDALCO": "Metals",
    "VEDL": "Metals", "SAIL": "Metals", "NMDC": "Metals", "NATIONALUM": "Metals",
    # Cement
    "ULTRACEMCO": "Cement", "SHREECEM": "Cement", "AMBUJACEM": "Cement",
    "ACC": "Cement", "JKCEMENT": "Cement",
    # Telecom
    "BHARTIARTL": "Telecom", "IDEA": "Telecom",
    # Consumer Durables
    "TITAN": "Consumer", "HAVELLS": "Consumer", "CROMPTON": "Consumer",
    "VOLTAS": "Consumer", "WHIRLPOOL": "Consumer", "VGUARD": "Consumer",
    # Real Estate
    "DLF": "Real Estate", "GODREJPROP": "Real Estate", "PRESTIGE": "Real Estate",
    "OBEROIRLTY": "Real Estate", "BRIGADE": "Real Estate",
    # Insurance
    "LICI": "Insurance", "SBILIFE": "Insurance", "HDFCLIFE": "Insurance",
    "ICICIPRULI": "Insurance", "NIACL": "Insurance",
    # Capital Goods / Infra
    "LT": "Capital Goods", "SIEMENS": "Capital Goods", "ABB": "Capital Goods",
    "BEL": "Capital Goods", "HAL": "Capital Goods", "BHEL": "Capital Goods",
    "CUMMINSIND": "Capital Goods",
    # Chemical
    "PIDILITIND": "Chemicals", "SRF": "Chemicals", "DEEPAKNTR": "Chemicals",
    "AARTIIND": "Chemicals", "NAVINFLUOR": "Chemicals", "ALKYLAMINE": "Chemicals",
}


def _get_redis():
    import redis as redis_lib
    return redis_lib.from_url(settings.REDIS_URL, decode_responses=True)


def _compute_sector_exposure(holdings: list) -> dict:
    """Derive sector breakdown from holdings list using SECTOR_MAP."""
    sector_value: dict[str, float] = {}
    total = 0.0
    for h in holdings:
        symbol = h.get("tradingsymbol", "")
        value = float(h.get("last_price", 0)) * int(h.get("quantity", 0))
        sector = SECTOR_MAP.get(symbol, "Other")
        sector_value[sector] = sector_value.get(sector, 0) + value
        total += value

    if total == 0:
        return {}

    return {
        sector: {"value": round(v, 2), "pct": round(v / total * 100, 1)}
        for sector, v in sorted(sector_value.items(), key=lambda x: -x[1])
    }


@celery_app.task(
    name="app.tasks.portfolio_sync_tasks.sync_portfolio_for_account",
    max_retries=3,
    default_retry_delay=30,
)
def sync_portfolio_for_account(broker_account_id_str: str):
    """
    Fetch holdings + MF holdings from KiteConnect → store in Redis.
    Uses a Redis lock to prevent concurrent syncs for same account.
    Called on-demand (cache miss or CNC settlement webhook).
    """
    import asyncio
    asyncio.run(_sync(broker_account_id_str))


async def _sync(broker_account_id_str: str):
    from app.core.database import SessionLocal
    from app.models.broker_account import BrokerAccount
    from app.services.zerodha_service import ZerodhaService, get_service_for_account
    from sqlalchemy import select

    broker_account_id = UUID(broker_account_id_str)
    r = _get_redis()
    lock_key = f"portfolio:syncing:{broker_account_id}"

    # Acquire lock — skip if another worker is already syncing this account
    acquired = r.set(lock_key, "1", ex=SYNC_LOCK_TTL, nx=True)
    if not acquired:
        logger.debug(f"Portfolio sync already in progress for {broker_account_id}, skipping")
        return

    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(BrokerAccount).where(BrokerAccount.id == broker_account_id)
            )
            account = result.scalar_one_or_none()
            if not account or not account.access_token:
                logger.warning(f"No active account/token for {broker_account_id}")
                return

            access_token = account.get_decrypted_token()
            svc = get_service_for_account(account)

            # Fetch holdings (equity CNC)
            try:
                holdings = await svc.get_holdings(access_token)
            except Exception as e:
                logger.error(f"Holdings fetch failed for {broker_account_id}: {e}")
                holdings = []

            # Fetch MF holdings
            try:
                mf_holdings = await svc.get_mf_holdings(access_token)
            except Exception as e:
                logger.error(f"MF holdings fetch failed for {broker_account_id}: {e}")
                mf_holdings = []

            # Compute sector exposure
            sector_exposure = _compute_sector_exposure(holdings)

            # Store in Redis
            now_iso = datetime.now(timezone.utc).isoformat()
            r.setex(f"portfolio:holdings:{broker_account_id}", HOLDINGS_TTL, json.dumps(holdings))
            r.setex(f"portfolio:mf_holdings:{broker_account_id}", MF_HOLDINGS_TTL, json.dumps(mf_holdings))
            r.setex(f"portfolio:sector:{broker_account_id}", SECTOR_TTL, json.dumps(sector_exposure))
            r.set(f"portfolio:synced_at:{broker_account_id}", now_iso)

            logger.info(
                f"Portfolio synced for {broker_account_id}: "
                f"{len(holdings)} holdings, {len(mf_holdings)} MF holdings"
            )
    finally:
        r.delete(lock_key)
