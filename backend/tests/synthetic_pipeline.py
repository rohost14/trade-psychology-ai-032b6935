"""
Drive the REAL ingestion pipeline with synthetic fills, and read back what it
wrote across every table it touches.

WHY THIS EXISTS

The audit's findings need proving fixed, and the account that produced this
book has been disconnected since 2026-07-31. Kite serves no order history
beyond the current day, so there is no way to replay a real trading session on
demand. Every later remediation phase needs to be able to ask "did this write
what it should" without waiting for a live market.

`test_adverse_add_integration.py` already proved this is possible: build a
Zerodha postback payload, hand it to `process_webhook_trade`, assert on the
rows. What it did not do is make that reusable - the payload builder, the
injection loop and the cleanup were local to that one file. This module is
those three things, generalised, plus a snapshot of all eight tables a fill
touches.

IT IS TEST INFRASTRUCTURE AND ONLY TEST INFRASTRUCTURE

Nothing under `app/` may import this - `test_no_production_code_imports_tests`
enforces that. It lives beside the tests it serves, imports nothing from
`alertlab/`, and drives production code without patching a line of it.

The no-alertlab rule is deliberate and is not tidiness. From
`test_adverse_add_integration.py:43`: the backend suite has no dependency
outside `backend/`, so it runs wherever the rest of it runs. `alertlab` has
richer helpers; reaching for them would trade a real architectural boundary for
a few saved lines.

IT WRITES COMMITTED ROWS, AND THAT IS WHY CLEANUP IS NOT OPTIONAL

`process_webhook_trade` opens its own session on its own connection in another
thread. It cannot see anything held in an uncommitted savepoint, so the
suite-wide isolation that stops tests leaking rows cannot be used here - the
same deliberate exception `test_adverse_add_integration.py` makes, for the same
reason.

The exception is paid for by `synthetic_account()`, which deletes every row it
committed in a `finally`, deepest dependency first. Use it as a context manager
and cleanup cannot be forgotten. 12,010 test users leaked into this database
over five months because a fixture committed and nothing removed the rows; that
is the failure this shape exists to prevent.

USAGE

    from tests.synthetic_pipeline import Fill, synthetic_account

    async with synthetic_account(db) as account:
        await account.submit([
            Fill("BUY",  "NIFTY25NOV26000CE", 75, 59.00),
            Fill("BUY",  "NIFTY25NOV26000CE", 75, 50.00),
            Fill("SELL", "NIFTY25NOV26000CE", 150, 40.00),
        ])
        rows = await account.snapshot()
        assert rows.completed_trades
        assert any(a["pattern_type"] == "adding_to_adverse_position"
                   for a in rows.risk_alerts)

WHAT IT CANNOT COVER, STATED PLAINLY

OAuth login, real postback delivery and its signature, live KiteTicker ticks,
the broker margin API, and token expiry against Zerodha. All of those need a
live connection and are listed in `docs/database/REMEDIATION_INDEX.md` §3 as
validation to do when the account is next connected. A fixture that quietly
implied it covered them would be worse than one that says it does not.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

#: Every table one fill can touch, ordered so deleting down the list never
#: trips a foreign key. `snapshot()` reads them and `_purge` deletes them, from
#: the same list - so a table added to the pipeline is either in both or
#: neither, and cannot be snapshotted while going uncleaned.
PIPELINE_TABLES = (
    "behavior_events",
    "risk_alerts",
    "alert_checkpoints",
    "completed_trades",
    "completed_trade_features",
    "position_ledger",
    "positions",
    "orders",
    "trades",
    "trading_sessions",
    "user_profiles",
)

#: Pipeline steps that are KNOWN BROKEN in production right now, mapped to what
#: is wrong. `submit()` tolerates a failure from these and raises on anything
#: else, so the fixture keeps working without pretending the step succeeded.
#:
#: This is NOT a place to silence an inconvenient failure. Every entry names a
#: defect that has been confirmed against the running code, and
#: `test_known_broken_steps_are_still_broken` fails the moment one starts
#: working - so a fix cannot land while the fixture quietly keeps excusing it.
#: EMPTY, and it should stay that way. The one entry it held -
#: `persist_order_event`, which raised NameError on every call because
#: `trade_tasks.py` had no `import asyncio` - was fixed the same day it was
#: found, and this test suite is what forced the entry out again:
#: `test_known_broken_steps_are_still_broken` failed the moment the task
#: started working. Add an entry only for a defect confirmed against running
#: code, never to quiet an inconvenient failure.
KNOWN_BROKEN_STEPS: dict[str, str] = {}

#: Tables that `snapshot()` returns as named attributes. A subset of the above:
#: the rest are cleaned but rarely asserted on.
SNAPSHOT_TABLES = (
    "orders",
    "trades",
    "position_ledger",
    "positions",
    "completed_trades",
    "behavior_events",
    "risk_alerts",
    "trading_sessions",
)


@dataclass(frozen=True)
class Fill:
    """
    One executed fill, in the terms a trader would describe it.

    `at` is optional: left None, fills are spaced three minutes apart from
    09:30 IST on `day`, which is what `test_adverse_add_integration.py` used
    and is far enough apart to clear the coalescing window without being so far
    apart that a session-scoped detector sees two sessions.
    """

    side: str            # BUY | SELL
    symbol: str
    quantity: int
    price: float
    at: datetime | None = None
    exchange: str = "NFO"
    product: str = "MIS"
    order_type: str = "MARKET"


@dataclass
class Snapshot:
    """Rows written by the pipeline, one list of dicts per table."""

    orders: list[dict] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)
    position_ledger: list[dict] = field(default_factory=list)
    positions: list[dict] = field(default_factory=list)
    completed_trades: list[dict] = field(default_factory=list)
    behavior_events: list[dict] = field(default_factory=list)
    risk_alerts: list[dict] = field(default_factory=list)
    trading_sessions: list[dict] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        """`{table: row count}` - the cheap before/after assertion."""
        return {name: len(getattr(self, name)) for name in SNAPSHOT_TABLES}


def postback(fill: Fill, order_id: str) -> dict:
    """
    The payload Zerodha posts, exactly as `webhooks.py` assembles it.

    Built here rather than imported from the alertlab harness - see the module
    docstring on why the backend suite keeps no dependency outside `backend/`.
    """
    stamp = fill.at.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "order_id": order_id,
        "exchange_order_id": f"X{order_id}",
        "status": "COMPLETE",
        "tradingsymbol": fill.symbol,
        "exchange": fill.exchange,
        "transaction_type": fill.side,
        "order_type": fill.order_type,
        "product": fill.product,
        "quantity": abs(fill.quantity),
        "filled_quantity": abs(fill.quantity),
        "pending_quantity": 0,
        "cancelled_quantity": 0,
        "price": fill.price,
        "average_price": fill.price,
        "trigger_price": 0.0,
        "status_message": None,
        "order_timestamp": stamp,
        "exchange_timestamp": stamp,
        "validity": "DAY",
        "variety": "regular",
        "disclosed_quantity": 0,
        "parent_order_id": None,
        "tag": "synthetic",
        "guid": None,
        "instrument_token": None,
        "raw_payload": {},
    }


class SyntheticAccount:
    """
    A throwaway account with the real pipeline behind it.

    Obtained from `synthetic_account()`, never constructed directly - the
    context manager is what guarantees the rows are removed again.
    """

    def __init__(self, session: AsyncSession, account_id, user_id):
        self.session = session
        self.account_id = account_id
        self.user_id = user_id
        self._submitted = 0
        #: {step label: the failure it produced}, for steps in
        #: KNOWN_BROKEN_STEPS. Populated as fills are submitted, and read by
        #: `test_known_broken_steps_are_still_broken` - so a step that starts
        #: working stops being excused instead of quietly staying excused.
        self.step_failures: dict[str, str] = {}

    async def submit(self, fills: list[Fill], *, day: date | None = None) -> None:
        """
        Push fills through the genuine entry point - BOTH halves of it.

        `webhooks.py` dispatches two tasks per postback, and the order matters:

          6a `persist_order_event`  - records the order-lifecycle event at
             whatever status it arrived in. This is what writes `orders`.
          6b `process_webhook_trade` - creates the trade, the ledger row and
             everything downstream, and only for a COMPLETE status.

        The first version of this fixture called only 6b, and every snapshot
        came back with `orders: 0`. That reads exactly like the audit's open
        question about `orders` never having seen a row, and it was not that
        at all - it was this fixture driving half the path. A fixture that
        covers half the entry point produces confident wrong answers, which is
        worse than covering none of it.

        Each task calls `asyncio.run()` internally, which raises inside an
        already-running loop, so both go to a thread. Celery runs eager here,
        so `.apply()` executes the real task body inline: when this returns,
        the rows exist.

        A failed task is RAISED, not logged - unless it is one of
        `KNOWN_BROKEN_STEPS`, which is recorded on `step_failures` instead.
        Both production call sites swallow this exception - audit finding M20,
        and how `orders` accepted no rows for eleven hours without anything
        going red. A fixture that swallowed it too would be useless for
        proving a fix.
        """
        from app.tasks.trade_tasks import persist_order_event, process_webhook_trade

        day = day or datetime.now().date()
        base = datetime.combine(day, datetime.min.time()) + timedelta(hours=9, minutes=30)

        for fill in fills:
            when = fill.at or base + timedelta(minutes=self._submitted * 3)
            payload = postback(
                Fill(**{**fill.__dict__, "at": when}),
                order_id=f"SYN{day:%Y%m%d}{self._submitted:04d}",
            )
            self._submitted += 1

            account = str(self.account_id)
            steps = (
                ("6a order-event", persist_order_event, [payload, account]),
                ("6b fill", process_webhook_trade, [payload, account, "synthetic"]),
            )

            def _run(steps=steps, broken=self.step_failures):
                for label, task, args in steps:
                    outcome = task.apply(args=args)
                    if not outcome.failed():
                        continue
                    if label in KNOWN_BROKEN_STEPS:
                        broken[label] = repr(outcome.result)
                        continue
                    raise AssertionError(
                        f"the {label} task failed and would have been "
                        f"swallowed in production: {outcome.result!r}"
                    )

            await asyncio.to_thread(_run)

    async def flush_entry_batch(self) -> None:
        """
        Release the entry-batch coalescing window.

        Entry-time detectors do not run per fill; they run when the batch
        flushes. Without this a ladder of adds produces no entry-time alert
        and the fixture looks like it proved an absence it never tested.
        """
        from app.tasks.position_monitor_tasks import _flush_entry_batch

        await _flush_entry_batch(str(self.account_id))

    async def snapshot(self) -> Snapshot:
        """Every row this account has, across the eight pipeline tables."""
        result = Snapshot()
        for name in SNAPSHOT_TABLES:
            rows = await self.session.execute(
                text(f"SELECT * FROM {name} WHERE broker_account_id = :a"),
                {"a": str(self.account_id)},
            )
            setattr(result, name, [dict(r) for r in rows.mappings()])
        return result


@asynccontextmanager
async def synthetic_account(session: AsyncSession, *, capital: float | None = None):
    """
    A committed throwaway user + broker account, removed again on exit.

    `session` must be one that genuinely commits. The suite's shared `db`
    fixture binds to an outer transaction and turns `commit()` into a savepoint
    release, which is what stops tests leaking rows - and which the fill task,
    on its own connection in another thread, cannot see through. Use the
    committing session the integration tests build from `make_engine()`.

    Cleanup runs in a `finally` and deletes deepest dependency first. A
    rollback cannot undo a commit, so anything committed here that is not
    deleted here stays in the database for every future run.
    """
    from app.models.broker_account import BrokerAccount
    from app.models.user import User
    from app.models.user_profile import UserProfile

    marker = uuid4().hex[:8]
    user = User(
        email=f"synthetic+{marker}@tests.invalid",
        display_name="Synthetic Pipeline",
        guardian_phone="+919999000001",
    )
    session.add(user)
    await session.flush()

    account = BrokerAccount(
        user_id=user.id,
        broker_name="zerodha",
        broker_email=user.email,
        broker_user_id=f"SYN{marker[:5].upper()}",
        status="connected",
    )
    session.add(account)
    await session.flush()

    # `trading_capital` is on UserProfile, NOT User - setting it on the user
    # succeeds silently, because assigning an undeclared attribute to a mapped
    # instance is just a Python attribute set, and the value never reaches the
    # database. The first version of this fixture did exactly that, and every
    # capital-relative detector abstained while looking like it had been given
    # a capital.
    if capital is not None:
        session.add(UserProfile(
            broker_account_id=account.id,
            trading_capital=capital,
        ))
        await session.flush()

    await session.commit()

    try:
        yield SyntheticAccount(session, account.id, user.id)
    finally:
        await _purge(session, account.id, user.id)


async def _purge(session: AsyncSession, account_id, user_id) -> None:
    """
    Delete every row this account produced, deepest dependency first.

    Each delete is its own attempt: a table that does not exist, or one the
    pipeline never wrote to, must not abort the rest of the cleanup and leave
    the account behind. The account and user deletes are NOT guarded - if
    those fail the caller has to know, because a leaked user is precisely the
    row class that reached 91% of this table.
    """
    for table in PIPELINE_TABLES:
        try:
            await session.execute(
                text(f"DELETE FROM {table} WHERE broker_account_id = :a"),
                {"a": str(account_id)},
            )
        except Exception:
            await session.rollback()

    await session.execute(
        text("DELETE FROM broker_accounts WHERE id = :a"), {"a": str(account_id)})
    await session.execute(
        text("DELETE FROM users WHERE id = :u"), {"u": str(user_id)})
    await session.commit()
