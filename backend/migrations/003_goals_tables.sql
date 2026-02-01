-- Goals Tables Migration
-- Run this in Supabase SQL Editor

-- Trading Goals table
CREATE TABLE IF NOT EXISTS trading_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    -- Risk limits
    max_risk_per_trade_percent FLOAT DEFAULT 2.0,
    max_daily_loss FLOAT DEFAULT 5000.0,
    max_trades_per_day INTEGER DEFAULT 10,
    require_stoploss BOOLEAN DEFAULT TRUE,
    min_time_between_trades_minutes INTEGER DEFAULT 5,
    max_position_size_percent FLOAT DEFAULT 5.0,

    -- Trading hours
    allowed_trading_start VARCHAR(10) DEFAULT '09:15',
    allowed_trading_end VARCHAR(10) DEFAULT '15:30',

    -- Capital tracking
    starting_capital FLOAT DEFAULT 100000.0,
    current_capital FLOAT DEFAULT 100000.0,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_modified_at TIMESTAMPTZ DEFAULT NOW(),

    -- One goal set per broker account
    UNIQUE(broker_account_id)
);

-- Commitment Log table
CREATE TABLE IF NOT EXISTS commitment_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    log_type VARCHAR(50) NOT NULL,  -- goal_set, goal_modified, goal_broken, streak_milestone
    description TEXT NOT NULL,
    reason TEXT,
    cost FLOAT,  -- For goal_broken entries

    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Streak Data table
CREATE TABLE IF NOT EXISTS streak_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    current_streak_days INTEGER DEFAULT 0,
    longest_streak_days INTEGER DEFAULT 0,
    streak_start_date TIMESTAMPTZ,

    -- Store daily status as JSONB array
    daily_status JSONB DEFAULT '[]'::jsonb,

    -- Store milestones as JSONB array
    milestones_achieved JSONB DEFAULT '[]'::jsonb,

    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- One streak record per broker account
    UNIQUE(broker_account_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_commitment_logs_broker ON commitment_logs(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_commitment_logs_timestamp ON commitment_logs(timestamp DESC);

-- RLS disabled for now (backend connects as postgres)
-- ALTER TABLE trading_goals DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE commitment_logs DISABLE ROW LEVEL SECURITY;
-- ALTER TABLE streak_data DISABLE ROW LEVEL SECURITY;

SELECT 'Goals tables created successfully!' as status;
