-- Migration 032: Create users table — stable identity above broker accounts
--
-- One user owns one-or-many broker_accounts.
-- Guardian contact moves from broker_accounts → users (belongs to the human).
-- JWT sub = user.id, JWT bid = broker_account.id.
--
-- ─────────────────────────────────────────────────────────────────
-- HOW TO RUN
-- Run the entire file in Supabase SQL editor in one go.
-- If you already ran part of it and hit the NOT NULL error, jump to
-- the "RESUME FROM HERE" section at the bottom of this file.
-- ─────────────────────────────────────────────────────────────────


-- ─────────────────────────────────────────────────────────────────
-- 1. Create users table
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,
    display_name    TEXT,
    avatar_url      TEXT,
    guardian_phone  TEXT,
    guardian_name   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);


-- ─────────────────────────────────────────────────────────────────
-- 2. Migrate existing broker_accounts → create user rows
--    Uses broker_email as the stable identity key.
--    Migrates guardian_phone/guardian_name before dropping those columns.
-- ─────────────────────────────────────────────────────────────────

-- 2a. Insert a user row for every unique email in broker_accounts
INSERT INTO users (email, avatar_url, guardian_phone, guardian_name, created_at)
SELECT DISTINCT ON (broker_email)
    broker_email,
    avatar_url,
    guardian_phone,
    guardian_name,
    COALESCE(created_at, now())
FROM broker_accounts
WHERE broker_email IS NOT NULL
  AND broker_email != ''
ORDER BY broker_email, created_at ASC
ON CONFLICT (email) DO NOTHING;

-- 2b. Link each broker_account to its user row
UPDATE broker_accounts ba
SET user_id = u.id
FROM users u
WHERE ba.broker_email = u.email
  AND ba.broker_email IS NOT NULL
  AND ba.broker_email != '';

-- 2c. Any accounts still with user_id = NULL have no broker_email.
--     These are dev/test rows — real Zerodha accounts always have a KYC email.
--     Delete them so the NOT NULL constraint below can be applied cleanly.
--     (If you have a test account you want to keep, set its broker_email first.)
DELETE FROM broker_accounts
WHERE user_id IS NULL
  AND (broker_email IS NULL OR broker_email = '');

-- 2d. Verify: this must return 0 rows before continuing.
--     If it returns rows, a real account was missed — investigate before proceeding.
--     SELECT id, broker_email, user_id FROM broker_accounts WHERE user_id IS NULL;


-- ─────────────────────────────────────────────────────────────────
-- 3. Add NOT NULL constraint + FK on broker_accounts.user_id
-- ─────────────────────────────────────────────────────────────────
ALTER TABLE broker_accounts
    ALTER COLUMN user_id SET NOT NULL;

ALTER TABLE broker_accounts
    ADD CONSTRAINT fk_broker_accounts_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_broker_accounts_user_id ON broker_accounts(user_id);


-- ─────────────────────────────────────────────────────────────────
-- 4. Drop guardian columns from broker_accounts
--    Data already migrated to users table in step 2a above.
-- ─────────────────────────────────────────────────────────────────
ALTER TABLE broker_accounts
    DROP COLUMN IF EXISTS guardian_phone,
    DROP COLUMN IF EXISTS guardian_name;


-- ═════════════════════════════════════════════════════════════════
-- RESUME FROM HERE — if you already ran steps 1-2 and hit the
-- NOT NULL error on step 3, run only the statements below.
-- ═════════════════════════════════════════════════════════════════

-- R1. Delete any accounts with no email (dev test data).
--     DELETE FROM broker_accounts
--     WHERE user_id IS NULL
--       AND (broker_email IS NULL OR broker_email = '');

-- R2. Verify zero nulls remain (must return 0 rows before continuing).
--     SELECT id, broker_email FROM broker_accounts WHERE user_id IS NULL;

-- R3. Once the above returns 0 rows, run steps 3 and 4:
--     ALTER TABLE broker_accounts ALTER COLUMN user_id SET NOT NULL;
--
--     ALTER TABLE broker_accounts
--         ADD CONSTRAINT fk_broker_accounts_user
--             FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
--
--     CREATE INDEX IF NOT EXISTS idx_broker_accounts_user_id ON broker_accounts(user_id);
--
--     ALTER TABLE broker_accounts
--         DROP COLUMN IF EXISTS guardian_phone,
--         DROP COLUMN IF EXISTS guardian_name;
