-- Migration 010: Margin History Tracking
-- Run this in Supabase SQL Editor
-- Purpose: Track margin utilization over time for behavioral insights

-- ============================================================================
-- TABLE: margin_snapshots - Historical margin data
-- ============================================================================

CREATE TABLE IF NOT EXISTS margin_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    -- Timestamp
    snapshot_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Equity segment
    equity_available DECIMAL(15,4),
    equity_used DECIMAL(15,4),
    equity_total DECIMAL(15,4),
    equity_utilization_pct DECIMAL(5,2),

    -- Commodity segment
    commodity_available DECIMAL(15,4),
    commodity_used DECIMAL(15,4),
    commodity_total DECIMAL(15,4),
    commodity_utilization_pct DECIMAL(5,2),

    -- Overall metrics
    max_utilization_pct DECIMAL(5,2),
    risk_level VARCHAR(20),

    -- Breakdown (JSONB for flexibility)
    equity_breakdown JSONB DEFAULT '{}'::jsonb,
    commodity_breakdown JSONB DEFAULT '{}'::jsonb,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for time-series queries
CREATE INDEX IF NOT EXISTS idx_margin_snapshots_account_time
ON margin_snapshots(broker_account_id, snapshot_at DESC);

-- Index for risk level queries
CREATE INDEX IF NOT EXISTS idx_margin_snapshots_risk
ON margin_snapshots(broker_account_id, risk_level);

COMMENT ON TABLE margin_snapshots IS 'Historical margin utilization for trend analysis';
COMMENT ON COLUMN margin_snapshots.risk_level IS 'safe, warning, danger';

-- ============================================================================
-- Notes on Usage
-- ============================================================================

-- Margin snapshots are INSERT-ONLY (no updates needed)
-- They are automatically created when:
--   1. GET /zerodha/margins/insights is called
--   2. POST /zerodha/sync/all completes successfully
--
-- For scheduled snapshots, set up a cron job to call the insights endpoint
-- or create a scheduled task in your application.
