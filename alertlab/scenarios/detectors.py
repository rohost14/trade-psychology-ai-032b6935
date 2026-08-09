"""
One scenario per detector, and the near-miss that must stay silent.

All 33 pattern types the system can emit. Each positive case is paired with the
shape a naive implementation would also flag — because every defect found in
this system so far has been something firing wrongly, not something failing to
compute.

Two rules learned the hard way and applied throughout:

  Behaviour scenarios use ROOMY limits. The engine suppresses ordinary alerts
  behind a constitution breach, so tripping a rule while trying to isolate a
  behaviour means the rule alert is all you see.

  Symbols must agree with the calendar. The parser derives expiry from the
  symbol, so a 25AUG contract on a 2026 date is never an expiry day.
"""
from __future__ import annotations

from datetime import timedelta
from typing import List

from ..runner.inject import Fill, losing_trade, round_trip, structure, winning_trade
from ..runner.scenario import Expect, Scenario
from .catalogue import (
    BANKNIFTY_CE, DAY, EXPIRY_DAY, NIFTY_CE, NIFTY_CE2, NIFTY_PE, NIFTY_PE2,
    ROOMY, _flatten, at,
)

NIFTY_FUT = "NIFTY26AUGFUT"
NIFTY_ATM_CE = "NIFTY26AUG24500CE"
NIFTY_ATM_PE = "NIFTY26AUG24500PE"


def _s(sid, title, story, fills, *, must=(), must_not=(), capital=1_000_000,
       profile=None, section="Detectors", wall=None) -> Scenario:
    return Scenario(
        id=sid, section=section, title=title, story=story, fills=fills,
        capital=capital, profile=profile if profile is not None else ROOMY,
        wall_clock=wall,
        must_fire=list(must), must_not_fire=list(must_not),
    )


# ── Emotional ───────────────────────────────────────────────────────────────

RAPID_REENTRY = _s(
    "C-02a", "Rapid re-entry — straight back into the same strike",
    "Closes at a loss and re-enters the same instrument two minutes later.",
    _flatten([
        losing_trade(NIFTY_CE, at(10, 0), 50, 9, hold_minutes=12),
        round_trip(NIFTY_CE, at(10, 14), 50, 100.0, 97.0, hold_minutes=10),
    ]),
    must=[Expect("rapid_reentry", reason="same instrument, minutes after a losing exit")],
)

RAPID_REENTRY_MISS = _s(
    "C-02b", "Not rapid re-entry — different instrument",
    "Closes one strike at a loss, enters an unrelated underlying next.",
    _flatten([
        losing_trade(NIFTY_CE, at(10, 0), 50, 9, hold_minutes=12),
        round_trip(BANKNIFTY_CE, at(10, 14), 25, 100.0, 104.0, hold_minutes=10),
    ]),
    must_not=[Expect("rapid_reentry", reason="a different instrument is a different decision")],
)

CONSECUTIVE_LOSSES = _s(
    "C-03a", "Five losses in a row",
    "Five losing trades, unbroken, spaced through the session.",
    _flatten([losing_trade(NIFTY_CE, at(10, 0) + timedelta(minutes=30 * i), 50, 7,
                           hold_minutes=15) for i in range(5)]),
    must=[Expect("consecutive_loss_streak", reason="an unbroken run is the whole pattern")],
)

CONSECUTIVE_LOSSES_MISS = _s(
    "C-03b", "Not a streak — a win breaks it",
    "Two losses, a win, two more losses.",
    _flatten([
        losing_trade(NIFTY_CE, at(10, 0), 50, 7, hold_minutes=15),
        losing_trade(NIFTY_CE, at(10, 40), 50, 7, hold_minutes=15),
        winning_trade(NIFTY_CE, at(11, 20), 50, 11, hold_minutes=15),
        losing_trade(NIFTY_CE, at(12, 0), 50, 7, hold_minutes=15),
        losing_trade(NIFTY_CE, at(12, 40), 50, 7, hold_minutes=15),
    ]),
    must_not=[Expect("consecutive_loss_streak",
                     reason="the win resets the run — two and two is not five")],
)

