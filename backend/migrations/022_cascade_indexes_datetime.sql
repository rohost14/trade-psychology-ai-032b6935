-- Migration 022: Add CASCADE, indexes, and fix DateTime types
-- Fixes: H9 (CASCADE), H10 (indexes), H11 (DateTime timezone)

-- ============================================================
-- H9: Add ON DELETE CASCADE to broker_account_id ForeignKeys
-- ============================================================

-- completed_trades
ALTER TABLE completed_trades DROP CONSTRAINT IF EXISTS completed_trades_broker_account_id_fkey;
ALTER TABLE completed_trades ADD CONSTRAINT completed_trades_broker_account_id_fkey
    FOREIGN KEY (broker_account_id) REFERENCES broker_accounts(id) ON DELETE CASCADE;

-- completed_trade_features
ALTER TABLE completed_trade_features DROP CONSTRAINT IF EXISTS completed_trade_features_broker_account_id_fkey;
ALTER TABLE completed_trade_features ADD CONSTRAINT completed_trade_features_broker_account_id_fkey
    FOREIGN KEY (broker_account_id) REFERENCES broker_accounts(id) ON DELETE CASCADE;

-- behavioral_events
ALTER TABLE behavioral_events DROP CONSTRAINT IF EXISTS behavioral_events_broker_account_id_fkey;
ALTER TABLE behavioral_events ADD CONSTRAINT behavioral_events_broker_account_id_fkey
    FOREIGN KEY (broker_account_id) REFERENCES broker_accounts(id) ON DELETE CASCADE;

-- incomplete_positions
ALTER TABLE incomplete_positions DROP CONSTRAINT IF EXISTS incomplete_positions_broker_account_id_fkey;
ALTER TABLE incomplete_positions ADD CONSTRAINT incomplete_positions_broker_account_id_fkey
    FOREIGN KEY (broker_account_id) REFERENCES broker_accounts(id) ON DELETE CASCADE;

-- risk_alerts
ALTER TABLE risk_alerts DROP CONSTRAINT IF EXISTS risk_alerts_broker_account_id_fkey;
ALTER TABLE risk_alerts ADD CONSTRAINT risk_alerts_broker_account_id_fkey
    FOREIGN KEY (broker_account_id) REFERENCES broker_accounts(id) ON DELETE CASCADE;

-- margin_snapshots
ALTER TABLE margin_snapshots DROP CONSTRAINT IF EXISTS margin_snapshots_broker_account_id_fkey;
ALTER TABLE margin_snapshots ADD CONSTRAINT margin_snapshots_broker_account_id_fkey
    FOREIGN KEY (broker_account_id) REFERENCES broker_accounts(id) ON DELETE CASCADE;

-- trading_goals
ALTER TABLE trading_goals DROP CONSTRAINT IF EXISTS trading_goals_broker_account_id_fkey;
ALTER TABLE trading_goals ADD CONSTRAINT trading_goals_broker_account_id_fkey
    FOREIGN KEY (broker_account_id) REFERENCES broker_accounts(id) ON DELETE CASCADE;

-- commitment_logs
ALTER TABLE commitment_logs DROP CONSTRAINT IF EXISTS commitment_logs_broker_account_id_fkey;
ALTER TABLE commitment_logs ADD CONSTRAINT commitment_logs_broker_account_id_fkey
    FOREIGN KEY (broker_account_id) REFERENCES broker_accounts(id) ON DELETE CASCADE;

-- streak_data
ALTER TABLE streak_data DROP CONSTRAINT IF EXISTS streak_data_broker_account_id_fkey;
ALTER TABLE streak_data ADD CONSTRAINT streak_data_broker_account_id_fkey
    FOREIGN KEY (broker_account_id) REFERENCES broker_accounts(id) ON DELETE CASCADE;


-- ============================================================
-- H10: Add missing indexes on broker_account_id
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_completed_trades_broker_account_id ON completed_trades(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_completed_trade_features_broker_account_id ON completed_trade_features(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_behavioral_events_broker_account_id ON behavioral_events(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_incomplete_positions_broker_account_id ON incomplete_positions(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_risk_alerts_broker_account_id ON risk_alerts(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_margin_snapshots_broker_account_id ON margin_snapshots(broker_account_id);


-- ============================================================
-- H11: Fix bare DateTime columns to use TIMESTAMP WITH TIME ZONE
-- ============================================================

-- cooldowns
ALTER TABLE cooldowns ALTER COLUMN started_at TYPE TIMESTAMP WITH TIME ZONE;
ALTER TABLE cooldowns ALTER COLUMN expires_at TYPE TIMESTAMP WITH TIME ZONE;
ALTER TABLE cooldowns ALTER COLUMN skipped_at TYPE TIMESTAMP WITH TIME ZONE;
ALTER TABLE cooldowns ALTER COLUMN acknowledged_at TYPE TIMESTAMP WITH TIME ZONE;
ALTER TABLE cooldowns ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE;

-- journal_entries
ALTER TABLE journal_entries ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE;
ALTER TABLE journal_entries ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE;

-- push_subscriptions
ALTER TABLE push_subscriptions ALTER COLUMN last_used_at TYPE TIMESTAMP WITH TIME ZONE;
ALTER TABLE push_subscriptions ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE;
ALTER TABLE push_subscriptions ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE;

-- user_profiles
ALTER TABLE user_profiles ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE;
ALTER TABLE user_profiles ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE;
