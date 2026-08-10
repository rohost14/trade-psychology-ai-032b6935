"""
The entry path, and the fills that arrive wrong.

Two things nothing else in the catalogue touches.

**Entry-time detection (E1–E5).** Every other scenario asserts on a
CompletedTrade — that is, after the position closed and the money was already
lost. The entry checks ask the same detectors while the trader can still act,
and they had no coverage at all: the newest code in the system, running live in
shadow, entirely untested. `at_entry=True` on an expectation is what separates
"the pattern was detected" from "the pattern was detected in time to matter" —
without it these scenarios would pass on the exit-time detection of the same
pattern and prove nothing.

Everything the entry path produces is shadow evidence. Nothing here alerts, by
design, and a scenario that expected an alert would be asserting the opposite of
the intended behaviour. Promotion is a separate decision, taken from the numbers
in /api/admin/detection-quality.

**Fills that arrive wrong.** Zerodha redelivers postbacks and does not promise
order. A redelivered fill counted twice does not look like a bug — it looks like
a bigger position, which then feeds size_escalation, martingale and the
constitution rules. The idempotency guard is `uq_trades_broker_order`; these
scenarios are what proves it holds, because every symptom of it failing is
indistinguishable from real behaviour.
"""
from __future__ import annotations

from datetime import timedelta
from typing import List

from ..runner.inject import Fill, losing_trade, round_trip, winning_trade
from ..runner.scenario import Expect, Scenario
from .catalogue import DAY, NIFTY_CE, NIFTY_PE, ROOMY, _flatten, at

NIFTY_ATM_CE = "NIFTY26AUG24500CE"
NIFTY_ATM_PE = "NIFTY26AUG24500PE"


def _s(sid, title, story, fills, *, must=(), must_not=(), records=(),
       capital=1_000_000, profile=None, section="Entry path") -> Scenario:
    return Scenario(
        id=sid, section=section, title=title, story=story, fills=fills,
        capital=capital, profile=profile if profile is not None else ROOMY,
        must_fire=list(must), must_not_fire=list(must_not), must_record=list(records),
    )


# ── Entry-time detection ────────────────────────────────────────────────────

ENTRY_REVENGE = _s(
    "N-01", "Revenge caught at entry, not at exit",
    "Loses, then re-enters bigger — flagged as the position opens.",
    _flatten([
        losing_trade(NIFTY_CE, at(10, 0), 50, 40, hold_minutes=12),
        losing_trade(NIFTY_CE, at(10, 25), 50, 35, hold_minutes=12),
    ]) + [
        # Left OPEN on purpose. If it closed, the exit-time detector would raise
        # the same pattern and the scenario could pass without the entry check
        # ever having run.
        Fill(NIFTY_CE, "BUY", 150, 100.0, at(10, 45), note="re-entry, still open"),
    ],
    records=[Expect("revenge_trade", at_entry=True,
                    reason="the entire point of E1–E5: known at entry, so saying it "
                           "at exit is only saying it later")],
)

ENTRY_SIZE_ESCALATION = _s(
    "N-02", "Size escalation, seen while the position is open",
    "Three losses at rising size; the fourth entry is still live.",
    _flatten([
        losing_trade(NIFTY_CE, at(10, 0), 50, 30, hold_minutes=12),
        losing_trade(NIFTY_CE, at(10, 25), 100, 30, hold_minutes=12),
        losing_trade(NIFTY_CE, at(10, 50), 150, 30, hold_minutes=12),
    ]) + [
        Fill(NIFTY_CE, "BUY", 300, 100.0, at(11, 15), note="4x the first entry, open"),
    ],
    records=[Expect("size_escalation", at_entry=True,
                    reason="size is fully known at entry — nothing about the outcome "
                           "changes whether it escalated")],
)

ENTRY_CLEAN = _s(
    "N-03", "Nothing to say at entry",
    "One considered entry, no history behind it.",
    [Fill(NIFTY_CE, "BUY", 50, 100.0, at(10, 0), note="first trade of the day")],
    must_not=[
        Expect("revenge_trade", reason="no prior loss — nothing to avenge"),
        Expect("size_escalation", reason="no prior size to escalate from"),
        Expect("martingale_behaviour", reason="one trade is not a progression"),
    ],
)

