"""
Session facts — one definition each, computed in one place.

WHY THIS EXISTS

"How many losses in a row is this trader on?" had four answers in this codebase,
and they disagreed by design rather than by accident:

  * `behavior_engine`            — within today's session, over CompletedTrades
  * `danger_zone_service`        — the last 10 CompletedTrades, ACROSS DAYS
  * `pattern_prediction_service` — today's raw `Trade` fills
  * `pnl_calculator._build_feature` — every prior round-trip, across days

None was wrong by its own definition. That is the problem: the definition was
never chosen, it was written four times. A trader who lost three trades on Friday
and one on Monday morning was simultaneously on a streak of 1 (engine, silent),
4 (danger zone, which starts a cooldown and sends a WhatsApp message) and 4
(their personal record page).

This module is the single definition. Everything that needs a session fact calls
it, and nothing computes its own.

THE DEFINITIONS

*Unit* — a **CompletedTrade**, one full round-trip. Never a raw fill. A position
exited in three tranches is one trade, not three, and summing `Trade.pnl` gives a
different number from summing `CompletedTrade.realized_pnl` because the former is
a compatibility value written onto closing fills.

*Scope* — one **session**. A CompletedTrade belongs to the session it CLOSED in,
bounded below by that day's market open (`get_session_boundaries`, FNO). Streaks,
P&L, peak and drawdown all reset at the open.

Session scope is a behavioural claim, not a convenience: tilt is a state a trader
is in *right now*, and it does not survive a night's sleep and a new open.
Counting Friday's losses into Monday's streak imposes a cooldown for something
that is already over.

*consecutive_losses* — count back from the most recent close while
`realized_pnl < 0`. A flat trade (exactly zero) BREAKS the streak: it is not a
loss. Wins break it too.

*pnl* — sum of `realized_pnl`. RAW: no brokerage, STT or tax, ever.

*peak_pnl* — the highest the running cumulative reached, floored at zero. A
session that never went green has a peak of zero, not a negative "peak".

*drawdown_from_peak* — `peak - current`, never negative. This is the drawdown
the trader ENDED on.

*max_drawdown* — the deepest peak-to-trough reached at any point in the session.
A trader who fell twenty thousand and clawed it all back ends with a
`drawdown_from_peak` of zero and a `max_drawdown` of twenty thousand. Baselines
want the second; a live "you are giving it back" alert wants the first. Two
facts, two names, both defined here rather than one of them being recomputed
inline wherever it is needed.

*longest_loss_run* — the longest losing run anywhere in the session, as against
`consecutive_losses`, which is the run still going at the end.

WHAT IS DELIBERATELY NOT HERE

Order-velocity counts ("how many orders in the last 30 minutes") are a different
fact measured in a different unit — raw `Trade` rows — and burst detection wants
exactly that. `danger_zone_service` keeps its own windowed count and is right to.
The rule is one definition per fact, not one unit for every question.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Iterable, List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.completed_trade import CompletedTrade

_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class SessionFacts:
    """
    What happened in one session, as of one moment.

    Every field derives from the same ordered list of CompletedTrades, so they
    cannot contradict each other — which two separately-computed fields
    routinely did.
    """

    trades: int
    pnl: Decimal
    consecutive_losses: int
    consecutive_wins: int
    peak_pnl: Decimal
    drawdown_from_peak: Decimal
    #: The deepest peak-to-trough within the session, which is NOT the same as
    #: drawdown_from_peak: a trader who fell 20k and recovered ends the day at a
    #: drawdown of zero and a max_drawdown of 20k. Baselines want this one.
    max_drawdown: Decimal
    #: The longest losing run anywhere in the session, as against
    #: consecutive_losses, which is the run still in progress at the end.
    longest_loss_run: int
    winners: int
    losers: int
    last_trade_pnl: Optional[Decimal]
    last_exit_time: Optional[datetime]

    @property
    def is_empty(self) -> bool:
        return self.trades == 0


EMPTY = SessionFacts(
    trades=0,
    pnl=Decimal("0"),
    consecutive_losses=0,
    consecutive_wins=0,
    peak_pnl=Decimal("0"),
    drawdown_from_peak=Decimal("0"),
    max_drawdown=Decimal("0"),
    longest_loss_run=0,
    winners=0,
    losers=0,
    last_trade_pnl=None,
    last_exit_time=None,
)


def _pnl(t: CompletedTrade) -> Decimal:
    return Decimal(str(t.realized_pnl or 0))


def in_exit_order(trades: Iterable[CompletedTrade]) -> List[CompletedTrade]:
    """
    Chronological by close.

    Callers assemble trades from more than one place — a query ordered ascending,
    plus the trade being analysed appended at the end. That is usually already in
    order and silently is not during a replay, where a trade can be processed
    after one that closed later. Ordering here rather than trusting the caller is
    what makes the streak deterministic.
    """
    return sorted(trades, key=lambda t: t.exit_time or _EPOCH)


def derive(trades: Iterable[CompletedTrade]) -> SessionFacts:
    """
    The session's facts from its completed trades. Pure; no IO, no clock.

    Order-independent by construction, because it sorts first. Idempotent, so a
    replay or a retried task recomputes the same answer rather than accumulating.
    """
    ordered = in_exit_order(trades)
    if not ordered:
        return EMPTY

    running = Decimal("0")
    peak = Decimal("0")
    max_dd = Decimal("0")
    run = longest_run = 0
    winners = losers = 0
    for t in ordered:
        p = _pnl(t)
        running += p
        if running > peak:
            peak = running
        if peak - running > max_dd:
            max_dd = peak - running
        if p > 0:
            winners += 1
        elif p < 0:
            losers += 1
        if p < 0:
            run += 1
            longest_run = max(longest_run, run)
        else:
            run = 0

    consecutive_losses = 0
    for t in reversed(ordered):
        if _pnl(t) < 0:
            consecutive_losses += 1
        else:
            break

    consecutive_wins = 0
    for t in reversed(ordered):
        if _pnl(t) > 0:
            consecutive_wins += 1
        else:
            break

    last = ordered[-1]
    return SessionFacts(
        trades=len(ordered),
        pnl=running,
        consecutive_losses=consecutive_losses,
        consecutive_wins=consecutive_wins,
        peak_pnl=peak,
        drawdown_from_peak=max(Decimal("0"), peak - running),
        max_drawdown=max_dd,
        longest_loss_run=longest_run,
        winners=winners,
        losers=losers,
        last_trade_pnl=_pnl(last),
        last_exit_time=last.exit_time,
    )


def as_of(trades: Iterable[CompletedTrade], moment: datetime) -> SessionFacts:
    """
    The same facts as they stood at `moment` — trades that had already CLOSED.

    This is what a per-trade feature row needs: "what state was this trader in
    when they entered". Same definitions, earlier cutoff, so a stored feature and
    a live alert cannot disagree about what a streak is.
    """
    return derive(t for t in trades if t.exit_time and t.exit_time < moment)


def session_start(session_date: date) -> datetime:
    """
    The lower bound of a session, in UTC.

    Market open, not IST midnight. The two differ only by the pre-open hours,
    which hold no F&O trades today — but "today's trades" and "this session's
    trades" are different claims, and only one of them survives a product that
    later handles overnight positions or another exchange's hours.
    """
    from app.core.market_hours import MarketSegment, get_session_boundaries

    open_utc, _ = get_session_boundaries(
        segment=MarketSegment.FNO, for_date=session_date
    )
    return open_utc


def session_date_now() -> date:
    """Today, in the market's timezone. One place, so callers stop re-deriving it."""
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


