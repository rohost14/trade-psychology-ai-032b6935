-- Add token_revoked_at column for JWT revocation support
-- When a user disconnects, this timestamp is set.
-- On reconnect, it is cleared back to NULL.
-- The auth dependency checks this to reject revoked JWTs.

ALTER TABLE broker_accounts
ADD COLUMN IF NOT EXISTS token_revoked_at TIMESTAMP WITH TIME ZONE;
