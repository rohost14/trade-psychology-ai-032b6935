"""
`options_premium_avg_down` is retired. These tests hold the retirement in place
AND prove the behaviour its copy promised is still covered.

WHY IT WAS RETIRED (2026-08-30, Pattern 20)

IT WAS NOT AN AVERAGE-DOWN. NOT ONCE.

It fired on a NEW long option entry when any OTHER long option on the same
UNDERLYING had closed that session with a realised loss >= 20% of premium. Not
the same contract, not the same strike, not even the same option type; no open
position, no fill sequence.

    firings where any "prior loser" was still an OPEN position:  0 of 44

Averaging down means adding to a position you still hold, so by construction it
could never observe one. Its own threshold comment said so, and so did the
engine's index. Only the trader-facing copy claimed otherwise - and it claimed
ANOTHER detector's mechanism: "Additional quantity on an option position already
down on premium." That is `adding_to_adverse_position`, verbatim. The same
failure retired `cooldown_violation` at Pattern 15.

AND `adding_to_adverse_position` ALREADY IS THE OPTION-PREMIUM-AVERAGING
DETECTOR: all 64 of its 64 firings on the book are LONG options. There was
nothing to consolidate - the option case is not a subset of the retired
detector's output, it is the whole of the surviving one's.

What the 44 firings were:
     21  a prior loser was the same contract, re-entered after closing
     23  a prior loser was a different option entirely
      9  EVERY prior loser was the opposite type - a CE after a PE lost, a
         change of view, the call `direction_instability` was retired for
         being unable to make
      5  LOOK-AHEAD - `session_trades` is EXIT-ordered, so a "prior" position
         can still have been OPEN at this trade's entry. For those, the message
         "You entered X AFTER N losing positions" was false.

Real subject was re-entry after a loss, owned by `same_symbol_obsession` (70%
of firings) and `revenge_trade` (48%). Alone on 7 of 44, of which 3 were
direction changes and 2 look-ahead - leaving TWO coherent firings in 175
sessions, both already seen at contract level.

Evidence: docs/patterns/20-options_premium_avg_down/.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

APP = Path(__file__).resolve().parents[1] / "app"

RETIRED = "options_premium_avg_down"


# ── 1. it cannot generate new events ───────────────────────────────────────

def test_the_detector_method_is_gone():
    from app.services.behavior_engine import BehaviorEngine

    assert not hasattr(BehaviorEngine(), "_detect_options_premium_avg_down")


def test_it_is_not_in_the_registry_or_the_vocabulary():
    from app.services.detector_registry import (
        ALIASES, BY_NAME, PATTERN_COPY, REGISTRY, all_pattern_types,
    )

    assert RETIRED not in BY_NAME
    assert RETIRED not in ALIASES
    assert RETIRED not in all_pattern_types()
    assert RETIRED not in PATTERN_COPY
    assert all(d.name != RETIRED for d in REGISTRY)


def test_no_registry_spec_points_at_the_deleted_method():
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import REGISTRY

    engine = BehaviorEngine()
    for spec in REGISTRY:
        assert spec.method != "_detect_options_premium_avg_down"
        assert hasattr(engine, spec.method), f"{spec.name} points at a missing method"


def test_the_engine_counts_are_what_the_retirement_left():
    from app.services.detector_registry import ALIASES, REGISTRY, all_pattern_types

    assert len(REGISTRY) == 15
    assert len(ALIASES) == 5
    assert len(all_pattern_types()) == 20


def test_it_is_recorded_as_retired():
    from tests.test_pattern_contract import RETIRED_PATTERN_NAMES

    assert RETIRED in RETIRED_PATTERN_NAMES


def test_its_threshold_is_gone_and_unreplaced():
    from app.core.threshold_registry import THRESHOLD_SPECS
    from app.core.trading_defaults import COLD_START_DEFAULTS

    assert "premium_avg_down_loss_pct" not in COLD_START_DEFAULTS
    assert "premium_avg_down_loss_pct" not in THRESHOLD_SPECS
    assert not any("premium_avg_down" in k for k in COLD_START_DEFAULTS)


def test_no_live_module_reads_the_deleted_threshold():
    offenders = []
    for path in APP.rglob("*.py"):
        if "__pycache__" in path.parts or "_archive" in path.parts:
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1
        ):
            if line.lstrip().startswith("#"):
                continue
            if "premium_avg_down_loss_pct" in line:
                offenders.append(f"{path.relative_to(APP)}:{lineno}")
    assert offenders == [], f"deleted threshold still read: {offenders}"


def test_it_is_no_longer_entry_decidable():
    from app.services.entry_detectors import ENTRY_DECIDABLE

    assert RETIRED not in ENTRY_DECIDABLE


# ── 2. THE BEHAVIOUR ITS COPY PROMISED IS STILL COVERED ────────────────────
#
# The half of this retirement that matters. The copy said "additional quantity
# on an option position already down on premium". That is exactly what
# `adding_to_adverse_position` does, and it must keep doing it for options.

def _fill(et, qty, price, after, avg_after, at):
    from app.core.position_fills import PositionFill
    return PositionFill(entry_type=et, fill_qty=qty, fill_price=price,
                        position_qty_after=after, avg_entry_price_after=avg_after,
                        occurred_at=at)


def test_adding_to_adverse_position_still_catches_option_premium_averaging():
    """
    A long CE bought at 100, then added to at 70 - premium already 30% down.
    This is the sentence the retired detector's copy promised and never
    delivered.
    """
    from app.core.trading_defaults import COLD_START_DEFAULTS
    from app.services.behavior_engine import BehaviorEngine, EngineContext

    engine = BehaviorEngine()
    now = datetime(2026, 4, 15, 11, 0, tzinfo=timezone.utc)
    acct = uuid4()

    ct = SimpleNamespace(
        id=uuid4(), broker_account_id=acct, tradingsymbol="NIFTY25APR24000CE",
        exchange="NFO", product="MIS", instrument_type="CE", direction="LONG",
        total_quantity=150, avg_entry_price=Decimal("85"),
        avg_exit_price=Decimal("60"), realized_pnl=Decimal("-3750"),
        pnl_pct=None, duration_minutes=45,
        entry_time=now - timedelta(minutes=45), exit_time=now,
        num_entries=2, num_exits=1, status="closed", quality_score=None)

    fills = [
        _fill("OPEN", 75, 100.0, 75, 100.0, now - timedelta(minutes=45)),
        _fill("INCREASE", 75, 70.0, 150, 85.0, now - timedelta(minutes=20)),
        _fill("CLOSE", -150, 60.0, 0, None, now),
    ]

    ctx = EngineContext(
        broker_account_id=acct,
        session=SimpleNamespace(session_pnl=Decimal("-3750"),
                                session_date=now.date(), market_open=None),
        completed_trade=ct, session_trades=[ct],
        thresholds=dict(COLD_START_DEFAULTS),
        position_fills=fills)

    result = engine._detect_adding_to_adverse_position(ctx)
    assert getattr(result, "fired", bool(result)), (
        "the behaviour the retired detector's COPY described must still be "
        "caught - it was always this detector's job")

    ev = getattr(result, "event", None) or result
    assert "NIFTY25APR24000CE" in (ev.message or "")


def test_adding_to_adverse_position_is_untouched_for_non_options():
    """
    The retirement must not have narrowed it. A futures position built the same
    way still reports.
    """
    from app.core.trading_defaults import COLD_START_DEFAULTS
    from app.services.behavior_engine import BehaviorEngine, EngineContext

    engine = BehaviorEngine()
    now = datetime(2026, 4, 15, 11, 0, tzinfo=timezone.utc)
    acct = uuid4()

    ct = SimpleNamespace(
        id=uuid4(), broker_account_id=acct, tradingsymbol="NIFTY25APRFUT",
        exchange="NFO", product="NRML", instrument_type="FUT", direction="LONG",
        total_quantity=150, avg_entry_price=Decimal("23900"),
        avg_exit_price=Decimal("23800"), realized_pnl=Decimal("-15000"),
        pnl_pct=None, duration_minutes=60,
        entry_time=now - timedelta(minutes=60), exit_time=now,
        num_entries=2, num_exits=1, status="closed", quality_score=None)

    fills = [
        _fill("OPEN", 75, 24000.0, 75, 24000.0, now - timedelta(minutes=60)),
        _fill("INCREASE", 75, 23800.0, 150, 23900.0, now - timedelta(minutes=30)),
        _fill("CLOSE", -150, 23800.0, 0, None, now),
    ]

    ctx = EngineContext(
        broker_account_id=acct,
        session=SimpleNamespace(session_pnl=Decimal("-15000"),
                                session_date=now.date(), market_open=None),
        completed_trade=ct, session_trades=[ct],
        thresholds=dict(COLD_START_DEFAULTS),
        position_fills=fills)

    result = engine._detect_adding_to_adverse_position(ctx)
    assert getattr(result, "fired", bool(result)), (
        "non-option behaviour must be unchanged by an options retirement")


def test_the_detectors_that_own_the_real_subject_survive():
    """Re-entry after a loss on one underlying - 70% and 48% of the firings."""
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import BY_NAME

    engine = BehaviorEngine()
    for name in ("same_symbol_obsession", "revenge_trade",
                 "adding_to_adverse_position"):
        assert name in BY_NAME, name
        assert hasattr(engine, BY_NAME[name].method), name


# ── 3. the docstring that justified a shared helper was corrected ──────────

def test_fill_classification_names_the_detector_that_actually_reads_it():
    """
    Its docstring justified the whole function by naming the detectors that
    need winner-adds and loser-adds kept apart, and one of the two was this
    detector - which never read the classification and never saw an open
    position. The surviving reader is `adding_to_adverse_position`.
    """
    src = (APP / "services" / "fill_classification.py").read_text(encoding="utf-8")

    body = src[src.index("def "):]
    assert "adding_to_adverse_position and martingale_behaviour exist to catch" in body
    assert "options_premium_avg_down exist to catch" not in body


# ── 4. the analytics surface is dead on a timer, NOT broken ────────────────

def test_the_options_behavior_endpoint_is_kept_for_historical_rows():
    """
    Deliberately NOT removed with the detector, and the reasoning is pinned so
    a later pass does not read the empty card as a bug and 'fix' it by
    repointing - which would silently change what its sections mean.

    Stored RiskAlert rows still exist and are still true. Once they age out the
    card renders NOTHING rather than three zeroes, and BehaviorTab folds that
    into its own empty state - so there is no misleading empty surface.
    """
    src = (APP / "api" / "analytics.py").read_text(encoding="utf-8")

    assert 'OPTIONS_PATTERNS = (' in src
    assert '"options_premium_avg_down",   # retired; historical rows only' in src
    assert "dead on a timer, not broken" in src


def test_the_card_hides_itself_rather_than_rendering_zeroes():
    card = (Path(__file__).resolve().parents[2] / "src" / "components" /
            "analytics" / "OptionsBehaviorCard.tsx")
    if not card.exists():
        return
    text = card.read_text(encoding="utf-8")
    assert "if (!data?.has_data) return null;" in text, (
        "the no-misleading-empty guarantee depends on this line")


# ── 5. historical rows stay readable ───────────────────────────────────────

def test_the_report_labels_survive_for_stored_rows():
    daily = (APP / "services" / "daily_reports_service.py").read_text(encoding="utf-8")
    assert '"options_premium_avg_down": "Premium averaging down"' in daily


def test_the_frontend_can_still_name_a_stored_row():
    ctx = Path(__file__).resolve().parents[2] / "src" / "contexts" / "AlertContext.tsx"
    if not ctx.exists():
        return
    text = ctx.read_text(encoding="utf-8")

    routing = text[text.index("const BACKEND_TO_FRONTEND_TYPE"):]
    routing = routing[:routing.index("\n};")]
    assert "'options_premium_avg_down':" not in routing, (
        "the engine cannot emit it, so the routing map must not name it")

    assert "'options_premium_avg_down':      'Premium Averaging Down'" in text, (
        "stored rows must still render a human name")
