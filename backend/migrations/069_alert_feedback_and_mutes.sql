-- 069_alert_feedback_and_mutes.sql
-- Alerts page product features:
--   1. Feedback loop — capture what the user actually DID about an alert, so we
--      can compute a real "alerts that changed behaviour" metric (not just "seen").
--   2. Per-pattern mute — let a user silence real-time delivery of a pattern they
--      disagree with, capped so they can't mute everything (that would defeat the app).

-- 1. Outcome feedback on an alert.
--    outcome ∈ ('stopped', 'took_anyway', 'not_useful'); NULL = no feedback yet.
--    Setting an outcome also acknowledges the alert (handled in the API).
ALTER TABLE risk_alerts
    ADD COLUMN IF NOT EXISTS outcome TEXT,
    ADD COLUMN IF NOT EXISTS outcome_at TIMESTAMPTZ;

ALTER TABLE risk_alerts
    DROP CONSTRAINT IF EXISTS risk_alerts_outcome_chk;
ALTER TABLE risk_alerts
    ADD CONSTRAINT risk_alerts_outcome_chk
    CHECK (outcome IS NULL OR outcome IN ('stopped', 'took_anyway', 'not_useful'));

-- 2. Per-account muted patterns. A muted pattern still generates its RiskAlert
--    (mirror philosophy — evidence is never hidden; it stays in History), but the
--    real-time PUSH and in-app TOAST are suppressed. The count cap is enforced in
--    the API (MAX_ACTIVE_MUTES) rather than the schema.
CREATE TABLE IF NOT EXISTS alert_mutes (
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    pattern_type      TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (broker_account_id, pattern_type)
);
