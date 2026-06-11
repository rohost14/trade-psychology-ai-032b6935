-- Migration 059: Unique constraint on positions (broker_account_id, tradingsymbol, exchange, product)
--
-- The sync upsert uses (tradingsymbol, exchange, product) as the lookup key.
-- Without this constraint, concurrent syncs can create duplicate rows for the
-- same instrument — the dict-based dedup in trade_sync_service.py would then
-- silently discard earlier rows on every subsequent sync.
--
-- Step 1: Deduplicate — keep the row with the most recent updated_at.
-- Step 2: Add the unique constraint.

DELETE FROM positions
WHERE id NOT IN (
    SELECT DISTINCT ON (broker_account_id, tradingsymbol, exchange, product) id
    FROM positions
    ORDER BY broker_account_id, tradingsymbol, exchange, product, updated_at DESC NULLS LAST
);

ALTER TABLE positions
    ADD CONSTRAINT uq_position_account_symbol_exchange_product
    UNIQUE (broker_account_id, tradingsymbol, exchange, product);
