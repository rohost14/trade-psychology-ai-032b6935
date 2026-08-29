"""
Semantic scenarios — plain Python, real engine code, no database.

WHAT THIS IS

A characterization harness. It runs the REAL detectors and the REAL semantic
primitives over hand-built positions covering trader situations the reference
book does not contain, and records what the engine currently does.

WHAT THIS IS NOT

**It is not a specification.** The recorded baseline includes behaviour the
Trading Semantics audit found to be wrong. Phase 1 fixes are EXPECTED to change
these snapshots — a diff here is the signal that a fix landed, not a regression.
Read `docs/DEEP_REVIEW/SEMANTIC_CONTRACT.md` for what the values SHOULD be.

WHY IN-PROCESS RATHER THAN SYNTHETIC TRADES IN THE DATABASE

The 203-session replay failed six times in two days (network drops, task
reaping, a 3h20m I/O hang) and left partial synthetic rows behind three times.
This runs in seconds, touches no shared state, and is deterministic — so a
before/after comparison is actually obtainable.

THREE LAYERS, matching the semantic contract

  L1 primitives   parse_symbol, classify_legs, count_structures,
                  estimate_capital_at_risk, _compute_fill_effect
  L2 lifecycle    fill sequences -> position state (the ledger's pure function)
  L3 detectors    the real detector methods over built CompletedTrades

Coverage limits are declared honestly in `COVERAGE_LIMITS` at the bottom: some
scenarios (multi-account, MTF margin, missing broker metadata) live in sync and
DB paths that no in-process harness can exercise.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from uuid import UUID

IST = timezone(timedelta(hours=5, minutes=30))

#: Fixed so snapshots are byte-stable. Never use uuid4() in this file.
ACCOUNT_A = UUID("00000000-0000-4000-8000-0000000000a1")
ACCOUNT_B = UUID("00000000-0000-4000-8000-0000000000b2")

DAY = datetime(2026, 3, 12, tzinfo=IST).date()


def _t(h: int, m: int, day_offset: int = 0):
    return datetime(2026, 3, 12, h, m, tzinfo=IST) + timedelta(days=day_offset)


_SEQ = [0]


def trade(
    symbol: str,
    *,
    direction: str = "LONG",
    qty: int = 75,
    entry: float = 100.0,
    exit_: float = 100.0,
    entry_at=None,
    exit_at=None,
    product: str = "MIS",
    exchange: str = "NFO",
    instrument_type: Optional[str] = None,
    num_entries: int = 1,
    account: UUID = ACCOUNT_A,
) -> SimpleNamespace:
    """One CompletedTrade, as the engine sees it. Deterministic id."""
    from app.services.instrument_parser import parse_symbol

    if instrument_type is None:
        try:
            instrument_type = parse_symbol(symbol).instrument_type or "EQ"
        except Exception:
            instrument_type = "EQ"

    sign = 1 if direction == "LONG" else -1
    pnl = (exit_ - entry) * qty * sign

    _SEQ[0] += 1
    return SimpleNamespace(
        id=UUID(int=_SEQ[0]),
        broker_account_id=account,
        tradingsymbol=symbol,
        exchange=exchange,
        product=product,
        instrument_type=instrument_type,
        direction=direction,
        total_quantity=qty,
        avg_entry_price=Decimal(str(entry)),
        avg_exit_price=Decimal(str(exit_)),
        realized_pnl=Decimal(str(round(pnl, 2))),
        pnl_pct=round((exit_ - entry) / entry * 100 * sign, 4) if entry else None,
        entry_time=entry_at or _t(9, 30),
        exit_time=exit_at or _t(10, 0),
        duration_minutes=30,
        num_entries=num_entries,
        num_exits=1,
        closed_by_flip=False,
        status="closed",
        quality_score=None,
        exit_trade_ids=[],
        entry_trade_ids=[],
    )


def leg(symbol: str, direction: str = "LONG"):
    """A LegView-shaped input for classify_legs."""
    from app.services.strategy_detector import LegView

    return LegView(symbol, direction)


# ---------------------------------------------------------------------------
# The scenarios. Each returns the pieces a layer needs.
# ---------------------------------------------------------------------------

#: L1 — structure classification. (name, [(symbol, direction), ...])
STRUCTURE_SCENARIOS: List[tuple] = [
    ("long_call_alone",            [("RELIANCE25MAR2900CE", "LONG")]),
    ("long_put_alone",             [("RELIANCE25MAR2900PE", "LONG")]),
    ("short_call_alone",           [("RELIANCE25MAR2900CE", "SHORT")]),
    ("short_put_alone",            [("RELIANCE25MAR2900PE", "SHORT")]),

    # the brief's explicit list
    ("ce_long_pe_long_straddle",   [("RELIANCE25MAR2900CE", "LONG"),
                                    ("RELIANCE25MAR2900PE", "LONG")]),
    ("ce_long_pe_short",           [("RELIANCE25MAR2900CE", "LONG"),
                                    ("RELIANCE25MAR2900PE", "SHORT")]),
    ("fut_long_pe_long_hedge",     [("RELIANCE25MARFUT", "LONG"),
                                    ("RELIANCE25MAR2900PE", "LONG")]),
    ("fut_long_pe_SHORT_riskadd",  [("RELIANCE25MARFUT", "LONG"),
                                    ("RELIANCE25MAR2900PE", "SHORT")]),
    ("fut_short_ce_long_hedge",    [("RELIANCE25MARFUT", "SHORT"),
                                    ("RELIANCE25MAR2900CE", "LONG")]),
    ("fut_short_ce_SHORT_riskadd", [("RELIANCE25MARFUT", "SHORT"),
                                    ("RELIANCE25MAR2900CE", "SHORT")]),
    ("nifty_fut_option_hedge",     [("NIFTY25MARFUT", "LONG"),
                                    ("NIFTY25MAR25000PE", "LONG")]),
    ("short_call_long_call_spread", [("NIFTY25MAR25000CE", "SHORT"),
                                     ("NIFTY25MAR25200CE", "LONG")]),
    ("short_put_long_put_spread",  [("NIFTY25MAR25000PE", "SHORT"),
                                    ("NIFTY25MAR24800PE", "LONG")]),
    ("strangle_long",              [("NIFTY25MAR25200CE", "LONG"),
                                    ("NIFTY25MAR24800PE", "LONG")]),
    ("iron_condor_4leg",           [("NIFTY25MAR25200CE", "SHORT"),
                                    ("NIFTY25MAR25400CE", "LONG"),
                                    ("NIFTY25MAR24800PE", "SHORT"),
                                    ("NIFTY25MAR24600PE", "LONG")]),
    ("iron_butterfly_4leg",        [("NIFTY25MAR25000CE", "SHORT"),
                                    ("NIFTY25MAR25000PE", "SHORT"),
                                    ("NIFTY25MAR25400CE", "LONG"),
                                    ("NIFTY25MAR24600PE", "LONG")]),
    ("butterfly_3leg",             [("NIFTY25MAR24800CE", "LONG"),
                                    ("NIFTY25MAR25000CE", "SHORT"),
                                    ("NIFTY25MAR25200CE", "LONG")]),
    # cross-expiry
    ("calendar_same_strike",       [("NIFTY25MAR25000CE", "SHORT"),
                                    ("NIFTY25APR25000CE", "LONG")]),
    ("calendar_same_direction",    [("NIFTY25MAR25000CE", "LONG"),
                                    ("NIFTY25APR25000CE", "LONG")]),
    ("diagonal_diff_strike",       [("NIFTY25MAR25000CE", "SHORT"),
                                    ("NIFTY25APR25200CE", "LONG")]),
    ("futures_rollover",           [("NIFTY25MARFUT", "LONG"),
                                    ("NIFTY25APRFUT", "SHORT")]),
    ("weekly_opt_monthly_fut",     [("NIFTY25MARFUT", "LONG"),
                                    ("NIFTY2532025000PE", "LONG")]),
    # equity
    ("covered_call_eq_plus_ce",    [("RELIANCE", "LONG"),
                                    ("RELIANCE25MAR2900CE", "SHORT")]),
    ("protective_put_eq_plus_pe",  [("RELIANCE", "LONG"),
                                    ("RELIANCE25MAR2900PE", "LONG")]),
    # ratio — quantity is invisible to the classifier, which is the point
    ("ratio_spread_1x2",           [("NIFTY25MAR25000CE", "LONG"),
                                    ("NIFTY25MAR25200CE", "SHORT")]),
    ("unknown_pair_two_calls",     [("NIFTY25MAR25000CE", "LONG"),
                                    ("NIFTY25MAR25100CE", "LONG")]),
]

#: L1 — capital at risk. (name, instrument_type, symbol, direction, price, qty)
RISK_SCENARIOS: List[tuple] = [
    ("long_option",        "CE",  "NIFTY25MAR25000CE", "LONG",  120.0, 75),
    ("short_option",       "CE",  "NIFTY25MAR25000CE", "SHORT", 120.0, 75),
    ("long_put",           "PE",  "NIFTY25MAR25000PE", "LONG",  120.0, 75),
    ("short_put",          "PE",  "NIFTY25MAR25000PE", "SHORT", 120.0, 75),
    ("futures_long",       "FUT", "NIFTY25MARFUT",     "LONG",  25000.0, 75),
    ("futures_short",      "FUT", "NIFTY25MARFUT",     "SHORT", 25000.0, 75),
    ("equity_long",        "EQ",  "RELIANCE",          "LONG",  2900.0, 100),
    ("equity_short",       "EQ",  "RELIANCE",          "SHORT", 2900.0, 100),
    ("mcx_lot_multiplier", "FUT", "ZINC25MARFUT",      "LONG",  280.0, 5),
    ("unparseable_symbol", None,  "WEIRD~SYMBOL",      "LONG",  100.0, 10),
]

#: L2 — fill lifecycle. (name, [(qty, price), ...]) signed qty, +buy/-sell
LIFECYCLE_SCENARIOS: List[tuple] = [
    ("open_then_close",            [(75, 100.0), (-75, 110.0)]),
    ("add_then_close",             [(75, 100.0), (75, 60.0), (-150, 50.0)]),
    ("partial_exit_then_close",    [(150, 100.0), (-75, 110.0), (-75, 90.0)]),
    ("multi_entry_partial_exits",  [(75, 100.0), (75, 90.0), (-50, 95.0),
                                    (-100, 85.0)]),
    ("reduce_then_add_then_close", [(150, 100.0), (-50, 105.0), (50, 95.0),
                                    (-150, 98.0)]),
    ("long_to_short_flip",         [(75, 100.0), (-150, 90.0), (75, 85.0)]),
    ("short_to_long_flip",         [(-75, 100.0), (150, 110.0), (-75, 115.0)]),
    ("short_cover_reenter",        [(-75, 100.0), (75, 95.0), (-75, 98.0),
                                    (75, 92.0)]),
    ("close_and_reopen_same",      [(75, 100.0), (-75, 105.0), (75, 103.0),
                                    (-75, 108.0)]),
    ("net_zero_same_instant",      [(75, 100.0), (-75, 100.0)]),
    ("over_closing_flip_2_exits",  [(100, 100.0), (-50, 90.0), (-200, 70.0)]),
]


def detector_scenarios() -> List[Dict[str, Any]]:
    """
    L3 — real detectors over built positions.

    Each entry: {name, subject, priors, thresholds, note}. `subject` is the
    CompletedTrade being analysed; `priors` are earlier trades in the session.
    """
    S: List[Dict[str, Any]] = []

    def add(name, subject, priors=None, thresholds=None, note=""):
        S.append({"name": name, "subject": subject, "priors": priors or [],
                  "thresholds": thresholds or {}, "note": note})

    # ── long vs short option, same loss shape ────────────────────────────
    add("long_option_50pct_loss",
        trade("NIFTY25MAR25000CE", direction="LONG", entry=120, exit_=60),
        note="baseline: the archetype every threshold was fitted to")
    add("short_option_premium_tripled",
        trade("NIFTY25MAR25000CE", direction="SHORT", entry=120, exit_=360),
        note="writer's loss is 2x premium received; contract says risk != premium")

    # ── futures ──────────────────────────────────────────────────────────
    add("futures_long_small_adverse_move",
        trade("NIFTY25MARFUT", direction="LONG", entry=25000, exit_=24800, qty=75),
        note="0.8% index move; option-style percentage logic must not apply")
    add("futures_short_adverse",
        trade("NIFTY25MARFUT", direction="SHORT", entry=25000, exit_=25200, qty=75))

    # ── averaging down: the denominator question ─────────────────────────
    add("no_add_50pct_loss",
        trade("NIFTY25MAR25000CE", entry=100, exit_=50, qty=75),
        note="loses 3,750")
    add("averaged_down_worse_money_smaller_pct",
        trade("NIFTY25MAR25000CE", entry=80, exit_=50, qty=150, num_entries=2),
        note="loses 4,500 - MORE money, smaller percentage")

    # ── reversal / re-entry / obsession ──────────────────────────────────
    ce_loser = trade("NIFTY25MAR25000CE", entry=100, exit_=70,
                     entry_at=_t(10, 0), exit_at=_t(10, 5))
    add("ce_loss_then_pe_buy_reversal",
        trade("NIFTY25MAR25000PE", entry=90, exit_=95,
              entry_at=_t(10, 8), exit_at=_t(10, 30)),
        priors=[ce_loser],
        note="CE->PE: brief says this must NOT be direction instability")
    add("ce_loss_then_other_strike_ce",
        trade("NIFTY25MAR25100CE", entry=95, exit_=99,
              entry_at=_t(10, 8), exit_at=_t(10, 30)),
        priors=[ce_loser],
        note="the canonical revenge shape, 3 min later")

    # ── same underlying, different contract ──────────────────────────────
    mar = trade("NIFTY25MARFUT", direction="LONG", entry=25000, exit_=24900,
                qty=75, entry_at=_t(9, 20), exit_at=_t(9, 50))
    add("futures_roll_to_next_month",
        trade("NIFTY25APRFUT", direction="LONG", entry=25100, exit_=25150,
              qty=75, entry_at=_t(9, 55), exit_at=_t(11, 0)),
        priors=[mar],
        note="a roll, not a re-entry")
    add("same_underlying_different_strike",
        trade("NIFTY25MAR25200CE", entry=80, exit_=85, entry_at=_t(11, 0)),
        priors=[trade("NIFTY25MAR25000CE", entry=100, exit_=70,
                      entry_at=_t(10, 0), exit_at=_t(10, 30))])

    # ── session scope: opened before today vs today ──────────────────────
    add("opened_yesterday_closed_today",
        trade("NIFTY25MAR25000CE", entry=100, exit_=80,
              entry_at=_t(14, 0, day_offset=-1), exit_at=_t(10, 0),
              product="NRML"),
        note="closed today, NOT opened today")
    add("opened_and_closed_today",
        trade("NIFTY25MAR25000CE", entry=100, exit_=80,
              entry_at=_t(9, 30), exit_at=_t(10, 0)))

    # ── expiry day ───────────────────────────────────────────────────────
    add("expiry_day_position",
        trade("NIFTY2531225000CE", entry=60, exit_=20,
              entry_at=_t(13, 30), exit_at=_t(15, 0)),
        note="12 Mar 2026 is this symbol's own expiry")

    # ── MTF ──────────────────────────────────────────────────────────────
    add("mtf_equity_position",
        trade("RELIANCE", direction="LONG", entry=2900, exit_=2850, qty=100,
              product="MTF", exchange="NSE", instrument_type="EQ"),
        thresholds={"trading_capital": 100000.0},
        note="leverage is the instrument's purpose; 2.9L notional on 1L capital")
    add("cash_equity_no_mtf",
        trade("RELIANCE", direction="LONG", entry=2900, exit_=2850, qty=100,
              product="NRML", exchange="NSE", instrument_type="EQ"),
        thresholds={"trading_capital": 100000.0})

    # ── missing / unknown metadata ───────────────────────────────────────
    t_missing = trade("NIFTY25MAR25000CE", entry=100, exit_=50)
    t_missing.instrument_type = None
    t_missing.direction = None
    add("missing_instrument_type_and_direction", t_missing,
        note="contract: UNKNOWN must not become a behavioural claim")

    t_unparseable = trade("WEIRD~SYMBOL", entry=100, exit_=50,
                          instrument_type=None)
    add("unparseable_symbol", t_unparseable,
        note="parse_symbol returns EQ for anything it cannot read")

    t_nodur = trade("NIFTY25MAR25000CE", entry=100, exit_=50)
    t_nodur.duration_minutes = None
    add("missing_duration", t_nodur)

    # ── multiple positions / accounts ────────────────────────────────────
    add("two_unrelated_underlyings",
        trade("TCS25MAR3500CE", entry=50, exit_=40, entry_at=_t(11, 0)),
        priors=[trade("RELIANCE25MAR2900CE", entry=100, exit_=80,
                      entry_at=_t(10, 0), exit_at=_t(10, 30))],
        note="simultaneous unrelated positions must not interact")
    add("other_account_priors_ignored",
        trade("NIFTY25MAR25000CE", entry=100, exit_=70, account=ACCOUNT_A),
        priors=[trade("NIFTY25MAR25000CE", entry=100, exit_=70,
                      account=ACCOUNT_B, entry_at=_t(9, 40),
                      exit_at=_t(9, 50))],
        note="engine is account-scoped; B's trades must not affect A")

    return S


#: Declared honestly — these need paths an in-process harness cannot reach.
COVERAGE_LIMITS = {
    "multi_account_aggregation":
        "Detectors are account-scoped by construction. The harness can show "
        "account A ignores account B's trades, but cross-account aggregation "
        "does not exist to be tested.",
    "mtf_margin_semantics":
        "No leverage model exists and broker margin is never consumed, so "
        "there is no MTF risk behaviour to baseline - only its absence.",
    "partial_exit_emission":
        "A partial exit produces no CompletedTrade. L2 shows the fill effect; "
        "L3 cannot show a detector reaction because none is produced.",
    "exit_order_types":
        "Populated from a DB lookup keyed on exit_trade_ids. The harness sets "
        "it explicitly to characterise both branches rather than reproduce "
        "the ID-space bug, which is a persistence defect, not a logic one.",
    "strategy_group_creation":
        "Requires _find_siblings against stored CompletedTrades. The harness "
        "exercises classify_legs directly and passes strategy_group to "
        "detectors explicitly.",
    "live_tick_path":
        "live_risk_state is covered by its own end-to-end tests.",
}
