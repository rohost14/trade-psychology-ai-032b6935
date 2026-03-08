-- Migration: 018_fix_data_types.sql
-- Description: Fix data types for PushSubscription and increase financial precision for Trades/Positions

-- 1. PushSubscription: Convert failed_count from String to Integer
ALTER TABLE push_subscriptions 
    ALTER COLUMN failed_count TYPE INTEGER USING failed_count::integer,
    ALTER COLUMN failed_count SET DEFAULT 0;

-- 2. Trades: Increase precision to NUMERIC(15, 4)
ALTER TABLE trades
    ALTER COLUMN price TYPE NUMERIC(15, 4),
    ALTER COLUMN trigger_price TYPE NUMERIC(15, 4),
    ALTER COLUMN average_price TYPE NUMERIC(15, 4),
    ALTER COLUMN market_protection TYPE NUMERIC(15, 4),
    ALTER COLUMN pnl TYPE NUMERIC(15, 4);

-- 3. Positions: Increase precision to NUMERIC(15, 4)
ALTER TABLE positions
    ALTER COLUMN average_entry_price TYPE NUMERIC(15, 4),
    ALTER COLUMN average_exit_price TYPE NUMERIC(15, 4),
    ALTER COLUMN last_price TYPE NUMERIC(15, 4),
    ALTER COLUMN close_price TYPE NUMERIC(15, 4),
    ALTER COLUMN realized_pnl TYPE NUMERIC(15, 4),
    ALTER COLUMN unrealized_pnl TYPE NUMERIC(15, 4),
    ALTER COLUMN day_pnl TYPE NUMERIC(15, 4),
    ALTER COLUMN value TYPE NUMERIC(15, 4),
    ALTER COLUMN buy_value TYPE NUMERIC(15, 4),
    ALTER COLUMN sell_value TYPE NUMERIC(15, 4),
    ALTER COLUMN day_buy_price TYPE NUMERIC(15, 4),
    ALTER COLUMN day_sell_price TYPE NUMERIC(15, 4),
    ALTER COLUMN day_buy_value TYPE NUMERIC(15, 4),
    ALTER COLUMN day_sell_value TYPE NUMERIC(15, 4);
