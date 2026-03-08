-- Migration 036: position_ledger table
--
-- Every fill that changes a position gets one row here.
-- entry_type = OPEN | INCREASE | DECREASE | CLOSE | FLIP
--
-- This is the foundation for accurate P&L that handles:
--   - Partial fills (BUY 100 arrives as BUY 40 + BUY 60)
--   - Position flips (SELL 100 when long 50 → closes 50, opens short 50)
--   - Averaging down (BUY 50 → BUY 50 → SELL 100)
--   - Out-of-order fills (late webhook arrival)
--
-- idempotency_key = broker_order_id prevents duplicate entries
-- from webhook retries or reconciliation re-queuing.
--
-- NOTE: This table is built alongside the existing FIFO calculator.
-- Phase 3 will cut over to use the ledger as the source of truth.
-- Phase 2 only builds and tests it in isolation.

CREATE TABLE IF NOT EXISTS position_ledger (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id    UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    -- Instrument
    tradingsymbol        TEXT NOT NULL,
    exchange             TEXT NOT NULL,

    -- Fill details
    entry_type           TEXT NOT NULL,           -- OPEN|INCREASE|DECREASE|CLOSE|FLIP
    fill_order_id        TEXT NOT NULL,           -- broker order_id of this fill
    fill_qty             INT  NOT NULL,           -- positive = buy, negative = sell
    fill_price           NUMERIC(15,4) NOT NULL,

    -- Running position state after this fill
    position_qty_after   INT NOT NULL,            -- net qty (positive = long, negative = short)
    avg_entry_price_after NUMERIC(15,4),          -- recalculated after each fill

    -- P&L — non-zero only on DECREASE / CLOSE / FLIP
    realized_pnl         NUMERIC(15,4) NOT NULL DEFAULT 0,

    -- Session linkage (FK added in migration 037 after trading_sessions exists)
    session_id           UUID,

    -- Timestamps
    occurred_at          TIMESTAMPTZ NOT NULL,    -- trade timestamp (NOT insert time)
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Idempotency: one ledger entry per fill
    -- Format: {broker_order_id}:{fill_seq} where fill_seq is 0 for single fills,
    --         or 0/1/2... for partial fills within the same order.
    idempotency_key      TEXT NOT NULL UNIQUE
);

-- Fast queries: "show me all fills for this account+symbol in order"
CREATE INDEX IF NOT EXISTS idx_position_ledger_account_symbol
    ON position_ledger (broker_account_id, tradingsymbol, occurred_at);

-- Fast lookup: is this fill already in the ledger?
CREATE INDEX IF NOT EXISTS idx_position_ledger_idempotency
    ON position_ledger (idempotency_key);
