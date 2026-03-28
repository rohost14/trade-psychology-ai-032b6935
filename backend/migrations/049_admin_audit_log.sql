-- Migration 049: Admin audit log
-- Persistent record of every admin action. Replaces app-logger-only trail.

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_email VARCHAR(255) NOT NULL,
    action      VARCHAR(100) NOT NULL,   -- 'login', 'suspend_user', 'unsuspend_user',
                                         -- 'send_message', 'set_maintenance',
                                         -- 'set_announcement', 'broadcast'
    target_type VARCHAR(50),             -- 'user', 'config', 'system', 'global'
    target_id   VARCHAR(255),            -- account_id, 'global', etc.
    details     JSONB,                   -- arbitrary context (truncated message, flags, etc.)
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_audit_log_created ON admin_audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_admin   ON admin_audit_log(admin_email);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_action  ON admin_audit_log(action);

COMMENT ON TABLE admin_audit_log IS
    'Immutable log of every admin panel action. Never delete rows from this table.';
