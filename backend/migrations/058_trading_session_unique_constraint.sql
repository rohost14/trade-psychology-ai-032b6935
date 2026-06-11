-- 058: Unique constraint on trading_sessions (broker_account_id, session_date)
--
-- WHY: _apply_alert_consolidation calls scalar_one_or_none() on this pair.
-- Concurrent 09:15 fills from two Celery workers can INSERT two session rows for
-- the same (account, day), causing MultipleResultsFound — alert consolidation
-- crashes and guardian notifications never fire.
--
-- Step 1: deduplicate any existing rows, keeping the one with the most data
-- (highest trade_count; ties broken by most-recently updated).
DELETE FROM trading_sessions
WHERE id NOT IN (
    SELECT DISTINCT ON (broker_account_id, session_date) id
    FROM trading_sessions
    ORDER BY broker_account_id, session_date, trade_count DESC, updated_at DESC
);

-- Step 2: add the unique constraint
ALTER TABLE trading_sessions
    ADD CONSTRAINT uq_trading_session_account_date
    UNIQUE (broker_account_id, session_date);
