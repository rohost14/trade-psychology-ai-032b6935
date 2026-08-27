"""
End to end: a real Kite LTP packet in, an alert out.

Pattern #8's primary behaviour is now the tick path, and unit tests on the
pieces do not prove the pieces are connected. These drive genuine binary tick
frames — the exact `>H` packet-count, `>H` length, `>I` token, `>I` price×100
layout `AsyncKiteTicker._handle_binary` parses off the wire — through the real
handler, and assert on what the alert writer was actually asked to write.

Nothing here is stubbed except the two edges: the Redis LTP cache write (which
predates this change and is not part of the risk evaluation) and the alert
write itself. The parsing, the throttle, the in-memory state, the crossing
logic, the consolidation and the async hand-off are all the real code.

THE PROPERTY THAT MATTERS MOST is `TestTheHotPathDoesNoIO`. The 60-second beat
this replaces failed at scale because it re-read the world every cycle; if the
tick path ever acquires a database read, a Redis read or a threshold
resolution, that failure comes straight back and no amount of architecture
documentation will catch it. So it is asserted by making those things RAISE.
"""

import asyncio
import struct as _struct
import time as _time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.live_risk_state import PositionWatch, live_risk_state
from app.services.price_stream_service import AsyncKiteTicker

TOKEN = 12345
TOKEN_B = 67890
SYMBOL = "NIFTY25AUG25000CE"
SYMBOL_B = "BANKNIFTY25AUG55000CE"
ACCOUNT = "11111111-1111-4111-8111-111111111111"
ENTRY = 100.0


def ltp_frame(*pairs) -> bytes:
    """
    A real Kite LTP-mode binary frame.

    Layout, from `_handle_binary`: number of packets as >H, then per packet a
    >H length followed by >I instrument_token and >I last_price in paise.
    """
    out = _struct.pack(">H", len(pairs))
    for token, price in pairs:
        body = _struct.pack(">I", int(token)) + _struct.pack(">I", int(round(price * 100)))
        out += _struct.pack(">H", len(body)) + body
    return out


def _watch(declared=None, epoch="e1", token=TOKEN, symbol=SYMBOL, entry=ENTRY):
    return PositionWatch(
        broker_account_id=ACCOUNT, tradingsymbol=symbol, instrument_token=token,
        epoch=epoch, avg_entry_price=entry, quantity=75,
        universal_bands=(40.0, 60.0, 80.0), declared_pct=declared,
    )


def price_at(loss_pct, entry=ENTRY):
    return entry * (1 - loss_pct / 100.0)


class Harness:
    """A real AsyncKiteTicker with only its two I/O edges captured."""

    def __init__(self):
        self.ticker = AsyncKiteTicker(token_provider=AsyncMock(return_value=None),
                                      on_tick_callback=AsyncMock())
        self.ticker._token_to_symbol = {TOKEN: SYMBOL, TOKEN_B: SYMBOL_B}
        self.fire = AsyncMock(return_value=True)
        self.ltp_writes = []

    async def tick(self, *pairs, advance=True):
        """Feed one frame and let the dispatch task finish."""
        if advance:
            # The handler throttles to one tick per second per symbol. Real time
            # does not move fast enough inside a test, so the throttle memory is
            # cleared rather than the clock faked - the throttle itself is
            # exercised by its own test below.
            self.ticker._last_tick_times.clear()
        with patch("app.core.ltp_cache.write_batch",
                   side_effect=lambda _r, prices: self.ltp_writes.append(dict(prices))), \
             patch("app.core.redis_pool.get_sync_redis", return_value=object()), \
             patch("app.tasks.position_monitor_tasks._fire_position_alert", self.fire):
            await self.ticker._handle_binary(ltp_frame(*pairs), _struct, _time)
            # the alert write is deliberately handed to a task so it cannot block
            # the price stream; drain it before asserting
            pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            if pending:
                await asyncio.wait(pending, timeout=2)

    @property
    def alerts(self):
        return [c.kwargs for c in self.fire.await_args_list]


@pytest.fixture(autouse=True)
def clean_state():
    live_risk_state.clear()
    yield
    live_risk_state.clear()


@pytest.fixture
def h():
    return Harness()


# ── the frame parses, and the price reaches the state ─────────────────────

@pytest.mark.asyncio
async def test_a_tick_frame_parses_into_the_ltp_cache(h):
    await h.tick((TOKEN, 55.0))
    assert h.ltp_writes == [{TOKEN: "55.0"}]


