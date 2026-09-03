-- PENDING, AND CORRECTLY SO — superseded except for one dead index (2026-09-03).
--
-- Live schema check: 5 of the 6 indexes below are absent by name. Almost
-- certainly a partial run — every statement uses CONCURRENTLY, which cannot
-- execute inside a transaction block, so a script that wrapped them would have
-- stopped after the first.
--
-- Four of the five are already covered by equivalent indexes on the same
-- columns, created by other migrations under different names:
--
--   idx_trades_account_status         -> idx_trades_broker_status
--   idx_trades_account_timestamp      -> idx_trades_broker_timestamp
--   idx_completed_trades_account_exit -> idx_completed_trade_account_exit
--   idx_risk_alerts_account_created   -> idx_risk_alerts_broker_detected
--
-- idx_position_ledger_account_symbol already exists.
--
-- The genuinely missing one is on `behavioral_events`, and that table is dead:
-- 133 rows, last written 2026-04-15, frozen at the Session 21 engine cutover.
-- No live writer — api/zerodha.py:891 hardcodes a count of 0 — and no live
-- reader; the `behavioral_events` local in api/analytics.py:1596 is a variable
-- name over a RiskAlert query. Indexing a frozen 133-row table would buy
-- nothing.
--
-- So this stays PENDING rather than being adopted: it was not applied, and
-- saying otherwise in the ledger would be false. It also should not be run —
-- there is no workload behind the one index it would actually add.
--
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
