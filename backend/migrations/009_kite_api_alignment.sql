-- Migration 008: Kite API Field Alignment
-- Run this in Supabase SQL Editor
-- Purpose: Add missing fields from Kite Connect API for production readiness

-- ============================================================================
-- PART 1: broker_accounts table updates
-- ============================================================================

ALTER TABLE broker_accounts
ADD COLUMN IF NOT EXISTS user_type VARCHAR(20);

ALTER TABLE broker_accounts
ADD COLUMN IF NOT EXISTS broker_name VARCHAR(50);

ALTER TABLE broker_accounts
ADD COLUMN IF NOT EXISTS exchanges TEXT[];

ALTER TABLE broker_accounts
ADD COLUMN IF NOT EXISTS products TEXT[];

ALTER TABLE broker_accounts
ADD COLUMN IF NOT EXISTS order_types TEXT[];

ALTER TABLE broker_accounts
ADD COLUMN IF NOT EXISTS meta JSONB DEFAULT '{}'::jsonb;

ALTER TABLE broker_accounts
ADD COLUMN IF NOT EXISTS avatar_url TEXT;

ALTER TABLE broker_accounts
ADD COLUMN IF NOT EXISTS demat_consent BOOLEAN DEFAULT false;

ALTER TABLE broker_accounts
ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE broker_accounts
ADD COLUMN IF NOT EXISTS sync_status VARCHAR(20) DEFAULT 'pending';

-- ============================================================================
-- PART 2: trades table updates
-- ============================================================================

-- Kite's order_id (different from exchange trade_id)
ALTER TABLE trades
ADD COLUMN IF NOT EXISTS kite_order_id VARCHAR(50);

-- Exchange-assigned order ID
ALTER TABLE trades
ADD COLUMN IF NOT EXISTS exchange_order_id VARCHAR(50);

-- Fill timestamp
ALTER TABLE trades
ADD COLUMN IF NOT EXISTS fill_timestamp TIMESTAMP WITH TIME ZONE;

-- Order validity (DAY, IOC, TTL)
ALTER TABLE trades
ADD COLUMN IF NOT EXISTS validity VARCHAR(10) DEFAULT 'DAY';

-- Order variety (regular, amo, co, iceberg)
ALTER TABLE trades
ADD COLUMN IF NOT EXISTS variety VARCHAR(20) DEFAULT 'regular';

-- Disclosed quantity
ALTER TABLE trades
ADD COLUMN IF NOT EXISTS disclosed_quantity INTEGER DEFAULT 0;

-- Parent order ID for bracket/cover orders
ALTER TABLE trades
ADD COLUMN IF NOT EXISTS parent_order_id VARCHAR(50);

-- User-defined tag (max 20 chars)
ALTER TABLE trades
ADD COLUMN IF NOT EXISTS tag VARCHAR(20);

-- Globally unique identifier
ALTER TABLE trades
ADD COLUMN IF NOT EXISTS guid VARCHAR(100);

-- Instrument token for WebSocket
ALTER TABLE trades
ADD COLUMN IF NOT EXISTS instrument_token BIGINT;

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_trades_kite_order_id ON trades(kite_order_id);
CREATE INDEX IF NOT EXISTS idx_trades_tag ON trades(tag);
CREATE INDEX IF NOT EXISTS idx_trades_instrument_token ON trades(instrument_token);

-- ============================================================================
-- PART 3: positions table updates
-- ============================================================================

-- Instrument token for WebSocket subscriptions
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS instrument_token BIGINT;

-- Overnight quantity
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS overnight_quantity INTEGER DEFAULT 0;

-- Lot size multiplier
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS multiplier DECIMAL(10,4) DEFAULT 1;

-- Mark-to-market P&L
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS m2m DECIMAL(15,4);

-- Day trading fields
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS day_buy_quantity INTEGER DEFAULT 0;

ALTER TABLE positions
ADD COLUMN IF NOT EXISTS day_sell_quantity INTEGER DEFAULT 0;

ALTER TABLE positions
ADD COLUMN IF NOT EXISTS day_buy_price DECIMAL(15,4);

ALTER TABLE positions
ADD COLUMN IF NOT EXISTS day_sell_price DECIMAL(15,4);

ALTER TABLE positions
ADD COLUMN IF NOT EXISTS day_buy_value DECIMAL(15,4);

ALTER TABLE positions
ADD COLUMN IF NOT EXISTS day_sell_value DECIMAL(15,4);

-- Index for positions
CREATE INDEX IF NOT EXISTS idx_positions_instrument_token ON positions(instrument_token);

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON COLUMN broker_accounts.user_type IS 'Kite user type: individual, corporate, etc.';
COMMENT ON COLUMN broker_accounts.broker_name IS 'Broker identifier: ZERODHA, ANGELONE, etc.';
COMMENT ON COLUMN broker_accounts.exchanges IS 'Enabled exchanges: NSE, BSE, NFO, MCX';
COMMENT ON COLUMN broker_accounts.products IS 'Enabled products: CNC, NRML, MIS, BO, CO';
COMMENT ON COLUMN broker_accounts.demat_consent IS 'Whether demat consent is given for holdings';
COMMENT ON COLUMN broker_accounts.last_sync_at IS 'Last successful sync timestamp';
COMMENT ON COLUMN broker_accounts.sync_status IS 'pending, syncing, complete, error';
COMMENT ON COLUMN trades.kite_order_id IS 'Kite internal order ID';
COMMENT ON COLUMN trades.variety IS 'regular, amo, co, iceberg';
COMMENT ON COLUMN trades.tag IS 'User-defined tag for order tracking';
COMMENT ON COLUMN positions.m2m IS 'Mark-to-market P&L';
COMMENT ON COLUMN positions.multiplier IS 'Lot size multiplier for F&O';
