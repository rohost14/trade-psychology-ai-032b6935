"""
DP2 (deep-review P6): the DPDP account-deletion Redis purge must include the
per-account event-replay stream (holds trade/alert payloads) and the current
rate-limit key shape (rl:acct:{id}:* after the F3/A1 fix). Pure test of the
pattern list (no Redis).
"""
from app.api.account_data import _redis_purge_patterns


def test_purge_includes_event_stream():
    pats = _redis_purge_patterns("ACC-1")
    assert "stream:ACC-1" in pats, "per-account event-replay stream must be purged (DP2)"


def test_purge_includes_current_rate_limit_key_shape():
    pats = _redis_purge_patterns("ACC-1")
    # F3/A1 changed the authed key to rl:acct:{bid}:{path}
    assert any(p.startswith("rl:acct:ACC-1") for p in pats), "new rl:acct: key shape must be purged"


def test_purge_keeps_core_account_keys():
    pats = _redis_purge_patterns("ACC-1")
    for expected in ("margin:ACC-1", "behavior_lock:ACC-1", "fifo_lock:ACC-1", "circuit:ACC-1:*"):
        assert expected in pats
