-- 073_admin_aggregate_indexes.sql
-- Polish for the two admin-only aggregate queries that can't use existing indexes.
-- Both are already Redis-cached (overview 60s, insights 120s), so this is a marginal
-- cache-MISS speedup at large data volumes — not a hot-path fix.
--
-- Run OUTSIDE a transaction (CREATE INDEX CONCURRENTLY cannot run in a txn block) so it
-- never locks writes on trades / risk_alerts. Matches the pattern in migration 043.

-- #1 Admin overview DAU/WAU/MAU filters on coalesce(order_timestamp, created_at), which is
--    non-sargable against the plain timestamp index. An expression index makes the range
--    filter usable.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trades_effective_ts
    ON trades ((coalesce(order_timestamp, created_at)));

-- #2 Admin behavioural insights aggregates alerts GLOBALLY (no broker_account_id filter),
--    so the composite (broker_account_id, created_at, …) index can't serve it. A standalone
--    created_at index covers the date-window scan feeding the GROUP BYs.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_risk_alerts_created_at
    ON risk_alerts (created_at DESC);
