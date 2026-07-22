"""
Tradebook import parser tests.

Kite Connect returns only the current day's trades, so the Console CSV is the
only route to real history — if this parser is wrong, a user's entire trading
past is imported wrong, silently.

The timestamp cases exist because of a bug caught during the build: Console's
`order_execution_time` is a FULL timestamp, and naively appending it to the
date column produced "<date> <date> <time>", which parsed as nothing and fell
back to the 09:15 default. Every trade landed in the same hour bucket, which
would have destroyed all hour-of-day analytics — the exact thing the record
lookup is built on.
"""
from zoneinfo import ZoneInfo

import pytest

from app.services.tradebook_import_service import (
    TradebookParseError,
    parse_tradebook_csv,
    to_trade_payload,
)

IST = ZoneInfo("Asia/Kolkata")

CANONICAL = (
    "symbol,isin,trade_date,exchange,segment,series,trade_type,auction,"
    "quantity,price,trade_id,order_id,order_execution_time\n"
    "NIFTY25JUL25000CE,,2026-07-15,NFO,FO,,buy,FALSE,75,142.50,10001,20260715000111,2026-07-15 09:32:11\n"
    "NIFTY25JUL25000CE,,2026-07-15,NFO,FO,,sell,FALSE,75,158.25,10002,20260715000222,2026-07-15 10:14:03\n"
)


def _rows(csv_text: str):
    rows, errors, meta = parse_tradebook_csv(csv_text.encode())
    return rows, errors, meta


class TestCanonicalParse:
    def test_parses_console_export(self):
        rows, errors, meta = _rows(CANONICAL)
        assert len(rows) == 2
        assert errors == []
        assert meta["header_row"] == 1
        assert rows[0]["tradingsymbol"] == "NIFTY25JUL25000CE"
        assert rows[0]["transaction_type"] == "BUY"
        assert rows[1]["transaction_type"] == "SELL"
        assert rows[0]["quantity"] == 75
        assert rows[0]["price"] == 142.50

    def test_maps_onto_live_sync_convention(self):
        """order_id must carry trade_id and kite_order_id the order id — that is
        what engages uq_trades_broker_order and gives idempotent re-import."""
        rows, _, _ = _rows(CANONICAL)
        p = to_trade_payload(rows[0])
        assert p["order_id"] == "10001"           # trade_id
        assert p["kite_order_id"] == "20260715000111"  # order id
        assert p["status"] == "COMPLETE"
        assert p["filled_quantity"] == 75
        assert p["raw_payload"]["source"] == "console_tradebook_import"


class TestTimestamps:
    """Hour-of-day correctness. See module docstring."""

    @pytest.mark.parametrize("time_col,value,expected_hhmm", [
        ("order_execution_time", "2026-07-15 09:32:11", "09:32"),
        ("trade_time",           "14:47:02",            "14:47"),
        ("order_execution_time", "2026-07-15T13:20:45", "13:20"),
        ("order_execution_time", "2026-07-15 02:30:00 PM", "14:30"),
    ])
    def test_time_formats_land_in_the_right_hour(self, time_col, value, expected_hhmm):
        csv_text = (
            f"symbol,trade_date,trade_type,quantity,price,{time_col}\n"
            f"X,2026-07-15,buy,1,1,{value}\n"
        )
        rows, _, _ = _rows(csv_text)
        ist = rows[0]["timestamp"].astimezone(IST)
        assert ist.strftime("%H:%M") == expected_hhmm

    def test_date_only_anchors_at_market_open_not_midnight(self):
        """Midnight would put trades outside market hours and skew hour buckets."""
        rows, _, _ = _rows("symbol,trade_date,trade_type,quantity,price\nX,2026-07-15,buy,1,1\n")
        ist = rows[0]["timestamp"].astimezone(IST)
        assert ist.strftime("%H:%M") == "09:15"

    def test_ist_is_converted_to_utc(self):
        rows, _, _ = _rows(CANONICAL)
        ts = rows[0]["timestamp"]
        assert ts.tzinfo is not None
        assert ts.strftime("%H:%M") == "04:02"   # 09:32 IST

    @pytest.mark.parametrize("date_value", ["2026-07-15", "15-07-2026", "15/07/2026", "15-Jul-2026"])
    def test_accepts_common_date_formats(self, date_value):
        rows, errors, _ = _rows(
            f"symbol,trade_date,trade_type,quantity,price\nX,{date_value},buy,1,1\n"
        )
        assert len(rows) == 1, errors


