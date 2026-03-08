-- Migration 029: Alert Checkpoints
-- Creates table for storing real counterfactual P&L data per alert.
-- When a danger/critical alert fires, snapshot the trigger position + LTP.
-- At T+30 and T+60 minutes, compare actual prices to compute real money_saved.

CREATE TABLE IF NOT EXISTS alert_checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id UUID NOT NULL REFERENCES risk_alerts(id) ON DELETE CASCADE,
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    -- Snapshot at alert time (single trigger instrument position)
    positions_snapshot JSONB DEFAULT '[]',
    total_unrealized_pnl NUMERIC(15, 4) DEFAULT 0,

    -- T+5 check (lightweight price ping)
    prices_at_t5 JSONB,
    pnl_at_t5 NUMERIC(15, 4),
    checked_at_t5 TIMESTAMP WITH TIME ZONE,

    -- T+30 check (primary counterfactual window)
    prices_at_t30 JSONB,
    pnl_at_t30 NUMERIC(15, 4),
    checked_at_t30 TIMESTAMP WITH TIME ZONE,

    -- T+60 check (final update)
    prices_at_t60 JSONB,
    pnl_at_t60 NUMERIC(15, 4),
    checked_at_t60 TIMESTAMP WITH TIME ZONE,

    -- Outcome: real data
    user_actual_pnl NUMERIC(15, 4),
    money_saved NUMERIC(15, 4),

    -- Status: pending | calculating | complete | no_positions | error
    calculation_status TEXT DEFAULT 'pending',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ac_alert_id ON alert_checkpoints(alert_id);
CREATE INDEX IF NOT EXISTS idx_ac_broker ON alert_checkpoints(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_ac_broker_created ON alert_checkpoints(broker_account_id, created_at DESC);
