"""
An alert must be explainable from what was stored, not from prose.

WHY

The stored record held the message, the severity and the detector's own
free-form context — but not the numbers the trade was judged against. That was
survivable while every threshold was a constant you could go and read. It is not
survivable now: thresholds resolve through a six-rung ladder, personal baselines
move as the trader trades, and adaptation is capped per period. The value that
fired an alert on Tuesday may not exist anywhere by Friday.

"Why did this fire?" then has no answer — and it has no answer *silently*, since
the alert still renders perfectly well.

These tests hold the line that a stored event carries its own thresholds and
their provenance.
"""
from datetime import timedelta
from decimal import Decimal

import pytest

from app.core import session_facts
from app.core.threshold_recorder import RecordingThresholds
from app.models.completed_trade import CompletedTrade
from app.services.behavior_engine import BehaviorEngine

engine = BehaviorEngine()


async def _loss(db, broker, minute, pnl=-2000):
    exit_at = session_facts.session_start(session_facts.session_date_now()) + timedelta(
        minutes=minute
    )
    ct = CompletedTrade(
        broker_account_id=broker.id,
        tradingsymbol="NIFTY25JANFUT",
        exchange="NFO",
        instrument_type="FUT",
        product="MIS",
        direction="LONG",
        total_quantity=50,
        num_entries=1,
        num_exits=1,
        avg_entry_price=Decimal("22000"),
        avg_exit_price=Decimal("21960"),
        realized_pnl=Decimal(str(pnl)),
        entry_time=exit_at - timedelta(minutes=15),
        exit_time=exit_at,
        duration_minutes=15,
        status="closed",
    )
    db.add(ct)
    await db.flush()
    return ct


# ── the recorder itself ────────────────────────────────────────────────────


def test_it_records_only_what_was_read():
    t = RecordingThresholds({"a": 1, "b": 2, "c": 3})
    t.start_recording()
    t.get("a")
    t["b"]
    assert t.keys_read() == {"a", "b"}
    assert set(t.provenance()) == {"a", "b"}


def test_membership_counts_as_a_read():
    """A detector branching on presence has used the key to decide."""
    t = RecordingThresholds({"a": 1})
    t.start_recording()
    assert "a" in t
    assert t.keys_read() == {"a"}


def test_a_key_that_does_not_exist_records_nothing():
    """`.get("maybe")` returning None says nothing worth storing."""
    t = RecordingThresholds({"a": 1})
    t.start_recording()
    t.get("nope")
    assert t.provenance() == {}


def test_provenance_without_a_ladder_record_says_unknown():
    """
    Silence about origin is worse than an explicit "unknown" — a threshold whose
    source we cannot state is exactly the one worth flagging.
    """
    t = RecordingThresholds({"a": 1})
    t.start_recording()
    t.get("a")
    assert t.provenance()["a"]["source"] == "unknown"


def test_values_survive_the_json_round_trip():
    """Evidence is stored as JSONB. A Decimal would not survive."""
    import json

    t = RecordingThresholds({"a": Decimal("1.5"), "b": [Decimal("2")]})
    t.start_recording()
    t.get("a")
    t.get("b")
    json.dumps(t.provenance())  # must not raise


def test_recording_resets_between_detectors():
    t = RecordingThresholds({"a": 1, "b": 2})
    t.start_recording()
    t.get("a")
    t.start_recording()
    t.get("b")
    assert t.keys_read() == {"b"}, "one detector's reads leaked into the next"


def test_it_is_still_an_ordinary_dict_for_detectors():
    """27 detectors read this without knowing. None of them may break."""
    t = RecordingThresholds({"a": 1})
    assert t.get("a") == 1
    assert t.get("missing", 7) == 7
    assert t["a"] == 1
    assert dict(t) == {"a": 1}


# ── end to end ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_stored_event_carries_the_thresholds_it_was_judged_against(db, broker):
    """
    Five losses on one underlying fires same_symbol_obsession. The stored event
    must say what threshold it was judged against, so the alert can be
    reconstructed when that number has since moved.

    Retargeted 2026-08-26: this used consecutive_loss_streak as its vehicle,
    which was retired. The mechanism under test is the recorder, not the
    detector — any detector that reads a threshold exercises it.
    """
    result = None
    for i in range(5):
        ct = await _loss(db, broker, 30 + i * 15)
        result = await engine.analyze(
            broker_account_id=broker.id, completed_trade=ct, db=db
        )

    events = [e for e in result.events if e.detector == "same_symbol_obsession"]
    assert events, "same_symbol_obsession did not fire on five losses"

    evidence = events[0].evidence or {}
    thresholds = evidence.get("_thresholds")
    assert thresholds, "the event cannot say what it was judged against"
    assert "obsession_min_losses" in thresholds

    entry = thresholds["obsession_min_losses"]
    assert "value" in entry and "source" in entry, (
        "a threshold without its origin is half an explanation"
    )


@pytest.mark.asyncio
async def test_the_thresholds_recorded_belong_to_that_detector(db, broker):
    """
    Per-detector, not per-trade. Storing every threshold the engine resolved on
    every event would be an audit log, not an explanation.
    """
    result = None
    for i in range(5):
        ct = await _loss(db, broker, 30 + i * 15)
        result = await engine.analyze(
            broker_account_id=broker.id, completed_trade=ct, db=db
        )

    for event in result.events:
        recorded = (event.evidence or {}).get("_thresholds") or {}
        assert len(recorded) < 20, (
            f"{event.detector} recorded {len(recorded)} thresholds — that is the "
            "whole resolved set, not the ones it read"
        )


@pytest.mark.asyncio
async def test_evidence_still_carries_the_detector_context(db, broker):
    """The explanation is additive. It must not displace what was there."""
    result = None
    for i in range(5):
        ct = await _loss(db, broker, 30 + i * 15)
        result = await engine.analyze(
            broker_account_id=broker.id, completed_trade=ct, db=db
        )

    event = [e for e in result.events if e.detector == "same_symbol_obsession"][0]
    evidence = event.evidence or {}
    assert any(k for k in evidence if not k.startswith("_")), (
        "detector context was lost when the thresholds were added"
    )


def test_a_personal_threshold_on_a_global_value_says_so():
    """
    Kind is what a threshold IS; Source is where it resolved this time. A
    personal_baseline threshold sitting on the repo default is correct for a
    trader with no history — but the two enum names side by side read as a
    contradiction, and the honest reading is the one that matters: they are being
    judged by a default, not by anything of theirs.
    """
    class _Resolved:
        value, source, confidence, detail = 5, "global", 0.0, "repo default"
        kind = "personal_baseline"

    t = RecordingThresholds({"revenge_window_danger_min": 5},
                            {"revenge_window_danger_min": _Resolved()})
    t.start_recording()
    t.get("revenge_window_danger_min")

    entry = t.provenance()["revenge_window_danger_min"]
    assert entry["personalised"] is False
    assert "history" in entry["note"]


def test_a_genuinely_personal_threshold_is_not_flagged():
    class _Resolved:
        value, source, confidence, detail = 4, "history", 0.8, "your own p85"
        kind = "personal_baseline"

    t = RecordingThresholds({"k": 4}, {"k": _Resolved()})
    t.start_recording()
    t.get("k")
    assert "personalised" not in t.provenance()["k"]
