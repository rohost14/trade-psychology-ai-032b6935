"""
Contracts the rest of the catalogue assumes but never checks.

Every other scenario asks "did the right pattern fire?". These ask the questions
underneath that: was it marked actionable, was it allowed to reach someone else,
and does the pipeline survive input that is legal but strange.

Three groups.

**Lifecycle.** `RiskAlert.lifecycle` distinguishes an alert raised while the
position is still open from one raised after it closed. The UI treats the two
differently — one is something you can still act on, the other is a post-mortem —
and migration 076 added the column, but nothing has ever asserted a value in it.

**Guardian routing.** WhatsApp delivery is parked until the business number
exists, so the decision is all there is to test, and it is the half worth
testing anyway. The assertion that matters is the negative one: `caution` must
never route. A trader agreed to have someone told when things are seriously
wrong; being reported for an ordinary bad afternoon is a different bargain and
would end the feature.

**Edge shapes.** Legal input that is easy to get wrong: a zero-quantity fill, a
position flipped through zero in a single order, and MCX — which trades past
15:30, so any detector reasoning about the intraday square-off must not fire on
it. The MCX case is the one most likely to break silently, because NFO session
boundaries are the ones everybody has in mind.
"""
from __future__ import annotations

from datetime import timedelta
from typing import List

from ..runner.inject import Fill, losing_trade, round_trip, winning_trade
from ..runner.scenario import Expect, Scenario
from .catalogue import NIFTY_CE, ROOMY, _flatten, at

MCX_FUT = "CRUDEOIL26AUGFUT"


def _s(sid, title, story, fills, *, must=(), must_not=(), records=(),
       capital=1_000_000, profile=None, section="Contracts") -> Scenario:
    return Scenario(
        id=sid, section=section, title=title, story=story, fills=fills,
        capital=capital, profile=profile if profile is not None else ROOMY,
        must_fire=list(must), must_not_fire=list(must_not), must_record=list(records),
    )


# ── Lifecycle ───────────────────────────────────────────────────────────────

POST_LIFECYCLE = _s(
    "G-01", "A closed-position alert is a post-mortem",
    "Five losses, all closed. Nothing here is still actionable.",
    _flatten([losing_trade(NIFTY_CE, at(10, 0) + timedelta(minutes=30 * i),
                           50, 30, hold_minutes=15) for i in range(5)]),
    must=[Expect("consecutive_loss_streak", lifecycle="post",
                 reason="raised after the trades closed — the UI must not offer it as "
                        "something the trader can still act on")],
)


# ── Guardian routing ────────────────────────────────────────────────────────

GUARDIAN_NO_ROUTE_ON_CAUTION = _s(
    "G-10", "A caution stays between the trader and the app",
    "An ordinary bad patch — enough to flag, nowhere near enough to report.",
    _flatten([
        losing_trade(NIFTY_CE, at(10, 0), 50, 25, hold_minutes=15),
        losing_trade(NIFTY_CE, at(10, 30), 50, 25, hold_minutes=15),
        losing_trade(NIFTY_CE, at(11, 0), 50, 25, hold_minutes=15),
    ]),
    must=[Expect("consecutive_loss_streak", routes_to_guardian=False,
                 reason="the trader consented to being reported when things are "
                        "seriously wrong, not for a bad afternoon — routing a caution "
                        "would break the bargain the feature rests on")],
)

GUARDIAN_ROUTES_ON_DANGER = _s(
    "G-11", "A danger on an eligible pattern does reach the partner",
    "Doubling into a losing run — the case the partner exists for.",
    _flatten([
        losing_trade(NIFTY_CE, at(10, 0) + timedelta(minutes=25 * i),
                     50 * (2 ** i), 30, hold_minutes=15)
        for i in range(4)
    ]),
    must=[Expect("martingale_behaviour", routes_to_guardian=True,
                 reason="guardian_eligible and danger — if this does not route, the "
                        "accountability feature is decorative")],
)


# ── Edge shapes ─────────────────────────────────────────────────────────────

ZERO_QTY_FILL = _s(
    "G-20", "A zero-quantity fill changes nothing",
    "A postback with quantity 0 arrives between two real fills.",
    [
        Fill(NIFTY_CE, "BUY", 50, 100.0, at(10, 0), note="open"),
        Fill(NIFTY_CE, "BUY", 0, 100.0, at(10, 10), note="zero-quantity postback"),
        Fill(NIFTY_CE, "SELL", 50, 94.0, at(10, 30), note="close"),
    ],
    must_not=[
        Expect("size_escalation", reason="nothing was added — a zero fill is not a trade"),
        Expect("overtrading_burst", reason="two fills, not three"),
    ],
)

FLIP_THROUGH_ZERO = _s(
    "G-21", "Long to short in one order",
    "Sells 100 while long 50 — closes the long and opens a short.",
    [
        Fill(NIFTY_CE, "BUY", 50, 100.0, at(10, 0), note="long 50"),
        Fill(NIFTY_CE, "SELL", 100, 94.0, at(10, 30), note="flip: close 50, short 50"),
        Fill(NIFTY_CE, "BUY", 50, 92.0, at(11, 0), note="cover the short"),
    ],
    must_not=[
        Expect("constitution_violation",
               reason="the flip is two positions, not a 100-lot one — sizing the whole "
                      "order as a single position would breach the per-trade rule"),
    ],
)

MCX_RUNS_LATE = _s(
    "G-22", "MCX trades past the equity square-off",
    "A commodity future entered at 16:30 — normal hours for MCX, after close for NFO.",
    _flatten([round_trip(MCX_FUT, at(16, 30), 10, 6000.0, 5900.0,
                         hold_minutes=40, exchange="MCX", product="NRML")]),
    must_not=[
        Expect("late_session_panic",
               reason="16:30 is the middle of the MCX session — reasoning with NFO's "
                      "15:30 boundary makes every commodity trade look like a "
                      "square-off scramble"),
        Expect("expiry_day_overtrading",
               reason="not an expiry day, and not an NFO contract"),
    ],
)

ALL: List[Scenario] = [
    POST_LIFECYCLE,
    GUARDIAN_NO_ROUTE_ON_CAUTION, GUARDIAN_ROUTES_ON_DANGER,
    ZERO_QTY_FILL, FLIP_THROUGH_ZERO, MCX_RUNS_LATE,
]
