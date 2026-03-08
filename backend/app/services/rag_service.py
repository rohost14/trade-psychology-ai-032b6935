"""
RAG (Retrieval-Augmented Generation) Service

Provides semantic search capabilities using Supabase pgvector.
Uses OpenAI embeddings for vector generation.

Features:
1. Generate embeddings for content (journal entries, trade notes, etc.)
2. Semantic search across user's trading history
3. Knowledge base search for coaching content
4. Context retrieval for AI chat
"""

import logging
from typing import Dict, List, Optional, Tuple
from uuid import UUID
from datetime import datetime
import json
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import settings

logger = logging.getLogger(__name__)


class RAGService:
    """
    RAG service for semantic search and context retrieval.
    """

    def __init__(self):
        self.embedding_model = "text-embedding-ada-002"
        self.embedding_dimensions = 1536
        self.openai_api_key = settings.OPENAI_API_KEY if hasattr(settings, 'OPENAI_API_KEY') else None

        if not self.openai_api_key:
            # Fallback to OpenRouter for embeddings
            self.use_openrouter = True
            self.api_key = settings.OPENROUTER_API_KEY
        else:
            self.use_openrouter = False
            self.api_key = self.openai_api_key

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding vector for text using OpenAI API.

        Args:
            text: The text to embed

        Returns:
            List of floats representing the embedding vector, or None on failure
        """
        if not text or not text.strip():
            return None

        # Truncate to max tokens (roughly 8000 tokens = 32000 chars for safety)
        text = text[:32000]

        try:
            if self.use_openrouter:
                return await self._generate_embedding_openrouter(text)
            else:
                return await self._generate_embedding_openai(text)
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    async def _generate_embedding_openai(self, text: str) -> Optional[List[float]]:
        """Generate embedding using OpenAI API directly."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.embedding_model,
                    "input": text
                },
                timeout=30.0
            )

            if response.status_code != 200:
                logger.error(f"OpenAI embedding error: {response.status_code} - {response.text}")
                return None

            data = response.json()
            return data["data"][0]["embedding"]

    async def _generate_embedding_openrouter(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding using OpenRouter.
        Note: OpenRouter may not support embeddings directly,
        so we might need to use a different approach.
        """
        # For now, return None if OpenRouter is used
        # In production, you'd want to set up OpenAI API key specifically for embeddings
        logger.warning("OpenRouter embeddings not directly supported. Set OPENAI_API_KEY for embeddings.")
        return None

    async def store_embedding(
        self,
        db: AsyncSession,
        content: str,
        content_type: str,
        content_id: Optional[UUID] = None,
        broker_account_id: Optional[UUID] = None,
        metadata: Optional[Dict] = None
    ) -> Optional[UUID]:
        """
        Generate and store embedding for content.

        Args:
            db: Database session
            content: Text content to embed
            content_type: Type of content ('journal_entry', 'trade_note', 'pattern', etc.)
            content_id: Optional reference to source record
            broker_account_id: User's broker account ID
            metadata: Additional metadata to store

        Returns:
            UUID of the stored embedding, or None on failure
        """
        embedding = await self.generate_embedding(content)

        if not embedding:
            logger.warning(f"Could not generate embedding for {content_type}")
            return None

        try:
            # Convert embedding to PostgreSQL vector format
            embedding_str = f"[{','.join(str(x) for x in embedding)}]"

            query = text("""
                INSERT INTO embeddings (
                    content_type, content_id, broker_account_id,
                    content, embedding, metadata
                )
                VALUES (
                    :content_type, :content_id, :broker_account_id,
                    :content, :embedding::vector, :metadata
                )
                RETURNING id
            """)

            result = await db.execute(query, {
                "content_type": content_type,
                "content_id": str(content_id) if content_id else None,
                "broker_account_id": str(broker_account_id) if broker_account_id else None,
                "content": content,
                "embedding": embedding_str,
                "metadata": json.dumps(metadata or {})
            })

            row = result.fetchone()
            await db.commit()

            logger.info(f"Stored embedding for {content_type}: {row[0]}")
            return row[0]

        except Exception as e:
            logger.error(f"Failed to store embedding: {e}")
            await db.rollback()
            return None

    async def search_similar(
        self,
        db: AsyncSession,
        query: str,
        broker_account_id: Optional[UUID] = None,
        content_type: Optional[str] = None,
        limit: int = 5,
        min_similarity: float = 0.7
    ) -> List[Dict]:
        """
        Search for similar content using semantic search.

        Args:
            db: Database session
            query: Search query text
            broker_account_id: Filter by user's account
            content_type: Filter by content type
            limit: Maximum results to return
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            List of matching documents with similarity scores
        """
        query_embedding = await self.generate_embedding(query)

        if not query_embedding:
            logger.warning("Could not generate query embedding")
            return []

        try:
            embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

            sql = text("""
                SELECT
                    id,
                    content_type,
                    content_id,
                    content,
                    metadata,
                    1 - (embedding <=> :embedding::vector) AS similarity
                FROM embeddings
                WHERE
                    (:broker_account_id IS NULL OR broker_account_id = :broker_account_id::uuid)
                    AND (:content_type IS NULL OR content_type = :content_type)
                    AND (1 - (embedding <=> :embedding::vector)) >= :min_similarity
                ORDER BY embedding <=> :embedding::vector
                LIMIT :limit
            """)

            result = await db.execute(sql, {
                "embedding": embedding_str,
                "broker_account_id": str(broker_account_id) if broker_account_id else None,
                "content_type": content_type,
                "min_similarity": min_similarity,
                "limit": limit
            })

            rows = result.fetchall()

            return [
                {
                    "id": str(row[0]),
                    "content_type": row[1],
                    "content_id": str(row[2]) if row[2] else None,
                    "content": row[3],
                    "metadata": row[4] if isinstance(row[4], dict) else json.loads(row[4] or '{}'),
                    "similarity": float(row[5])
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    async def search_knowledge_base(
        self,
        db: AsyncSession,
        query: str,
        category: Optional[str] = None,
        patterns: Optional[List[str]] = None,
        limit: int = 5
    ) -> List[Dict]:
        """
        Search the knowledge base for relevant coaching content.

        Args:
            db: Database session
            query: Search query
            category: Filter by category
            patterns: Filter by relevant behavioral patterns
            limit: Maximum results

        Returns:
            List of matching knowledge base entries
        """
        query_embedding = await self.generate_embedding(query)

        if not query_embedding:
            return []

        try:
            embedding_str = f"[{','.join(str(x) for x in query_embedding)}]"

            # Build pattern filter if provided
            pattern_filter = ""
            if patterns:
                patterns_array = "ARRAY[" + ",".join(f"'{p}'" for p in patterns) + "]"
                pattern_filter = f"AND relevance_patterns && {patterns_array}"

            sql = text(f"""
                SELECT
                    id,
                    category,
                    subcategory,
                    title,
                    content,
                    tags,
                    1 - (embedding <=> :embedding::vector) AS similarity
                FROM knowledge_base
                WHERE
                    is_active = TRUE
                    AND (:category IS NULL OR category = :category)
                    {pattern_filter}
                ORDER BY embedding <=> :embedding::vector
                LIMIT :limit
            """)

            result = await db.execute(sql, {
                "embedding": embedding_str,
                "category": category,
                "limit": limit
            })

            rows = result.fetchall()

            return [
                {
                    "id": str(row[0]),
                    "category": row[1],
                    "subcategory": row[2],
                    "title": row[3],
                    "content": row[4],
                    "tags": row[5],
                    "similarity": float(row[6])
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Knowledge base search failed: {e}")
            return []

    async def get_chat_context(
        self,
        db: AsyncSession,
        query: str,
        broker_account_id: UUID,
        patterns_active: Optional[List[str]] = None
    ) -> str:
        """
        Get relevant context for AI chat responses.
        Combines user's historical data with knowledge base.

        Args:
            db: Database session
            query: User's chat message
            broker_account_id: User's account
            patterns_active: Currently detected behavioral patterns

        Returns:
            Formatted context string for LLM
        """
        context_parts = []

        # 1. Search user's journal entries
        journal_results = await self.search_similar(
            db=db,
            query=query,
            broker_account_id=broker_account_id,
            content_type="journal_entry",
            limit=3,
            min_similarity=0.6
        )

        if journal_results:
            context_parts.append("**Relevant Journal Entries:**")
            for entry in journal_results:
                date = entry.get("metadata", {}).get("date", "Unknown date")
                context_parts.append(f"- [{date}] {entry['content'][:200]}...")

        # 2. Search trade notes
        trade_notes = await self.search_similar(
            db=db,
            query=query,
            broker_account_id=broker_account_id,
            content_type="trade_note",
            limit=2,
            min_similarity=0.6
        )

        if trade_notes:
            context_parts.append("\n**Relevant Trade Notes:**")
            for note in trade_notes:
                context_parts.append(f"- {note['content'][:150]}...")

        # 3. Search knowledge base for coaching content
        kb_results = await self.search_knowledge_base(
            db=db,
            query=query,
            patterns=patterns_active,
            limit=3
        )

        if kb_results:
            context_parts.append("\n**Relevant Trading Psychology Insights:**")
            for kb in kb_results:
                context_parts.append(f"- [{kb['title']}] {kb['content'][:200]}...")

        if not context_parts:
            return ""

        return "\n".join(context_parts)

    async def embed_journal_entry(
        self,
        db: AsyncSession,
        broker_account_id: UUID,
        journal_entry_id: UUID,
        content: str,
        entry_date: datetime,
        mood: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Optional[UUID]:
        """
        Create embedding for a journal entry.

        Args:
            db: Database session
            broker_account_id: User's account
            journal_entry_id: ID of the journal entry
            content: Journal entry content
            entry_date: Date of the entry
            mood: Optional mood indicator
            tags: Optional tags

        Returns:
            ID of stored embedding
        """
        metadata = {
            "date": entry_date.isoformat(),
            "mood": mood,
            "tags": tags or []
        }

        return await self.store_embedding(
            db=db,
            content=content,
            content_type="journal_entry",
            content_id=journal_entry_id,
            broker_account_id=broker_account_id,
            metadata=metadata
        )

    async def delete_embedding(
        self,
        db: AsyncSession,
        content_id: UUID
    ) -> bool:
        """
        Delete embedding by content ID.

        Args:
            db: Database session
            content_id: ID of the source content

        Returns:
            True if deleted successfully
        """
        try:
            query = text("DELETE FROM embeddings WHERE content_id = :content_id")
            await db.execute(query, {"content_id": str(content_id)})
            await db.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete embedding: {e}")
            await db.rollback()
            return False


# Singleton instance
rag_service = RAGService()
