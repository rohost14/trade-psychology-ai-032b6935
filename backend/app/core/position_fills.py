"""
The fill sequence of one open position, and what happened inside it.

WHY THIS EXISTS
───────────────
A `CompletedTrade` aggregates every entry into one `avg_entry_price`. A trader
who goes 1 lot @50, adds 1 @40 and adds 1 @30 produces a single row at 40, and
the two adds are gone before any detector sees them. Measured on a year of real
trades, 64 positions were built that way — including the largest single loss in
the book — and no detector in the engine could see any of them.

This module carries the sequence, and nothing else. It decides what each fill
WAS; it does not decide whether that is worth telling anyone, which is the
detector's job.

WHAT AN ADVERSE ADD IS
──────────────────────
The position moved against the trader and the trader added exposure to it.
Direction-symmetric by construction:

    adverse% = (avg_entry_price − fill_price) / avg_entry_price × direction

A long filling lower and a short filling higher produce the same positive number,
so equity, futures, long options and short options all measure identically. The
price is the trader's own fill, which is a market print at the moment of the
decision — no market feed, no staleness class.

The size of the add is NOT part of whether this happened. Same-size adds count:
in the real book 95 of 96 adverse adds were smaller than 1.5× the position held,
and the median add was 0.67× — a multiplier rule is blind to the behaviour.

Adding after a FAVOURABLE move is a different thing (scaling into a position that
is working) and is never reported here.

See docs/patterns/02-adding_to_adverse_position/adding_to_adverse_position_contract.md and its three
validation companions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence

#: Ledger entry_type values. The ledger already classifies every fill, so this
#: module reads that classification rather than re-deriving it from quantities —
#: one definition of "this was an add", in the place that writes it.
OPEN = "OPEN"
INCREASE = "INCREASE"
DECREASE = "DECREASE"
CLOSE = "CLOSE"
FLIP = "FLIP"


@dataclass(frozen=True)
class PositionFill:
    """One fill, exactly as `position_ledger` recorded it. Nothing derived."""

    entry_type: str
    fill_qty: int                       # signed: + buy, − sell
    fill_price: float
    position_qty_after: int             # signed
    avg_entry_price_after: Optional[float]
    occurred_at: Optional[datetime]

    @staticmethod
    def from_ledger(row) -> "PositionFill":
        return PositionFill(
            entry_type=(row.entry_type or "").upper(),
            fill_qty=int(row.fill_qty or 0),
            fill_price=float(row.fill_price or 0),
            position_qty_after=int(row.position_qty_after or 0),
            avg_entry_price_after=(
                float(row.avg_entry_price_after)
                if row.avg_entry_price_after is not None else None
            ),
            occurred_at=row.occurred_at,
        )


@dataclass(frozen=True)
class AdverseAdd:
    """One add taken while the position was already losing."""

    #: 1 for the first adverse add in this position, 2 for the second, and so on.
    index: int
    #: How far the position had moved against the trader, in percent. Always > 0.
    adverse_pct: float
    #: Quantity added, and what was held before it. Both absolute.
    added_qty: int
    held_qty: int
    #: Price paid, and the average it was averaging away from.
    fill_price: float
    avg_before: float
    avg_after: float
    occurred_at: Optional[datetime]

    @property
    def add_ratio(self) -> float:
        """Size of the add against the position it was added to."""
        return self.added_qty / self.held_qty if self.held_qty else 0.0

    @property
    def at_least_doubled_down(self) -> bool:
        """
        Did the trader add at least as much as they were already holding?

        1.0 is the identity, not a chosen threshold: below it the position grew
        by less than it already was, at or above it the trader put on at least
        as much again.
        """
        return self.add_ratio >= 1.0


def adverse_adds(fills: Sequence[PositionFill]) -> List[AdverseAdd]:
    """
    Every adverse add in one position's fill sequence, oldest first.

    Walks the sequence and keeps only `INCREASE` fills taken while the position
    was under water. `DECREASE` does not change average cost, so a later re-add
    is still measured against the original average. `CLOSE` and `FLIP` end the
    position, and a flip starts a new one with its own counter — the trader who
    reverses is not still adding to the position they just closed.
    """
    out: List[AdverseAdd] = []
    held = 0
    avg = 0.0
    n = 0

    for f in fills:
        et = f.entry_type

        if et in (OPEN, FLIP):
            # A new position starts here, so anything recorded so far belonged
            # to one that no longer exists. The counter AND the collected adds
            # both reset - resetting only the counter was a bug, caught by
            # test_flip_resets_the_counter: the indices restarted at 1 while the
            # list kept growing, so a flip double-counted.
            #
            # CLOSE deliberately does NOT clear: a sequence that ends
            # OPEN..INCREASE..CLOSE is exactly one position, and that position's
            # adds are the answer.
            out.clear()
            held, avg, n = f.position_qty_after, f.fill_price, 0
            continue

        if et == CLOSE:
            held, avg, n = 0, 0.0, 0
            continue

        if et == DECREASE:
            # A partial exit reduces the position without changing what it cost.
            held = f.position_qty_after
            continue

        if et != INCREASE or held == 0 or avg <= 0:
            continue

        direction = 1.0 if held > 0 else -1.0
        adverse = (avg - f.fill_price) / avg * 100.0 * direction
        new_avg = (f.avg_entry_price_after
                   if f.avg_entry_price_after is not None else avg)

        if adverse > 0:
            n += 1
            out.append(AdverseAdd(
                index=n,
                adverse_pct=round(adverse, 4),
                added_qty=abs(f.fill_qty),
                held_qty=abs(held),
                fill_price=f.fill_price,
                avg_before=avg,
                avg_after=new_avg,
                occurred_at=f.occurred_at,
            ))
        # A favourable or flat add is not this behaviour. It still moves the
        # running state, because the next add is measured from the new average.

        held = f.position_qty_after
        avg = new_avg

    return out


def deepens_each_time(adds: Sequence[AdverseAdd]) -> bool:
    """Was every add further under water than the one before it?"""
    return len(adds) >= 2 and all(
        b.adverse_pct > a.adverse_pct for a, b in zip(adds, adds[1:])
    )
