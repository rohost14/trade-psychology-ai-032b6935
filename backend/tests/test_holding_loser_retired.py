"""
`holding_loser` and `overexposure` are retired. These tests hold it in place.

They go in one file because they were retired on the same day, for opposite
reasons, and the contrast is the point.

── `holding_loser` — RETIRED 2026-09-02, on evidence ──────────────────────────

Its predicate was:

    unrealized_pnl < 0  AND  loss >= 0.5%  AND  held >= 30 minutes

A SNAPSHOT plus a STOPWATCH. Nothing in it observed the loss CHANGING, so it
could not tell a position drifting further down from one recovering — and
"holding a loser" is a claim about persistence through a drawdown, not about a
position being red at one instant.

The obvious substitute — "this trader holds losers longer than winners" — was
measured on the 203-session book and FAILED THE PERSISTENCE TEST:

    winner/loser hold ratio, first half    0.62   (losers held SHORTER)
    winner/loser hold ratio, second half   2.54
    intraday only, 82% of rounds           1.04   label-shuffle p = 0.343
    median ratio, full book                0.98

The sign FLIPS between halves. The whole apparent effect is a handful of
multi-day holds; the median says there is nothing there. That is the same test
that retired `time_of_day_bias`, and it fails the same way.

NOT REPLACED, DELIBERATELY. No MTM capture was built, no AlertCheckpoint
polling, and the winner-vs-loser comparison was NOT promoted to an analytics
surface — it fails the same test that killed the alert, so shipping it as
"analytics" would only move an unsupported claim to a quieter place.

Reviving it needs a stored mark-to-market series per open position. That does
not exist and cannot be reconstructed from what is stored.

── `overexposure` — RETIRED 2026-09-02, because it was already dead ───────────

Nothing about the BEHAVIOUR. `_overexposure_task` emits
`pattern_type="constitution_violation"` with `rule="max_trade_risk"`, gates on
the trader's DECLARED limit, and abstains when the capital requirement is
unavailable. It has not emitted `"overexposure"` since the exposure hierarchy
shipped. The alias entry was the last thing keeping the name in the vocabulary.

THE ENTRY-TIME CHECK IS UNTOUCHED AND STILL RUNS. This retires a NAME, not a
guard, and these tests assert that distinction rather than assuming it.
"""
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"
SRC = Path(__file__).resolve().parents[2] / "src"


# ── The vocabulary ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("retired", ["holding_loser", "overexposure"])
def test_it_is_gone_from_the_vocabulary(retired):
    from app.services.detector_registry import (
        ALIASES, BY_NAME, PATTERN_COPY, all_pattern_types,
    )

    assert retired not in ALIASES
    assert retired not in BY_NAME
    assert retired not in PATTERN_COPY
    assert retired not in all_pattern_types()


def test_the_engine_counts_are_what_these_retirements_left():
    """14 detectors, 16 pattern types, 2 aliases."""
    from app.services.detector_registry import ALIASES, REGISTRY, all_pattern_types

    assert len(REGISTRY) == 14
    assert len(all_pattern_types()) == 16
    assert set(ALIASES) == {"daily_overtrading", "capital_mismatch"}


@pytest.mark.parametrize("retired", ["holding_loser", "overexposure"])
def test_it_is_recorded_as_retired(retired):
    from tests.test_pattern_contract import RETIRED_PATTERN_NAMES

    assert retired in RETIRED_PATTERN_NAMES


# ── holding_loser: it cannot fire, and nothing schedules it ────────────────

def test_the_predicate_is_gone():
    """
    Checked against CODE lines only. The retirement note in that file names the
    two constants so a reader knows what was removed and that neither was
    replaced — a historical mention is the opposite of a live definition.
    """
    text = (APP / "tasks" / "position_monitor_tasks.py").read_text(encoding="utf-8")
    code = [
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    ]
    code = chr(10).join(code)
    assert "HOLDING_LOSER_MIN_DURATION" not in code
    assert "HOLDING_LOSER_MIN_LOSS_PCT" not in code
    assert '"pattern": "holding_loser"' not in code


