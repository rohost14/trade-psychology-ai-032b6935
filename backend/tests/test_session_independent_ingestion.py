"""
The TradeMentor login session must not control the broker ingestion lifecycle.

THE INVARIANT

    TradeMentor user session  !=  broker account ingestion lifecycle

Logging out must not stop background synchronisation, and logging back in must
not restore stale state. The broker is the source of truth for whether a
position is open.

THE SCENARIO

    position OPEN -> user logs out -> broker position CLOSED -> user logs in
    => TradeMentor must show CLOSED, with the exit reconstructed

WHAT WAS ALREADY TRUE, and is pinned here so it cannot regress:

  * There is no user logout endpoint at all. User auth is a JWT minted from
    Zerodha OAuth, so "logging out" is the client dropping a token — it touches
    neither BrokerAccount nor the access token.
  * Both background jobs select on `BrokerAccount.status == "connected"` and a
    present access token. Neither references login, session or activity.
  * `sync_positions` marks any position ABSENT from the broker response as
    closed, so open-state self-corrects on any sync.

WHAT WAS NOT TRUE, and is fixed:

  * `eod_dispatch_chunk` selected only accounts that had TRADED TODAY, which
    excluded exactly the accounts whose exit we had missed. See the widened
    selection below.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
APP = BACKEND / "app"


def _src(rel: str) -> str:
    return (APP / rel).read_text(encoding="utf-8")


# ── the session cannot touch ingestion ─────────────────────────────────────

def test_there_is_no_user_logout_endpoint_that_could_stop_ingestion():
    """
    A user "logs out" by discarding a JWT. If a logout route ever appears it
    must not revoke the broker token — that would stop background sync for a
    user who simply closed the app.
    """
    for path in (APP / "api").glob("*.py"):
        if "_archive" in path.parts:
            continue
        src = path.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'@router\.(post|get)\("([^"]*logout[^"]*)"', src):
            # Admin logout is a different subsystem and may exist.
            assert "admin" in path.as_posix(), (
                f"user-facing logout route {m.group(2)} in {path.name} — "
                f"it must not be able to revoke broker ingestion"
            )


@pytest.mark.parametrize("rel,fn", [
    ("tasks/trade_tasks.py", "eod_dispatch_chunk"),
    ("tasks/reconciliation_tasks.py", "_reconcile_all_accounts"),
])
def test_background_jobs_do_not_filter_on_user_session(rel, fn):
    """
    Ingestion is selected by BROKER ACCOUNT state, never by whether anyone is
    logged in. A session-shaped filter here would silently stop sync for every
    user who closed their browser.
    """
    src = _src(rel)
    body = src[src.index(f"def {fn}"):]
    body = body[: body.find("\nasync def ", 10) if "\nasync def " in body[10:] else len(body)]
    for forbidden in ("last_login", "session_active", "is_online", "last_seen",
                      "jwt", "current_user"):
        assert forbidden not in body, (
            f"{fn} filters ingestion on {forbidden!r} — the user session must "
            f"not gate broker sync"
        )
    assert 'status == "connected"' in body or "status == 'connected'" in body


# ── the fix: EOD must reach accounts holding an open position ──────────────

def test_eod_covers_accounts_that_hold_an_open_position():
    """
    THE GAP. Selection was `traded_today` alone, so a user who opened a
    position yesterday, closed the browser and exited today from the Kite app
    produced no trade row and was skipped — losing the only same-day chance to
    reconstruct the exit.
    """
    src = _src("tasks/trade_tasks.py")
    body = src[src.index("async def eod_dispatch_chunk"):]
    body = body[: body.index("@celery_app.task", 10)] if "@celery_app.task" in body[10:] else body

    assert "holds_open_position" in body
    assert "or_(" in body, "the two account sets must be OR-ed, not AND-ed"
    assert 'Position.status != "closed"' in body or "_Position.status != \"closed\"" in body
    assert "total_quantity != 0" in body


def test_eod_still_covers_accounts_that_traded_today():
    """The widening must ADD a set, never replace the original one."""
    src = _src("tasks/trade_tasks.py")
    body = src[src.index("async def eod_dispatch_chunk"):]
    assert "traded_today" in body
    assert "Trade.order_timestamp >= today_start_utc" in body


def test_the_widening_is_not_polling():
    """
    An account appears at most once per daily fan-out either way. If this ever
    grows a schedule of its own it stops being a daily sweep.
    """
    src = _src("tasks/trade_tasks.py")
    body = src[src.index("async def eod_dispatch_chunk"):]
    body = body[: body.index("@celery_app.task", 10)] if "@celery_app.task" in body[10:] else body
    assert ".distinct()" in body
    # Strip comments first — the rationale prose legitimately contains words
    # like "every", and matching against it would be testing the comment.
    code = chr(10).join(
        l for l in body.splitlines() if not l.strip().startswith("#")
    )
    for forbidden in ("while True", "sleep(", "countdown=1"):
        assert forbidden not in code


# ── broker is the source of truth for open/closed ──────────────────────────

def test_a_position_absent_from_the_broker_response_is_marked_closed():
    """
    The reverse sweep. Without it, a position closed while we were not watching
    would stay open locally forever — the broker would no longer be the source
    of truth.
    """
    src = _src("services/trade_sync_service.py")
    body = src[src.index("async def sync_positions"):]
    assert "seen_keys" in body
    assert 'status = "closed"' in body
    assert "total_quantity = 0" in body


def test_an_overnight_close_is_reconstructed_from_broker_fields():
    """
    The exit fill itself is unrecoverable once the day rolls, so the
    CompletedTrade is rebuilt from Zerodha's own position numbers rather than
    from a fabricated fill.
    """
    from app.services.trade_sync_service import TradeSyncService

    doc = inspect.getdoc(TradeSyncService._backfill_overnight_completed_trades) or ""
    assert "realised" in doc
    assert "day_sell_price" in doc
    # entry_time is an approximation and must be documented as one, not
    # presented as an observed timestamp.
    assert "approximation" in doc.lower()


def test_the_overnight_backfill_is_gated_on_a_tracked_position():
    """
    Only positions we already had a row for are backfilled — otherwise any
    unrelated broker position would materialise as a TradeMentor trade.
    """
    src = _src("services/trade_sync_service.py")
    body = src[src.index("async def sync_positions"):]
    assert "_pos_key not in existing_positions" in body
    assert "overnight_quantity" in body


def test_replay_of_missed_fills_is_idempotent_by_construction():
    """
    Duplicate reconciliation must not double-count. The ledger keys on the
    fill's idempotency key, so a fill already ingested by the stream is a no-op
    when the sync replays it.
    """
    src = _src("services/trade_sync_service.py")
    assert "replay_missed_fills_into_ledger" in src
    assert "idempotent" in src.lower()


def test_login_sync_is_a_safety_net_not_the_primary_mechanism():
    """
    The auto-sync on page load is allowed to exist, but the daily fan-out must
    remain scheduled independently of it — otherwise ingestion would depend on
    someone opening the app.
    """
    celery_src = (APP / "core" / "celery_app.py").read_text(encoding="utf-8")
    assert "eod_sync_all_accounts" in celery_src
    assert "reconciliation_tasks.reconcile_trades" in celery_src


# ── the test database must never be the production one ─────────────────────

def test_the_suite_refuses_an_unrecognised_database(monkeypatch):
    """
    The suite writes and deletes rows using `settings.DATABASE_URL` — the same
    URL the application runs on. A bad DELETE in a test could destroy real
    trader data and nothing stopped it.

    FAIL CLOSED: anything not recognisable as a test database is treated as
    production. Guessing wrong in that direction is recoverable; the other way
    is not.
    """
    from tests.conftest import _assert_safe_test_database

    # The escape hatch may be set for this very run; the guard itself must
    # still refuse without it.
    monkeypatch.delenv("ALLOW_TESTS_ON_THIS_DB", raising=False)
    with pytest.raises(RuntimeError, match="REFUSING"):
        _assert_safe_test_database(
            "postgresql://u:p@db.abcdefghijkl.supabase.co:5432/postgres"
        )


@pytest.mark.parametrize("url", [
    "postgresql://u:p@localhost:5432/app",
    "postgresql://u:p@127.0.0.1:5432/app",
    "postgresql://u:p@host:5432/tradementor_test",
])
def test_recognisable_test_databases_are_allowed(url, monkeypatch):
    from tests.conftest import _assert_safe_test_database

    monkeypatch.delenv("ALLOW_TESTS_ON_THIS_DB", raising=False)
    _assert_safe_test_database(url)


def test_the_escape_hatch_is_explicit(monkeypatch):
    """
    Running against the current database must be a deliberate act, not a
    default. It is opt-in per invocation.
    """
    from tests.conftest import _assert_safe_test_database

    prod = "postgresql://u:p@db.abcdefghijkl.supabase.co:5432/postgres"
    monkeypatch.setenv("ALLOW_TESTS_ON_THIS_DB", "1")
    _assert_safe_test_database(prod)
    monkeypatch.setenv("ALLOW_TESTS_ON_THIS_DB", "0")
    with pytest.raises(RuntimeError):
        _assert_safe_test_database(prod)


def test_checkpoint_tasks_is_archived_and_unscheduled():
    """
    It made 2 Kite REST calls per alert plus one at T+30 and had no caller at
    all. Archived rather than deleted, per the project rule.
    """
    assert not (APP / "tasks" / "checkpoint_tasks.py").exists()
    assert (APP / "tasks" / "_archive" / "checkpoint_tasks.py").exists()

    celery_src = (APP / "core" / "celery_app.py").read_text(encoding="utf-8")
    for line in celery_src.splitlines():
        if line.strip().startswith("#"):
            continue
        assert "checkpoint_tasks" not in line, (
            "checkpoint_tasks is registered or routed again"
        )
