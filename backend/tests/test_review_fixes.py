"""
Regressions for the four defects found reviewing this session's own work.

Each was introduced by a change made the same day, and three of the four are the
same shape: a class of bug was fixed in one place and asserted fixed everywhere
without checking. Consent, `== "danger"`, leg-counting and the latency exclusion
all recurred within hours of being "fixed".
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.alert_service import guardian_reachable
from app.services.detection_quality import latency_seconds, summarise_latency
from app.services.entry_checks import evaluate_mis_panic
from app.tasks.trade_tasks import _same_instrument

NOW = datetime(2026, 8, 9, 10, 0, tzinfo=timezone.utc)


# ── 1. The merge must not attribute another instrument's money ───────────────

def live_alert(symbol=None):
    return SimpleNamespace(details={"symbol": symbol} if symbol else {})


def trade(symbol):
    return SimpleNamespace(tradingsymbol=symbol)


def test_merge_refuses_a_different_instrument():
    """
    A live premium_loss_event on a NIFTY call, then an unrelated BANKNIFTY round
    closing, used to link the NIFTY alert to BANKNIFTY's trade — and
    behaviour→money joins on that column, so the figure the merge exists to
    protect reported another instrument's P&L.
    """
    assert _same_instrument(
        live_alert("NIFTY25AUG24500CE"), trade("BANKNIFTY25AUG52000PE")
    ) is False


def test_merge_accepts_the_same_instrument():
    assert _same_instrument(
        live_alert("NIFTY25AUG24500CE"), trade("NIFTY25AUG24500CE")
    ) is True


def test_merge_is_case_insensitive():
    assert _same_instrument(live_alert("nifty25aug24500ce"), trade("NIFTY25AUG24500CE")) is True


def test_account_level_alerts_still_merge():
    """
    A daily trade or loss limit names no instrument — it is a statement about
    the session, so it legitimately links to whichever round closed.
    """
    assert _same_instrument(live_alert(None), trade("NIFTY25AUG24500CE")) is True
    assert _same_instrument(SimpleNamespace(details=None), trade("ANY")) is True


# ── 2. A merged alert must stay out of the latency sample ───────────────────

def alert(seconds=1.0, lifecycle="post", details=None):
    return SimpleNamespace(
        pattern_type="revenge_trade", lifecycle=lifecycle,
        detected_at=NOW, created_at=NOW + timedelta(seconds=seconds),
        outcome=None, acknowledged_at=None, details=details or {},
    )


def test_a_merged_entry_alert_is_still_excluded_from_latency():
    """
    The merge flips lifecycle to 'post', so a lifecycle-only check let the
    near-zero delta back into the sample — reintroducing exactly the distortion
    the exclusion was written to prevent, and making the pipeline look faster
    than it is. `at_entry` survives the merge; lifecycle does not.
    """
    merged = alert(seconds=0.01, lifecycle="post", details={"at_entry": True})
    assert latency_seconds(merged) is None


def test_ordinary_post_hoc_alerts_are_still_measured():
    assert latency_seconds(alert(seconds=3.0)) == 3.0


def test_merged_alerts_are_reported_as_excluded_not_measured():
    summary = summarise_latency([
        alert(seconds=0.01, lifecycle="post", details={"at_entry": True}),
        alert(seconds=2.0),
    ])
    assert summary["alerts_measured"] == 1
    assert summary["alerts_excluded_live"] == 1
    assert summary["p50_seconds"] == 2.0


# ── 3. The MIS window must use this batch's exchange ────────────────────────

IST_OFFSET = timezone(timedelta(hours=5, minutes=30))


def test_mcx_window_does_not_silence_an_nfo_entry():
    """
    The exchange used to come from the first MIS fill of the DAY. One morning
    MCX position set the window to MCX's 23:00 square-off, and every afternoon
    NFO entry then evaluated against it — the detector silently never fired for
    the rest of the session.
    """
    at_1510 = datetime(2026, 8, 6, 15, 10, tzinfo=IST_OFFSET)
    assert evaluate_mis_panic(at_1510, "MCX", "MIS", 3) is None      # wrong exchange
    assert evaluate_mis_panic(at_1510, "NFO", "MIS", 3) is not None  # right one fires


# ── 4. Every guardian path goes through one consent gate ───────────────────

def user(phone="+919000000002", confirmed=True):
    return SimpleNamespace(guardian_phone=phone, guardian_confirmed=confirmed)


def test_an_unconfirmed_guardian_is_never_reachable():
    """
    The gate existed on two paths and not on four others, so a guardian who
    replied NO — or never replied — still received scheduled reports daily and
    weekly. The consent handshake promises otherwise.
    """
    phone, reason = guardian_reachable(user(confirmed=False))
    assert phone is None
    assert reason == "guardian_not_confirmed"


def test_a_confirmed_guardian_is_reachable():
    phone, reason = guardian_reachable(user())
    assert phone == "+919000000002"
    assert reason is None


def test_no_phone_is_reported_distinctly_from_no_consent():
    """Different reasons need different fixes — one is setup, one is a refusal."""
    assert guardian_reachable(user(phone=None))[1] == "no_guardian_phone"
    assert guardian_reachable(user(phone="   "))[1] == "no_guardian_phone"
    assert guardian_reachable(None)[1] == "no_user"


def test_every_guardian_send_path_uses_the_gate():
    """
    The structural half. Four task modules contacted a guardian and none checked
    consent; a fifth path fixed earlier is not evidence the rest were.
    """
    import pathlib

    tasks = pathlib.Path(__file__).resolve().parent.parent / "app" / "tasks"
    offenders = []
    for name in ("alert_tasks.py", "report_tasks.py", "retention_tasks.py"):
        text = (tasks / name).read_text(encoding="utf-8")
        if "guardian_phone" in text and "guardian_reachable" not in text:
            offenders.append(name)
    assert offenders == [], f"guardian contacted without the consent gate: {offenders}"


def test_the_merge_call_site_actually_checks_the_instrument():
    """
    The helper being correct proves nothing if the merge does not call it —
    which is how a green suite covered a guardian formatter that production
    never reached. This asserts the guard is in the branch.
    """
    import pathlib
    import re

    src = (pathlib.Path(__file__).resolve().parent.parent
           / "app" / "tasks" / "trade_tasks.py").read_text(encoding="utf-8")
    merge = re.search(
        r"_prior = last_fired_alert\.get\(k\)(.{0,400}?)_prior\.trigger_completed_trade_id = ",
        src, re.S,
    )
    assert merge, "merge block not found — did it move?"
    assert "_same_instrument(" in merge.group(1)


def test_a_merged_position_monitor_alert_is_also_excluded():
    """
    overexposure, holding_loser and portfolio_concentration carry no `at_entry`
    marker — they are not entry-rule checks. _fire_position_alert stamps `live`
    on every alert it creates so the exclusion survives a merge for those too.
    """
    merged = alert(seconds=0.02, lifecycle="post", details={"live": True, "symbol": "X"})
    assert latency_seconds(merged) is None


def test_position_monitor_stamps_the_live_marker_at_creation():
    """
    Stamped once where the alerts are born, not at each call site — three of the
    five callers had no marker at all.
    """
    import pathlib

    src = (pathlib.Path(__file__).resolve().parent.parent
           / "app" / "tasks" / "position_monitor_tasks.py").read_text(encoding="utf-8")
    assert 'details.setdefault("live", True)' in src


# ── The five lower-severity items ────────────────────────────────────────────

def test_drain_does_not_lose_a_fill_that_lands_mid_drain():
    """
    Read-then-delete dropped fills. A fill landing between the LRANGE and the
    DELETE was wiped, and because its SET NX succeeded it also scheduled a flush
    that then drained an empty window — so that entry got no checks at all,
    silently. RENAME moves the list aside in one operation.
    """
    from tests.test_entry_batch import ACCOUNT, FakeRedis, leg
    from app.services.entry_batch_service import add_fill, drain

    r = FakeRedis()
    add_fill(r, ACCOUNT, leg("FIRST"))

    original_lrange = r.lrange

    def lrange_then_race(key, start, end):
        rows = original_lrange(key, start, end)
        add_fill(r, ACCOUNT, leg("RACER"))    # arrives mid-drain
        return rows

    r.lrange = lrange_then_race
    drained = drain(r, ACCOUNT)

    assert [f["symbol"] for f in drained] == ["FIRST"]
    # The racer must survive into the NEXT window rather than vanish.
    assert [f["symbol"] for f in drain(r, ACCOUNT)] == ["RACER"]


def test_draining_an_empty_window_is_not_an_error():
    from tests.test_entry_batch import ACCOUNT, FakeRedis
    from app.services.entry_batch_service import drain

    assert drain(FakeRedis(), ACCOUNT) == []


def test_releasing_a_window_lets_the_next_fill_open_a_new_one():
    """
    When the flush cannot be queued, the claim has to be given back — otherwise
    every fill for the marker's full TTL joins a window nobody will process and
    none of them falls back to an inline check.
    """
    from tests.test_entry_batch import ACCOUNT, FakeRedis, leg
    from app.services.entry_batch_service import add_fill, release_window

    r = FakeRedis()
    assert add_fill(r, ACCOUNT, leg("A")) is True
    assert add_fill(r, ACCOUNT, leg("B")) is False       # window already open
    release_window(r, ACCOUNT)
    assert add_fill(r, ACCOUNT, leg("C")) is True        # claim is free again


def test_a_panic_call_and_put_is_not_one_disciplined_straddle():
    """
    A 120s window swallowed a panic entry: buying a call and then a put a minute
    later classified as a straddle and collapsed to one decision — the opposite
    of what that behaviour is. Structures go in seconds apart.
    """
    from tests.test_structure_counting import trade, CE_LO
    from app.services.strategy_detector import count_structures

    panic = [trade(CE_LO, "LONG", 0), trade("NIFTY25AUG24500PE", "LONG", 60)]
    assert count_structures(panic) == 2

    real_straddle = [trade(CE_LO, "LONG", 0), trade("NIFTY25AUG24500PE", "LONG", 2)]
    assert count_structures(real_straddle) == 1


def test_has_danger_is_true_for_critical():
    """
    A critical alert published has_danger:false to the browser — the exact
    literal comparison app/core/severity.py exists to eliminate, in a function
    this session had already edited twice.
    """
    import pathlib

    src = (pathlib.Path(__file__).resolve().parent.parent
           / "app" / "tasks" / "position_monitor_tasks.py").read_text(encoding="utf-8")
    assert '"has_danger": is_notifiable(severity)' in src
    assert '"has_danger": severity == "danger"' not in src


# ── instrument_type on the live path (found by alertlab scenario E-05) ───────

def test_ledger_derives_instrument_type_from_the_symbol():
    """
    A Kite postback carries no instrument type, and the ledger builder replaced
    the FIFO calculator that used to set it — so every CompletedTrade created
    live had instrument_type NULL. Twelve guards in behavior_engine read it, so
    premium_loss_event, options_premium_avg_down, expiry_day_overtrading
    (since retired, 2026-08-27), fomo_entry and opening_5min_trap fired on
    bulk-synced trades and silently never fired on live ones.
    """
    from app.services.position_ledger_service import _instrument_type_for

    assert _instrument_type_for("NIFTY26AUG24500CE") == "CE"
    assert _instrument_type_for("NIFTY26AUG24500PE") == "PE"
    assert _instrument_type_for("NIFTY26AUGFUT") == "FUT"


def test_an_equity_ticker_ending_in_ce_is_not_an_option():
    """RELIANCE ends in CE. A suffix check would make every options detector
    run against an equity position."""
    from app.services.position_ledger_service import _instrument_type_for

    assert _instrument_type_for("RELIANCE") == "EQ"


def test_the_completed_trade_builder_sets_instrument_type():
    """The helper being right proves nothing if the builder does not call it."""
    import pathlib
    import re

    src = (pathlib.Path(__file__).resolve().parent.parent
           / "app" / "services" / "position_ledger_service.py").read_text(encoding="utf-8")
    ctor = re.search(r"tradingsymbol=close_entry\.tradingsymbol,(.{0,900}?)direction=fields",
                     src, re.S)
    assert ctor, "CompletedTrade construction not found — did it move?"
    assert "instrument_type=_instrument_type_for(" in ctor.group(1)
