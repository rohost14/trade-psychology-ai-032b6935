-- Migration 055: Add pnl_pct to completed_trades
--
-- pnl_pct = percentage return on the entry premium / price
--   LONG:  (avg_exit_price - avg_entry_price) / avg_entry_price * 100
--   SHORT: (avg_entry_price - avg_exit_price) / avg_entry_price * 100
--
-- NULL for rows created before this migration; a startup repair in main.py
-- backfills existing rows where avg_entry_price IS NOT NULL.

ALTER TABLE completed_trades
    ADD COLUMN IF NOT EXISTS pnl_pct FLOAT;

-- Index for analytics queries that filter/sort by pnl_pct
CREATE INDEX IF NOT EXISTS idx_completed_trades_pnl_pct
    ON completed_trades (broker_account_id, pnl_pct)
    WHERE pnl_pct IS NOT NULL;
