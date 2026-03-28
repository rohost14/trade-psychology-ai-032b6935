-- Migration 042: Portfolio Radar tables
-- gtt_tracking: tracks GTT (Good Till Triggered) SL discipline
-- position_alerts_sent: deduplication cooldown for portfolio concentration alerts

-- GTT tracking — one row per GTT per account
CREATE TABLE IF NOT EXISTS gtt_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    gtt_id INTEGER NOT NULL,
    tradingsymbol VARCHAR(100) NOT NULL,
    exchange VARCHAR(20),
    trigger_price NUMERIC(15, 4),
    order_type VARCHAR(20),
    quantity INTEGER,
    gtt_status VARCHAR(20) DEFAULT 'active',   -- active | triggered | cancelled | expired
    outcome VARCHAR(20),                        -- honored | overridden | NULL (still active)
    outcome_order_id VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT now(),
    triggered_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(broker_account_id, gtt_id)
);

CREATE INDEX IF NOT EXISTS idx_gtt_tracking_account
    ON gtt_tracking(broker_account_id, gtt_status);

-- Portfolio concentration alert deduplication
CREATE TABLE IF NOT EXISTS position_alerts_sent (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) NOT NULL,   -- expiry_concentration | underlying_concentration | directional_skew | margin_utilization
    alert_key VARCHAR(200) NOT NULL,   -- e.g. "2024-W04" | "NIFTY" | "all_long"
    fired_at TIMESTAMPTZ DEFAULT now(),
    cooldown_until TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_position_alerts_lookup
    ON position_alerts_sent(broker_account_id, alert_type, cooldown_until);
