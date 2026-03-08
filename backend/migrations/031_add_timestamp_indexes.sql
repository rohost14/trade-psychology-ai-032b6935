-- Migration 031: Add missing timestamp indexes for high-frequency queries
--
-- These indexes cover the two queries that fire on EVERY sync but have
-- no covering index in any prior migration:
--   1. completed_trades WHERE broker_account_id=? AND exit_time >= cutoff
--   2. risk_alerts WHERE broker_account_id=? ORDER BY detected_at DESC
--
-- Also adds a per-symbol FIFO index used by pnl_calculator for FIFO matching.

CREATE INDEX IF NOT EXISTS idx_completed_trades_broker_exit
    ON completed_trades(broker_account_id, exit_time DESC);

CREATE INDEX IF NOT EXISTS idx_risk_alerts_broker_detected
    ON risk_alerts(broker_account_id, detected_at DESC);

-- Covers pnl_calculator's per-symbol chronological FIFO query
CREATE INDEX IF NOT EXISTS idx_trades_broker_symbol_timestamp
    ON trades(broker_account_id, tradingsymbol, order_timestamp ASC);
