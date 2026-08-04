"""
Analytics caching must never show one trader another's numbers, and never show
anyone their pre-trade numbers after a trade.

api/analytics.py had no caching at all: every Dashboard and Analytics load
recomputed multi-day Postgres aggregates, and the Analytics page fires several at
once. The reason it was not simply given a TTL is that a plain TTL is wrong here —
a trader closes a position and opens Analytics immediately, and stale numbers break
the one thing the product promises.

So invalidation is by per-account version stamp, bumped when a CompletedTrade is
written. These tests pin the three properties that make that safe: the key is
scoped to an account, a bump makes old entries unreachable, and any Redis problem
degrades to computing live rather than erroring.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.core import response_cache
from app.core.response_cache import cached_analytics, make_key


class TestKeyScoping:

    def test_different_accounts_never_share_a_key(self):
        a, b = uuid4(), uuid4()
        assert make_key(a, 1, "overview", {"days": 30}) != make_key(b, 1, "overview", {"days": 30})

    def test_different_params_never_share_a_key(self):
        acct = uuid4()
        assert make_key(acct, 1, "overview", {"days": 30}) != make_key(acct, 1, "overview", {"days": 90})

    def test_param_order_does_not_split_the_cache(self):
        acct = uuid4()
        assert (
            make_key(acct, 1, "overview", {"days": 30, "tab": "edge"})
            == make_key(acct, 1, "overview", {"tab": "edge", "days": 30})
        )

    def test_a_version_bump_makes_the_old_key_unreachable(self):
        """This is the invalidation mechanism — not key deletion, not SCAN."""
        acct = uuid4()
        assert make_key(acct, 1, "overview", {"days": 30}) != make_key(acct, 2, "overview", {"days": 30})


class TestCachedDecorator:

    async def test_second_call_is_served_from_cache(self):
        calls = []

        @cached_analytics(ttl=60)
        async def handler(days=30, broker_account_id=None):
            calls.append(days)
            return {"value": len(calls)}

        acct = uuid4()
        store = {}

        async def _get(key):
            return store.get(key)

        async def _set(key, value, ttl):
            store[key] = value

        with patch.object(response_cache, "get_account_version", AsyncMock(return_value=1)), \
             patch.object(response_cache, "cache_get", _get), \
             patch.object(response_cache, "cache_set", _set):
            first = await handler(days=30, broker_account_id=acct)
            second = await handler(days=30, broker_account_id=acct)

        assert first == second
        assert len(calls) == 1, "the handler must not run again on a cache hit"

    async def test_version_bump_forces_a_recompute(self):
        calls = []

        @cached_analytics(ttl=60)
        async def handler(days=30, broker_account_id=None):
            calls.append(days)
            return {"n": len(calls)}

        acct = uuid4()
        store = {}

        async def _get(key):
            return store.get(key)

        async def _set(key, value, ttl):
            store[key] = value

        version = {"v": 1}

        async def _version(_account_id):
            return version["v"]

        with patch.object(response_cache, "get_account_version", _version), \
             patch.object(response_cache, "cache_get", _get), \
             patch.object(response_cache, "cache_set", _set):
            await handler(days=30, broker_account_id=acct)
            version["v"] = 2                      # a CompletedTrade landed
            result = await handler(days=30, broker_account_id=acct)

        assert len(calls) == 2, "a new completed trade must invalidate the cached view"
        assert result["n"] == 2

    async def test_handler_without_an_account_is_never_cached(self):
        """No account in scope means no safe key — passing through beats guessing."""
        calls = []

        @cached_analytics(ttl=60)
        async def handler(days=30):
            calls.append(days)
            return {"n": len(calls)}

        with patch.object(response_cache, "cache_get", AsyncMock()) as get:
            await handler(days=30)
            await handler(days=30)

        assert len(calls) == 2
        get.assert_not_called()

    async def test_redis_failure_degrades_to_computing_live(self):
        """A cache that can break the page is not worth having."""
        calls = []

        @cached_analytics(ttl=60)
        async def handler(days=30, broker_account_id=None):
            calls.append(days)
            return {"n": len(calls)}

        async def _boom(*a, **kw):
            raise RuntimeError("redis down")

        with patch.object(response_cache, "get_account_version", AsyncMock(return_value=1)), \
             patch.object(response_cache, "cache_get", AsyncMock(return_value=None)), \
             patch.object(response_cache, "cache_set", _boom):
            result = await handler(days=30, broker_account_id=uuid4())

        assert result == {"n": 1}

    async def test_non_scalar_dependencies_are_not_part_of_the_key(self):
        """A db session must never be reached for in key construction."""
        captured = {}

        async def _get(key):
            captured["key"] = key
            return None

        @cached_analytics(ttl=60)
        async def handler(days=30, broker_account_id=None, db=None):
            return {"ok": True}

        class _Session:
            pass

        with patch.object(response_cache, "get_account_version", AsyncMock(return_value=1)), \
             patch.object(response_cache, "cache_get", _get), \
             patch.object(response_cache, "cache_set", AsyncMock()):
            await handler(days=30, broker_account_id=uuid4(), db=_Session())

        assert "key" in captured
