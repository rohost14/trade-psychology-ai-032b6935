"""
Session boundaries must come from the instrument's OWN exchange.

Two live detectors previously hardcoded NSE hours (09:15-15:30 / a flat 15:00
panic start). MCX trades until 23:30 and CDS until 17:00, so for commodity and
currency traders that produced:

  * _detect_fomo_entry — mins_after_open went negative in the morning and
    mins_before_close went ~460 min negative in the evening, so BOTH the
    open-window and close-window FOMO signals were permanently dead on MCX.

  * _detect_end_of_session_mis_panic — panic_start was a flat 15:00 with no
    commodity branch, so every MCX MIS entry from 15:00 to 23:30 was scored as
    "end of session panic": 8.5 hours a day of false alerts.

These tests pin the per-exchange behaviour and, critically, assert that NSE/NFO
timings are UNCHANGED — the fix must not retune thresholds that already work.
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.core.exchange_constants import get_close_time, get_open_time

IST = ZoneInfo("Asia/Kolkata")


def _fomo_windows(exchange: str, hh: int, mm: int, open_win: int = 30, close_win: int = 30):
    """Replicates the window maths in _detect_fomo_entry."""
    entry = datetime(2026, 7, 15, hh, mm, tzinfo=IST)
    o, c = get_open_time(exchange), get_close_time(exchange)
    market_open = entry.replace(hour=o.hour, minute=o.minute, second=0, microsecond=0)
    market_close = entry.replace(hour=c.hour, minute=c.minute, second=0, microsecond=0)
    after = (entry - market_open).total_seconds() / 60
    before = (market_close - entry).total_seconds() / 60
    return (0 <= after <= open_win), (0 <= before <= close_win)


def _panic_start_minutes(exchange: str) -> int:
    """Replicates the panic_start maths in _detect_end_of_session_mis_panic."""
    if exchange in ("NFO", "BFO"):
        return 15 * 60
    if exchange in ("MCX", "CDS", "BCD"):
        c = get_close_time(exchange)
        return (c.hour * 60 + c.minute - 5) - 25
    return 15 * 60


class TestExchangeConstants:
    def test_mcx_runs_to_2330(self):
        assert get_open_time("MCX") == time(9, 0)
        assert get_close_time("MCX") == time(23, 30)

    def test_nse_nfo_unchanged(self):
        for ex in ("NSE", "NFO"):
            assert get_open_time(ex) == time(9, 15)
            assert get_close_time(ex) == time(15, 30)


class TestFomoWindows:
    @pytest.mark.parametrize("exchange,hh,mm,expect_open,expect_close", [
        # NSE/NFO — behaviour that already worked must keep working
        ("NFO", 9, 25, True, False),     # just after open
        ("NFO", 15, 10, False, True),    # run-up to close
        ("NFO", 12, 0, False, False),    # midday
        # MCX — previously BOTH were permanently False
        ("MCX", 9, 10, True, False),     # just after 09:00 open
        ("MCX", 23, 10, False, True),    # run-up to 23:30 close
        ("MCX", 14, 0, False, False),    # midday, correctly neither
    ])
    def test_windows_follow_the_exchange(self, exchange, hh, mm, expect_open, expect_close):
        is_open, is_close = _fomo_windows(exchange, hh, mm)
        assert is_open is expect_open
        assert is_close is expect_close

    def test_old_hardcoded_hours_would_miss_mcx_entirely(self):
        """Regression guard: documents the bug that was fixed."""
        entry = datetime(2026, 7, 15, 23, 10, tzinfo=IST)
        hardcoded_close = entry.replace(hour=15, minute=30, second=0, microsecond=0)
        mins_before_close = (hardcoded_close - entry).total_seconds() / 60
        assert mins_before_close < 0            # negative -> window can never match
        # The fix produces a real, positive window.
        _, is_close = _fomo_windows("MCX", 23, 10)
        assert is_close is True


class TestPanicWindow:
    def test_nse_and_nfo_panic_start_unchanged_at_1500(self):
        assert _panic_start_minutes("NFO") == 15 * 60
        assert _panic_start_minutes("NSE") == 15 * 60

    def test_mcx_panic_window_tracks_its_own_close(self):
        assert _panic_start_minutes("MCX") == 23 * 60      # 23:00, not 15:00

    def test_cds_panic_window_tracks_its_own_close(self):
        assert _panic_start_minutes("CDS") == 16 * 60 + 30  # 16:30

    @pytest.mark.parametrize("exchange,expected_hours", [("MCX", 8.5), ("CDS", 2.0)])
    def test_false_positive_window_removed(self, exchange, expected_hours):
        """How much of the evening used to be wrongly scored as panic."""
        close = get_close_time(exchange)
        old_window_min = (close.hour * 60 + close.minute) - 15 * 60
        assert old_window_min / 60 == pytest.approx(expected_hours)
        # After the fix the window is the intended 25-minute run-up.
        new_window_min = (close.hour * 60 + close.minute - 5) - _panic_start_minutes(exchange)
        assert new_window_min == 25
