-- Migration 066: BehaviorEvent idempotency (P0 fix #1 from the Principal
-- Engineer review).
--
-- Defect: bulk sync re-runs analyze() over trades the webhook already
-- processed; alerts dedup but events don't -> every manual sync duplicated
-- the day's evidence rows, inflating driver scores and death-spiral domain
-- counts.
--
-- Fix: deterministic idempotency_key = detector + trigger trade (+ rule for
-- constitution_violation, which legitimately emits multiple events per
-- trade). Partial unique index; inserts use ON CONFLICT DO NOTHING.
-- Events without a trigger trade (death_spiral, position monitor) keep
-- key NULL - they carry their own escalation/window dedup.
--
-- Step 1: column
ALTER TABLE behavior_events
    ADD COLUMN IF NOT EXISTS idempotency_key TEXT;

-- Step 2: backfill existing rows
UPDATE behavior_events
SET idempotency_key =
    detector || ':' || trigger_completed_trade_id::text ||
    ':' || COALESCE(evidence->>'rule', '')
WHERE trigger_completed_trade_id IS NOT NULL
  AND idempotency_key IS NULL;

-- Step 3: remove existing duplicates, keeping the EARLIEST row per key
-- (earliest = the original webhook-path detection; later ones are sync dupes)
DELETE FROM behavior_events be
USING behavior_events keep
WHERE be.idempotency_key IS NOT NULL
  AND be.idempotency_key = keep.idempotency_key
  AND be.broker_account_id = keep.broker_account_id
  AND keep.created_at < be.created_at;

-- Step 4: partial unique index (scoped per account for safety)
CREATE UNIQUE INDEX IF NOT EXISTS uq_behavior_events_idem
    ON behavior_events (broker_account_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
