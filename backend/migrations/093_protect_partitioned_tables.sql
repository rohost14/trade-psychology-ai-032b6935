-- 093: make the partitioned tables refuse to be dropped by accident
--
-- WHAT THIS IS FOR
--
-- On 2026-09-03, 344 order rows were destroyed by ONE statement. Migration 090
-- was re-run by hand against an already-partitioned `orders`; the rename moved
-- the live table aside WITH its 24 partitions and all its rows, every
-- CREATE ... PARTITION OF then failed on a name still held by the moved table's
-- children, the INSERT failed for want of a partition — and then
--
--     DROP TABLE orders_legacy
--
-- succeeded, taking the partitions and the data with it. Only that one
-- statement had to work. The project is on a Supabase plan with no backups and
-- Kite serves no order history beyond the current day, so the rows are gone.
--
-- Every protection we already have sits in the wrong place to have stopped it:
--
--   * scripts/migrate.py cannot re-run a recorded migration - but the statement
--     was not run through the runner
--   * 090 is wrapped in BEGIN/COMMIT - but it was executed statement by
--     statement with error recovery, so the transaction never protected anything
--   * the retention job's snapshot gate and MAX_DROPS_PER_RUN cap - but this
--     was not the retention job
--   * the test suite - it asserts against migration FILE TEXT, so it stayed
--     green throughout
--
-- The one thing they have in common is that they all assume the drop arrives
-- through a path we control. This does not. An event trigger lives in the
-- DATABASE and fires for every session, every tool and every human: psql, a
-- migration file, an ORM, an agent with a connection string. It is the only
-- layer that sees the statement that actually did the damage.
--
-- WHAT IT BLOCKS
--
-- Dropping `orders` or `behavior_events`, any monthly partition of either, their
-- DEFAULT partitions, or anything left under a `_legacy` name. Note that
-- dropping a partitioned PARENT cascades to its children and reports each one
-- to this trigger, which is exactly why the fatal `DROP TABLE orders_legacy`
-- would have been caught: the parent had been renamed, but its partitions were
-- still called orders_yYYYYmMM.
--
-- HOW LEGITIMATE DROPS STILL WORK
--
-- Retention genuinely needs to drop a partition a month. It announces itself:
--
--     SET LOCAL tm.allow_drop = 'on';
--     DROP TABLE orders_y2026m02;
--
-- SET LOCAL dies with the transaction, so the permission cannot leak into the
-- next statement, let alone the next session. `app/tasks/maintenance_tasks.py`
-- sets it immediately before each drop and nowhere else.
--
-- This is deliberately a SPEED BUMP, not a vault. Anyone who means it can set
-- the flag or drop the trigger. That is the right strength: it cannot stop a
-- determined operator, and it does stop the accident - a stray statement, a
-- re-run migration, a tool doing something nobody reviewed. The 090 re-run was
-- an accident, and an accident is what this catches.

CREATE OR REPLACE FUNCTION tm_block_protected_drops()
RETURNS event_trigger
LANGUAGE plpgsql
AS $$
DECLARE
    obj RECORD;
BEGIN
    -- The escape hatch. Checked once: if this transaction has announced itself,
    -- there is nothing to police.
    IF coalesce(current_setting('tm.allow_drop', true), '') = 'on' THEN
        RETURN;
    END IF;

    FOR obj IN SELECT * FROM pg_event_trigger_dropped_objects()
    LOOP
        IF obj.object_type IN ('table', 'table partition')
           AND obj.schema_name = 'public'
           AND obj.object_name ~ '^(orders|behavior_events)(_legacy|_default|_y[0-9]{4}m[0-9]{2})?$'
        THEN
            RAISE EXCEPTION
                'REFUSING to drop protected table "%": it holds trading data '
                'that cannot be recovered (no backups on this plan, and Kite '
                'serves no order history beyond today). If this is the '
                'retention job or a deliberate migration, announce it first: '
                'SET LOCAL tm.allow_drop = ''on'';',
                obj.object_name
            USING ERRCODE = 'insufficient_privilege',
                  HINT = 'See migration 093. 344 order rows were lost to an '
                         'unguarded DROP on 2026-09-03.';
        END IF;
    END LOOP;
END;
$$;

COMMENT ON FUNCTION tm_block_protected_drops() IS
    'Event-trigger guard: refuses DROP on orders/behavior_events and their '
    'partitions unless the transaction sets tm.allow_drop = on. See 093.';

DROP EVENT TRIGGER IF EXISTS tm_protect_partitioned_tables;
CREATE EVENT TRIGGER tm_protect_partitioned_tables
    ON sql_drop
    EXECUTE FUNCTION tm_block_protected_drops();
