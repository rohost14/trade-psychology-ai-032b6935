-- 071_admin_iam.sql — Admin IAM: session invalidation + forced first-login setup.
--
-- session_epoch      : bumped on force-logout / deactivate / role-change / password reset.
--                      The current epoch is embedded in each admin JWT as `sv`; deps rejects
--                      a token whose `sv` != the row's session_epoch → instant revoke of ALL
--                      of that admin's tokens without waiting for the 8h expiry.
-- must_change_password: set when an admin is created/reset with a temp password. The app forces
--                      a password change on next login before granting access.
-- totp_required      : set on create / reset-TOTP. Forces TOTP enrolment on next login.
-- created_by         : email of the superadmin who created this admin (audit trail).

ALTER TABLE admin_users
    ADD COLUMN IF NOT EXISTS session_epoch        INTEGER      NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS must_change_password  BOOLEAN      NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS totp_required         BOOLEAN      NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS created_by            VARCHAR(255);
