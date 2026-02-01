from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from typing import List, Optional

from app.core.database import get_db
from app.services.ai_service import ai_service
from app.models.trade import Trade
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str


class ChatRequest(BaseModel):
    message: str
    broker_account_id: UUID
    history: Optional[List[ChatMessage]] = []


class ChatResponse(BaseModel):
    response: str
    timestamp: str

@router.get("/insight")
async def get_coach_insight(
    broker_account_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate AI-powered coach insight based on current trading state.
    Updates every time user refreshes dashboard.
    """
    
    try:
        # Get today's data
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        result = await db.execute(
            select(Trade).where(
                Trade.broker_account_id == broker_account_id,
                Trade.order_timestamp >= today_start,
                Trade.status == 'COMPLETE'
            )
        )
        trades_today = result.scalars().all()
        
        # Calculate today's P&L
        total_pnl = sum(float(t.pnl or 0) for t in trades_today)
        
        # Determine risk state (simplified - could be more sophisticated)
        recent_losses = [t for t in trades_today[-5:] if float(t.pnl or 0) < 0]
        
        if len(trades_today) > 10 or len(recent_losses) >= 3:
            risk_state = 'danger'
        elif len(trades_today) > 5 or len(recent_losses) >= 2:
            risk_state = 'caution'
        else:
            risk_state = 'safe'
        
        # Get current time context
        current_hour = datetime.now(timezone.utc).hour
        if 9 <= current_hour < 12:
            time_of_day = "Morning session"
        elif 12 <= current_hour < 15:
            time_of_day = "Afternoon session"
        else:
            time_of_day = "Post-market"
        
        # 🤖 AI CALL - Generate contextual insight
        insight = await ai_service.generate_coach_insight(
            risk_state=risk_state,
            total_pnl=total_pnl,
            patterns_active=[],  # Could add quick pattern check here
            recent_trades=len(trades_today),
            time_of_day=time_of_day
        )
        
        return {
            "insight": insight,
            "risk_state": risk_state,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        logger.error(f"Failed to generate coach insight: {e}", exc_info=True)
        return {
            "insight": "Focus on discipline. Trade with a clear plan.",
            "risk_state": "safe",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.post("/chat", response_model=ChatResponse)
async def chat_with_coach(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Chat with AI trading coach. Provides personalized advice based on trading data.
    """
    try:
        # Get trader's context from database
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)

        # Today's trades
        today_result = await db.execute(
            select(Trade).where(
                Trade.broker_account_id == request.broker_account_id,
                Trade.order_timestamp >= today_start,
                Trade.status == 'COMPLETE'
            )
        )
        trades_today = today_result.scalars().all()

        # Week's trades for patterns
        week_result = await db.execute(
            select(Trade).where(
                Trade.broker_account_id == request.broker_account_id,
                Trade.order_timestamp >= week_start,
                Trade.status == 'COMPLETE'
            )
        )
        trades_week = week_result.scalars().all()

        # Calculate stats
        total_pnl_today = sum(float(t.pnl or 0) for t in trades_today)
        total_pnl_week = sum(float(t.pnl or 0) for t in trades_week)
        winners_week = [t for t in trades_week if float(t.pnl or 0) > 0]
        win_rate = (len(winners_week) / len(trades_week) * 100) if trades_week else 0

        # Build trading context for AI
        trading_context = f"""
**Trader's Current Data:**
- Today's P&L: ₹{total_pnl_today:.2f}
- Today's trades: {len(trades_today)}
- This week's P&L: ₹{total_pnl_week:.2f}
- This week's trades: {len(trades_week)}
- Win rate (7 days): {win_rate:.1f}%
"""

        # Add recent trade info if available
        if trades_today:
            last_trade = trades_today[-1]
            trading_context += f"""
**Last Trade:**
- Symbol: {last_trade.tradingsymbol}
- Type: {last_trade.transaction_type}
- P&L: ₹{float(last_trade.pnl or 0):.2f}
"""

        # Generate AI response
        response = await ai_service.generate_chat_response(
            user_message=request.message,
            trading_context=trading_context,
            chat_history=request.history or []
        )

        return ChatResponse(
            response=response,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return ChatResponse(
            response="I'm having trouble analyzing your data right now. Try asking about your trading patterns or recent performance.",
            timestamp=datetime.now(timezone.utc).isoformat()
        )
