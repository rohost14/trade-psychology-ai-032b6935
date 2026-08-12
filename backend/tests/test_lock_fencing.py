"""
The per-account detection lock must survive its own TTL expiring.

Every counter and dedup check in trade_tasks.py assumes detection never runs
twice concurrently on one account. With a constant lock value and an
unconditional DELETE, that assumption breaks in a way nothing observes:

    A acquires (ttl 60s) -> A runs long, key expires -> B acquires
    -> A finishes and DELETEs B's key -> C acquires while B still runs
"""
from app.tasks.trade_tasks import _acquire_lock, _release_lock


class _FakeRedis:
    """SET NX EX and EVAL, enough to model the race."""

    def __init__(self):
        self.store = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    def delete(self, key):
        self.store.pop(key, None)

    def eval(self, script, numkeys, key, arg):
        # Mirrors _RELEASE_IF_MINE: delete only when the token still matches.
        if self.store.get(key) == arg:
            del self.store[key]
            return 1
        return 0

    def expire_now(self, key):
        self.store.pop(key, None)


def test_acquire_returns_a_token_and_blocks_a_second_holder():
    r = _FakeRedis()
    first = _acquire_lock(r, "behavior_lock:acct", 60)
    second = _acquire_lock(r, "behavior_lock:acct", 60)

    assert first
    assert second is None


def test_release_after_ttl_expiry_does_not_free_another_workers_lock():
    """The whole point of the token."""
    r = _FakeRedis()
    key = "behavior_lock:acct"

    a_token = _acquire_lock(r, key, 60)
    r.expire_now(key)                      # A's detection outran its TTL
    b_token = _acquire_lock(r, key, 60)    # B legitimately acquires

    _release_lock(r, key, a_token)         # A's finally block runs late

    assert r.store.get(key) == b_token, "A deleted B's lock"
    assert _acquire_lock(r, key, 60) is None, "a third worker got in"


def test_release_with_the_right_token_frees_the_lock():
    r = _FakeRedis()
    key = "behavior_lock:acct"
    token = _acquire_lock(r, key, 60)

    _release_lock(r, key, token)

    assert key not in r.store
    assert _acquire_lock(r, key, 60)


def test_release_survives_a_redis_error():
    """A failed release must not fail the task — the TTL still clears it."""
    class _Broken(_FakeRedis):
        def eval(self, *a, **k):
            raise RuntimeError("connection reset")

    r = _Broken()
    token = _acquire_lock(r, "k", 60)
    _release_lock(r, "k", token)           # must not raise


def test_tokenless_release_is_still_supported():
    r = _FakeRedis()
    _acquire_lock(r, "k", 60)

    _release_lock(r, "k")

    assert "k" not in r.store
