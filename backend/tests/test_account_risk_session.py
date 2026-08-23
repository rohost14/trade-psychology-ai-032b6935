"""
The account-size denominator is decided once per session and written down.

WHY FREEZING IS A CORRECTNESS DECISION

Every "how much of your account did this cost" question divides by one number.
If that number is re-read per trade, a deposit at 13:00 retroactively changes
what the morning's alerts meant — the 40% loss recorded at 10:15 silently
becomes a 25% one, and the alert can no longer be checked against anything.

So it is resolved on the first trade of a session and frozen on the session row,
with its source, its age and its quality alongside it. The performance property
— one query per session rather than per trade — falls out of the correctness
one.

ABSTENTION IS AN ANSWER

A trader whose equity we cannot see gets `UNKNOWN` and no account-relative
claims, rather than a fabricated denominator. That is not a gap in coverage:
trade-relative and structural safety both work on a trader's first ever trade
without any account size at all (see app/core/measurements).
"""
from datetime import timedelta
from decimal import Decimal

import pytest

from app.core import session_facts
from app.core.account_risk import Quality
from app.models.completed_trade import CompletedTrade
from app.services.behavior_engine import BehaviorEngine
from app.models.user_profile import UserProfile
from app.services.trading_session_service import TradingSessionService

engine = BehaviorEngine()


async def _profile_with_capital(db, broker, capital):
    """
    A profile declaring capital. No shared fixture exists, and these tests want
    the declared-capital rung specifically.
    """
    p = UserProfile(broker_account_id=broker.id, trading_capital=Decimal(str(capital)))
    db.add(p)
    await db.flush()
    return p


async def _trade(db, broker, minute, pnl=-1500):
    exit_at = session_facts.session_start(session_facts.session_date_now()) + timedelta(
        minutes=minute
    )
    ct = CompletedTrade(
        broker_account_id=broker.id,
        tradingsymbol="NIFTY25JANFUT",
        exchange="NFO",
        instrument_type="FUT",
        product="MIS",
        direction="LONG",
        total_quantity=50,
        num_entries=1,
        num_exits=1,
        avg_entry_price=Decimal("22000"),
        avg_exit_price=Decimal("21990"),
        realized_pnl=Decimal(str(pnl)),
        entry_time=exit_at - timedelta(minutes=10),
        exit_time=exit_at,
        duration_minutes=10,
        status="closed",
    )
    db.add(ct)
    await db.flush()
    return ct


async def _session(db, broker):
    return await TradingSessionService.get_or_create_session(
        broker.id, session_facts.session_date_now(), db
    )


@pytest.mark.asyncio
async def test_it_resolves_and_lands_on_the_context(db, broker):
    ct = await _trade(db, broker, 30)
    session = await _session(db, broker)
    ctx = await engine._load_context(broker.id, ct, session, db)

    assert ctx.account_risk is not None, (
        "the denominator was not resolved; a detector migrated later would "
        "silently divide by nothing"
    )


@pytest.mark.asyncio
async def test_with_no_equity_and_no_declared_capital_it_abstains(db, broker):
    """
    The honest outcome. A fabricated denominator would let the engine tell
    someone they lost 40% of an account it cannot see.
    """
    ct = await _trade(db, broker, 30)
    session = await _session(db, broker)
    ctx = await engine._load_context(broker.id, ct, session, db)

    assert ctx.account_risk.is_usable is False
    assert ctx.account_risk.quality is Quality.UNKNOWN
    assert ctx.account_risk.fraction(1000) is None, (
        "an unusable denominator must refuse to divide, not return a number"
    )


@pytest.mark.asyncio
async def test_an_abstention_is_recorded_not_left_blank(db, broker):
    """
    A session we could not measure must be distinguishable from one nobody
    asked about.
    """
    ct = await _trade(db, broker, 30)
    session = await _session(db, broker)
    await engine._load_context(broker.id, ct, session, db)

    assert session.risk_denominator is None
    assert session.risk_denominator_quality == Quality.UNKNOWN.value


@pytest.mark.asyncio
async def test_declared_capital_is_used_but_never_trusted_as_good(db, broker):
    """
    Self-reported capital goes stale — which is what `capital_mismatch` exists to
    detect — so it resolves as PARTIAL. Recording it as GOOD would launder a
    guess into a measurement.
    """
    await _profile_with_capital(db, broker, 500000)

    ct = await _trade(db, broker, 30)
    session = await _session(db, broker)
    ctx = await engine._load_context(broker.id, ct, session, db)

    assert ctx.account_risk.is_usable
    assert ctx.account_risk.quality is Quality.PARTIAL
    assert ctx.account_risk.fraction(50_000) == pytest.approx(0.1)
    assert session.risk_denominator == Decimal("500000")


@pytest.mark.asyncio
async def test_a_mid_session_change_does_not_move_the_denominator(db, broker):
    """
    The reason this is frozen at all. Depositing at lunchtime must not rewrite
    what the morning's alerts meant.
    """
    profile = await _profile_with_capital(db, broker, 500000)

    first = await _trade(db, broker, 30)
    session = await _session(db, broker)
    await engine._load_context(broker.id, first, session, db)
    assert session.risk_denominator == Decimal("500000")

    # Trader adds capital and updates their profile mid-session.
    profile.trading_capital = Decimal("2000000")
    await db.flush()

    later = await _trade(db, broker, 120)
    ctx = await engine._load_context(broker.id, later, session, db)

    assert session.risk_denominator == Decimal("500000")
    assert ctx.account_risk.value == Decimal("500000"), (
        "the afternoon was measured against a denominator the morning never saw"
    )
    assert "frozen" in (ctx.account_risk.detail or "")


@pytest.mark.asyncio
async def test_resolution_costs_nothing_after_the_first_trade(db, broker):
    """
    Session-scoping is what keeps this off the per-trade bill: the frozen path
    reads the session row that is already loaded.
    """
    from tests.test_engine_hot_path import QueryCounter

    profile = await _profile_with_capital(db, broker, 500000)

    session = await _session(db, broker)
    first = await _trade(db, broker, 30)
    await engine._load_context(broker.id, first, session, db)

    from app.core.account_risk import resolve_account_risk

    with QueryCounter(db) as counter:
        risk = await resolve_account_risk(
            broker.id, db, session=session, profile=profile
        )

    assert risk.value == Decimal("500000")
    assert counter.count == 0, (
        f"the frozen denominator still cost {counter.count} queries"
    )
