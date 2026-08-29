"""
Capture and resolve BROKER margin for live positions.

WHY THIS EXISTS
---------------
F17 made capital-relative detectors abstain when capital is unknown, which is
correct but leaves futures and short-option positions unjudged. The only way to
know what those actually required is to ask the broker, and the only moment we
can ask is while the position is live.

    Kite's postback carries NO margin field of any kind - verified against the
    documented payload. And `/margins/orders` is PROSPECTIVE only: no endpoint
    returns the margin of a position that is already closed. So a margin figure
    either gets captured while the position exists or it never exists at all.

WHAT IS CAPTURED
----------------
The whole open structure on one underlying, through `/margins/basket`, not each
leg on its own. Margin is a property of the structure: measured on a real
account, a NIFTY call spread cost 64,174 against 175,747 for its short leg
alone. Charging legs independently overstates committed capital threefold.

WHEN
----
On a fill that OPENS or INCREASES a position, and not otherwise. No polling, no
per-tick calls, nothing on exits - a shrinking position does not need a fresh
observation, and the figure that matters for "how much did this trade commit"
was set when it went on. One call per position-opening fill sits comfortably
inside the 3 req/s REST budget.

IMMUTABILITY
------------
Observations are append-only. A COMPUTED estimate never overwrites a BROKER
observation, and a stored observation is never recomputed later against today's
market data.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import and_, desc, select

logger = logging.getLogger(__name__)

#: Products whose positions carry a margin obligation worth capturing. A CNC
#: delivery buy is paid in full and is not tracked by this platform anyway.
_MARGIN_PRODUCTS = {"MIS", "NRML", "MTF"}

#: Fill classifications that establish or grow a position.
_CAPTURE_ON = {"OPEN", "INCREASE", "FLIP"}

#: None = not yet probed, False = migration 081 is not applied on this database.
#: Memoised per process. Without it, every lookup would issue a query that fails
#: and - worse - a failed statement ABORTS the surrounding transaction, so every
#: later query in the same session dies with "current transaction is aborted".
#: A read that is allowed to fail must never be able to poison its caller.
_TABLE_AVAILABLE: Optional[bool] = None


def should_capture(entry_type: Optional[str], product: Optional[str]) -> bool:
    """The whole lifecycle policy, in one testable place."""
    return ((entry_type or "").upper() in _CAPTURE_ON
            and (product or "").upper() in _MARGIN_PRODUCTS)


def _leg_payload(pos) -> dict:
    """
    One open position rendered as a Kite margin-API order.

    `transaction_type` is the direction needed to HOLD the position, which is
    what it was established with - a long leg is a BUY. Quantity is absolute
    because direction is carried separately.
    """
    qty = int(pos.total_quantity or 0)
    return {
        "exchange": pos.exchange,
        "tradingsymbol": pos.tradingsymbol,
        "transaction_type": "BUY" if qty > 0 else "SELL",
        "variety": "regular",
        "product": pos.product or "NRML",
        "order_type": "MARKET",
        "quantity": abs(qty),
        "price": 0,
        "trigger_price": 0,
    }


async def capture_for_underlying(
    broker_account_id: UUID,
    underlying: str,
    db,
    account,
    access_token: str,
) -> Optional[dict]:
    """
    Ask the broker what the currently-open structure on `underlying` requires,
    and persist the answer.

    Returns the stored figures, or None when there is nothing to ask about or
    the call could not be made. Never raises into the caller: a failed capture
    must degrade to "no observation", which makes the risk layer abstain — it
    must never break the fill pipeline.
    """
    from app.models.position import Position
    from app.services.instrument_parser import parse_symbol
    from app.services.zerodha_service import get_service_for_account

    try:
        rows = (await db.execute(
            select(Position).where(and_(
                Position.broker_account_id == broker_account_id,
                Position.total_quantity != 0,
            ))
        )).scalars().all()
    except Exception as exc:                                   # noqa: BLE001
        logger.warning("margin capture: cannot read positions: %s", exc)
        return None

    legs_pos = []
    for p in rows:
        if (p.product or "").upper() not in _MARGIN_PRODUCTS:
            continue
        try:
            u = parse_symbol(p.tradingsymbol or "").underlying or p.tradingsymbol
        except Exception:                                      # noqa: BLE001
            u = p.tradingsymbol
        if u == underlying:
            legs_pos.append(p)

    if not legs_pos:
        return None

    payload = [_leg_payload(p) for p in legs_pos]

    try:
        svc = get_service_for_account(account)
        # basket, not orders: spread benefit is applied across the legs, which
        # is what the account actually has blocked.
        resp = await svc.get_order_margins(
            access_token, payload, mode="basket",
            broker_account_id=broker_account_id,
        )
    except Exception as exc:                                   # noqa: BLE001
        logger.warning("margin capture failed for %s/%s: %s",
                       broker_account_id, underlying, exc)
        return None

    figures = _read_basket_response(resp, payload)
    if figures is None or not figures.get("total"):
        logger.debug("margin capture: unusable response for %s", underlying)
        return None

    stored = await _persist(
        db, broker_account_id, underlying, legs_pos, payload, figures)
    return stored


def _read_basket_response(resp: Any, payload: list[dict]) -> Optional[dict]:
    """
    Normalise Kite's basket answer.

    `final` is the one to keep: it has spread benefit applied and is therefore
    what the account actually has blocked. `initial` charges the legs
    independently and would overstate a hedged structure.
    """
    if isinstance(resp, list):                    # /margins/orders shape
        legs = resp
        agg = {k: sum(float(o.get(k) or 0) for o in legs)
               for k in ("span", "exposure", "option_premium", "additional", "total")}
    elif isinstance(resp, dict):
        final = resp.get("final") or {}
        legs = resp.get("orders") or []
        if not final:
            return None
        agg = {k: float(final.get(k) or 0)
               for k in ("span", "exposure", "option_premium", "additional", "total")}
    else:
        return None

    per_leg = {}
    for order, sent in zip(legs, payload):
        sym = (order.get("tradingsymbol") if isinstance(order, dict) else None) \
            or sent.get("tradingsymbol")
        if sym:
            per_leg[sym] = float((order or {}).get("total") or 0)

    agg["per_leg"] = per_leg
    return agg


async def _persist(db, broker_account_id, underlying, legs_pos, payload, figures):
    from app.models.position_margin_observation import PositionMarginObservation

    obs = PositionMarginObservation(
        broker_account_id=broker_account_id,
        captured_at=datetime.now(timezone.utc),
        exchange=legs_pos[0].exchange,
        underlying=underlying,
        product=legs_pos[0].product,
        leg_count=len(payload),
        legs=payload,
        span=figures.get("span"),
        exposure=figures.get("exposure"),
        option_premium=figures.get("option_premium"),
        additional=figures.get("additional"),
        total=figures.get("total"),
        per_leg=figures.get("per_leg") or {},
        basis="basket",
        margin_source="broker",
    )
    global _TABLE_AVAILABLE
    if _TABLE_AVAILABLE is False:
        return None
    try:
        # Savepoint again: a write into a missing table must not abort the fill
        # pipeline's transaction. Capturing margin is strictly additive - if it
        # cannot happen, the trade still records correctly.
        async with db.begin_nested():
            db.add(obs)
            await db.flush()
        _TABLE_AVAILABLE = True
    except Exception as exc:                                   # noqa: BLE001
        if "position_margin_observations" in str(exc):
            _TABLE_AVAILABLE = False
        logger.warning("margin observation not stored (migration 081 applied?): %s", exc)
        return None

    logger.info("captured BROKER margin %s for %s (%d leg(s))",
                figures.get("total"), underlying, len(payload))
    return figures


# ---------------------------------------------------------------------------
# Resolution — what the risk layer asks for
# ---------------------------------------------------------------------------

async def resolve_for_trade(trade, db) -> Optional["object"]:
    """
    The BROKER margin for one completed trade, or None.

    Matches on account and underlying, taking the latest observation captured
    at or before the trade closed. Later observations are ignored: they belong
    to a position this trade is no longer part of.

    Returns a `Capital` tagged BROKER, or None so the caller can fall through
    to COMPUTED or to an abstention. Never raises — a missing table, a missing
    observation and a failed query are all "no broker figure".
    """
    from app.core.risk_quantities import Capital, MarginSource
    from app.models.position_margin_observation import PositionMarginObservation
    from app.services.instrument_parser import parse_symbol

    symbol = getattr(trade, "tradingsymbol", None)
    account_id = getattr(trade, "broker_account_id", None)
    if not symbol or not account_id:
        return None
    try:
        underlying = parse_symbol(symbol).underlying or symbol
    except Exception:                                          # noqa: BLE001
        underlying = symbol

    global _TABLE_AVAILABLE
    if _TABLE_AVAILABLE is False:
        return None

    cutoff = getattr(trade, "exit_time", None) or getattr(trade, "entry_time", None)

    stmt = select(PositionMarginObservation).where(and_(
        PositionMarginObservation.broker_account_id == account_id,
        PositionMarginObservation.underlying == underlying,
    ))
    if cutoff is not None:
        stmt = stmt.where(PositionMarginObservation.captured_at <= cutoff)
    stmt = stmt.order_by(desc(PositionMarginObservation.captured_at)).limit(1)

    try:
        # Savepoint. A failure here rolls back only this read, leaving the
        # caller's transaction usable - the engine runs several more queries
        # after this one and none of them may inherit an aborted transaction.
        async with db.begin_nested():
            obs = (await db.execute(stmt)).scalars().first()
        _TABLE_AVAILABLE = True
    except Exception as exc:                                   # noqa: BLE001
        if "position_margin_observations" in str(exc):
            # Migration 081 not applied. Say so once, then stop asking.
            if _TABLE_AVAILABLE is None:
                logger.info(
                    "migration 081 (position_margin_observations) is not applied; "
                    "broker margin capture is inactive and capital-relative "
                    "detectors will abstain on futures and short options")
            _TABLE_AVAILABLE = False
        else:
            logger.debug("no broker margin available (%s)", exc)
        return None

    if obs is None or not obs.total:
        return None

    # A structure's margin is not one leg's margin. When the observation covers
    # several legs, hand back this leg's own figure and say the scope is the
    # structure, so a consumer can never mistake one for the other.
    leg_value = (obs.per_leg or {}).get(symbol)
    if obs.leg_count > 1 and leg_value:
        return Capital(
            amount=float(leg_value), source=MarginSource.BROKER,
            scope="structure",
            note=(f"broker margin captured {obs.captured_at:%Y-%m-%d %H:%M} as part "
                  f"of a {obs.leg_count}-leg structure on {underlying} "
                  f"(structure total {float(obs.total):,.0f})"))

    return Capital(
        amount=float(obs.total), source=MarginSource.BROKER, scope="position",
        note=f"broker margin captured {obs.captured_at:%Y-%m-%d %H:%M}")
