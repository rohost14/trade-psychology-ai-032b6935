"""
The danger zone's consecutive-loss trigger reads the trader's declared rule.

WHAT CHANGED, 2026-08-26

It used to run a three-tier ladder on `consecutive_loss_caution` (3),
`consecutive_loss_danger` (5) and an inline `danger + 2` (7) — the same fixed
counts, from the same two threshold keys, as the `consecutive_loss_streak`
detector retired the same day. Of 189 sessions, 63 contained a 3+ loss run
against 63.0 expected from the trader's win rate alone: the run is not evidence
of a changed state, and this service was escalating on it as far as a WhatsApp to
the trader's guardian.

Now there is one reference, `max_consecutive_losses`, which the trader declares
at onboarding — and which was already present in the very dict this service
reads, at Source.FACT, while it used 3/5/7 instead. That meant a trader with a
declared limit of 4 got silence at 4 and a message to their guardian at 7.

Two properties these tests exist to hold:

  * **No declaration, no check.** A commitment cannot be inferred, so there is no
    fallback and no default.
  * **Nothing above the limit.** `constitution_violation` owns the severe
    percentage logic, and no evidence says a second level above the trader's own
    line adds anything.
"""

from datetime import timedelta
from decimal import Decimal

import pytest

from app.core import session_facts
from app.models.completed_trade import CompletedTrade
from app.models.user_profile import UserProfile
from app.services.danger_zone_service import danger_zone_service


async def _loss(db, broker, minutes, pnl=-2000):
    """One losing position, closed `minutes` after this session's open."""
    exit_at = session_facts.session_start(
        session_facts.session_date_now()
    ) + timedelta(minutes=minutes)
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


async def _declare(db, broker, limit):
    """The trader's rulebook. `limit` of None means they declared nothing."""
    profile = UserProfile(
        broker_account_id=broker.id,
        max_consecutive_losses=limit,
    )
    db.add(profile)
    await db.flush()
    return profile


async def _assess(db, broker, losses):
    # Spaced 30 min apart so the burst-trading trigger cannot fire and confuse
    # the level assertions — this test is about consecutive losses alone.
    for i in range(losses):
        await _loss(db, broker, 30 + i * 30)
    return await danger_zone_service.assess_danger_level(db, broker.id)


# ── no declared rule → no consecutive-loss check at all ────────────────────

@pytest.mark.asyncio
async def test_no_profile_means_no_consecutive_loss_trigger(db, broker):
    """
    The cold-start case. Eight losses in a row and the danger zone says nothing
    about the streak, because the trader never told us where their line is.
    """
    status = await _assess(db, broker, 8)

    assert status.consecutive_losses == 8, "the fact is still reported"
    assert not [t for t in status.triggers if t.startswith("consecutive_loss")]


@pytest.mark.asyncio
async def test_a_profile_with_no_declared_limit_is_the_same_as_no_profile(db, broker):
    """`max_consecutive_losses` is nullable. Present-but-None must not default."""
    await _declare(db, broker, None)
    status = await _assess(db, broker, 8)

    assert not [t for t in status.triggers if t.startswith("consecutive_loss")]


@pytest.mark.parametrize("losses", [3, 5, 7])
@pytest.mark.asyncio
async def test_the_old_fixed_counts_no_longer_fire(db, broker, losses):
    """
    Regression on the retirement itself. 3 / 5 / 7 were caution / danger /
    critical, the last of them a hard cooldown and a WhatsApp to the guardian.
    With nothing declared, all three must now be silent.
    """
    status = await _assess(db, broker, losses)

    assert not [t for t in status.triggers if t.startswith("consecutive_loss")], (
        f"{losses} losses still trips a fixed-count trigger"
    )


# ── declared rule → one warning rung and one breach ────────────────────────

@pytest.mark.asyncio
async def test_one_short_of_the_declared_limit_warns(db, broker):
    await _declare(db, broker, 4)
    status = await _assess(db, broker, 3)

    assert "consecutive_loss_warning" in status.triggers
    assert status.level.value == "warning"
    assert any("One more loss" in r for r in status.recommendations)


@pytest.mark.asyncio
async def test_reaching_the_declared_limit_is_danger(db, broker):
    await _declare(db, broker, 4)
    status = await _assess(db, broker, 4)

    assert "consecutive_loss_danger" in status.triggers
    assert status.level.value == "danger"
    assert status.intervention.value == "soft_cooldown"
    assert any("you said you stop at 4" in r for r in status.recommendations)


@pytest.mark.asyncio
async def test_nothing_escalates_above_the_declared_limit(db, broker):
    """
    The adjustment the user made to this change: no 1.2x tier.
    constitution_violation owns the severe percentage logic, and a second level
    above the trader's own line has no evidence behind it. Eight losses against a
    declared 4 is exactly as loud as four.
    """
    await _declare(db, broker, 4)
    status = await _assess(db, broker, 8)

    assert status.level.value == "danger", "there is no tier above the limit"
    assert status.intervention.value == "soft_cooldown", "no hard cooldown"
    assert "consecutive_loss_critical" not in status.triggers


@pytest.mark.asyncio
async def test_below_the_warning_rung_says_nothing(db, broker):
    await _declare(db, broker, 4)
    status = await _assess(db, broker, 2)

    assert not [t for t in status.triggers if t.startswith("consecutive_loss")]


@pytest.mark.asyncio
async def test_the_line_moves_with_the_traders_number(db, broker):
    """
    The point of the change. Two traders, the same three losses, different
    answers — because they told us different things.
    """
    await _declare(db, broker, 3)
    status = await _assess(db, broker, 3)

    assert "consecutive_loss_danger" in status.triggers, (
        "a declared limit of 3 is breached at 3, where a limit of 4 only warns"
    )


@pytest.mark.asyncio
async def test_a_declared_limit_of_one_breaches_with_no_warning(db, broker):
    """Nothing precedes the first loss, so there is no rung to warn on."""
    await _declare(db, broker, 1)
    status = await _assess(db, broker, 1)

    assert "consecutive_loss_danger" in status.triggers
    assert "consecutive_loss_warning" not in status.triggers


@pytest.mark.asyncio
async def test_a_winner_clears_the_streak(db, broker):
    await _declare(db, broker, 3)
    for i in range(3):
        await _loss(db, broker, 30 + i * 30)
    await _loss(db, broker, 150, pnl=5000)

    status = await danger_zone_service.assess_danger_level(db, broker.id)

    assert status.consecutive_losses == 0
    assert not [t for t in status.triggers if t.startswith("consecutive_loss")]
