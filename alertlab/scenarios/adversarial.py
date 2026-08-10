"""
The boundaries, from both sides.

Every scenario elsewhere sits comfortably inside or outside a threshold, which
tests that a detector works but not where it stops. These pairs sit either side
of a real number read out of trading_defaults: one just inside, one just
outside, otherwise identical. A detector that fires on both is not detecting a
pattern, it is detecting that trading happened.

Written adversarially on purpose. The near-misses elsewhere in the catalogue
were written by me alongside their positive cases and share my assumptions about
what the code does; these were written from the threshold values instead, which
is the closest I can get to disagreeing with myself.

Two things a boundary pair is unusually good at catching, and neither shows up
in ordinary coverage: an off-by-one in a comparison (`>` where `>=` was meant
moves the line by exactly one trade), and a threshold that has quietly stopped
being read from the profile at all — a hard-coded constant passes every test
that never probes its edge.

The `>` versus `>=` cases are deliberately left as the code defines them rather
than as I would define them. A pair asserts that the line is where the constants
say it is; it does not argue about which side of the line the boundary value
belongs on.
"""
from __future__ import annotations

from datetime import timedelta
from typing import List

from ..runner.inject import Fill, losing_trade, round_trip, winning_trade
from ..runner.scenario import Expect, Scenario
from .catalogue import NIFTY_CE, ROOMY, _flatten, at

NIFTY_ATM_CE = "NIFTY26AUG24500CE"


def _s(sid, title, story, fills, *, must=(), must_not=(), records=(),
       capital=1_000_000, profile=None, section="Boundaries") -> Scenario:
    return Scenario(
        id=sid, section=section, title=title, story=story, fills=fills,
        capital=capital, profile=profile if profile is not None else ROOMY,
        must_fire=list(must), must_not_fire=list(must_not), must_record=list(records),
    )


# ── revenge_min_loss_inr = 500 ──────────────────────────────────────────────
# The floor that separates a scratch from a loss worth avenging. It already
# caught one wrong scenario of mine: a 7% move on a ₹120 option is ₹420 across
# 50 lots, and the detector was right to stay quiet.

REVENGE_UNDER_FLOOR = _s(
    "X-01", "A ₹400 loss is a scratch",
    "Re-enters bigger after losing ₹400 — under the ₹500 floor.",
    _flatten([losing_trade(NIFTY_CE, at(10, 0), 50, 8, hold_minutes=10)])
    + [Fill(NIFTY_CE, "BUY", 150, 100.0, at(10, 12), note="₹400 lost, re-entry")],
    must_not=[Expect("revenge_trade",
                     reason="below revenge_min_loss_inr — a scratch is not a wound, and "
                            "flagging one teaches the trader to ignore the alert")],
)

REVENGE_OVER_FLOOR = _s(
    "X-02", "A ₹600 loss is not",
    "Identical shape, ₹600 lost instead of ₹400.",
    _flatten([losing_trade(NIFTY_CE, at(10, 0), 50, 12, hold_minutes=10)])
    + [Fill(NIFTY_CE, "BUY", 150, 100.0, at(10, 12), note="₹600 lost, re-entry")],
    records=[Expect("revenge_trade", at_entry=True,
                    reason="the only difference from X-01 is ₹200 — if both are silent "
                           "the floor is wrong, if both fire it is not being read")],
)


# ── consecutive_loss_caution = 3 ────────────────────────────────────────────

STREAK_TWO = _s(
    "X-03", "Two losses is not a streak",
    "Two losing trades, nothing else.",
    _flatten([
        losing_trade(NIFTY_CE, at(10, 0), 50, 20, hold_minutes=15),
        losing_trade(NIFTY_CE, at(10, 40), 50, 20, hold_minutes=15),
    ]),
    must_not=[Expect("consecutive_loss_streak",
                     reason="one under the threshold — everybody loses twice")],
)

STREAK_THREE = _s(
    "X-04", "Three is",
    "The same session with one more loss.",
    _flatten([
        losing_trade(NIFTY_CE, at(10, 0), 50, 20, hold_minutes=15),
        losing_trade(NIFTY_CE, at(10, 40), 50, 20, hold_minutes=15),
        losing_trade(NIFTY_CE, at(11, 20), 50, 20, hold_minutes=15),
    ]),
    must=[Expect("consecutive_loss_streak",
                 reason="exactly at consecutive_loss_caution — the boundary value "
                        "belongs inside, and a > instead of >= moves it by one trade")],
)


# ── rapid_reentry_min = 5 ───────────────────────────────────────────────────

REENTRY_OUTSIDE_WINDOW = _s(
    "X-05", "Back in after seven minutes",
    "Same instrument, but outside the five-minute window.",
    _flatten([losing_trade(NIFTY_CE, at(10, 0), 50, 45, hold_minutes=10)])
    + [Fill(NIFTY_CE, "BUY", 50, 100.0, at(10, 17), note="7 min after the exit")],
    must_not=[Expect("rapid_reentry",
                     reason="waiting is the behaviour the pattern is contrasted with — "
                            "if seven minutes still counts, the window means nothing")],
)

