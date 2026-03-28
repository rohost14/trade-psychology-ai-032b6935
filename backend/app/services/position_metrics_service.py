"""
Position Metrics Service

Calculates systematic option/futures metrics for all open F&O positions.
Pure math — no AI, no guesses. All values derived from:
  - positions table (entry price, quantity, instrument_token)
  - instruments table (strike, expiry, lot_size, instrument_type)
  - Redis LTP cache (current price via KiteTicker)

Called by:
  - portfolio_radar_tasks.py (every 5 min during market hours)
  - portfolio_radar API endpoint (on-demand)
"""

import logging
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Instrument types that are option contracts
_OPTION_TYPES = {"CE", "PE"}
_FNO_EXCHANGES = {"NFO", "BFO", "MCX"}

# Regex to extract underlying name from NFO tradingsymbol.
# e.g. NIFTY24JAN22500CE  → NIFTY
#      BANKNIFTY24FEB50000PE → BANKNIFTY
#      RELIANCE24MAR1500CE  → RELIANCE
# Pattern: one or more uppercase letters at the start, followed by 2 digits (year)
_UNDERLYING_RE = re.compile(r"^([A-Z&]+)\d{2}[A-Z]{3}")


def _extract_underlying(tradingsymbol: str) -> Optional[str]:
    """Extract base symbol from NFO option/future tradingsymbol."""
    m = _UNDERLYING_RE.match(tradingsymbol)
    return m.group(1) if m else None


def _days_to_expiry(expiry: date) -> int:
    today = date.today()
    return max(0, (expiry - today).days)


def _calc_breakeven(
    instrument_type: str,
    strike: float,
    entry_price: float,
) -> Optional[float]:
    """
    Breakeven price for the option buyer.
    CE buyer: underlying must reach strike + premium_paid to break even.
    PE buyer: underlying must fall to strike - premium_paid to break even.
    """
    if instrument_type == "CE":
        return round(strike + entry_price, 2)
    if instrument_type == "PE":
        return round(strike - entry_price, 2)
    return None  # FUT — no strike-based breakeven


def _calc_breakeven_gap(
    instrument_type: str,
    breakeven: float,
    underlying_ltp: Optional[float],
) -> Optional[float]:
    """
    Distance the underlying still needs to move for the option to break even.
    Positive = already past breakeven (in profit zone).
    Negative = needs to move this far more.
    Returns None if no underlying price available.
    """
    if underlying_ltp is None or breakeven is None:
        return None
    if instrument_type == "CE":
        return round(underlying_ltp - breakeven, 2)
    if instrument_type == "PE":
        return round(breakeven - underlying_ltp, 2)
    return None


def _calc_premium_decay_pct(entry_price: float, current_ltp: float) -> Optional[float]:
    """
    How much of the entry premium has decayed.
    Positive = premium has shrunk (option worth less than entry).
    Only meaningful when buying options (long position).
    """
    if entry_price <= 0:
        return None
    return round((entry_price - current_ltp) / entry_price * 100, 1)


def _calc_capital_at_risk(current_ltp: float, lot_size: int, quantity: int) -> float:
    """Current market value of the open position (absolute)."""
    return round(abs(current_ltp * lot_size * quantity), 2)


