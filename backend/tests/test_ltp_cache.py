"""
The LTP cache must cost one Redis command per tick batch, and must still go quiet
when an instrument stops trading.

It used to write one `SET ltp:{token}` per instrument inside a pipeline. A pipeline
saves round-trips, not commands, and a per-command Redis plan bills every one — at
~2,500 watched instruments ticking once a second that is ~1.2 billion commands a
month just to cache prices. Zerodha already delivers ticks in batches; the old code
unpacked them and issued a command each.

The risky half of the change is staleness. The old design leaned on a 2-second
per-key TTL, so an instrument that stopped ticking simply disappeared and callers
correctly saw "no live price". A hash cannot expire individual fields, so the write
timestamp travels with the price. If that check were wrong, an illiquid option that
stopped trading would serve its last price forever and every P&L and alert built on
it would silently drift — which is worse than the cost problem being fixed.
"""

import time

from app.core import ltp_cache
from app.core.ltp_cache import LTP_HASH, read, write_batch


class FakeRedis:
    """Minimal hash store that also records how many commands were issued."""

    def __init__(self):
        self.hashes = {}
        self.commands = 0

    def hset(self, key, mapping=None):
        self.commands += 1
        self.hashes.setdefault(key, {}).update(mapping or {})

    def hget(self, key, field):
        self.commands += 1
        return self.hashes.get(key, {}).get(field)

    def expire(self, key, ttl):
        self.commands += 1

    def pipeline(self, transaction=False):
        return _FakePipeline(self)


class _FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.ops = []

    def hset(self, key, mapping=None):
        self.ops.append(("hset", key, mapping))

    def expire(self, key, ttl):
        self.ops.append(("expire", key, ttl))

    def execute(self):
        for op in self.ops:
            if op[0] == "hset":
                self.redis.hset(op[1], mapping=op[2])
            else:
                self.redis.expire(op[1], op[2])
        self.ops = []


class TestCommandCount:

    def test_a_whole_batch_costs_two_commands(self):
        """The entire point: 50 instruments must not be 50 commands."""
        r = FakeRedis()
        write_batch(r, {i: 100.0 + i for i in range(50)})
        assert r.commands == 2, "one HSET for the batch, one EXPIRE"

    def test_an_empty_batch_costs_nothing(self):
        r = FakeRedis()
        write_batch(r, {})
        assert r.commands == 0


class TestRoundTrip:

    def test_price_survives_the_round_trip(self):
        r = FakeRedis()
        write_batch(r, {12345: 987.65})
        assert read(r, 12345) == 987.65

    def test_unknown_instrument_reads_as_none(self):
        r = FakeRedis()
        write_batch(r, {12345: 100.0})
        assert read(r, 99999) is None

    def test_every_instrument_in_the_batch_is_readable(self):
        r = FakeRedis()
        write_batch(r, {1: 10.5, 2: 20.5, 3: 30.5})
        assert [read(r, t) for t in (1, 2, 3)] == [10.5, 20.5, 30.5]


class TestStaleness:

    def test_a_price_older_than_the_window_reads_as_none(self):
        """
        The behaviour the per-key TTL used to give for free. Without it, an
        instrument that stopped trading keeps serving its last price forever.
        """
        r = FakeRedis()
        stale_ms = int(time.time() * 1000) - (ltp_cache.STALE_MS + 500)
        r.hashes[LTP_HASH] = {"777": f"250.0:{stale_ms}"}
        assert read(r, 777) is None

    def test_a_fresh_price_is_returned(self):
        r = FakeRedis()
        fresh_ms = int(time.time() * 1000) - 100
        r.hashes[LTP_HASH] = {"777": f"250.0:{fresh_ms}"}
        assert read(r, 777) == 250.0

    def test_a_corrupt_value_reads_as_none_rather_than_raising(self):
        """A bad field must not take down position monitoring for every symbol."""
        r = FakeRedis()
        r.hashes[LTP_HASH] = {"777": "not-a-price"}
        assert read(r, 777) is None


class TestFailureIsSilent:

    def test_a_write_failure_never_raises(self):
        """An exception here would kill the ticker; the next tick replaces the loss."""
        class Broken:
            def pipeline(self, transaction=False):
                raise RuntimeError("redis down")

        write_batch(Broken(), {1: 100.0})

    def test_a_read_failure_returns_none(self):
        class Broken:
            def hget(self, *a, **kw):
                raise RuntimeError("redis down")

        assert read(Broken(), 1) is None
