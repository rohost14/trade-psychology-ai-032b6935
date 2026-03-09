-- Migration 040: shadow_behavioral_events table
--
-- Shadow mode table for BehaviorEngine (Phase 3).
-- The new BehaviorEngine writes here ONLY while in shadow mode.
-- Production behavioral_events table is untouched.
--
-- Comparison workflow:
--   1. Old engines (RiskDetector + BehavioralEvaluator) write to production tables
--   2. BehaviorEngine writes same-trade result here
--   3. Shadow log compares: same patterns? different risk_scores? unexpected events?
--   4. After 5 trading days of match_rate > 95%, cutover replaces old engines
--
-- This table is DROPPED after cutover is stable.

CREATE TABLE IF NOT EXISTS shadow_behavioral_events (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id       UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    -- Trigger
    trigger_completed_trade_id UUID,   -- CompletedTrade that triggered this detection
    trigger_session_id      UUID REFERENCES trading_sessions(id) ON DELETE SET NULL,

    -- Detection result
    event_type              TEXT NOT NULL,
    severity                TEXT NOT NULL,       -- LOW | MEDIUM | HIGH
    confidence              NUMERIC(3, 2) NOT NULL,
    message                 TEXT NOT NULL,
    context                 JSONB,               -- structured detection context

    -- Risk score at time of detection
    risk_score_before       NUMERIC(5, 2) NOT NULL DEFAULT 0,
    risk_score_delta        NUMERIC(5, 2) NOT NULL DEFAULT 0,
    risk_score_after        NUMERIC(5, 2) NOT NULL DEFAULT 0,

    -- Behavior state at detection
    behavior_state          TEXT NOT NULL,       -- Stable|Pressure|Tilt Risk|Tilt|Breakdown|Recovery
    trajectory              TEXT NOT NULL,       -- improving|stable|deteriorating

    -- Shadow comparison metadata
    matched_production      BOOLEAN,             -- NULL=not compared, TRUE=match, FALSE=divergence
    divergence_notes        TEXT,                -- why it differed from production

    detected_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_shadow_events_account_detected
    ON shadow_behavioral_events (broker_account_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_shadow_events_session
    ON shadow_behavioral_events (trigger_session_id, detected_at)
    WHERE trigger_session_id IS NOT NULL;
