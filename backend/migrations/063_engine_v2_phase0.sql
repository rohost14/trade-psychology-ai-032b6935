-- Migration 063: Behavioral Engine v2 — Phase 0 schema groundwork
--
-- 1. trigger_completed_trade_id: alerts finally reference the CompletedTrade
--    that triggered them. The legacy trigger_trade_id column FKs trades(id)
--    (raw fills) and was always NULL — kept for old rows, no longer written.
-- 2. detector_version: every alert records which detector version produced it
--    (Engine v2 Appendix A.2). Existing rows backfilled to '1.0.0'.
-- 3. confidence: detection certainty 0-100, independent of severity
--    (master spec §1.3). Nullable — deterministic detectors write it from
--    data quality in Phase 1; legacy rows stay NULL.
--
-- Severity note: 'critical' becomes a valid severity value. The column is
-- plain VARCHAR (no CHECK constraint / enum in current schema), so no DDL is
-- needed for it — this migration documents the contract:
--   severity ∈ ('info', 'caution', 'danger', 'critical')

ALTER TABLE risk_alerts
    ADD COLUMN IF NOT EXISTS trigger_completed_trade_id UUID
        REFERENCES completed_trades(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS detector_version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    ADD COLUMN IF NOT EXISTS confidence NUMERIC(5,2);

CREATE INDEX IF NOT EXISTS idx_risk_alerts_trigger_ct
    ON risk_alerts (trigger_completed_trade_id)
    WHERE trigger_completed_trade_id IS NOT NULL;
