-- Migration 023: Add segment column to trades and positions
-- Fix: H13 (segment column present in DB but missing from ORM models)

ALTER TABLE trades ADD COLUMN IF NOT EXISTS segment VARCHAR(20);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS segment VARCHAR(20);

-- Index for filtering by segment
CREATE INDEX IF NOT EXISTS idx_trades_segment ON trades(segment);
CREATE INDEX IF NOT EXISTS idx_positions_segment ON positions(segment);
