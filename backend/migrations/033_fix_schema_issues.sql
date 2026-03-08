-- Migration 033: Fix three schema integrity issues
--
-- Issue 1: trades.user_id — nullable UUID with no FK to users.
--           Always NULL in practice (sync service never sets it).
--           User is reachable via trades → broker_accounts → users.
--           FIX: Drop the column.
--
-- Issue 2: risk_alerts.user_id — same problem.
--           Set from trigger_trade.user_id which is also always NULL.
--           FIX: Drop the column.
--
-- Issue 3: risk_alerts.trigger_trade_id FK has no ON DELETE rule.
--           Default is RESTRICT — deleting a Trade referenced by an alert
--           would raise an IntegrityError and block the delete.
--           FIX: Drop + re-add FK with ON DELETE SET NULL.
--           (Alert is preserved; trigger_trade_id becomes NULL.)
--

-- ─────────────────────────────────────────────────────────────────
-- 1. Drop orphan user_id columns
-- ─────────────────────────────────────────────────────────────────
ALTER TABLE trades       DROP COLUMN IF EXISTS user_id;
ALTER TABLE risk_alerts  DROP COLUMN IF EXISTS user_id;


-- ─────────────────────────────────────────────────────────────────
-- 2. Fix risk_alerts.trigger_trade_id FK → ON DELETE SET NULL
-- ─────────────────────────────────────────────────────────────────

-- Drop the existing FK (name may vary — drop by column scan)
DO $$
DECLARE
    v_constraint TEXT;
BEGIN
    SELECT tc.constraint_name INTO v_constraint
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
      ON tc.constraint_name = kcu.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_name = 'risk_alerts'
      AND kcu.column_name = 'trigger_trade_id'
    LIMIT 1;

    IF v_constraint IS NOT NULL THEN
        EXECUTE format('ALTER TABLE risk_alerts DROP CONSTRAINT %I', v_constraint);
    END IF;
END $$;

-- Re-add with SET NULL so deleting a trade nullifies the reference, not blocks it
ALTER TABLE risk_alerts
    ADD CONSTRAINT fk_risk_alerts_trigger_trade
        FOREIGN KEY (trigger_trade_id)
        REFERENCES trades(id)
        ON DELETE SET NULL;
