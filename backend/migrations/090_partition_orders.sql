-- 090: partition `orders` by month on order_timestamp
--
-- WHY NOW, AT 344 ROWS
--
-- `orders` was a low-volume table when the EOD sync was its only writer. Since
-- 2026-09-03 every order lifecycle state is persisted, so a stop trailed
-- through a session writes on each move. Measured today: 344 rows = 128 kB of
-- data and 200 kB of indexes, about 250 bytes a row, indexes costing more than
-- the rows. At the 1M-trades/day target that is roughly 7M rows and ~1.75 GB a
-- day, ~450 GB a year.
--
-- The trigger for partitioning is usually "when it hurts". Doing it then means
-- rewriting a 50M-row table behind a maintenance window. Doing it at 344 rows
-- is instantaneous and carries no operational risk, so the cheap moment is now
-- and the expensive moment is later. Nothing about the growth estimate is
-- needed to justify that ordering.
--
-- WHAT CHANGES, AND THE ONE THING TO WATCH
--
-- Postgres requires the partition key in every UNIQUE constraint, so
--
--     UNIQUE (broker_account_id, kite_order_id)
--  -> UNIQUE (broker_account_id, kite_order_id, order_timestamp)
--
-- and every ON CONFLICT target moves with it (upsert_order, sync_orders_to_db).
--
-- That is only safe because order_timestamp is the order's PLACEMENT time and
-- does not change across its lifecycle - Kite resends the same value on every
-- update for that order, so a modify still lands on the same row in the same
-- partition. If it ever varied, one order could exist twice in two partitions.
-- Two things hold that down: the column becomes NOT NULL here (0 of 344 rows
-- are null, and the webhook already rejects payloads with no timestamps at
-- all), and `upsert_order` falls back to exchange_timestamp then now() so the
-- write path cannot produce a null.
--
-- A DEFAULT partition catches anything outside the declared months rather than
-- failing the insert. Rows landing there are a signal, not a loss.
--
-- Retention is NOT implemented here. Partitioning is what makes retention a
-- DROP TABLE later instead of a mass DELETE; choosing the window is a separate
-- decision.

BEGIN;

ALTER TABLE orders RENAME TO orders_legacy;

ALTER INDEX IF EXISTS uq_orders_account_kite_id      RENAME TO uq_orders_account_kite_id_legacy;
ALTER INDEX IF EXISTS idx_orders_account_date        RENAME TO idx_orders_account_date_legacy;
ALTER INDEX IF EXISTS idx_orders_status              RENAME TO idx_orders_status_legacy;
ALTER INDEX IF EXISTS idx_orders_symbol              RENAME TO idx_orders_symbol_legacy;
ALTER INDEX IF EXISTS idx_orders_broker_account_id   RENAME TO idx_orders_broker_account_id_legacy;
ALTER INDEX IF EXISTS idx_orders_account_symbol_time RENAME TO idx_orders_account_symbol_time_legacy;

CREATE TABLE orders (
    LIKE orders_legacy INCLUDING DEFAULTS INCLUDING COMMENTS
) PARTITION BY RANGE (order_timestamp);

ALTER TABLE orders ALTER COLUMN order_timestamp SET NOT NULL;

ALTER TABLE orders ADD PRIMARY KEY (id, order_timestamp);
ALTER TABLE orders ADD CONSTRAINT uq_orders_account_kite_id
    UNIQUE (broker_account_id, kite_order_id, order_timestamp);

CREATE INDEX idx_orders_account_symbol_time
    ON orders (broker_account_id, tradingsymbol, order_timestamp);
CREATE INDEX idx_orders_account_date ON orders (broker_account_id, order_timestamp);
CREATE INDEX idx_orders_status       ON orders (broker_account_id, status);
CREATE INDEX idx_orders_symbol       ON orders (tradingsymbol);

-- Anything outside the declared months, including back-dated rows.
CREATE TABLE orders_default PARTITION OF orders DEFAULT;

-- Cover the existing data (Feb-Jul 2026) and forward to the end of 2027. The
-- maintenance beat keeps rolling the window; these are the floor.
CREATE TABLE orders_y2026m02 PARTITION OF orders FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE orders_y2026m03 PARTITION OF orders FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
CREATE TABLE orders_y2026m04 PARTITION OF orders FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE orders_y2026m05 PARTITION OF orders FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE orders_y2026m06 PARTITION OF orders FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE orders_y2026m07 PARTITION OF orders FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE orders_y2026m08 PARTITION OF orders FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE orders_y2026m09 PARTITION OF orders FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE orders_y2026m10 PARTITION OF orders FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE orders_y2026m11 PARTITION OF orders FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
CREATE TABLE orders_y2026m12 PARTITION OF orders FOR VALUES FROM ('2026-12-01') TO ('2027-01-01');
CREATE TABLE orders_y2027m01 PARTITION OF orders FOR VALUES FROM ('2027-01-01') TO ('2027-02-01');
CREATE TABLE orders_y2027m02 PARTITION OF orders FOR VALUES FROM ('2027-02-01') TO ('2027-03-01');
CREATE TABLE orders_y2027m03 PARTITION OF orders FOR VALUES FROM ('2027-03-01') TO ('2027-04-01');
CREATE TABLE orders_y2027m04 PARTITION OF orders FOR VALUES FROM ('2027-04-01') TO ('2027-05-01');
CREATE TABLE orders_y2027m05 PARTITION OF orders FOR VALUES FROM ('2027-05-01') TO ('2027-06-01');
CREATE TABLE orders_y2027m06 PARTITION OF orders FOR VALUES FROM ('2027-06-01') TO ('2027-07-01');
CREATE TABLE orders_y2027m07 PARTITION OF orders FOR VALUES FROM ('2027-07-01') TO ('2027-08-01');
CREATE TABLE orders_y2027m08 PARTITION OF orders FOR VALUES FROM ('2027-08-01') TO ('2027-09-01');
CREATE TABLE orders_y2027m09 PARTITION OF orders FOR VALUES FROM ('2027-09-01') TO ('2027-10-01');
CREATE TABLE orders_y2027m10 PARTITION OF orders FOR VALUES FROM ('2027-10-01') TO ('2027-11-01');
CREATE TABLE orders_y2027m11 PARTITION OF orders FOR VALUES FROM ('2027-11-01') TO ('2027-12-01');
CREATE TABLE orders_y2027m12 PARTITION OF orders FOR VALUES FROM ('2027-12-01') TO ('2028-01-01');

INSERT INTO orders SELECT * FROM orders_legacy WHERE order_timestamp IS NOT NULL;

DROP TABLE orders_legacy;

COMMIT;
