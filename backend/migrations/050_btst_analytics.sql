-- Migration 050: BTST Analytics
-- Adds overnight_close_price to completed_trades for BTST (Buy Today Sell Tomorrow)
-- overnight reversal detection.
--
-- BTST criteria:
--   product = NRML, entry after 15:00 IST, exit before 09:45 IST next trading day
--   overnight_close_price: closing price of the instrument at EOD of the entry day
--   Used to detect "overnight reversals" (was profitable at EOD, closed at a loss next day)

ALTER TABLE completed_trades
ADD COLUMN IF NOT EXISTS overnight_close_price NUMERIC(15,4);

COMMENT ON COLUMN completed_trades.overnight_close_price IS
  'For BTST trades only: closing price of the instrument at end of entry day (from Zerodha close_price field). NULL for intraday trades. Used to detect overnight reversals.';

CREATE INDEX IF NOT EXISTS idx_completed_trades_btst
  ON completed_trades (broker_account_id, entry_time, exit_time)
  WHERE overnight_close_price IS NOT NULL;
