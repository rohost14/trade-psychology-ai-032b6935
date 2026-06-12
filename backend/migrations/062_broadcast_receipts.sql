-- Migration 062: Broadcast delivery tracking
-- broadcast_logs: one row per send action
-- broadcast_receipts: one row per user per broadcast, tracks delivery status

CREATE TABLE IF NOT EXISTS broadcast_logs (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    created_by  VARCHAR(255) NOT NULL,
    segment     VARCHAR(50)  NOT NULL,
    message     TEXT         NOT NULL,
    total       INTEGER      NOT NULL DEFAULT 0,
    sent        INTEGER      NOT NULL DEFAULT 0,
    failed      INTEGER      NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS broadcast_receipts (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    broadcast_id UUID        NOT NULL REFERENCES broadcast_logs(id) ON DELETE CASCADE,
    phone        VARCHAR(20) NOT NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'queued',  -- queued | sent | failed
    error        TEXT,
    sent_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_broadcast_receipts_broadcast_id ON broadcast_receipts(broadcast_id);
CREATE INDEX IF NOT EXISTS idx_broadcast_receipts_status       ON broadcast_receipts(status);
CREATE INDEX IF NOT EXISTS idx_broadcast_logs_created_at       ON broadcast_logs(created_at DESC);