@pytest.mark.asyncio
async def test_a_position_under_the_first_band_produces_no_alert(h):
    live_risk_state.replace_account(ACCOUNT, [_watch()])
    await h.tick((TOKEN, price_at(35)))
    assert h.alerts == []


# ── 40 / 60 / 80 through the real handler ─────────────────────────────────

@pytest.mark.asyncio
async def test_crossing_forty_percent_reaches_the_dispatcher(h):
    live_risk_state.replace_account(ACCOUNT, [_watch()])
    await h.tick((TOKEN, price_at(45)))

    assert len(h.alerts) == 1
    a = h.alerts[0]
    assert a["pattern_type"] == "premium_loss_event"
    assert a["severity"] == "caution"
    assert a["broker_account_id"] == ACCOUNT
    assert a["details"]["symbol"] == SYMBOL
    assert a["details"]["loss_pct"] == 45.0
    assert a["details"]["live"] is True
    assert SYMBOL in a["message"]


@pytest.mark.asyncio
async def test_escalation_40_then_60_then_80_over_three_ticks(h):
    live_risk_state.replace_account(ACCOUNT, [_watch()])
    for loss in (45, 65, 85):
        await h.tick((TOKEN, price_at(loss)))
    assert [a["severity"] for a in h.alerts] == ["caution", "danger", "critical"]
    assert [a["details"]["loss_pct"] for a in h.alerts] == [45.0, 65.0, 85.0]


@pytest.mark.asyncio
async def test_sitting_inside_a_reported_band_stays_silent(h):
    live_risk_state.replace_account(ACCOUNT, [_watch()])
    await h.tick((TOKEN, price_at(45)))
    for loss in (46, 50, 59):
        await h.tick((TOKEN, price_at(loss)))
    assert len(h.alerts) == 1, "a position that is not deteriorating says nothing"


# ── the trader's declared rule, end to end ────────────────────────────────

@pytest.mark.asyncio
async def test_the_declared_rule_fires_as_a_constitution_violation(h):
    live_risk_state.replace_account(ACCOUNT, [_watch(declared=25.0)])
    await h.tick((TOKEN, price_at(30)))

    assert len(h.alerts) == 1
    a = h.alerts[0]
    assert a["pattern_type"] == "constitution_violation"
    assert a["details"]["rule"] == "sl_percent_options"
    assert a["details"]["limit_pct"] == 25.0
    assert a["details"]["current_pct"] == 30.0
    assert "25%" in a["message"]


@pytest.mark.asyncio
async def test_the_declared_rule_speaks_before_the_universal_band(h):
    """A tighter promise is reached first, and is its own event."""
    live_risk_state.replace_account(ACCOUNT, [_watch(declared=25.0)])
    await h.tick((TOKEN, price_at(30)))     # declared only
    await h.tick((TOKEN, price_at(45)))     # universal only
    assert [a["pattern_type"] for a in h.alerts] == [
        "constitution_violation", "premium_loss_event",
    ]


@pytest.mark.asyncio
async def test_a_looser_declared_rule_cannot_delay_the_safety_band(h):
    """`safety_bounds`: a declared value may only tighten."""
    live_risk_state.replace_account(ACCOUNT, [_watch(declared=90.0)])
    await h.tick((TOKEN, price_at(45)))
    assert len(h.alerts) == 1
    assert h.alerts[0]["pattern_type"] == "premium_loss_event"


# ── the overlap case: one alert, both facts ───────────────────────────────

@pytest.mark.asyncio
async def test_both_boundaries_on_one_tick_produce_exactly_one_alert(h):
    live_risk_state.replace_account(ACCOUNT, [_watch(declared=25.0)])
    await h.tick((TOKEN, price_at(45)))

    assert len(h.alerts) == 1, "one position, one alert"
    a = h.alerts[0]
    assert a["pattern_type"] == "constitution_violation"


@pytest.mark.asyncio
async def test_the_safety_finding_survives_inside_the_winning_alert(h):
    """
    Layer.SAFETY — a universal finding may never be suppressed by anything
    learned from the trader. It is carried, in both the evidence and the words.
    """
    live_risk_state.replace_account(ACCOUNT, [_watch(declared=25.0)])
    await h.tick((TOKEN, price_at(45)))

    a = h.alerts[0]
    also = a["details"]["also_crossed"]
    assert also["pattern_type"] == "premium_loss_event"
    assert also["boundary_pct"] == 40.0
    assert also["severity"] == "caution"
    assert "40% safety level" in a["message"]


