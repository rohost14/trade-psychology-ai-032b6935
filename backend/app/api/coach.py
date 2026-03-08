"""
AI Coach API Endpoints

Chat with AI trading coach powered by user's actual trading data.

Key improvements:
- Uses POSITIONS (not raw orders) → correct trade count and P&L
- Fetches LAST 7 DAYS positions with full detail (symbol, P&L, IST time, duration)
- Fetches journal entries DIRECTLY from DB (no embedding dependency)
- Provides rich per-trade context so AI can answer "what was my last trade", "how much on BDL", etc.
- Hourly + symbol performance analysis for 7-day window questions
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pydantic import BaseModel
from typing import List, Optional

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
from app.services.ai_service import ai_service
from app.services.rag_service import rag_service
from app.models.position import Position
from app.models.risk_alert import RiskAlert
from app.models.user_profile import UserProfile
from app.models.journal_entry import JournalEntry
from app.core.rate_limiter import coach_limiter
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


def _ist(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)


def _fmt(dt: Optional[datetime]) -> str:
    ist_dt = _ist(dt)
    return ist_dt.strftime("%d %b %Y %H:%M IST") if ist_dt else "Unknown time"


def _fmt_date(dt: Optional[datetime]) -> str:
    ist_dt = _ist(dt)
    return ist_dt.strftime("%d %b %Y") if ist_dt else "Unknown date"


class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []


class ChatResponse(BaseModel):
    response: str
    timestamp: str


async def _build_trading_context(
    broker_account_id: UUID,
    db: AsyncSession
) -> str:
    """
    Build rich trading context for LLM from the last 7 days of CLOSED positions
    and journal entries. This is what the AI uses to answer questions like:
    - "What was my last trade?"
    - "How much did I lose on BDL?"
    - "What's my worst time of day?"
    - "Give me analysis of last 7 days"
    """
    now_ist = datetime.now(IST)
    seven_days_ago_utc = (now_ist - timedelta(days=7)).astimezone(timezone.utc)

    # ── 1. Fetch last 7 days of CLOSED positions (not raw orders) ──
    pos_result = await db.execute(
        select(Position)
        .where(
            Position.broker_account_id == broker_account_id,
            Position.status == "closed",
            Position.last_exit_time >= seven_days_ago_utc
        )
        .order_by(Position.last_exit_time.desc())
        .limit(50)
    )
    positions: List[Position] = list(pos_result.scalars().all())

    # ── 2. Also fetch open positions (still in trade) ──
    open_result = await db.execute(
        select(Position)
        .where(
            Position.broker_account_id == broker_account_id,
            Position.status == "open"
        )
        .order_by(Position.first_entry_time.desc())
        .limit(5)
    )
    open_positions: List[Position] = list(open_result.scalars().all())

    # ── 3. Fetch alerts from last 7 days ──
    alerts_result = await db.execute(
        select(RiskAlert)
        .where(
            RiskAlert.broker_account_id == broker_account_id,
            RiskAlert.detected_at >= seven_days_ago_utc
        )
        .order_by(RiskAlert.detected_at.desc())
        .limit(20)
    )
    alerts = list(alerts_result.scalars().all())

    # ── 4. Fetch journal entries directly from DB (no embeddings needed) ──
    journal_result = await db.execute(
        select(JournalEntry)
        .where(
            JournalEntry.broker_account_id == broker_account_id,
            JournalEntry.created_at >= seven_days_ago_utc
        )
        .order_by(JournalEntry.created_at.desc())
        .limit(10)
    )
    journal_entries = list(journal_result.scalars().all())

    # ── 5. Fetch user profile ──
    profile_result = await db.execute(
        select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
    )
    profile = profile_result.scalar_one_or_none()

    # ─────────── Build context string ───────────

    lines = []

    # Section A: Current moment
    lines.append(f"**Current Time:** {now_ist.strftime('%d %b %Y, %H:%M IST')} ({now_ist.strftime('%A')})")
    lines.append(f"**Market Status:** {'Open' if (9*60+15) <= (now_ist.hour*60 + now_ist.minute) <= (15*60+30) else 'Closed'}")
    lines.append("")

    # Section B: Trader profile
    if profile:
        lines.append("**Trader Profile:**")
        lines.append(f"- Experience: {profile.experience_level or 'Unknown'}, Style: {profile.trading_style or 'Unknown'}")
        lines.append(f"- Risk Tolerance: {profile.risk_tolerance or 'Unknown'}")
        lines.append(f"- Known Weaknesses: {', '.join(profile.known_weaknesses or []) or 'None reported'}")
        if profile.daily_loss_limit:
            lines.append(f"- Daily loss limit: ₹{profile.daily_loss_limit:,.0f}")
        if profile.daily_trade_limit:
            lines.append(f"- Daily trade limit: {profile.daily_trade_limit}")
        lines.append("")

    # Section C: OPEN POSITIONS (active trades right now)
    if open_positions:
        lines.append(f"**Currently Open Positions ({len(open_positions)}):**")
        for p in open_positions:
            unrealized = float(p.unrealized_pnl or p.pnl or 0)
            entry_time = _fmt(p.first_entry_time)
            pnl_sign = "+" if unrealized >= 0 else ""
            lines.append(
                f"- {p.tradingsymbol}: entered {entry_time}, "
                f"unrealized P&L ₹{pnl_sign}{unrealized:,.2f}"
            )
        lines.append("")

    # Section D: RECENT CLOSED POSITIONS (last 7 days, detailed)
    if positions:
        total_pnl = sum(float(p.realized_pnl or p.pnl or 0) for p in positions)
        winners = [p for p in positions if float(p.realized_pnl or p.pnl or 0) > 0]
        losers = [p for p in positions if float(p.realized_pnl or p.pnl or 0) < 0]
        win_rate = round(len(winners) / len(positions) * 100, 1) if positions else 0

        lines.append(f"**Last 7 Days: {len(positions)} Closed Positions**")
        lines.append(f"- Net P&L: ₹{total_pnl:+,.2f}")
        lines.append(f"- Win Rate: {win_rate}% ({len(winners)} wins, {len(losers)} losses)")
        lines.append("")

        # Most recent 5 positions — full detail so AI can answer "what was my last trade"
        lines.append("**Most Recent Closed Positions (newest first):**")
        for i, p in enumerate(positions[:8]):
            pnl = float(p.realized_pnl or p.pnl or 0)
            duration = f"{p.holding_duration_minutes}min" if p.holding_duration_minutes else "unknown duration"
            exit_time = _fmt(p.last_exit_time)
            entry_time = _fmt(p.first_entry_time)
            pnl_sign = "+" if pnl >= 0 else ""
            outcome = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "FLAT")
            lines.append(
                f"{i+1}. {p.tradingsymbol} [{outcome}] ₹{pnl_sign}{pnl:,.2f} | "
                f"Entry: {entry_time} → Exit: {exit_time} | "
                f"Held: {duration}"
            )
        lines.append("")

        # Symbol-level performance (all 7 days)
        symbol_pnl: dict[str, dict] = {}
        for p in positions:
            sym = p.tradingsymbol or "Unknown"
            pnl = float(p.realized_pnl or p.pnl or 0)
            if sym not in symbol_pnl:
                symbol_pnl[sym] = {"total": 0.0, "count": 0, "wins": 0}
            symbol_pnl[sym]["total"] += pnl
            symbol_pnl[sym]["count"] += 1
            if pnl > 0:
                symbol_pnl[sym]["wins"] += 1

        if len(symbol_pnl) > 1:
            lines.append("**Symbol P&L (7 days):**")
            for sym, data in sorted(symbol_pnl.items(), key=lambda x: x[1]["total"]):
                wr = round(data["wins"] / data["count"] * 100)
                sign = "+" if data["total"] >= 0 else ""
                lines.append(f"- {sym}: ₹{sign}{data['total']:,.2f} ({data['count']} trades, {wr}% win rate)")
            lines.append("")

        # Time-of-day performance (IST hours)
        pnl_by_hour: dict[int, list] = {}
        for p in positions:
            ist_dt = _ist(p.first_entry_time)
            if ist_dt:
                h = ist_dt.hour
                pnl = float(p.realized_pnl or p.pnl or 0)
                pnl_by_hour.setdefault(h, []).append(pnl)

        if pnl_by_hour:
            lines.append("**Hourly Performance (IST, 7 days):**")
            for h in sorted(pnl_by_hour.keys()):
                pnls_h = pnl_by_hour[h]
                total_h = sum(pnls_h)
                wrs_h = round(sum(1 for x in pnls_h if x > 0) / len(pnls_h) * 100)
                avg_h = round(total_h / len(pnls_h), 2)
                sign = "+" if total_h >= 0 else ""
                lines.append(
                    f"- {h:02d}:00–{h:02d}:59 IST: {len(pnls_h)} trades, "
                    f"net ₹{sign}{total_h:,.2f}, avg ₹{avg_h:+,.2f}, {wrs_h}% win rate"
                )
            lines.append("")

        # Average hold time by outcome
        win_durations = [p.holding_duration_minutes for p in winners if p.holding_duration_minutes]
        loss_durations = [p.holding_duration_minutes for p in losers if p.holding_duration_minutes]
        if win_durations or loss_durations:
            lines.append("**Avg Hold Time by Outcome:**")
            if win_durations:
                lines.append(f"- Winning trades: avg {round(sum(win_durations)/len(win_durations))} min")
            if loss_durations:
                lines.append(f"- Losing trades: avg {round(sum(loss_durations)/len(loss_durations))} min")
            lines.append("")

    else:
        lines.append("**Closed Positions (7 days): None found.**")
        lines.append("(Either no trades have been made, or positions haven't been synced yet.)")
        lines.append("")

    # Section E: Behavioral alerts (7 days)
    if alerts:
        danger_alerts = [a for a in alerts if a.severity == "danger"]
        pattern_counts: dict[str, int] = {}
        for a in alerts:
            pattern_counts[a.pattern_type] = pattern_counts.get(a.pattern_type, 0) + 1

        lines.append(f"**Behavioral Alerts (7 days): {len(alerts)} total, {len(danger_alerts)} danger**")
        for pattern, count in sorted(pattern_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- {pattern.replace('_', ' ').title()}: {count} occurrences")
        lines.append("")

    # Section F: Journal entries (direct from DB — no embedding needed)
    if journal_entries:
        lines.append(f"**Journal Entries (last 7 days, {len(journal_entries)} entries):**")
        for entry in journal_entries:
            date_str = _fmt_date(entry.created_at)
            sym = entry.trade_symbol or "General"
            pnl_str = f" | P&L: ₹{entry.trade_pnl}" if entry.trade_pnl else ""
            emotions = ", ".join(entry.emotion_tags or []) if entry.emotion_tags else ""
            notes_preview = (entry.notes or "")[:250]
            lessons_preview = (entry.lessons or "")[:150]
            lines.append(f"- [{date_str}] {sym}{pnl_str} | Emotions: {emotions or 'not tagged'}")
            if notes_preview:
                lines.append(f"  Notes: {notes_preview}")
            if lessons_preview:
                lines.append(f"  Lessons: {lessons_preview}")
        lines.append("")

    return "\n".join(lines)


# Cache TTL for coach insight: 15 minutes
_COACH_INSIGHT_TTL_MINUTES = 15


@router.get("/insight")
async def get_coach_insight(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Return AI coach insight for the current trading session.

    Non-blocking: checks DB cache first (15-min TTL). On cache miss,
    returns a fallback immediately and fires a Celery task to generate
    the real LLM insight in the background. The next request (frontend
    polls once after 5s) will get the cached LLM response.
    """
    try:
        now_ist = datetime.now(IST)
        today_start_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_utc = today_start_ist.astimezone(timezone.utc)

        # ----------------------------------------------------------------
        # 1. Check cache (UserProfile.ai_cache["coach_insight"])
        # ----------------------------------------------------------------
        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
        )
        user_profile = profile_result.scalar_one_or_none()

        if user_profile and user_profile.ai_cache:
            cached = user_profile.ai_cache.get("coach_insight")
            if cached:
                try:
                    generated_at = datetime.fromisoformat(cached["generated_at"])
                    age_minutes = (datetime.now(timezone.utc) - generated_at).total_seconds() / 60
                    if age_minutes < _COACH_INSIGHT_TTL_MINUTES:
                        return {
                            "insight": cached["insight"],
                            "risk_state": cached.get("risk_state", "safe"),
                            "timestamp": cached["generated_at"],
                            "cached": True,
                        }
                except Exception:
                    pass  # Bad cache entry — fall through to generate

        # ----------------------------------------------------------------
        # 2. Build context (fast DB queries, no LLM)
        # ----------------------------------------------------------------
        pos_result = await db.execute(
            select(Position).where(
                Position.broker_account_id == broker_account_id,
                Position.last_exit_time >= today_start_utc,
                Position.status == "closed"
            )
        )
        positions_today = list(pos_result.scalars().all())
        total_pnl = sum(float(p.realized_pnl or p.pnl or 0) for p in positions_today)
        recent_losses = [p for p in positions_today[-5:] if float(p.realized_pnl or p.pnl or 0) < 0]

        patterns_active = []
        try:
            alerts_result = await db.execute(
                select(RiskAlert).where(
                    RiskAlert.broker_account_id == broker_account_id,
                    RiskAlert.detected_at >= today_start_utc
                )
            )
            patterns_active = list(set(
                a.pattern_type for a in alerts_result.scalars().all() if a.pattern_type
            ))
        except Exception:
            pass

        if len(positions_today) > 10 or len(recent_losses) >= 3:
            risk_state = "danger"
        elif len(positions_today) > 5 or len(recent_losses) >= 2:
            risk_state = "caution"
        else:
            risk_state = "safe"

        user_profile_context = ""
        if user_profile:
            user_profile_context = (
                f"\nTrader Profile: {user_profile.experience_level or 'Unknown'} level, "
                f"{user_profile.trading_style or 'Unknown'} style, "
                f"{user_profile.risk_tolerance or 'Unknown'} risk tolerance. "
                f"Known weaknesses: {', '.join(user_profile.known_weaknesses or []) or 'None reported'}."
            )

        now_min = now_ist.hour * 60 + now_ist.minute
        if 9 * 60 + 15 <= now_min < 12 * 60:
            time_of_day = "Morning session"
        elif 12 * 60 <= now_min <= 15 * 60 + 30:
            time_of_day = "Afternoon session"
        else:
            time_of_day = "Post-market"

        context = {
            "risk_state": risk_state,
            "total_pnl": total_pnl,
            "patterns_active": patterns_active,
            "recent_trades": len(positions_today),
            "time_of_day": time_of_day,
            "user_profile_context": user_profile_context,
        }

        # ----------------------------------------------------------------
        # 3. Queue LLM generation in background, return fallback immediately
        # ----------------------------------------------------------------
        from app.tasks.report_tasks import generate_coach_insight_task
        generate_coach_insight_task.delay(str(broker_account_id), context)

        fallback = _coach_fallback(risk_state, total_pnl)
        return {
            "insight": fallback,
            "risk_state": risk_state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "generating",  # Frontend polls once after 5s
        }

    except Exception as e:
        logger.error(f"Failed to generate coach insight: {e}", exc_info=True)
        return {
            "insight": "Focus on discipline. Trade with a clear plan.",
            "risk_state": "safe",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def _coach_fallback(risk_state: str, total_pnl: float) -> str:
    """Return a fast rule-based fallback while LLM generates in background."""
    if risk_state == "danger":
        return "High-risk session. Step back, review your trades before continuing."
    if risk_state == "caution":
        return "Caution zone. Reduce size, stick to your rules."
    if total_pnl > 0:
        return "Good session so far. Protect your gains — don't give them back."
    return "Focus on process, not P&L. One good trade at a time."


@router.post("/chat", response_model=ChatResponse)
async def chat_with_coach(
    request: ChatRequest,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(coach_limiter)
):
    """
    Chat with AI trading coach.
    Provides rich, data-aware responses using actual positions, journal entries,
    and behavioral patterns.
    """
    try:
        # Build rich trading context from positions + journal (7 days)
        trading_context = await _build_trading_context(broker_account_id, db)

        # Get user profile for persona
        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
        )
        user_profile = profile_result.scalar_one_or_none()
        ai_persona = user_profile.ai_persona if user_profile and user_profile.ai_persona else "coach"

        # Try RAG for semantic journal/KB search (optional enhancement, won't break if it fails)
        rag_context = None
        try:
            rag_context = await rag_service.get_chat_context(
                db=db,
                query=request.message,
                broker_account_id=broker_account_id,
                patterns_active=[]
            )
        except Exception as e:
            logger.debug(f"RAG context skipped (non-critical): {e}")

        # Generate AI response
        response = await ai_service.generate_chat_response(
            user_message=request.message,
            trading_context=trading_context,
            chat_history=[m.dict() for m in (request.history or [])],
            rag_context=rag_context or None,
            ai_persona=ai_persona
        )

        return ChatResponse(
            response=response,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return ChatResponse(
            response="I'm having trouble analyzing your data right now. Please try again in a moment.",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
