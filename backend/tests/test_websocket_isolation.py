"""
One slow client must never delay another user's alert.

THE DEFECT THIS PROVES FIXED

`send_to_account` awaits each socket with a 2-second timeout, and the event
subscriber used to `await` that whole delivery before reading the next event. So
a trader on a stalled connection delayed EVERY other trader's alerts by up to two
seconds per socket of theirs.

At one user that is invisible. At a few thousand it is the difference between a
mirror and a report — the product's entire claim is that the alert arrives while
the decision is still live.

WHAT IS ASSERTED, AND WHY IT IS TIMING-BASED

Isolation is a claim about *waiting*, so it can only be proved by measuring who
waits. These tests use a socket that blocks on send and assert that a different
account's message still arrives promptly. The margins are wide (the slow socket
blocks far longer than the assertion window) so the tests are not flaky on a
loaded machine.

Ordering within one account is asserted separately, because the fix must not buy
isolation by reordering a trader's own alerts.
"""
import asyncio
import time

import pytest

from app.api.websocket import ConnectionManager


class FakeSocket:
    """A socket that records what it received, optionally slowly."""

    def __init__(self, delay: float = 0.0):
        self.delay = delay
        self.received = []
        self.started = asyncio.Event()

    async def send_json(self, message):
        self.started.set()
        if self.delay:
            await asyncio.sleep(self.delay)
        self.received.append(message)


@pytest.mark.asyncio
async def test_a_slow_client_does_not_delay_another_account():
    """
    The regression. Account A's socket blocks for 3 seconds; account B must be
    served without waiting for it.
    """
    manager = ConnectionManager()
    slow = FakeSocket(delay=3.0)
    fast = FakeSocket()
    await manager.connect("acct-slow", slow)
    await manager.connect("acct-fast", fast)

    started = time.perf_counter()
    manager.deliver("acct-slow", {"n": 1})
    manager.deliver("acct-fast", {"n": 1})

    # Give the fast account's drain task a moment; it must not wait on the slow one.
    for _ in range(40):
        await asyncio.sleep(0.01)
        if fast.received:
            break
    elapsed = time.perf_counter() - started

    assert fast.received == [{"n": 1}], "the fast account was not served"
    assert elapsed < 1.0, (
        f"fast account waited {elapsed:.2f}s behind a slow one - deliveries are "
        "still serialised across accounts"
    )
    assert slow.received == [], "the slow socket should still be blocked"


@pytest.mark.asyncio
async def test_deliver_returns_immediately():
    """
    The subscriber calls this. If it waits for sockets, every account behind it
    in the stream waits too — which is the defect, restated.
    """
    manager = ConnectionManager()
    await manager.connect("acct", FakeSocket(delay=3.0))

    started = time.perf_counter()
    manager.deliver("acct", {"n": 1})
    elapsed = time.perf_counter() - started

    assert elapsed < 0.05, f"deliver blocked for {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_ordering_within_an_account_is_preserved():
    """
    Isolation must not be bought with reordering. A trader's own alerts have a
    sequence and it has to survive.
    """
    manager = ConnectionManager()
    sock = FakeSocket(delay=0.01)
    await manager.connect("acct", sock)

    for n in range(10):
        manager.deliver("acct", {"n": n})

    for _ in range(200):
        await asyncio.sleep(0.01)
        if len(sock.received) == 10:
            break

    assert [m["n"] for m in sock.received] == list(range(10))


@pytest.mark.asyncio
async def test_two_devices_of_one_account_do_not_block_each_other():
    """
    Same trader, phone and desktop. Nothing orders them relative to each other,
    so a stalled phone must not hold up the desktop beside it.
    """
    manager = ConnectionManager()
    slow_device = FakeSocket(delay=3.0)
    fast_device = FakeSocket()
    await manager.connect("acct", slow_device)
    await manager.connect("acct", fast_device)

    started = time.perf_counter()
    manager.deliver("acct", {"n": 1})
    for _ in range(40):
        await asyncio.sleep(0.01)
        if fast_device.received:
            break
    elapsed = time.perf_counter() - started

    assert fast_device.received == [{"n": 1}]
    assert elapsed < 1.0, f"the second device waited {elapsed:.2f}s on the first"


