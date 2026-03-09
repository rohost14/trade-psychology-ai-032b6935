"""
Instrument master management.
Downloads and caches Kite instruments for symbol lookups.
"""

from datetime import datetime, date, timezone
from typing import Optional, List, Dict
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert
import logging

from app.models.instrument import Instrument
from app.services.zerodha_service import zerodha_client, KiteAPIError

logger = logging.getLogger(__name__)


class InstrumentService:
    """
    Manages instrument master data.

    Kite provides CSV dump of all instruments.
    We cache this in DB for:
    1. instrument_token lookups (for WebSocket)
    2. Lot size information (for P&L calculation)
    3. Option strike/expiry mapping
    """

    SUPPORTED_EXCHANGES = ["NSE", "NFO", "BSE", "BFO", "MCX"]

    async def load_master_cache(self, exchanges: List[str] = None) -> Dict:
        """
        Download instrument master CSV and load into memory.
        Avoids daily SQL bulk insert (100k rows).
        """
        exchanges = exchanges or self.SUPPORTED_EXCHANGES
        count = 0
        errors = []

        # Initialize/Clear cache
        if not hasattr(self, "master_cache"):
            self.master_cache = {}

        for exchange in exchanges:
            try:
                instruments = await zerodha_client.get_instruments(exchange)
                
                for inst in instruments:
                    token = inst["instrument_token"]
                    self.master_cache[token] = {
                        "instrument_token": token,
                        "exchange_token": inst.get("exchange_token"),
                        "tradingsymbol": inst["tradingsymbol"],
                        "name": inst.get("name"),
                        "last_price": inst.get("last_price"),
                        "expiry": self._parse_date(inst.get("expiry")),
                        "strike": inst.get("strike"),
                        "tick_size": inst.get("tick_size", 0.05),
                        "lot_size": inst.get("lot_size", 1),
                        "instrument_type": inst.get("instrument_type"),
                        "segment": inst.get("segment"),
                        "exchange": inst.get("exchange"),
                        "updated_at": datetime.now(timezone.utc)
                    }
                    count += 1
                
                logger.info(f"Loaded {len(instruments)} instruments for {exchange} into memory")

            except Exception as e:
                logger.error(f"Failed to load instruments for {exchange}: {e}")
                errors.append(f"{exchange}: {str(e)}")

        return {"total": count, "model": "Lazy Memory Cache", "errors": errors}

    async def refresh_instruments(
        self,
        db: AsyncSession,
        exchanges: List[str] = None
    ) -> Dict:
        """
        DEPRECATED: Use load_master_cache() instead.
        Kept for backward compatibility to prevent crashes during migration.
        """
        logger.warning("refresh_instruments is deprecated. Switching to in-memory cache.")
        return await self.load_master_cache(exchanges)

    async def get_instrument(
        self,
        tradingsymbol: str,
        exchange: str,
        db: AsyncSession
    ) -> Optional[Instrument]:
        """Get instrument by symbol and exchange"""
        result = await db.execute(
            select(Instrument).where(
                Instrument.tradingsymbol == tradingsymbol,
                Instrument.exchange == exchange
            )
        )
        return result.scalar_one_or_none()

    async def get_instrument_by_token(
        self,
        instrument_token: int,
        db: AsyncSession
    ) -> Optional[Instrument]:
        """Get instrument by token"""
        result = await db.execute(
            select(Instrument).where(Instrument.instrument_token == instrument_token)
        )
        return result.scalar_one_or_none()

    async def get_lot_size(
        self,
        tradingsymbol: str,
        exchange: str,
        db: AsyncSession
    ) -> int:
        """Get lot size for an instrument (default 1 for equity)"""
        instrument = await self.get_instrument(tradingsymbol, exchange, db)
        return instrument.lot_size if instrument else 1

    async def get_option_chain(
        self,
        underlying: str,
        expiry: date,
        db: AsyncSession
    ) -> Dict[str, List[Instrument]]:
        """Get option chain for an underlying"""
        result = await db.execute(
            select(Instrument).where(
                Instrument.name == underlying,
                Instrument.expiry == expiry,
                Instrument.instrument_type.in_(["CE", "PE"])
            ).order_by(Instrument.strike)
        )
        instruments = result.scalars().all()

        chain = {"CE": [], "PE": []}
        for inst in instruments:
            if inst.instrument_type in chain:
                chain[inst.instrument_type].append(inst)

        return chain

    async def get_futures(
        self,
        underlying: str,
        db: AsyncSession
    ) -> List[Instrument]:
        """Get all futures contracts for an underlying"""
        result = await db.execute(
            select(Instrument).where(
                Instrument.name == underlying,
                Instrument.instrument_type == "FUT"
            ).order_by(Instrument.expiry)
        )
        return result.scalars().all()

    async def search_instruments(
        self,
        query: str,
        exchange: str = None,
        limit: int = 20,
        db: AsyncSession = None
    ) -> List[Instrument]:
        """Search instruments by symbol or name"""
        stmt = select(Instrument).where(
            Instrument.tradingsymbol.ilike(f"%{query}%")
        )

        if exchange:
            stmt = stmt.where(Instrument.exchange == exchange)

        stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def cleanup_expired(self, db: AsyncSession) -> int:
        """Remove expired F&O instruments"""
        today = date.today()
        result = await db.execute(
            delete(Instrument).where(
                Instrument.expiry < today,
                Instrument.expiry.isnot(None)
            )
        )
        await db.commit()
        return result.rowcount

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string from Kite"""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None


# Singleton instance
instrument_service = InstrumentService()
