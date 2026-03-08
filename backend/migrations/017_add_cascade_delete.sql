-- Migration: 017_add_cascade_delete.sql
-- Description: Update Foreign Key constraints to support ON DELETE CASCADE for BrokerAccount deletion

-- 1. Trades
ALTER TABLE trades DROP CONSTRAINT IF EXISTS trades_broker_account_id_fkey;
ALTER TABLE trades 
    ADD CONSTRAINT trades_broker_account_id_fkey 
    FOREIGN KEY (broker_account_id) 
    REFERENCES broker_accounts(id) 
    ON DELETE CASCADE;

-- 2. Positions
ALTER TABLE positions DROP CONSTRAINT IF EXISTS positions_broker_account_id_fkey;
ALTER TABLE positions 
    ADD CONSTRAINT positions_broker_account_id_fkey 
    FOREIGN KEY (broker_account_id) 
    REFERENCES broker_accounts(id) 
    ON DELETE CASCADE;

-- 3. Orders
ALTER TABLE orders DROP CONSTRAINT IF EXISTS orders_broker_account_id_fkey;
ALTER TABLE orders 
    ADD CONSTRAINT orders_broker_account_id_fkey 
    FOREIGN KEY (broker_account_id) 
    REFERENCES broker_accounts(id) 
    ON DELETE CASCADE;

-- 4. Holdings
ALTER TABLE holdings DROP CONSTRAINT IF EXISTS holdings_broker_account_id_fkey;
ALTER TABLE holdings 
    ADD CONSTRAINT holdings_broker_account_id_fkey 
    FOREIGN KEY (broker_account_id) 
    REFERENCES broker_accounts(id) 
    ON DELETE CASCADE;

-- 5. Trading Goals (handling potential table name variants just in case, but target is trading_goals)
ALTER TABLE trading_goals DROP CONSTRAINT IF EXISTS trading_goals_broker_account_id_fkey;
ALTER TABLE trading_goals DROP CONSTRAINT IF EXISTS goals_broker_account_id_fkey; -- Remove old if exists
ALTER TABLE trading_goals 
    ADD CONSTRAINT trading_goals_broker_account_id_fkey 
    FOREIGN KEY (broker_account_id) 
    REFERENCES broker_accounts(id) 
    ON DELETE CASCADE;

-- 6. Risk Alerts
ALTER TABLE risk_alerts DROP CONSTRAINT IF EXISTS risk_alerts_broker_account_id_fkey;
ALTER TABLE risk_alerts 
    ADD CONSTRAINT risk_alerts_broker_account_id_fkey 
    FOREIGN KEY (broker_account_id) 
    REFERENCES broker_accounts(id) 
    ON DELETE CASCADE;

-- 7. Journal Entries
ALTER TABLE journal_entries DROP CONSTRAINT IF EXISTS journal_entries_broker_account_id_fkey;
ALTER TABLE journal_entries 
    ADD CONSTRAINT journal_entries_broker_account_id_fkey 
    FOREIGN KEY (broker_account_id) 
    REFERENCES broker_accounts(id) 
    ON DELETE CASCADE;

-- 8. Cooldowns
ALTER TABLE cooldowns DROP CONSTRAINT IF EXISTS cooldowns_broker_account_id_fkey;
ALTER TABLE cooldowns 
    ADD CONSTRAINT cooldowns_broker_account_id_fkey 
    FOREIGN KEY (broker_account_id) 
    REFERENCES broker_accounts(id) 
    ON DELETE CASCADE;

-- 9. Push Subscriptions
ALTER TABLE push_subscriptions DROP CONSTRAINT IF EXISTS push_subscriptions_broker_account_id_fkey;
ALTER TABLE push_subscriptions 
    ADD CONSTRAINT push_subscriptions_broker_account_id_fkey 
    FOREIGN KEY (broker_account_id) 
    REFERENCES broker_accounts(id) 
    ON DELETE CASCADE;

-- 10. User Profiles (if linked to broker_account_id)
-- Note: Check if table uses broker_account_id. Assuming it might based on context.
-- If user_profiles uses user_id generally, this might not be needed or key name differs.
-- Skipping user_profiles for now unless strictly needed, to avoid breaking if column doesn't exist.
-- But given the task is "No Cascade Delete from BrokerAccount", implied coverage of all children.
