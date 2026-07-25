"""
M6 / E2 (deep-review): the live ledger builder and the batch FIFO builder must
produce the SAME deterministic CompletedTrade id for the same round, so a batch
recompute doesn't delete+recreate with a new id (which nulls alert
trigger_completed_trade_id via ON DELETE SET NULL and under-counts behaviour-cost).
Pure-function tests (no DB).
"""
from datetime import datetime, timezone
from uuid import UUID

from app.services.position_ledger_service import stable_completed_trade_id

E = datetime(2026, 7, 20, 9, 30, tzinfo=timezone.utc)
X = datetime(2026, 7, 20, 10, 15, tzinfo=timezone.utc)


def test_deterministic_same_inputs():
    a = stable_completed_trade_id("acc-1", "NIFTY25JULFUT", E, "LONG", X)
    b = stable_completed_trade_id("acc-1", "NIFTY25JULFUT", E, "LONG", X)
    assert a == b
    assert isinstance(a, UUID)


def test_differs_by_round():
    base = stable_completed_trade_id("acc-1", "NIFTY25JULFUT", E, "LONG", X)
    assert base != stable_completed_trade_id("acc-1", "NIFTY25JULFUT", E, "SHORT", X)
    assert base != stable_completed_trade_id("acc-1", "NIFTY25JULFUT", E, "LONG", datetime(2026, 7, 20, 11, tzinfo=timezone.utc))
    assert base != stable_completed_trade_id("acc-2", "NIFTY25JULFUT", E, "LONG", X)


def test_ledger_and_batch_engines_agree():
    """The whole point of M6: both P&L engines must key the same round identically."""
    from app.services.pnl_calculator import PnLCalculator
    ledger_id = stable_completed_trade_id("acc-1", "NIFTY25JULFUT", E, "LONG", X)
    batch_id = PnLCalculator._stable_ct_id("acc-1", "NIFTY25JULFUT", E, "LONG", X)
    assert ledger_id == batch_id
