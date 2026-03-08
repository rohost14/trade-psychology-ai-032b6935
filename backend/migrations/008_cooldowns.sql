-- Migration: Create cooldowns table for trading breaks
-- Run this in Supabase SQL Editor

CREATE TABLE IF NOT EXISTS cooldowns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    -- Cooldown details
    reason VARCHAR(50) NOT NULL,  -- 'revenge_pattern', 'loss_limit', 'consecutive_loss', 'manual', 'overtrading', 'fomo', 'tilt'
    duration_minutes INTEGER NOT NULL DEFAULT 15,

    -- Timing
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Skip/Acknowledge
    can_skip BOOLEAN DEFAULT TRUE,
    skipped BOOLEAN DEFAULT FALSE,
    skipped_at TIMESTAMP WITH TIME ZONE,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP WITH TIME ZONE,

    -- Context
    trigger_alert_id UUID,  -- Alert that triggered this cooldown
    message VARCHAR(500),
    meta_data JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_cooldowns_broker_account
    ON cooldowns(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_cooldowns_active
    ON cooldowns(broker_account_id, expires_at)
    WHERE skipped = FALSE;
CREATE INDEX IF NOT EXISTS idx_cooldowns_expires
    ON cooldowns(expires_at);

COMMENT ON TABLE cooldowns IS 'Active and historical cooling-off periods after risky behavior';
