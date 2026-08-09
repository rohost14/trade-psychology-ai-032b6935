"""
The same behaviour, across every axis a trader can vary.

A detector that only works at the capital it was tuned for, on the instrument
the author had in mind, is a detector that works for one person. These generate
the same story across capital tiers, lot sizes, instrument types, products,
exchanges and strategy structures — so a gap shows up as a row that behaves
differently from its neighbours rather than as a silence nobody notices.

Generated rather than hand-written: eight capital tiers by one story is eight
scenarios that must stay identical in shape, and copying them by hand is how
they drift apart.
"""
from __future__ import annotations

from datetime import timedelta
from typing import List

from ..runner.inject import Fill, losing_trade, round_trip, structure, winning_trade
from ..runner.scenario import Expect, Scenario
from .catalogue import DAY, ROOMY, _flatten, at

NIFTY_CE = "NIFTY26AUG24500CE"
NIFTY_CE_FAR = "NIFTY26AUG24700CE"
NIFTY_PE = "NIFTY26AUG24300PE"
NIFTY_PE_FAR = "NIFTY26AUG24100PE"
NIFTY_ATM_PE = "NIFTY26AUG24500PE"
NIFTY_FUT = "NIFTY26AUGFUT"
BANKNIFTY_CE = "BANKNIFTY26AUG52000CE"
CRUDE_FUT = "CRUDEOIL26AUGFUT"


# ---------------------------------------------------------------------------
# A — capital tiers
# ---------------------------------------------------------------------------
# ₹10k cannot afford one NIFTY lot; ₹1Cr makes a ₹50k loss a rounding error.
# The BEHAVIOUR must be recognised at both ends, even where severity differs.

CAPITAL_TIERS = [
    ("A-01", 10_000, 25), ("A-02", 25_000, 50), ("A-03", 50_000, 50),
    ("A-04", 100_000, 50), ("A-05", 500_000, 100), ("A-06", 1_000_000, 100),
    ("A-07", 2_000_000, 200), ("A-08", 10_000_000, 500),
]


def _capital_scenario(sid: str, capital: int, qty: int) -> Scenario:
    return Scenario(
        id=sid, section="Capital tiers",
        title=f"Losing streak at ₹{capital:,} capital",
        story=f"Five losses in a row, {qty} lots each. Same behaviour, different account size.",
        capital=capital, profile=ROOMY,
        fills=_flatten([
            losing_trade(NIFTY_CE, at(10, 0) + timedelta(minutes=30 * i), qty, 6,
                         hold_minutes=15)
            for i in range(5)
        ]),
        must_fire=[Expect("consecutive_loss_streak",
                          reason="a streak is a streak at ₹10k and at ₹1Cr — "
                                 "thresholds tuned at one tier must not blind the others")],
    )


# ---------------------------------------------------------------------------
# L — lot sizes
# ---------------------------------------------------------------------------
# One lot to a hundred, on fixed capital. Sizing detectors read ratios, so the
# absolute quantity should not change whether a pattern is recognised.

LOT_SIZES = [("L-01", 25), ("L-02", 50), ("L-03", 150), ("L-04", 500), ("L-05", 2500)]


def _lot_scenario(sid: str, qty: int) -> Scenario:
    return Scenario(
        id=sid, section="Lot sizes",
        title=f"Doubling after each loss — base {qty} lots",
        story=f"Martingale from {qty} lots: {qty} → {qty*2} → {qty*4} → {qty*8}.",
        capital=20_000_000, profile=ROOMY,
        fills=_flatten([
            # FOUR steps, not three: the detector needs at least three PRIOR
            # session trades before it will look, so a three-trade martingale is
            # invisible to it by design.
            losing_trade(NIFTY_CE, at(10, 0) + timedelta(minutes=25 * i),
                         qty * (2 ** i), 30, hold_minutes=15)
            for i in range(4)
        ]),
        must_fire=[Expect("martingale_behaviour",
                          reason="the ratio is what matters — base size must not change the verdict")],
    )


# ---------------------------------------------------------------------------
# I — instrument types
# ---------------------------------------------------------------------------
# CE, PE, FUT and EQ take different paths through the parser and the detectors.
# instrument_type was NULL on every live trade until it was fixed; these are the
# scenarios that would have caught it on any of the four.

