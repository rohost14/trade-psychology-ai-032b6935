-- Update Positions Table with Zerodha P&L Fields
-- Run this in Supabase SQL Editor

-- Add missing columns to positions table
ALTER TABLE positions ADD COLUMN IF NOT EXISTS pnl NUMERIC(12, 2);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS unrealized_pnl NUMERIC(12, 2);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS day_pnl NUMERIC(12, 2);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS last_price NUMERIC(12, 2);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS close_price NUMERIC(12, 2);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS value NUMERIC(14, 2);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS buy_value NUMERIC(14, 2);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS sell_value NUMERIC(14, 2);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS synced_at TIMESTAMPTZ;

-- Update realized_pnl precision
ALTER TABLE positions ALTER COLUMN realized_pnl TYPE NUMERIC(12, 2);

SELECT 'Positions table updated successfully!' as status;
