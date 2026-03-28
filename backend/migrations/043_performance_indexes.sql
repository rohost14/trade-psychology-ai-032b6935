-- Migration 043: Performance indexes for production scale
-- Run in Supabase SQL editor.
-- All indexes use CONCURRENTLY so they build without locking writes.
-- Safe to run on a live database.

-- trades: most common filter — account + COMPLETE status (webhook pipeline reads this)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_account_status
    ON trades(broker_account_id, status);

-- trades: time-range queries for daily/session analytics
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_account_timestamp
    ON trades(broker_account_id, order_timestamp DESC);

-- completed_trades: behavioral analysis always filters by account + exit_time window
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_completed_trades_account_exit
    ON completed_trades(broker_account_id, exit_time DESC);

-- behavioral_events: pattern history queries, dedup checks (account + time window)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_behavioral_events_account_detected
    ON behavioral_events(broker_account_id, detected_at DESC);

-- risk_alerts: dashboard + dedup filter (account + created_at + severity)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_risk_alerts_account_created
    ON risk_alerts(broker_account_id, created_at DESC, severity);

-- position_ledger: FIFO queries always filter by account + symbol + time
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_position_ledger_account_symbol
    ON position_ledger(broker_account_id, tradingsymbol, occurred_at);

-- trading_sessions: session lookup by account + date
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trading_sessions_account_date
    ON trading_sessions(broker_account_id, session_date DESC);