REENTRY_INSIDE_WINDOW = _s(
    "X-06", "Back in after three",
    "The same trade, four minutes earlier.",
    _flatten([losing_trade(NIFTY_CE, at(10, 0), 50, 45, hold_minutes=10)])
    + [Fill(NIFTY_CE, "BUY", 50, 100.0, at(10, 13), note="3 min after the exit")],
    records=[Expect("rapid_reentry", at_entry=True,
                    reason="inside rapid_reentry_min")],
)


# ── martingale_caution_multiplier = 1.5 ─────────────────────────────────────

MARTINGALE_UNDER_MULTIPLIER = _s(
    "X-07", "Sizing up by 40% is not doubling",
    "Four losses, each entry 1.4x the last — under the 1.5x line.",
    _flatten([
        losing_trade(NIFTY_CE, at(10, 0) + timedelta(minutes=25 * i),
                     int(50 * (1.4 ** i)), 30, hold_minutes=15)
        for i in range(4)
    ]),
    must_not=[Expect("martingale_behaviour",
                     reason="under martingale_caution_multiplier — a trader who sizes up "
                            "gently is doing something different from one who doubles")],
)

MARTINGALE_AT_MULTIPLIER = _s(
    "X-08", "Sizing up by 60% is",
    "The same four losses at 1.6x each step.",
    _flatten([
        losing_trade(NIFTY_CE, at(10, 0) + timedelta(minutes=25 * i),
                     int(50 * (1.6 ** i)), 30, hold_minutes=15)
        for i in range(4)
    ]),
    must=[Expect("martingale_behaviour",
                 reason="over the caution multiplier, under the 2.0 danger one")],
)


# ── obsession_min_losses = 3, obsession_min_reentries = 2 ───────────────────

OBSESSION_TWO_LOSSES = _s(
    "X-09", "Two losses on one strike is not obsession",
    "Two losing round trips on the same instrument, then a third entry.",
    _flatten([
        losing_trade(NIFTY_CE, at(10, 0), 50, 25, hold_minutes=15),
        losing_trade(NIFTY_CE, at(10, 40), 50, 25, hold_minutes=15),
    ]) + [Fill(NIFTY_CE, "BUY", 50, 100.0, at(11, 20), note="third entry, open")],
    must_not=[Expect("same_symbol_obsession",
                     reason="one loss short of obsession_min_losses — trading one "
                            "instrument you know well is a strategy, not a symptom")],
)


# ── premium_avg_down_loss_pct = 20 ──────────────────────────────────────────

AVG_DOWN_SHALLOW = _s(
    "X-10", "A 10% drawdown is not averaging into a loser",
    "Two small losses on one strike, then buying it again.",
    _flatten([
        round_trip(NIFTY_ATM_CE, at(10, 0), 50, 100.0, 90.0, hold_minutes=15),
        round_trip(NIFTY_ATM_CE, at(10, 30), 50, 100.0, 90.0, hold_minutes=15),
    ]) + [Fill(NIFTY_ATM_CE, "BUY", 100, 95.0, at(11, 0), note="third buy, open")],
    must_not=[Expect("options_premium_avg_down",
                     reason="under premium_avg_down_loss_pct — a 10% move on an option "
                            "is an ordinary morning, not a position going wrong")],
)


# ── Shapes that look like the pattern and are not ───────────────────────────

ROLLING_A_POSITION = _s(
    "X-11", "Rolling a position is not revenge",
    "Closes a losing call and immediately opens the next strike up.",
    _flatten([losing_trade("NIFTY26AUG24500CE", at(10, 0), 50, 45, hold_minutes=20)])
    + [Fill("NIFTY26AUG24600CE", "BUY", 50, 60.0, at(10, 22), note="rolled up, open")],
    must_not=[Expect("same_symbol_obsession",
                     reason="a different strike is a different position — rolling is "
                            "routine and flagging it would make the alert useless to "
                            "anyone who trades options seriously"),
              Expect("martingale_behaviour",
                     reason="same size, not a progression")],
)

SCALING_OUT = _s(
    "X-12", "Scaling out is not a reversal",
    "One entry, closed in three pieces at improving prices.",
    [
        Fill(NIFTY_CE, "BUY", 150, 100.0, at(10, 0), note="one entry"),
        Fill(NIFTY_CE, "SELL", 50, 104.0, at(10, 20), note="first third"),
        Fill(NIFTY_CE, "SELL", 50, 106.0, at(10, 30), note="second third"),
        Fill(NIFTY_CE, "SELL", 50, 108.0, at(10, 40), note="last third"),
    ],
    must_not=[
        Expect("direction_instability",
               reason="taking profit in pieces is one decision executed carefully"),
        Expect("overtrading_burst",
               reason="three exits of one position are not three trades"),
    ],
)

ALL: List[Scenario] = [
    REVENGE_UNDER_FLOOR, REVENGE_OVER_FLOOR,
    STREAK_TWO, STREAK_THREE,
    REENTRY_OUTSIDE_WINDOW, REENTRY_INSIDE_WINDOW,
    MARTINGALE_UNDER_MULTIPLIER, MARTINGALE_AT_MULTIPLIER,
    OBSESSION_TWO_LOSSES, AVG_DOWN_SHALLOW,
    ROLLING_A_POSITION, SCALING_OUT,
]
