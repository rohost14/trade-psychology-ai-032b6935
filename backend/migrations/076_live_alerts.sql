-- 076: alerts that can fire while a position is still open.
--
-- Additive and nullable throughout. Every existing row reads as 'post', which
-- is what it is: raised by BehaviorEngine after FIFO closed the position. No
-- existing query changes behaviour.
--
-- lifecycle
--   'post'  raised after the trade closed. Everything to date.
--   'live'  raised while the position was still open, by LivePositionEngine.
--           Carries no realized money, because there isn't any yet.
--
-- trigger_position_id
--   The open position a live alert was raised against. Needed for dedupe: when
--   the post-hoc engine later detects the same pattern on the completed trade
--   that position became, it UPDATES this row (fills the money, flips lifecycle
--   to 'post') rather than inserting a second alert for the same finding.
--   No FK — position rows are transient and may be gone by the time we look.

ALTER TABLE risk_alerts
    ADD COLUMN IF NOT EXISTS lifecycle TEXT NOT NULL DEFAULT 'post',
    ADD COLUMN IF NOT EXISTS trigger_position_id UUID;

ALTER TABLE risk_alerts
    DROP CONSTRAINT IF EXISTS risk_alerts_lifecycle_check;
ALTER TABLE risk_alerts
    ADD CONSTRAINT risk_alerts_lifecycle_check CHECK (lifecycle IN ('live', 'post'));

-- The dedupe lookup: "is there already a live alert of this pattern for this
-- position?" Partial, because only live rows are ever searched this way.
CREATE INDEX IF NOT EXISTS idx_risk_alerts_live_dedupe
    ON risk_alerts (broker_account_id, trigger_position_id, pattern_type)
    WHERE lifecycle = 'live';

COMMENT ON COLUMN risk_alerts.lifecycle IS
    'live = raised while the position was open (no realized money yet); post = raised after close. See docs/LIVE_ALERTS_SPEC.md';
COMMENT ON COLUMN risk_alerts.trigger_position_id IS
    'Open position a live alert was raised against; used to merge the post-hoc alert into this row instead of duplicating it.';
