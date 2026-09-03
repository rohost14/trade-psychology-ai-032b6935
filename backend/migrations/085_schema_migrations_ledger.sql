-- 085: a ledger of which migrations have been applied
--
-- THE PROBLEM THIS SOLVES
--
-- There are dozens of migration files in this directory and no record anywhere of
-- which of them have been run. Applied state has lived in prose, and the prose
-- disagrees with itself: MEMORY.md says 077 is unapplied, docs/PENDING.md says
-- it was applied 2026-08-04, and nothing in the repository can settle it. That
-- matters because 077 adds `positions.entry_price_source`, and until it is
-- applied `sync_positions` cannot write positions at all.
--
-- Deliberately NOT Alembic. Migrations here are hand-written SQL applied by
-- hand, several are edited after the fact, and a framework that wants to own
-- schema generation would fight that. What was missing is not a framework; it
-- is a place to write down what happened.
--
-- checksum is sha256 of the file's bytes at the moment it was recorded. It
-- exists to catch the specific hazard of this repo: a migration edited AFTER
-- being applied, where the file on disk no longer describes the database.
--
-- applied_by distinguishes a migration the runner executed ("runner") from one
-- adopted as already-applied during the one-time backfill ("adopt"), so the
-- backfill can never be mistaken for evidence that the SQL ran here.

CREATE TABLE IF NOT EXISTS schema_migrations (
    filename    TEXT PRIMARY KEY,
    checksum    TEXT NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    applied_by  TEXT NOT NULL DEFAULT 'runner',
    note        TEXT
);

COMMENT ON TABLE schema_migrations IS
    'Which files in backend/migrations/ have been applied. Written by '
    'scripts/migrate.py. applied_by=adopt means recorded as already-applied '
    'without being executed here.';
