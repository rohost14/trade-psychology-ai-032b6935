-- Migration 065: Engine v2 Phase 2 — Trading Constitution
--
-- The constitution IS the existing UserProfile rule fields (single source of
-- truth, master §1C.2) — daily_loss_limit, daily_trade_limit,
-- max_position_size, cooldown_after_loss. This migration adds:
--   1. The two missing constitution rules (max_consecutive_losses,
--      restricted_windows)
--   2. Lock/override metadata (§1C.3: tighten instant; loosen = friction +
--      logged + effective next session when changed during market hours)
--   3. constitution_history — audit of every rule change (Q18): which rule
--      version was active when violation N happened.

ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS max_consecutive_losses INTEGER,
    ADD COLUMN IF NOT EXISTS restricted_windows JSONB DEFAULT '[]'::jsonb,  -- ["13:00-14:00", ...] IST
    ADD COLUMN IF NOT EXISTS constitution_accepted_at TIMESTAMPTZ,          -- review-screen acceptance (Q24)
    ADD COLUMN IF NOT EXISTS constitution_locked_until TIMESTAMPTZ,         -- 30-day soft lock horizon
    ADD COLUMN IF NOT EXISTS constitution_pending JSONB;                    -- loosening changes awaiting next session
    -- constitution_pending shape: {"field": new_value, ..., "_effective_at": iso}

CREATE TABLE IF NOT EXISTS constitution_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL
        REFERENCES broker_accounts(id) ON DELETE CASCADE,
    changed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    change_type  VARCHAR(20) NOT NULL,   -- initial | accept | tighten | loosen | pending_applied
    changes      JSONB NOT NULL,         -- {"field": {"old": x, "new": y}, ...}
    effective_at TIMESTAMPTZ NOT NULL,   -- when the change takes effect (loosen in-session -> next day)
    during_market_hours BOOLEAN NOT NULL DEFAULT FALSE,
    override_flag BOOLEAN NOT NULL DEFAULT FALSE  -- loosening confirmed through the friction flow
);

CREATE INDEX IF NOT EXISTS idx_constitution_history_broker
    ON constitution_history (broker_account_id, changed_at);
