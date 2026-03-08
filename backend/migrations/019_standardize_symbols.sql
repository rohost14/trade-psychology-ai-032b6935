-- Migration: 019_standardize_symbols.sql
-- Description: Standardize trading_symbol column name to tradingsymbol across all tables

-- 1. Holdings
ALTER TABLE holdings RENAME COLUMN trading_symbol TO tradingsymbol;

-- 2. Orders
ALTER TABLE orders RENAME COLUMN trading_symbol TO tradingsymbol;

-- 3. Instruments
ALTER TABLE instruments RENAME COLUMN trading_symbol TO tradingsymbol;
