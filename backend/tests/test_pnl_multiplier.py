"""
M3 (deep-review P1): unrealized P&L must apply the lot multiplier for MCX/CDS,
where Position.total_quantity is in LOTS. Pure-function tests (no DB).
"""
from app.services.pnl_calculator import _unrealized_pnl_for_position


def test_nse_unrealized_no_multiplier():
    # NSE/NFO: Kite qty already expanded to units, multiplier = 1.
    # NIFTY long 75 @100 -> 110  => (110-100)*75*1 = 750
    assert _unrealized_pnl_for_position(75, 100.0, 110.0, 1) == 750.0


def test_mcx_long_applies_multiplier():
    # CRUDEOIL 1 lot (multiplier=100), 6000 -> 6050  => (6050-6000)*1*100 = 5000
    # (the bug returned 50 — multiplier dropped)
    assert _unrealized_pnl_for_position(1, 6000.0, 6050.0, 100) == 5000.0


def test_mcx_short_applies_multiplier():
    # short 1 lot, 6050 -> 6000  => (6050-6000)*1*100 = 5000 profit
    assert _unrealized_pnl_for_position(-1, 6050.0, 6000.0, 100) == 5000.0


def test_mcx_long_loss():
    # long 2 lots, 6000 -> 5990  => (5990-6000)*2*100 = -2000
    assert _unrealized_pnl_for_position(2, 6000.0, 5990.0, 100) == -2000.0
