-- Migration 046: Strategy Groups
-- Multi-leg strategy detection tables
-- Run in Supabase SQL editor

-- StrategyGroup: one row per detected multi-leg strategy
CREATE TABLE IF NOT EXISTS strategy_groups (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    strategy_type     VARCHAR(50)  NOT NULL,   -- straddle_buy | iron_condor | ...
    underlying        VARCHAR(50)  NOT NULL,   -- NIFTY | BANKNIFTY | RELIANCE
    expiry_key        VARCHAR(20),             -- "2025-03" or "2025-03-20"
    status            VARCHAR(20)  NOT NULL DEFAULT 'open',  -- open | partially_closed | closed
    net_pnl           NUMERIC(15, 4),
    opened_at         TIMESTAMPTZ,             -- earliest entry_time across legs
    closed_at         TIMESTAMPTZ,             -- latest exit_time across legs
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- StrategyGroupLeg: links a completed_trade to its strategy group
CREATE TABLE IF NOT EXISTS strategy_group_legs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_group_id   UUID NOT NULL REFERENCES strategy_groups(id) ON DELETE CASCADE,
    completed_trade_id  UUID NOT NULL REFERENCES completed_trades(id) ON DELETE CASCADE,
    leg_role            VARCHAR(30),  -- long_call | short_call | long_put | short_put | long_futures | short_futures | unknown
    leg_pnl             NUMERIC(15, 4),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (completed_trade_id)     -- one CompletedTrade belongs to at most one strategy group
);

-- Indexes for lookups
CREATE INDEX IF NOT EXISTS idx_strategy_groups_broker ON strategy_groups (broker_account_id);
CREATE INDEX IF NOT EXISTS idx_strategy_group_legs_group ON strategy_group_legs (strategy_group_id);
CREATE INDEX IF NOT EXISTS idx_strategy_group_legs_trade ON strategy_group_legs (completed_trade_id);
