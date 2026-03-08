-- Add Segment Support for Multi-Market Trading
-- Supports: EQUITY, FNO, COMMODITY, CURRENCY
-- Run this in Supabase SQL Editor

-- Add primary_segment to trading_goals
ALTER TABLE trading_goals ADD COLUMN IF NOT EXISTS primary_segment VARCHAR(20) DEFAULT 'EQUITY';

-- Add segment-specific hours (JSON)
ALTER TABLE trading_goals ADD COLUMN IF NOT EXISTS segment_hours JSONB DEFAULT '{}'::jsonb;

-- Update existing goals with default segment hours
UPDATE trading_goals
SET segment_hours = '{
  "EQUITY": {"start": "09:15", "end": "15:30"},
  "FNO": {"start": "09:15", "end": "15:30"},
  "COMMODITY": {"start": "09:00", "end": "23:30"},
  "CURRENCY": {"start": "09:00", "end": "17:00"}
}'::jsonb
WHERE segment_hours = '{}'::jsonb OR segment_hours IS NULL;

-- Add segment column to positions if not exists (for filtering)
ALTER TABLE positions ADD COLUMN IF NOT EXISTS segment VARCHAR(20);

-- Update existing positions with segment based on exchange
UPDATE positions SET segment =
  CASE
    WHEN exchange IN ('NSE', 'BSE') THEN 'EQUITY'
    WHEN exchange IN ('NFO', 'BFO') THEN 'FNO'
    WHEN exchange IN ('MCX', 'NCDEX') THEN 'COMMODITY'
    WHEN exchange = 'CDS' THEN 'CURRENCY'
    ELSE 'EQUITY'
  END
WHERE segment IS NULL;

-- Add segment column to trades if not exists
ALTER TABLE trades ADD COLUMN IF NOT EXISTS segment VARCHAR(20);

-- Update existing trades with segment
UPDATE trades SET segment =
  CASE
    WHEN exchange IN ('NSE', 'BSE') THEN 'EQUITY'
    WHEN exchange IN ('NFO', 'BFO') THEN 'FNO'
    WHEN exchange IN ('MCX', 'NCDEX') THEN 'COMMODITY'
    WHEN exchange = 'CDS' THEN 'CURRENCY'
    ELSE 'EQUITY'
  END
WHERE segment IS NULL;

-- Create index for segment filtering
CREATE INDEX IF NOT EXISTS idx_trades_segment ON trades(segment);
CREATE INDEX IF NOT EXISTS idx_positions_segment ON positions(segment);

SELECT 'Segment support added successfully!' as status;
