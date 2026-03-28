-- Migration 051: Position Guardrail Rules
-- Alert-only rules that fire when an open position hits a condition.
-- Sends WhatsApp + push notification. No order execution.
-- Rules expire at 15:30 IST daily and are configured before market opens.

CREATE TABLE IF NOT EXISTS guardrail_rules (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id  UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    -- User-defined label e.g. "Protect NIFTY trade"
    name               VARCHAR(100) NOT NULL,

    -- Which symbols this rule watches. NULL = all open positions.
    target_symbols     TEXT[],

    -- Condition type (one per rule)
    -- loss_threshold  → unrealized P&L on target drops below condition_value (negative ₹)
    -- loss_range_time → position has been continuously in loss for > condition_value minutes
    -- total_pnl_drop  → sum of all open position unrealized P&L drops below condition_value (negative ₹)
    -- profit_target   → unrealized P&L on target exceeds condition_value (positive ₹)
    condition_type     VARCHAR(50) NOT NULL,
    condition_value    NUMERIC(15, 2) NOT NULL,

    -- Notification channels
    notify_whatsapp    BOOLEAN NOT NULL DEFAULT TRUE,
    notify_push        BOOLEAN NOT NULL DEFAULT TRUE,

    -- State machine: active → triggered (once, never re-arms) or active → paused → active
    status             VARCHAR(20) NOT NULL DEFAULT 'active',
    triggered_at       TIMESTAMPTZ,
    trigger_count      INTEGER NOT NULL DEFAULT 0,

    -- Auto-expires at 15:30 IST on creation day
    expires_at         TIMESTAMPTZ NOT NULL,

    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_guardrail_rules_account
    ON guardrail_rules(broker_account_id);

CREATE INDEX IF NOT EXISTS idx_guardrail_rules_active
    ON guardrail_rules(broker_account_id, status, expires_at)
    WHERE status = 'active';

COMMENT ON TABLE guardrail_rules IS
    'User-defined alert rules on open positions. Fire once (status→triggered), never re-arm.';
COMMENT ON COLUMN guardrail_rules.condition_type IS
    'loss_threshold | loss_range_time | total_pnl_drop | profit_target';
COMMENT ON COLUMN guardrail_rules.target_symbols IS
    'NULL = watch all open positions for this account';
