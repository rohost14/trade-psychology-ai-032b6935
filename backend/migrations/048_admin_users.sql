-- Migration 048: Admin users table
-- Separate auth system for admin panel — independent of Zerodha OAuth.
-- OTPs are stored in Redis (TTL-based), not in this table.

CREATE TABLE IF NOT EXISTS admin_users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name          VARCHAR(255) NOT NULL,
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_admin_users_email ON admin_users(email);

COMMENT ON TABLE admin_users IS 'Admin panel users — separate from trader accounts. Password-based auth + email OTP.';
