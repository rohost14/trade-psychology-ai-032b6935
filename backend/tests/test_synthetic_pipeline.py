"""
The synthetic fixture, proved to work, and the boundary it must not cross.

WHY THIS FILE EXISTS

`synthetic_pipeline.py` is the validation capability every later remediation
phase depends on. If it silently stops driving the real pipeline - a task
signature changes, the entry batch moves, a table is renamed - then every phase
that used it to prove a fix proved nothing, and nothing would have said so.

So the fixture is tested like production code: it must write rows, it must
clean them up completely, and it must fail loudly rather than quietly when the
pipeline underneath it breaks. The migration runner that shipped in `eb89a56`
had eight passing tests and failed on first real use, because all eight
asserted on source text; these run the thing.

These tests COMMIT to the application database and delete what they wrote. They
need Redis for the entry-batch path and skip visibly without it.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text

from tests.synthetic_pipeline import (
    KNOWN_BROKEN_STEPS,
    PIPELINE_TABLES,
    SNAPSHOT_TABLES,
    Fill,
    postback,
    synthetic_account,
)

# No module-level asyncio mark: pytest.ini sets asyncio_mode=auto, so the
# async tests here are marked automatically and the sync ones stay unmarked.
APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def _redis_or_skip():
    try:
        from app.core.redis_pool import get_sync_redis

        get_sync_redis().ping()
    except Exception as err:  # pragma: no cover - environment dependent
        pytest.skip(f"redis unavailable, the entry-batch path cannot run: {err}")


@pytest_asyncio.fixture
async def committing_session():
    """
    A session that genuinely commits.

    The shared `db` fixture turns `commit()` into a savepoint release so tests
    cannot leak rows - correct everywhere else, and unusable here: the fill
    task runs on its own connection in another thread and would not see the
    account at all. The fixture cleans up after itself, which is what makes
    the exception affordable.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from tests.conftest import make_engine

    engine = make_engine()
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
        await session.rollback()
    await engine.dispose()


# ── the boundary the fixture must not cross ────────────────────────────────

def test_no_production_code_imports_the_test_package():
    """
    Test scaffolding must never become a production dependency.

    Asserted by parsing every module under `app/` rather than grepping, so a
    conditional or function-local `import tests...` is caught too - a grep for
    a top-of-file import would miss both.
    """
    offenders: list[str] = []

    for path in APP_ROOT.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:  # pragma: no cover - a broken file is another test's problem
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                if name == "tests" or name.startswith("tests."):
                    offenders.append(f"{path.relative_to(APP_ROOT.parent)}:{node.lineno} -> {name}")

    assert not offenders, (
        "production code under app/ imports the test package:\n  "
        + "\n  ".join(offenders)
        + "\nTest fixtures must not be reachable from a running server."
    )


def test_the_fixture_does_not_import_alertlab():
    """
    The backend suite keeps no dependency outside `backend/`, so it runs
    wherever the rest of it runs - stated at
    `test_adverse_add_integration.py:43`. `alertlab` has richer helpers and
    reaching for them would trade a real architectural boundary for a few
    saved lines.
    """
    source = (Path(__file__).parent / "synthetic_pipeline.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")

    crossings = sorted(
        name for name in imported
        if name == "alertlab" or name.startswith("alertlab.")
    )
    assert not crossings, f"synthetic_pipeline imports alertlab: {crossings}"


def test_every_snapshotted_table_is_also_cleaned_up():
    """
    A table that can be asserted on but is not purged is a row leak with a
    test pointing straight at it.
    """
    uncleaned = sorted(set(SNAPSHOT_TABLES) - set(PIPELINE_TABLES))
    assert not uncleaned, (
        f"snapshot reads {uncleaned} but cleanup never deletes from them"
    )


# ── the payload the whole path rests on ────────────────────────────────────