INSTRUMENTS = [
    ("I-01", NIFTY_CE, "NFO", "MIS", "call option"),
    ("I-02", NIFTY_ATM_PE, "NFO", "MIS", "put option"),
    ("I-03", NIFTY_FUT, "NFO", "MIS", "index future"),
    ("I-04", "RELIANCE", "NSE", "MIS", "intraday equity"),
    ("I-05", CRUDE_FUT, "MCX", "NRML", "commodity future"),
]


def _instrument_scenario(sid: str, symbol: str, exchange: str,
                         product: str, label: str) -> Scenario:
    price = 2900.0 if exchange == "NSE" else (24500.0 if "FUT" in symbol else 120.0)
    # The loss has to clear revenge_min_loss_inr (₹500) or the detector correctly
    # treats it as a scratch. A 7% move on a ₹120 option is ₹420 across 50 lots —
    # under the floor, and the first draft of these scenarios failed on exactly that.
    loss_price = price * 0.5 if price < 1000 else price * 0.95
    return Scenario(
        id=sid, section="Instruments",
        title=f"Revenge re-entry on {label}",
        story=f"A loss on {symbol}, then straight back in at triple size.",
        capital=5_000_000, profile=ROOMY,
        fills=_flatten([
            round_trip(symbol, at(10, 0), 50, price, loss_price, hold_minutes=10,
                       product=product, exchange=exchange),
            round_trip(symbol, at(10, 16), 150, price, price * 0.97, hold_minutes=12,
                       product=product, exchange=exchange),
        ]),
        must_fire=[Expect("revenge_trade",
                          reason=f"the pattern is about timing and size — it must not "
                                 f"depend on the instrument being an option")],
    )


# ---------------------------------------------------------------------------
# P — products
# ---------------------------------------------------------------------------
# MIS is squared off for you; NRML and CNC are not. Only MIS should attract the
# end-of-session pattern, and none of them should change the sizing verdict.

PRODUCTS = [("P-01", "MIS"), ("P-02", "NRML")]


def _product_scenario(sid: str, product: str) -> Scenario:
    exchange, symbol, price = "NFO", NIFTY_CE, 120.0
    return Scenario(
        id=sid, section="Products",
        title=f"Size escalation on {product}",
        story=f"Quantity climbing across losing {product} trades.",
        capital=10_000_000, profile=ROOMY,
        fills=_flatten([
            losing_trade(symbol, at(10, 0) + timedelta(minutes=25 * i),
                         50 + 50 * i, price * 0.05, entry_price=price,
                         hold_minutes=15, product=product, exchange=exchange)
            for i in range(4)
        ]),
        must_fire=[Expect("size_escalation",
                          reason="escalation is escalation whatever the product")],
    )


# ---------------------------------------------------------------------------
# S — strategy structures
# ---------------------------------------------------------------------------
# Each is ONE decision arriving as several fills. None should read as a burst of
# separate trades, and none should trip the sizing or direction detectors —
# eight condor legs counted as eight trades is the defect this guards.

STRUCTURES = [
    ("S-01", "Long straddle", [(NIFTY_CE, "BUY"), (NIFTY_ATM_PE, "BUY")]),
    ("S-02", "Short strangle", [(NIFTY_CE_FAR, "SELL"), (NIFTY_PE_FAR, "SELL")]),
    ("S-03", "Bull call spread", [(NIFTY_CE, "BUY"), (NIFTY_CE_FAR, "SELL")]),
    ("S-04", "Bear put spread", [(NIFTY_PE, "BUY"), (NIFTY_PE_FAR, "SELL")]),
    ("S-05", "Iron condor", [(NIFTY_CE_FAR, "SELL"), (NIFTY_CE, "BUY"),
                             (NIFTY_PE, "SELL"), (NIFTY_PE_FAR, "BUY")]),
    ("S-06", "Hedged long future", [(NIFTY_FUT, "BUY"), (NIFTY_ATM_PE, "BUY")]),
]


def _structure_scenario(sid: str, label: str, legs) -> Scenario:
    return Scenario(
        id=sid, section="Structures",
        title=f"{label} — one decision, {len(legs)} fills",
        story=f"A {label.lower()} entered as a basket, then closed together.",
        capital=5_000_000, profile=ROOMY,
        fills=(
            structure(legs, at(10, 0), 50)
            + structure([(sym, "SELL" if side == "BUY" else "BUY") for sym, side in legs],
                        at(11, 30), 50)
        ),
        must_not_fire=[
            Expect("overtrading_burst",
                   reason="legs of one structure are not separate trades"),
            Expect("direction_instability",
                   reason="opposing legs are the strategy, not a change of mind"),
            Expect("size_escalation", reason="identical size across legs"),
            Expect("fomo_entry", reason="one underlying, however many strikes"),
        ],
    )


