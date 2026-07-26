"""
R6 (deep-review P3): Zerodha postback checksum verification must use a
constant-time compare. Behaviour preserved (valid passes, invalid fails); this
just removes the timing side-channel. Pure test.
"""
import hashlib

from app.api.webhooks import verify_zerodha_checksum, verify_zerodha_checksum_header

SECRET = "test_api_secret"
OID = "250101000000001"
TS = "2026-07-20 09:30:00"
GOOD = hashlib.sha256(f"{OID}{TS}{SECRET}".encode()).hexdigest()


def test_valid_body_checksum_passes():
    assert verify_zerodha_checksum({"checksum": GOOD, "order_id": OID, "order_timestamp": TS}, SECRET) is True


def test_invalid_body_checksum_fails():
    assert verify_zerodha_checksum({"checksum": "deadbeef", "order_id": OID, "order_timestamp": TS}, SECRET) is False


def test_missing_checksum_fails():
    assert verify_zerodha_checksum({"order_id": OID, "order_timestamp": TS}, SECRET) is False


def test_valid_header_checksum_passes():
    assert verify_zerodha_checksum_header(OID, TS, GOOD, SECRET) is True


def test_invalid_header_checksum_fails():
    assert verify_zerodha_checksum_header(OID, TS, "nope", SECRET) is False
