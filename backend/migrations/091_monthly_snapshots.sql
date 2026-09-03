-- 091: immutable monthly snapshots, so retention never costs a trader their history
--
-- WHY
--
-- `orders` retention drops a month at a time (migration 090 partitioned it for
-- exactly that). Before a month can be dropped, what it said must be recorded
-- somewhere permanent, and the drop must be refused until that has happened and
-- been verified.
--
-- WHAT IS AND IS NOT AT RISK — worth being exact, because it is easy to
-- over-claim what a snapshot is protecting.
--
-- Dropping an `orders` partition does NOT delete trades, P&L, rule violations
-- or detector events. Those live in completed_trades, risk_alerts and
-- behavior_events, none of which is under retention (behavior_events is
-- explicitly never dropped). A monthly summary of them would survive with or
-- without this table.
--
-- What IS lost with the partition is the order-level record: how many orders
-- were placed, how many were cancelled or rejected, and the protective-stop
-- evidence F4 reads - SL/SL-M placement, trigger prices, modifications. Those
-- have no other home, so they are the part this table genuinely rescues. The
-- trade and behaviour aggregates are stored alongside them so one row can
-- render a month without fanning out across four tables.
--
-- IMMUTABLE BY CONVENTION, enforced by the writer: a snapshot is written once
-- per (account, month) and never rewritten, because a summary that can change
-- after the raw data is gone is not a record of anything. The unique constraint
-- makes re-generation a no-op rather than an overwrite.
--
-- VERSIONED, because the numbers are only interpretable against the code that
-- produced them. A detector retired next year must not make an old month look
-- wrong - it makes it OLD, which is a different thing and needs to be legible.

CREATE TABLE IF NOT EXISTS monthly_snapshots (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id   UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    -- First day of the month it summarises, in IST. The natural key.
    month               DATE NOT NULL,

    -- The aggregates. JSONB rather than columns because the set will grow as
    -- detectors change, and a snapshot's shape must be readable against the
    -- version stamped beside it rather than migrated to match today's code.
    metrics             JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- What produced these numbers.
    snapshot_version    INTEGER NOT NULL DEFAULT 1,
    detector_version    TEXT,

    -- Set when the orders partition for this month has actually been dropped,
    -- so the UI can say "detailed orders are no longer available" honestly
    -- rather than implying the raw data is still there.
    orders_pruned_at    TIMESTAMPTZ,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_monthly_snapshot_account_month UNIQUE (broker_account_id, month)
);

CREATE INDEX IF NOT EXISTS idx_monthly_snapshots_account_month
    ON monthly_snapshots (broker_account_id, month DESC);

COMMENT ON TABLE monthly_snapshots IS
    'Immutable per-account monthly summary. Written and verified BEFORE the '
    'corresponding orders partition may be dropped; kept indefinitely.';
