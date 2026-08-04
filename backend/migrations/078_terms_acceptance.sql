-- 078_terms_acceptance.sql
--
-- Record Terms of Service acceptance against the user instead of a browser variable.
--
-- The landing page gated its "Connect Zerodha" button behind a React useState
-- checkbox. That state resets on every page load, and because Kite access tokens
-- expire daily, the user re-ticked the same box every single day — while nothing
-- was ever persisted. There was no answer to "prove this user accepted the terms".
--
-- Acceptance is now stamped in two places, both explicit:
--   1. the Zerodha OAuth callback, where pressing the button IS the acceptance
--      (clickwrap by action — what every broker-connected Indian app does), and
--      only when no acceptance exists yet, so an older version is never silently
--      overwritten;
--   2. POST /api/legal/accept, the explicit re-acceptance after a material change.
--
-- Existing rows are left NULL on purpose rather than backfilled with a fabricated
-- timestamp: we do not know when or whether those users accepted anything. They
-- are stamped on their next login. A backfill here would be inventing legal
-- evidence, which is worse than having none.
--
-- Idempotent. Safe to re-run.

ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_version     VARCHAR(20);

COMMENT ON COLUMN users.terms_accepted_at IS
    'When this user last accepted the Terms of Service. NULL = predates migration 078; stamped on next login.';
COMMENT ON COLUMN users.terms_version IS
    'Which Terms version was accepted (see backend/app/core/legal.py CURRENT_TERMS_VERSION). Older than current triggers a one-time re-acceptance interstitial.';
