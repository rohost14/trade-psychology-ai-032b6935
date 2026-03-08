-- Add missing indexes on broker_account_id for core tables
-- These are the most queried columns and were missing indexes

CREATE INDEX IF NOT EXISTS idx_trades_broker_account_id ON trades(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_positions_broker_account_id ON positions(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_orders_broker_account_id ON orders(broker_account_id);

-- Also add composite index for common trade queries
CREATE INDEX IF NOT EXISTS idx_trades_broker_status ON trades(broker_account_id, status);
CREATE INDEX IF NOT EXISTS idx_trades_broker_timestamp ON trades(broker_account_id, order_timestamp DESC);
