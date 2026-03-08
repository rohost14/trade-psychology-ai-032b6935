-- =============================================
-- Migration 020: Trade Architecture Overhaul
-- Creates: completed_trades, completed_trade_features,
--          incomplete_positions, behavioral_events
-- Cleans: duplicate trades from /orders push
-- =============================================

-- =============================================
-- LAYER 3: completed_trades (flat-to-flat rounds)
-- =============================================
CREATE TABLE IF NOT EXISTS completed_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id),
    tradingsymbol VARCHAR(100) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    instrument_type VARCHAR(20),
    product VARCHAR(20),
    direction VARCHAR(10),
    total_quantity INTEGER,
    num_entries INTEGER DEFAULT 1,
    num_exits INTEGER DEFAULT 1,
    avg_entry_price NUMERIC(15, 4),
    avg_exit_price NUMERIC(15, 4),
    realized_pnl NUMERIC(15, 4),
    entry_time TIMESTAMP WITH TIME ZONE,
    exit_time TIMESTAMP WITH TIME ZONE,
    duration_minutes INTEGER,
    closed_by_flip BOOLEAN DEFAULT false,
    entry_trade_ids TEXT[],
    exit_trade_ids TEXT[],
    status VARCHAR(20) DEFAULT 'closed',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ct_broker ON completed_trades(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_ct_exit_time ON completed_trades(exit_time DESC);
CREATE INDEX IF NOT EXISTS idx_ct_symbol ON completed_trades(tradingsymbol, exchange);
CREATE INDEX IF NOT EXISTS idx_ct_broker_exit ON completed_trades(broker_account_id, exit_time DESC);

-- =============================================
-- ML FEATURES: completed_trade_features
-- =============================================
CREATE TABLE IF NOT EXISTS completed_trade_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    completed_trade_id UUID NOT NULL REFERENCES completed_trades(id) ON DELETE CASCADE,
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id),
    holding_duration_minutes INTEGER,
    entry_hour_ist INTEGER,
    exit_hour_ist INTEGER,
    entry_day_of_week INTEGER,
    is_expiry_day BOOLEAN DEFAULT false,
    size_relative_to_avg NUMERIC(10, 4),
    is_scaled_entry BOOLEAN DEFAULT false,
    is_scaled_exit BOOLEAN DEFAULT false,
    entry_after_loss BOOLEAN DEFAULT false,
    consecutive_loss_count INTEGER DEFAULT 0,
    session_pnl_at_entry NUMERIC(15, 4) DEFAULT 0,
    minutes_since_last_round INTEGER,
    is_winner BOOLEAN DEFAULT false,
    pnl_per_unit NUMERIC(15, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ctf_one_per_trade ON completed_trade_features(completed_trade_id);
CREATE INDEX IF NOT EXISTS idx_ctf_broker ON completed_trade_features(broker_account_id);

-- =============================================
-- DATA INTEGRITY: incomplete_positions
-- =============================================
CREATE TABLE IF NOT EXISTS incomplete_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id),
    tradingsymbol VARCHAR(100) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    product VARCHAR(20),
    direction VARCHAR(10),
    unmatched_quantity INTEGER,
    avg_entry_price NUMERIC(15, 4),
    entry_time TIMESTAMP WITH TIME ZONE,
    reason VARCHAR(50) NOT NULL,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    details TEXT,
    resolution_status VARCHAR(20) DEFAULT 'PENDING',
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_method VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ip_broker ON incomplete_positions(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_ip_status ON incomplete_positions(resolution_status);

-- =============================================
-- SIGNAL LAYER: behavioral_events
-- =============================================
CREATE TABLE IF NOT EXISTS behavioral_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id),
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(10) NOT NULL,
    confidence NUMERIC(3, 2) NOT NULL CHECK (confidence >= 0.70),
    trigger_trade_id UUID REFERENCES trades(id),
    trigger_position_key VARCHAR(200),
    message TEXT NOT NULL,
    context JSONB,
    detected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    delivery_status VARCHAR(20) DEFAULT 'PENDING',
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_be_broker ON behavioral_events(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_be_detected ON behavioral_events(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_be_type ON behavioral_events(event_type);
CREATE INDEX IF NOT EXISTS idx_be_delivery ON behavioral_events(delivery_status) WHERE delivery_status = 'PENDING';
CREATE INDEX IF NOT EXISTS idx_be_broker_type_recent ON behavioral_events(broker_account_id, event_type, detected_at DESC);

-- =============================================
-- CLEANUP: Remove duplicate trades from /orders push
-- /trades fills always have fill_timestamp; /orders entries don't
-- =============================================
DELETE FROM trades WHERE fill_timestamp IS NULL AND status = 'COMPLETE';
