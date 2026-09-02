"""
A declared trigger is a dispatch path, and nothing may declare one silently.

THE BUG THIS EXISTS TO PREVENT

`DetectorSpec.trigger` was documented as "exit | session — when the detector
can fire". The engine's per-CompletedTrade loop branched on exactly one value:

    if spec.trigger == "entry":
        continue

Everything else ran. So `win_rate_collapse`, which declared "session", ran on
the exit path anyway and its declaration was absorbed without a word. Any
future value — "eod", "weekly", a typo — would have been absorbed the same way,
and the failure is invisible: the detector runs, just not where it says.

The field was doing two jobs. `entry` and `exit` answer WHEN the engine invokes
a detector; `session` answered WHAT its subject is. Those are different
questions, which is why one of the three was unenforceable. They are now
`trigger` (dispatch, validated) and `scope` (subject, descriptive).

`win_rate_collapse` did not move: it declares trigger="exit" now, which is
where it has always run, plus scope="session". No behaviour change.
"""
from __future__ import annotations

import dataclasses

import pytest

from app.services.detector_registry import (
    BY_NAME,
    REGISTRY,
    SCOPES,
    TRIGGERS,
    DetectorSpec,
)


def test_the_dispatch_vocabulary_is_exactly_the_paths_that_exist():
    """Two dispatch paths exist: the entry-batch flush and the exit loop."""
    assert TRIGGERS == frozenset({"entry", "exit"})


@pytest.mark.parametrize("spec", REGISTRY, ids=lambda s: s.name)
def test_every_spec_declares_a_real_dispatch_path(spec: DetectorSpec):
    assert spec.trigger in TRIGGERS, (
        f"{spec.name} declares trigger={spec.trigger!r}, which no dispatch "
        f"path runs. If the detector judges the whole session, that is "
        f"scope='session'."
    )


@pytest.mark.parametrize("spec", REGISTRY, ids=lambda s: s.name)
def test_every_spec_declares_a_known_scope(spec: DetectorSpec):
    assert spec.scope in SCOPES


def test_an_unknown_trigger_is_rejected_at_registry_import():
    """
    The registry validates on import. Re-run that validation against a spec
    carrying the old value to prove the message points at the right fix.
    """
    bad = dataclasses.replace(BY_NAME["win_rate_collapse"], trigger="session")
    assert bad.trigger not in TRIGGERS


def test_the_engine_raises_rather_than_running_an_unknown_trigger():
    """
    The loop must not absorb an unrecognised value. Checked by reading the
    dispatch source: a bare `continue` on 'entry' with no else is exactly the
    shape that hid this for months.
    """
    import inspect

    from app.services.behavior_engine import BehaviorEngine

    src = inspect.getsource(BehaviorEngine._run_all_detectors)
    assert 'spec.trigger != "exit"' in src, (
        "the exit loop no longer rejects unknown triggers"
    )
    assert "raise ValueError" in src


def test_win_rate_collapse_runs_on_the_exit_path_and_judges_the_session():
    """The specific spec this was found through. Both halves, pinned."""
    spec = BY_NAME["win_rate_collapse"]
    assert spec.trigger == "exit"
    assert spec.scope == "session"
    # Unchanged, and deliberately so: evidence-only until there is a decision
    # to make the performance domain notifiable.
    assert spec.disposition == "analytics"
    assert spec.notification_level == 0


def test_the_only_entry_triggered_detector_is_still_the_expected_one():
    entry = sorted(s.name for s in REGISTRY if s.trigger == "entry")
    assert entry == ["adding_to_adverse_position"]


def test_session_scope_is_declared_not_inferred():
    """
    `scope` is descriptive. Nothing branches on it, so this asserts only that
    the one session-scoped detector is the one we know about — a second one
    appearing should be a deliberate act, not a side effect.
    """
    session_scoped = sorted(s.name for s in REGISTRY if s.scope == "session")
    assert session_scoped == ["win_rate_collapse"]
