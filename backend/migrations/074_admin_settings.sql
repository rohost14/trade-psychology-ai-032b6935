-- 074_admin_settings.sql — runtime global settings controllable from the admin panel
-- (feature kill-switches, signup gate, AI model overrides) without a redeploy.
-- Durable source of truth; a Redis cache (admin:settings) fronts it for cheap sync reads.
-- Anything unset falls back to code defaults, so the table being empty = current behaviour.

CREATE TABLE IF NOT EXISTS admin_settings (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL,
    updated_by  TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
