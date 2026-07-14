-- Migration 067: partition behavior_events by month (P2 / review S8 item 1:
-- "unpartitioned, JSONB-heavy - dead at week one at scale").
--
-- Table is young and small, so we do the simple swap: rename old, create
-- partitioned parent, copy, drop old.
--
-- Two deliberate schema changes forced by Postgres partitioning rules
-- (unique constraints must include the partition key):
--   * No PK on the partitioned table. The table is append-only evidence;
--     nothing joins INTO it by id. The ORM keeps its declarative id pk
--     (mapper-only); the DB keeps id as an indexed uuid column.
--   * The idempotency unique index becomes (broker_account_id,
--     idempotency_key, detected_at). Semantics preserved: detected_at is
--     deterministic for keyed events (always the trigger trade's exit
--     time), so a retry/re-sync produces the identical tuple and still
--     conflicts. Documented assumption - engine sets detected_at =
--     completed_trade.exit_time for every keyed event.
--
-- Retention (review S8): drop old partitions after 90-180 days, e.g.
--   DROP TABLE behavior_events_y2026m07;
-- Add new-year partitions annually with the pattern below.

-- 1. Move the old table + its index names out of the way
ALTER TABLE behavior_events RENAME TO behavior_events_legacy;
ALTER INDEX IF EXISTS behavior_events_pkey RENAME TO behavior_events_legacy_pkey;
ALTER INDEX IF EXISTS idx_behavior_events_broker_detected RENAME TO idx_be_legacy_broker_detected;
ALTER INDEX IF EXISTS idx_behavior_events_detector RENAME TO idx_be_legacy_detector;
ALTER INDEX IF EXISTS uq_behavior_events_idem RENAME TO uq_be_legacy_idem;

-- 2. Partitioned parent
CREATE TABLE behavior_events (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL
        REFERENCES broker_accounts(id) ON DELETE CASCADE,
    detector          VARCHAR(60)  NOT NULL,
    detector_version  VARCHAR(20)  NOT NULL,
    severity          VARCHAR(10)  NOT NULL,
    confidence        NUMERIC(5,2),
    data_quality      VARCHAR(10)  NOT NULL DEFAULT 'GOOD',
    message           TEXT         NOT NULL,
    evidence          JSONB,
    input_snapshot    JSONB,
    trigger_completed_trade_id UUID
        REFERENCES completed_trades(id) ON DELETE SET NULL,
    risk_alert_id     UUID
        REFERENCES risk_alerts(id) ON DELETE SET NULL,
    idempotency_key   TEXT,
    detected_at       TIMESTAMPTZ  NOT NULL,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
) PARTITION BY RANGE (detected_at);

-- 3. Indexes (propagate to all partitions)
CREATE INDEX idx_behavior_events_broker_detected
    ON behavior_events (broker_account_id, detected_at);
CREATE INDEX idx_behavior_events_detector
    ON behavior_events (detector, detected_at);
CREATE INDEX idx_behavior_events_id ON behavior_events (id);
CREATE UNIQUE INDEX uq_behavior_events_idem
    ON behavior_events (broker_account_id, idempotency_key, detected_at)
    WHERE idempotency_key IS NOT NULL;

-- 4. Monthly partitions (Jul 2026 - Jun 2027) + safety net
CREATE TABLE behavior_events_y2026m07 PARTITION OF behavior_events FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE behavior_events_y2026m08 PARTITION OF behavior_events FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE behavior_events_y2026m09 PARTITION OF behavior_events FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE behavior_events_y2026m10 PARTITION OF behavior_events FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE behavior_events_y2026m11 PARTITION OF behavior_events FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
CREATE TABLE behavior_events_y2026m12 PARTITION OF behavior_events FOR VALUES FROM ('2026-12-01') TO ('2027-01-01');
CREATE TABLE behavior_events_y2027m01 PARTITION OF behavior_events FOR VALUES FROM ('2027-01-01') TO ('2027-02-01');
CREATE TABLE behavior_events_y2027m02 PARTITION OF behavior_events FOR VALUES FROM ('2027-02-01') TO ('2027-03-01');
CREATE TABLE behavior_events_y2027m03 PARTITION OF behavior_events FOR VALUES FROM ('2027-03-01') TO ('2027-04-01');
CREATE TABLE behavior_events_y2027m04 PARTITION OF behavior_events FOR VALUES FROM ('2027-04-01') TO ('2027-05-01');
CREATE TABLE behavior_events_y2027m05 PARTITION OF behavior_events FOR VALUES FROM ('2027-05-01') TO ('2027-06-01');
CREATE TABLE behavior_events_y2027m06 PARTITION OF behavior_events FOR VALUES FROM ('2027-06-01') TO ('2027-07-01');
CREATE TABLE behavior_events_default PARTITION OF behavior_events DEFAULT;

-- 5. Copy existing rows (pre-2026-07 rows land in DEFAULT). Required because
-- Postgres cannot convert a regular table to partitioned in place - the only
-- path is new-table + copy + swap.
INSERT INTO behavior_events (
    id, broker_account_id, detector, detector_version, severity, confidence,
    data_quality, message, evidence, input_snapshot,
    trigger_completed_trade_id, risk_alert_id, idempotency_key,
    detected_at, created_at
)
SELECT id, broker_account_id, detector, detector_version, severity, confidence,
       data_quality, message, evidence, input_snapshot,
       trigger_completed_trade_id, risk_alert_id, idempotency_key,
       detected_at, created_at
FROM behavior_events_legacy;

-- 6. Verify the copy, then KEEP the legacy table for manual cleanup.
-- Run this check - both counts must match:
--   SELECT (SELECT COUNT(*) FROM behavior_events)        AS new_count,
--          (SELECT COUNT(*) FROM behavior_events_legacy) AS legacy_count;
-- After verifying (and after a few live trading days), drop it yourself:
--   DROP TABLE behavior_events_legacy;
-- Nothing writes to or reads from the legacy table once this migration runs.

-- 7. Future partitions are AUTO-CREATED by the monthly Celery beat task
-- ensure_behavior_event_partitions (see app/tasks/maintenance_tasks.py) -
-- it idempotently creates the next 3 months. The DEFAULT partition is only
-- the safety net if that task somehow fails for months in a row.
