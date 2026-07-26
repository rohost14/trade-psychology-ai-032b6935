-- 075_position_ledger_product.sql — M1: product is part of the position KEY.
--
-- The same symbol held in two products at once (e.g. NIFTY fut in MIS intraday
-- AND NRML carry) is two independent positions. The ledger previously keyed
-- positions by (account, symbol, exchange) with no product dimension, so a MIS
-- buy and an NRML sell of the same symbol netted together → wrong realized P&L
-- and wrong open qty. This adds `product` to the key.
--
-- Idempotent (IF NOT EXISTS / IF NULL). Safe to re-run.

-- 1. Add the column (nullable — legacy rows written before this migration have no
--    product; NULL groups with NULL, preserving pre-migration behaviour for them).
ALTER TABLE position_ledger ADD COLUMN IF NOT EXISTS product VARCHAR(20);

-- 2. Backfill from the source trade. fill_order_id is the broker order id:
--    webhook path stores trades.order_id, sync path stores trades.kite_order_id,
--    so match either. This is exact (per-order), not a guess.
UPDATE position_ledger pl
SET product = t.product
FROM trades t
WHERE pl.product IS NULL
  AND pl.broker_account_id = t.broker_account_id
  AND (pl.fill_order_id = t.order_id OR pl.fill_order_id = t.kite_order_id)
  AND t.product IS NOT NULL;

-- 3. Backfill completed_trades.product (column already existed) ONLY for symbols
--    that unambiguously had a single product in the ledger. Mixed-product symbols
--    are left NULL on purpose — those are exactly the ones whose historical P&L was
--    wrong; their CompletedTrades get rewritten correctly by the next ledger-replay
--    / EOD reconcile (which now scopes by product), then confirmed at live validation.
UPDATE completed_trades ct
SET product = sub.product
FROM (
    SELECT broker_account_id, tradingsymbol, exchange, MIN(product) AS product
    FROM position_ledger
    WHERE product IS NOT NULL
    GROUP BY broker_account_id, tradingsymbol, exchange
    HAVING COUNT(DISTINCT product) = 1
) sub
WHERE ct.product IS NULL
  AND ct.broker_account_id = sub.broker_account_id
  AND ct.tradingsymbol   = sub.tradingsymbol
  AND ct.exchange        = sub.exchange;

-- 4. Index the 4-part position key used by get_position / _get_last_entry / replay.
CREATE INDEX IF NOT EXISTS idx_position_ledger_key
    ON position_ledger (broker_account_id, tradingsymbol, exchange, product, occurred_at DESC);
