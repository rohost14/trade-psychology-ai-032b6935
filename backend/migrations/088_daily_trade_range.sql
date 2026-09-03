-- 088: the daily trade rule becomes a RANGE the trader declares
--
-- WHY
--
-- Onboarding captured one number on a 1-50 slider and called it "Max Trades
-- Per Day". A single number cannot say what a trader actually means, which is
-- normally an intended band: "I take three to five trades on a normal day".
--
-- The MAXIMUM is the only half that can be breached, so it stays where it is,
-- in `daily_trade_limit`. That keeps the constitution gate untouched - lower is
-- still tighter, tightening still applies instantly, loosening still needs the
-- override path - and it keeps every existing reader correct without a rename.
--
-- This adds the lower half. `daily_trade_min` is INFORMATIONAL: it records what
-- the trader considers a normal day so the range can be shown back to them and
-- edited as a range. Nothing alerts on it. A trader who takes fewer trades than
-- they intended has not broken a rule, and inventing an alert for it would be
-- exactly the kind of unrequested judgement this product does not make.
--
-- NULLABLE and unset by default, like every other opt-in rule. A profile with
-- daily_trade_limit set and daily_trade_min NULL is valid and behaves exactly
-- as it does today.

ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS daily_trade_min INTEGER;

COMMENT ON COLUMN user_profiles.daily_trade_min IS
    'Lower half of the trader''s declared daily trade range. Informational: the '
    'breach point is daily_trade_limit (the maximum). NULL when undeclared.';
