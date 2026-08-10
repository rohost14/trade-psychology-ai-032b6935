"""
Real session volume.

Every other scenario is under fifteen fills, and the parts of the pipeline that
only exist because sessions are bigger than that — the dedup window, alert
consolidation, the batching window, the per-detector cooldowns — never bind at
that size. They are therefore the least tested code in the system while being
the code that decides what a trader actually sees on a busy day.

The assertion that matters here is the ceiling, not the floor. Correctness at
volume is not "did the pattern fire" — every scenario above answers that — it is
**how many times**. A session that produces forty alerts has told the trader
nothing, however defensible each one is in isolation. `max_alerts` is the only
place the noise budget is stated as a number rather than assumed.

The budgets below are deliberately generous. They are not a claim about the
right number; they are a tripwire for the failure mode where a dedup window
stops binding and one pattern fires once per fill. If a change makes these fail,
the question to ask is whether dedup broke, not whether the budget is too tight.

Snapshots are off. The per-fill timeline costs three queries per fill and exists
so you can see which trade caused which alert — worth it at twelve fills,
meaningless across two hundred.
"""
from __future__ import annotations

from datetime import timedelta
from typing import List

from ..runner.inject import Fill, losing_trade, round_trip, winning_trade
from ..runner.scenario import Expect, Scenario
from .catalogue import BANKNIFTY_CE, NIFTY_CE, NIFTY_CE2, NIFTY_PE, ROOMY, _flatten, at

STRIKES = [
    "NIFTY26AUG24300CE", "NIFTY26AUG24400CE", "NIFTY26AUG24500CE",
    "NIFTY26AUG24600CE", "NIFTY26AUG24700CE",
    "NIFTY26AUG24300PE", "NIFTY26AUG24400PE", "NIFTY26AUG24500PE",
]


def _s(sid, title, story, fills, *, must=(), must_not=(), records=(),
       max_alerts=None, capital=2_000_000, profile=None,
       section="Volume") -> Scenario:
    return Scenario(
        id=sid, section=section, title=title, story=story, fills=fills,
        capital=capital, profile=profile if profile is not None else ROOMY,
        must_fire=list(must), must_not_fire=list(must_not), must_record=list(records),
        max_alerts=max_alerts, snapshot_steps=False,
    )


def _scalper_day(count: int) -> List[Fill]:
    """
    A heavy but ordinary scalping session: alternating small wins and losses,
    rotating across strikes, a few minutes apart.

    Alternating on purpose. An unbroken losing run would trip the streak
    detectors and the result would be a test of those rather than of volume.
    """
    fills: List[Fill] = []
    start = at(9, 30)
    for i in range(count):
        symbol = STRIKES[i % len(STRIKES)]
        when = start + timedelta(minutes=4 * i)
        if i % 3 == 2:
            fills += losing_trade(symbol, when, 50, 6, hold_minutes=2)
        else:
            fills += winning_trade(symbol, when, 50, 5, hold_minutes=2)
    return fills


BUSY_SESSION = _s(
    "V-01", "A hundred round trips in one session",
    "A scalper's full day — 200 fills across eight strikes.",
    _scalper_day(100),
    max_alerts=40,
    must_not=[
        Expect("consecutive_loss_streak",
               reason="wins break every run — a streak detector firing here would be "
                      "reading volume as a losing run"),
    ],
)

RELENTLESS_LOSING_DAY = _s(
    "V-02", "Forty losses, one after another",
    "The worst realistic session: forty losing round trips, no wins.",
    _flatten([
        losing_trade(STRIKES[i % len(STRIKES)], at(9, 30) + timedelta(minutes=8 * i),
                     50, 20, hold_minutes=4)
        for i in range(40)
    ]),
    max_alerts=60,
    must=[
        Expect("consecutive_loss_streak", reason="forty in a row is the pattern"),
    ],
)

ONE_SYMBOL_ALL_DAY = _s(
    "V-03", "Thirty round trips on a single strike",
    "The same instrument, over and over, for the whole session.",
    _flatten([
        (losing_trade if i % 2 else winning_trade)(
            NIFTY_CE, at(9, 30) + timedelta(minutes=11 * i), 50, 12, hold_minutes=5)
        for i in range(30)
    ]),
    max_alerts=40,
    must=[
        Expect("same_symbol_obsession",
               reason="thirty round trips on one strike is the definition of it"),
    ],
)

WIDE_BOOK = _s(
    "V-04", "Eight instruments open at once",
    "Positions across every strike, all held, none closed.",
    [
        Fill(symbol, "BUY", 50, 100.0, at(10, 0) + timedelta(minutes=i),
             note=f"leg {i + 1}")
        for i, symbol in enumerate(STRIKES)
    ],
    max_alerts=15,
    must_not=[
        Expect("consecutive_loss_streak", reason="nothing has closed — there are no "
                                                 "outcomes to form a streak from"),
    ],
)

ALL: List[Scenario] = [BUSY_SESSION, RELENTLESS_LOSING_DAY, ONE_SYMBOL_ALL_DAY, WIDE_BOOK]
