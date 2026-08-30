"""
What a fill did to a position — the vocabulary entry-time detection runs on.

PositionLedger already classifies every fill as OPEN / INCREASE / DECREASE /
CLOSE / FLIP. This module turns that into the two questions the entry-time
pipeline actually asks:

  1. Did this fill open or grow a position? (only those are entries)
  2. If it grew one, did it add to a winner or to a loser?

Both are pure functions over a ledger row. They live here rather than in
trade_tasks so the position monitor and future entry detectors can import them
without pulling in the whole Celery task module.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

# PositionLedger entry_type values that mean "a position was opened or grown".
#
# FLIP counts: it closes one direction and opens the opposite, so it is an entry
# as well as an exit — and behaviourally it is one of the louder things a trader
# can do. DECREASE and CLOSE are exits and must never trigger entry-time checks.
#
# This replaced a `transaction_type == "BUY"` test, which conflated the side of
# an order with its effect: covering a short is a BUY and an exit, and opening a
# short is a SELL and an entry. Both were wrong in production.
POSITION_OPENING_FILLS = frozenset({"OPEN", "INCREASE", "FLIP"})

#: Scale-in classifications returned by classify_scale_in.
ADD_TO_LOSER = "add_to_loser"
ADD_TO_WINNER = "add_to_winner"


def opens_position(entry_type: Optional[str]) -> bool:
    """True when this fill opened or grew a position. None (unknown) is False."""
    return entry_type in POSITION_OPENING_FILLS


def classify_scale_in(
    entry_type: Optional[str],
    position_qty_after: Optional[int],
    fill_price: Optional[Decimal | float],
    avg_entry_price_after: Optional[Decimal | float],
) -> Optional[str]:
    """
    For an INCREASE, did the trader add to a winner or to a loser?

    These are opposite behaviours in the same shape. Adding to a winner is
    pyramiding into strength; adding to a loser is averaging down, which is what
    adding_to_adverse_position and martingale_behaviour exist to catch.
    Collapsing them into one "add" category would false-positive on every
    disciplined scale-in.

    Corrected 2026-08-30: this used to name `options_premium_avg_down` as the
    second consumer. That detector never read this classification and never saw
    an open position - it was retired at Pattern 20 for exactly that. The
    detector that DOES read this sequence is `adding_to_adverse_position`, and
    naming it here keeps the justification for this function attached to the
    code that depends on it.

    The test is the fill price against the position's average, and it needs no
    price feed. `avg_entry_price_after` is a weighted average of the price
    before and the fill price, so it always lies between them — which means
    `fill_price < avg_after` holds exactly when `fill_price < avg_before`. For a
    long, adding below your average is averaging down; for a short, adding above
    it is.

    Returns ADD_TO_LOSER, ADD_TO_WINNER, or None when the question does not
    apply (not an INCREASE) or cannot be answered (missing price data).

    Note this describes the *entry*, not the position's live P&L. A long that
    added below its average has averaged down even if the market has since
    rallied — the behaviour is what happened at the fill.
    """
    if entry_type != "INCREASE":
        return None
    if not position_qty_after or fill_price is None or avg_entry_price_after is None:
        return None

    price = Decimal(str(fill_price))
    avg = Decimal(str(avg_entry_price_after))
    if avg <= 0 or price <= 0:
        return None
    if price == avg:
        return None  # no information either way

    is_long = position_qty_after > 0
    added_below_average = price < avg
    # Long: cheaper than your average = averaging down.
    # Short: dearer than your average = averaging down (your average sale price
    # is being dragged toward a worse level).
    averaging_down = added_below_average if is_long else not added_below_average
    return ADD_TO_LOSER if averaging_down else ADD_TO_WINNER


def classify_fill(ledger_entry) -> dict:
    """
    The full classification of one ledger row, as a plain dict for the batch.

    Kept deliberately small and JSON-safe: it is written to Redis between the
    fill arriving and the coalescing window closing.
    """
    entry_type = getattr(ledger_entry, "entry_type", None)
    return {
        "entry_type": entry_type,
        "symbol": getattr(ledger_entry, "tradingsymbol", None),
        "exchange": getattr(ledger_entry, "exchange", None),
        "product": getattr(ledger_entry, "product", None),
        "qty": getattr(ledger_entry, "fill_qty", None),
        "scale_in": classify_scale_in(
            entry_type,
            getattr(ledger_entry, "position_qty_after", None),
            getattr(ledger_entry, "fill_price", None),
            getattr(ledger_entry, "avg_entry_price_after", None),
        ),
    }
