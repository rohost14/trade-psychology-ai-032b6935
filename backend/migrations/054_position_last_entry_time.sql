-- Migration 054: Add last_entry_time to positions
-- C2 audit fix: position_monitor_tasks.py references last_entry_time for
-- holding-duration calculations, but the column never existed. All
-- holding-loser alerts were silently failing with AttributeError.
--
-- last_entry_time = timestamp of the most recent BUY fill for this position.
-- For a simple entry: same as first_entry_time.
-- For averaged-up positions: tracks when the user last added to the trade.

ALTER TABLE positions
    ADD COLUMN IF NOT EXISTS last_entry_time TIMESTAMPTZ;

-- Backfill: set last_entry_time = first_entry_time for all existing rows.
-- The sync service will keep it updated going forward.
UPDATE positions
SET last_entry_time = first_entry_time
WHERE last_entry_time IS NULL
  AND first_entry_time IS NOT NULL;

COMMENT ON COLUMN positions.last_entry_time IS
    'Timestamp of the most recent BUY fill. Equals first_entry_time for single-entry positions; '
    'updated each time the user adds to an existing position (pyramid/averaging).';
