"""
E1 — fill classification and the entry coalescing window.

Two things are under test:

  * classify_scale_in — adding to a winner and adding to a loser are opposite
    behaviours in the same shape, and collapsing them would false-positive on
    every disciplined scale-in.
  * entry_batch_service — the window that makes one intent produce one
    evaluation, whether it arrived as one fill, three partial fills, or the four
    legs of a condor.
"""
from decimal import Decimal

import pytest

from app.services.entry_batch_service import (
    MAX_BATCH_FILLS, add_fill, describe, drain, summarise,
)
from app.services.fill_classification import (
    ADD_TO_LOSER, ADD_TO_WINNER, classify_fill, classify_scale_in, opens_position,
)


# ── Scale-in classification ──────────────────────────────────────────────────

def test_long_adding_below_its_average_is_averaging_down():
    """Bought more at 90 when the average is 95 — the average was dragged down."""
    assert classify_scale_in("INCREASE", 200, Decimal("90"), Decimal("95")) == ADD_TO_LOSER


def test_long_adding_above_its_average_is_pyramiding():
    """Bought more at 110 when the average is 105 — adding into strength."""
    assert classify_scale_in("INCREASE", 200, Decimal("110"), Decimal("105")) == ADD_TO_WINNER


def test_short_adding_above_its_average_is_averaging_down():
    """For a short, selling more at a HIGHER price is the losing direction."""
    assert classify_scale_in("INCREASE", -200, Decimal("110"), Decimal("105")) == ADD_TO_LOSER


def test_short_adding_below_its_average_is_pyramiding():
    assert classify_scale_in("INCREASE", -200, Decimal("90"), Decimal("95")) == ADD_TO_WINNER


def test_only_increases_are_classified():
    """OPEN has no average to compare against; exits are not scale-ins at all."""
    for entry_type in ("OPEN", "DECREASE", "CLOSE", "FLIP", None):
        assert classify_scale_in(entry_type, 200, Decimal("90"), Decimal("95")) is None


def test_missing_prices_yield_no_classification():
    """Silence beats a guess — a wrong scale-in label feeds the sizing detectors."""
    assert classify_scale_in("INCREASE", 200, None, Decimal("95")) is None
    assert classify_scale_in("INCREASE", 200, Decimal("90"), None) is None
    assert classify_scale_in("INCREASE", 200, Decimal("90"), Decimal("0")) is None


def test_adding_at_exactly_the_average_is_neither():
    assert classify_scale_in("INCREASE", 200, Decimal("95"), Decimal("95")) is None


def test_classify_fill_is_json_safe_and_complete():
    """The payload goes into Redis, so it must be plain data."""
    import json
    from types import SimpleNamespace

    row = SimpleNamespace(
        entry_type="INCREASE", tradingsymbol="NIFTY25AUG24500CE", exchange="NFO",
        product="MIS", fill_qty=50, position_qty_after=150,
        fill_price=Decimal("90"), avg_entry_price_after=Decimal("95"),
    )
    payload = classify_fill(row)
    assert payload["scale_in"] == ADD_TO_LOSER
    assert payload["symbol"] == "NIFTY25AUG24500CE"
    json.dumps(payload, default=str)   # must not raise


def test_opens_position_matches_the_gate():
    assert opens_position("OPEN") and opens_position("INCREASE") and opens_position("FLIP")
    assert not opens_position("CLOSE")
    assert not opens_position("DECREASE")
    assert not opens_position(None)


# ── The coalescing window ────────────────────────────────────────────────────

class FakeRedis:
    """Enough Redis for the batch: lists, string keys with NX, expiry as a no-op."""

    def __init__(self):
        self.lists = {}
        self.keys = {}

    def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    def ltrim(self, key, start, end):
        items = self.lists.get(key, [])
        self.lists[key] = items[start:] if end == -1 else items[start:end + 1]

    def expire(self, key, ttl):
        pass

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.keys:
            return None
        self.keys[key] = value
        return True

    def rename(self, src, dst):
        # Real Redis raises when the source key does not exist. Modelling that
        # matters: drain() relies on the error to detect an empty window, and a
        # forgiving fake would hide a wrong branch.
        if src not in self.lists:
            raise RuntimeError("no such key")
        self.lists[dst] = self.lists.pop(src)

    def lrange(self, key, start, end):
        return list(self.lists.get(key, []))

    def delete(self, key):
        self.lists.pop(key, None)
        self.keys.pop(key, None)


