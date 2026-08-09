"""
Delivery receipts — RiskAlert.delivered_push_at / delivered_whatsapp_at.

Both columns arrived with migration 038 and were read in two places while being
written in none. That left two things broken at once:

  * check_guardian_budget counts this month's guardian messages by counting rows
    where delivered_whatsapp_at is set. Always zero, so the "hard cap 1-3 per
    month" the design calls for could never engage.
  * send_danger_alert retries up to three times with no record of what it had
    already sent, so a failure after a successful push re-pushed the same alert.

These tests cover the receipt predicates and the budget that depends on them.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.behavior_scores_service import check_guardian_budget
from app.tasks.trade_tasks import _already_delivered, _push_succeeded

NOW = datetime.now(timezone.utc)


# ── Did the push actually reach a device? ────────────────────────────────────

def test_push_counts_as_delivered_when_a_device_received_it():
    assert _push_succeeded({"sent": 1, "failed": 0}) is True
    assert _push_succeeded({"sent": 3, "failed": 2}) is True


def test_push_not_delivered_when_every_device_failed():
    """Stamping a receipt here would silently cancel the retry that should happen."""
    assert _push_succeeded({"sent": 0, "failed": 4}) is False


def test_push_not_delivered_when_unconfigured_or_disabled():
    assert _push_succeeded({"sent": 0, "failed": 0, "error": "Not configured"}) is False
    assert _push_succeeded({"sent": 0, "failed": 0, "error": "No subscriptions"}) is False


def test_push_result_that_is_not_a_dict_is_never_a_receipt():
    for value in (None, True, "sent", 1):
        assert _push_succeeded(value) is False


def test_malformed_sent_count_is_not_a_receipt():
    assert _push_succeeded({"sent": "many"}) is False


# ── The retry guard ──────────────────────────────────────────────────────────

def test_channels_are_tracked_independently():
    """A delivered push must not suppress the guardian message, or vice versa."""
    alert = SimpleNamespace(delivered_push_at=NOW, delivered_whatsapp_at=None)
    assert _already_delivered(alert, "push") is True
    assert _already_delivered(alert, "whatsapp") is False


def test_undelivered_alert_is_sendable_on_both_channels():
    alert = SimpleNamespace(delivered_push_at=None, delivered_whatsapp_at=None)
    assert _already_delivered(alert, "push") is False
    assert _already_delivered(alert, "whatsapp") is False


def test_guardian_receipt_blocks_a_second_guardian_message():
    alert = SimpleNamespace(delivered_push_at=None, delivered_whatsapp_at=NOW)
    assert _already_delivered(alert, "whatsapp") is True


# ── The budget those receipts feed ───────────────────────────────────────────

class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class StubDB:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, *_a, **_k):
        return _Result(self.rows)


def delivered(n: int):
    """n guardian messages already sent this month."""
    return [SimpleNamespace(id=uuid4(), delivered_whatsapp_at=NOW) for _ in range(n)]


async def test_budget_allows_a_send_when_nothing_was_delivered():
    assert await check_guardian_budget(uuid4(), StubDB([])) is True


async def test_budget_allows_a_send_below_the_cap():
    assert await check_guardian_budget(uuid4(), StubDB(delivered(2))) is True


async def test_budget_blocks_at_the_cap():
    """
    Three is the documented monthly cap. Before receipts were written this query
    always returned zero rows, so this branch was unreachable in production.
    """
    assert await check_guardian_budget(uuid4(), StubDB(delivered(3))) is False


async def test_budget_blocks_past_the_cap():
    assert await check_guardian_budget(uuid4(), StubDB(delivered(9))) is False


# ── The task actually stamps them ────────────────────────────────────────────
# The predicates above would still pass if the assignments were deleted from
# send_danger_alert, which is the exact shape of the original bug. These drive
# the real task.

class _TaskResult:
    def __init__(self, row):
        self.row = row

    def scalar_one_or_none(self):
        return self.row


class TaskStubDB:
    """Answers the task's queries in order: alert, account. Then get() -> user."""

    def __init__(self, alert, account, user):
        self._rows = [alert, account]
        self.user = user
        self.commits = 0

    async def execute(self, *_a, **_k):
        return _TaskResult(self._rows.pop(0) if self._rows else None)

    async def get(self, *_a, **_k):
        return self.user

    async def commit(self):
        self.commits += 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False


def make_alert(**overrides):
    base = dict(
        id=uuid4(),
        pattern_type="session_meltdown",   # guardian_eligible in the registry
        severity="danger",
        message="Session meltdown",
        details={},
        detected_at=NOW,
        delivered_push_at=None,
        delivered_whatsapp_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def run_task(monkeypatch, alert, *, push_sent=1, guardian_sent=True, budget_ok=True):
    import app.services.alert_service as alert_service_mod
    import app.services.behavior_scores_service as scores_mod
    import app.services.push_notification_service as push_mod
    import app.tasks.trade_tasks as tt

    account = SimpleNamespace(id=uuid4(), user_id=uuid4())
    user = SimpleNamespace(
        guardian_phone="+919000000002", guardian_confirmed=True,
        guardian_name="Mentor", display_name="Rohit O",
    )
    db = TaskStubDB(alert, account, user)

    monkeypatch.setattr(tt, "SessionLocal", lambda: db)

    async def fake_push(_alert, _db):
        return {"sent": push_sent, "failed": 0}

    async def fake_guardian(self, *_a, **_k):
        return guardian_sent

    async def fake_budget(*_a, **_k):
        return budget_ok

    monkeypatch.setattr(push_mod.push_service, "send_risk_alert_notification", fake_push)
    monkeypatch.setattr(alert_service_mod.AlertService, "send_guardian_alert", fake_guardian)
    monkeypatch.setattr(scores_mod, "check_guardian_budget", fake_budget)

    results = tt.send_danger_alert(str(account.id), str(alert.id))
    return results, db


def test_task_stamps_both_receipts_on_success(monkeypatch):
    alert = make_alert()
    results, db = run_task(monkeypatch, alert)

    assert alert.delivered_push_at is not None, "push receipt not written"
    assert alert.delivered_whatsapp_at is not None, "guardian receipt not written"
    assert db.commits >= 1, "receipts were never committed"
    assert results["whatsapp"] is True


def test_task_writes_no_push_receipt_when_no_device_got_it(monkeypatch):
    alert = make_alert()
    run_task(monkeypatch, alert, push_sent=0)
    assert alert.delivered_push_at is None


def test_task_writes_no_guardian_receipt_when_the_send_failed(monkeypatch):
    alert = make_alert()
    run_task(monkeypatch, alert, guardian_sent=False)
    assert alert.delivered_whatsapp_at is None


def test_task_writes_no_guardian_receipt_when_the_budget_is_exhausted(monkeypatch):
    alert = make_alert()
    results, _ = run_task(monkeypatch, alert, budget_ok=False)
    assert alert.delivered_whatsapp_at is None
    assert results["whatsapp"] == "skipped"


def test_retry_does_not_resend_what_was_already_delivered(monkeypatch):
    """The whole point of the receipts: attempt two is a no-op."""
    earlier = NOW - timedelta(minutes=1)
    alert = make_alert(delivered_push_at=earlier, delivered_whatsapp_at=earlier)

    results, _ = run_task(monkeypatch, alert)

    assert results["push"] == "already_delivered"
    assert results["whatsapp"] == "already_delivered"
    assert alert.delivered_push_at == earlier
    assert alert.delivered_whatsapp_at == earlier
