-- Migration 064: Behavioral Engine v2 Phase 1 — behavior_events table
--
-- The append-only EVIDENCE record (master spec §1B.1, A.4, A.8).
-- RiskAlert = the notification record; BehaviorEvent = what the engine saw.
--
-- Key differences from the legacy `behavioral_events` table (frozen since
-- Session 21, kept untouched for old rows):
--   * severity vocabulary matches the engine: info/caution/danger/critical
--   * info events ARE recorded (suppression happens at notification layer
--     only — master §1C.8: "never suppress the BehaviorEvent")
--   * confidence 0-100, nullable, no >=0.70 insert gate
--   * data_quality per event (A.6)
--   * evidence + input_snapshot for explainability (A.8) and replayability (A.4)
--   * detector_version for versioned attribution (A.2)

CREATE TABLE IF NOT EXISTS behavior_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL
        REFERENCES broker_accounts(id) ON DELETE CASCADE,

    detector          VARCHAR(60)  NOT NULL,   -- pattern_type, e.g. 'revenge_trade'
    detector_version  VARCHAR(20)  NOT NULL,
    severity          VARCHAR(10)  NOT NULL,   -- info | caution | danger | critical
    confidence        NUMERIC(5,2),            -- 0-100 detection certainty (Q22: independent of severity)
    data_quality      VARCHAR(10)  NOT NULL DEFAULT 'GOOD',  -- GOOD | PARTIAL | UNKNOWN | INVALID

    message           TEXT         NOT NULL,
    evidence          JSONB,                   -- detector context: trade lists, thresholds crossed
    input_snapshot    JSONB,                   -- replayability: trade ids + thresholds used

    trigger_completed_trade_id UUID
        REFERENCES completed_trades(id) ON DELETE SET NULL,
    risk_alert_id     UUID
        REFERENCES risk_alerts(id) ON DELETE SET NULL,  -- linked notification, NULL for info/suppressed

    detected_at       TIMESTAMPTZ  NOT NULL,   -- trade time, never processing time
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_behavior_events_broker_detected
    ON behavior_events (broker_account_id, detected_at);
CREATE INDEX IF NOT EXISTS idx_behavior_events_detector
    ON behavior_events (detector, detected_at);