ENTRY_BATCH_ONE_EVALUATION = _s(
    "N-04", "Four legs, one entry decision",
    "An iron condor arrives as four fills inside the batching window.",
    [
        Fill("NIFTY26AUG24300PE", "BUY", 50, 30.0, at(10, 0), note="condor leg 1"),
        Fill("NIFTY26AUG24400PE", "SELL", 50, 60.0, at(10, 0), note="leg 2"),
        Fill("NIFTY26AUG24600CE", "SELL", 50, 62.0, at(10, 0), note="leg 3"),
        Fill("NIFTY26AUG24700CE", "BUY", 50, 28.0, at(10, 0), note="leg 4"),
    ],
    must_not=[
        Expect("overtrading_burst",
               reason="four legs of one structure is one decision — E2 exists so the "
                      "entry check sees a condor, not four impulsive trades"),
        Expect("direction_instability",
               reason="calls and puts together are the structure, not indecision"),
    ],
)


# ── Fills that arrive wrong ─────────────────────────────────────────────────

DUPLICATE_POSTBACK = _s(
    "N-10", "The same fill delivered twice",
    "Zerodha redelivers one postback; the position must not double.",
    [
        Fill(NIFTY_CE, "BUY", 50, 100.0, at(10, 0),
             order_id="LABDUPE0001", note="original"),
        Fill(NIFTY_CE, "BUY", 50, 100.0, at(10, 0),
             order_id="LABDUPE0001", note="redelivered — same order id"),
        Fill(NIFTY_CE, "SELL", 50, 92.0, at(10, 30), note="close the 50 that exist"),
    ],
    must_not=[
        Expect("size_escalation",
               reason="a redelivered fill counted twice is not visible as a bug — it "
                      "looks like a bigger position, and feeds every size detector"),
        Expect("constitution_violation",
               reason="a phantom doubling would breach the per-trade risk rule"),
    ],
)

DUPLICATE_CLOSE = _s(
    "N-11", "The closing fill delivered twice",
    "A redelivered exit must not open a short.",
    [
        Fill(NIFTY_CE, "BUY", 50, 100.0, at(10, 0), note="open"),
        Fill(NIFTY_CE, "SELL", 50, 92.0, at(10, 30),
             order_id="LABDUPX0001", note="close"),
        Fill(NIFTY_CE, "SELL", 50, 92.0, at(10, 30),
             order_id="LABDUPX0001", note="redelivered close"),
    ],
    must_not=[
        Expect("direction_instability",
               reason="a duplicated exit processed twice would flip flat to short and "
                      "read as a reversal the trader never made"),
    ],
)

OUT_OF_ORDER_FILLS = _s(
    "N-12", "The exit postback arrives before the entry",
    "Same two fills, delivered in the wrong order.",
    [
        # The timestamps still say what really happened; only the delivery order
        # is wrong. The ledger is ordered by occurred_at for exactly this reason.
        Fill(NIFTY_CE, "SELL", 50, 92.0, at(10, 30), note="exit, delivered first"),
        Fill(NIFTY_CE, "BUY", 50, 100.0, at(10, 0), note="entry, delivered second"),
    ],
    must_not=[
        Expect("direction_instability",
               reason="reading the exit first would record a short that was never "
                      "taken, then a reversal on the entry"),
    ],
)

PARTIAL_THEN_DUPLICATE = _s(
    "N-13", "A sliced entry with one slice redelivered",
    "Three slices of one entry; the middle one arrives twice.",
    [
        Fill(NIFTY_CE, "BUY", 25, 100.0, at(10, 0), order_id="LABSLICE01", note="slice 1"),
        Fill(NIFTY_CE, "BUY", 25, 100.5, at(10, 1), order_id="LABSLICE02", note="slice 2"),
        Fill(NIFTY_CE, "BUY", 25, 100.5, at(10, 1), order_id="LABSLICE02", note="slice 2 again"),
        Fill(NIFTY_CE, "BUY", 25, 101.0, at(10, 2), order_id="LABSLICE03", note="slice 3"),
        Fill(NIFTY_CE, "SELL", 75, 96.0, at(10, 40), note="close all 75"),
    ],
    must_not=[
        Expect("overtrading_burst",
               reason="one sliced entry is one decision, and the duplicate must not "
                      "make it look like a fourth"),
    ],
)

ALL: List[Scenario] = [
    ENTRY_REVENGE, ENTRY_SIZE_ESCALATION, ENTRY_CLEAN, ENTRY_BATCH_ONE_EVALUATION,
    DUPLICATE_POSTBACK, DUPLICATE_CLOSE, OUT_OF_ORDER_FILLS, PARTIAL_THEN_DUPLICATE,
]
