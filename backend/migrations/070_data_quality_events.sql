-- 070_data_quality_events.sql
-- Data-quality observability: promote the FIFO-vs-broker P&L reconciliation
-- check in trade_sync_service._reconcile_pnl_with_zerodha() from log-only to a
-- stored metric. Each row is one observed divergence (e.g. an MCX/CDS contract
-- whose FIFO P&L differs >10% from Zerodha's own figure — the signal that a
-- contract multiplier is missing from mcx_contract_specs.py).
--
-- Generic by design (kind column) so future data-quality signals — missing
-- fills, orphaned positions, feature-computation gaps — reuse the same table.

CREATE TABLE IF NOT EXISTS data_quality_events (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    kind              TEXT NOT NULL,          -- 'fifo_broker_divergence' | future kinds
    tradingsymbol     TEXT,
    exchange          TEXT,
    fifo_pnl          NUMERIC(15,4),
    broker_pnl        NUMERIC(15,4),
    ratio             NUMERIC(10,4),          -- fifo_pnl / broker_pnl
    details           JSONB NOT NULL DEFAULT '{}'::jsonb,
    detected_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dq_events_account_time
    ON data_quality_events (broker_account_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_dq_events_kind_time
    ON data_quality_events (kind, detected_at DESC);

-- Reconciliation runs on EVERY sync; the same still-unfixed divergence must not
-- insert a new row each time. One row per (account, kind, symbol, IST day) —
-- inserts use ON CONFLICT DO NOTHING against this index.
CREATE UNIQUE INDEX IF NOT EXISTS uq_dq_events_daily
    ON data_quality_events (
        broker_account_id,
        kind,
        tradingsymbol,
        ((detected_at AT TIME ZONE 'Asia/Kolkata')::date)
    );
