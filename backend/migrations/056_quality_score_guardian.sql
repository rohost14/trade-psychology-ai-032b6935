-- Migration 056: Trade quality score + Guardian confirmation fields

-- Quality score on completed_trades (0-8, computed nightly or on-demand)
ALTER TABLE completed_trades
    ADD COLUMN IF NOT EXISTS quality_score SMALLINT;

CREATE INDEX IF NOT EXISTS idx_completed_trades_quality
    ON completed_trades (broker_account_id, quality_score)
    WHERE quality_score IS NOT NULL;

-- Guardian confirmation fields on users table
-- guardian_phone and guardian_name already exist (added manually pre-migration)
-- Adding confirmation + loss limit fields
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS guardian_confirmed       BOOLEAN     DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS guardian_confirmed_at    TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS guardian_loss_limit      NUMERIC(15, 4);
