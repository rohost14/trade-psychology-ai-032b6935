-- Migration 039: context fields on behavioral_events
--
-- Without session_id + equity snapshot, we cannot answer:
--   "What sequence of events leads to account blowups?"
--
-- risk_score_at_event: the session risk score when this event fired.
--   Lets us see: "revenge trading always fires at risk_score > 60"
--
-- account_equity_at_event: margin balance snapshot when event fired.
--   Lets us see: "position sizing alerts fire when equity is low"
--
-- position_exposure_at_event: total open position value when event fired.
--   Lets us see: "overtrading fires when exposure is 3x normal"
--
-- All columns nullable — existing rows will have NULL (pre-Phase 2 events).

ALTER TABLE behavioral_events
    ADD COLUMN IF NOT EXISTS session_id                  UUID REFERENCES trading_sessions(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS risk_score_at_event         NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS account_equity_at_event     NUMERIC(15,4),
    ADD COLUMN IF NOT EXISTS position_exposure_at_event  NUMERIC(15,4);

-- Fast queries: "show me all events in this session ordered by time"
CREATE INDEX IF NOT EXISTS idx_behavioral_events_session
    ON behavioral_events (broker_account_id, session_id, detected_at)
    WHERE session_id IS NOT NULL;
