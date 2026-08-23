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
    # A1 measured, unjudged — B3 is caution, decided from the alert audit
    (1, 1, "info"), (1, 2, "info"), (1, 3, "caution"),
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
    A0 and A1 used to be identical rows, treating "we measured it and have no
    rule to judge it by" exactly like "we could not see it at all". They are
    different claims and must not act the same.

    They now differ at B1 and B2, where a measured-but-unjudged loss stays silent.
    They agree at B3, for the reason in
    `test_escalation_is_reachable_without_a_significance_threshold`.
    """
    assert M[0][1] == M[1][1] == "info"
    assert M[0][2] == M[1][2] == "info"


def test_escalation_is_reachable_without_a_significance_threshold():
    """
    (A1, B3) is `caution`, and that cell was decided from evidence rather than
    taste.

    Auditing the eight sessions this detector used to alert on gave eleven
    loss-to-re-entry pairs: five likely false positives — every one a B1 re-entry
    into a DIFFERENT underlying — four ambiguous, and two likely genuine. B3
    occurred exactly once in eleven, on a 33%-of-premium loss returning to the
    same strike two minutes later with 25% more size, inside a session escalating
    40 → 40 → 80 → 100 → 200 across four consecutive losses.

    An earlier revision made this `info` to suppress a trivial-loss case that
    existed only in a unit test. It removed the clearest genuine sequence in the
    book and suppressed no false positive — every false positive is B1, and no B3
    cell can reach them.
    """
    assert M[1][3] == "caution"
    assert M[1][1] == "info" and M[1][2] == "info", (
        "B1 and B2 stay silent at A1 — B2 is genuinely mixed and separating it "
        "is what S2a is for"
    )


def test_severity_rises_with_reaction_structure_within_a_row():
    from app.core.severity import SEVERITY_ORDER

    for a in M:
        levels = [SEVERITY_ORDER.index(M[a][b]) for b in sorted(M[a])]
        assert levels == sorted(levels), f"A{a} is not monotonic in B"


def test_severity_never_falls_as_trigger_magnitude_rises():
    """
    Monotonic down every column. With (A1,B3) restored there is no inversion
    left, so this holds without exception — a stronger property than the one it
    replaced.
    """
    from app.core.severity import SEVERITY_ORDER

    for b in (1, 2, 3):
        for a in (1, 2, 3):
            assert SEVERITY_ORDER.index(M[a][b]) >= SEVERITY_ORDER.index(M[a - 1][b]), (
                f"A{a}B{b} ranks below A{a-1}B{b}"
            )


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