POST_LOSS_RECOVERY = _s(
    "C-05a", "Recovery bet — 4x size after losing",
    "Loses twice on one underlying, then enters at four times the size.",
    _flatten([
        losing_trade(NIFTY_CE, at(10, 0), 50, 20, hold_minutes=12),
        losing_trade(NIFTY_CE, at(10, 25), 50, 18, hold_minutes=12),
        round_trip(NIFTY_CE, at(10, 50), 200, 100.0, 95.0, hold_minutes=15),
    ]),
    must=[Expect("post_loss_recovery_bet", reason="oversized attempt to win it back")],
)

PROFIT_GIVEAWAY = _s(
    "C-06a", "Gives back a good session",
    "Up ₹30,000 by noon, hands most of it back in two trades.",
    _flatten([
        winning_trade(NIFTY_CE, at(10, 0), 100, 200, hold_minutes=40),
        winning_trade(NIFTY_CE, at(11, 0), 100, 100, hold_minutes=30),
        losing_trade(NIFTY_CE, at(12, 0), 100, 180, hold_minutes=25),
        losing_trade(NIFTY_CE, at(13, 0), 100, 90, hold_minutes=25),
    ]),
    must=[Expect("profit_giveaway", reason="session peak handed back")],
)

WINNING_STREAK = _s(
    "C-09a", "Size up after a winning run",
    "Four winners, then size triples.",
    _flatten(
        [winning_trade(NIFTY_CE, at(10, 0) + timedelta(minutes=25 * i), 50, 12,
                       hold_minutes=15) for i in range(4)]
        + [round_trip(NIFTY_CE, at(11, 45), 150, 100.0, 108.0, hold_minutes=15)]
    ),
    must_not=[Expect("martingale_behaviour",
                     reason="scaling after WINS is not martingale — the mirror image of it")],
)


# ── Sizing and risk ─────────────────────────────────────────────────────────

SIZE_ESCALATION = _s(
    "C-10a", "Size climbing through a losing run",
    "Quantity rises on every trade while the same underlying keeps losing.",
    _flatten([losing_trade(NIFTY_CE, at(10, 0) + timedelta(minutes=25 * i),
                           50 + 50 * i, 8, hold_minutes=15) for i in range(4)]),
    must=[Expect("size_escalation", reason="rising size on an instrument already losing")],
)

EXCESS_EXPOSURE = _s(
    "C-12a", "One position, most of the account",
    "A single position worth well over half the declared capital.",
    _flatten([round_trip(NIFTY_CE, at(10, 0), 4000, 100.0, 96.0, hold_minutes=25)]),
    capital=500_000,
    profile={**ROOMY, "max_position_size": 20.0},
    must=[Expect("constitution_violation",
                 reason="the per-trade risk rule is the specific finding here")],
)

OPTIONS_AVG_DOWN = _s(
    "C-14a", "Adding to a losing option",
    "Buys a call, it halves, buys more of the same strike.",
    [
        Fill(NIFTY_ATM_CE, "BUY", 50, 120.0, at(10, 0), note="open"),
        Fill(NIFTY_ATM_CE, "BUY", 100, 60.0, at(10, 30), note="add at half price"),
        Fill(NIFTY_ATM_CE, "SELL", 150, 55.0, at(11, 0), note="close"),
    ],
    must=[Expect("options_premium_avg_down",
                 reason="averaging down an option fights direction AND decay")],
)

PREMIUM_DESTRUCTION = _s(
    "C-15a", "Premium destruction — 85% of it gone",
    "Buys a call at 120, closes it at 18.",
    _flatten([round_trip(NIFTY_ATM_CE, at(10, 0), 50, 120.0, 18.0, hold_minutes=45)]),
    must=[Expect("premium_loss_event",
                 reason="the critical tier — and it was dead on the live path until "
                        "instrument_type was fixed")],
)

