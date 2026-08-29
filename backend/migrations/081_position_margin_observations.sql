-- 081: per-position broker margin observations
--
-- NOT YET APPLIED. This project has no migration runner and no
-- schema_migrations table; applied state lives in prose. Apply by hand and
-- record it. All code that reads this table degrades to "no observation"
-- when it is missing, so an unapplied migration is safe: the risk layer
-- simply abstains on futures and short options, exactly as it does today.
--
-- WHY A NEW TABLE
--
-- margin_snapshots already exists and is ACCOUNT-level utilisation from
-- kite.margins(). It cannot answer "what did this position require".
--
-- This table is append-only. A broker margin is an observation of a fact at a
-- moment, and volatility moves, so a row is never updated and never
-- recomputed. A later COMPUTED estimate must never overwrite an earlier
-- BROKER observation.

CREATE TABLE IF NOT EXISTS position_margin_observations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id   UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,

    -- When the broker was asked. The figure is only meaningful with this.
    captured_at         TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- What was asked about. `legs` is the exact payload sent to Kite, so the
    -- observation can always be explained after the fact.
    exchange            VARCHAR(20),
    underlying          VARCHAR(100),
    product             VARCHAR(20),
    leg_count           INTEGER NOT NULL DEFAULT 1,
    legs                JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Kite's own breakdown for the whole structure.
    span                NUMERIC(18, 4),
    exposure            NUMERIC(18, 4),
    option_premium      NUMERIC(18, 4),
    additional          NUMERIC(18, 4),
    total               NUMERIC(18, 4),

    -- Per-leg margins keyed by tradingsymbol, from the basket response's
    -- `orders` array. Needed because a detector reasons about ONE trade while
    -- margin is a property of the structure.
    per_leg             JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- 'basket' when spread benefit was applied across legs, 'orders' when the
    -- legs were charged independently. Never collapse the two.
    basis               VARCHAR(16) NOT NULL DEFAULT 'basket',
    -- Always 'broker' here. The column exists so a reader never has to assume.
    margin_source       VARCHAR(16) NOT NULL DEFAULT 'broker',

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The lookup the risk layer performs: latest observation for an account and
-- underlying at or before a point in time.
CREATE INDEX IF NOT EXISTS idx_pmo_account_underlying_time
    ON position_margin_observations (broker_account_id, underlying, captured_at DESC);

CREATE INDEX IF NOT EXISTS idx_pmo_account_time
    ON position_margin_observations (broker_account_id, captured_at DESC);

COMMENT ON TABLE position_margin_observations IS
    'Append-only broker margin observations per position/structure. Never '
    'updated, never recomputed. A COMPUTED estimate must not overwrite one.';
