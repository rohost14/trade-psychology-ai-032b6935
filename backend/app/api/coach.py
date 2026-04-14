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
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pydantic import BaseModel
from typing import List, Optional
import json as _json
import asyncio

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
    analysis_type: Optional[str] = "fast"  # "fast" (Haiku) or "deep" (Sonnet)


class ChatResponse(BaseModel):
    response: str
    timestamp: str


class SaveInsightRequest(BaseModel):
    content: str


async def _build_trading_context(
    broker_account_id: UUID,
    db: AsyncSession
) -> tuple[str, Optional["UserProfile"]]:
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

    # Section E: Today's session summary — gives AI the numbers to do erosion math
    today_start_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = today_start_ist.astimezone(timezone.utc)
    today_closed = [p for p in positions if p.last_exit_time and p.last_exit_time >= today_start_utc]
    if today_closed:
        # Sort by exit time ascending to compute running P&L and find peak
        today_sorted = sorted(today_closed, key=lambda p: p.last_exit_time)
        running = 0.0
        peak = 0.0
        running_series = []
        for p in today_sorted:
            pnl = float(p.realized_pnl or p.pnl or 0)
            running += pnl
            if running > peak:
                peak = running
            running_series.append((p.tradingsymbol, pnl, running))

        final = running
        erosion = peak - final
        erosion_pct = (erosion / peak * 100) if peak > 0 else 0

        lines.append("**Today's Session (closed trades only, chronological):**")
        lines.append(f"- Peak P&L reached: ₹{peak:+,.2f}")
        lines.append(f"- Final P&L: ₹{final:+,.2f}")
        if erosion > 0:
            lines.append(f"- Gave back: ₹{erosion:,.2f} ({erosion_pct:.0f}% of peak gains)")
        lines.append("- Trade sequence:")
        for sym, pnl, cum in running_series:
            sign = "+" if pnl >= 0 else ""
            cum_sign = "+" if cum >= 0 else ""
            lines.append(f"  • {sym}: ₹{sign}{pnl:,.2f} → running total ₹{cum_sign}{cum:,.2f}")
        lines.append("")

    # Section F: Behavioral alerts — linked to trade symbols where available
    if alerts:
        danger_alerts = [a for a in alerts if a.severity == "danger"]
        lines.append(f"**Behavioral Alerts (7 days): {len(alerts)} total, {len(danger_alerts)} danger**")
        # Show each alert with its trigger symbol so AI can link alert → trade
        for a in sorted(alerts, key=lambda x: x.detected_at, reverse=True)[:15]:
            date_str = _fmt_date(a.detected_at)
            sym = (a.details or {}).get("trigger_symbol", "") if a.details else ""
            sym_str = f" on {sym}" if sym else ""
            lines.append(
                f"- [{date_str}] {a.pattern_type.replace('_', ' ').title()} [{a.severity.upper()}]{sym_str}: {a.message}"
            )
        lines.append("")

    # Section G: Journal entries — structured fields for synthesis (not for quoting back)
    if journal_entries:
        lines.append(f"**Journal Entries (last 7 days, {len(journal_entries)} entries):**")
        lines.append("(Use these fields to UNDERSTAND the trader's mindset and decisions — do NOT quote them back verbatim)")
        for entry in journal_entries:
            date_str = _fmt_date(entry.created_at)
            sym = entry.trade_symbol or "General"
            pnl_str = f" | P&L: ₹{entry.trade_pnl:+,.2f}" if entry.trade_pnl else ""
            emotions = ", ".join(entry.emotion_tags or []) if entry.emotion_tags else "none tagged"

            # Build a structured signal summary — what this entry SIGNALS about the trader's state
            signals = []
            if entry.followed_plan is not None:
                signals.append(f"followed plan: {'YES' if entry.followed_plan else 'NO'}")
            if entry.deviation_reason:
                signals.append(f"deviated because: {entry.deviation_reason}")
            if entry.exit_reason:
                signals.append(f"exit reason: {entry.exit_reason}")
            if entry.setup_quality:
                signals.append(f"setup quality: {entry.setup_quality}/5")
            if entry.would_repeat is not None:
                signals.append(f"would repeat: {'YES' if entry.would_repeat else 'NO'}")
            if entry.market_condition:
                signals.append(f"market: {entry.market_condition}")

            parts = [f"- [{date_str}] {sym}{pnl_str} | Emotions: {emotions}"]
            if signals:
                parts.append(f"  Signals: {' | '.join(signals)}")
            if entry.notes:
                parts.append(f"  Raw note: \"{(entry.notes or '').strip()[:200]}\"")
            lines.extend(parts)
        lines.append("")

    return "\n".join(lines), profile


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


