"""
Account Risk Base — the one place that answers "how big is this account".

Every rule of the form "this cost X% of the account" needs a number to divide
by. Before this module there was no agreed answer, so `session_meltdown`
invented one inline (5% of declared capital) and nothing else could reuse it.
Detectors must not each grow their own version of this.

WHAT THE DENOMINATOR IS

`opening_balance` from Kite's /user/margins, documented by Kite as "Opening
balance at the day start".

WHAT IT IS NOT

`live_balance`. The obvious-looking field, and wrong: it is Kite's *current*
balance and moves with M2M and margin utilisation through the session. Using it
would mean a trader's account appears to shrink the moment they take risk, so a
5%-of-equity floor would get EASIER to breach as the day got worse. Backwards.
`margin_snapshots.equity_total` stores live_balance despite its name, so it is
not usable here either.

WHY IT IS FROZEN PER SESSION

Resolved once, when the session's first trade is processed, and then left alone.
A deposit or withdrawal at 13:00 must not retroactively change what the
morning's alerts meant — the risk a trader took at 10:00 was risk against the
account they had at 10:00. The resolved value is stored on the session row with
its source, timestamp and quality, so a stale or self-reported figure can never
be mistaken for live truth.

DEPLOYMENT ORDER

Migration 080 must be applied BEFORE the ORM columns are mapped. A mapped
attribute for a column that does not exist fails every select against that
table immediately - not lazily on first use. The columns are therefore left
unmapped in the models until 080 lands, and this module degrades to the
declared-capital rung in the meantime.

ABSTENTION

If nothing in the chain answers, this returns quality UNKNOWN and
`value is None`. That is a legitimate outcome, not a failure: account-relative
rules must then abstain rather than substitute a guess. A detector that cannot
compute account impact should say nothing about account impact.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

#: How old an opening_balance may be before it is downgraded to PARTIAL.
#: One calendar day: yesterday's opening balance is a reasonable stand-in for
#: today's account size; last week's is not.
STALE_AFTER = timedelta(days=1)

#: Beyond this we stop trusting it at all and fall through to declared capital.
UNUSABLE_AFTER = timedelta(days=7)


class DenominatorSource(str, Enum):
    """Which rung of the fallback chain answered. Never live_balance."""

    OPENING_BALANCE = "opening_balance"              # from this session
    OPENING_BALANCE_STALE = "opening_balance_stale"  # from a previous session
    DECLARED_CAPITAL = "declared_capital"            # self-reported


class Quality(str, Enum):
    """Same vocabulary the engine already uses for detector inputs."""

    GOOD = "GOOD"        # measured, current
    PARTIAL = "PARTIAL"  # real but stale, or self-reported
    UNKNOWN = "UNKNOWN"  # nothing usable — account-relative rules must abstain


@dataclass(frozen=True)
class AccountRisk:
    """
    The account-size denominator for one session, and how much to trust it.

    `value is None` means abstain. Callers must not substitute a default.
    """

    value: Optional[Decimal]
    source: Optional[DenominatorSource]
    as_of: Optional[datetime]
    quality: Quality
    detail: Optional[str] = None

    @property
    def is_usable(self) -> bool:
        return self.value is not None and self.value > 0

    def fraction(self, amount: float) -> Optional[float]:
        """
        `amount` as a fraction of the account, or None when we cannot say.

        Returning None is the point: a caller that wants "5% of the account"
        must handle not knowing, rather than receiving a number derived from a
        guess.
        """
        if not self.is_usable:
            return None
        return abs(float(amount)) / float(self.value)

    def describe(self) -> str:
        """Human-readable provenance, for alert copy and the Rules page."""
        if not self.is_usable:
            return "account size unknown"
        if self.source is DenominatorSource.OPENING_BALANCE:
            return f"₹{self.value:,.0f} (your opening balance today)"
        if self.source is DenominatorSource.OPENING_BALANCE_STALE:
            return f"₹{self.value:,.0f} (your last known opening balance)"
        return f"₹{self.value:,.0f} (the capital you declared)"


ABSTAIN = AccountRisk(None, None, None, Quality.UNKNOWN, "no usable account size")


async def resolve_account_risk(
    broker_account_id: UUID,
    db: AsyncSession,
    session=None,
    profile=None,
    now: Optional[datetime] = None,
) -> AccountRisk:
    """
    Resolve the denominator for this session, reusing the frozen value if set.

    Order:
      1. already frozen on the session   → return it unchanged
      2. opening_balance from a snapshot taken today        → GOOD
      3. most recent opening_balance, under UNUSABLE_AFTER  → PARTIAL
      4. declared trading_capital                           → PARTIAL
      5. abstain                                            → UNKNOWN
    """
    now = now or datetime.now(timezone.utc)

    # 1. Frozen. The whole point of session scoping: once this session has an
    #    answer, mid-session deposits do not change it.
    if session is not None and getattr(session, "risk_denominator", None):
        try:
            return AccountRisk(
                value=Decimal(str(session.risk_denominator)),
                source=DenominatorSource(session.risk_denominator_source),
                as_of=session.risk_denominator_as_of,
                quality=Quality(session.risk_denominator_quality or Quality.PARTIAL.value),
                detail="frozen for this session",
            )
        except (ValueError, TypeError) as e:
            # A stored value we cannot interpret is worse than none: it would be
            # a number of unknown provenance. Fall through and re-resolve.
            logger.warning(f"[account_risk] unreadable frozen denominator: {e}")

    snapshot = await _latest_opening_balance(broker_account_id, db)

    if snapshot is not None:
        value, as_of = snapshot
        age = now - as_of
        if age <= STALE_AFTER:
            return AccountRisk(value, DenominatorSource.OPENING_BALANCE, as_of,
                               Quality.GOOD, "opening balance from this session")
        if age <= UNUSABLE_AFTER:
            return AccountRisk(value, DenominatorSource.OPENING_BALANCE_STALE, as_of,
                               Quality.PARTIAL, f"opening balance from {age.days}d ago")

    declared = getattr(profile, "trading_capital", None) if profile is not None else None
    if declared and float(declared) > 0:
        # Self-reported and often out of date — which is what `capital_mismatch`
        # exists to detect — so PARTIAL, never GOOD.
        return AccountRisk(Decimal(str(declared)), DenominatorSource.DECLARED_CAPITAL,
                           None, Quality.PARTIAL, "capital you declared")

    return ABSTAIN


async def _latest_opening_balance(broker_account_id: UUID, db: AsyncSession):
    """Most recent non-null opening balance, with its timestamp."""
    from app.models.margin_snapshot import MarginSnapshot

    # Until migration 080 is applied the column is not mapped, and asking for it
    # would raise rather than degrade. Absence simply means this rung cannot
    # answer, so the chain falls through to declared capital - which is exactly
    # what the fallback exists for.
    col = getattr(MarginSnapshot, "equity_opening_balance", None)
    if col is None:
        return None

    result = await db.execute(
        select(col, MarginSnapshot.snapshot_at)
        .where(
            MarginSnapshot.broker_account_id == broker_account_id,
            col.isnot(None),
            col > 0,
        )
        .order_by(desc(MarginSnapshot.snapshot_at))
        .limit(1)
    )
    row = result.first()
    if not row or row[0] is None:
        return None
    as_of = row[1]
    if as_of is not None and as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    return Decimal(str(row[0])), as_of


async def freeze_for_session(session, risk: AccountRisk, db: AsyncSession) -> None:
    """
    Record the denominator this session used, once.

    Writing it down is what makes an alert re-explainable later: "you were 40%
    into your day" is only checkable if we know what the day was measured
    against. Never overwrites — a session's denominator is decided once.
    """
    if session is None or getattr(session, "risk_denominator", None):
        return
    if not risk.is_usable:
        # Abstention is recorded too. A session where we could not measure
        # account impact should be distinguishable from one we never asked
        # about, so the quality is stored even with no value.
        session.risk_denominator_quality = Quality.UNKNOWN.value
        return

    session.risk_denominator = risk.value
    session.risk_denominator_source = risk.source.value if risk.source else None
    session.risk_denominator_as_of = risk.as_of
    session.risk_denominator_quality = risk.quality.value
    await db.flush()
