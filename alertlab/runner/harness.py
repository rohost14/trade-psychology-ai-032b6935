"""
The seams that let the real pipeline run without market hours, Redis or Celery.

Nothing in `app/` changes. Everything here is applied from the outside, the way
the existing test suite monkeypatches modules — which is the whole reason the lab
can drive production code without forking it.

Three seams:

  fake Redis   the pipeline uses seven Redis operations (set NX, delete, rpush,
               ltrim, expire, lrange, rename). All are modelled here, including
               RENAME raising on a missing key, because drain() depends on that
               error to detect an empty window.

  eager Celery `task_always_eager` makes .delay() and .apply_async() run inline.
               The real task bodies execute; no worker, no broker. `countdown`
               is ignored, so the 5-second coalescing window is not exercised —
               the batching logic is, the timer is not.

  frozen clock five checks read the wall clock (entry rules, holding-loser, live
               premium, the dead beat monitor, the alert writer). The 27 engine
               detectors do not — they read the trade's own timestamps — so most
               scenarios need no freezing at all. Where it matters, a scenario
               declares its wall time and this pins it.
"""
from __future__ import annotations

import asyncio as _asyncio
import contextlib
import datetime as _dt
import logging
import os
import uuid
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

# Must be set BEFORE app.core.database is imported anywhere.
#
# The pipeline runs Celery task bodies, and those call asyncio.run() internally —
# so each fill executes in its own fresh event loop. asyncpg connections are
# bound to the loop that created them, and a pooled connection from a previous
# loop fails with an SSL error that looks nothing like its cause.
#
# The codebase already solves this for its own workers: CELERY_WORKER=1 selects
# NullPool, documented there as "connection per checkout, no cross-loop reuse".
# The lab is a worker by any other name.
os.environ.setdefault("CELERY_WORKER", "1")

IST = ZoneInfo("Asia/Kolkata")


def quiet_logs() -> None:
    """
    Silence the query firehose.

    `echo` is on whenever ENVIRONMENT is development, and SQLAlchemy sets that
    level on `sqlalchemy.engine.Engine` when the engine is constructed — so a
    parent logger set beforehand does nothing. This has to run after the import.
    """
    for name in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool",
                 "celery", "celery.app.trace", "app.services.ai_service",
                 "app.tasks.trade_tasks", "app.services.behavior_engine",
                 "app.tasks.position_monitor_tasks", "app.services.strategy_detector",
                 "app.core.metrics", "app.services.position_ledger_service"):
        logging.getLogger(name).setLevel(logging.WARNING)

    # setLevel alone is not enough: `echo=True` re-applies INFO to the engine
    # logger every time an engine is constructed, and the lab builds one per
    # run — so the firehose came back partway through a full-suite run and
    # buried the results under 900KB of INSERT statements. `disabled` is the one
    # switch echo never touches.
    logging.getLogger("sqlalchemy.engine.Engine").disabled = True

#: Path of the cross-process run lock. See `single_run_lock`.
_LOCK_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          ".run.lock")


