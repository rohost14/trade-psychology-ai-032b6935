-- 092: repair `orders` — restore its partitions, its foreign key and its trigger
--
-- WHAT WENT WRONG
--
-- 090 partitioned `orders`. On 2026-09-03 it was run a SECOND time, outside
-- scripts/migrate.py (the runner cannot do this: cmd_apply filters
-- `n not in recorded`, and no second ledger row exists), against a database
-- where `orders` was ALREADY partitioned, and without a transaction around it.
--
-- That sequence is destructive in one specific way:
--
--   ALTER TABLE orders RENAME TO orders_legacy   -- moves the GOOD table aside,
--                                                -- and with it all 24 partitions
--                                                -- and all 344 rows
--   CREATE TABLE orders (LIKE orders_legacy ...) -- builds a fresh empty shell
--   CREATE TABLE orders_default PARTITION OF ... -- FAILS: name still held by
--                                                -- the legacy table's own child
--   CREATE TABLE orders_yYYYYmMM PARTITION OF .. -- FAILS, all 23, same reason
--   INSERT INTO orders SELECT * FROM orders_legacy -- FAILS: no partition for row
--   DROP TABLE orders_legacy                     -- SUCCEEDS. This is the loss.
--
-- Only the last statement had to succeed for the data to go, and it did.
--
-- STATE THIS FILE FOUND
--
--   orders             relkind='p', RANGE (order_timestamp)   -- partitioned
--   partitions         NONE. Not even DEFAULT.
--   rows               0     (344 before; `trades` still references 269
--                             distinct kite_order_id across Feb-Jul 2026)
--   FK                 GONE  -- orders was the ONLY table in the database with
--                            -- a broker_account_id and no FK to broker_accounts
--   trigger            GONE  -- update_orders_updated_at
--   table comment      GONE
--   PK / UNIQUE        intact, correct 3-column form
--   6 indexes          intact, each exactly once, 0 attached children
--
-- A partitioned table with no partitions and no DEFAULT cannot accept ANY row.
-- Every order write was failing with "no partition of relation orders found for
-- row", and failing silently: webhooks.py logs it non-fatal, trade_tasks.py
-- retries and gives up. So no stop-loss, cancellation or rejection evidence was
-- being captured at all, and F4's stop-evidence query read an empty table.
--
-- WHY THE FK AND TRIGGER WERE MISSING IN THE FIRST PLACE
--
-- 090 built the new table with
--   CREATE TABLE orders (LIKE orders_legacy INCLUDING DEFAULTS INCLUDING COMMENTS)
-- LIKE copies columns, types, NOT NULL and (with INCLUDING DEFAULTS) defaults.
-- It does NOT copy foreign keys - not even with INCLUDING CONSTRAINTS - nor
-- triggers, nor the TABLE comment (INCLUDING COMMENTS covers column comments,
-- which is why those survived). So the FK from 017 and the trigger from 010
-- were lost the FIRST time 090 ran, silently, and would have stayed lost.
--
-- WHY THIS IS A NEW FILE AND NOT A RE-RUN OF 090
--
-- Re-running 090 is precisely what caused the damage. 090 is written to convert
-- an unpartitioned table and is not safe to apply twice. This file only ADDS
-- what is missing and is safe to run repeatedly.
--
-- ORDER MATTERS: orders_default IS CREATED FIRST
--
-- Deliberately, before the monthly partitions. A DEFAULT partition is what turns
-- any future recurrence of this from silent data loss into a visible signal: a
-- row that belongs to no declared month lands there and is COUNTED (the admin
-- panel reports default occupancy and drives a critical health state off it)
-- instead of raising an error that both call sites swallow. It is also what lets
-- a back-dated tradebook CSV import land at all.
--
-- THE 344 ROWS ARE NOT RECOVERABLE FROM HERE. Kite serves no order history
-- beyond the current day, so a database backup taken before 2026-09-03 18:30 UTC
-- is the only route to them. This file restores the STRUCTURE so that writes
-- work again from now on; it does not pretend to restore the data.

BEGIN;

-- ── 1. the safety net, first ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders_default PARTITION OF orders DEFAULT;

