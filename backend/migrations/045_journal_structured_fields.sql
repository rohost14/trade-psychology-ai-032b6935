-- Migration 045: Add structured fields to journal_entries
-- Replaces the 3 free-text textarea approach with structured quick-select data.
-- These fields enable pattern analytics:
--   "You deviate from plan 60% of the time on revenge trades"
--   "Setup quality 1-2 trades have 5x higher loss rate"
--   "When you said FOMO, next trade lost 73% of the time"
--
-- Run in Supabase SQL editor.

ALTER TABLE journal_entries
    ADD COLUMN IF NOT EXISTS followed_plan    VARCHAR(20),   -- 'yes' | 'partially' | 'no'
    ADD COLUMN IF NOT EXISTS deviation_reason VARCHAR(50),   -- 'fomo' | 'revenge' | 'overconfident' | 'bored' | 'impulse' | 'other'
    ADD COLUMN IF NOT EXISTS exit_reason      VARCHAR(50),   -- 'sl_hit' | 'target_hit' | 'trailed_stop' | 'manual' | 'panic' | 'news'
    ADD COLUMN IF NOT EXISTS setup_quality    SMALLINT       CHECK (setup_quality BETWEEN 1 AND 5),
    ADD COLUMN IF NOT EXISTS would_repeat     VARCHAR(10),   -- 'yes' | 'maybe' | 'no'
    ADD COLUMN IF NOT EXISTS market_condition VARCHAR(20);   -- 'trending' | 'ranging' | 'volatile' | 'choppy' | 'news_driven'

-- Index for analytics queries: "avg P&L when followed_plan = 'no'"
CREATE INDEX IF NOT EXISTS idx_journal_followed_plan
    ON journal_entries(broker_account_id, followed_plan)
    WHERE followed_plan IS NOT NULL;

-- Index for setup quality analytics
CREATE INDEX IF NOT EXISTS idx_journal_setup_quality
    ON journal_entries(broker_account_id, setup_quality)
    WHERE setup_quality IS NOT NULL;
