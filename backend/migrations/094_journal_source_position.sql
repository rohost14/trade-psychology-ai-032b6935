-- 094: keep the position a journal entry was written about
--
-- WHY
--
-- `journal_entries.trade_id` holds two different things, deliberately. For a
-- closed trade it is the CompletedTrade id. For an OPEN position it is a
-- synthetic per-episode id that exists in no table at all — derived in
-- `src/lib/journalKey.ts` from (position id + IST trading date), because a
-- Position row is REUSED across episodes: the same symbol+exchange+product
-- slot is updated in place and keeps its id, so journaling by raw position id
-- would let a future, unrelated position on the same contract inherit an old
-- entry.
--
-- That design is sound and this migration does not change it. What it fixes is
-- the half that was dropped on the floor.
--
-- The client already sends the real position id as `source_id`, and
-- `api/journal.py` reads it to verify the trader owns the position — then
-- throws it away. It is not in the JournalEntry construction and there was no
-- column for it. So an open-position journal entry ends up holding only a key
-- that resolves to nothing, and the note cannot be joined back to the position
-- it was written about. The trader still SEES their note — `trade_symbol`,
-- `trade_pnl` and the text are denormalised onto the row — but nothing can
-- correlate it with what actually happened.
--
-- The model has expected this column for some time. Its docstring says an
-- entry can be attached to "a specific position (position_id)"; no such column
-- was ever added.
--
-- WHY ON DELETE SET NULL, AND NOT CASCADE
--
-- A journal entry is the trader's own writing. Deleting a position must never
-- delete what they wrote about it. SET NULL drops the pointer and keeps the
-- record — which is also what makes this safe to add to a table where 6 of 20
-- existing rows already point at positions that no longer exist.
--
-- WHAT THIS MIGRATION DOES NOT DO
--
--   * It does not add a foreign key to `trade_id`. One is impossible there by
--     design: for open positions that column is SUPPOSED to reference nothing.
--   * It does not backfill. The real position id was never stored, so for the
--     20 existing rows it cannot be recovered. They keep source_position_id
--     NULL, which is honest.
--   * It does not delete or rewrite any existing row.
--
-- Additive and reversible: one nullable column and its index.

ALTER TABLE journal_entries
    ADD COLUMN IF NOT EXISTS source_position_id UUID
        REFERENCES positions(id) ON DELETE SET NULL;

COMMENT ON COLUMN journal_entries.source_position_id IS
    'The real positions.id an open-position journal entry was written about. '
    'NULL for closed-trade entries (trade_id is the CompletedTrade id there) '
    'and for every entry written before migration 094, where the value was '
    'verified at write time and discarded.';

-- Journal entries are read per account and per trade; this index serves the
-- other direction — "what did the trader write about this position" — which is
-- the question the column exists to make answerable.
CREATE INDEX IF NOT EXISTS idx_journal_entries_source_position
    ON journal_entries (source_position_id)
    WHERE source_position_id IS NOT NULL;