async def _build_chat_context(
    broker_account_id: UUID,
    db: AsyncSession,
    message: str,
) -> tuple[str, str, Optional[str]]:
    """
    Build full LLM context for a chat request.
    Returns (full_context, ai_persona, rag_context).
    Shared by both /chat and /chat/stream to avoid duplication.
    """
    from app.models.coach_session import CoachSession
    from sqlalchemy import desc

    trading_context, user_profile = await _build_trading_context(broker_account_id, db)
    ai_persona = user_profile.ai_persona if user_profile and user_profile.ai_persona else "coach"

    session_memory = ""
    try:
        mem_result = await db.execute(
            select(CoachSession)
            .where(
                CoachSession.broker_account_id == broker_account_id,
                CoachSession.summary != None,  # noqa: E711
            )
            .order_by(desc(CoachSession.started_at))
            .limit(3)
        )
        past_sessions = mem_result.scalars().all()
        if past_sessions:
            session_memory = "\n\nPrevious conversation context:\n" + "\n".join(
                f"- {s.summary}" for s in reversed(past_sessions)
            )
    except Exception:
        pass

    rag_context = None
    try:
        rag_context = await rag_service.get_chat_context(
            db=db,
            query=message,
            broker_account_id=broker_account_id,
            patterns_active=[],
        )
    except Exception:
        pass

    return trading_context + session_memory, ai_persona, rag_context


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
        from app.models.coach_session import CoachSession
        from sqlalchemy import desc

        full_context, ai_persona, rag_context = await _build_chat_context(
            broker_account_id, db, request.message
        )

        # Generate AI response
        response = await ai_service.generate_chat_response(
            user_message=request.message,
            trading_context=full_context,
            chat_history=[m.dict() for m in (request.history or [])],
            rag_context=rag_context or None,
            ai_persona=ai_persona,
            deep_mode=(request.analysis_type == "deep"),
        )

        # ── Save this exchange to the current session ──────────────────
        try:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)

            # Get or create today's session
            sess_result = await db.execute(
                select(CoachSession)
                .where(
                    CoachSession.broker_account_id == broker_account_id,
                    CoachSession.started_at >= today_start,
                )
                .order_by(desc(CoachSession.started_at))
                .limit(1)
            )
            current_session = sess_result.scalar_one_or_none()

            if not current_session:
                current_session = CoachSession(
                    broker_account_id=broker_account_id,
                    messages=[],
                )
                db.add(current_session)

            # Append this exchange
            msgs = list(current_session.messages or [])
            msgs.append({"role": "user", "content": request.message,
                         "ts": datetime.now(timezone.utc).isoformat()})
            msgs.append({"role": "assistant", "content": response,
                         "ts": datetime.now(timezone.utc).isoformat()})
            current_session.messages = msgs

            # Generate summary after 4+ exchanges (8 messages)
            if len(msgs) >= 8 and not current_session.summary:
                topics = set()
                for msg in msgs:
                    if msg["role"] == "user":
                        content = msg["content"][:100].lower()
                        if any(w in content for w in ["loss", "losing", "down"]):
                            topics.add("losses")
                        if any(w in content for w in ["trade", "position", "entry"]):
                            topics.add("trades")
                        if any(w in content for w in ["pattern", "behavior", "habit"]):
                            topics.add("patterns")
                current_session.summary = (
                    f"Session discussed: {', '.join(topics) or 'general trading topics'}. "
                    f"{len(msgs)//2} exchanges."
                )

            await db.commit()
        except Exception as sess_err:
            logger.debug(f"Session save skipped (non-critical): {sess_err}")

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


async def _save_chat_session_bg(
    broker_account_id_str: str,
    user_message: str,
    assistant_message: str,
) -> None:
    """Save a streaming chat exchange to CoachSession using a fresh DB session."""
    from app.core.database import SessionLocal
    from app.models.coach_session import CoachSession
    from sqlalchemy import desc

    try:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        bid = UUID(broker_account_id_str)

        async with SessionLocal() as db:
            sess_result = await db.execute(
                select(CoachSession)
                .where(
                    CoachSession.broker_account_id == bid,
                    CoachSession.started_at >= today_start,
                )
                .order_by(desc(CoachSession.started_at))
                .limit(1)
            )
            current_session = sess_result.scalar_one_or_none()

            if not current_session:
                current_session = CoachSession(broker_account_id=bid, messages=[])
                db.add(current_session)

            msgs = list(current_session.messages or [])
            now_ts = datetime.now(timezone.utc).isoformat()
            msgs.append({"role": "user", "content": user_message, "ts": now_ts})
            msgs.append({"role": "assistant", "content": assistant_message, "ts": now_ts})
            current_session.messages = msgs

            if len(msgs) >= 8 and not current_session.summary:
                topics: set[str] = set()
                for msg in msgs:
                    if msg["role"] == "user":
                        text = msg["content"][:100].lower()
                        if any(w in text for w in ["loss", "losing", "down"]):
                            topics.add("losses")
                        if any(w in text for w in ["trade", "position", "entry"]):
                            topics.add("trades")
                        if any(w in text for w in ["pattern", "behavior", "habit"]):
                            topics.add("patterns")
                current_session.summary = (
                    f"Session discussed: {', '.join(topics) or 'general trading topics'}. "
                    f"{len(msgs) // 2} exchanges."
                )

            await db.commit()
    except Exception as e:
        logger.debug(f"Background session save failed (non-critical): {e}")


