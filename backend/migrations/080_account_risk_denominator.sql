-- 080_account_risk_denominator.sql
--
-- Gives account-relative risk a stable, session-scoped denominator, and records
-- which one was used.
--
-- WHY THIS IS NEEDED
--
-- Every "how much of the account did this cost" rule needs an account size to
-- divide by. Until now there was no agreed answer, so `session_meltdown`
-- invented one inline (5% of declared capital) and nothing else could reuse it.
--
-- The obvious candidate was wrong. `margin_snapshots.equity_total` is stored as
-- `live_balance` — Kite's *current* balance, which moves with M2M and margin
-- utilisation through the session. Using it would mean a trader's "equity"
-- shrinks the moment they take risk, so a 5%-of-equity floor gets EASIER to
-- breach as the day goes worse. Backwards.
--
-- Kite's /user/margins returns `available.opening_balance`, documented as
-- "Opening balance at the day start". That is stable across the session and is
-- the honest answer to "how big is this account today". Our own client
-- docstring omitted the field, which is why it was nearly missed.
--
-- WHY IT IS SESSION-SCOPED
--
-- A deposit or withdrawal mid-session must not silently reinterpret the whole
-- day's risk. If a trader adds funds at 13:00, the morning's alerts were
-- computed against the morning's account and must stay that way. So the
-- denominator is resolved ONCE per session, stored on the session row, and used
-- unchanged until the next one — with its source, timestamp and quality
-- recorded so a stale or guessed figure can never masquerade as live truth.
--
-- FALLBACK ORDER (implemented in app/core/account_risk.py)
--
--   1. opening_balance from a margin snapshot taken during this session
--   2. the most recent opening_balance we have, if not too old  (quality PARTIAL)
--   3. the trader's declared trading_capital                    (quality PARTIAL)
--   4. nothing — the engine ABSTAINS from account-relative rules (quality UNKNOWN)
--
-- Never live_balance. It is deliberately absent from the chain.

BEGIN;

-- ── The field Kite gives us and we were not storing ──────────────────────────
ALTER TABLE margin_snapshots
    ADD COLUMN IF NOT EXISTS equity_opening_balance NUMERIC(18, 2);

COMMENT ON COLUMN margin_snapshots.equity_opening_balance IS
    'Kite available.opening_balance — balance at day start. Stable across the '
    'session, unlike equity_total which stores live_balance and moves with '
    'utilisation. This is the canonical account-risk denominator.';

-- ── The denominator actually used for a given session ───────────────────────
ALTER TABLE trading_sessions
    ADD COLUMN IF NOT EXISTS risk_denominator NUMERIC(18, 2),
    ADD COLUMN IF NOT EXISTS risk_denominator_source TEXT,
    ADD COLUMN IF NOT EXISTS risk_denominator_as_of TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS risk_denominator_quality TEXT;

COMMENT ON COLUMN trading_sessions.risk_denominator IS
    'Account size every account-relative rule divided by during THIS session. '
    'Resolved once and frozen: a mid-session deposit or withdrawal must not '
    'retroactively change what the morning''s alerts meant.';

COMMENT ON COLUMN trading_sessions.risk_denominator_source IS
    'opening_balance | opening_balance_stale | declared_capital — which rung of '
    'the fallback chain answered. Never live_balance.';

COMMENT ON COLUMN trading_sessions.risk_denominator_quality IS
    'GOOD | PARTIAL | UNKNOWN. PARTIAL means the figure is real but stale or '
    'self-reported; UNKNOWN means account-relative rules abstained entirely.';

-- Constraint rather than convention: an unrecognised source is a bug, and a
-- denominator that silently became live_balance is the specific bug this
-- migration exists to prevent.
ALTER TABLE trading_sessions
    DROP CONSTRAINT IF EXISTS ck_trading_sessions_risk_denominator_source;
ALTER TABLE trading_sessions
    ADD CONSTRAINT ck_trading_sessions_risk_denominator_source
    CHECK (
        risk_denominator_source IS NULL
        OR risk_denominator_source IN (
            'opening_balance', 'opening_balance_stale', 'declared_capital'
        )
    );

ALTER TABLE trading_sessions
    DROP CONSTRAINT IF EXISTS ck_trading_sessions_risk_denominator_quality;
ALTER TABLE trading_sessions
    ADD CONSTRAINT ck_trading_sessions_risk_denominator_quality
    CHECK (
        risk_denominator_quality IS NULL
        OR risk_denominator_quality IN ('GOOD', 'PARTIAL', 'UNKNOWN')
    );

COMMIT;
