# Kite Connect API - Production Implementation Plan

**Document Version:** 2.0
**Date:** 2026-02-06
**Purpose:** Bridge gap between current implementation and Kite API specification for production readiness

---

## Executive Summary

After thorough analysis of Kite Connect API documentation against our codebase, this document outlines all required changes for production deployment. The current implementation covers ~60% of what's needed for a robust trading psychology platform.

---

## Table of Contents

1. [Schema Updates (Database)](#1-schema-updates-database)
2. [Code Updates (Existing Files)](#2-code-updates-existing-files)
3. [New Additions](#3-new-additions)
4. [Deletions/Deprecations](#4-deletionsdeprecations)
5. [Implementation Priority](#5-implementation-priority)
6. [SQL Migrations](#6-sql-migrations)

---

## 1. Schema Updates (Database)

### 1.1 `broker_accounts` Table Updates

**Current State:** Basic OAuth fields stored
**Required Changes:** Add Kite profile data fields

| Column | Type | Purpose |
|--------|------|---------|
| user_type | VARCHAR(20) | 'individual', 'corporate', etc. |
| broker_name | VARCHAR(50) | 'ZERODHA', 'ANGELONE', etc. for multi-broker |
| exchanges | TEXT[] | Enabled exchanges: ['NSE', 'BSE', 'NFO', 'MCX'] |
| products | TEXT[] | Enabled products: ['CNC', 'NRML', 'MIS', 'BO', 'CO'] |
| order_types | TEXT[] | Enabled order types: ['MARKET', 'LIMIT', 'SL', 'SL-M'] |
| meta | JSONB | Additional broker-specific data |
| avatar_url | TEXT | User avatar from Kite |
| demat_consent | BOOLEAN | Whether demat consent is given |
| last_sync_at | TIMESTAMP | Last successful data sync |
| sync_status | VARCHAR(20) | 'pending', 'syncing', 'complete', 'error' |

### 1.2 `trades` Table Updates

**Current State:** Missing critical Kite fields
**Required Changes:** Add order tracking and metadata fields

| Column | Type | Purpose |
|--------|------|---------|
| kite_order_id | VARCHAR(50) | Kite's internal order_id |
| exchange_order_id | VARCHAR(50) | Exchange-assigned order ID |
| fill_timestamp | TIMESTAMP WITH TIME ZONE | Trade fill timestamp |
| validity | VARCHAR(10) | 'DAY', 'IOC', 'TTL' |
| variety | VARCHAR(20) | 'regular', 'amo', 'co', 'iceberg' |
| disclosed_quantity | INTEGER | Disclosed quantity |
| parent_order_id | VARCHAR(50) | For bracket/cover orders |
| tag | VARCHAR(20) | User-defined tag (max 20 chars) |
| guid | VARCHAR(100) | Globally unique identifier |
| instrument_token | BIGINT | For WebSocket subscriptions |

### 1.3 `positions` Table Updates

**Current State:** Basic position tracking
**Required Changes:** Add Kite position fields

| Column | Type | Purpose |
|--------|------|---------|
| instrument_token | BIGINT | For WebSocket subscriptions |
| overnight_quantity | INTEGER | Overnight carried quantity |
| multiplier | DECIMAL(10,4) | Lot size multiplier for F&O |
| m2m | DECIMAL(15,4) | Mark-to-market P&L |
| day_buy_quantity | INTEGER | Day's buy quantity |
| day_sell_quantity | INTEGER | Day's sell quantity |
| day_buy_price | DECIMAL(15,4) | Average day buy price |
| day_sell_price | DECIMAL(15,4) | Average day sell price |
| day_buy_value | DECIMAL(15,4) | Total day buy value |
| day_sell_value | DECIMAL(15,4) | Total day sell value |

### 1.4 NEW Table: `instruments`

**Purpose:** Cache instrument master for symbol lookups and WebSocket subscriptions

| Column | Type | Purpose |
|--------|------|---------|
| instrument_token | BIGINT | Unique identifier for WebSocket |
| exchange_token | BIGINT | Exchange-specific token |
| trading_symbol | VARCHAR(50) | Trading symbol |
| name | VARCHAR(100) | Instrument name |
| last_price | DECIMAL(15,4) | Last traded price |
| expiry | DATE | F&O expiry date |
| strike | DECIMAL(15,4) | Option strike price |
| tick_size | DECIMAL(10,4) | Minimum price movement |
| lot_size | INTEGER | Lot size for F&O |
| instrument_type | VARCHAR(20) | 'EQ', 'FUT', 'CE', 'PE' |
| segment | VARCHAR(20) | 'NSE', 'NFO', 'BSE', 'BFO', 'MCX' |
| exchange | VARCHAR(10) | Exchange code |

### 1.5 NEW Table: `orders`

**Purpose:** Track all orders (not just executed trades) for order flow analysis

| Column | Type | Purpose |
|--------|------|---------|
| kite_order_id | VARCHAR(50) | Kite's order ID |
| exchange_order_id | VARCHAR(50) | Exchange-assigned ID |
| status | VARCHAR(20) | 'OPEN', 'COMPLETE', 'CANCELLED', 'REJECTED' |
| status_message | TEXT | Human-readable status |
| trading_symbol | VARCHAR(50) | Trading symbol |
| exchange | VARCHAR(10) | Exchange code |
| transaction_type | VARCHAR(10) | 'BUY', 'SELL' |
| order_type | VARCHAR(10) | 'MARKET', 'LIMIT', 'SL', 'SL-M' |
| product | VARCHAR(10) | 'CNC', 'MIS', 'NRML' |
| variety | VARCHAR(20) | 'regular', 'amo', 'co', 'iceberg' |
| validity | VARCHAR(10) | 'DAY', 'IOC', 'TTL' |
| quantity | INTEGER | Order quantity |
| filled_quantity | INTEGER | Filled quantity |
| pending_quantity | INTEGER | Pending quantity |
| cancelled_quantity | INTEGER | Cancelled quantity |
| price | DECIMAL(15,4) | Limit price |
| trigger_price | DECIMAL(15,4) | Stop-loss trigger |
| average_price | DECIMAL(15,4) | Average fill price |

### 1.6 NEW Table: `holdings`

**Purpose:** Track CNC holdings separately from intraday positions

| Column | Type | Purpose |
|--------|------|---------|
| trading_symbol | VARCHAR(50) | Trading symbol |
| exchange | VARCHAR(10) | Exchange code |
| isin | VARCHAR(20) | ISIN code |
| quantity | INTEGER | Holding quantity |
| authorised_quantity | INTEGER | CDSL TPIN authorized |
| t1_quantity | INTEGER | T+1 holdings |
| collateral_quantity | INTEGER | Pledged quantity |
| average_price | DECIMAL(15,4) | Average buy price |
| last_price | DECIMAL(15,4) | Current market price |
| pnl | DECIMAL(15,4) | Unrealized P&L |
| day_change | DECIMAL(15,4) | Day's change |
| day_change_percentage | DECIMAL(10,4) | Day's change % |

---

## 2. Code Updates (Existing Files)

### 2.1 `backend/app/services/zerodha_service.py`

**Changes Made:**
- Added rate limiting (3 requests/second)
- Added custom exceptions (KiteAPIError, KiteRateLimitError, KiteTokenExpiredError)
- Added new endpoints: get_holdings, get_margins, get_instruments, get_order_history
- Added postback checksum validation

### 2.2 `backend/app/services/trade_sync_service.py`

**Changes Made:**
- Updated trade mapping to include all Kite fields
- Updated position sync to include new fields
- Added proper timestamp parsing

### 2.3 `backend/app/api/zerodha.py`

**Changes Made:**
- OAuth callback now stores additional profile data
- Added endpoints: /margins, /holdings, /order-analytics, /instruments/refresh, /instruments/search

### 2.4 `backend/app/api/webhooks.py`

**Changes Made:**
- Added X-Kite-Checksum header validation
- Updated trade data mapping with new fields

---

## 3. New Additions

### 3.1 New Services Created

| Service | File | Purpose |
|---------|------|---------|
| InstrumentService | `instrument_service.py` | Cache and lookup instrument master |
| MarginService | `margin_service.py` | Track margin utilization |
| OrderAnalyticsService | `order_analytics_service.py` | Analyze order patterns |

### 3.2 New Models Created

| Model | File | Purpose |
|-------|------|---------|
| Instrument | `instrument.py` | Instrument master cache |
| Order | `order.py` | Order tracking |
| Holding | `holding.py` | CNC holdings |

---

## 4. Deletions/Deprecations

### 4.1 Fields to Monitor

The following fields exist in current schema but should be verified against Kite data:
- `trades.order_id` - Ensure this maps to `trade_id` from Kite
- `positions.pnl` vs `positions.m2m` - Understand the difference

### 4.2 Hardcoded Values to Remove

Replace hardcoded exchange/product lists with values from `broker_account.exchanges` and `broker_account.products`.

---

## 5. Implementation Priority

### Phase 1: Critical for Production ✅ COMPLETE

| Task | Status |
|------|--------|
| Database migrations | Ready to run |
| Trade field mapping | Complete |
| Rate limiting | Complete |
| Error handling | Complete |
| Postback checksum validation | Complete |

### Phase 2: Data Completeness ✅ COMPLETE

| Task | Status |
|------|--------|
| Implement Order sync | ✅ Complete |
| Implement Holdings sync | ✅ Complete |
| Add instrument master cache | ✅ Complete |
| Update P&L calculation with lot sizes | ✅ Complete |

**New API Endpoints Added:**
- `POST /zerodha/sync/orders` - Sync all orders
- `POST /zerodha/sync/holdings` - Sync CNC holdings
- `POST /zerodha/sync/all` - Comprehensive sync (trades, positions, orders, holdings)

### Phase 3: Enhanced Features ✅ COMPLETE

| Task | Status |
|------|--------|
| Margin tracking with history | ✅ Complete |
| Margin trend analysis | ✅ Complete |
| Order analytics | ✅ Complete |
| WebSocket for real-time quotes | ✅ Complete |
| Price stream control endpoints | ✅ Complete |

**New API Endpoints Added:**
- `POST /zerodha/stream/start` - Start real-time price streaming
- `POST /zerodha/stream/stop` - Stop price streaming
- `POST /zerodha/margins/check-order` - Pre-trade margin check
- `GET /zerodha/margins/insights` - Margin insights with history

**New Migration:**
- `010_margin_history.sql` - Margin snapshots table for trend analysis

### Phase 4: Production Polish ✅ COMPLETE

| Task | Status |
|------|--------|
| Token validation & management | ✅ Complete |
| Multi-broker abstract interface | ✅ Complete |
| Comprehensive logging/monitoring | ✅ Complete |
| Request logging middleware | ✅ Complete |
| Metrics collection | ✅ Complete |
| Health check endpoint | ✅ Complete |

**New API Endpoints Added:**
- `GET /zerodha/token/validate` - Check if token is valid
- `GET /zerodha/token/status` - Status of all account tokens
- `GET /zerodha/accounts/needing-reauth` - Accounts with expired tokens
- `GET /zerodha/metrics` - API performance metrics
- `POST /zerodha/metrics/reset` - Reset metrics
- `GET /zerodha/health` - Health check

**New Files Created:**
- `services/token_manager.py` - Token lifecycle management
- `services/broker_interface.py` - Abstract broker interface for multi-broker support
- `core/logging_config.py` - Structured logging, metrics, decorators
- `middleware/request_logging.py` - Request/response logging middleware

---

## 6. SQL Migrations

### Migration 008: Kite API Field Alignment

**Run this FIRST in Supabase SQL Editor:**

```sql
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

ALTER TABLE trades
ADD COLUMN IF NOT EXISTS kite_order_id VARCHAR(50);

ALTER TABLE trades
ADD COLUMN IF NOT EXISTS exchange_order_id VARCHAR(50);

ALTER TABLE trades
ADD COLUMN IF NOT EXISTS fill_timestamp TIMESTAMP WITH TIME ZONE;

ALTER TABLE trades
ADD COLUMN IF NOT EXISTS validity VARCHAR(10) DEFAULT 'DAY';

ALTER TABLE trades
ADD COLUMN IF NOT EXISTS variety VARCHAR(20) DEFAULT 'regular';

ALTER TABLE trades
ADD COLUMN IF NOT EXISTS disclosed_quantity INTEGER DEFAULT 0;

ALTER TABLE trades
ADD COLUMN IF NOT EXISTS parent_order_id VARCHAR(50);

ALTER TABLE trades
ADD COLUMN IF NOT EXISTS tag VARCHAR(20);

ALTER TABLE trades
ADD COLUMN IF NOT EXISTS guid VARCHAR(100);

ALTER TABLE trades
ADD COLUMN IF NOT EXISTS instrument_token BIGINT;

CREATE INDEX IF NOT EXISTS idx_trades_kite_order_id ON trades(kite_order_id);
CREATE INDEX IF NOT EXISTS idx_trades_tag ON trades(tag);
CREATE INDEX IF NOT EXISTS idx_trades_instrument_token ON trades(instrument_token);

-- ============================================================================
-- PART 3: positions table updates
-- ============================================================================

ALTER TABLE positions
ADD COLUMN IF NOT EXISTS instrument_token BIGINT;

ALTER TABLE positions
ADD COLUMN IF NOT EXISTS overnight_quantity INTEGER DEFAULT 0;

ALTER TABLE positions
ADD COLUMN IF NOT EXISTS multiplier DECIMAL(10,4) DEFAULT 1;

ALTER TABLE positions
ADD COLUMN IF NOT EXISTS m2m DECIMAL(15,4);

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

CREATE INDEX IF NOT EXISTS idx_positions_instrument_token ON positions(instrument_token);

-- ============================================================================
-- PART 4: Add comments for documentation
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
```

---

### Migration 009: New Tables

**Run this SECOND in Supabase SQL Editor:**

```sql
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
    kite_order_id VARCHAR(50) NOT NULL,
    exchange_order_id VARCHAR(50),
    status VARCHAR(20) NOT NULL,
    status_message TEXT,
    status_message_raw TEXT,
    trading_symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    transaction_type VARCHAR(10) NOT NULL,
    order_type VARCHAR(10) NOT NULL,
    product VARCHAR(10) NOT NULL,
    variety VARCHAR(20) NOT NULL,
    validity VARCHAR(10) NOT NULL DEFAULT 'DAY',
    quantity INTEGER NOT NULL,
    disclosed_quantity INTEGER DEFAULT 0,
    pending_quantity INTEGER DEFAULT 0,
    cancelled_quantity INTEGER DEFAULT 0,
    filled_quantity INTEGER DEFAULT 0,
    price DECIMAL(15,4),
    trigger_price DECIMAL(15,4),
    average_price DECIMAL(15,4),
    order_timestamp TIMESTAMP WITH TIME ZONE,
    exchange_timestamp TIMESTAMP WITH TIME ZONE,
    exchange_update_timestamp TIMESTAMP WITH TIME ZONE,
    tag VARCHAR(20),
    guid VARCHAR(100),
    parent_order_id VARCHAR(50),
    meta JSONB DEFAULT '{}'::jsonb,
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
    trading_symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    isin VARCHAR(20),
    quantity INTEGER NOT NULL,
    authorised_quantity INTEGER DEFAULT 0,
    t1_quantity INTEGER DEFAULT 0,
    collateral_quantity INTEGER DEFAULT 0,
    collateral_type VARCHAR(20),
    average_price DECIMAL(15,4),
    last_price DECIMAL(15,4),
    close_price DECIMAL(15,4),
    pnl DECIMAL(15,4),
    day_change DECIMAL(15,4),
    day_change_percentage DECIMAL(10,4),
    instrument_token BIGINT,
    product VARCHAR(10) DEFAULT 'CNC',
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
```

---

## 7. Testing Checklist

### API Integration Tests

- [ ] OAuth flow completes successfully
- [ ] Token refresh works when token expires
- [ ] Rate limiting prevents 429 errors
- [ ] Postback webhook validates checksum
- [ ] All trade fields mapped correctly
- [ ] Orders sync with all statuses
- [ ] Holdings sync for CNC trades
- [ ] Positions sync with F&O multipliers
- [ ] P&L calculation accurate for F&O

### Data Integrity Tests

- [ ] No duplicate trades on re-sync
- [ ] Position quantities match broker
- [ ] P&L calculations verified against Kite dashboard
- [ ] Instrument token lookups work

### Error Handling Tests

- [ ] Graceful handling of API downtime
- [ ] Token expiry triggers re-auth flow
- [ ] Invalid orders handled properly
- [ ] Network timeout recovery

---

## 8. Environment Variables Required

```env
# Kite Connect (existing - verify these are set)
ZERODHA_API_KEY=your_api_key
ZERODHA_API_SECRET=your_api_secret
```

---

## Summary

This implementation plan addresses all gaps between the current codebase and Kite Connect API requirements. Key priorities:

1. **Database schema alignment** - Store all Kite fields for complete data
2. **Error handling** - Rate limits, token expiry, API errors
3. **New tables** - Orders, Holdings, Instruments for complete trading picture
4. **F&O accuracy** - Lot sizes, multipliers for correct P&L
5. **Real-time capability** - WebSocket foundation for live updates

Following this plan will make TradeMentor AI production-ready for Zerodha integration.

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-06 | Initial plan created |
| 1.1 | 2026-02-06 | Fixed SQL syntax, aligned with actual migration files |
| 1.2 | 2026-02-06 | Phase 2 complete: Order sync, Holdings sync, P&L with lot sizes |
| 1.3 | 2026-02-06 | Added missing columns: broker_name, demat_consent, last_sync_at |
| 1.4 | 2026-02-06 | Phase 3 complete: WebSocket, margin history, price stream control |
| 2.0 | 2026-02-06 | Phase 4 complete: Token management, multi-broker interface, logging/monitoring |
