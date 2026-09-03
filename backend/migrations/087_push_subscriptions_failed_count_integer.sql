-- 087: push_subscriptions.failed_count is a counter, so make it an integer
--
-- WHY
--
-- `PushSubscription.failed_count` is declared `Column(Integer, default=0)` in
-- app/models/push_subscription.py, and the schema declares `failed_count: int`.
-- The live column is `character varying`. The ORM and the database have
-- disagreed about this column's type since the table was created.
--
-- HOW IT GOT THIS WAY
--
-- Migration 018 was supposed to fix it, alongside widening a long list of price
-- columns to NUMERIC(15,4). A schema check on 2026-09-03 found 018 was never
-- applied: `trades.price` is still numeric(10,2). The rest of 018 is dead
-- letter -- the models were later written to Numeric(10,2), which is what the
-- database already has, so applying 018 now would make the database disagree
-- with the ORM in the other direction. 018 is recorded as SKIP for that reason.
--
-- This is the one part of 018 still worth doing, lifted out on its own.
--
-- SAFE
--
-- Every value in the column is either NULL or a small integer written by
-- `push_notification_service`, so the USING cast cannot fail on real data. The
-- table is small and rarely written. Idempotent via the DO block: re-running
-- after the type is already integer does nothing.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'push_subscriptions'
          AND column_name = 'failed_count'
          AND data_type <> 'integer'
    ) THEN
        -- The existing default is '0'::character varying, and Postgres will
        -- not cast a default automatically along with the column, so it has to
        -- come off first and go back on afterwards.
        ALTER TABLE push_subscriptions
            ALTER COLUMN failed_count DROP DEFAULT;
        ALTER TABLE push_subscriptions
            ALTER COLUMN failed_count TYPE INTEGER
            USING NULLIF(failed_count::text, '')::integer;
        ALTER TABLE push_subscriptions
            ALTER COLUMN failed_count SET DEFAULT 0;
    END IF;
END $$;