async def load_session_trades(
    db: AsyncSession,
    broker_account_id: UUID,
    session_date: date,
    *,
    exclude_id=None,
    as_of: Optional[datetime] = None,
) -> List[CompletedTrade]:
    """
    This session's completed trades, oldest close first.

    `exclude_id` exists for the engine, which holds the trade being analysed
    separately and must not load it twice.

    `as_of` IS THE TEMPORAL BOUNDARY, and it exists because there was not one.
    ─────────────────────────────────────────────────────────────────────────
    Without it this query returns EVERY completed trade of the day, in both
    directions from the caller's position in the session.

    On the live postback path that is harmless: the engine runs when a trade
    closes, and a trade that has not closed yet has no CompletedTrade row, so
    the bound was implicit in the data. On the BULK path
    (`run_behavior_engine_full_session`, used when trades arrive by REST sync
    because the trader was not in the app) every row of the day already
    exists — so analysing trade 3 of 10 handed the detectors trades 4 to 10.

    Measured on the 175-session reference book: **1,808 of the 3,616 entries
    the detectors were given had not happened yet — 50%**, touching 565 of 740
    trades, up to 13 future trades on a single one. The divergence is not
    theoretical either; the same session produced 248 `overtrading_burst`
    firings through the bulk path against 13 through the live one.

    So pass `as_of=<the trade's exit_time>` when reconstructing what was known
    at a moment. Callers that legitimately want the whole day — the coach, the
    constitution screen, `load_facts`, early warning — pass nothing and are
    unaffected.

    NOT bounded by entry time. A trade entered after this one but closed before
    it HAS happened by the time the engine fires, and for counting detectors it
    is plainly one of today's trades. Detectors that instead use a prior's
    OUTCOME to describe a DECISION must compare against `ct.entry_time`
    themselves, and `revenge_trade`, `constitution_violation`'s cooldown rule
    and `fomo_entry` already do. Applying an entry bound here instead was
    measured and rejected: it changes live firing for four detectors
    (`overtrading_burst` 13 -> 2) and breaks count semantics.
    """
    conditions = [
        CompletedTrade.broker_account_id == broker_account_id,
        CompletedTrade.exit_time >= session_start(session_date),
    ]
    if as_of is not None:
        conditions.append(CompletedTrade.exit_time <= as_of)
    if exclude_id is not None:
        conditions.append(CompletedTrade.id != exclude_id)

    result = await db.execute(
        select(CompletedTrade)
        .where(and_(*conditions))
        .order_by(CompletedTrade.exit_time.asc())
    )
    return list(result.scalars().all())


async def load_facts(
    db: AsyncSession,
    broker_account_id: UUID,
    session_date: Optional[date] = None,
) -> SessionFacts:
    """
    A session's facts, straight from the database. Defaults to today.

    The entry point for callers outside the engine — danger zone, prediction,
    anything answering "where is this trader right now". Each used to write its
    own query, which is how each got its own answer.
    """
    if session_date is None:
        session_date = session_date_now()
    return derive(await load_session_trades(db, broker_account_id, session_date))