@router.get("/session/today")
async def get_today_session(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Return today's coach session messages and a live trading snapshot."""
    now_ist = datetime.now(IST)
    today_start_utc = now_ist.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)

    from app.models.coach_session import CoachSession
    from sqlalchemy import desc

    # Run all three queries in parallel — no data dependency between them
    sess_result, pos_result, alerts_result = await asyncio.gather(
        db.execute(
            select(CoachSession)
            .where(
                CoachSession.broker_account_id == broker_account_id,
                CoachSession.started_at >= today_start_utc,
            )
            .order_by(desc(CoachSession.started_at))
            .limit(1)
        ),
        db.execute(
            select(Position).where(
                Position.broker_account_id == broker_account_id,
                Position.last_exit_time >= today_start_utc,
                Position.status == "closed",
            )
        ),
        db.execute(
            select(RiskAlert).where(
                RiskAlert.broker_account_id == broker_account_id,
                RiskAlert.detected_at >= today_start_utc,
            )
        ),
    )

    session = sess_result.scalar_one_or_none()
    positions_today = list(pos_result.scalars().all())
    total_pnl = sum(float(p.realized_pnl or p.pnl or 0) for p in positions_today)
    alerts_today = list(alerts_result.scalars().all())
    active_alerts = len([a for a in alerts_today if getattr(a, "status", None) in (None, "active", "new")])

    recent_losses = [p for p in positions_today[-5:] if float(p.realized_pnl or p.pnl or 0) < 0]
    if len(positions_today) > 10 or len(recent_losses) >= 3:
        risk_state = "danger"
    elif len(positions_today) > 5 or len(recent_losses) >= 2:
        risk_state = "caution"
    else:
        risk_state = "safe"

    return {
        "messages": session.messages if session else [],
        "snapshot": {
            "trades_today": len(positions_today),
            "pnl_today": total_pnl,
            "active_alerts": active_alerts,
            "risk_state": risk_state,
        },
    }


@router.delete("/session/today", status_code=204)
async def clear_today_session(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Clear today's coach session so the frontend starts fresh."""
    from app.models.coach_session import CoachSession

    now_ist = datetime.now(IST)
    today_start_utc = now_ist.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)

    result = await db.execute(
        select(CoachSession).where(
            CoachSession.broker_account_id == broker_account_id,
            CoachSession.started_at >= today_start_utc,
        )
    )
    session = result.scalar_one_or_none()
    if session:
        await db.delete(session)
        await db.commit()


@router.post("/chat/stream")
async def chat_with_coach_stream(
    request: ChatRequest,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(coach_limiter),
):
    """
    SSE streaming version of /chat.
    Yields text/event-stream chunks. Client reads with fetch + ReadableStream.
    Session save runs as a background asyncio task after the stream completes.
    """
    try:
        full_context, ai_persona, rag_context = await _build_chat_context(
            broker_account_id, db, request.message
        )
        history = [m.dict() for m in (request.history or [])]
        collected: list[str] = []

        async def generate():
            async for chunk in ai_service.generate_chat_response_stream(
                user_message=request.message,
                trading_context=full_context,
                chat_history=history,
                rag_context=rag_context,
                ai_persona=ai_persona,
                deep_mode=(request.analysis_type == "deep"),
            ):
                collected.append(chunk)
                yield f"data: {_json.dumps({'text': chunk})}\n\n"

            yield "data: [DONE]\n\n"

            asyncio.create_task(
                _save_chat_session_bg(
                    str(broker_account_id),
                    request.message,
                    "".join(collected),
                )
            )

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    except Exception as e:
        logger.error(f"Streaming chat error: {e}", exc_info=True)

        async def error_stream():
            msg = "I'm having trouble right now. Please try again."
            yield f"data: {_json.dumps({'text': msg})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(error_stream(), media_type="text/event-stream")


@router.post("/save-insight")
async def save_insight_to_journal(
    request: SaveInsightRequest,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Save an AI coach message as a daily journal entry."""
    try:
        entry = JournalEntry(
            broker_account_id=broker_account_id,
            notes=request.content,
            lessons=f"Saved from AI Coach — {datetime.now(IST).strftime('%d %b %H:%M IST')}",
            entry_type="daily",
            emotion_tags=[],
        )
        db.add(entry)
        await db.commit()
        return {"success": True, "id": str(entry.id)}
    except Exception as e:
        logger.error(f"Failed to save insight to journal: {e}")
        return {"success": False}
