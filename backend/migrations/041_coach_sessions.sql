-- Migration 041: coach_sessions table (P-04)
--
-- Stores chat conversation history per broker account.
-- Last 3 sessions are summarized and injected into the system prompt
-- so the AI coach remembers context across conversations.
--
-- messages JSONB: [{role: "user"|"assistant", content: "...", ts: "ISO"}]
-- summary TEXT: auto-generated summary of the session (for prompt injection)

CREATE TABLE IF NOT EXISTS coach_sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id   UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    messages            JSONB NOT NULL DEFAULT '[]',
    summary             TEXT,            -- generated after session ends
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at            TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_coach_sessions_account_started
    ON coach_sessions (broker_account_id, started_at DESC);
