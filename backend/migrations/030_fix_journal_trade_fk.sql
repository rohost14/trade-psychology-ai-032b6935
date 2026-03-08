-- Migration 030: Drop FK constraint on journal_entries.trade_id
--
-- The journal_entries.trade_id column had a FK pointing to trades.id (raw fills).
-- But the journal UI links entries to completed_trades (flat-to-flat rounds),
-- which have their own UUIDs in a different table.
-- Dropping the FK lets any UUID be stored here without violation.

ALTER TABLE journal_entries
    DROP CONSTRAINT IF EXISTS journal_entries_trade_id_fkey;
