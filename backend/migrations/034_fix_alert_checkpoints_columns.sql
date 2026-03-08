-- Migration 034: Add missing columns to alert_checkpoints
--
-- Migration 029 used CREATE TABLE IF NOT EXISTS, so if the table already
-- existed with a partial schema, the new columns were silently skipped.
-- This migration adds each column individually with IF NOT EXISTS guards.

ALTER TABLE alert_checkpoints
    ADD COLUMN IF NOT EXISTS positions_snapshot    JSONB DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS total_unrealized_pnl  NUMERIC(15, 4) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS prices_at_t5          JSONB,
    ADD COLUMN IF NOT EXISTS pnl_at_t5             NUMERIC(15, 4),
    ADD COLUMN IF NOT EXISTS checked_at_t5         TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS prices_at_t30         JSONB,
    ADD COLUMN IF NOT EXISTS pnl_at_t30            NUMERIC(15, 4),
    ADD COLUMN IF NOT EXISTS checked_at_t30        TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS prices_at_t60         JSONB,
    ADD COLUMN IF NOT EXISTS pnl_at_t60            NUMERIC(15, 4),
    ADD COLUMN IF NOT EXISTS checked_at_t60        TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS user_actual_pnl       NUMERIC(15, 4),
    ADD COLUMN IF NOT EXISTS money_saved           NUMERIC(15, 4),
    ADD COLUMN IF NOT EXISTS calculation_status    TEXT DEFAULT 'pending';

-- Ensure indexes exist
CREATE INDEX IF NOT EXISTS idx_ac_alert_id
    ON alert_checkpoints(alert_id);

CREATE INDEX IF NOT EXISTS idx_ac_broker
    ON alert_checkpoints(broker_account_id);

CREATE INDEX IF NOT EXISTS idx_ac_broker_created
    ON alert_checkpoints(broker_account_id, created_at DESC);
