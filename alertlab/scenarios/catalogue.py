"""
The scenario catalogue — trader stories, as executable definitions.

Sections mirror SCENARIOS.md. Written in Python rather than YAML because these
need computed timestamps, loops (a scalper takes forty trades) and capital
arithmetic; a data format would have grown a small language to express them.

Every scenario states what must fire AND what must stay silent. Roughly half the
assertions here are negative, matching where the defects actually are.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from ..runner.harness import IST
from ..runner.inject import (
    Fill, losing_trade, partial_fills, round_trip, structure, winning_trade,
)
from ..runner.scenario import Expect, Scenario

# A fixed Wednesday in the middle of a series, so nothing is accidentally an
# expiry day unless a scenario asks for one.
DAY = datetime(2026, 8, 5, tzinfo=IST)
# The LAST THURSDAY of the contract month — the parser derives expiry from the
# symbol, so an arbitrary Thursday is not an expiry day and is_expiry_day says so.
EXPIRY_DAY = datetime(2026, 8, 27, tzinfo=IST)


def at(hour: int, minute: int = 0, day: datetime = DAY) -> datetime:
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


NIFTY_CE = "NIFTY26AUG24500CE"
NIFTY_CE2 = "NIFTY26AUG24700CE"
NIFTY_PE = "NIFTY26AUG24300PE"
NIFTY_PE2 = "NIFTY26AUG24100PE"
BANKNIFTY_CE = "BANKNIFTY26AUG52000CE"


#: Limits deliberately far out of reach.
#:
#: The engine suppresses ordinary behavioural alerts behind a constitution
#: breach — the rule the trader wrote is the louder, more specific finding. That
#: is correct product behaviour and has its own scenario (F-15), but it means a
#: scenario isolating a BEHAVIOUR must not also trip a RULE, or the rule alert
#: is all you see. Six scenarios failed exactly this way on first run.
ROOMY = {
    "max_position_size": 60.0,
    "daily_trade_limit": 60,
    "max_consecutive_losses": 20,
    "cooldown_after_loss": 1,
    "daily_loss_limit": 5_000_000,
}


def _flatten(groups) -> List[Fill]:
    return [f for g in groups for f in g]


# ---------------------------------------------------------------------------
# K — the control. The most important scenario in the catalogue.
# ---------------------------------------------------------------------------

QUIET_DAY = Scenario(
    id="K-01", section="Control", title="A clean, disciplined session",
    story="Four trades, sensible size, two winners, every rule respected.",
    capital=500_000,
    fills=_flatten([
        winning_trade(NIFTY_CE, at(10, 0), 50, 12, hold_minutes=25),
        losing_trade(NIFTY_CE, at(11, 30), 50, 6, hold_minutes=20),
        winning_trade(BANKNIFTY_CE, at(13, 0), 25, 18, hold_minutes=30),
        losing_trade(NIFTY_PE, at(14, 15), 50, 5, hold_minutes=15),
    ]),
    must_not_fire=[
        Expect("overtrading_burst", reason="four trades across five hours is not a burst"),
        Expect("daily_overtrading", reason="well under any sane daily limit"),
        Expect("revenge_trade", reason="entries are spaced and sized normally"),
        Expect("size_escalation", reason="size never rises"),
        Expect("consecutive_loss_streak", reason="losses are not consecutive"),
        Expect("session_meltdown", reason="session is near flat"),
    ],
)


# ---------------------------------------------------------------------------
# B — trader archetypes
# ---------------------------------------------------------------------------

SPREAD_TRADER = Scenario(
    id="B-05", section="Archetypes", title="Spread trader — two iron condors",
    story="Two four-leg condors, entered as baskets, an hour apart. Eight fills, two decisions.",
    capital=1_000_000,
    fills=_flatten([
        structure([(NIFTY_CE2, "SELL"), (NIFTY_CE, "BUY"),
                   (NIFTY_PE, "SELL"), (NIFTY_PE2, "BUY")], at(10, 0), 50),
        structure([(NIFTY_CE2, "SELL"), (NIFTY_CE, "BUY"),
                   (NIFTY_PE, "SELL"), (NIFTY_PE2, "BUY")], at(11, 0), 50),
    ]),
    must_not_fire=[
        Expect("overtrading_burst",
               reason="THE regression: eight legs read as eight trades and fired danger"),
        Expect("daily_overtrading", reason="two structures, not eight trades"),
        Expect("direction_instability", reason="a condor is long and short by design"),
        Expect("fomo_entry", reason="one underlying, however many strikes"),
        Expect("size_escalation", reason="identical size both times"),
    ],
)

OPTION_SELLER = Scenario(
    id="B-04", section="Archetypes", title="Option seller — short strangle held all day",
    story="Sells a strangle in the morning, holds it, closes near the bell at a loss.",
    capital=2_000_000,
    fills=_flatten([
        round_trip(NIFTY_CE2, at(9, 45), 50, 120.0, 190.0, hold_minutes=330,
                   direction="SHORT"),
        round_trip(NIFTY_PE2, at(9, 45), 50, 110.0, 60.0, hold_minutes=330,
                   direction="SHORT"),
    ]),
    must_not_fire=[
        Expect("premium_loss_event",
               reason="long-only by design — firing it on a seller is wrong in direction and meaning"),
        Expect("overtrading_burst", reason="two legs of one position"),
    ],
)

DISCIPLINED_BAD_DAY = Scenario(
    id="B-12", section="Archetypes", title="Disciplined trader having a bad day",
    story="Six losses in a row, constant size, patient gaps. Losing is not misbehaving.",
    capital=500_000,
    profile=ROOMY,
    fills=_flatten([
        losing_trade(NIFTY_CE, at(9 + i, 30), 50, 8, hold_minutes=25)
        for i in range(6)
    ]),
    must_fire=[
        Expect("consecutive_loss_streak", reason="six in a row is exactly this pattern"),
    ],
    must_not_fire=[
        Expect("revenge_trade", reason="an hour between trades is not a reaction"),
        Expect("size_escalation", reason="size never changes"),
        Expect("martingale_behaviour", reason="no doubling"),
        Expect("post_loss_recovery_bet", reason="no oversized recovery attempt"),
    ],
)

SCALPER = Scenario(
    id="B-01", section="Archetypes", title="Scalper — 12 rapid round trips",
    story="Twelve trades in ninety minutes, tiny holds, same instrument.",
    capital=500_000,
    profile=ROOMY,
    fills=_flatten([
        round_trip(NIFTY_CE, at(10, 0) + timedelta(minutes=7 * i), 50,
                   100.0, 100.0 + (3 if i % 2 else -4), hold_minutes=3)
        for i in range(12)
    ]),
    must_fire=[
        Expect("overtrading_burst", reason="twelve entries inside the burst window"),
    ],
    # NOT daily_overtrading. Both come from the same detector and the burst
    # check returns first, so on any given trade they are mutually exclusive —
    # asserting both was a misreading of the code, not a bug in it.
)


# ---------------------------------------------------------------------------
# C — detector coverage, positive and near-miss
# ---------------------------------------------------------------------------

REVENGE = Scenario(
    id="C-01a", section="Detectors", title="Revenge trade — straight back in, bigger",
    story="Loses ₹4,200, re-enters the same instrument eight minutes later at 3x size.",
    # Deliberately roomy. At ₹500k the 150-lot re-entry ALSO breaches the
    # per-trade risk rule, and the engine suppresses ordinary behavioural
    # alerts behind a constitution breach — the rule the trader wrote is the
    # louder, more specific finding. Isolating revenge means not tripping it.
    capital=5_000_000,
    profile={"max_position_size": 40.0, "daily_loss_limit": 200_000,
             "cooldown_after_loss": 5, "daily_trade_limit": 20},
    fills=_flatten([
        losing_trade(NIFTY_CE, at(10, 0), 50, 84, hold_minutes=10),
        round_trip(NIFTY_CE, at(10, 18), 150, 100.0, 96.0, hold_minutes=12),
    ]),
    must_fire=[Expect("revenge_trade", reason="fast, same instrument, tripled size")],
)

REVENGE_NEAR_MISS = Scenario(
    id="C-01b", section="Detectors", title="Not revenge — same size, much later",
    story="Loses ₹4,200, waits ninety minutes, re-enters at normal size.",
    capital=500_000,
    fills=_flatten([
        losing_trade(NIFTY_CE, at(10, 0), 50, 84, hold_minutes=10),
        round_trip(NIFTY_CE, at(11, 40), 50, 100.0, 104.0, hold_minutes=15),
    ]),
    must_not_fire=[
        Expect("revenge_trade", reason="outside the window and no size increase"),
        Expect("rapid_reentry", reason="ninety minutes is a fresh decision"),
    ],
)

MARTINGALE = Scenario(
    id="C-11a", section="Detectors", title="Martingale — doubling after every loss",
    story="1 → 2 → 4 → 8 lots, each after losing on the same instrument.",
    capital=1_000_000,
    fills=_flatten([
        losing_trade(NIFTY_CE, at(10, 0) + timedelta(minutes=20 * i), 50 * (2 ** i),
                     6, hold_minutes=12)
        for i in range(4)
    ]),
    must_fire=[Expect("martingale_behaviour", reason="size doubles after each loss")],
)

PYRAMIDING_NEAR_MISS = Scenario(
    id="C-11b", section="Detectors", title="Not martingale — adding after wins",
    story="1 → 2 → 4 lots, each after a winning trade. Pyramiding into strength.",
    capital=1_000_000,
    fills=_flatten([
        winning_trade(NIFTY_CE, at(10, 0) + timedelta(minutes=25 * i), 50 * (2 ** i),
                      9, hold_minutes=15)
        for i in range(3)
    ]),
    must_not_fire=[
        Expect("martingale_behaviour", reason="doubling after WINS is the opposite behaviour"),
        Expect("size_escalation", reason="escalation while winning is not the pattern"),
    ],
)

FOMO_NEAR_MISS = Scenario(
    id="C-08b", section="Detectors", title="Not FOMO — four strikes, one underlying",
    story="Buys four NIFTY strikes in fifteen minutes.",
    capital=1_000_000,
    fills=_flatten([
        round_trip(sym, at(10, 0) + timedelta(minutes=4 * i), 50, 100.0, 103.0,
                   hold_minutes=20)
        for i, sym in enumerate([NIFTY_CE, NIFTY_CE2, NIFTY_PE, NIFTY_PE2])
    ]),
    must_not_fire=[
        Expect("fomo_entry",
               reason="FOMO counts distinct UNDERLYINGS — four NIFTY strikes is one"),
    ],
)


# ---------------------------------------------------------------------------
# D — fill and position mechanics. Where this week's defects lived.
# ---------------------------------------------------------------------------

SHORT_COVER = Scenario(
    id="D-05", section="Mechanics", title="Covering a short is an exit, not an entry",
    story="Opens a short with a SELL, covers it with a BUY.",
    capital=500_000,
    profile={"cooldown_after_loss": 30},
    wall_clock=at(11, 0),
    fills=_flatten([
        losing_trade(NIFTY_CE, at(10, 0), 50, 10, hold_minutes=15),
        round_trip(NIFTY_CE2, at(10, 30), 50, 120.0, 150.0, hold_minutes=20,
                   direction="SHORT"),
    ]),
    must_not_fire=[
        Expect("cooldown_violation",
               reason="the covering BUY is an exit — short sellers got false cooldown alerts on the way OUT"),
    ],
)

PARTIAL_FILLS = Scenario(
    id="D-01", section="Mechanics", title="Partial fills are one entry",
    story="A 150-lot order arriving in three tranches, then closed.",
    capital=500_000,
    fills=(
        partial_fills(NIFTY_CE, "BUY", at(10, 0), [50, 50, 50], price=100.0)
        + [Fill(NIFTY_CE, "SELL", 150, 104.0, at(10, 30), note="close")]
    ),
    must_not_fire=[
        Expect("overtrading_burst", reason="three tranches of one order is one decision"),
        Expect("size_escalation", reason="the position was built, not escalated"),
    ],
)

EQUITY_NOT_AN_OPTION = Scenario(
    id="D-12", section="Mechanics", title="RELIANCE is not a call option",
    story="Two equity round trips on a ticker whose name ends in CE.",
    capital=500_000,
    fills=_flatten([
        round_trip("RELIANCE", at(10, 0), 100, 2900.0, 2880.0, hold_minutes=30,
                   product="CNC", exchange="NSE"),
        round_trip("RELIANCE", at(11, 30), 100, 2880.0, 2905.0, hold_minutes=30,
                   product="CNC", exchange="NSE"),
    ]),
    must_not_fire=[
        Expect("premium_loss_event",
               reason="a ticker ending in CE is not an option — this misparse was caught in testing"),
        Expect("options_premium_avg_down", reason="equity has no premium"),
    ],
)


# ---------------------------------------------------------------------------
# A — capital tiers, identical behaviour
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# E / F — time of day and suppression
# ---------------------------------------------------------------------------

EXPIRY_DAY_HEAVY = Scenario(
    id="E-05", section="Time", title="Expiry-day churn after 13:00",
    story="Eight NIFTY round trips on expiry Thursday afternoon.",
    capital=5_000_000,
    profile=ROOMY,
    fills=_flatten([
        round_trip(NIFTY_CE, at(13, 0, EXPIRY_DAY) + timedelta(minutes=12 * i), 50,
                   100.0, 100.0 + (4 if i % 3 == 0 else -6), hold_minutes=8)
        for i in range(8)
    ]),
    must_fire=[Expect("expiry_day_overtrading", reason="past the count, after 13:00, on expiry")],
)

DEDUP_ONE_ALERT = Scenario(
    id="F-01", section="Suppression", title="The same pattern twice — one alert",
    story="Two revenge-shaped entries an hour apart in the same session.",
    capital=5_000_000,
    profile=ROOMY,
    fills=_flatten([
        losing_trade(NIFTY_CE, at(10, 0), 50, 84, hold_minutes=10),
        round_trip(NIFTY_CE, at(10, 15), 150, 100.0, 96.0, hold_minutes=10),
        losing_trade(NIFTY_CE, at(12, 0), 50, 80, hold_minutes=10),
        round_trip(NIFTY_CE, at(12, 15), 150, 100.0, 97.0, hold_minutes=10),
    ]),
    must_fire=[Expect("revenge_trade", reason="fires once; the second is deduplicated")],
)


_CORE: List[Scenario] = [
    QUIET_DAY,
    SPREAD_TRADER, OPTION_SELLER, DISCIPLINED_BAD_DAY, SCALPER,
    REVENGE, REVENGE_NEAR_MISS, MARTINGALE, PYRAMIDING_NEAR_MISS, FOMO_NEAR_MISS,
    SHORT_COVER, PARTIAL_FILLS, EQUITY_NOT_AN_OPTION,
    EXPIRY_DAY_HEAVY, DEDUP_ONE_ALERT,
]


def _all() -> List[Scenario]:
    """Core stories, detectors, the variation matrix, entry path, contracts."""
    from .contracts import ALL as CONTRACT_SCENARIOS
    from .detectors import DETECTOR_SCENARIOS
    from .entry import ALL as ENTRY_SCENARIOS
    from .variations import VARIATION_SCENARIOS

    merged = (_CORE + DETECTOR_SCENARIOS + VARIATION_SCENARIOS
              + ENTRY_SCENARIOS + CONTRACT_SCENARIOS)
    seen, out = set(), []
    for sc in merged:
        # A duplicate id would silently shadow one scenario with another and the
        # count would still look right.
        if sc.id in seen:
            raise ValueError(f"duplicate scenario id: {sc.id}")
        seen.add(sc.id)
        out.append(sc)
    return out


ALL_SCENARIOS: List[Scenario] = _all()
BY_ID = {s.id: s for s in ALL_SCENARIOS}
