from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import logging

from app.core.database import get_db
from app.services.ai_service import ai_service
from app.services.whatsapp_service import whatsapp_service
from app.services.behavioral_analysis_service import BehavioralAnalysisService
from app.models.trade import Trade
from app.core.config import settings
from uuid import UUID

router = APIRouter()
logger = logging.getLogger(__name__)
behavioral_service = BehavioralAnalysisService()

@router.post("/whatsapp")
async def send_whatsapp_report(
    broker_account_id: UUID,
    period_days: int = 2,
    to_number: str = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate and send a WhatsApp report for the last N days.
    """
    try:
        # 1. Fetch trades
        cutoff = datetime.now() - timedelta(days=period_days)
        result = await db.execute(
            select(Trade).where(
                Trade.broker_account_id == broker_account_id,
                Trade.order_timestamp >= cutoff,
                Trade.status == "COMPLETE"
            ).order_by(Trade.order_timestamp)
        )
        trades = result.scalars().all()
        
        if not trades:
            return {"status": "skipped", "message": "No trades found in period"}

        # 2. Analyze Stats
        total_pnl = sum((t.pnl or 0) for t in trades)
        wins = [t for t in trades if (t.pnl or 0) > 0]
        losses = [t for t in trades if (t.pnl or 0) <= 0]
        
        trade_count = len(trades)
        win_rate = (len(wins) / trade_count * 100) if trade_count > 0 else 0
        
        best_trade = max((t.pnl or 0) for t in trades) if trades else 0
        worst_trade = min((t.pnl or 0) for t in trades) if trades else 0
        
        # 3. Analyze Behavior (Reuse existing service)
        # We reuse the full analysis logic but scoped to these trades if possible,
        # or just quick-detect. For accurate persona, we generally need more history,
        # but for "Active Patterns" in a 2-day report, we can run detection on just these trades
        # OR fetch the comprehensive analysis and filter.
        # Let's run detection on the specific set for immediate feedback.
        
        detected_patterns = []
        for pattern in behavioral_service.patterns:
            res = pattern.detect(trades)
            if res["detected"]:
                detected_patterns.append(pattern.name)
        
        # Quick strength/weakness heuristic for the report
        key_strength = "Discipline" if not any(p for p in detected_patterns if "Revenge" in p or "Overtrading" in p) else "Resilience"
        key_weakness = detected_patterns[0] if detected_patterns else "None"

        # 4. Generate AI Report
        report_content = await ai_service.generate_whatsapp_report(
            period_days=period_days,
            total_pnl=total_pnl,
            trade_count=trade_count,
            win_rate=win_rate,
            best_trade=best_trade,
            worst_trade=worst_trade,
            patterns_detected=detected_patterns,
            key_strength=key_strength,
            key_weakness=key_weakness
        )
        
        # 5. Send Message
        # Use provided number or fallback to config
        recipient = to_number or settings.TWILIO_WHATSAPP_FROM # Default to self/sender if not specified? 
        # Actually usually you send TO a user's number. 
        # For now, we'll assume we send TO the user. 
        # Since we don't store user phone yet, we'll default to the 'FROM' number simply for testing 
        # (assuming user sends to themselves in sandbox) or a placeholder.
        # Let's require to_number or log it.
        
        if not recipient:
             # Safety fallback for safe mode logging
             recipient = "+919999999999" 

        success = whatsapp_service.send_message(recipient, report_content)
        
        return {
            "status": "success" if success else "failed", 
            "recipient": recipient,
            "report_preview": report_content
        }

    except Exception as e:
        logger.error(f"Failed to generate WhatsApp report: {e}")
        raise HTTPException(status_code=500, detail=str(e))
