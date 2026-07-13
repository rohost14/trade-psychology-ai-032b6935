-- 065b: constitution_history — lock-friendly version.
-- The original CREATE TABLE timed out because the inline FK needs a
-- SHARE ROW EXCLUSIVE lock on broker_accounts (blocked by pooled
-- connections). This version creates the table without the FK, then adds
-- the constraint NOT VALID (no long lock) and validates (instant on an
-- empty table). Run statements ONE AT A TIME if the editor still times out.

CREATE TABLE IF NOT EXISTS constitution_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL,
    changed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    change_type  VARCHAR(20) NOT NULL,
    changes      JSONB NOT NULL,
    effective_at TIMESTAMPTZ NOT NULL,
    during_market_hours BOOLEAN NOT NULL DEFAULT FALSE,
    override_flag BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_constitution_history_broker
    ON constitution_history (broker_account_id, changed_at);

ALTER TABLE constitution_history
    ADD CONSTRAINT constitution_history_broker_fk
    FOREIGN KEY (broker_account_id) REFERENCES broker_accounts(id)
    ON DELETE CASCADE NOT VALID;

ALTER TABLE constitution_history VALIDATE CONSTRAINT constitution_history_broker_fk;
