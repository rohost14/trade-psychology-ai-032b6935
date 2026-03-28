-- Migration 044: Two indexes missed in 043
-- Run in Supabase SQL editor.
-- CONCURRENTLY builds without locking writes — safe on a live database.

-- positions: "find open positions for account" — used by position monitor tasks
-- Partial index: only indexes rows where total_quantity != 0 (open positions).
-- Dramatically smaller index than a full-table index; stays fast as positions close.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_positions_open
    ON positions(broker_account_id) WHERE total_quantity != 0;

-- broker_accounts: "find connected accounts" — used by beat tasks + port radar
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_broker_accounts_active
    ON broker_accounts(status, token_revoked_at);
