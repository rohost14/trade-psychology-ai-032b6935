"""
EOD fan-out must stay bounded and must not sync accounts that did not trade.

The original queued every connected account in one loop onto the `trades` queue —
the same queue process_webhook_trade uses to produce live behavioural alerts. At
scale that put every live fill behind thousands of batch syncs, so alerts stopped
being live exactly when the market closed. It also synced accounts with no fills at
all, which is pure waste: the job exists to catch fills the webhook missed, and an
account with no fills today has none to catch.

Kite's REST limit is 3 req/s per API key, and under Model A that one key is shared
by every user — so the work is rate-bound regardless of worker count. Cutting the
population is the only thing that actually makes it finish sooner.

These tests drive the real task against the database with Celery dispatch stubbed,
so they assert what was queued, with which arguments, and onto which queue.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from app.models.broker_account import BrokerAccount
from app.models.trade import Trade
from app.models.user import User
from app.tasks import trade_tasks
from tests.helpers import make_email

IST_OFFSET = timedelta(hours=5, minutes=30)


def _today_ist_utc_start() -> datetime:
    from zoneinfo import ZoneInfo
    today_ist = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    return datetime.combine(today_ist, datetime.min.time()).replace(
        tzinfo=timezone.utc
    ) - IST_OFFSET


async def _account(db, *, connected=True, token="tok"):
    u = User(email=make_email(), display_name="EOD QA")
    db.add(u)
    await db.flush()
    ba = BrokerAccount(
        user_id=u.id,
        broker_name="zerodha",
        broker_email=u.email,
        broker_user_id=f"QA{uuid4().hex[:6]}",
        status="connected" if connected else "disconnected",
        access_token=token,
    )
    db.add(ba)
    await db.flush()
    return ba


async def _trade_today(db, account, *, minutes_ago=30):
    t = Trade(
        broker_account_id=account.id,
        order_id=f"ORD_{uuid4().hex[:10]}",
        tradingsymbol="NIFTY26AUGFUT",
        exchange="NFO",
        transaction_type="BUY",
        order_type="MARKET",
        product="MIS",
        quantity=50,
        filled_quantity=50,
        status="COMPLETE",
        asset_class="DERIVATIVE",
        instrument_type="FUT",
        product_type="MIS",
        order_timestamp=_today_ist_utc_start() + timedelta(hours=4),
    )
    db.add(t)
    await db.flush()
    return t


class TestEodDispatch:

    async def test_account_with_no_trades_today_is_not_queued(self, db):
        """
        The expensive mistake: syncing every connected account regardless.

        Uses a fully eligible account (connected, has a token) so the ONLY reason it
        can be skipped is the absence of trades today. The shared `broker` fixture
        has no access_token, which would have made this pass for the wrong reason.
        """
        account = await _account(db)

        with patch.object(trade_tasks.sync_trades_for_account, "apply_async") as send, \
             patch.object(trade_tasks.eod_sync_all_accounts, "apply_async"), \
             patch("app.tasks.trade_tasks.SessionLocal", return_value=_SessionCtx(db)):
            result = await trade_tasks.eod_dispatch_chunk()

        queued_ids = [c.kwargs["args"][0] for c in send.call_args_list]
        assert str(account.id) not in queued_ids
        assert result["queued"] == 0

    async def test_account_that_traded_today_is_queued_onto_bulk(self, db):
        account = await _account(db)
        await _trade_today(db, account)

        with patch.object(trade_tasks.sync_trades_for_account, "apply_async") as send, \
             patch.object(trade_tasks.eod_sync_all_accounts, "apply_async"), \
             patch("app.tasks.trade_tasks.SessionLocal", return_value=_SessionCtx(db)):
            await trade_tasks.eod_dispatch_chunk()

        calls = {c.kwargs["args"][0]: c.kwargs for c in send.call_args_list}
        assert str(account.id) in calls
        assert calls[str(account.id)]["queue"] == "bulk", (
            "must not share the trades queue with live webhook processing"
        )

    async def test_account_without_a_token_is_not_queued(self, db):
        """Traded today, but no usable token — syncing it can only fail."""
        account = await _account(db, token=None)
        await _trade_today(db, account)

        with patch.object(trade_tasks.sync_trades_for_account, "apply_async") as send, \
             patch.object(trade_tasks.eod_sync_all_accounts, "apply_async"), \
             patch("app.tasks.trade_tasks.SessionLocal", return_value=_SessionCtx(db)):
            await trade_tasks.eod_dispatch_chunk()

        queued_ids = [c.kwargs["args"][0] for c in send.call_args_list]
        assert str(account.id) not in queued_ids

    async def test_dispatch_is_chunked_and_reschedules_itself(self, db):
        """Queue depth stays bounded; the dispatcher carries a cursor forward."""
        accounts = []
        for _ in range(3):
            a = await _account(db)
            await _trade_today(db, a)
            accounts.append(a)

        with patch.object(trade_tasks, "EOD_CHUNK_SIZE", 2), \
             patch.object(trade_tasks.sync_trades_for_account, "apply_async") as send, \
             patch.object(trade_tasks.eod_sync_all_accounts, "apply_async") as again, \
             patch("app.tasks.trade_tasks.SessionLocal", return_value=_SessionCtx(db)):
            result = await trade_tasks.eod_dispatch_chunk()

        assert len(send.call_args_list) == 2, "chunk size must cap one pass"
        assert result["done"] is False
        again.assert_called_once()
        follow_up = again.call_args.kwargs
        assert follow_up["kwargs"]["after_id"], "cursor must be carried to the next pass"
        assert follow_up["countdown"] == trade_tasks.EOD_CHUNK_INTERVAL

    async def test_final_pass_reports_done_and_stops(self, db):
        """An empty chunk ends the chain rather than rescheduling forever."""
        with patch.object(trade_tasks.sync_trades_for_account, "apply_async") as send, \
             patch.object(trade_tasks.eod_sync_all_accounts, "apply_async") as again, \
             patch("app.tasks.trade_tasks.SessionLocal", return_value=_SessionCtx(db)):
            result = await trade_tasks.eod_dispatch_chunk(
                after_id=str(uuid4()), queued_so_far=7
            )

        assert result == {"queued": 7, "done": True}
        send.assert_not_called()
        again.assert_not_called()


class _SessionCtx:
    """
    Hand the task the test's session instead of opening a new one.

    The task runs its own asyncio.run() with `async with SessionLocal() as db`, so a
    plain object is not enough — it needs the async context-manager protocol, and it
    must NOT close the session the fixture still owns.
    """

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False
