"""
`fomo_entry` — breadth across underlyings, one threshold, every context.

WHAT CHANGED, 2026-08-27 (Pattern #7)

There were four thresholds — expiry day 4, market open 2, pre-close 3, otherwise
3 — and on the reference book two of them could not fire at all. Expiry needed 4
distinct underlyings inside 30 minutes and the maximum ever reached across 142
expiry entries was 3, once. Pre-close needed 3 and the maximum across 50 entries
was 2. A threshold above the highest value its own branch has ever produced is
not conservative, it is absent. Both were removed rather than replaced, because
replacing them means inventing a number this book cannot justify.

The market-open threshold of 2 is gone too — the outcome of the mandatory review
it was flagged for. It produced 29 of the detector's 74 firings, 39% of all
output, at 3.6:1 against the general threshold, on a state occurring in 20% of
all entries.

And the cause claim is gone from the copy. A permutation null that keeps each
session's exact entry times and its exact multiset of instruments, permuting
only which was traded when, reproduced the firings almost exactly: 74 observed
against 78.4 expected, ratio 0.94, and 1.02 on the market-open branch. The
flagged trades also win more often than this trader's average, 45.9% against
39.9%.

NOT changed, deliberately: the 30-minute window and the threshold of 3 are
unsourced and were left exactly as they were. Severity stays caution, the
disposition stays alerting.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.models.completed_trade import CompletedTrade
from app.services.behavior_engine import BehaviorEngine, EngineContext

engine = BehaviorEngine()
IST = ZoneInfo("Asia/Kolkata")

#: A Wednesday, so the NIFTY weekly below expires on it only when the symbol
#: says so. Keeps the expiry tests explicit rather than incidental.
DAY = datetime(2025, 8, 27, tzinfo=IST)


def _ct(symbol, hh, mm, instrument_type="CE", exchange="NFO"):
    ct = MagicMock(spec=CompletedTrade)
    ct.id = uuid4()
    ct.broker_account_id = uuid4()
    ct.tradingsymbol = symbol
    ct.exchange = exchange
    ct.direction = "LONG"
    ct.instrument_type = instrument_type
    ct.realized_pnl = Decimal("-100")
    ct.total_quantity = 50
    ct.avg_entry_price = Decimal("200")
    ct.avg_exit_price = Decimal("190")
    ct.entry_time = DAY.replace(hour=hh, minute=mm).astimezone(timezone.utc)
    ct.exit_time = ct.entry_time + timedelta(minutes=5)
    return ct


def _run(trades, thresholds=None):
    """Evaluate the LAST trade with the others as session history."""
    ctx = EngineContext(
        broker_account_id=trades[-1].broker_account_id,
        session=SimpleNamespace(session_pnl=Decimal("0"),
                                session_date=DAY.date(), market_open=None),
        completed_trade=trades[-1],
        session_trades=trades[:-1],
        thresholds=thresholds if thresholds is not None else {},
    )
    return engine._detect_fomo_entry(ctx)


# Three underlyings, all inside half an hour, at a chosen clock time.
def _three(hh, mm, suffix="25AUG"):
    return [
        _ct(f"NIFTY{suffix}25000CE", hh, mm),
        _ct(f"BANKNIFTY{suffix}55000CE", hh, mm + 5),
        _ct(f"RELIANCE{suffix}3000CE", hh, mm + 10),
    ]


def _two(hh, mm, suffix="25AUG"):
    return [
        _ct(f"NIFTY{suffix}25000CE", hh, mm),
        _ct(f"BANKNIFTY{suffix}55000CE", hh, mm + 5),
    ]


# ── one threshold, every context ───────────────────────────────────────────

@pytest.mark.parametrize("hh,mm,where", [
    (9, 20, "market open"),     # inside the opening 30 minutes
    (12, 0, "midday"),          # the general case
    (15, 10, "pre-close"),      # inside the closing 30 minutes
])
def test_three_underlyings_fires_in_every_context(hh, mm, where):
    ev = _run(_three(hh, mm))
    assert ev is not None, f"{where}: three underlyings should fire"
    assert ev.severity == "caution"
    assert ev.context["threshold"] == 3
    assert len(ev.context["distinct_underlyings"]) == 3


@pytest.mark.parametrize("hh,mm,where", [
    (9, 20, "market open"),
    (12, 0, "midday"),
    (15, 10, "pre-close"),
])
def test_two_underlyings_is_silent_in_every_context(hh, mm, where):
    """
    The regression that matters. At market open this used to fire on 2, and that
    single branch produced 39% of the detector's entire output.
    """
    assert _run(_two(hh, mm)) is None, f"{where}: two underlyings must not fire"


def test_the_open_branch_no_longer_has_its_own_threshold():
    """
    Explicitly: the same two trades, one set at 09:20 and one at 12:00, must now
    agree. Before this change they disagreed.
    """
    assert _run(_two(9, 20)) is None
    assert _run(_two(12, 0)) is None


def test_expiry_day_falls_through_to_the_general_threshold():
    """
    Was 4 — unreachable across 142 expiry-day entries whose maximum was 3.
    Three underlyings on an expiry day now fires like any other day.
    """
    ev = _run(_three(12, 0, suffix="25827"))   # weekly expiring 2025-08-27
    assert ev is not None
    assert ev.context["threshold"] == 3


def test_the_context_is_still_reported_even_though_it_does_not_gate():
    """Which stretch of the session a trade landed in is a fact worth keeping."""
    assert _run(_three(9, 20)).context["context_note"] == "market open"
    assert _run(_three(15, 10)).context["context_note"] == "pre-close"
    assert _run(_three(12, 0)).context["context_note"] is None


def test_expiry_day_is_still_detected_and_reported():
    ev = _run(_three(12, 0, suffix="25827"))
    assert ev.context["is_expiry_day"] is True
    assert ev.context["context_note"] == "expiry day"
    assert _run(_three(12, 0)).context["is_expiry_day"] is False


# ── the counting itself is unchanged ───────────────────────────────────────

def test_strikes_of_one_underlying_count_once():
    """Two NIFTY strikes are a structure, not a scatter. The best decision here."""
    trades = [
        _ct("NIFTY25AUG25000CE", 12, 0),
        _ct("NIFTY25AUG25200CE", 12, 5),
        _ct("NIFTY25AUG24800PE", 12, 10),
    ]
    assert _run(trades) is None


def test_the_current_trade_is_included_in_the_count():
    """A threshold of N means N total, not N prior plus the current one."""
    ev = _run(_three(12, 0))
    assert len(ev.context["distinct_underlyings"]) == 3
    assert "RELIANCE" in ev.context["distinct_underlyings"]


def test_trades_outside_the_window_do_not_count():
    trades = [
        _ct("NIFTY25AUG25000CE", 11, 0),        # 60 min earlier
        _ct("BANKNIFTY25AUG55000CE", 12, 0),
        _ct("RELIANCE25AUG3000CE", 12, 5),
    ]
    assert _run(trades) is None, "the NIFTY leg is outside the 30-minute window"


def test_equity_is_not_considered():
    trades = [
        _ct("NIFTY25AUG25000CE", 12, 0),
        _ct("BANKNIFTY25AUG55000CE", 12, 5),
        _ct("INFY", 12, 8, instrument_type="EQ", exchange="NSE"),
    ]
    assert _run(trades) is None


def test_a_single_trade_says_nothing():
    assert _run([_ct("NIFTY25AUG25000CE", 12, 0)]) is None


# ── the window and threshold were left alone ───────────────────────────────

def test_the_window_and_threshold_are_unchanged():
    from app.core.trading_defaults import COLD_START_DEFAULTS as D

    assert D["fomo_window_min"] == 30
    assert D["fomo_symbols_in_window"] == 3


def test_the_threshold_is_still_configurable():
    """Unsourced does not mean hardcoded. A resolved value still overrides."""
    assert _run(_two(12, 0), {"fomo_symbols_in_window": 2}) is not None
    assert _run(_three(12, 0), {"fomo_symbols_in_window": 4}) is None


# ── no fake personalisation ────────────────────────────────────────────────

def test_the_three_context_thresholds_are_gone():
    from app.core.threshold_registry import THRESHOLD_SPECS
    from app.core.trading_defaults import COLD_START_DEFAULTS as D

    for key in ("fomo_symbols_at_open", "fomo_symbols_at_close",
                "fomo_expiry_day_symbols"):
        assert key not in D, f"{key} still resolves"
        assert key not in THRESHOLD_SPECS, f"{key} still declared"


def test_the_registry_no_longer_claims_a_personalisation_it_cannot_perform():
    """
    It was PERSONAL_BASELINE resolving from Source.HISTORY via
    `fomo_underlyings_per_window_p75` — a metric produced by nothing, so every
    trader got the fallback forever while the registry said otherwise.
    """
    from app.core.threshold_registry import THRESHOLD_SPECS
    from app.core.threshold_resolution import Kind

    spec = THRESHOLD_SPECS["fomo_symbols_in_window"]
    assert spec.kind is Kind.FALLBACK
    assert spec.resolution_source is None
    assert spec.metric is None
    assert spec.personalise is False


def test_no_fomo_baseline_metric_is_produced_anywhere():
    """
    If one is ever produced, this test should be the thing that fails — so it
    scans the PRODUCERS. `threshold_registry` is excluded on purpose: it carries
    a comment naming the metric to explain why the classification changed, and a
    comment saying a thing is absent is not that thing being present.
    """
    import inspect

    from app.core import threshold_resolution
    from app.services import baseline_service, behavioral_baseline_service

    for mod in (threshold_resolution, baseline_service,
                behavioral_baseline_service):
        src = inspect.getsource(mod)
        assert "fomo_underlyings" not in src, (
            f"{mod.__name__} now produces a fomo baseline metric; the registry "
            f"classification should be updated from FALLBACK to say so"
        )


# ── the copy makes no claim about why ──────────────────────────────────────
#
# The assertion is about the CLAIM, not the vocabulary. Breadth across
# underlyings is observable; the mental state behind it is not, and the
# permutation null says the timing carries no information about it either (74
# firings observed against 78.4 expected, ratio 0.94). So the copy may describe
# what was counted and may not say what it proves.
#
# The word "fomo" is deliberately NOT banned outright: `fomo_entry` is the
# pattern_type, stored rows carry it, and the registry key is it. It is banned
# as a claim and allowed as an identifier — see the test below.

#: Phrases that assert WHY the trades were taken.
_INTENT_CLAIMS = (
    "chasing", "chase", "chased",
    "impulse", "impulsive",
    "panic", "panicked",
    "focused plan", "not a plan", "lack of a plan", "without a plan",
    "unplanned",
    "indicates fomo", "is fomo", "means fomo", "signals fomo", "suggests fomo",
    "fear of missing out",
    "rather than acting on a view",
)


def _copy_blob():
    from app.services.detector_registry import pattern_copy

    c = pattern_copy("fomo_entry")
    return f"{c.label} {c.observes} {c.explanation}"


@pytest.mark.parametrize("claim", _INTENT_CLAIMS)
def test_the_registry_copy_asserts_no_intent(claim):
    blob = _copy_blob().lower()
    assert claim not in blob, f"registry copy asserts intent: {claim!r}"


@pytest.mark.parametrize("claim", _INTENT_CLAIMS)
def test_the_alert_message_asserts_no_intent(claim):
    assert claim not in _run(_three(12, 0)).message.lower(), (
        f"alert message asserts intent: {claim!r}"
    )


def test_the_word_fomo_appears_only_as_the_identifier():
    """
    Not a vocabulary ban. `fomo_entry` is the pattern_type and is load-bearing —
    historical alert rows carry it and the registry is keyed on it, so copy that
    names the pattern is legitimate. What must not happen is the word being used
    to tell the trader what their breadth means.
    """
    for label, text in (("registry copy", _copy_blob()),
                        ("alert message", _run(_three(12, 0)).message)):
        residue = text.lower().replace("fomo_entry", "")
        assert "fomo" not in residue, (
            f"{label} uses 'fomo' as a claim rather than as the pattern name: "
            f"{text!r}"
        )


def test_the_message_still_says_the_useful_part():
    """Stripping the claim must not strip the facts."""
    ev = _run(_three(12, 0))
    assert "3 different underlyings" in ev.message
    assert "30 min" in ev.message
    assert "NIFTY" in ev.message and "BANKNIFTY" in ev.message


def test_the_copy_still_explains_what_is_measured():
    """A pattern with no explanation renders as a bare label."""
    from app.services.detector_registry import pattern_copy

    c = pattern_copy("fomo_entry")
    assert "underlying" in c.observes.lower()
    assert len(c.explanation.strip()) > 20


# ── unchanged behaviour that must stay unchanged ───────────────────────────

def test_severity_and_disposition_were_not_touched():
    from app.services.detector_registry import BY_NAME

    spec = BY_NAME["fomo_entry"]
    assert spec.disposition == "alerting"
    assert spec.nature == "emotional"
    assert _run(_three(12, 0)).severity == "caution"


def test_the_detector_is_still_pure():
    import inspect

    src = inspect.getsource(engine._detect_fomo_entry)
    for forbidden in ("await ", "db.", "select("):
        assert forbidden not in src


def test_a_non_nfo_exchange_still_uses_its_own_session_bounds():
    """
    Hardcoding 09:15/15:30 made mins_after_open negative for MCX mornings and
    silently disabled both windows. The bounds still come from the instrument's
    own exchange. The detector judges the LAST trade, so the set below ends at
    09:40: 25 minutes after the NSE open and therefore inside its window, but 40
    minutes after MCX's 09:00 open and therefore outside.
    """
    nfo = _run(_three(9, 30))
    assert nfo.context["context_note"] == "market open"

    mcx = [_ct(t.tradingsymbol, 9, 30 + i * 5, exchange="MCX")
           for i, t in enumerate(_three(9, 30))]
    ev = _run(mcx)
    assert ev is not None, "the count is unaffected by the exchange"
    assert ev.context["context_note"] is None, (
        "MCX opens at 09:00, so 09:40 is past its opening 30 minutes"
    )