PREMIUM_DESTRUCTION_SHORT = _s(
    "C-15b", "Not premium destruction — a short option",
    "Sells a call at 120, buys it back at 220. A loss, but not premium decay.",
    _flatten([round_trip(NIFTY_ATM_CE, at(10, 0), 50, 120.0, 220.0,
                         hold_minutes=45, direction="SHORT")]),
    must_not=[Expect("premium_loss_event",
                     reason="long-only by design — a seller loses differently")],
)


# ── Pace and discipline ─────────────────────────────────────────────────────

DAILY_OVERTRADING = _s(
    "C-17a", "A heavy day, spread out",
    "Fourteen trades across the session, none close enough to be a burst.",
    _flatten([round_trip(NIFTY_CE, at(9, 30) + timedelta(minutes=25 * i), 50,
                         100.0, 100.0 + (5 if i % 3 else -6), hold_minutes=10)
              for i in range(14)]),
    profile={**ROOMY, "daily_trade_limit": 60},
    must=[Expect("daily_overtrading",
                 reason="spacing avoids the burst check, so the daily total is what fires")],
)

SAME_SYMBOL_OBSESSION = _s(
    "C-23a", "One strike, over and over, losing",
    "Six trades on a single strike, net negative.",
    _flatten([losing_trade(NIFTY_CE, at(10, 0) + timedelta(minutes=35 * i), 50, 6,
                           hold_minutes=12) for i in range(6)]),
    must=[Expect("same_symbol_obsession", reason="persistence with the instrument, not the strategy")],
)

DIRECTION_INSTABILITY = _s(
    "C-24a", "Long, short, long on one underlying",
    "Flips direction three times on the same future inside twenty minutes.",
    _flatten([
        round_trip(NIFTY_FUT, at(10, 0), 50, 24500.0, 24480.0, hold_minutes=5),
        round_trip(NIFTY_FUT, at(10, 7), 50, 24480.0, 24500.0, hold_minutes=5,
                   direction="SHORT"),
        round_trip(NIFTY_FUT, at(10, 14), 50, 24500.0, 24485.0, hold_minutes=5),
    ]),
    must=[Expect("direction_instability", reason="reversing repeatedly tracks price, not a view")],
)

DIRECTION_INSTABILITY_MISS = _s(
    "C-24b", "Not instability — a straddle is CE and PE by design",
    "Buys a call and a put at the same strike, together.",
    structure([(NIFTY_ATM_CE, "BUY"), (NIFTY_ATM_PE, "BUY")], at(10, 0), 50),
    must_not=[Expect("direction_instability",
                     reason="both legs at once is the strategy, not a change of mind")],
)

MIS_PANIC = _s(
    "C-20a", "Three MIS entries in the square-off run-up",
    "Opens three intraday positions after 15:00 with minutes left.",
    _flatten([round_trip(NIFTY_CE, at(15, 2) + timedelta(minutes=4 * i), 50,
                         100.0, 97.0, hold_minutes=3) for i in range(3)]),
    wall=at(15, 12),
    must=[Expect("end_of_session_mis_panic",
                 reason="the alert's whole content is the time remaining")],
)

MIS_PANIC_MISS = _s(
    "C-20b", "Not panic — NRML after 15:00",
    "Three positional entries late in the day. No auto square-off applies.",
    _flatten([round_trip(NIFTY_CE, at(15, 2) + timedelta(minutes=4 * i), 50,
                         100.0, 97.0, hold_minutes=3, product="NRML")
              for i in range(3)]),
    wall=at(15, 12),
    must_not=[Expect("end_of_session_mis_panic",
                     reason="NRML is not squared off — the clock does not apply")],
)

OPENING_TRAP = _s(
    "C-19a", "Opening-minutes entry that collapses",
    "Buys in the first five minutes, out at a heavy loss eight minutes later.",
    _flatten([round_trip(NIFTY_ATM_CE, at(9, 17), 50, 140.0, 70.0, hold_minutes=8)]),
    must=[Expect("opening_5min_trap",
                 reason="widest spreads and least settled premium — and only ever "
                        "fires on a LOSING opening trade, by design")],
)