def test_the_postback_payload_has_the_fields_the_webhook_reads():
    """
    A missing key here fails deep inside the task with a message about
    something else. Pinned against the field list `webhooks.py` assembles.
    """
    from datetime import datetime

    fill = Fill("BUY", "NIFTY25NOV26000CE", 75, 59.0, at=datetime(2026, 9, 6, 9, 30))
    payload = postback(fill, order_id="SYN1")

    for key in ("order_id", "status", "tradingsymbol", "exchange",
                "transaction_type", "product", "quantity", "filled_quantity",
                "average_price", "order_timestamp", "exchange_timestamp"):
        assert key in payload, f"postback payload is missing {key!r}"

    assert payload["status"] == "COMPLETE"
    assert payload["filled_quantity"] == 75
    assert payload["order_timestamp"] == "2026-09-06 09:30:00"


# ── it actually drives the pipeline ────────────────────────────────────────

async def test_fills_produce_rows_across_the_pipeline(committing_session):
    """
    THE ONE THAT MATTERS. A round trip - two adds and an exit - has to reach
    `trades`, the ledger and `completed_trades`. If this goes quiet, every
    phase that used this fixture to prove a fix proved nothing.
    """
    _redis_or_skip()

    async with synthetic_account(committing_session, capital=100000) as account:
        await account.submit([
            Fill("BUY", "NIFTY25NOV26000CE", 75, 59.00),
            Fill("BUY", "NIFTY25NOV26000CE", 75, 50.00),
            Fill("SELL", "NIFTY25NOV26000CE", 150, 40.00),
        ])
        await account.flush_entry_batch()

        rows = await account.snapshot()

        assert rows.trades, (
            "three fills produced no trades rows - the pipeline is not "
            f"running. Counts: {rows.counts()}"
        )
        assert len(rows.trades) == 3, rows.counts()
        assert rows.position_ledger, (
            f"no ledger rows; the detectors read the ledger, not positions. "
            f"Counts: {rows.counts()}"
        )
        assert rows.completed_trades, (
            f"the position was fully exited and no CompletedTrade was written. "
            f"Counts: {rows.counts()}"
        )


async def test_a_losing_ladder_reaches_the_behaviour_engine(committing_session):
    """
    The same ladder the adverse-add integration test uses, asserted one level
    up: the engine ran at all. Which pattern fires is that detector's own
    test; what this pins is that the fixture reaches the engine, so a phase
    asserting "no new alerts" is asserting on a path that was alive.
    """
    _redis_or_skip()

    async with synthetic_account(committing_session, capital=100000) as account:
        await account.submit([
            Fill("BUY", "NIFTY25NOV26000CE", 75, 59.00),
            Fill("BUY", "NIFTY25NOV26000CE", 75, 50.00),
            Fill("BUY", "NIFTY25NOV26000CE", 75, 42.70),
            Fill("BUY", "NIFTY25NOV26000CE", 75, 34.35),
        ])

        # Flush BEFORE the exit, which is what happens in a real session: the
        # batch releases on a timer while the position is still open. Flushing
        # after the exit finds nothing open and the entry-time detectors
        # correctly abstain - the first version of this test did that, and
        # read the resulting silence as the engine being unreachable.
        await account.flush_entry_batch()

        await account.submit([Fill("SELL", "NIFTY25NOV26000CE", 300, 30.00)])

        rows = await account.snapshot()
        assert rows.completed_trades, rows.counts()
        assert rows.risk_alerts or rows.behavior_events, (
            "an averaging-down ladder into a full loss produced neither a "
            f"RiskAlert nor a BehaviorEvent. Counts: {rows.counts()}"
        )


