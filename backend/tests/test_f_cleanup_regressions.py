"""
Regressions for the F-series cleanup of 2026-08-29.

Each test pins ONE already-classified correctness bug so it cannot return.
Nothing here changes a threshold or a detector's claim; every fix was either a
crash, an unreachable branch, a lookup that could not match, or an assertion
made without reading the thing being asserted about.
"""
from __future__ import annotations

import inspect
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


# ── F1: exit_trade_ids holds two identifier spaces ─────────────────────────

def test_f1_exit_order_type_lookup_matches_both_identifier_spaces():
    """
    The live ledger writes Kite ORDER ids into exit_trade_ids
    (position_ledger_service: `e.fill_order_id`) while the batch FIFO writes
    Trade.id UUIDs (pnl_calculator: `str(f["trade_id"])`).

    The consumer matched only Trade.id, so on the live path it matched nothing
    and exit_order_types came back empty for every trade - indistinguishable
    from "this trade had no stop-loss".
    """
    src = (APP / "services" / "behavior_engine.py").read_text(encoding="utf-8")
    block = src[src.index("Query 4: exit order types"):][:1800]
    assert "_Trade.order_id.in_(" in block, "the Kite order-id space must be matched"
    assert "_cast(_Trade.id, _String).in_(" in block, "the UUID space must still match"
    assert "_or(" in block, "both spaces, not one replacing the other"


def test_f1_the_two_writers_still_disagree_which_is_why_both_are_matched():
    """Pins the premise. If a writer is ever unified, this test should be revisited."""
    ledger = (APP / "services" / "position_ledger_service.py").read_text(encoding="utf-8")
    fifo = (APP / "services" / "pnl_calculator.py").read_text(encoding="utf-8")
    assert '"exit_trade_ids": [e.fill_order_id for e in exit_fills]' in ledger
    assert 'exit_trade_ids=[str(f["trade_id"]) for f in exit_fills]' in fifo


# ── F10: product belongs in the FIFO position key ──────────────────────────

def test_f10_fifo_grouping_includes_product():
    """
    The position ledger keys on product and the positions table's unique
    constraint includes it. This grouping omitted it, so one symbol held in MIS
    and NRML at once was netted into rounds that never existed.
    """
    src = (APP / "services" / "pnl_calculator.py").read_text(encoding="utf-8")
    assert 'key = f"{trade.tradingsymbol}|{trade.exchange}|{trade.product' in src


# ── F19: overexposure crashed on a dual-product symbol ─────────────────────

def test_f19_overexposure_cannot_raise_multiple_results_found():
    from app.tasks import position_monitor_tasks as pmt

    # Only the POSITION query was the bug. The UserProfile lookup further down
    # is legitimately one-or-none and must not be swept up.
    src = inspect.getsource(pmt._overexposure_task)
    pos_query = src[src.index("select(Position)"):src.index("profile_result")]
    code = chr(10).join(l for l in pos_query.splitlines()
                        if not l.lstrip().startswith("#"))
    assert "scalar_one_or_none()" not in code, (
        "product is part of the position key, so a symbol open in MIS and NRML "
        "returns two rows and scalar_one_or_none() raises MultipleResultsFound")
    assert "scalars().all()" in code
    assert "scalar_one_or_none()" in src, (
        "the profile lookup is correctly one-or-none and should still be there")


def test_f19_did_not_silently_decide_netting():
    """
    Combining an MIS and an NRML leg is a netting question (D3) and is NOT
    answered here. The largest single position is judged, which is bit-identical
    to the old behaviour whenever only one row exists.
    """
    from app.tasks import position_monitor_tasks as pmt

    src = inspect.getsource(pmt._overexposure_task)
    assert "max(open_rows" in src
    assert "netting decision" in src


# ── F22: unreachable branch in post_loss_recovery_bet ──────────────────────

def test_f22_the_unreachable_cross_underlying_branch_is_gone():
    """
    `prior` is built filtered to `== ct_underlying`, so the set the branch
    tested could never hold more than one element and the cross-underlying arm
    never ran.
    """
    from app.services.behavior_engine import BehaviorEngine

    src = inspect.getsource(BehaviorEngine._detect_post_loss_recovery_bet)
    assert "== ct_underlying" in src, "the filter that made it unreachable"
    assert "if _cross:" not in src
    assert "self._notional(" not in src, "the dead branch's only caller"


# Two tests were deleted here on 2026-08-30 because their subject was
# `winning_streak_overconfidence`, retired that day:
#
#   test_f22_left_the_reachable_cross_branch_in_the_other_detector_alone
#       It pinned the distinction that F22's fix must NOT be swept into the
#       other detector, whose `_cross` branch WAS reachable. It did its job -
#       the branch survived F22 - and F22's own fix stays pinned by
#       `test_f22_the_unreachable_cross_underlying_branch_is_gone` above.
#
#   test_f23_a_zero_baseline_is_treated_as_no_baseline
#       F23 was `avg_baseline is not None` passing for 0.0, which made the
#       danger gate `current_qty >= 0` - unconditionally true. The fix was
#       correct and lived in that detector to the end. THE BUG CLASS IS NOT
#       CLOSED by deleting the test: any `x is not None` guard on a numeric
#       baseline elsewhere has the same defect. Recorded, not swept for.
#
# Both are reproduced in tests/test_winning_streak_retired.py so the reasoning
# survives the detector.


# ── F21 / F24: classified, verified, NOT bugs ──────────────────────────────

def test_f21_capital_mismatch_is_vocabulary_but_not_a_behaviour_detector():
    """
    Recorded as a fix candidate, verified as correct behaviour.

    REWRITTEN 2026-09-02. It used to prove the point through death_spiral's
    `_ALIAS_NATURE` map - capital_mismatch was deliberately absent from it, so
    a housekeeping nudge could not contribute a behavioural domain. Both that
    map and death_spiral are gone.

    The underlying fact is unchanged and is now asserted directly: it writes a
    `risk_alerts.pattern_type`, so it is part of the alert VOCABULARY, but it
    has no DetectorSpec, so it is not a behaviour detector and carries no
    `nature`. Anything that classifies detectors must therefore skip it.
    """
    from app.services.detector_registry import ALIASES, BY_NAME, all_pattern_types

    assert "capital_mismatch" in ALIASES, "it IS part of the alert vocabulary"
    assert "capital_mismatch" in all_pattern_types()
    assert BY_NAME.get("capital_mismatch") is None, (
        "it must have no DetectorSpec - it is a maintenance nudge, not a detector")


def test_f24_adding_to_adverse_position_runs_on_the_entry_path():
    """
    Recorded as "exit path never runs", verified as by design.

    It is the one detector with trigger="entry". The exit loop skips such specs
    deliberately and with a comment, and the entry-batch flush dispatches it
    directly. It is wired and it does run.
    """
    from app.services.detector_registry import BY_NAME

    assert BY_NAME["adding_to_adverse_position"].trigger == "entry"

    engine_src = (APP / "services" / "behavior_engine.py").read_text(encoding="utf-8")
    assert 'if spec.trigger == "entry":\n                continue' in engine_src

    task_src = (APP / "tasks" / "position_monitor_tasks.py").read_text(encoding="utf-8")
    assert "_detect_adding_to_adverse_position(ctx)" in task_src, (
        "the entry path is its real dispatch site")
