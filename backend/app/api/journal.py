"""
Trade Journal API Endpoints

CRUD operations for journal entries - traders' notes, emotions, and lessons.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from datetime import datetime, timezone
import logging

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
from app.models.journal_entry import JournalEntry
from app.models.trade import Trade
from app.models.completed_trade import CompletedTrade
from app.models.position import Position
from app.services.rag_service import rag_service

router = APIRouter()
logger = logging.getLogger(__name__)


def _apply_fields(entry: "JournalEntry", data) -> None:
    """Apply non-None fields from a create/update payload onto an entry row."""
    for field in (
        "emotion_tags", "followed_plan", "deviation_reason", "exit_reason",
        "setup_quality", "would_repeat", "market_condition", "notes",
    ):
        val = getattr(data, field, None)
        if val is not None:
            setattr(entry, field, val)


async def embed_journal_entry_async(db: AsyncSession, entry: JournalEntry):
    """Background task to embed a journal entry for RAG."""
    try:
        content_parts = []
        if entry.notes:
            content_parts.append(f"Notes: {entry.notes}")
        if entry.emotions:
            content_parts.append(f"Emotions: {entry.emotions}")
        if entry.lessons:
            content_parts.append(f"Lessons: {entry.lessons}")
        if entry.trade_symbol:
            content_parts.append(f"Symbol: {entry.trade_symbol}")
        if entry.trade_type:
            content_parts.append(f"Trade type: {entry.trade_type}")
        if entry.trade_pnl:
            content_parts.append(f"P&L: {entry.trade_pnl}")
        if entry.emotion_tags:
            content_parts.append(f"Emotion tags: {', '.join(entry.emotion_tags)}")

        content = "\n".join(content_parts)

        if content.strip():
            await rag_service.embed_journal_entry(
                db=db,
                broker_account_id=entry.broker_account_id,
                journal_entry_id=entry.id,
                content=content,
                entry_date=entry.created_at,
                mood=entry.emotions[:50] if entry.emotions else None,
                tags=entry.emotion_tags
            )
            logger.info(f"Embedded journal entry: {entry.id}")
    except Exception as e:
        logger.warning(f"Failed to embed journal entry {entry.id}: {e}")


# Request/Response Models
class JournalEntryCreate(BaseModel):
    trade_id: Optional[str] = None
    emotion_tags: Optional[List[str]] = None
    # Structured fields (migration 045)
    followed_plan: Optional[str] = None       # 'yes' | 'partially' | 'no'
    deviation_reason: Optional[str] = None    # 'fomo' | 'revenge' | 'overconfident' | 'bored' | 'impulse' | 'other'
    exit_reason: Optional[str] = None         # 'sl_hit' | 'target_hit' | 'trailed_stop' | 'manual' | 'panic' | 'news'
    setup_quality: Optional[int] = None       # 1–5
    would_repeat: Optional[str] = None        # 'yes' | 'maybe' | 'no'
    market_condition: Optional[str] = None    # 'trending' | 'ranging' | 'volatile' | 'choppy' | 'news_driven'
    notes: Optional[str] = None               # optional free text
    # Trade context
    trade_symbol: Optional[str] = None
    trade_type: Optional[str] = None
    trade_pnl: Optional[str] = None
    entry_type: str = "trade"


class JournalEntryUpdate(BaseModel):
    emotion_tags: Optional[List[str]] = None
    followed_plan: Optional[str] = None
    deviation_reason: Optional[str] = None
    exit_reason: Optional[str] = None
    setup_quality: Optional[int] = None
    would_repeat: Optional[str] = None
    market_condition: Optional[str] = None
    notes: Optional[str] = None


class JournalEntryResponse(BaseModel):
    id: str
    broker_account_id: str
    trade_id: Optional[str]
    emotion_tags: List[str]
    followed_plan: Optional[str]
    deviation_reason: Optional[str]
    exit_reason: Optional[str]
    setup_quality: Optional[int]
    would_repeat: Optional[str]
    market_condition: Optional[str]
    notes: Optional[str]
    trade_symbol: Optional[str]
    trade_type: Optional[str]
    trade_pnl: Optional[str]
    entry_type: str
    created_at: str
    updated_at: str


@router.get("/")
async def list_journal_entries(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    entry_type: Optional[str] = None,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """List all journal entries for an account."""
    try:
        query = select(JournalEntry).where(
            JournalEntry.broker_account_id == broker_account_id
        )

        if entry_type:
            query = query.where(JournalEntry.entry_type == entry_type)

        query = query.order_by(JournalEntry.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await db.execute(query)
        entries = result.scalars().all()

        return {
            "entries": [e.to_dict() for e in entries],
            "total": len(entries),
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error(f"Failed to list journal entries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/trade/{trade_id}")
async def get_journal_by_trade(
    trade_id: str,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Get journal entry for a specific trade."""
    try:
        t_id = UUID(trade_id)

        result = await db.execute(
            select(JournalEntry).where(
                JournalEntry.broker_account_id == broker_account_id,
                JournalEntry.trade_id == t_id
            )
        )
        entry = result.scalar_one_or_none()

        if entry:
            return {"entry": entry.to_dict()}
        else:
            return {"entry": None}

    except Exception as e:
        logger.error(f"Failed to get journal entry: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{entry_id}")
