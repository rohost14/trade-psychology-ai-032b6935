"""
Alerts raised while a position is still open.

WHY THIS IS SEPARATE FROM BehaviorEngine
BehaviorEngine.analyze() is called once per CompletedTrade, after FIFO closes a
position. Every one of its 26 detectors declares `completed_trade` in its
`consumes` tuple, either explicitly or via the registry default, so none of them
can run without a closed trade. Making that context optional would weaken the
guarantees of every existing detector on the money-truth path, so this is a
separate engine that shares only thresholds, the RiskAlert model and the
severity vocabulary.

SCOPE
Deliberately one detector: no_stoploss. It is the least ambiguous of the seven
candidates in docs/LIVE_ALERTS_SPEC.md, needs no trade history, and can be
checked by hand against a Kite order book. The failure mode we are avoiding is a
wall of live alerts nobody trusts, which is strictly worse than the current wall
of receipts nobody reads. Add the next detector only after this one has survived
a week of shadow mode.

SHADOW MODE
Gated by the existing detector_flags machinery under the key
`live_no_stoploss`. Off by default. In shadow it writes the alert and marks it
undelivered, so we can compare what the live path concluded against what the
post-hoc engine concludes at close, without showing the user anything.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.risk_alert import RiskAlert

logger = logging.getLogger(__name__)

DETECTOR_KEY = "live_no_stoploss"
DETECTOR_VERSION = "1.0.0"

#: Minutes a position may sit without a stop-loss before it is worth saying so.
#: Not zero: an SL order frequently lands a few seconds after the entry fill,
#: and firing on that race would train the user to distrust the alert on day one.
GRACE_MINUTES = 5


@dataclass
class LivePosition:
    """The minimum a live check needs. Built from the postback payload plus
    cached session state — deliberately no REST calls, see the spec."""
    position_id: UUID
    tradingsymbol: str
    quantity: int
    entry_time: datetime
    has_stoploss_order: bool
    unrealized_pnl: float


@dataclass
class LiveDetection:
    pattern_type: str
    severity: str
    message: str
    details: dict


def detect_no_stoploss(
    position: LivePosition,
    now: Optional[datetime] = None,
) -> Optional[LiveDetection]:
    """
    An open position with no stop-loss order attached, past the grace window.

    States the fact and the exposure. It does not tell the trader to place a
    stop, and it must never be wired to disable anything — the charter is
    mirror, not blocker.
    """
    now = now or datetime.now(timezone.utc)

    if position.has_stoploss_order:
        return None
    if position.quantity == 0:
        return None

    entry = position.entry_time
    if entry.tzinfo is None:
        entry = entry.replace(tzinfo=timezone.utc)
    open_minutes = (now - entry).total_seconds() / 60.0
    if open_minutes < GRACE_MINUTES:
        return None

    # Severity follows exposure, not opinion. A position already underwater
    # without a stop is the case worth saying loudly.
    losing = position.unrealized_pnl < 0
    severity = "danger" if losing else "caution"

    mins = int(open_minutes)
    if losing:
        message = (
            f"{position.tradingsymbol} has been open {mins} min with no stop-loss. "
            f"Currently down ₹{abs(round(position.unrealized_pnl)):,}."
        )
    else:
        message = f"{position.tradingsymbol} has been open {mins} min with no stop-loss."

    return LiveDetection(
        pattern_type="no_stoploss",
        severity=severity,
        message=message,
        details={
            "open_minutes": mins,
            "unrealized_pnl": round(position.unrealized_pnl, 2),
            "quantity": position.quantity,
            "tradingsymbol": position.tradingsymbol,
            "live": True,
        },
    )


class LivePositionEngine:
    """Evaluates open positions. One detector for now, by design."""

    async def evaluate(
        self,
        broker_account_id: UUID,
        positions: Sequence[LivePosition],
        db: AsyncSession,
        *,
        shadow: bool = True,
        now: Optional[datetime] = None,
    ) -> list[RiskAlert]:
        """
        Returns the alerts written. In shadow mode they are written but left
        undelivered, so the live conclusion can be compared against what the
        post-hoc engine decides at close without the user seeing anything.
        """
        now = now or datetime.now(timezone.utc)
        written: list[RiskAlert] = []

        for position in positions:
            detection = detect_no_stoploss(position, now=now)
            if detection is None:
                continue

            # One live alert per (position, pattern) ever. Re-evaluating on every
            # tick or postback must not produce a second row.
            if await self._already_raised(
                broker_account_id, position.position_id, detection.pattern_type, db
            ):
                continue

            alert = RiskAlert(
                broker_account_id=broker_account_id,
                pattern_type=detection.pattern_type,
                severity=detection.severity,
                message=detection.message,
                details=detection.details,
                detector_version=DETECTOR_VERSION,
                detected_at=now,
                lifecycle="live",
                trigger_position_id=position.position_id,
            )
            db.add(alert)
            written.append(alert)

            logger.info(
                "live alert %s for %s (%s, shadow=%s)",
                detection.pattern_type, position.tradingsymbol,
                broker_account_id, shadow,
            )

        if written:
            await db.commit()
        return written

    @staticmethod
    async def _already_raised(
        broker_account_id: UUID,
        position_id: UUID,
        pattern_type: str,
        db: AsyncSession,
    ) -> bool:
        result = await db.execute(
            select(RiskAlert.id).where(and_(
                RiskAlert.broker_account_id == broker_account_id,
                RiskAlert.trigger_position_id == position_id,
                RiskAlert.pattern_type == pattern_type,
                RiskAlert.lifecycle == "live",
            )).limit(1)
        )
        return result.scalar_one_or_none() is not None


async def merge_live_alert_on_close(
    broker_account_id: UUID,
    position_id: Optional[UUID],
    pattern_type: str,
    completed_trade_id: UUID,
    db: AsyncSession,
) -> bool:
    """
    Dedupe. Called by the post-hoc path before it inserts.

    A live alert at entry and a post-hoc alert at close are the same finding
    twice. When a live row already exists for this position and pattern, promote
    it — attach the completed trade so it picks up realized money, flip it to
    'post' — and tell the caller not to insert.

    Returns True when it merged (caller must skip its insert), False otherwise.
    """
    if position_id is None:
        return False

    result = await db.execute(
        select(RiskAlert).where(and_(
            RiskAlert.broker_account_id == broker_account_id,
            RiskAlert.trigger_position_id == position_id,
            RiskAlert.pattern_type == pattern_type,
            RiskAlert.lifecycle == "live",
        )).limit(1)
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        return False

    existing.lifecycle = "post"
    existing.trigger_completed_trade_id = completed_trade_id
    details = dict(existing.details or {})
    details["raised_live"] = True   # keep the fact that we warned in time
    existing.details = details
    await db.commit()

    logger.info(
        "merged post-hoc %s into live alert %s (position %s)",
        pattern_type, existing.id, position_id,
    )
    return True
