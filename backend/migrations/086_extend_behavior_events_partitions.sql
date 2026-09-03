-- 086: extend the behavior_events monthly partitions through 2027-12
--
-- WHY THIS EXISTS
--
-- 067 partitioned `behavior_events` and declared fourteen monthly partitions,
-- from 2026-07 to 2027-06. Only four of them were ever created: a live schema
-- check on 2026-09-03 found y2026m07 through y2026m10 and nothing after. The
-- file was later extended, so the file on disk stopped describing the database
-- — which is exactly the hazard `schema_migrations.checksum` exists to catch,
-- and it is why 067 is recorded as PENDING rather than adopted.
--
-- Coverage therefore ended 2026-10-31, eight weeks out. Nothing would have
-- failed loudly: `behavior_events_default` exists and would have swallowed
-- every row from November onwards. Partitioning would simply have stopped
-- working, silently, which is the worst way for it to go.
--
-- WHAT THIS DOES
--
-- Creates every month from 2026-11 to 2027-12 inclusive. That is the ten
-- 067 declared but never created, plus six more.
--
-- SAFE TO RUN, AND WHY
--
-- * `IF NOT EXISTS` on every statement, so it is idempotent and re-runnable.
-- * The DEFAULT partition held ZERO rows when this was written. Attaching a
--   partition whose range overlaps rows already sitting in DEFAULT requires a
--   full scan and fails if any are found; with an empty default there is
--   nothing to move and nothing to block.
-- * Bounds are written with an explicit +05:30 offset rather than bare dates.
--   067 used bare dates and the server's TimeZone (Asia/Kolkata) resolved
--   them, so its bounds are 00:00+05:30. A bare date applied from a session in
--   another timezone would land on a different absolute instant and would not
--   abut y2026m10's upper bound — leaving a gap or an overlap. Explicit
--   offsets remove the dependency on who runs this and from where.
-- * No index work is needed: all four of the parent's indexes are PARTITIONED
--   indexes (pg_class.relkind = 'I'), so each new partition inherits them on
--   creation.
--
-- KEEPING IT FROM EXPIRING AGAIN
--
-- `backend/tests/test_partition_runway.py` fails when the newest declared
-- partition is less than six months away. It reads the migration files, not
-- the database, so it runs in CI and fails months before production degrades.
-- That is the protection: a test that goes red on a calendar, long before a
-- partition is actually needed.

CREATE TABLE IF NOT EXISTS behavior_events_y2026m11 PARTITION OF behavior_events
    FOR VALUES FROM ('2026-11-01 00:00:00+05:30') TO ('2026-12-01 00:00:00+05:30');
CREATE TABLE IF NOT EXISTS behavior_events_y2026m12 PARTITION OF behavior_events
    FOR VALUES FROM ('2026-12-01 00:00:00+05:30') TO ('2027-01-01 00:00:00+05:30');
CREATE TABLE IF NOT EXISTS behavior_events_y2027m01 PARTITION OF behavior_events
    FOR VALUES FROM ('2027-01-01 00:00:00+05:30') TO ('2027-02-01 00:00:00+05:30');
CREATE TABLE IF NOT EXISTS behavior_events_y2027m02 PARTITION OF behavior_events
    FOR VALUES FROM ('2027-02-01 00:00:00+05:30') TO ('2027-03-01 00:00:00+05:30');
CREATE TABLE IF NOT EXISTS behavior_events_y2027m03 PARTITION OF behavior_events
    FOR VALUES FROM ('2027-03-01 00:00:00+05:30') TO ('2027-04-01 00:00:00+05:30');
CREATE TABLE IF NOT EXISTS behavior_events_y2027m04 PARTITION OF behavior_events
    FOR VALUES FROM ('2027-04-01 00:00:00+05:30') TO ('2027-05-01 00:00:00+05:30');
CREATE TABLE IF NOT EXISTS behavior_events_y2027m05 PARTITION OF behavior_events
    FOR VALUES FROM ('2027-05-01 00:00:00+05:30') TO ('2027-06-01 00:00:00+05:30');
CREATE TABLE IF NOT EXISTS behavior_events_y2027m06 PARTITION OF behavior_events
    FOR VALUES FROM ('2027-06-01 00:00:00+05:30') TO ('2027-07-01 00:00:00+05:30');
CREATE TABLE IF NOT EXISTS behavior_events_y2027m07 PARTITION OF behavior_events
    FOR VALUES FROM ('2027-07-01 00:00:00+05:30') TO ('2027-08-01 00:00:00+05:30');
CREATE TABLE IF NOT EXISTS behavior_events_y2027m08 PARTITION OF behavior_events
    FOR VALUES FROM ('2027-08-01 00:00:00+05:30') TO ('2027-09-01 00:00:00+05:30');
CREATE TABLE IF NOT EXISTS behavior_events_y2027m09 PARTITION OF behavior_events
    FOR VALUES FROM ('2027-09-01 00:00:00+05:30') TO ('2027-10-01 00:00:00+05:30');
CREATE TABLE IF NOT EXISTS behavior_events_y2027m10 PARTITION OF behavior_events
    FOR VALUES FROM ('2027-10-01 00:00:00+05:30') TO ('2027-11-01 00:00:00+05:30');
CREATE TABLE IF NOT EXISTS behavior_events_y2027m11 PARTITION OF behavior_events
    FOR VALUES FROM ('2027-11-01 00:00:00+05:30') TO ('2027-12-01 00:00:00+05:30');
CREATE TABLE IF NOT EXISTS behavior_events_y2027m12 PARTITION OF behavior_events
    FOR VALUES FROM ('2027-12-01 00:00:00+05:30') TO ('2028-01-01 00:00:00+05:30');
