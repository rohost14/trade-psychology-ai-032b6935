-- Migration: Create journal_entries table for trade journals
-- Run this in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS journal_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    -- Link to trade (optional - can be standalone entry)
    trade_id UUID REFERENCES trades(id) ON DELETE SET NULL,

    -- Journal content
    notes TEXT,           -- General trade notes/thesis
    emotions TEXT,        -- Free-text emotional state
    lessons TEXT,         -- Key lessons learned

    -- Quick emotion tags for analytics (JSONB array)
    emotion_tags JSONB DEFAULT '[]'::jsonb,

    -- Trade context (captured at time of entry)
    trade_symbol VARCHAR(100),
    trade_type VARCHAR(10),    -- BUY/SELL
    trade_pnl VARCHAR(50),     -- Stored as string

    -- Entry type: 'trade', 'daily', 'weekly', 'custom'
    entry_type VARCHAR(20) DEFAULT 'trade' NOT NULL,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_journal_entries_broker_account
    ON journal_entries(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_journal_entries_trade
    ON journal_entries(trade_id) WHERE trade_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_journal_entries_created
    ON journal_entries(broker_account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_journal_entries_type
    ON journal_entries(broker_account_id, entry_type);

-- Unique constraint: one journal entry per trade
CREATE UNIQUE INDEX IF NOT EXISTS idx_journal_entries_unique_trade
    ON journal_entries(broker_account_id, trade_id) WHERE trade_id IS NOT NULL;

-- Updated at trigger
CREATE OR REPLACE FUNCTION update_journal_entries_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_journal_entries_updated_at ON journal_entries;
CREATE TRIGGER trigger_journal_entries_updated_at
    BEFORE UPDATE ON journal_entries
    FOR EACH ROW
    EXECUTE FUNCTION update_journal_entries_updated_at();

-- GIN index for emotion_tags search
CREATE INDEX IF NOT EXISTS idx_journal_entries_emotion_tags
    ON journal_entries USING GIN (emotion_tags);

-- Comment on table
COMMENT ON TABLE journal_entries IS 'Trade journal entries - optional notes, emotions, and lessons for trades';
