-- Migration 037: trading_sessions table
--
-- One row per (broker_account, trading_day).
-- Tracks session P&L, risk score (0-100), and state machine.
--
-- risk_score is internal only — never shown to users directly.
-- It drives alert escalation and session state transitions.
--
-- session_state: normal → caution → danger → blowup
--   normal:  risk_score 0-39
--   caution: risk_score 40-69
--   danger:  risk_score 70-89
--   blowup:  risk_score 90-100
--
-- After this migration, add the FK from position_ledger.session_id.

CREATE TABLE IF NOT EXISTS trading_sessions (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id    UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    -- Session identity
    session_date         DATE NOT NULL,
    market_open          TIMESTAMPTZ,             -- 09:15 IST on session_date
    market_close         TIMESTAMPTZ,             -- 15:30 IST on session_date

    -- Equity snapshots
    opening_equity       NUMERIC(15,4),           -- margin at market open
    closing_equity       NUMERIC(15,4),           -- margin at market close

    -- Aggregated session metrics (updated incrementally as trades arrive)
    session_pnl          NUMERIC(15,4) NOT NULL DEFAULT 0,
    trade_count          INT           NOT NULL DEFAULT 0,
    alerts_fired         INT           NOT NULL DEFAULT 0,

    -- Risk tracking (internal, never surfaced directly to user)
    risk_score           NUMERIC(5,2)  NOT NULL DEFAULT 0,  -- current 0-100
    peak_risk_score      NUMERIC(5,2)  NOT NULL DEFAULT 0,  -- highest reached today

    -- State machine
    session_state        TEXT NOT NULL DEFAULT 'normal',
    -- CHECK: session_state IN ('normal', 'caution', 'danger', 'blowup')

    -- Timestamps
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- One session per account per day
    UNIQUE (broker_account_id, session_date)
);

CREATE INDEX IF NOT EXISTS idx_trading_sessions_account_date
    ON trading_sessions (broker_account_id, session_date DESC);

-- Now that trading_sessions exists, add the FK from position_ledger
ALTER TABLE position_ledger
    ADD CONSTRAINT fk_position_ledger_session
    FOREIGN KEY (session_id) REFERENCES trading_sessions(id)
    ON DELETE SET NULL;

-- Add CHECK constraint for session_state
ALTER TABLE trading_sessions
    ADD CONSTRAINT chk_session_state
    CHECK (session_state IN ('normal', 'caution', 'danger', 'blowup'));
