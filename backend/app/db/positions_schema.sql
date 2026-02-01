CREATE TABLE positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id),
    
    -- Symbol info
    tradingsymbol TEXT NOT NULL,
    exchange TEXT NOT NULL,
    instrument_token BIGINT,
    
    -- Classification (computed)
    asset_class TEXT NOT NULL,
    instrument_type TEXT NOT NULL,
    product TEXT NOT NULL,
    
    -- Position details
    quantity INTEGER NOT NULL,
    average_price DECIMAL(12, 2),
    last_price DECIMAL(12, 2),
    close_price DECIMAL(12, 2),
    
    -- P&L
    pnl DECIMAL(12, 2),
    day_pnl DECIMAL(12, 2),
    
    -- Risk metrics
    value DECIMAL(12, 2),
    buy_value DECIMAL(12, 2),
    sell_value DECIMAL(12, 2),
    
    -- Timestamps
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Raw data
    raw_payload JSONB,
    
    UNIQUE(broker_account_id, tradingsymbol, exchange, product)
);

CREATE INDEX idx_positions_broker ON positions(broker_account_id);
CREATE INDEX idx_positions_asset_class ON positions(asset_class);
CREATE INDEX idx_positions_quantity ON positions(quantity) WHERE quantity != 0;

ALTER TABLE positions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own positions"
    ON positions FOR SELECT
    USING (auth.uid() = user_id);
