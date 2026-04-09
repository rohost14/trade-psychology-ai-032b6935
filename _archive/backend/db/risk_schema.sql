-- Create risk_alerts table
CREATE TABLE IF NOT EXISTS risk_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id),
    
    -- Pattern detected
    pattern_type TEXT NOT NULL, 
    severity TEXT NOT NULL,     
    
    -- Context
    message TEXT NOT NULL,
    details JSONB,              
    
    -- Related trades
    trigger_trade_id UUID REFERENCES trades(id),
    related_trade_ids UUID[],   
    
    -- Timestamps
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_risk_alerts_broker ON risk_alerts(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_detected_at ON risk_alerts(detected_at);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_pattern ON risk_alerts(pattern_type);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_severity ON risk_alerts(severity);
