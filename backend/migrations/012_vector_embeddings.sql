-- =============================================
-- Migration: Vector Embeddings for RAG
-- Description: Enable pgvector and create embeddings table for semantic search
-- =============================================

-- Enable the pgvector extension (Supabase has this available)
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================
-- Embeddings Table
-- Stores vector embeddings for various content types
-- =============================================
CREATE TABLE IF NOT EXISTS embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Content identification
    content_type VARCHAR(50) NOT NULL,  -- 'journal_entry', 'trade_note', 'pattern', 'coaching_tip'
    content_id UUID,                     -- Reference to source (journal_entries.id, trades.id, etc.)
    broker_account_id UUID REFERENCES broker_accounts(id) ON DELETE CASCADE,

    -- The actual content and its embedding
    content TEXT NOT NULL,               -- Original text content
    embedding vector(1536),              -- OpenAI ada-002 produces 1536 dimensions

    -- Metadata for filtering
    metadata JSONB DEFAULT '{}',         -- Additional context (date, pattern_type, sentiment, etc.)

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- Indexes for efficient similarity search
-- =============================================

-- Index for vector similarity search using IVFFlat (faster for large datasets)
-- Note: You may need to run this separately after inserting data
-- CREATE INDEX IF NOT EXISTS embeddings_vector_idx
--     ON embeddings USING ivfflat (embedding vector_cosine_ops)
--     WITH (lists = 100);

-- For smaller datasets, use HNSW (more accurate, slower to build)
CREATE INDEX IF NOT EXISTS embeddings_vector_hnsw_idx
    ON embeddings USING hnsw (embedding vector_cosine_ops);

-- Index for filtering by broker account and content type
CREATE INDEX IF NOT EXISTS embeddings_broker_type_idx
    ON embeddings(broker_account_id, content_type);

-- Index for content lookup
CREATE INDEX IF NOT EXISTS embeddings_content_id_idx
    ON embeddings(content_id);

-- =============================================
-- Trading Psychology Knowledge Base
-- Pre-populated coaching content for RAG
-- =============================================
CREATE TABLE IF NOT EXISTS knowledge_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Content categorization
    category VARCHAR(100) NOT NULL,      -- 'pattern', 'strategy', 'psychology', 'intervention'
    subcategory VARCHAR(100),            -- More specific classification
    title VARCHAR(255) NOT NULL,

    -- The actual content
    content TEXT NOT NULL,

    -- Embedding
    embedding vector(1536),

    -- Metadata
    tags TEXT[] DEFAULT '{}',
    relevance_patterns TEXT[] DEFAULT '{}',  -- Which behavioral patterns this content addresses
    severity_level VARCHAR(20),              -- 'info', 'warning', 'critical'

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for knowledge base similarity search
CREATE INDEX IF NOT EXISTS knowledge_base_vector_idx
    ON knowledge_base USING hnsw (embedding vector_cosine_ops);

-- Index for category filtering
CREATE INDEX IF NOT EXISTS knowledge_base_category_idx
    ON knowledge_base(category, subcategory);

-- =============================================
-- Function to search similar embeddings
-- =============================================
CREATE OR REPLACE FUNCTION search_embeddings(
    query_embedding vector(1536),
    match_count INT DEFAULT 5,
    filter_broker_account_id UUID DEFAULT NULL,
    filter_content_type VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    content_type VARCHAR,
    content_id UUID,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id,
        e.content_type,
        e.content_id,
        e.content,
        e.metadata,
        1 - (e.embedding <=> query_embedding) AS similarity
    FROM embeddings e
    WHERE
        (filter_broker_account_id IS NULL OR e.broker_account_id = filter_broker_account_id)
        AND (filter_content_type IS NULL OR e.content_type = filter_content_type)
    ORDER BY e.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- =============================================
-- Function to search knowledge base
-- =============================================
CREATE OR REPLACE FUNCTION search_knowledge_base(
    query_embedding vector(1536),
    match_count INT DEFAULT 5,
    filter_category VARCHAR DEFAULT NULL,
    filter_patterns TEXT[] DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    category VARCHAR,
    title VARCHAR,
    content TEXT,
    tags TEXT[],
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        kb.id,
        kb.category,
        kb.title,
        kb.content,
        kb.tags,
        1 - (kb.embedding <=> query_embedding) AS similarity
    FROM knowledge_base kb
    WHERE
        kb.is_active = TRUE
        AND (filter_category IS NULL OR kb.category = filter_category)
        AND (filter_patterns IS NULL OR kb.relevance_patterns && filter_patterns)
    ORDER BY kb.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- =============================================
-- Trigger to update updated_at on embeddings
-- =============================================
CREATE OR REPLACE FUNCTION update_embeddings_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER embeddings_updated_at
    BEFORE UPDATE ON embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_embeddings_timestamp();

CREATE TRIGGER knowledge_base_updated_at
    BEFORE UPDATE ON knowledge_base
    FOR EACH ROW
    EXECUTE FUNCTION update_embeddings_timestamp();
