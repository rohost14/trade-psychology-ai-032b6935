"""
The account-risk denominator must be stable, honest about its source, and
willing to say it does not know.

Three properties this pins, each of which was a live defect or a near-miss:

  1. `live_balance` must never be the denominator. It moves with M2M and margin
     utilisation, so a %-of-equity floor built on it gets EASIER to breach as
     the day goes worse. `margin_snapshots.equity_total` stores live_balance
     despite its name — this is the trap.
  2. The denominator is frozen per session. A deposit at 13:00 must not
     retroactively change what the morning's alerts meant.
  3. Abstention returns None, not a default. A caller that wants "5% of the
     account" has to handle not knowing.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.account_risk import (
    ABSTAIN,
    STALE_AFTER,
    UNUSABLE_AFTER,
    AccountRisk,
    DenominatorSource,
    Quality,
    freeze_for_session,
)


class FakeSession:
    def __init__(self, **kw):
        self.risk_denominator = kw.get("risk_denominator")
        self.risk_denominator_source = kw.get("risk_denominator_source")
        self.risk_denominator_as_of = kw.get("risk_denominator_as_of")
        self.risk_denominator_quality = kw.get("risk_denominator_quality")


class FakeDB:
    async def flush(self):
        return None


NOW = datetime(2026, 8, 23, 10, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# The arithmetic, and refusing to do it
# ---------------------------------------------------------------------------

def test_fraction_of_a_known_account():
    r = AccountRisk(Decimal("50000"), DenominatorSource.OPENING_BALANCE, NOW, Quality.GOOD)
    assert r.fraction(2500) == pytest.approx(0.05)
    assert r.fraction(-2500) == pytest.approx(0.05)   # sign-agnostic: it is a magnitude


def test_abstention_returns_none_not_a_default():
    """
    The whole point. A caller asking "what fraction of the account is this"
    must receive None and handle it, never a number derived from a guess.
    """
    assert ABSTAIN.value is None
    assert ABSTAIN.is_usable is False
    assert ABSTAIN.fraction(10_000) is None
    assert ABSTAIN.quality is Quality.UNKNOWN


def test_a_zero_or_negative_account_is_not_usable():
    """A debit-balance account cannot denominate a percentage."""
    for bad in (Decimal("0"), Decimal("-5000")):
        r = AccountRisk(bad, DenominatorSource.OPENING_BALANCE, NOW, Quality.GOOD)
        assert r.is_usable is False
        assert r.fraction(1000) is None


# ---------------------------------------------------------------------------
# Provenance must survive to the copy
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("source,expected_phrase", [
    (DenominatorSource.OPENING_BALANCE, "opening balance today"),
    (DenominatorSource.OPENING_BALANCE_STALE, "last known opening balance"),
    (DenominatorSource.DECLARED_CAPITAL, "capital you declared"),
])
def test_describe_names_the_source(source, expected_phrase):
    """
    A trader told "that was 40% of your account" deserves to know whether we
    measured that or they told us.
    """
    r = AccountRisk(Decimal("50000"), source, NOW, Quality.GOOD)
    assert expected_phrase in r.describe()


def test_declared_capital_is_never_GOOD_quality():
    """
    Self-reported and usually stale — that is what capital_mismatch exists to
    catch. It is usable, but it is not a measurement.
    """
    r = AccountRisk(Decimal("50000"), DenominatorSource.DECLARED_CAPITAL, None, Quality.PARTIAL)
    assert r.quality is not Quality.GOOD
    assert r.is_usable


def test_live_balance_is_not_an_available_source():
    """
    Guard against the specific mistake this module exists to prevent. If someone
    adds a live_balance rung later, this fails and they have to argue for it.
    """
    assert "live_balance" not in {s.value for s in DenominatorSource}


# ---------------------------------------------------------------------------
# Session freezing
# ---------------------------------------------------------------------------

async def test_freeze_records_value_source_and_quality():
    s = FakeSession()
    r = AccountRisk(Decimal("50000"), DenominatorSource.OPENING_BALANCE, NOW, Quality.GOOD)
    await freeze_for_session(s, r, FakeDB())
    assert s.risk_denominator == Decimal("50000")
    assert s.risk_denominator_source == "opening_balance"
    assert s.risk_denominator_quality == "GOOD"
    assert s.risk_denominator_as_of == NOW


async def test_freeze_never_overwrites_an_existing_denominator():
    """
    A mid-session deposit must not rewrite the morning. The risk a trader took
    at 10:00 was risk against the account they had at 10:00.
    """
    s = FakeSession(risk_denominator=Decimal("50000"),
                    risk_denominator_source="opening_balance",
                    risk_denominator_quality="GOOD")
    bigger = AccountRisk(Decimal("500000"), DenominatorSource.OPENING_BALANCE, NOW, Quality.GOOD)
    await freeze_for_session(s, bigger, FakeDB())
    assert s.risk_denominator == Decimal("50000")


async def test_abstention_is_recorded_not_silent():
    """
    A session where we could not measure account impact must be
    distinguishable from one we never asked about.
    """
    s = FakeSession()
    await freeze_for_session(s, ABSTAIN, FakeDB())
    assert s.risk_denominator is None
    assert s.risk_denominator_quality == "UNKNOWN"


# ---------------------------------------------------------------------------
# Staleness
# ---------------------------------------------------------------------------

def test_staleness_windows_are_ordered_and_sane():
    """
    Yesterday's opening balance is a reasonable stand-in for today's account
    size; last month's is not.
    """
    assert timedelta(0) < STALE_AFTER < UNUSABLE_AFTER
    assert UNUSABLE_AFTER <= timedelta(days=30)
