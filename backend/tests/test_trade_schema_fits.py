"""
Schema-fit guard for the trade ingestion path (no DB required).

Class of bug this closes: "value too long for type character varying(N)"
(asyncpg StringDataRightTruncationError). A String(N) column crashes the INSERT
if the transform emits a longer value. This test runs the REAL transform
(transform_zerodha_order) on a realistic max-length Zerodha COMPLETE postback and
asserts every string it produces fits the corresponding Trade column's length.

It also pins the contract at the exact boundary (tag = 20 chars) so a future
column shrink or a transform change that stops bounding a field fails CI here,
not at 3 AM on a real fill.
"""
from sqlalchemy import String

from app.models.trade import Trade
from app.services.trade_sync_service import TradeSyncService


def _bounded_string_columns() -> dict[str, int]:
    """Map column name -> max length for every bounded String(N) column on Trade."""
    out: dict[str, int] = {}
    for col in Trade.__table__.columns:
        if isinstance(col.type, String) and col.type.length is not None:
            out[col.name] = col.type.length
    return out


def _realistic_complete_postback(tag: str = "a" * 20) -> dict:
    """A realistic Zerodha COMPLETE fill with fields at their real max sizes.

    Kite caps `tag` at 20 chars; option symbols are the longest tradingsymbols;
    order_id / kite_order_id are ~16-digit numeric strings.
    """
    return {
        "order_id": "250726300000123456",          # ~18-digit Kite order id
        "trade_id": "250726700000123456",
        "exchange_order_id": "1100000000123456",
        "tradingsymbol": "BANKNIFTY24DEC2452000CE",  # long option symbol
        "exchange": "NFO",
        "transaction_type": "BUY",
        "order_type": "MARKET",
        "product": "MIS",
        "validity": "DAY",
        "variety": "regular",
        "quantity": 15,
        "filled_quantity": 15,
        "pending_quantity": 0,
        "cancelled_quantity": 0,
        "price": 123.45,
        "average_price": 123.45,
        "trigger_price": 0.0,
        "status": "COMPLETE",
        "status_message": None,
        "tag": tag,
        "guid": "g" * 100,                           # guid column is String(100)
        "order_timestamp": "2026-07-26 13:14:05",
        "exchange_timestamp": "2026-07-26 13:14:05",
    }


def test_transform_output_fits_all_bounded_columns():
    """Every string the transform emits must fit its String(N) column."""
    bounded = _bounded_string_columns()
    assert bounded, "expected at least one bounded String column on Trade"

    normalized = TradeSyncService.transform_zerodha_order(_realistic_complete_postback())

    for name, limit in bounded.items():
        value = normalized.get(name)
        if isinstance(value, str):
            assert len(value) <= limit, (
                f"transform emitted {name}={value!r} ({len(value)} chars) "
                f"> column limit String({limit}) — this crashes the INSERT"
            )


def test_tag_at_kite_max_boundary_fits():
    """A 20-char tag (Kite's documented max) must fit the tag column exactly."""
    tag_limit = _bounded_string_columns()["tag"]
    assert tag_limit == 20, "tag column length changed — revisit Kite's tag contract"

    normalized = TradeSyncService.transform_zerodha_order(
        _realistic_complete_postback(tag="x" * tag_limit)
    )
    assert len(normalized["tag"]) == tag_limit
