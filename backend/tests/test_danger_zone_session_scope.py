"""
The danger zone counts within the session. Intentional behavioural change.

WHAT CHANGED

`_count_consecutive_losses` walked back through the last ten completed trades
with no session boundary. Three losses on Friday afternoon and one on Monday
morning read as a streak of four — enough to reach `consecutive_loss_critical`,
start a hard cooldown and send a WhatsApp message about a run that had ended two
days earlier. The alert engine, counting within the session, was silent about the
same trader at the same moment.

The danger zone now reads `session_facts`, like everything else. It therefore
fires LESS than it used to, and these tests pin the difference in both
directions: yesterday's losses must not carry, today's must still count.
"""
from datetime import timedelta
from decimal import Decimal

import pytest

from app.core import session_facts
from app.models.completed_trade import CompletedTrade
from app.services.danger_zone_service import danger_zone_service


def _at(session_date, minutes):
    return session_facts.session_start(session_date) + timedelta(minutes=minutes)


async def _loss(db, broker, session_date, minutes, pnl=-2000):
    exit_at = _at(session_date, minutes)
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
        avg_exit_price=Decimal("21960"),
        realized_pnl=Decimal(str(pnl)),
        entry_time=exit_at - timedelta(minutes=15),
        exit_time=exit_at,
        duration_minutes=15,
        status="closed",
    )
    db.add(ct)
    await db.flush()
    return ct


@pytest.mark.asyncio
async def test_yesterdays_losses_do_not_carry_into_todays_streak(db, broker):
    today = session_facts.session_date_now()
    yesterday = today - timedelta(days=1)

    # A bad session yesterday: five losses in a row.
    for i in range(5):
        await _loss(db, broker, yesterday, 30 + i * 20)
    # One loss today.
    await _loss(db, broker, today, 30)

    status = await danger_zone_service.assess_danger_level(db, broker.id)

    assert status.consecutive_losses == 1, (
        "yesterday's run is over; counting it starts a cooldown for something "
        "that already ended"
    )
    assert "consecutive_loss_critical" not in status.triggers
    assert "consecutive_loss_danger" not in status.triggers


@pytest.mark.asyncio
async def test_todays_losses_still_escalate(db, broker):
    """The change narrows the scope. It must not blunt the detector."""
    today = session_facts.session_date_now()
    for i in range(7):
        await _loss(db, broker, today, 30 + i * 15)

    status = await danger_zone_service.assess_danger_level(db, broker.id)

    assert status.consecutive_losses == 7
    assert status.level.value in ("danger", "critical")
    assert any(t.startswith("consecutive_loss") for t in status.triggers)


@pytest.mark.asyncio
async def test_a_win_today_clears_the_streak(db, broker):
    today = session_facts.session_date_now()
    for i in range(4):
        await _loss(db, broker, today, 30 + i * 15)
    await _loss(db, broker, today, 120, pnl=5000)  # a winner

    status = await danger_zone_service.assess_danger_level(db, broker.id)
    assert status.consecutive_losses == 0


@pytest.mark.asyncio
async def test_session_pnl_and_trade_count_come_from_the_same_place(db, broker):
    """
    Danger zone and the canonical facts must not disagree about the day, which
    they could when each ran its own query with its own day boundary — the
    service used IST midnight, the engine used the market open.
    """
    today = session_facts.session_date_now()
    await _loss(db, broker, today, 30, pnl=-1000)
    await _loss(db, broker, today, 60, pnl=-500)
    await _loss(db, broker, today, 90, pnl=2000)

    facts = await session_facts.load_facts(db, broker.id)
    status = await danger_zone_service.assess_danger_level(db, broker.id)

    assert facts.pnl == Decimal("500")
    assert facts.trades == 3
    assert status.trade_count_today == facts.trades
