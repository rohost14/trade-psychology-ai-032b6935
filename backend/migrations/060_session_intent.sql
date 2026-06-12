-- Migration 060: morning intent columns on trading_sessions
--
-- Adds per-session intent acknowledgement + optional limit overrides.
-- Users commit to their plan before market open; EOD comparison uses
-- intent_max_trades / intent_max_loss vs actual session metrics.
--
-- If intent_max_trades / intent_max_loss are NULL the profile defaults
-- (daily_trade_limit / daily_loss_limit from user_profiles) are used.

ALTER TABLE trading_sessions
    ADD COLUMN IF NOT EXISTS intent_acknowledged    BOOLEAN     NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS intent_max_trades      INTEGER,
    ADD COLUMN IF NOT EXISTS intent_max_loss        NUMERIC(15,4),
    ADD COLUMN IF NOT EXISTS intent_time            TIMESTAMPTZ;
