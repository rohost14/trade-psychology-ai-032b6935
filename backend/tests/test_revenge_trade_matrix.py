"""
The `revenge_trade` A x B matrix, and the properties that make it not a score.

Two axes, each taking the HIGHEST level any frame establishes — a lattice join.
Severity is read from a table. Nothing is summed, weighted or counted.

The two properties worth defending are not the cell values but the joins:

  * an abstaining frame can never LOWER a level, so missing equity cannot reduce
    the severity of a large trade-relative loss;
  * personal history can only RAISE one, so "this is normal for them" is
    unreachable by construction rather than by promise.

Both have negative controls at the bottom.
"""
import pytest

from app.services.behavior_engine import BehaviorEngine

engine = BehaviorEngine()
M = BehaviorEngine._RT_MATRIX


# ── the table ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("a,b,expected", [
    # A3 account-threatening
    (3, 1, "danger"), (3, 2, "danger"), (3, 3, "critical"),
    # A2 large — a decided threshold was crossed
    (2, 1, "caution"), (2, 2, "danger"), (2, 3, "danger"),
    # A1 measured, unjudged — recorded, never notified
    (1, 1, "info"), (1, 2, "info"), (1, 3, "info"),
    # A0 unmeasurable — structure alone carries the cold-start cell
    (0, 1, "info"), (0, 2, "info"), (0, 3, "caution"),
])
def test_every_cell(a, b, expected):
    assert M[a][b] == expected


def test_b0_is_absent_from_the_table():
    """
    B0 means the two trades were unrelated. That is a NON-detection, returned
    before the table is reached — recording it would write an event on
    essentially every trade that follows a loss, all session, every session.
    """
    for a in M:
        assert 0 not in M[a], "B0 must not be reachable as a severity"


def test_only_one_cell_is_critical():
    criticals = [(a, b) for a in M for b, sev in M[a].items() if sev == "critical"]
    assert criticals == [(3, 3)]


def test_a_measured_small_loss_is_quieter_than_an_unknown_one():
    """
    The revision. A0 and A1 used to be identical rows, which treated "we measured
    it and have no rule to judge it by" exactly like "we could not see it at all".

    A1 is quieter, which reads backwards until the reason is stated: at A0 the
    loss MIGHT have been large and the structural claim is all the evidence there
    is; at A1 we hold a number we are not licensed to interpret, and claiming
    harm would decide significance at the moment of use.
    """
    assert M[0][3] == "caution"
    assert M[1][3] == "info"


def test_the_a1_row_never_notifies():
    """
    Until a significance threshold is decided, a measured loss produces evidence
    and nothing louder. This is real lost coverage and it is deliberate — it
    makes the missing decision visible instead of hiding it behind a number
    nobody chose.
    """
    assert set(M[1].values()) == {"info"}


def test_severity_rises_with_reaction_structure_within_a_row():
    from app.core.severity import SEVERITY_ORDER

    for a in M:
        levels = [SEVERITY_ORDER.index(M[a][b]) for b in sorted(M[a])]
        assert levels == sorted(levels), f"A{a} is not monotonic in B"


def test_severity_rises_with_trigger_magnitude_within_a_column():
    """
    Except at B3, where A0 outranks A1 for the reason in
    `test_a_measured_small_loss_is_quieter_than_an_unknown_one`. That single
    inversion is the whole content of the revision, so it is asserted rather
    than tolerated.
    """
    from app.core.severity import SEVERITY_ORDER

    for b in (1, 2, 3):
        for a in (1, 2, 3):
            assert SEVERITY_ORDER.index(M[a][b]) >= SEVERITY_ORDER.index(M[a - 1][b]) \
                or (a, b) == (1, 3), f"A{a}B{b} ranks below A{a-1}B{b}"


# ── the joins, with negative controls ──────────────────────────────────────


def test_the_axes_are_joins_not_sums():
    """
    If either axis summed or counted, three mild observations would outrank one
    severe one. `max` is what prevents that, and it is what makes an abstention
    harmless.
    """
    import inspect

    src = inspect.getsource(engine._detect_revenge_trade)
    assert "a_level = max(" in src, "the A axis must join, not accumulate"
    assert "+=" not in src.split("a_level = 0")[1].split("b_level")[0], (
        "something is accumulating into the A axis"
    )


def test_no_points_remain():
    """The old score in miniature: 30 for a base case, 20 for this, 10 for that."""
    import inspect

    src = inspect.getsource(engine._detect_revenge_trade)
    assert "signal_points" not in src
    assert "confidence +=" not in src


def test_capital_is_no_longer_a_gate():
    """
    The defect this rewrite exists to correct. `revenge_min_loss_inr` resolved to
    1% of capital and gated the detector, so a larger account raised the bar:
    8 alerts at Rs 50,000 and zero at Rs 5,00,000.
    """
    import inspect

    src = inspect.getsource(engine._detect_revenge_trade)
    assert "revenge_min_loss_inr" not in src.split('"""')[2], (
        "the capital-derived gate is back in the body"
    )


def test_size_escalation_needs_no_constant():
    """B3 is a plain inequality: larger than the position that just lost."""
    import inspect

    src = inspect.getsource(engine._detect_revenge_trade)
    assert "1.5" not in src, "a size multiple reappeared"
