-- 072_admin_login_events.sql — persistent admin login history (who/when/where/how).
-- Written on every successful 2nd-factor verify. Complements the Redis session
-- registry (active/live sessions) with a durable audit trail of logins.

CREATE TABLE IF NOT EXISTS admin_login_events (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id     UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    admin_email  TEXT NOT NULL,
    ip           TEXT,
    user_agent   TEXT,
    method       TEXT NOT NULL,          -- 'email_otp' | 'totp' | 'dev_bypass'
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_login_events_admin_time
    ON admin_login_events (admin_id, created_at DESC);