@pytest.mark.asyncio
async def test_a_backlogged_client_is_dropped_not_buffered_forever():
    """
    A client this far behind will read those alerts long after they mattered.
    Buffering more of its backlog spends memory for no benefit, so the queue is
    bounded and overflow is reported rather than hidden.
    """
    manager = ConnectionManager()
    await manager.connect("acct", FakeSocket(delay=30.0))

    accepted = sum(1 for n in range(manager.QUEUE_MAXSIZE + 50)
                   if manager.deliver("acct", {"n": n}))

    assert accepted <= manager.QUEUE_MAXSIZE + 1, (
        "the outbound queue is unbounded"
    )


@pytest.mark.asyncio
async def test_delivering_to_an_unknown_account_is_a_no_op():
    manager = ConnectionManager()
    assert manager.deliver("nobody", {"n": 1}) is False


@pytest.mark.asyncio
async def test_disconnect_releases_the_queue_and_its_task():
    """
    Otherwise every account that ever connected leaks a queue and a task for the
    life of the process.
    """
    manager = ConnectionManager()
    sock = FakeSocket()
    await manager.connect("acct", sock)
    manager.deliver("acct", {"n": 1})
    await asyncio.sleep(0.05)

    await manager.disconnect("acct", sock)

    assert "acct" not in manager._queues
    assert "acct" not in manager._drainers


@pytest.mark.asyncio
async def test_one_account_failing_does_not_stop_another():
    """
    A drain task raising must be contained. Before, an exception in delivery
    propagated into the subscriber loop and took the whole stream reader down.
    """
    class Exploding(FakeSocket):
        async def send_json(self, message):
            raise RuntimeError("socket exploded")

    manager = ConnectionManager()
    ok = FakeSocket()
    await manager.connect("bad", Exploding())
    await manager.connect("good", ok)

    manager.deliver("bad", {"n": 1})
    manager.deliver("good", {"n": 1})

    for _ in range(40):
        await asyncio.sleep(0.01)
        if ok.received:
            break

    assert ok.received == [{"n": 1}]


@pytest.mark.asyncio
async def test_the_old_serialised_path_would_have_blocked_and_the_new_one_does_not():
    """
    A direct A/B, so the isolation claim rests on a comparison rather than on a
    refactor being described as better.

    OLD: the subscriber awaited delivery per account, in stream order. If the
    slow account's event came first, the fast account waited behind it.
    NEW: delivery is handed to a per-account drain task and the loop moves on.

    Same two accounts, same messages, same sockets — only the dispatch strategy
    differs.
    """
    manager = ConnectionManager()
    slow = FakeSocket(delay=2.0)
    fast = FakeSocket()
    await manager.connect("slow", slow)
    await manager.connect("fast", fast)

    # OLD: await each account's delivery in turn, as the subscriber used to.
    t0 = time.perf_counter()
    await manager.send_to_account("slow", {"n": "old"})
    await manager.send_to_account("fast", {"n": "old"})
    old_elapsed = time.perf_counter() - t0

    # NEW: hand both off; the fast account is served while the slow one blocks.
    slow2 = FakeSocket(delay=2.0)
    fast2 = FakeSocket()
    manager2 = ConnectionManager()
    await manager2.connect("slow", slow2)
    await manager2.connect("fast", fast2)

    t1 = time.perf_counter()
    manager2.deliver("slow", {"n": "new"})
    manager2.deliver("fast", {"n": "new"})
    for _ in range(50):
        await asyncio.sleep(0.01)
        if fast2.received:
            break
    new_elapsed = time.perf_counter() - t1

    assert old_elapsed > 1.5, (
        f"the old path completed in {old_elapsed:.2f}s - the fixture is not "
        "actually reproducing a slow socket"
    )
    assert new_elapsed < 1.0, (
        f"the new path still took {new_elapsed:.2f}s for the fast account"
    )
    assert fast2.received == [{"n": "new"}]
    assert old_elapsed > new_elapsed * 2, (
        f"old {old_elapsed:.2f}s vs new {new_elapsed:.2f}s - no measurable "
        "isolation improvement"
    )