async def get_journal_entry(
    entry_id: str,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific journal entry by ID."""
    try:
        result = await db.execute(
            select(JournalEntry).where(
                JournalEntry.id == UUID(entry_id),
                JournalEntry.broker_account_id == broker_account_id
            )
        )
        entry = result.scalar_one_or_none()

        if not entry:
            raise HTTPException(status_code=404, detail="Journal entry not found")

        return {"entry": entry.to_dict()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get journal entry: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/")
async def create_journal_entry(
    data: JournalEntryCreate,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Create a new journal entry."""
    try:
        trade_uuid = UUID(data.trade_id) if data.trade_id else None

        # Verify trade ownership — trade must belong to the requesting broker account.
        # The ID can come from completed_trades, positions, or trades table depending
        # on whether the user is journaling a closed trade or open position.
        if trade_uuid:
            owned = False

            # Check completed_trades first (most common — closed trades)
            ct_check = await db.execute(
                select(CompletedTrade.id).where(
                    CompletedTrade.id == trade_uuid,
                    CompletedTrade.broker_account_id == broker_account_id,
                )
            )
            if ct_check.scalar_one_or_none():
                owned = True

            # Check positions table (open positions)
            if not owned:
                pos_check = await db.execute(
                    select(Position.id).where(
                        Position.id == trade_uuid,
                        Position.broker_account_id == broker_account_id,
                    )
                )
                if pos_check.scalar_one_or_none():
                    owned = True

            # Check raw trades table (individual fills)
            if not owned:
                trade_check = await db.execute(
                    select(Trade.id).where(
                        Trade.id == trade_uuid,
                        Trade.broker_account_id == broker_account_id,
                    )
                )
                if trade_check.scalar_one_or_none():
                    owned = True

            if not owned:
                raise HTTPException(
                    status_code=403,
                    detail="Trade does not belong to your account",
                )

        # Check if entry already exists for this trade — upsert
        if trade_uuid:
            result = await db.execute(
                select(JournalEntry).where(
                    JournalEntry.broker_account_id == broker_account_id,
                    JournalEntry.trade_id == trade_uuid
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                _apply_fields(existing, data)
                existing.updated_at = datetime.now(timezone.utc)
                await db.commit()
                await db.refresh(existing)
                return {"entry": existing.to_dict(), "created": False, "updated": True}

        entry = JournalEntry(
            broker_account_id=broker_account_id,
            trade_id=trade_uuid,
            emotion_tags=data.emotion_tags or [],
            followed_plan=data.followed_plan,
            deviation_reason=data.deviation_reason,
            exit_reason=data.exit_reason,
            setup_quality=data.setup_quality,
            would_repeat=data.would_repeat,
            market_condition=data.market_condition,
            notes=data.notes,
            trade_symbol=data.trade_symbol,
            trade_type=data.trade_type,
            trade_pnl=data.trade_pnl,
            entry_type=data.entry_type
        )

        db.add(entry)
        await db.commit()
        await db.refresh(entry)

        logger.info(f"Journal entry created: {entry.id}")

        try:
            await embed_journal_entry_async(db, entry)
        except Exception as e:
            logger.warning(f"Embedding failed (non-critical): {e}")

        return {
            "entry": entry.to_dict(),
            "created": True,
            "updated": False
        }

    except Exception as e:
        logger.error(f"Failed to create journal entry: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{entry_id}")
async def update_journal_entry(
    entry_id: str,
    data: JournalEntryUpdate,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Update an existing journal entry."""
    try:
        result = await db.execute(
            select(JournalEntry).where(
                JournalEntry.id == UUID(entry_id),
                JournalEntry.broker_account_id == broker_account_id
            )
        )
        entry = result.scalar_one_or_none()

        if not entry:
            raise HTTPException(status_code=404, detail="Journal entry not found")

        _apply_fields(entry, data)
        entry.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(entry)

        try:
            await rag_service.delete_embedding(db, entry.id)
            await embed_journal_entry_async(db, entry)
        except Exception as e:
            logger.warning(f"Embedding update failed (non-critical): {e}")

        return {"entry": entry.to_dict()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update journal entry: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{entry_id}")
async def delete_journal_entry(
    entry_id: str,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Delete a journal entry."""
    try:
        result = await db.execute(
            select(JournalEntry).where(
                JournalEntry.id == UUID(entry_id),
                JournalEntry.broker_account_id == broker_account_id
            )
        )
        entry = result.scalar_one_or_none()

        if not entry:
            raise HTTPException(status_code=404, detail="Journal entry not found")

        try:
            await rag_service.delete_embedding(db, entry.id)
        except Exception as e:
            logger.warning(f"Failed to delete embedding: {e}")

        await db.delete(entry)
        await db.commit()

        logger.info(f"Journal entry deleted: {entry_id}")

        return {"deleted": True, "id": entry_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete journal entry: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/trade/{trade_id}")
async def delete_journal_by_trade(
    trade_id: str,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Delete journal entry for a specific trade."""
    try:
        t_id = UUID(trade_id)

        result = await db.execute(
            delete(JournalEntry).where(
                JournalEntry.broker_account_id == broker_account_id,
                JournalEntry.trade_id == t_id
            )
        )

        await db.commit()

        return {"deleted": result.rowcount > 0, "trade_id": trade_id}

    except Exception as e:
        logger.error(f"Failed to delete journal entry: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stats/emotions")
async def get_emotion_stats(
    days: int = Query(default=30, ge=1, le=365),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Get emotion statistics for analytics."""
    from datetime import timedelta
    from sqlalchemy import func, and_

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await db.execute(
            select(JournalEntry).where(
                and_(
                    JournalEntry.broker_account_id == broker_account_id,
                    JournalEntry.created_at >= cutoff,
                    JournalEntry.emotion_tags != None
                )
            )
        )
        entries = result.scalars().all()

        emotion_counts = {}
        emotion_pnl = {}

        for entry in entries:
            tags = entry.emotion_tags or []
            pnl = 0
            if entry.trade_pnl:
                try:
                    pnl = float(entry.trade_pnl.replace(',', '').replace('₹', ''))
                except:
                    pass

            for tag in tags:
                emotion_counts[tag] = emotion_counts.get(tag, 0) + 1
                if tag not in emotion_pnl:
                    emotion_pnl[tag] = {"total": 0, "count": 0}
                emotion_pnl[tag]["total"] += pnl
                emotion_pnl[tag]["count"] += 1

        emotion_avg_pnl = {
            tag: data["total"] / data["count"] if data["count"] > 0 else 0
            for tag, data in emotion_pnl.items()
        }

        return {
            "emotion_counts": emotion_counts,
            "emotion_avg_pnl": emotion_avg_pnl,
            "total_entries": len(entries),
            "period_days": days
        }

    except Exception as e:
        logger.error(f"Failed to get emotion stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/search/semantic")
async def semantic_search_journal(
    query: str,
    limit: int = Query(default=5, ge=1, le=50),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Semantic search across journal entries using RAG."""
    try:
        results = await rag_service.search_similar(
            db=db,
            query=query,
            broker_account_id=broker_account_id,
            content_type="journal_entry",
            limit=limit,
            min_similarity=0.5
        )

        entries = []
        for result in results:
            if result.get("content_id"):
                entry_result = await db.execute(
                    select(JournalEntry).where(
                        JournalEntry.id == UUID(result["content_id"])
                    )
                )
                entry = entry_result.scalar_one_or_none()
                if entry:
                    entry_dict = entry.to_dict()
                    entry_dict["similarity"] = result["similarity"]
                    entries.append(entry_dict)

        return {
            "query": query,
            "results": entries,
            "total": len(entries)
        }

    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
