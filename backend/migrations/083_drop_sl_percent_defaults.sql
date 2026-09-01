-- Migration 083: drop the vestigial column defaults on sl_percent_options and
-- sl_percent_futures, and NULL the one inert sl_percent_futures value.
--
-- WHY
--
-- Migration 028 added both columns with a DEFAULT:
--
--     ALTER TABLE user_profiles ADD COLUMN ... sl_percent_futures FLOAT DEFAULT 1.0;
--     ALTER TABLE user_profiles ADD COLUMN ... sl_percent_options FLOAT DEFAULT 50.0;
--
-- In Postgres `ADD COLUMN ... DEFAULT` BACKFILLS every existing row, so every
-- profile that predated 028 was written those values by the migration itself,
-- with no user involved.
--
-- The defaults are VESTIGIAL for the application. Verified against the live
-- database in a rolled-back transaction:
--
--     ORM  UserProfile(broker_account_id=x)  ->  sl_percent_options = NULL
--                                                sl_percent_futures = NULL
--     RAW  INSERT (id, broker_account_id)    ->  (50.0, 1.0)
--
-- The SQLAlchemy model declares no Python-side default for either column, so
-- the ORM sends an explicit NULL and the DB default never applies on the path
-- the application actually uses. Only raw SQL and 028's own backfill ever wrote
-- them. Dropping the defaults therefore changes NO application behaviour - it
-- removes a trap for future raw inserts and makes "the trader has not declared
-- this rule" representable, which is what `threshold_resolution` now expects
-- after the 2026-09-01 provenance fix.
--
-- WHY sl_percent_futures IS NULLED AND sl_percent_options IS NOT
--
-- sl_percent_futures is INERT. Both threshold resolvers put it into the
-- threshold dict and NOTHING consumes it - no detector, no task, no live path -
-- and it is not in `constitution_service.RULE_FIELDS`. Setting it to NULL
-- cannot change any alert, because nothing reads it.
--
-- sl_percent_options is NOT inert and NOT touched here. Pattern #8 (2026-08-27)
-- promoted it to a RULE_FIELD, so the live premium-loss path raises it as a
-- `constitution_violation`. Its stored value is genuinely AMBIGUOUS:
--
--   * `ProfileTab` renders presets [30, 50, 70, 100] and highlights the
--     fallback `?? 50`, so 50 is both the default shown as selected and a
--     legitimate click - the two are indistinguishable in the column.
--   * `constitution_history` cannot settle it either: the one affected profile
--     was last updated 2026-07-30, BEFORE the field became a RULE_FIELD on
--     2026-08-27, so a Settings save at that time would have written no history
--     row. Absence of history is not evidence of absence of choice.
--
-- One profile holds 50.0 and it is the only account with real trades. Nulling
-- it could discard a rule the trader chose; leaving it could keep one they did
-- not. That needs the trader's answer, not a migration's guess, so this
-- migration DELIBERATELY LEAVES IT ALONE.
--
-- cooldown_after_loss is NOT touched. Its default is intentional product
-- behaviour: `generate_defaults` returns a per-experience value (15/10/5/5) and
-- the onboarding wizard renders it as a slider the trader sees and submits. It
-- is an always-on rule with a suggested value, not an opt-in rule.
--
-- AFFECTED ROWS, verified before running:
--
--   sl_percent_futures = 1.0  ->  exactly 1 row (profile a7927997, acct d5cf0bf0)
--   sl_percent_options        ->  0 rows changed
--   cooldown_after_loss       ->  0 rows changed
--
-- REVERSIBILITY: fully reversible, and the down-migration is at the bottom of
-- this file. Restoring the defaults is one statement each. The single nulled
-- value is recorded here verbatim (sl_percent_futures = 1.0 on profile
-- a7927997) so it can be put back exactly.
--
-- APPLIED 2026-09-02. Verified after running:
--   sl_percent_options  column_default -> NULL   (was 50.0)
--   sl_percent_futures  column_default -> NULL   (was 1.0)
--   profile a7927997    sl_percent_futures 1.0 -> NULL   (1 row)
--   profile a7927997    sl_percent_options 50.0 -> UNCHANGED
--   cooldown_after_loss default 15 and all row values UNCHANGED
--   a raw INSERT omitting the columns now yields (NULL, NULL, 15)
--
-- Evidence: docs/DEEP_REVIEW/NON_NULL_DEFAULTS_INVESTIGATION.md

BEGIN;

-- 1. Drop the defaults. No row values change here.
ALTER TABLE user_profiles ALTER COLUMN sl_percent_options DROP DEFAULT;
ALTER TABLE user_profiles ALTER COLUMN sl_percent_futures DROP DEFAULT;

-- 2. NULL the one inert value. Scoped to the exact default so a trader who
--    genuinely picked a different futures stop (0.5, 1.5, 2, 3 are the other
--    presets) is untouched.
UPDATE user_profiles
   SET sl_percent_futures = NULL
 WHERE sl_percent_futures = 1.0;

COMMIT;

-- ---------------------------------------------------------------------------
-- DOWN (not run automatically)
--
--   ALTER TABLE user_profiles ALTER COLUMN sl_percent_options SET DEFAULT 50.0;
--   ALTER TABLE user_profiles ALTER COLUMN sl_percent_futures SET DEFAULT 1.0;
--   UPDATE user_profiles SET sl_percent_futures = 1.0
--    WHERE id = 'a7927997-a3b5-4b15-a813-830604dc30a6';  -- the single row nulled
--
-- Note that restoring the DEFAULT does NOT re-backfill existing rows; that is
-- what `ADD COLUMN ... DEFAULT` did in 028 and is not repeated by SET DEFAULT.
-- ---------------------------------------------------------------------------
