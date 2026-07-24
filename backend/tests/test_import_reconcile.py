"""Tests for the tradebook-import dedup twin-key.

A fill captured live via a postback (keyed on kite_order_id) has no trade_id, so on
re-import it must be recognised as the SAME fill and skipped — otherwise history double-
counts. The twin-key is what makes that match; these pin its behaviour.
"""
from datetime import datetime, timezone

from app.api.account_data import _twin_key


def _ts(h, m, s):
    return datetime(2026, 1, 15, h, m, s, tzinfo=timezone.utc)


def test_same_fill_different_seconds_same_minute_collapses():
    # postback ts vs tradebook ts can differ by seconds within the same minute
    a = _twin_key("NIFTY24JAN18000CE", "BUY", 50, 101.25, _ts(9, 30, 5))
    b = _twin_key("NIFTY24JAN18000CE", "BUY", 50, 101.25, _ts(9, 30, 41))
    assert a == b


def test_case_insensitive_symbol_and_side():
    a = _twin_key("nifty24jan18000ce", "buy", 50, 101.25, _ts(9, 30, 0))
    b = _twin_key("NIFTY24JAN18000CE", "BUY", 50, 101.25, _ts(9, 30, 0))
    assert a == b


def test_price_rounded_to_2dp():
    a = _twin_key("X", "BUY", 1, 100.001, _ts(9, 30, 0))
    b = _twin_key("X", "BUY", 1, 100.004, _ts(9, 30, 0))
    assert a == b  # both round to 100.00


def test_different_price_distinct():
    a = _twin_key("X", "BUY", 1, 100.00, _ts(9, 30, 0))
    b = _twin_key("X", "BUY", 1, 101.00, _ts(9, 30, 0))
    assert a != b


def test_different_minute_distinct():
    a = _twin_key("X", "BUY", 1, 100.0, _ts(9, 30, 0))
    b = _twin_key("X", "BUY", 1, 100.0, _ts(9, 31, 0))
    assert a != b


def test_different_side_distinct():
    buy = _twin_key("X", "BUY", 1, 100.0, _ts(9, 30, 0))
    sell = _twin_key("X", "SELL", 1, 100.0, _ts(9, 30, 0))
    assert buy != sell


def test_none_price_and_ts_do_not_crash():
    k = _twin_key("X", "BUY", 1, None, None)
    assert k[3] is None and k[4] is None
