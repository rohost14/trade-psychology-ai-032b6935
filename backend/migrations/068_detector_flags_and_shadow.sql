-- 068_detector_flags_and_shadow.sql
-- Feature flags for behavioral detectors + shadow-event marking.
--
-- Migration model (user V-final): each detector is toggleable through
--   off → shadow → canary(rollout %) → on
-- so a new/changed detector version is dark-launchable without a deploy and
-- migrated one detector at a time (never all in one PR).
--
-- shadow ≠ suppressed. A SHADOW detector still RUNS and still WRITES its
-- BehaviorEvent (so we can audit exactly what it would have done), but it must
-- NOT alert AND must NOT move any user-facing score. Suppressed events, by
-- contrast, still feed the score. The `shadow` column below is what the scoring
-- reads (WHERE shadow = false) to keep dark-launched detectors out of the number.

-- 1. Shadow marker on behavior_events.
--    behavior_events is a partitioned parent (migration 067); ADD COLUMN cascades
--    to all partitions in PostgreSQL 11+.
ALTER TABLE behavior_events
    ADD COLUMN IF NOT EXISTS shadow BOOLEAN NOT NULL DEFAULT false;

-- 2. Runtime detector flag overrides.
--    The detector registry (code) provides the DEFAULT mode per detector; a row
--    here OVERRIDES it at runtime. Absent row ⇒ registry default (normally 'on').
CREATE TABLE IF NOT EXISTS detector_flags (
    detector    TEXT PRIMARY KEY,
    mode        TEXT NOT NULL DEFAULT 'on',
    rollout_pct INTEGER NOT NULL DEFAULT 100,   -- canary: % of accounts run live
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by  TEXT,
    CONSTRAINT detector_flags_mode_chk
        CHECK (mode IN ('off', 'shadow', 'canary', 'on')),
    CONSTRAINT detector_flags_rollout_chk
        CHECK (rollout_pct BETWEEN 0 AND 100)
);
