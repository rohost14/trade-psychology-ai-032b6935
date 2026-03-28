-- Migration 053: Store per-user KiteConnect api_secret (encrypted)
-- Allows users to bring their own KiteConnect app credentials
-- before the developer obtains Zerodha multi-user partnership.
--
-- api_key is already stored in broker_accounts (added in earlier migrations).
-- api_secret_enc stores the Fernet-encrypted api_secret so we can re-sign
-- token exchange requests using the user's own credentials.

ALTER TABLE broker_accounts
    ADD COLUMN IF NOT EXISTS api_secret_enc VARCHAR;

COMMENT ON COLUMN broker_accounts.api_secret_enc IS
    'Fernet-encrypted KiteConnect api_secret. NULL = use global server credentials.';