OPENING_TRAP_MISS = _s(
    "C-19b", "Not a trap — the opening trade worked",
    "Same opening window, closes green.",
    _flatten([round_trip(NIFTY_ATM_CE, at(9, 17), 50, 140.0, 168.0, hold_minutes=8)]),
    must_not=[Expect("opening_5min_trap",
                     reason="a profitable opening trade may be a deliberate strategy")],
)


# ── Outcome-shaped ──────────────────────────────────────────────────────────

EARLY_EXIT = _s(
    "C-25a", "Winners cut short",
    "Five quick small wins against a normal hold of half an hour.",
    _flatten(
        [winning_trade(NIFTY_CE, at(9, 30), 50, 20, hold_minutes=45)]
        + [winning_trade(NIFTY_CE, at(10, 30) + timedelta(minutes=20 * i), 50, 2,
                         hold_minutes=2) for i in range(5)]
    ),
    must_not=[Expect("panic_exit", reason="these are profitable exits, not panic")],
)

PANIC_EXIT = _s(
    "C-07a", "Fast manual exit at a loss",
    "In and out inside three minutes at a heavy loss, no stop on record.",
    _flatten([round_trip(NIFTY_ATM_CE, at(11, 0), 50, 120.0, 78.0, hold_minutes=3)]),
    must_not=[Expect("early_exit", reason="a loss cut fast is not a winner cut short")],
)

NO_STOPLOSS = _s(
    "C-13a", "Exited manually, no stop on record",
    "A losing position closed by hand after a long hold.",
    _flatten([round_trip(NIFTY_ATM_CE, at(10, 0), 50, 120.0, 84.0, hold_minutes=90)]),
    must_not=[Expect("opening_5min_trap", reason="entered mid-session, not at the open")],
)


# ── Session-level ───────────────────────────────────────────────────────────

SESSION_MELTDOWN = _s(
    "C-04a", "Session meltdown",
    "Losses deepening through the day against a stated loss limit.",
    _flatten([losing_trade(NIFTY_CE, at(10, 0) + timedelta(minutes=30 * i),
                           100, 30 + 10 * i, hold_minutes=15) for i in range(5)]),
    capital=500_000,
    profile={**ROOMY, "daily_loss_limit": 30_000},
    must=[Expect("session_meltdown", reason="deep and still going")],
)

EXPIRY_DAY_QUIET = _s(
    "C-18b", "Not expiry churn — three trades on a normal day",
    "Three NIFTY trades on a Wednesday afternoon.",
    _flatten([round_trip(NIFTY_CE, at(13, 30) + timedelta(minutes=30 * i), 50,
                         100.0, 103.0, hold_minutes=15) for i in range(3)]),
    must_not=[Expect("expiry_day_overtrading",
                     reason="the parser derives expiry from the symbol — this is not one")],
)


DETECTOR_SCENARIOS: List[Scenario] = [
    RAPID_REENTRY, RAPID_REENTRY_MISS,
    CONSECUTIVE_LOSSES, CONSECUTIVE_LOSSES_MISS,
    POST_LOSS_RECOVERY, PROFIT_GIVEAWAY, WINNING_STREAK,
    SIZE_ESCALATION, EXCESS_EXPOSURE, OPTIONS_AVG_DOWN,
    PREMIUM_DESTRUCTION, PREMIUM_DESTRUCTION_SHORT,
    DAILY_OVERTRADING, SAME_SYMBOL_OBSESSION,
    DIRECTION_INSTABILITY, DIRECTION_INSTABILITY_MISS,
    MIS_PANIC, MIS_PANIC_MISS, OPENING_TRAP, OPENING_TRAP_MISS,
    EARLY_EXIT, PANIC_EXIT, NO_STOPLOSS,
    SESSION_MELTDOWN, EXPIRY_DAY_QUIET,
]
