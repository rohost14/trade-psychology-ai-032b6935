-- Migration 035: Data Integrity Hardening (Phase 1, Items 1-2)
--
-- 1. UNIQUE constraint on (broker_account_id, order_id) in trades table.
--    Enforces what upsert_trade() already assumes. Prevents duplicate rows
--    from webhook retry storms or parallel Celery tasks.
--
-- 2. processed_at column on trades table.
--    Idempotency guard for the signal pipeline. Set atomically at the START
--    of FIFO + behavioral detection. If NOT NULL → pipeline already ran,
--    skip entirely. Prevents duplicate CompletedTrades and duplicate alerts
--    from parallel or retried Celery tasks.
--
-- Safe to run on live DB: both operations use IF NOT EXISTS / IF NOT EXISTS
-- equivalent patterns. No data is modified.

-- 1. Unique constraint: one trade row per (account, order_id)
--    Use CREATE UNIQUE INDEX rather than ALTER TABLE ADD CONSTRAINT so we
--    can use IF NOT EXISTS (ALTER TABLE doesn't support that in Postgres).
CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_account_order_unique
    ON trades (broker_account_id, order_id);

-- 2. Idempotency column: marks when the signal pipeline (FIFO + behavioral)
--    started processing this trade. NULL = not yet processed.
ALTER TABLE trades
    ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ;

-- Index for fast "find unprocessed COMPLETE trades" queries
CREATE INDEX IF NOT EXISTS idx_trades_processed_at
    ON trades (broker_account_id, processed_at)
    WHERE processed_at IS NULL;