async def test_an_order_event_reaches_the_orders_table(committing_session):
    """
    THE REGRESSION, and the reason `orders` was empty.

    `persist_order_event` called `asyncio.run()` in a module with no
    `import asyncio` and had no function-local one either - alone among the
    nine tasks in that file that call it. Every invocation raised NameError,
    retried three times and was swallowed at both call sites, so the table
    took zero rows and nothing said so. The audit read that emptiness as "the
    feature shipped after the last trading session and was never exercised".

    Nothing detected it because nothing ran the task. This does.
    """
    _redis_or_skip()

    async with synthetic_account(committing_session) as account:
        await account.submit([Fill("BUY", "NIFTY25NOV26000CE", 75, 59.00)])

        rows = await account.snapshot()
        assert rows.orders, (
            "a postback produced no orders row. persist_order_event is "
            f"failing again and both call sites swallow it. Counts: "
            f"{rows.counts()}"
        )
        assert rows.orders[0]["status"] == "COMPLETE"
        assert rows.orders[0]["tradingsymbol"] == "NIFTY25NOV26000CE"


async def test_known_broken_steps_is_empty(committing_session):
    """
    `KNOWN_BROKEN_STEPS` lets the fixture work around a confirmed production
    defect instead of going red on it. This is what stops it becoming a
    permanent excuse: a listed step that starts succeeding fails here and the
    entry has to come out.

    It is empty, and that is the desired state. The one entry it ever held was
    `persist_order_event`, and this test is what evicted it - it went red the
    moment the one-line fix landed.
    """
    _redis_or_skip()

    assert KNOWN_BROKEN_STEPS == {}, (
        "a pipeline step is being excused: "
        f"{sorted(KNOWN_BROKEN_STEPS)}. That is allowed, but only for a defect "
        "confirmed against running code and only while it is unfixed."
    )

    async with synthetic_account(committing_session) as account:
        await account.submit([Fill("BUY", "NIFTY25NOV26000CE", 75, 59.00)])
        assert account.step_failures == {}, (
            f"pipeline steps failed: {account.step_failures}"
        )


# ── it must leave nothing behind ───────────────────────────────────────────

async def test_the_account_and_all_its_rows_are_gone_afterwards(committing_session):
    """
    12,010 test users leaked into this database over five months because a
    fixture committed and nothing removed the rows. This asserts the opposite
    property directly, on every table the fixture writes to.
    """
    _redis_or_skip()

    async with synthetic_account(committing_session) as account:
        account_id, user_id = account.account_id, account.user_id
        await account.submit([
            Fill("BUY", "NIFTY25NOV26000CE", 75, 59.00),
            Fill("SELL", "NIFTY25NOV26000CE", 75, 55.00),
        ])
        assert (await account.snapshot()).trades, "nothing was written to clean up"

    for table in PIPELINE_TABLES:
        left = (await committing_session.execute(
            text(f"SELECT count(*) FROM {table} WHERE broker_account_id = :a"),
            {"a": str(account_id)},
        )).scalar()
        assert left == 0, f"{left} row(s) left behind in {table}"

    for table, column, value in (
        ("broker_accounts", "id", account_id),
        ("users", "id", user_id),
    ):
        left = (await committing_session.execute(
            text(f"SELECT count(*) FROM {table} WHERE {column} = :v"),
            {"v": str(value)},
        )).scalar()
        assert left == 0, f"the synthetic {table} row was not deleted"


async def test_cleanup_runs_even_when_the_body_raises(committing_session):
    """
    A failing assertion inside the context manager must not leak the account.
    Without this, the first red test in a later phase leaves rows behind and
    the leak starts again exactly the way it did before.
    """
    captured = {}

    with pytest.raises(RuntimeError, match="deliberate"):
        async with synthetic_account(committing_session) as account:
            captured["account_id"] = account.account_id
            captured["user_id"] = account.user_id
            raise RuntimeError("deliberate failure inside the fixture")

    for table, value in (
        ("broker_accounts", captured["account_id"]),
        ("users", captured["user_id"]),
    ):
        left = (await committing_session.execute(
            text(f"SELECT count(*) FROM {table} WHERE id = :v"),
            {"v": str(value)},
        )).scalar()
        assert left == 0, f"{table} row survived a raising test body"
