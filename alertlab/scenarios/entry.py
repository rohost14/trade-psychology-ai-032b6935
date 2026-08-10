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
from .catalogue import BANKNIFTY_CE, DAY, NIFTY_CE, NIFTY_PE, ROOMY, _flatten, at

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


# ── The rest of ENTRY_DECIDABLE, checked at entry ───────────────────────────
#
# Ten detectors are entry-decidable and running live in shadow. Two are covered
# above; these are the other eight. Exit-time coverage says nothing about them
# here: at entry the outcome fields are None, and the engine's idiom throughout
# is `float(ct.realized_pnl or 0)`, which turns None into a clean zero. A
# detector that reads the outcome anywhere in its path will therefore not crash
# — it will quietly answer as though the trade broke even, which is the failure
# mode worth catching before any of these is promoted.
#
# Every scenario leaves its final position OPEN. A closed one lets the exit-time
# detector answer instead, and the scenario would pass without the entry check
# having run at all.

ENTRY_RAPID_REENTRY = _s(
    "N-05", "Rapid re-entry, caught as it happens",
    "Closes at a loss and is back in the same strike two minutes later.",
    _flatten([losing_trade(NIFTY_CE, at(10, 0), 50, 45, hold_minutes=12)])
    + [Fill(NIFTY_CE, "BUY", 50, 100.0, at(10, 14), note="straight back in, still open")],
    records=[Expect("rapid_reentry", at_entry=True,
                    reason="the gap to the previous exit is known the moment the "
                           "order fills — nothing about the outcome changes it")],
)

ENTRY_POST_LOSS_RECOVERY = _s(
    "N-06", "The recovery bet, before it resolves",
    "Three losses, then an entry at four times the size — still open.",
    _flatten([
        losing_trade(NIFTY_CE, at(10, 0), 50, 20, hold_minutes=12),
        losing_trade(NIFTY_CE, at(10, 25), 50, 18, hold_minutes=12),
        losing_trade(NIFTY_CE, at(10, 50), 50, 22, hold_minutes=12),
    ]) + [Fill(NIFTY_CE, "BUY", 200, 100.0, at(11, 15), note="4x, open")],
    records=[Expect("post_loss_recovery_bet", at_entry=True,
                    reason="size and the losses behind it are both already on the "
                           "record — this is the alert with the most to gain from "
                           "arriving early")],
)

ENTRY_MARTINGALE = _s(
    "N-07", "Martingale, with the last leg still live",
    "Doubling after every loss; the fourth double has not resolved.",
    _flatten([
        losing_trade(NIFTY_CE, at(10, 0), 25, 30, hold_minutes=15),
        losing_trade(NIFTY_CE, at(10, 25), 50, 30, hold_minutes=15),
        losing_trade(NIFTY_CE, at(10, 50), 100, 30, hold_minutes=15),
    ]) + [Fill(NIFTY_CE, "BUY", 200, 100.0, at(11, 15), note="the fourth double, open")],
    records=[Expect("martingale_behaviour", at_entry=True,
                    reason="a progression is visible from the sizes alone; waiting for "
                           "the outcome only confirms what the pattern already said")],
)

ENTRY_SAME_SYMBOL_OBSESSION = _s(
    "N-08", "Back to the same strike a fourth time",
    "Three losses on one strike, then a fourth entry that is still open.",
    _flatten([
        losing_trade(NIFTY_CE, at(10, 0), 50, 25, hold_minutes=15),
        losing_trade(NIFTY_CE, at(10, 30), 75, 25, hold_minutes=15),
        losing_trade(NIFTY_CE, at(11, 0), 100, 25, hold_minutes=15),
    ]) + [Fill(NIFTY_CE, "BUY", 150, 100.0, at(11, 30), note="fourth attempt, open")],
    records=[Expect("same_symbol_obsession", at_entry=True,
                    reason="three losses and a fourth entry on one underlying — the "
                           "count is complete before this trade resolves")],
)

ENTRY_DIRECTION_INSTABILITY = _s(
    "N-09", "Reversing the view, mid-reversal",
    "Long the call, loses, and is immediately long the put instead.",
    _flatten([losing_trade(NIFTY_ATM_CE, at(10, 0), 50, 40, hold_minutes=12)])
    + [Fill(NIFTY_ATM_PE, "BUY", 50, 95.0, at(10, 14), note="opposite view, open")],
    records=[Expect("direction_instability", at_entry=True,
                    reason="flipping from a call to a put on the same underlying "
                           "minutes after a loss is a decision, not an outcome")],
)

ENTRY_WINNING_STREAK = _s(
    "N-14", "Sizing up on a winning run, before it turns",
    "Four winners, then triple size — the fifth is still open.",
    _flatten([
        winning_trade(NIFTY_CE, at(10, 0) + timedelta(minutes=25 * i), 50, 12,
                      hold_minutes=15) for i in range(4)
    ]) + [Fill(NIFTY_CE, "BUY", 150, 100.0, at(11, 45), note="3x after four wins, open")],
    records=[Expect("winning_streak_overconfidence", at_entry=True,
                    reason="the one entry-time pattern that fires on a GOOD run — "
                           "worth saying while the position can still be sized down")],
)

ENTRY_PREMIUM_AVG_DOWN = _s(
    "N-15", "Averaging into a losing option, live",
    "Two heavy losses on one strike, then buying it again — open.",
    _flatten([
        round_trip(NIFTY_ATM_CE, at(10, 0), 50, 120.0, 72.0, hold_minutes=15),
        round_trip(NIFTY_ATM_CE, at(10, 30), 50, 100.0, 62.0, hold_minutes=15),
    ]) + [Fill(NIFTY_ATM_CE, "BUY", 100, 90.0, at(11, 0), note="third buy, open")],
    records=[Expect("options_premium_avg_down", at_entry=True,
                    reason="averaging down an option fights direction and decay at "
                           "once — the moment to say so is before the third entry "
                           "is sitting there")],
)

ENTRY_FOMO = _s(
    "N-16", "Chasing several strikes in the opening half hour",
    "Three different instruments inside the first thirty minutes.",
    _flatten([
        round_trip(NIFTY_CE, at(9, 20), 50, 100.0, 97.0, hold_minutes=8),
        round_trip(NIFTY_PE, at(9, 30), 50, 90.0, 87.0, hold_minutes=8),
    ]) + [Fill(BANKNIFTY_CE, "BUY", 25, 150.0, at(9, 40), note="third instrument, open")],
    records=[Expect("fomo_entry", at_entry=True,
                    reason="how many instruments were touched in the window is a "
                           "count of entries, and needs no outcome at all")],
)

ALL += [
    ENTRY_RAPID_REENTRY, ENTRY_POST_LOSS_RECOVERY, ENTRY_MARTINGALE,
    ENTRY_SAME_SYMBOL_OBSESSION, ENTRY_DIRECTION_INSTABILITY,
    ENTRY_WINNING_STREAK, ENTRY_PREMIUM_AVG_DOWN, ENTRY_FOMO,
]
