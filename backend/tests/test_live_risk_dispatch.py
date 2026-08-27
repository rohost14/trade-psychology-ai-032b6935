"""
Turning tick crossings into alerts — the consolidation half of Pattern #8.

The event contract's rule: **one position, one alert per escalation step**, with
priority most-specific-first — the trader's own declared line, then an action
they took, then the market moving.

The constraint that shapes it, and the reason nothing is simply dropped:

    Layer.SAFETY — "findings may never be suppressed by anything learned from
    the trader, because a habit is not a licence."

`premium_loss_event` resolves from `UNIVERSAL_SAFETY` thresholds, so a
behavioural or personal finding may not silence it. It is either the alert, or
it is **carried inside** the alert that wins. Merging is not suppressing when the
number still reaches the trader — the same mechanism `_consolidate` already uses
when several constitution rules break on one trade.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.live_risk_state import DECLARED, UNIVERSAL, Crossing
from app.tasks.position_monitor_tasks import dispatch_risk_crossings


def _crossing(kind=UNIVERSAL, severity="caution", loss=45.0, boundary=40.0,
              band=0, symbol="NIFTY25AUG25000CE", account="acct-1", epoch="e1",
              entry=100.0, last=55.0, expiry=False):
    return Crossing(
        broker_account_id=account, tradingsymbol=symbol, instrument_token=111,
        kind=kind, severity=severity, loss_pct=loss, boundary_pct=boundary,
        band_index=band, entry_price=entry, last_price=last, quantity=75,
        epoch=epoch, expiry_day=expiry,
    )


def _fire_patch():
    """Capture what would be written, without touching a database."""
    return patch("app.tasks.position_monitor_tasks._fire_position_alert",
                 new_callable=AsyncMock, return_value=True)


@pytest.mark.asyncio
async def test_nothing_to_dispatch_is_free():
    with _fire_patch() as fire:
        assert await dispatch_risk_crossings([]) == 0
        fire.assert_not_awaited()


# ── case A: the safety band alone ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_universal_crossing_alone_speaks_in_its_own_voice():
    with _fire_patch() as fire:
        assert await dispatch_risk_crossings([_crossing()]) == 1
    kw = fire.await_args.kwargs
    assert kw["pattern_type"] == "premium_loss_event"
    assert kw["severity"] == "caution"
    assert "45% down on the premium paid" in kw["message"]
    assert kw["details"]["symbol"] == "NIFTY25AUG25000CE"
    assert kw["details"]["live"] is True


@pytest.mark.asyncio
async def test_the_message_states_the_number_and_stops():
    """
    A large premium loss is a market outcome, not a behavioural failure. The
    alert's job is to close the gap between what is true and what the trader
    knows — it assigns no fault and asks for nothing.
    """
    with _fire_patch() as fire:
        await dispatch_risk_crossings([_crossing()])
    low = fire.await_args.kwargs["message"].lower()
    for claim in ("destruction", "bleeding", "you should", "before it gets worse",
                  "panic", "chasing", "mistake"):
        assert claim not in low, f"message editorialises: {claim!r}"


@pytest.mark.parametrize("severity", ["caution", "danger", "critical"])
@pytest.mark.asyncio
async def test_each_band_carries_its_severity(severity):
    with _fire_patch() as fire:
        await dispatch_risk_crossings([_crossing(severity=severity)])
    assert fire.await_args.kwargs["severity"] == severity


# ── case B: the trader's own line ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_declared_crossing_becomes_a_constitution_violation():
    """
    Reaching a line the trader wrote down is a rule breach, not a behavioural
    finding — the same resolution Pattern 4 reached for max_consecutive_losses.
    """
    with _fire_patch() as fire:
        await dispatch_risk_crossings([
            _crossing(kind=DECLARED, severity="danger", loss=30.0, boundary=25.0, band=-1)
        ])
    kw = fire.await_args.kwargs
    assert kw["pattern_type"] == "constitution_violation"
    assert kw["details"]["rule"] == "sl_percent_options"
    assert kw["details"]["limit_pct"] == 25.0
    assert "you set your options exit at 25%" in kw["message"].lower()


# ── case D: both cross on one price ────────────────────────────────────────

@pytest.mark.asyncio
async def test_both_layers_on_one_position_produce_one_alert():
    with _fire_patch() as fire:
        assert await dispatch_risk_crossings([
            _crossing(kind=DECLARED, severity="danger", loss=45.0, boundary=25.0, band=-1),
            _crossing(kind=UNIVERSAL, severity="caution", loss=45.0, boundary=40.0),
        ]) == 1
    assert fire.await_count == 1
    assert fire.await_args.kwargs["pattern_type"] == "constitution_violation"


@pytest.mark.asyncio
async def test_the_safety_finding_is_carried_not_dropped():
    """
    Layer.SAFETY: a universal finding may not be silenced by a personal one. It
    survives inside the alert that wins, in both the evidence and the sentence.
    """
    with _fire_patch() as fire:
        await dispatch_risk_crossings([
            _crossing(kind=DECLARED, severity="danger", loss=45.0, boundary=25.0, band=-1),
            _crossing(kind=UNIVERSAL, severity="caution", loss=45.0, boundary=40.0),
        ])
    kw = fire.await_args.kwargs
    also = kw["details"]["also_crossed"]
    assert also["pattern_type"] == "premium_loss_event"
    assert also["boundary_pct"] == 40.0
    assert also["severity"] == "caution"
    assert "40% safety level" in kw["message"]


# ── independence ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_two_positions_produce_two_alerts():
    """
    The measured bug this replaces: account-scoped dedup on the exit path
    swallowed 7 of 48 detections, one of them a critical at 86.7%.
    """
    with _fire_patch() as fire:
        assert await dispatch_risk_crossings([
            _crossing(symbol="NIFTY25AUG25000CE", epoch="e1"),
            _crossing(symbol="MAZDOCK25OCT3400CE", epoch="e2",
                      severity="critical", loss=86.7, boundary=80.0, band=2),
        ]) == 2
    symbols = {c.kwargs["details"]["symbol"] for c in fire.await_args_list}
    assert symbols == {"NIFTY25AUG25000CE", "MAZDOCK25OCT3400CE"}


@pytest.mark.asyncio
async def test_the_same_symbol_in_two_epochs_is_two_stories():
    with _fire_patch() as fire:
        assert await dispatch_risk_crossings([
            _crossing(epoch="e1"), _crossing(epoch="e2"),
        ]) == 2


@pytest.mark.asyncio
async def test_two_accounts_are_never_folded_together():
    with _fire_patch() as fire:
        assert await dispatch_risk_crossings([
            _crossing(account="acct-1"), _crossing(account="acct-2"),
        ]) == 2


# ── failure is contained ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a_failed_write_does_not_lose_the_rest():
    """One bad write must not take the batch down — this runs off the tick path."""
    with patch("app.tasks.position_monitor_tasks._fire_position_alert",
               new_callable=AsyncMock) as fire:
        fire.side_effect = [RuntimeError("db down"), True]
        assert await dispatch_risk_crossings([
            _crossing(symbol="AAA25AUG100CE", epoch="e1"),
            _crossing(symbol="BBB25AUG100CE", epoch="e2"),
        ]) == 1


@pytest.mark.asyncio
async def test_a_deduped_write_is_not_counted():
    with patch("app.tasks.position_monitor_tasks._fire_position_alert",
               new_callable=AsyncMock, return_value=False):
        assert await dispatch_risk_crossings([_crossing()]) == 0


# ── the beat it replaces is gone ───────────────────────────────────────────

def test_the_sixty_second_beat_is_retired():
    """
    It re-read every account's positions and profile once a minute — about
    20,001 database round trips at 10k users, in a serial loop that does not fit
    inside its own period.
    """
    from app.core.celery_app import celery_app

    assert "live-premium-monitor" not in (celery_app.conf.beat_schedule or {})


def test_the_tick_path_dispatches_crossings():
    """The hook exists where the prices arrive, and nothing DB-bound is inline."""
    import inspect

    from app.services import price_stream_service

    src = inspect.getsource(price_stream_service.AsyncKiteTicker._handle_binary)
    assert "live_risk_state.evaluate_batch" in src
    assert "dispatch_risk_crossings" in src
    assert "create_task" in src, "the alert write must not block the price stream"
