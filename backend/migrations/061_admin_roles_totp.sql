-- Migration 061: Admin roles + TOTP secret
-- Adds role-based access control and TOTP MFA support to admin_users.

ALTER TABLE admin_users
    ADD COLUMN IF NOT EXISTS role           VARCHAR(50) NOT NULL DEFAULT 'superadmin',
    ADD COLUMN IF NOT EXISTS totp_secret_enc TEXT;

COMMENT ON COLUMN admin_users.role IS 'superadmin | ops | support';
COMMENT ON COLUMN admin_users.totp_secret_enc IS 'Fernet-encrypted pyotp base32 secret. NULL = TOTP not configured (uses email OTP).';

CREATE INDEX IF NOT EXISTS idx_admin_users_role ON admin_users(role);
