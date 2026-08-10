"""
Feeding synthetic fills into the real pipeline.

Injection is at the FILL, in the Kite postback shape, through
`process_webhook_trade` — the same task the live webhook dispatches. With Celery
in eager mode that runs the genuine orchestration inline:

    ledger → fill classification → coalescing window → entry checks →
    strategy grouping → CompletedTrade → BehaviorEngine → dedup →
    consolidation → alert rows → delivery receipts

Injecting CompletedTrades directly would have been simpler and would have
skipped the top half — which is exactly where this week's defects lived
(a BUY covering a short read as an entry, four condor legs counted as four
trades, a fill lost mid-drain). The lab has to exercise the layer that breaks.

The HTTP endpoint and its checksum are deliberately skipped: that is transport,
and `test_webhook_checksum` already covers it.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .harness import IST, LAB_ACCOUNT_ID


@dataclass
class Fill:
    """
    One synthetic fill.

    `at` is the fill's own timestamp and is what the 27 engine detectors read —
    which is why most scenarios need no clock freezing: a fill stamped 09:17 on
    an expiry Thursday IS that moment as far as the engine is concerned.
    """
    symbol: str
    side: str                      # BUY | SELL
    qty: int
    price: float
    at: datetime
    product: str = "MIS"
    exchange: str = "NFO"
    order_type: str = "MARKET"
    order_id: Optional[str] = None
    note: str = ""                 # shown in the lab timeline, ignored by the pipeline

    def __post_init__(self):
        if self.order_id is None:
            self.order_id = f"LAB{uuid.uuid4().hex[:12].upper()}"
        if self.at.tzinfo is None:
            self.at = self.at.replace(tzinfo=IST)


def postback(fill: Fill) -> Dict[str, Any]:
    """
    Build the payload Zerodha would have posted.

    Mirrors the dict `webhooks.py` assembles from the form body, so the task
    receives exactly the shape it does in production.
    """
    stamp = fill.at.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "order_id": fill.order_id,
        "exchange_order_id": f"X{fill.order_id}",
        "status": "COMPLETE",
        "tradingsymbol": fill.symbol,
        "exchange": fill.exchange,
        "transaction_type": fill.side,
        "order_type": fill.order_type,
        "product": fill.product,
        "quantity": abs(fill.qty),
        "filled_quantity": abs(fill.qty),
        "pending_quantity": 0,
        "cancelled_quantity": 0,
        "price": fill.price,
        "average_price": fill.price,
        "trigger_price": 0.0,
        "status_message": None,
        "order_timestamp": stamp,
        "exchange_timestamp": stamp,
        "validity": "DAY",
        "variety": "regular",
        "disclosed_quantity": 0,
        "parent_order_id": None,
        "tag": "alertlab",
        "guid": None,
        "instrument_token": None,
        "raw_payload": {"source": "alertlab"},
    }


async def inject(fill: Fill) -> Dict[str, Any]:
    """
    Push one fill through the real pipeline and return what the task reported.

    Run in a worker thread, deliberately. `process_webhook_trade` calls
    `asyncio.run()` internally — which raises inside an already-running event
    loop. Called directly from this async runner the task failed instantly,
    eager mode swallowed the error, and every scenario produced zero alerts.
    Negative scenarios then passed for the worst possible reason: nothing ran at
    all. A separate thread gives `asyncio.run` the fresh loop it expects.

    Eager Celery keeps it synchronous: by the time this returns, every
    downstream effect — ledger row, position, completed trade, alerts, receipts
    — has already happened.
    """
    import asyncio

    from app.tasks.trade_tasks import process_webhook_trade

    payload = postback(fill)

    def _run():
        outcome = process_webhook_trade.apply(
            args=[payload, str(LAB_ACCOUNT_ID), "alertlab"]
        )
        # Eager mode with task_eager_propagates=False stores the exception
        # rather than raising it. Surfacing it here is the difference between a
        # scenario that failed and a scenario that never ran.
        if outcome.failed():
            return {"error": repr(outcome.result)}
        return {"result": outcome.result}

    result = await asyncio.to_thread(_run)
    return {"order_id": fill.order_id, **result}


# ---------------------------------------------------------------------------
# Convenience builders — the shapes scenarios keep needing
# ---------------------------------------------------------------------------

def round_trip(
    symbol: str,
    entry_at: datetime,
    qty: int,
    entry_price: float,
    exit_price: float,
    hold_minutes: int = 5,
    product: str = "MIS",
    exchange: str = "NFO",
    direction: str = "LONG",
    note: str = "",
) -> List[Fill]:
    """
    One complete round: open then close.

    `direction` builds a short as SELL-then-BUY, which matters more than it
    looks — the pipeline classifies fills by their effect on the position, and a
    BUY that covers a short must not be read as an entry.
    """
    open_side, close_side = ("BUY", "SELL") if direction == "LONG" else ("SELL", "BUY")
    exit_at = entry_at + timedelta(minutes=hold_minutes)
    return [
        Fill(symbol, open_side, qty, entry_price, entry_at, product, exchange,
             note=note or f"open {direction.lower()}"),
        Fill(symbol, close_side, qty, exit_price, exit_at, product, exchange,
             note="close"),
    ]


def losing_trade(symbol: str, at: datetime, qty: int, loss_per_unit: float,
                 entry_price: float = 100.0, **kw) -> List[Fill]:
    """A round trip that loses a stated amount per unit."""
    return round_trip(symbol, at, qty, entry_price,
                      entry_price - loss_per_unit, **kw)


def winning_trade(symbol: str, at: datetime, qty: int, gain_per_unit: float,
                  entry_price: float = 100.0, **kw) -> List[Fill]:
    return round_trip(symbol, at, qty, entry_price,
                      entry_price + gain_per_unit, **kw)


def structure(symbols_sides: List[tuple], at: datetime, qty: int,
              price: float = 100.0, seconds_apart: int = 1,
              exchange: str = "NFO", product: str = "MIS") -> List[Fill]:
    """
    A multi-leg entry — legs placed seconds apart, as a basket order arrives.

    Spacing matters: the structure grouping uses a 30-second window, so legs
    spread over minutes are counted as separate decisions by design.
    """
    return [
        Fill(sym, side, qty, price, at + timedelta(seconds=i * seconds_apart),
             product, exchange, note=f"leg {i + 1}")
        for i, (sym, side) in enumerate(symbols_sides)
    ]


def partial_fills(symbol: str, side: str, at: datetime, tranches: List[int],
                  price: float = 100.0, seconds_apart: int = 1, **kw) -> List[Fill]:
    """One order arriving in several tranches — must read as ONE entry."""
    return [
        Fill(symbol, side, q, price, at + timedelta(seconds=i * seconds_apart), **kw,
             note=f"partial {i + 1}/{len(tranches)}")
        for i, q in enumerate(tranches)
    ]


async def sync_positions_from_ledger(db, account_id) -> int:
    """
    Write the `positions` rows the Kite position sync would have written.

    Not a convenience — without this the entry-time path cannot run at all.

    The postback pipeline writes `position_ledger` and `completed_trades`. It
    does NOT write `positions`: that table is maintained by
    `trade_sync_service`, which polls Kite. So a lab driven purely by postbacks
    has an empty `positions` table, and `_shadow_entry_detection` — which starts
    by loading the open positions for the symbols in the batch — returns
    `{"skipped": "no_open_positions"}` every time, silently, with no log line.

    Worth carrying out of the lab: in production the entry batch flushes about
    five seconds after a fill, and if the Kite sync has not landed by then the
    same skip happens for the same reason. The lab makes that visible; it does
    not cause it.

    Derived from the ledger's own running totals rather than recomputed, so the
    quantities and average price here are the pipeline's numbers, not a second
    opinion that could disagree with it.
    """
    from sqlalchemy import delete, select

    from app.models.position import Position
    from app.models.position_ledger import PositionLedger
    from app.services.instrument_parser import parse_symbol

    rows = (await db.execute(
        select(PositionLedger)
        .where(PositionLedger.broker_account_id == account_id)
        .order_by(PositionLedger.occurred_at, PositionLedger.created_at)
    )).scalars().all()

    latest = {}
    for entry in rows:
        latest[(entry.tradingsymbol, entry.exchange, entry.product)] = entry

    await db.execute(delete(Position).where(Position.broker_account_id == account_id))

    written = 0
    for (symbol, exchange, product), entry in latest.items():
        qty = entry.position_qty_after or 0
        if qty == 0:
            continue        # flat: the sync would not carry a row either
        try:
            instrument_type = parse_symbol(symbol).instrument_type or None
        except Exception:
            instrument_type = None
        db.add(Position(
            broker_account_id=account_id,
            tradingsymbol=symbol,
            exchange=exchange,
            instrument_type=instrument_type,
            product=product,
            total_quantity=qty,
            average_entry_price=entry.avg_entry_price_after,
        ))
        written += 1

    await db.commit()
    return written