class PositionMetricsService:
    """
    Computes structured metrics for a set of open F&O positions.

    Usage:
        svc = PositionMetricsService()
        metrics = await svc.compute_all(broker_account_id, db)
    """

    async def compute_all(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
    ) -> List[Dict]:
        """
        Return metrics for all open F&O positions of an account.
        Positions with no instrument data or no LTP are included but with
        partial metrics (None for missing fields).
        """
        from app.models.position import Position
        from app.models.instrument import Instrument
        from app.services.price_stream_service import get_cached_ltp

        # Load open F&O positions
        result = await db.execute(
            select(Position).where(
                and_(
                    Position.broker_account_id == broker_account_id,
                    Position.total_quantity != 0,
                    Position.exchange.in_(list(_FNO_EXCHANGES)),
                )
            )
        )
        positions = result.scalars().all()
        if not positions:
            return []

        # Batch-load instrument data for all tradingsymbols
        symbols = [p.tradingsymbol for p in positions]
        inst_result = await db.execute(
            select(Instrument).where(
                and_(
                    Instrument.tradingsymbol.in_(symbols),
                    Instrument.exchange.in_(list(_FNO_EXCHANGES)),
                )
            )
        )
        instruments_by_symbol: Dict[str, Instrument] = {
            i.tradingsymbol: i for i in inst_result.scalars().all()
        }

        # Also load underlying instrument tokens for breakeven_gap calculation.
        # E.g. for NIFTY options, we need the spot NIFTY or NIFTY FUT LTP.
        underlyings_needed = set()
        for pos in positions:
            u = _extract_underlying(pos.tradingsymbol)
            if u:
                underlyings_needed.add(u)

        underlying_tokens: Dict[str, Optional[int]] = {}
        if underlyings_needed:
            und_result = await db.execute(
                select(Instrument).where(
                    and_(
                        Instrument.name.in_(list(underlyings_needed)),
                        Instrument.instrument_type == "EQ",  # NSE spot
                    )
                )
            )
            for inst in und_result.scalars().all():
                underlying_tokens[inst.name] = inst.instrument_token

        metrics = []
        for pos in positions:
            inst = instruments_by_symbol.get(pos.tradingsymbol)
            itype = (inst.instrument_type if inst else None) or pos.instrument_type or ""

            # LTP from Redis cache
            token = pos.instrument_token or (inst.instrument_token if inst else None)
            current_ltp: Optional[float] = get_cached_ltp(token) if token else None

            # Underlying LTP for breakeven_gap
            underlying_name = _extract_underlying(pos.tradingsymbol)
            underlying_ltp: Optional[float] = None
            if underlying_name:
                u_token = underlying_tokens.get(underlying_name)
                if u_token:
                    underlying_ltp = get_cached_ltp(u_token)

            entry_price = float(pos.average_entry_price or 0)
            lot_size = inst.lot_size if inst else 1
            quantity = pos.total_quantity or 0

            strike = float(inst.strike or 0) if inst else None
            expiry = inst.expiry if inst else None

            breakeven = None
            breakeven_gap = None
            premium_decay_pct = None
            capital_at_risk = None
            days_to_expiry = None

            if itype in _OPTION_TYPES and strike:
                breakeven = _calc_breakeven(itype, strike, entry_price)
                if breakeven and underlying_ltp is not None:
                    breakeven_gap = _calc_breakeven_gap(itype, breakeven, underlying_ltp)

            if itype in _OPTION_TYPES and current_ltp is not None and quantity > 0:
                # Long options only — decay is relevant for buyers
                premium_decay_pct = _calc_premium_decay_pct(entry_price, current_ltp)

            if current_ltp is not None:
                capital_at_risk = _calc_capital_at_risk(current_ltp, lot_size, quantity)

            if expiry:
                days_to_expiry = _days_to_expiry(expiry)

            metrics.append({
                "position_id": str(pos.id),
                "tradingsymbol": pos.tradingsymbol,
                "exchange": pos.exchange,
                "instrument_type": itype,
                "quantity": quantity,
                "lot_size": lot_size,
                "entry_price": entry_price,
                "current_ltp": current_ltp,
                "underlying_name": underlying_name,
                "underlying_ltp": underlying_ltp,
                "strike": strike,
                "expiry": expiry.isoformat() if expiry else None,
                "days_to_expiry": days_to_expiry,
                "breakeven": breakeven,
                "breakeven_gap": breakeven_gap,
                "premium_decay_pct": premium_decay_pct,
                "capital_at_risk": capital_at_risk,
                "unrealized_pnl": float(pos.unrealized_pnl or 0),
            })

        return metrics


position_metrics_service = PositionMetricsService()
