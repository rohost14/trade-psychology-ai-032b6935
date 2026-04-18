-- Migration 057: Discipline score + streak tracking tables

CREATE TABLE IF NOT EXISTS discipline_scores (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    week_start      DATE NOT NULL,
    score           SMALLINT NOT NULL DEFAULT 0,
    max_score       SMALLINT NOT NULL DEFAULT 100,
    danger_alerts   SMALLINT NOT NULL DEFAULT 0,
    caution_alerts  SMALLINT NOT NULL DEFAULT 0,
    trades_count    SMALLINT NOT NULL DEFAULT 0,
    avg_quality     NUMERIC(4, 2),
    breakdown       JSONB DEFAULT '{}',
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (broker_account_id, week_start)
);

CREATE INDEX IF NOT EXISTS idx_discipline_scores_account_week
    ON discipline_scores (broker_account_id, week_start DESC);

CREATE TABLE IF NOT EXISTS discipline_streaks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    streak_type     VARCHAR(60) NOT NULL,
    -- e.g. 'revenge_free', 'size_discipline', 'quality_trader', 'time_discipline'
    current_count   SMALLINT NOT NULL DEFAULT 0,
    best_count      SMALLINT NOT NULL DEFAULT 0,
    last_updated    DATE NOT NULL DEFAULT CURRENT_DATE,
    last_broken_at  TIMESTAMPTZ,
    UNIQUE (broker_account_id, streak_type)
);

CREATE INDEX IF NOT EXISTS idx_discipline_streaks_account
    ON discipline_streaks (broker_account_id);