ACCOUNT = "11111111-2222-3333-4444-555555555555"


def leg(symbol, scale_in=None):
    return {"entry_type": "OPEN", "symbol": symbol, "scale_in": scale_in}


def test_first_fill_opens_the_window_and_owns_the_flush():
    r = FakeRedis()
    assert add_fill(r, ACCOUNT, leg("NIFTY25AUG24500CE")) is True


def test_later_fills_join_the_open_window():
    """
    The four legs of a condor must schedule ONE flush. If each returned True the
    coalescing would be pointless — four windows, four evaluations.
    """
    r = FakeRedis()
    results = [
        add_fill(r, ACCOUNT, leg(s))
        for s in ("N24500CE", "N24700CE", "N24300PE", "N24100PE")
    ]
    assert results == [True, False, False, False]


def test_draining_returns_every_fill_in_the_window():
    r = FakeRedis()
    for s in ("N24500CE", "N24700CE"):
        add_fill(r, ACCOUNT, leg(s))
    fills = drain(r, ACCOUNT)
    assert [f["symbol"] for f in fills] == ["N24500CE", "N24700CE"]


def test_draining_clears_the_window():
    r = FakeRedis()
    add_fill(r, ACCOUNT, leg("N24500CE"))
    drain(r, ACCOUNT)
    assert drain(r, ACCOUNT) == []


def test_a_fill_after_the_drain_opens_a_new_window():
    """Otherwise a burst that straddles a flush would be silently swallowed."""
    r = FakeRedis()
    add_fill(r, ACCOUNT, leg("N24500CE"))
    drain(r, ACCOUNT)
    assert add_fill(r, ACCOUNT, leg("N24900CE")) is True


def test_accounts_do_not_share_a_window():
    r = FakeRedis()
    other = "99999999-8888-7777-6666-555555555555"
    add_fill(r, ACCOUNT, leg("N24500CE"))
    assert add_fill(r, other, leg("BANKNIFTY52000CE")) is True
    assert len(drain(r, ACCOUNT)) == 1
    assert len(drain(r, other)) == 1


def test_window_is_capped_but_keeps_the_most_recent():
    r = FakeRedis()
    for i in range(MAX_BATCH_FILLS + 10):
        add_fill(r, ACCOUNT, leg(f"SYM{i}"))
    fills = drain(r, ACCOUNT)
    assert len(fills) == MAX_BATCH_FILLS
    assert fills[-1]["symbol"] == f"SYM{MAX_BATCH_FILLS + 9}"


def test_undecodable_entries_are_skipped_not_fatal():
    r = FakeRedis()
    add_fill(r, ACCOUNT, leg("N24500CE"))
    r.lists["entry_batch:" + ACCOUNT].append("{not json")
    fills = drain(r, ACCOUNT)
    assert [f["symbol"] for f in fills] == ["N24500CE"]


# ── Summarising a window ─────────────────────────────────────────────────────

def test_partial_fills_of_one_order_summarise_as_one_instrument():
    """Three fills of a 300-lot order are one entry, not three."""
    fills = [leg("NIFTY25AUG24500CE") for _ in range(3)]
    summary = summarise(fills)
    assert summary["fill_count"] == 3
    assert summary["distinct_symbols"] == 1


def test_a_four_leg_structure_summarises_as_four_instruments():
    fills = [leg(s) for s in ("N24500CE", "N24700CE", "N24300PE", "N24100PE")]
    assert summarise(fills)["distinct_symbols"] == 4


def test_summary_collects_scale_in_labels():
    fills = [leg("A", ADD_TO_LOSER), leg("B"), leg("C", ADD_TO_WINNER)]
    assert summarise(fills)["scale_ins"] == [ADD_TO_LOSER, ADD_TO_WINNER]


# ── Copy ─────────────────────────────────────────────────────────────────────

def test_one_instrument_is_named():
    assert describe(["NIFTY25AUG24500CE"]) == "NIFTY25AUG24500CE"


def test_several_instruments_are_counted_not_listed():
    """
    Naming one arbitrary leg of a four-leg structure is a false statement about
    what the trader did; listing all four is unreadable on a phone.
    """
    text = describe(["N24500CE", "N24700CE", "N24300PE", "N24100PE"])
    assert "4 positions" in text
    assert "N24500CE" in text
    assert "+3 more" in text


