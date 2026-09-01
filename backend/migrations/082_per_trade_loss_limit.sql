-- 082: per-trade loss limit — a new optional trader rule
--
-- NOT YET APPLIED. This project has no migration runner and no
-- schema_migrations table; applied state lives in prose. Apply by hand and
-- record it.
--
-- MUST BE APPLIED BEFORE THE CODE SHIPS. An earlier draft of this comment
-- claimed the migration was safe to leave unapplied. THAT WAS WRONG, and it was
-- caught by running the suite: adding the column to the SQLAlchemy model makes
-- every `SELECT user_profiles.*` name it, so with the column missing every
-- profile load raises
--
--     asyncpg.exceptions.UndefinedColumnError:
--     column user_profiles.per_trade_loss_limit does not exist
--
-- 34 tests failed on exactly that. The engine degrades ("profile load failed,
-- using defaults") rather than crashing, but a trader would silently lose EVERY
-- declared rule, not just this one.
--
-- The threshold layer's own reads are still defensive - `getattr(profile,
-- "per_trade_loss_limit", None)` - so an object without the attribute is fine.
-- What is not fine is the query that builds the object.
--
-- Order of operations: apply this migration, THEN deploy.
--
-- WHAT IT IS
--
-- The maximum RAW realised loss the trader is willing to take on ONE position,
-- in rupees. It joins daily_loss_limit (the day) and max_position_size (capital
-- committed) as the third money rule, and like both of those it is:
--
--   * OPT-IN. NULL until the trader explicitly enables it. There is NO
--     suggested value — the product is for F&O traders and we have no evidence
--     for a recommended per-trade loss figure, so we do not invent one.
--   * enforced by `constitution_violation`, not by a new detector.
--   * measured against RAW P&L, consistent with every other figure in the
--     product: (exit - entry) x qty x multiplier, no brokerage, no STT, no tax.
--
-- POSITION-LEVEL, NOT FILL-LEVEL. A CompletedTrade is written only when the
-- position returns to zero, so its realized_pnl already sums every exit
-- tranche. Splitting an exit cannot evade the limit. Measured on the reference
-- book: 8 of 740 rounds closed in more than one tranche, all as single rows.
--
-- MULTI-LEG IS A KNOWN LIMITATION, NOT A DESIGN. Netting a spread's legs was
-- approved in principle and then measured as unusable: strategy grouping keys
-- on "same underlying, entered within 15 minutes", 45% of grouped rounds have
-- no closed sibling at their own exit (so the same structure would be judged
-- leg-level then net-level), and 29 of 48 candidate pairs are the same option
-- type — a spread or two independent bets, indistinguishable. This rule
-- therefore measures each leg separately and does NOT read strategy_group.
-- See docs/patterns/24-constitution_violation/per_trade_loss_limit_semantics.md.

ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS per_trade_loss_limit DOUBLE PRECISION;

COMMENT ON COLUMN user_profiles.per_trade_loss_limit IS
    'Max RAW realised loss on a single position, in rupees. NULL = rule not set. '
    'Opt-in, never suggested. Enforced by constitution_violation at exit.';
