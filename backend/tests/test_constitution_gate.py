"""
The constitution gate: tightening is instant, loosening has friction.

This is the one piece of the alert system the Alert Lab cannot reach. Its
behaviour is a 409 from PUT /api/profile and a queued change that lands next
session — nothing a synthetic fill can produce — so simulating it there would
have tested a fiction. It belongs here, next to the service.

What makes the gate worth testing rather than reading: the rules are the one
part of the product the trader wrote themselves, and the asymmetry is the whole
design. Making a rule stricter is always allowed and takes effect immediately.
Making it looser requires explicit confirmation, and during market hours it does
not take effect until the next session — because the moment a trader most wants
to relax a limit is the moment the limit is doing its work.

Direction is not obvious per field and a sign error would silently invert the
protection: a higher daily_loss_limit is looser, a higher cooldown_after_loss is
tighter. Removing any restricted window is loosening even though the set changed
in a way that could look like an edit.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services import constitution_service as cs
from app.services.constitution_service import (
    ConstitutionService, LoosenRequiresOverride, classify_change,
)


class _FakeDB:
    """Enough AsyncSession for apply_changes: it adds history rows and commits."""

    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


def _profile(**overrides):
    base = dict(
        broker_account_id="00000000-0000-4000-8000-000000000009",
        daily_loss_limit=5000,
        daily_trade_limit=10,
        max_position_size=20.0,
        cooldown_after_loss=10,
        max_consecutive_losses=3,
        restricted_windows=["09:15-09:30"],
        constitution_pending=None,
        constitution_locked_until=None,
        constitution_accepted_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# ── Direction ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("field, old, new, expected", [
    # Lower is tighter: a smaller loss limit protects more.
    ("daily_loss_limit", 5000, 3000, "tighten"),
    ("daily_loss_limit", 5000, 9000, "loosen"),
    ("daily_trade_limit", 10, 5, "tighten"),
    ("daily_trade_limit", 10, 20, "loosen"),
    ("max_position_size", 20.0, 10.0, "tighten"),
    ("max_position_size", 20.0, 40.0, "loosen"),
    ("max_consecutive_losses", 3, 2, "tighten"),
    ("max_consecutive_losses", 3, 6, "loosen"),
    # Higher is tighter: a longer cooldown keeps you out for longer. The one
    # field where the sign is inverted, and the one a refactor would get wrong.
    ("cooldown_after_loss", 10, 30, "tighten"),
    ("cooldown_after_loss", 10, 2, "loosen"),
    # Adding a rule is tightening; removing it entirely is loosening, whatever
    # the numbers would otherwise say.
    ("daily_loss_limit", None, 5000, "tighten"),
    ("daily_loss_limit", 5000, None, "loosen"),
    # No change is not a change.
    ("daily_loss_limit", 5000, 5000, None),
])
def test_classify_change_direction(field, old, new, expected):
    assert classify_change(field, old, new) == expected


@pytest.mark.parametrize("old, new, expected", [
    (["09:15-09:30"], ["09:15-09:30", "15:00-15:30"], "tighten"),   # added
    (["09:15-09:30", "15:00-15:30"], ["09:15-09:30"], "loosen"),    # removed
    (["09:15-09:30"], ["09:15-09:30"], None),                       # unchanged
    # A swap removes one window, and a removal is loosening no matter what
    # arrives alongside it — otherwise "edit" becomes a way to drop a rule.
    (["09:15-09:30"], ["15:00-15:30"], "loosen"),
])
def test_classify_change_restricted_windows(old, new, expected):
    assert classify_change("restricted_windows", old, new) == expected


# ── Tightening ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("market_hours", [True, False])
@pytest.mark.asyncio
async def test_tighten_applies_instantly(monkeypatch, market_hours):
    """Instant in both cases: there is never a reason to delay more protection."""
    monkeypatch.setattr(cs, "_is_market_hours", lambda _now: market_hours)
    profile, db = _profile(), _FakeDB()

    result = await ConstitutionService.apply_changes(
        profile, db, {"daily_loss_limit": 2000}
    )

    assert result["change_type"] == "tighten"
    assert result["applied"] == {"daily_loss_limit": 2000}
    assert result["pending"] == {}
    assert profile.daily_loss_limit == 2000
    assert not profile.constitution_pending


@pytest.mark.asyncio
async def test_tighten_needs_no_override(monkeypatch):
    monkeypatch.setattr(cs, "_is_market_hours", lambda _now: True)
    profile, db = _profile(), _FakeDB()
    # override_confirmed defaults to False; tightening must not care.
    await ConstitutionService.apply_changes(profile, db, {"cooldown_after_loss": 45})
    assert profile.cooldown_after_loss == 45


# ── Loosening ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_loosen_without_confirmation_is_refused(monkeypatch):
    """The 409 the API returns. Nothing may change on the way out."""
    monkeypatch.setattr(cs, "_is_market_hours", lambda _now: False)
    profile, db = _profile(), _FakeDB()

    with pytest.raises(LoosenRequiresOverride) as exc:
        await ConstitutionService.apply_changes(
            profile, db, {"daily_loss_limit": 50000}
        )

    assert "daily_loss_limit" in exc.value.fields
    assert profile.daily_loss_limit == 5000, "refused change must not be applied"
    assert db.commits == 0, "a refusal must not commit"


@pytest.mark.asyncio
async def test_loosen_during_market_hours_is_queued(monkeypatch):
    """
    The core protection. A trader relaxing a limit mid-session is exactly when
    the limit matters, so the change is real but does not land until tomorrow.
    """
    monkeypatch.setattr(cs, "_is_market_hours", lambda _now: True)
    profile, db = _profile(), _FakeDB()

    result = await ConstitutionService.apply_changes(
        profile, db, {"daily_loss_limit": 50000}, override_confirmed=True
    )

    assert result["pending"] == {"daily_loss_limit": 50000}
    assert result["applied"] == {}
    assert profile.daily_loss_limit == 5000, "still governed by the old limit today"
    assert profile.constitution_pending["daily_loss_limit"] == 50000
    assert "_effective_at" in profile.constitution_pending


@pytest.mark.asyncio
async def test_loosen_outside_market_hours_applies_now(monkeypatch):
    """Deciding this in the evening is a different act from doing it mid-trade."""
    monkeypatch.setattr(cs, "_is_market_hours", lambda _now: False)
    profile, db = _profile(), _FakeDB()

    result = await ConstitutionService.apply_changes(
        profile, db, {"daily_loss_limit": 50000}, override_confirmed=True
    )

    assert result["applied"] == {"daily_loss_limit": 50000}
    assert result["pending"] == {}
    assert profile.daily_loss_limit == 50000


@pytest.mark.asyncio
async def test_tighten_and_loosen_together(monkeypatch):
    """
    A mixed submission must not let the loosening ride along on the tightening.
    """
    monkeypatch.setattr(cs, "_is_market_hours", lambda _now: True)
    profile, db = _profile(), _FakeDB()

    result = await ConstitutionService.apply_changes(
        profile, db,
        {"daily_trade_limit": 3, "daily_loss_limit": 50000},
        override_confirmed=True,
    )

    assert profile.daily_trade_limit == 3, "the tightening is instant"
    assert profile.daily_loss_limit == 5000, "the loosening waits for next session"
    assert result["pending"] == {"daily_loss_limit": 50000}


@pytest.mark.asyncio
async def test_mixed_change_without_override_refuses_everything(monkeypatch):
    """
    Pairing a loosening with a tightening must not be a way to skip the gate —
    and the tightening must not be applied either, or a refused request would
    have left the profile half-changed.
    """
    monkeypatch.setattr(cs, "_is_market_hours", lambda _now: True)
    profile, db = _profile(), _FakeDB()

    with pytest.raises(LoosenRequiresOverride):
        await ConstitutionService.apply_changes(
            profile, db, {"daily_trade_limit": 3, "daily_loss_limit": 50000}
        )

    assert profile.daily_trade_limit == 10
    assert profile.daily_loss_limit == 5000


# ── Onboarding and bookkeeping ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_onboarding_bypasses_the_gate(monkeypatch):
    """Nothing to protect yet — the first set of rules is not a relaxation."""
    monkeypatch.setattr(cs, "_is_market_hours", lambda _now: True)
    profile, db = _profile(daily_loss_limit=None), _FakeDB()

    result = await ConstitutionService.apply_changes(
        profile, db, {"daily_loss_limit": 20000}, change_type_override="initial"
    )

    assert result["change_type"] == "initial"
    assert profile.daily_loss_limit == 20000
    assert profile.constitution_accepted_at is not None


@pytest.mark.asyncio
async def test_no_change_is_not_a_change(monkeypatch):
    monkeypatch.setattr(cs, "_is_market_hours", lambda _now: True)
    profile, db = _profile(), _FakeDB()

    result = await ConstitutionService.apply_changes(
        profile, db, {"daily_loss_limit": 5000}
    )

    assert result["change_type"] == "none"
    assert db.commits == 0, "a no-op must not write history"


@pytest.mark.asyncio
async def test_any_change_refreshes_the_lock(monkeypatch):
    monkeypatch.setattr(cs, "_is_market_hours", lambda _now: False)
    profile, db = _profile(), _FakeDB()

    await ConstitutionService.apply_changes(profile, db, {"daily_loss_limit": 2000})

    assert profile.constitution_locked_until is not None
    remaining = profile.constitution_locked_until - datetime.now(timezone.utc)
    assert timedelta(days=29) < remaining <= timedelta(days=cs.LOCK_DAYS)


@pytest.mark.asyncio
async def test_non_rule_fields_are_ignored(monkeypatch):
    """
    Only RULE_FIELDS go through the gate. A profile update carrying unrelated
    keys must not be treated as a constitution change at all.
    """
    monkeypatch.setattr(cs, "_is_market_hours", lambda _now: True)
    profile, db = _profile(), _FakeDB()

    result = await ConstitutionService.apply_changes(
        profile, db, {"display_name": "someone else", "timezone": "UTC"}
    )

    assert result["change_type"] == "none"