def test_empty_batch_still_describes_something():
    assert describe([]) == "a position"


# ── The flush: one window, one evaluation ────────────────────────────────────

async def test_flush_evaluates_a_four_leg_window_once(monkeypatch):
    """
    The point of E1. Four legs in one window must produce ONE concentration
    check and ONE entry-rules check, not four of each — while exposure stays
    per instrument, because each leg is its own position.
    """
    import app.tasks.position_monitor_tasks as pm

    r = FakeRedis()
    for s in ("N24500CE", "N24700CE", "N24300PE", "N24100PE"):
        add_fill(r, ACCOUNT, leg(s))

    monkeypatch.setattr(pm, "_get_redis", lambda: r)

    calls = {"concentration": 0, "exposure": [], "rules": []}

    async def fake_concentration(_acct):
        calls["concentration"] += 1

    async def fake_exposure(_acct, symbol):
        calls["exposure"].append(symbol)

    async def fake_rules(_acct, symbols):
        calls["rules"].append(symbols)

    monkeypatch.setattr(pm, "_concentration_task", fake_concentration)
    monkeypatch.setattr(pm, "_overexposure_task", fake_exposure)
    monkeypatch.setattr(pm, "_entry_rules_task", fake_rules)

    result = await pm._flush_entry_batch(ACCOUNT)

    assert result == {"fills": 4, "symbols": 4}
    assert calls["concentration"] == 1
    assert calls["exposure"] == ["N24500CE", "N24700CE", "N24300PE", "N24100PE"]
    assert calls["rules"] == [["N24500CE", "N24700CE", "N24300PE", "N24100PE"]]


async def test_flush_of_partial_fills_checks_one_instrument(monkeypatch):
    """Three fills of one order are one entry — one exposure check, not three."""
    import app.tasks.position_monitor_tasks as pm

    r = FakeRedis()
    for _ in range(3):
        add_fill(r, ACCOUNT, leg("NIFTY25AUG24500CE"))

    monkeypatch.setattr(pm, "_get_redis", lambda: r)
    seen = []

    async def noop(*_a, **_k):
        return None

    async def fake_exposure(_acct, symbol):
        seen.append(symbol)

    monkeypatch.setattr(pm, "_concentration_task", noop)
    monkeypatch.setattr(pm, "_entry_rules_task", noop)
    monkeypatch.setattr(pm, "_overexposure_task", fake_exposure)

    result = await pm._flush_entry_batch(ACCOUNT)
    assert result == {"fills": 3, "symbols": 1}
    assert seen == ["NIFTY25AUG24500CE"]


async def test_flush_of_an_empty_window_does_nothing(monkeypatch):
    """A second flush for the same window must not re-run the checks."""
    import app.tasks.position_monitor_tasks as pm

    r = FakeRedis()
    monkeypatch.setattr(pm, "_get_redis", lambda: r)

    called = []

    async def boom(*_a, **_k):
        called.append(1)

    monkeypatch.setattr(pm, "_concentration_task", boom)
    monkeypatch.setattr(pm, "_overexposure_task", boom)
    monkeypatch.setattr(pm, "_entry_rules_task", boom)

    assert await pm._flush_entry_batch(ACCOUNT) == {"skipped": "empty_batch"}
    assert called == []


async def test_one_failing_check_does_not_stop_the_others(monkeypatch):
    """Entry rules must still run when the exposure check raises."""
    import app.tasks.position_monitor_tasks as pm

    r = FakeRedis()
    add_fill(r, ACCOUNT, leg("N24500CE"))
    monkeypatch.setattr(pm, "_get_redis", lambda: r)

    ran = []

    async def fake_concentration(_acct):
        ran.append("concentration")

    async def broken_exposure(_acct, _symbol):
        raise RuntimeError("LTP cache down")

    async def fake_rules(_acct, _symbols):
        ran.append("rules")

    monkeypatch.setattr(pm, "_concentration_task", fake_concentration)
    monkeypatch.setattr(pm, "_overexposure_task", broken_exposure)
    monkeypatch.setattr(pm, "_entry_rules_task", fake_rules)

    await pm._flush_entry_batch(ACCOUNT)
    assert ran == ["concentration", "rules"]
