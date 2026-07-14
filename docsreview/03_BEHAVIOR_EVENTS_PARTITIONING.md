# behavior_events Partitioning — Design, History, Operations
*P2 Runtime Architecture Migration · finalized 2026-07-15*

## 1. Why partition this table at all

`behavior_events` is the engine's evidence log: every detection writes a row.
The Principal Engineer review (S8) ranked it the **first thing that breaks at
scale** — at the 50k-user target it takes 5–15M rows/day of JSONB-heavy data.

Two problems on a normal (unpartitioned) table at that volume:

1. **Retention.** Evidence older than ~90–180 days must be removed. On a
   normal table that's `DELETE ... WHERE detected_at < X` over millions of
   rows: hours of runtime, table bloat, vacuum pressure, index churn. On a
   partitioned table it's `DROP TABLE behavior_events_y2026m07;` — an
   instant metadata operation.
2. **Query locality.** Scores, death spiral, and analytics only ever read
   recent windows. Partition pruning means those queries touch one or two
   month-tables instead of scanning years of history.

**Why we did it NOW, at ~zero rows:** Postgres cannot convert an existing
table to partitioned in place. The only path is new-table + copy + swap.
With 0 rows that swap is free; with a billion rows it is a weekend outage.
We paid the cost while the cost was nothing.

## 2. Why MONTHLY child tables — and what they actually are

Postgres declarative partitioning physically stores each range as its own
child table (`behavior_events_y2026m07`, `..m08`, ...). This is plumbing,
not schema you manage:

- Application code reads and writes **only `behavior_events`** — Postgres
  routes every row to the right child automatically (verified live: a test
  insert landed in `behavior_events_y2026m07`).
- Monthly granularity matches the retention unit (drop whole months) and
  keeps per-partition size sane at target volume (~150–450M rows/month →
  still large; sub-monthly granularity is a later knob if ever needed).

## 3. History: original design → user challenge → final design

| | Original (067 v1) | Final (067 v2 + task) |
|---|---|---|
| Future partitions | 12 pre-created (Jul'26–Jun'27), **manual** yearly addition documented in a comment | **Auto-created by a Celery beat task** — rolling window of current month + 3 ahead |
| After the pre-created range ran out | Rows silently fall into the DEFAULT partition; nothing errors, but DEFAULT grows unbounded and the partitioning benefit quietly evaporates — a manual chore that **fails silently** | Cannot happen while the task runs; DEFAULT demoted to pure safety net |
| Legacy table after copy | `DROP TABLE` in the migration | **Kept** as `behavior_events_legacy`; drop is an explicit manual step after verification |

Both changes came from a direct user challenge ("create tables by hand for
lifetime?", "why drop legacy?") — both were correct.

## 4. The Celery job

**Task:** `app.tasks.maintenance_tasks.ensure_behavior_event_partitions`
**Schedule:** 1st and 15th of every month, 02:00 IST (twice monthly purely
for redundancy — the task is idempotent).

What it does each run:
1. For current month + 3 months ahead: check `pg_tables` for
   `behavior_events_yYYYYmMM`.
2. If missing → `CREATE TABLE ... PARTITION OF behavior_events FOR VALUES
   FROM (month-start) TO (next-month-start)`.
3. Existing partitions are skipped — running it twice, or after a missed
   month, is harmless.

Month arithmetic is unit-tested including year rollover (Dec→Jan). Failure
retries twice with 5-min backoff and logs ERROR. Even a task dead for
3+ months only means rows land in DEFAULT — data is never lost, and rows
can be re-homed from DEFAULT later.

## 5. Two schema consequences of partitioning (accepted, documented)

Postgres requires unique constraints on partitioned tables to include the
partition key. Therefore:

- **No DB-level primary key.** The table is append-only evidence; nothing
  joins into it by `id`. The ORM keeps its declarative `id` pk (mapper
  only); the DB keeps `id` as an indexed plain uuid column.
- **The idempotency unique index is `(broker_account_id, idempotency_key,
  detected_at)`.** Semantics preserved because `detected_at` is
  deterministic per key — the engine always sets it to the trigger trade's
  exit time, so a retry/re-sync produces the identical tuple and still
  conflicts. This assumption is load-bearing: if detected_at semantics
  ever change for keyed events, revisit this index.

## 6. Current live state (verified 2026-07-15)

- `behavior_events` — partitioned parent (relkind `p`), 4 indexes
- Partitions: `y2026m07 … y2026m10` (created via the task's own logic —
  the automation is proven live) + `behavior_events_default`
- Insert routing verified (test row → y2026m07, rolled back)
- `behavior_events_legacy` — **0 rows** (the engine had never run live
  before the swap, so the copy step was a no-op). Safe to drop whenever:
  `DROP TABLE behavior_events_legacy;`

## 7. Ops runbook

| Action | Command / where |
|---|---|
| Check partitions exist | `SELECT tablename FROM pg_tables WHERE tablename LIKE 'behavior_events_y%' ORDER BY 1;` |
| Retention (drop a month older than policy) | `DROP TABLE behavior_events_y2026m07;` |
| DEFAULT partition should stay empty | `SELECT COUNT(*) FROM behavior_events_default;` — nonzero means the beat task missed months; create the proper partitions, then re-home rows |
| Force partition creation now | trigger `ensure_behavior_event_partitions` from admin tasks / celery |
| Drop the legacy shell | `DROP TABLE behavior_events_legacy;` (0 rows, safe now) |

Retention policy itself (90 vs 180 days, cold archive before drop) is a
product decision deferred until real volume exists.