-- ── 2. the declared window ────────────────────────────────────────────────
-- Same range 090 declared: Feb 2026 (the first month with data) through Dec
-- 2027. The maintenance beat keeps rolling the far end forward; these are the
-- floor. Historical months are included because a Console CSV import is
-- back-dated by nature and must not land in DEFAULT by default.
CREATE TABLE IF NOT EXISTS orders_y2026m02 PARTITION OF orders FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE IF NOT EXISTS orders_y2026m03 PARTITION OF orders FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE IF NOT EXISTS orders_y2026m04 PARTITION OF orders FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE IF NOT EXISTS orders_y2026m05 PARTITION OF orders FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE IF NOT EXISTS orders_y2026m06 PARTITION OF orders FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE IF NOT EXISTS orders_y2026m07 PARTITION OF orders FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE IF NOT EXISTS orders_y2026m08 PARTITION OF orders FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE IF NOT EXISTS orders_y2026m09 PARTITION OF orders FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE IF NOT EXISTS orders_y2026m10 PARTITION OF orders FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE IF NOT EXISTS orders_y2026m11 PARTITION OF orders FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
CREATE TABLE IF NOT EXISTS orders_y2026m12 PARTITION OF orders FOR VALUES FROM ('2026-12-01') TO ('2027-01-01');
CREATE TABLE IF NOT EXISTS orders_y2027m01 PARTITION OF orders FOR VALUES FROM ('2027-01-01') TO ('2027-02-01');
CREATE TABLE IF NOT EXISTS orders_y2027m02 PARTITION OF orders FOR VALUES FROM ('2027-02-01') TO ('2027-03-01');
CREATE TABLE IF NOT EXISTS orders_y2027m03 PARTITION OF orders FOR VALUES FROM ('2027-03-01') TO ('2027-04-01');
CREATE TABLE IF NOT EXISTS orders_y2027m04 PARTITION OF orders FOR VALUES FROM ('2027-04-01') TO ('2027-05-01');
CREATE TABLE IF NOT EXISTS orders_y2027m05 PARTITION OF orders FOR VALUES FROM ('2027-05-01') TO ('2027-06-01');
CREATE TABLE IF NOT EXISTS orders_y2027m06 PARTITION OF orders FOR VALUES FROM ('2027-06-01') TO ('2027-07-01');
CREATE TABLE IF NOT EXISTS orders_y2027m07 PARTITION OF orders FOR VALUES FROM ('2027-07-01') TO ('2027-08-01');
CREATE TABLE IF NOT EXISTS orders_y2027m08 PARTITION OF orders FOR VALUES FROM ('2027-08-01') TO ('2027-09-01');
CREATE TABLE IF NOT EXISTS orders_y2027m09 PARTITION OF orders FOR VALUES FROM ('2027-09-01') TO ('2027-10-01');
CREATE TABLE IF NOT EXISTS orders_y2027m10 PARTITION OF orders FOR VALUES FROM ('2027-10-01') TO ('2027-11-01');
CREATE TABLE IF NOT EXISTS orders_y2027m11 PARTITION OF orders FOR VALUES FROM ('2027-11-01') TO ('2027-12-01');
CREATE TABLE IF NOT EXISTS orders_y2027m12 PARTITION OF orders FOR VALUES FROM ('2027-12-01') TO ('2028-01-01');

-- ── 3. the foreign key LIKE dropped (originally migration 017) ─────────────
-- ON DELETE CASCADE is what makes a user-initiated account deletion
-- (api/account_data.py issues a hard DELETE FROM users) reach `orders`.
-- Without it those rows would be orphaned by a deletion that reports success.
-- The table is empty, so this cannot fail validation.
ALTER TABLE orders DROP CONSTRAINT IF EXISTS orders_broker_account_id_fkey;
ALTER TABLE orders
    ADD CONSTRAINT orders_broker_account_id_fkey
    FOREIGN KEY (broker_account_id)
    REFERENCES broker_accounts(id)
    ON DELETE CASCADE;

-- ── 4. the trigger LIKE dropped (originally migration 010) ─────────────────
-- Low impact today, because both ON CONFLICT DO UPDATE blocks in
-- trade_sync_service set updated_at explicitly. It matters for any other
-- UPDATE path, which would otherwise leave the column stale forever.
DROP TRIGGER IF EXISTS update_orders_updated_at ON orders;
CREATE TRIGGER update_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ── 5. the table comment INCLUDING COMMENTS did not carry ─────────────────
COMMENT ON TABLE orders IS 'All orders including cancelled/rejected for order flow analysis';

COMMIT;
