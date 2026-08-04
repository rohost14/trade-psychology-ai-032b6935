-- 077_position_entry_price_source.sql
--
-- `positions.average_entry_price` was a straight mirror of Kite's `average_price`
-- from the net-positions payload. That field is the day-CUMULATIVE buy average:
-- it still includes fills belonging to rounds that have already closed.
--
--   BUY  1 lot @ 9.00
--   SELL 1 lot @ 8.85   <- round closed, position flat
--   BUY  3 lots @ 9.41  <- new round
--
-- Kite reports average_price = (9.00*1 + 9.41*3) / 4 = 9.3075, while the three
-- open lots actually cost 9.41. Every unrealized-P&L consumer multiplies that gap
-- by the open quantity, so the dashboard's day total disagreed with Kite's own.
--
-- PositionLedger already models this correctly (a CLOSE resets the running
-- average), so trade_sync_service now overwrites the broker figure with the
-- ledger's — but only when the ledger's net quantity agrees with the broker's.
-- This column records which source won, so the fallback is visible rather than
-- silent, and so a ledger/broker disagreement can be spotted in admin.
--
-- Idempotent. Safe to re-run. No backfill: sync_positions rewrites every open
-- row on the next sync, and closed history was always ledger-derived (correct).

ALTER TABLE positions ADD COLUMN IF NOT EXISTS entry_price_source VARCHAR(10);

COMMENT ON COLUMN positions.entry_price_source IS
    'ledger = cost of the currently open round (correct); broker = Kite day-cumulative average (fallback when the ledger lacks the position''s entry leg or disagrees on quantity)';
