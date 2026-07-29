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

    # CDS (currency derivatives) included so its instrument tokens + lot sizes are
    # resolvable (needed for price subscriptions and position-sizing on USDINR etc.).
    SUPPORTED_EXCHANGES = ["NSE", "NFO", "BSE", "BFO", "MCX", "CDS"]

    # Rows per bulk-upsert statement — keeps each INSERT well under Postgres param limits.
    _UPSERT_BATCH = 1000

    async def refresh_instruments(
        self,
        db: AsyncSession,
        exchanges: Optional[List[str]] = None,
    ) -> Dict:
        """
        Download the Kite instrument master per exchange and persist it into the
        `instruments` table via bulk UPSERT (ON CONFLICT on instrument_token).

        The DB table is the source of truth for every reader (instrument_token
        lookups for price subscriptions, lot sizes for position-sizing alerts, option
        chains). This runs at most once per day, gated by the 23-hour staleness check
        in the trade-sync pipeline, so the one-time bulk write is not a hot path.
        """
        exchanges = exchanges or self.SUPPORTED_EXCHANGES
        now = datetime.now(timezone.utc)
        total = 0
        errors: List[str] = []

        for exchange in exchanges:
            try:
                instruments = await zerodha_client.get_instruments(exchange)
            except Exception as e:
                logger.error(f"Failed to fetch instruments for {exchange}: {e}")
                errors.append(f"{exchange}: {str(e)}")
                continue

            batch: List[Dict] = []
            for inst in instruments:
                token = inst.get("instrument_token")
                if token is None:
                    continue
                batch.append({
                    "instrument_token": int(token),
                    "exchange_token": inst.get("exchange_token"),
                    "tradingsymbol": inst.get("tradingsymbol"),
                    "name": inst.get("name"),
                    "last_price": inst.get("last_price") or None,
                    "expiry": self._parse_date(inst.get("expiry")),
                    "strike": inst.get("strike") or None,
                    "tick_size": inst.get("tick_size", 0.05),
                    "lot_size": inst.get("lot_size", 1) or 1,
                    "instrument_type": inst.get("instrument_type"),
                    "segment": inst.get("segment"),
                    "exchange": inst.get("exchange") or exchange,
                    "updated_at": now,
                })
                if len(batch) >= self._UPSERT_BATCH:
                    total += await self._safe_upsert(db, batch, exchange, errors)
                    batch = []

            if batch:
                total += await self._safe_upsert(db, batch, exchange, errors)

            logger.info(f"Upserted instruments for {exchange}")

        return {"total": total, "model": "DB upsert", "errors": errors}

    async def _safe_upsert(self, db, batch: List[Dict], exchange: str, errors: List[str]) -> int:
        """Upsert one batch in its OWN transaction. A failed batch is rolled back and
        SKIPPED with a SHORT log (never dump the 14k-param SQL — that floods the logs
        and blows Sentry's payload limit / your Redis budget), so the rest still load."""
        try:
            n = await self._upsert_batch(db, batch)
            await db.commit()
            return n
        except Exception as e:
            try:
                await db.rollback()
            except Exception:
                pass
            msg = f"{exchange}: instrument batch upsert failed ({type(e).__name__})"
            if msg not in errors:
                errors.append(msg)
            logger.warning(f"[instruments] {msg} — skipped {len(batch)} rows")
            return 0

    async def _upsert_batch(self, db: AsyncSession, rows: List[Dict]) -> int:
        """Bulk INSERT ... ON CONFLICT (instrument_token) DO UPDATE for one batch."""
        if not rows:
            return 0
        stmt = insert(Instrument).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["instrument_token"],
            set_={
                "exchange_token": stmt.excluded.exchange_token,
                "tradingsymbol": stmt.excluded.tradingsymbol,
                "name": stmt.excluded.name,
                "last_price": stmt.excluded.last_price,
                "expiry": stmt.excluded.expiry,
                "strike": stmt.excluded.strike,
                "tick_size": stmt.excluded.tick_size,
                "lot_size": stmt.excluded.lot_size,
                "instrument_type": stmt.excluded.instrument_type,
                "segment": stmt.excluded.segment,
                "exchange": stmt.excluded.exchange,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        await db.execute(stmt)
        return len(rows)

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
        return list(result.scalars().all())

    async def search_instruments(
        self,
        query: str,
        exchange: Optional[str] = None,
        limit: int = 20,
        db: Optional[AsyncSession] = None
    ) -> List[Instrument]:
        """Search instruments by symbol or name"""
        stmt = select(Instrument).where(
            Instrument.tradingsymbol.ilike(f"%{query}%")
        )

        if exchange:
            stmt = stmt.where(Instrument.exchange == exchange)

        stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

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
