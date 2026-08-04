"""
Only one instance may own the KiteTicker.

SharedPriceStream keeps the ticker and its subscription maps in PROCESS memory, so
a second FastAPI instance opens a SECOND connection to Zerodha: duplicate ticks,
split subscription state, and `subscription_refresh` events landing on whichever
instance happened to read them. That is the one split brain the Redis Streams event
bus does not already solve — alerts fan out to every instance, so those are fine.

The single most important property here is the DEFAULT: with
PRICE_STREAM_MULTI_INSTANCE off, nothing changes. One process, one ticker,
in-process fan-out, no extra Redis traffic. A regression that made a single-instance
deployment depend on a lease would take the live price feed down.
"""

from unittest.mock import AsyncMock, patch

from app.services.price_stream_service import SharedPriceStream


class TestTickerOwnership:

    def test_single_instance_always_owns_the_ticker(self):
        """The default path must not consult a lease at all."""
        stream = SharedPriceStream()
        with patch.object(SharedPriceStream, "_multi_instance", staticmethod(lambda: False)):
            assert stream._may_own_ticker() is True

    def test_multi_instance_defers_to_the_lease(self):
        stream = SharedPriceStream()
        with patch.object(SharedPriceStream, "_multi_instance", staticmethod(lambda: True)), \
             patch("app.services.ticker_lease.is_owner", return_value=False):
            assert stream._may_own_ticker() is False

        with patch.object(SharedPriceStream, "_multi_instance", staticmethod(lambda: True)), \
             patch("app.services.ticker_lease.is_owner", return_value=True):
            assert stream._may_own_ticker() is True

    async def test_non_owner_never_builds_a_ticker(self):
        """The actual split-brain guard: no lease, no second connection to Zerodha."""
        stream = SharedPriceStream()
        with patch.object(SharedPriceStream, "_multi_instance", staticmethod(lambda: True)), \
             patch("app.services.ticker_lease.is_owner", return_value=False), \
             patch.object(stream, "_build_ticker", new=AsyncMock()) as build:
            ticker = await stream._ensure_ticker(db=None)

        assert ticker is None
        build.assert_not_called()


class TestTickDelivery:

    async def test_single_instance_delivers_locally_without_redis(self):
        """No publish hop when there is nobody else to publish to."""
        stream = SharedPriceStream()
        stream._token_holders[111] = {"acct-a"}

        sent = []

        async def _capture(account_id, msg):
            sent.append((account_id, msg))

        with patch.object(SharedPriceStream, "_multi_instance", staticmethod(lambda: False)), \
             patch("app.api.websocket.manager.send_to_account", new=_capture):
            await stream.broadcast_ltp("NIFTY", {"instrument_token": 111, "last_price": 42.5})

        assert len(sent) == 1
        account_id, msg = sent[0]
        assert account_id == "acct-a"
        assert msg["type"] == "ltp_update"
        assert msg["data"]["last_price"] == 42.5

    async def test_multi_instance_publishes_instead_of_delivering(self):
        """
        The owner must NOT deliver locally as well — it holds the ticker but not
        necessarily the clients, and doing both would double-send to its own.
        """
        stream = SharedPriceStream()
        stream._token_holders[111] = {"acct-a"}

        redis = AsyncMock()
        with patch.object(SharedPriceStream, "_multi_instance", staticmethod(lambda: True)), \
             patch("app.core.redis_pool.get_async_redis", new=AsyncMock(return_value=redis)), \
             patch.object(stream, "deliver_ltp_locally", new=AsyncMock()) as local:
            await stream.broadcast_ltp("NIFTY", {"instrument_token": 111, "last_price": 42.5})

        local.assert_not_called()
        redis.publish.assert_awaited_once()
        channel, payload = redis.publish.await_args.args
        assert channel == "ticks"
        assert "42.5" in payload and "111" in payload

    async def test_delivery_skips_instruments_this_instance_does_not_hold(self):
        """Each instance routes with its OWN map, so it reaches only its own clients."""
        stream = SharedPriceStream()
        sent = []

        async def _capture(account_id, msg):
            sent.append(account_id)

        with patch("app.api.websocket.manager.send_to_account", new=_capture):
            await stream.deliver_ltp_locally("NIFTY", 42.5, 999)

        assert sent == []

    async def test_publish_failure_never_raises(self):
        """A dropped tick is replaced a second later; an exception kills the ticker."""
        stream = SharedPriceStream()
        stream._token_holders[111] = {"acct-a"}

        redis = AsyncMock()
        redis.publish.side_effect = RuntimeError("redis down")
        with patch.object(SharedPriceStream, "_multi_instance", staticmethod(lambda: True)), \
             patch("app.core.redis_pool.get_async_redis", new=AsyncMock(return_value=redis)):
            await stream.broadcast_ltp("NIFTY", {"instrument_token": 111, "last_price": 42.5})