# ── recovery, re-crossing, and a new position ─────────────────────────────

@pytest.mark.asyncio
async def test_recovery_then_recrossing_the_same_band_stays_silent(h):
    live_risk_state.replace_account(ACCOUNT, [_watch()])
    await h.tick((TOKEN, price_at(45)))
    await h.tick((TOKEN, price_at(15)))      # recovered
    await h.tick((TOKEN, price_at(47)))      # same band again
    assert len(h.alerts) == 1


@pytest.mark.asyncio
async def test_recovery_then_a_deeper_band_still_escalates(h):
    live_risk_state.replace_account(ACCOUNT, [_watch()])
    await h.tick((TOKEN, price_at(45)))
    await h.tick((TOKEN, price_at(10)))
    await h.tick((TOKEN, price_at(65)))
    assert [a["severity"] for a in h.alerts] == ["caution", "danger"]


@pytest.mark.asyncio
async def test_a_new_position_in_the_same_symbol_starts_a_new_story(h):
    live_risk_state.replace_account(ACCOUNT, [_watch(epoch="e1")])
    await h.tick((TOKEN, price_at(45)))
    # closed and re-entered: same symbol, new epoch
    live_risk_state.replace_account(ACCOUNT, [_watch(epoch="e2")])
    await h.tick((TOKEN, price_at(45)))
    assert len(h.alerts) == 2


# ── missing and stale data must never invent a loss ───────────────────────

@pytest.mark.asyncio
async def test_a_tick_for_an_unwatched_instrument_says_nothing(h):
    live_risk_state.replace_account(ACCOUNT, [_watch(token=TOKEN)])
    await h.tick((TOKEN_B, price_at(90)))
    assert h.alerts == []


@pytest.mark.asyncio
async def test_no_state_at_all_produces_no_alerts(h):
    """Before the first rebuild — e.g. straight after a restart — silence."""
    await h.tick((TOKEN, price_at(95)))
    assert h.alerts == []


@pytest.mark.asyncio
async def test_a_truncated_frame_is_ignored(h):
    live_risk_state.replace_account(ACCOUNT, [_watch()])
    with patch("app.tasks.position_monitor_tasks._fire_position_alert", h.fire):
        await h.ticker._handle_binary(b"\x00", _struct, _time)
        await h.ticker._handle_binary(b"", _struct, _time)
    assert h.alerts == []


@pytest.mark.asyncio
async def test_a_zero_price_does_not_become_a_hundred_percent_lie(h):
    """
    A zero print is bad data, not a total loss. It clamps at 100 rather than
    producing something impossible, and the clamp is the same one the exit path
    applies.
    """
    live_risk_state.replace_account(ACCOUNT, [_watch()])
    await h.tick((TOKEN, 0.0))
    assert len(h.alerts) == 1
    assert h.alerts[0]["details"]["loss_pct"] == 100.0


@pytest.mark.asyncio
async def test_the_one_second_throttle_still_applies(h):
    """
    A burst on one instrument is one evaluation, not many. Without clearing the
    throttle memory the second frame is dropped before it ever reaches the state.
    """
    live_risk_state.replace_account(ACCOUNT, [_watch()])
    await h.tick((TOKEN, price_at(20)))
    await h.tick((TOKEN, price_at(45)), advance=False)   # throttled away
    assert h.alerts == []


# ── reconnect and refresh must not re-announce ────────────────────────────

@pytest.mark.asyncio
async def test_a_subscription_refresh_does_not_repeat_an_alert(h):
    """
    `refresh_subscriptions` rebuilds the account on every fill, including fills
    in unrelated symbols. Band memory is carried across for an unchanged epoch,
    so a rebuild cannot re-announce something the trader already heard.
    """
    live_risk_state.replace_account(ACCOUNT, [_watch(epoch="e1")])
    await h.tick((TOKEN, price_at(45)))
    live_risk_state.replace_account(ACCOUNT, [_watch(epoch="e1")])   # rebuild
    await h.tick((TOKEN, price_at(47)))
    assert len(h.alerts) == 1


@pytest.mark.asyncio
async def test_a_rebuild_after_a_gap_still_escalates_on_a_deeper_band(h):
    live_risk_state.replace_account(ACCOUNT, [_watch(epoch="e1")])
    await h.tick((TOKEN, price_at(45)))
    live_risk_state.replace_account(ACCOUNT, [_watch(epoch="e1")])
    await h.tick((TOKEN, price_at(85)))
    assert [a["severity"] for a in h.alerts] == ["caution", "critical"]