@contextlib.contextmanager
def single_run_lock(owner: str = "cli"):
    """
    One lab run at a time, across processes.

    Every run shares LAB_ACCOUNT_ID and every scenario begins by tearing that
    account down. So two runs at once — the UI server and the CLI, typically —
    delete each other's rows mid-flight. That does not fail loudly: it surfaces
    as scenarios reporting zero alerts, alerts attributed to structures that
    were never traded, and `UPDATE on trading_sessions expected to update 1
    row(s); 0 were matched`. A whole suite came back 35/70 that way while every
    one of those scenarios passed individually, which is the most expensive
    possible way to be told two runs collided.

    A lockfile rather than an in-process lock, because the colliding runs are
    separate processes. Stale locks are reclaimed: a crashed run must not
    require manual cleanup to get the lab working again.
    """
    stale_after = 3600
    try:
        if os.path.exists(_LOCK_PATH) and \
                (_dt.datetime.now().timestamp() - os.path.getmtime(_LOCK_PATH)) > stale_after:
            os.unlink(_LOCK_PATH)
        fd = os.open(_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            held = open(_LOCK_PATH).read().strip()
        except OSError:
            held = "unknown"
        raise RuntimeError(
            f"another lab run is already in progress ({held}). Runs share one "
            f"account and tear it down per scenario, so a second run would "
            f"corrupt both. Wait for it to finish, or delete {_LOCK_PATH} if "
            f"nothing is actually running."
        ) from None

    try:
        os.write(fd, f"{owner} pid={os.getpid()}".encode())
        os.close(fd)
        yield
    finally:
        with contextlib.suppress(OSError):
            os.unlink(_LOCK_PATH)


#: One reserved account. Everything the lab creates hangs off it, and teardown is
#: a single delete that cascades. Fixed so a crashed run is still cleanable.
LAB_ACCOUNT_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
LAB_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
LAB_EMAIL = "alertlab@synthetic.local"
LAB_BROKER_USER_ID = "LAB000001"


# ---------------------------------------------------------------------------
# Fake Redis
# ---------------------------------------------------------------------------

class FakeRedis:
    """
    Enough Redis for the pipeline, with the semantics that actually matter.

    RENAME raises when the source key is missing, exactly as the real server
    does. entry_batch_service.drain() relies on that error to recognise an empty
    window — a forgiving fake would hide the branch and quietly pass a broken
    implementation.
    """

    def __init__(self) -> None:
        self.lists: Dict[str, List[str]] = {}
        self.keys: Dict[str, Any] = {}

    # strings / locks
    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.keys:
            return None
        self.keys[key] = value
        return True

    def get(self, key):
        return self.keys.get(key)

    def delete(self, key):
        self.lists.pop(key, None)
        self.keys.pop(key, None)

    def expire(self, key, ttl):
        return True

    # lists
    def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    def lrange(self, key, start, end):
        return list(self.lists.get(key, []))

    def ltrim(self, key, start, end):
        items = self.lists.get(key, [])
        self.lists[key] = items[start:] if end == -1 else items[start:end + 1]

    def rename(self, src, dst):
        if src not in self.lists:
            raise RuntimeError("no such key")
        self.lists[dst] = self.lists.pop(src)

    def flush(self) -> None:
        self.lists.clear()
        self.keys.clear()


# ---------------------------------------------------------------------------
# Frozen clock
# ---------------------------------------------------------------------------

def _frozen_datetime_class(pinned: _dt.datetime):
    """A datetime subclass whose now()/utcnow() return a fixed instant."""

    class _Frozen(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return pinned.astimezone(tz) if tz else pinned.replace(tzinfo=None)

        @classmethod
        def utcnow(cls):
            return pinned.astimezone(_dt.timezone.utc).replace(tzinfo=None)

    return _Frozen


#: Modules whose wall-clock reads change behaviour. Kept explicit rather than
#: patched globally: a scenario that silently froze time somewhere unexpected
#: would be worse than one that does not freeze it at all.
_CLOCK_MODULES = (
    "app.tasks.position_monitor_tasks",
    "app.tasks.trade_tasks",
    "app.services.entry_checks",
    # The engine itself resolves "today" from the wall clock when it builds
    # session_trades. Leaving it out meant every scenario ran with an empty
    # session: session_meltdown still fired (it reads the session row), but
    # every detector that compares against earlier trades — revenge, streaks,
    # sizing — silently found no history and returned None. Alerts were absent
    # from the suppression trace too, so it looked like nothing was detected
    # rather than like nothing was visible.
    "app.services.behavior_engine",
    "app.services.behavior_summary",
)


@contextlib.contextmanager
def frozen_clock(when: Optional[_dt.datetime]):
    """
    Pin wall-clock reads to `when` for the duration of the block.

    Pass None to run against the real clock — correct for the many scenarios
    that are driven purely by trade timestamps.
    """
    if when is None:
        yield
        return

    import importlib

    pinned = when if when.tzinfo else when.replace(tzinfo=IST)
    frozen = _frozen_datetime_class(pinned)
    originals = {}
    for name in _CLOCK_MODULES:
        try:
            module = importlib.import_module(name)
        except Exception:
            continue
        if hasattr(module, "datetime"):
            originals[name] = (module, module.datetime)
            module.datetime = frozen
    try:
        yield
    finally:
        for module, original in originals.values():
            module.datetime = original


def clock_is_frozen(expected: _dt.datetime) -> bool:
    """
    Canary. If patching silently stops working — an import style changes, a
    module is reloaded — every time-based scenario would quietly start testing
    the wrong hour and still pass. One assertion catches that.
    """
    from app.tasks import position_monitor_tasks as pm

    return pm.datetime.now(IST).hour == expected.astimezone(IST).hour


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

def _in_fresh_loop(fn):
    """
    Run a sync function in its own thread, so it sees no running event loop.

    Only takes effect when a loop IS running. Outside one the function is called
    directly, so the wrapper costs nothing where it is not needed.
    """
    import functools
    import threading

    @functools.wraps(fn)
    def runner(*args, **kwargs):
        try:
            _asyncio.get_running_loop()
        except RuntimeError:
            return fn(*args, **kwargs)      # no loop; nothing to work around

        box = {}

        def go():
            try:
                box["value"] = fn(*args, **kwargs)
            except BaseException as exc:     # surfaced, never silently dropped
                box["error"] = exc

        thread = threading.Thread(target=go, daemon=True)
        thread.start()
        thread.join()
        if "error" in box:
            raise box["error"]
        return box.get("value")

    return runner


def _isolate_task_loops(celery_app):
    """
    Give every Celery task the loop-free context a real worker would.

    Returns what was replaced, so `lab_environment` can put it back — these are
    module-level objects shared with anything else in the process.
    """
    replaced = []
    for task in list(celery_app.tasks.values()):
        run = getattr(task, "run", None)
        if run is None or getattr(run, "__wrapped__", None) is not None:
            continue
        if _asyncio.iscoroutinefunction(run):
            continue                          # Celery would not accept it anyway
        replaced.append((task, run))
        task.run = _in_fresh_loop(run)
    return replaced


@contextlib.contextmanager
def lab_environment(when: Optional[_dt.datetime] = None):
    """
    Real pipeline, no infrastructure.

    Patches the two Redis accessors and puts Celery in eager mode, so
    `.delay()` and `.apply_async()` execute the real task bodies inline.
    """
    from app.core.celery_app import celery_app
    from app.tasks import position_monitor_tasks as pm
    from app.tasks import trade_tasks as tt

    redis = FakeRedis()
    saved = {
        "tt_redis": tt._get_redis_client,
        "pm_redis": pm._get_redis,
        "eager": celery_app.conf.task_always_eager,
        "propagate": celery_app.conf.task_eager_propagates,
    }
    # Every sync Celery task in this codebase calls asyncio.run() on an async
    # body. Under a real worker that is correct — the worker process has no
    # running loop. Eager mode runs the task inline inside the loop already
    # driving the scenario, where asyncio.run() raises, and
    # task_eager_propagates=False swallows the error.
    #
    # The cost was silent and total: flush_entry_batch, check_holding_loser and
    # send_danger_alert all died this way, so entry-time detection never ran in
    # the lab at ALL. Nothing reported a problem, because "the entry checks
    # found nothing" and "the entry checks never executed" produce identical
    # output — every entry scenario would have passed or failed for a reason
    # unrelated to what it was testing.
    #
    # Wrapping every task rather than the three found so far: the next task to
    # be added will have the same shape, and would fail just as quietly.
    saved["task_runs"] = _isolate_task_loops(celery_app)

    # The entry checks load open positions first, and `positions` is written by
    # the Kite sync, not by the postback path — so the flush must see a sync
    # that has already landed. In production that is the normal case: the sync
    # runs on its own cadence and the flush is ~5s behind the fill. Emulating it
    # here is what lets the entry path be exercised at all; the race it papers
    # over is real and is written up in inject.sync_positions_from_ledger.
    saved["flush_body"] = pm._flush_entry_batch

    async def _flush_with_synced_positions(broker_account_id: str):
        from app.core.database import SessionLocal as _S
        from alertlab.runner.inject import sync_positions_from_ledger
        async with _S() as db:
            await sync_positions_from_ledger(db, LAB_ACCOUNT_ID)
        return await saved["flush_body"](broker_account_id)

    pm._flush_entry_batch = _flush_with_synced_positions

    tt._get_redis_client = lambda: redis
    pm._get_redis = lambda: redis
    # `flush_entry_batch` is a sync Celery task that calls asyncio.run() on its
    # async body. Under a real worker that is correct — the worker process has no
    # running loop. Eager mode runs it inline inside the loop that is already
    # driving the scenario, where asyncio.run() raises, and
    # task_eager_propagates=False swallows it.
    #
    # The cost of that was total: entry-time detection never executed in the lab
    # at all, and the failure was invisible because "no entry detections" and
    # "entry detections found nothing" produce identical output. Every scenario
    # asserting entry behaviour would have passed or failed for the wrong reason.
    #
    # Running the body in its own thread gives it the loop-free context a worker
    # would provide, without changing the task.

    celery_app.conf.task_always_eager = True
    # A failing task must not abort the scenario: the pipeline treats several
    # steps as non-fatal, and the lab has to observe that same behaviour rather
    # than a raised exception the real system would have swallowed.
    celery_app.conf.task_eager_propagates = False

    try:
        with frozen_clock(when):
            yield redis
    finally:
        tt._get_redis_client = saved["tt_redis"]
        pm._get_redis = saved["pm_redis"]
        celery_app.conf.task_always_eager = saved["eager"]
        celery_app.conf.task_eager_propagates = saved["propagate"]
        for task, original in saved["task_runs"]:
            task.run = original
        pm._flush_entry_batch = saved["flush_body"]


# ---------------------------------------------------------------------------
# Synthetic account lifecycle
# ---------------------------------------------------------------------------

async def ensure_lab_account(db, capital: float = 500_000, **profile_overrides) -> None:
    """
    Create (or reset) the synthetic user, broker account and profile.

    Profile fields drive most thresholds — capital, the constitution limits,
    experience level — so a scenario states them and gets a clean slate.
    """
    from sqlalchemy import select

    from app.models.broker_account import BrokerAccount
    from app.models.user import User
    from app.models.user_profile import UserProfile

    user = await db.get(User, LAB_USER_ID)
    if user is None:
        db.add(User(id=LAB_USER_ID, email=LAB_EMAIL, display_name="Alert Lab"))
        await db.flush()

    account = await db.get(BrokerAccount, LAB_ACCOUNT_ID)
    if account is None:
        db.add(BrokerAccount(
            id=LAB_ACCOUNT_ID,
            user_id=LAB_USER_ID,
            broker_name="synthetic",
            broker_email=LAB_EMAIL,
            broker_user_id=LAB_BROKER_USER_ID,
            status="connected",
        ))
        await db.flush()

    profile = (await db.execute(
        select(UserProfile).where(UserProfile.broker_account_id == LAB_ACCOUNT_ID)
    )).scalar_one_or_none()

    defaults = dict(
        trading_capital=capital,
        experience_level="intermediate",
        onboarding_completed=True,
        daily_loss_limit=round(capital * 0.02),
        daily_trade_limit=10,
        max_position_size=2.0,
        cooldown_after_loss=15,
        max_consecutive_losses=3,
        restricted_windows=[],
    )
    defaults.update(profile_overrides)

    if profile is None:
        profile = UserProfile(broker_account_id=LAB_ACCOUNT_ID, **defaults)
        db.add(profile)
    else:
        for key, value in defaults.items():
            setattr(profile, key, value)

    await db.commit()


async def teardown_lab(db) -> Dict[str, int]:
    """
    Remove everything the lab created.

    Not housekeeping. Lab alerts share `risk_alerts` with
    /api/admin/detection-quality, so anything left behind distorts the precision
    and latency numbers that measure the real engine. A run that does not tear
    down has corrupted the instrument it was built to protect.
    """
    from sqlalchemy import delete, func, select

    from app.models.behavior_event import BehaviorEvent
    from app.models.completed_trade import CompletedTrade
    from app.models.position import Position
    from app.models.position_ledger import PositionLedger
    from app.models.risk_alert import RiskAlert
    from app.models.trade import Trade
    from app.models.trading_session import TradingSession

    counts: Dict[str, int] = {}
    # Ordered child-first. The FK cascade would handle most of it, but deleting
    # explicitly reports what was there — a silent cascade tells you nothing
    # about whether the run behaved.
    for model, label in (
        (BehaviorEvent, "behavior_events"),
        (RiskAlert, "risk_alerts"),
        (CompletedTrade, "completed_trades"),
        (PositionLedger, "ledger_entries"),
        (Position, "positions"),
        (Trade, "trades"),
        (TradingSession, "sessions"),
    ):
        counts[label] = (await db.execute(
            select(func.count()).select_from(model)
            .where(model.broker_account_id == LAB_ACCOUNT_ID)
        )).scalar() or 0
        await db.execute(delete(model).where(model.broker_account_id == LAB_ACCOUNT_ID))

    # Strategy groups have no direct account column on their legs.
    try:
        from app.models.strategy_group import StrategyGroup, StrategyGroupLeg
        groups = (await db.execute(
            select(StrategyGroup.id).where(StrategyGroup.broker_account_id == LAB_ACCOUNT_ID)
        )).scalars().all()
        if groups:
            await db.execute(delete(StrategyGroupLeg).where(
                StrategyGroupLeg.strategy_group_id.in_(groups)))
            await db.execute(delete(StrategyGroup).where(
                StrategyGroup.broker_account_id == LAB_ACCOUNT_ID))
        counts["strategy_groups"] = len(groups)
    except Exception:
        counts["strategy_groups"] = 0

    try:
        from app.models.alert_mute import AlertMute
        await db.execute(delete(AlertMute).where(
            AlertMute.broker_account_id == LAB_ACCOUNT_ID))
    except Exception:
        pass

    await db.commit()
    return counts