def test_the_scheduled_chain_is_gone():
    """
    A Celery chain re-ran the check every 30 minutes, up to 8 times. It existed
    only to re-ask a retired question.
    """
    import app.tasks.position_monitor_tasks as pmt

    assert not hasattr(pmt, "check_holding_loser_scheduled")
    assert not hasattr(pmt, "_holding_loser_task")
    assert not hasattr(pmt, "MAX_HOLDING_LOSER_CHECKS")


def test_nothing_dispatches_the_chain_any_more():
    """
    THE BUG THIS PREVENTS, and it has happened before in this file's history:
    deleting a task while a caller still imports it inside a broad
    `try/except Exception` turns the ImportError into a silently skipped block
    — taking every other position check with it.
    """
    text = (APP / "tasks" / "trade_tasks.py").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        assert "check_holding_loser_scheduled" not in line


def test_the_position_check_seam_produces_nothing_now():
    """`holding_loser` was its last remaining event."""
    import asyncio

    import app.tasks.position_monitor_tasks as pmt

    assert asyncio.run(pmt._check_position(object(), {}, None)) == []


def test_no_replacement_predicate_was_introduced():
    """
    The instruction was explicit: retire it, do not redesign it. This fails if
    a hold-duration rule reappears under any name in that module.
    """
    text = (APP / "tasks" / "position_monitor_tasks.py").read_text(encoding="utf-8")
    body = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    assert "hold_min" not in body
    assert "disposition" not in body.lower()


# ── overexposure: the NAME went, the guard did not ─────────────────────────

def test_the_entry_time_exposure_check_still_exists():
    """The whole point of the distinction. Retiring the alias must not have
    removed the check that replaced it."""
    import app.tasks.position_monitor_tasks as pmt

    assert hasattr(pmt, "_overexposure_task")


def test_it_fires_as_a_constitution_violation_not_as_overexposure():
    import inspect

    import app.tasks.position_monitor_tasks as pmt

    src = inspect.getsource(pmt._overexposure_task)
    assert 'pattern_type="constitution_violation"' in src
    assert '"rule": "max_trade_risk"' in src
    assert 'pattern_type="overexposure"' not in src


def test_it_still_requires_a_declared_limit_and_still_abstains():
    """
    The two properties that make it defensible: no universal exposure line, and
    silence when the capital requirement is unknown rather than a guess.
    """
    import inspect

    import app.tasks.position_monitor_tasks as pmt

    src = inspect.getsource(pmt._overexposure_task)
    assert "no_declared_exposure_rule" in src
    assert "capital_requirement_unavailable" in src


# ── The consolidation family that named them ───────────────────────────────

def test_the_dead_family_is_gone():
    """
    "the position is too big" listed four names, and by 2026-09-02 every one
    was retired or not a behaviour detector. A family whose members cannot fire
    is inert — and inert entries that read like live rules are how retired
    names come back.
    """
    from app.services.behavior_engine import BehaviorEngine

    names = {n for n, _ in BehaviorEngine._FAMILIES}
    assert "the position is too big" not in names


def test_no_family_names_a_pattern_that_cannot_be_emitted():
    """The general form, so this cannot recur for a different family."""
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import all_pattern_types

    live = set(all_pattern_types())
    dead = {
        m for _, members in BehaviorEngine._FAMILIES for m in members if m not in live
    }
    assert dead == set(), f"consolidation families name unemittable patterns: {dead}"


# ── Historical rows stay readable ──────────────────────────────────────────

@pytest.mark.parametrize("retired,label", [
    ("holding_loser", "Holding a loser"),
    ("overexposure", "Position too large"),
])
def test_the_frontend_still_renders_a_stored_row(retired, label):
    text = (SRC / "contexts" / "AlertContext.tsx").read_text(encoding="utf-8")
    assert f"'{retired}': '{label}'" in text


@pytest.mark.parametrize("retired", ["holding_loser", "overexposure"])
def test_it_is_not_a_pattern_type_in_the_guest_fixtures(retired):
    demo = (SRC / "lib" / "demoData.ts").read_text(encoding="utf-8")
    assert f"pattern_type: '{retired}'" not in demo
    assert f'pattern_type: "{retired}"' not in demo