@pytest.mark.asyncio
async def test_a_closed_position_stops_alerting_after_the_rebuild(h):
    live_risk_state.replace_account(ACCOUNT, [
        _watch(token=TOKEN, epoch="e1"),
        _watch(token=TOKEN_B, symbol=SYMBOL_B, epoch="e2"),
    ])
    live_risk_state.replace_account(ACCOUNT, [_watch(token=TOKEN, epoch="e1")])
    await h.tick((TOKEN_B, price_at(90)))
    assert h.alerts == []


# ── two positions in one frame ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_two_positions_in_one_frame_produce_two_alerts(h):
    """
    The bug the old account-scoped exit dedup had: 7 of 48 detections swallowed,
    one a critical at 86.7%.
    """
    live_risk_state.replace_account(ACCOUNT, [
        _watch(token=TOKEN, symbol=SYMBOL, epoch="e1"),
        _watch(token=TOKEN_B, symbol=SYMBOL_B, epoch="e2"),
    ])
    await h.tick((TOKEN, price_at(45)), (TOKEN_B, price_at(85)))

    assert len(h.alerts) == 2
    by_symbol = {a["details"]["symbol"]: a["severity"] for a in h.alerts}
    assert by_symbol == {SYMBOL: "caution", SYMBOL_B: "critical"}


# ── the property the whole design rests on ────────────────────────────────

class TestTheHotPathDoesNoIO:
    """
    Asserted by making I/O raise, not by reading the source.

    The beat this replaces did ~20,001 database round trips a minute at 10k
    users. If evaluation ever acquires a read, that returns — so the test breaks
    the moment it does.
    """

    def _watched(self):
        live_risk_state.clear()
        live_risk_state.replace_account(ACCOUNT, [_watch(declared=25.0)])

    def test_evaluation_touches_no_database(self):
        self._watched()
        boom = lambda *a, **k: pytest.fail("the tick path opened a DB session")
        with patch("app.core.database.SessionLocal", boom):
            out = live_risk_state.evaluate_batch({TOKEN: price_at(45)})
        assert len(out) == 2

    def test_evaluation_reads_no_redis(self):
        self._watched()
        boom = lambda *a, **k: pytest.fail("the tick path read Redis")
        with patch("app.core.redis_pool.get_sync_redis", boom), \
             patch("app.core.ltp_cache.read", boom):
            assert live_risk_state.evaluate_batch({TOKEN: price_at(45)})

    def test_evaluation_resolves_no_thresholds(self):
        """
        The beat called `get_thresholds` once per account per minute — a full
        ladder walk. The bands are baked into the watch when it is built.
        """
        self._watched()
        boom = lambda *a, **k: pytest.fail("the tick path resolved thresholds")
        with patch("app.core.trading_defaults.get_thresholds", boom), \
             patch("app.core.threshold_resolution.resolve_thresholds", boom):
            assert live_risk_state.evaluate_batch({TOKEN: price_at(45)})

    def test_evaluation_opens_no_sockets(self):
        self._watched()
        import socket

        def boom(*a, **k):
            pytest.fail("the tick path opened a socket")

        with patch.object(socket.socket, "connect", boom), \
             patch.object(socket.socket, "connect_ex", boom):
            assert live_risk_state.evaluate_batch({TOKEN: price_at(45)})

    @pytest.mark.asyncio
    async def test_the_alert_write_is_handed_off_not_awaited_inline(self):
        """
        The dispatcher touches the database. It must never do so inside the tick
        handler, or one slow write stalls the price stream for every user.
        """
        self._watched()
        ticker = AsyncKiteTicker(token_provider=AsyncMock(return_value=None),
                                 on_tick_callback=AsyncMock())
        ticker._token_to_symbol = {TOKEN: SYMBOL}

        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_fire(**kwargs):
            started.set()
            await release.wait()
            return True

        with patch("app.core.ltp_cache.write_batch", lambda *a, **k: None), \
             patch("app.core.redis_pool.get_sync_redis", return_value=object()), \
             patch("app.tasks.position_monitor_tasks._fire_position_alert", slow_fire):
            await asyncio.wait_for(
                ticker._handle_binary(ltp_frame((TOKEN, price_at(45))), _struct, _time),
                timeout=1.0,
            )
            # the handler returned while the write is still blocked
            await asyncio.wait_for(started.wait(), timeout=1.0)
            release.set()
            pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            if pending:
                await asyncio.wait(pending, timeout=2)