# ---------------------------------------------------------------------------
# O — order shapes
# ---------------------------------------------------------------------------

ORDER_SHAPES: List[Scenario] = [
    Scenario(
        id="O-01", section="Order shapes",
        title="Scale in, then scale out",
        story="Builds a position in three adds, unwinds it in three reductions.",
        capital=5_000_000, profile=ROOMY,
        fills=[
            Fill(NIFTY_CE, "BUY", 50, 120.0, at(10, 0), note="open"),
            Fill(NIFTY_CE, "BUY", 50, 118.0, at(10, 10), note="add"),
            Fill(NIFTY_CE, "BUY", 50, 116.0, at(10, 20), note="add"),
            Fill(NIFTY_CE, "SELL", 50, 122.0, at(11, 0), note="trim"),
            Fill(NIFTY_CE, "SELL", 50, 124.0, at(11, 10), note="trim"),
            Fill(NIFTY_CE, "SELL", 50, 126.0, at(11, 20), note="close"),
        ],
        must_not_fire=[
            Expect("overtrading_burst",
                   reason="six fills, one position — building is not trading six times"),
        ],
    ),
    Scenario(
        id="O-02", section="Order shapes",
        title="Position flip — long to short in one order",
        story="Long 50, sells 150: closes the long and opens a short.",
        capital=5_000_000, profile=ROOMY,
        fills=[
            Fill(NIFTY_FUT, "BUY", 50, 24500.0, at(10, 0), note="open long"),
            Fill(NIFTY_FUT, "SELL", 150, 24450.0, at(10, 30), note="flip to short"),
            Fill(NIFTY_FUT, "BUY", 100, 24480.0, at(11, 0), note="cover short"),
        ],
        must_not_fire=[
            Expect("early_exit", reason="a flip is a deliberate reversal, not a cut winner"),
        ],
    ),
    Scenario(
        id="O-03", section="Order shapes",
        title="Overnight hold — entry today, exit tomorrow",
        story="An NRML position opened in the afternoon and closed the next morning.",
        capital=5_000_000, profile=ROOMY,
        fills=[
            Fill(NIFTY_CE, "BUY", 50, 120.0, at(14, 0), product="NRML", note="open"),
            Fill(NIFTY_CE, "SELL", 50, 108.0,
                 at(10, 0, DAY + timedelta(days=1)), product="NRML", note="close next day"),
        ],
        must_not_fire=[
            Expect("end_of_session_mis_panic", reason="NRML is not squared off"),
            Expect("panic_exit", reason="an overnight hold is not a fast reaction"),
        ],
    ),
]


CNC_EXCLUDED = Scenario(
    id="P-03", section="Products",
    title="Delivery trades never reach the engine",
    story="Six CNC equity round trips — a heavy day by any measure.",
    capital=1_000_000, profile=ROOMY,
    fills=_flatten([
        round_trip("RELIANCE", at(10, 0) + timedelta(minutes=25 * i), 100,
                   2900.0, 2820.0, hold_minutes=15, product="CNC", exchange="NSE")
        for i in range(6)
    ]),
    must_not_fire=[
        Expect("daily_overtrading",
               reason="CNC is filtered before any processing (trade_tasks.py) — this "
                      "product is deliberately out of scope, and the scenario records "
                      "that rather than leaving it an unexplained silence"),
        Expect("consecutive_loss_streak", reason="same — delivery is not covered"),
        Expect("same_symbol_obsession", reason="same"),
    ],
)


VARIATION_SCENARIOS: List[Scenario] = (
    [_capital_scenario(sid, cap, qty) for sid, cap, qty in CAPITAL_TIERS]
    + [_lot_scenario(sid, qty) for sid, qty in LOT_SIZES]
    + [_instrument_scenario(*args) for args in INSTRUMENTS]
    + [_product_scenario(sid, p) for sid, p in PRODUCTS]
    + [_structure_scenario(*args) for args in STRUCTURES]
    + ORDER_SHAPES
    + [CNC_EXCLUDED]
)
