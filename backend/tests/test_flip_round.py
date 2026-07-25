"""
M2 (deep-review P1): a position OPENED by a FLIP must still produce a
CompletedTrade when it later closes. The old ledger builder excluded the FLIP
(it's classified as the previous round's exit), so a flip-opened round had no
entry fills and returned None -> the real-time engine never saw the trade.

Pure-function tests of `_build_round_ct_fields` (no DB).
"""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.services.position_ledger_service import _build_round_ct_fields


def _e(entry_type, fill_qty, fill_price, minute, realized_pnl=0,
       position_qty_after=0, avg_entry_price_after=None, oid=None):
    return SimpleNamespace(
        entry_type=entry_type, fill_qty=fill_qty, fill_price=Decimal(str(fill_price)),
        occurred_at=datetime(2026, 7, 20, 9, minute, tzinfo=timezone.utc),
        realized_pnl=Decimal(str(realized_pnl)),
        position_qty_after=position_qty_after,
        avg_entry_price_after=(Decimal(str(avg_entry_price_after)) if avg_entry_price_after is not None else None),
        fill_order_id=oid or f"o{minute}",
    )


def test_normal_long_round_unchanged():
    # OPEN +50 @100, CLOSE -50 @110  => long, entry 100, exit 110, pnl 500
    rnd = [_e("OPEN", 50, 100, 15, position_qty_after=50, avg_entry_price_after=100),
           _e("CLOSE", -50, 110, 30, realized_pnl=500, position_qty_after=0)]
    f = _build_round_ct_fields(rnd, preceding_flip=None)
    assert f is not None
    assert f["direction"] == "LONG"
    assert f["total_quantity"] == 50
    assert float(f["avg_entry"]) == 100.0
    assert float(f["avg_exit"]) == 110.0
    assert float(f["total_pnl"]) == 500.0
    assert f["num_entries"] == 1


def test_flip_opened_short_round_now_builds():
    # A FLIP closed a long and opened 50 short @200; then CLOSE +50 @190 (pnl 500).
    # OLD behaviour: entry_fills empty -> None. FIX: the flip opens the round.
    flip = _e("FLIP", -100, 200, 30, realized_pnl=250, position_qty_after=-50, avg_entry_price_after=200)
    rnd = [_e("CLOSE", 50, 190, 45, realized_pnl=500, position_qty_after=0)]
    f = _build_round_ct_fields(rnd, preceding_flip=flip)
    assert f is not None, "flip-opened round must produce a CompletedTrade (M2)"
    assert f["direction"] == "SHORT"
    assert f["total_quantity"] == 50           # opened by the flip
    assert float(f["avg_entry"]) == 200.0      # flip fill price
    assert float(f["avg_exit"]) == 190.0
    assert float(f["total_pnl"]) == 500.0
    assert f["num_entries"] == 1


def test_flip_opened_then_added():
    # flip opens 50 short @200, INCREASE sell 50 @210 (now -100), CLOSE buy 100 @190
    flip = _e("FLIP", -100, 200, 30, position_qty_after=-50, avg_entry_price_after=200)
    rnd = [_e("INCREASE", -50, 210, 40, position_qty_after=-100, avg_entry_price_after=205),
           _e("CLOSE", 100, 190, 50, realized_pnl=2500, position_qty_after=0)]
    f = _build_round_ct_fields(rnd, preceding_flip=flip)
    assert f is not None
    assert f["direction"] == "SHORT"
    assert f["total_quantity"] == 100          # 50 (flip) + 50 (increase)
    # weighted avg entry = (50*200 + 50*210)/100 = 205
    assert float(f["avg_entry"]) == 205.0
    assert f["num_entries"] == 2


def test_insufficient_returns_none():
    assert _build_round_ct_fields([], preceding_flip=None) is None
    # entries but no exit
    assert _build_round_ct_fields([_e("OPEN", 50, 100, 15)], preceding_flip=None) is None
