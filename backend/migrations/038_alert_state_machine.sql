-- Migration 038: alert state machine columns on risk_alerts
--
-- Currently risk_alerts only tracks acknowledged_at.
-- We need to track the full delivery lifecycle:
--
--   detected  → delivered_push  → delivered_whatsapp  → acknowledged → resolved/expired
--
-- Without these columns we cannot answer:
--   "Was this alert actually delivered to the user?"
--   "Did the user act on it?"
--   "How long between detection and acknowledgement?"
--
-- All columns are nullable — existing rows default to NULL (unknown delivery state).

ALTER TABLE risk_alerts
    ADD COLUMN IF NOT EXISTS delivered_push_at      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS delivered_whatsapp_at  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS expired_at             TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS resolved_at            TIMESTAMPTZ;

-- Index for querying undelivered alerts (alert delivery worker)
CREATE INDEX IF NOT EXISTS idx_risk_alerts_undelivered
    ON risk_alerts (broker_account_id, detected_at)
    WHERE delivered_push_at IS NULL AND expired_at IS NULL;