class TestTolerance:
    def test_skips_banner_rows_above_the_table(self):
        csv_text = (
            "Zerodha Broking Ltd,,,\n"
            "Tradebook for ZA1234,,,\n"
            "Period: 01-04-2025 to 31-03-2026,,,\n"
            ",,,\n"
            "Symbol,Trade Date,Exchange,Trade Type,Quantity,Price,Trade ID,Order ID\n"
            "BANKNIFTY25JUL52000PE,15-07-2026,NFO,SELL,15,310.00,T1,O1\n"
        )
        rows, errors, meta = _rows(csv_text)
        assert len(rows) == 1
        assert errors == []
        assert meta["header_row"] == 5

    def test_header_aliases(self):
        csv_text = (
            "Instrument,Date,Type,Qty,Avg Price,Trade No\n"
            "INFY,2026-07-15,B,10,1500,T5\n"
        )
        rows, errors, _ = _rows(csv_text)
        assert len(rows) == 1, errors
        assert rows[0]["transaction_type"] == "BUY"

    def test_bad_rows_are_reported_not_fatal(self):
        csv_text = (
            "symbol,trade_date,trade_type,quantity,price,trade_id\n"
            "GOOD,2026-07-15,buy,10,100,T9\n"
            ",2026-07-15,buy,10,100,T10\n"
            "BADTYPE,2026-07-15,hold,10,100,T11\n"
            "BADDATE,notadate,buy,10,100,T12\n"
        )
        rows, errors, _ = _rows(csv_text)
        assert len(rows) == 1
        assert len(errors) == 3
        assert all("line" in e and e["problems"] for e in errors)

    def test_blank_lines_ignored(self):
        rows, errors, _ = _rows(
            "symbol,trade_date,trade_type,quantity,price\n"
            "X,2026-07-15,buy,1,1\n"
            "\n"
            ",,,,\n"
        )
        assert len(rows) == 1
        assert errors == []

    def test_rejects_a_file_that_is_not_a_tradebook(self):
        with pytest.raises(TradebookParseError):
            parse_tradebook_csv(b"name,email\nfoo,bar\n")

    def test_rejects_empty_file(self):
        with pytest.raises(TradebookParseError):
            parse_tradebook_csv(b"")

    def test_handles_utf8_bom(self):
        rows, _, _ = parse_tradebook_csv(
            b"\xef\xbb\xbfsymbol,trade_date,trade_type,quantity,price\nX,2026-07-15,buy,1,1\n"
        )
        assert len(rows) == 1

    def test_strips_thousands_separators_and_currency(self):
        rows, _, _ = _rows(
            "symbol,trade_date,trade_type,quantity,price\n"
            'X,2026-07-15,buy,"1,200","₹1,450.75"\n'
        )
        assert rows[0]["quantity"] == 1200
        assert rows[0]["price"] == 1450.75

    def test_negative_quantity_is_treated_as_magnitude(self):
        """Some exports render sells as negative quantities; direction comes
        from trade_type, so quantity must stay positive."""
        rows, _, _ = _rows(
            "symbol,trade_date,trade_type,quantity,price\nX,2026-07-15,sell,-50,10\n"
        )
        assert rows[0]["quantity"] == 50
        assert rows[0]["transaction_type"] == "SELL"


class TestIdempotency:
    def test_dedupe_key_is_stable_across_uploads(self):
        first, _, _ = _rows(CANONICAL)
        second, _, _ = _rows(CANONICAL)
        assert [r["trade_id"] for r in first] == [r["trade_id"] for r in second]

    def test_missing_ids_get_a_deterministic_synthetic_key(self):
        """Without a broker id we still must not duplicate on re-upload."""
        csv_text = "symbol,trade_date,trade_type,quantity,price\nX,2026-07-15,buy,5,50\n"
        a, _, _ = _rows(csv_text)
        b, _, _ = _rows(csv_text)
        assert a[0]["trade_id"] == b[0]["trade_id"]
        assert a[0]["trade_id"].startswith("syn-")

    def test_distinct_trades_get_distinct_keys(self):
        csv_text = (
            "symbol,trade_date,trade_type,quantity,price\n"
            "X,2026-07-15,buy,5,50\n"
            "X,2026-07-15,buy,5,51\n"
        )
        rows, _, _ = _rows(csv_text)
        assert rows[0]["trade_id"] != rows[1]["trade_id"]


class TestExchangeInference:
    @pytest.mark.parametrize("segment,symbol,expected", [
        ("FO", "NIFTY25JUL25000CE", "NFO"),
        ("EQ", "INFY", "NSE"),
        ("MCX", "GOLDM25AUGFUT", "MCX"),
        ("CD", "USDINR25JULFUT", "CDS"),
    ])
    def test_infers_exchange_when_column_blank(self, segment, symbol, expected):
        rows, _, _ = _rows(
            "symbol,trade_date,exchange,segment,trade_type,quantity,price\n"
            f"{symbol},2026-07-15,,{segment},buy,1,1\n"
        )
        assert rows[0]["exchange"] == expected

    def test_explicit_exchange_wins(self):
        rows, _, _ = _rows(
            "symbol,trade_date,exchange,segment,trade_type,quantity,price\n"
            "INFY,2026-07-15,BSE,EQ,buy,1,1\n"
        )
        assert rows[0]["exchange"] == "BSE"
