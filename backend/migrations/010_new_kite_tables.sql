-- Migration 009: New Tables for Kite API Integration
-- Run this in Supabase SQL Editor
-- Purpose: Add instruments, orders, and holdings tables

-- ============================================================================
-- TABLE 1: instruments - Cache instrument master for symbol lookups
-- ============================================================================

CREATE TABLE IF NOT EXISTS instruments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_token BIGINT UNIQUE NOT NULL,
    exchange_token BIGINT,
    trading_symbol VARCHAR(50) NOT NULL,
    name VARCHAR(100),
    last_price DECIMAL(15,4),
    expiry DATE,
    strike DECIMAL(15,4),
    tick_size DECIMAL(10,4) DEFAULT 0.05,
    lot_size INTEGER DEFAULT 1,
    instrument_type VARCHAR(20),
    segment VARCHAR(20),
    exchange VARCHAR(10),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT uq_instruments_exchange_symbol UNIQUE(exchange, trading_symbol)
);

CREATE INDEX IF NOT EXISTS idx_instruments_symbol ON instruments(trading_symbol);
CREATE INDEX IF NOT EXISTS idx_instruments_token ON instruments(instrument_token);
CREATE INDEX IF NOT EXISTS idx_instruments_expiry ON instruments(expiry) WHERE expiry IS NOT NULL;

COMMENT ON TABLE instruments IS 'Kite instrument master cache for symbol lookups and WebSocket subscriptions';
COMMENT ON COLUMN instruments.instrument_type IS 'EQ, FUT, CE, PE';
COMMENT ON COLUMN instruments.segment IS 'NSE, NFO, BSE, BFO, MCX';

-- ============================================================================
-- TABLE 2: orders - Track all orders (not just executed trades)
-- ============================================================================

CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    -- Kite identifiers
    kite_order_id VARCHAR(50) NOT NULL,
    exchange_order_id VARCHAR(50),

    -- Status
    status VARCHAR(20) NOT NULL,
    status_message TEXT,
    status_message_raw TEXT,

    -- Order details
    trading_symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    transaction_type VARCHAR(10) NOT NULL,
    order_type VARCHAR(10) NOT NULL,
    product VARCHAR(10) NOT NULL,
    variety VARCHAR(20) NOT NULL,
    validity VARCHAR(10) NOT NULL DEFAULT 'DAY',

    -- Quantities
    quantity INTEGER NOT NULL,
    disclosed_quantity INTEGER DEFAULT 0,
    pending_quantity INTEGER DEFAULT 0,
    cancelled_quantity INTEGER DEFAULT 0,
    filled_quantity INTEGER DEFAULT 0,

    -- Prices
    price DECIMAL(15,4),
    trigger_price DECIMAL(15,4),
    average_price DECIMAL(15,4),

    -- Timestamps
    order_timestamp TIMESTAMP WITH TIME ZONE,
    exchange_timestamp TIMESTAMP WITH TIME ZONE,
    exchange_update_timestamp TIMESTAMP WITH TIME ZONE,

    -- Metadata
    tag VARCHAR(20),
    guid VARCHAR(100),
    parent_order_id VARCHAR(50),
    meta JSONB DEFAULT '{}'::jsonb,

    -- System timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT uq_orders_account_kite_id UNIQUE(broker_account_id, kite_order_id)
);

CREATE INDEX IF NOT EXISTS idx_orders_account_date ON orders(broker_account_id, order_timestamp);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(broker_account_id, status);
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(trading_symbol);

COMMENT ON TABLE orders IS 'All orders including cancelled/rejected for order flow analysis';
COMMENT ON COLUMN orders.status IS 'OPEN, COMPLETE, CANCELLED, REJECTED';
COMMENT ON COLUMN orders.variety IS 'regular, amo, co, iceberg';

-- ============================================================================
-- TABLE 3: holdings - Track CNC holdings (delivery)
-- ============================================================================

CREATE TABLE IF NOT EXISTS holdings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    -- Identity
    trading_symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    isin VARCHAR(20),

    -- Quantities
    quantity INTEGER NOT NULL,
    authorised_quantity INTEGER DEFAULT 0,
    t1_quantity INTEGER DEFAULT 0,
    collateral_quantity INTEGER DEFAULT 0,
    collateral_type VARCHAR(20),

    -- Prices
    average_price DECIMAL(15,4),
    last_price DECIMAL(15,4),
    close_price DECIMAL(15,4),

    -- P&L
    pnl DECIMAL(15,4),
    day_change DECIMAL(15,4),
    day_change_percentage DECIMAL(10,4),

    -- Metadata
    instrument_token BIGINT,
    product VARCHAR(10) DEFAULT 'CNC',

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT uq_holdings_account_symbol UNIQUE(broker_account_id, trading_symbol, exchange)
);

CREATE INDEX IF NOT EXISTS idx_holdings_account ON holdings(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_holdings_symbol ON holdings(trading_symbol);

COMMENT ON TABLE holdings IS 'CNC/delivery holdings separate from intraday positions';
COMMENT ON COLUMN holdings.t1_quantity IS 'T+1 holdings not yet settled';
COMMENT ON COLUMN holdings.authorised_quantity IS 'Quantity authorized for selling via CDSL TPIN';

-- ============================================================================
-- Function to auto-update updated_at timestamp
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to new tables
DROP TRIGGER IF EXISTS update_instruments_updated_at ON instruments;
CREATE TRIGGER update_instruments_updated_at
    BEFORE UPDATE ON instruments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_orders_updated_at ON orders;
CREATE TRIGGER update_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_holdings_updated_at ON holdings;
CREATE TRIGGER update_holdings_updated_at
    BEFORE UPDATE ON holdings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
