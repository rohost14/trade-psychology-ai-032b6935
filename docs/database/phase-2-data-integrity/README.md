# Phase 2 — Data Integrity (the two HIGH findings)

**Involves a schema change and a migration. Highest care of any phase.**

Audit source: `../DATABASE_ARCHITECTURE_AUDIT.md` (frozen).
Depends on: **Phase 1** — so the fix is provable and cannot silently regress.

---

## H1 · `behavior_events` has no primary key

**Audit:** §5.2, §7.6, §19.1 · DATA INTEGRITY / CRITICAL · Severity high · Confidence HIGH

The only addressable table in the database with no primary key constraint. What
exists instead is a **non-unique** index on `id`:

```
idx_behavior_events_id     CREATE INDEX        ... USING btree (id)          <-- NOT unique
uq_behavior_events_idem    CREATE UNIQUE INDEX ... (broker_account_id, idempotency_key)
```

The sibling partitioned table does it correctly:

```
orders_pkey                PRIMARY KEY (id, order_timestamp)
```

**Current data is clean** — 0 duplicate ids, 0 null ids, 0 duplicate idempotency
keys. The defect is the absent guarantee, not present corruption. Severity is
high for the missing invariant, not for damage already done.

**The question to answer before writing any migration:** was the omission
deliberate? A partitioned table's primary key **must include the partition key**,
so the PK here would have to be `(id, detected_at)` rather than `(id)`. Someone
may have declined that deliberately. If so the correct outcome is different —
document the constraint, prove the unique index is sufficient, and H1 becomes
GOOD WITH NOTE rather than a schema change.

**Do not assume it was an accident.** `orders` shows the team knows how to do
composite partitioned PKs.

### M18 · `idempotency_key` is nullable and 2 rows are NULL

**Audit:** §14.6 · DATA INTEGRITY · Severity medium · Confidence HIGH

```
behavior_events total       145
idempotency_key IS NULL       2
distinct idempotency_key    143
```

This is part of the same fix. In PostgreSQL **NULLs do not collide in a unique
index**, so `uq_behavior_events_idem` gives those two rows no protection at all.
Combined with the missing PK, they have **no uniqueness guarantee of any kind**.

Both documented writers construct a key unconditionally
(`behavior_engine.py:664`, `trade_tasks.py:522`), so a third path must have
produced them. Finding that path is part of this work.

**Proof for H1 + M18:** re-run the audit queries
(`count(*) - count(DISTINCT id)`, the null-key count); assert the constraint
exists in the *live* DB via Phase 1's assertions; confirm the synthetic pipeline
still writes events after the change.

---

## H2 · `journal_entries.trade_id` is polymorphic and 35% dangling

**Audit:** §6.5, §10.2, §19.2 · DATA INTEGRITY · Severity high · Confidence HIGH

```
total rows                    : 20
trade_id IS NOT NULL          : 20   (100% populated)
matching trades.id            :  0   <-- despite the column name
matching completed_trades.id  :  4
matching positions.id         :  9
matching nothing at all       :  7   <-- 35%
```

No foreign key. No discriminator column recording which table a row points at.

**Three separate problems needing three separate answers:**

1. **Which table is the write path supposed to target?** Read
   `backend/app/api/journal.py`. Not one row points at `trades`, so the column
   name is at best misleading and at worst has misled a past contributor.
2. **What are the 7 dangling rows?** Determine whether they predate the recent
   deletion of ~13k test accounts or were orphaned by it. That decides whether
   this is a historical artefact or an active defect with a live cause.
3. **Should the column be split?** One `uuid` meaning three things is the root
   cause. Options: add a discriminator, or split into two nullable typed columns
   each with a real FK.

**Do not simply add a foreign key.** With 7 of 20 rows dangling and the other 13
split across two different tables, an FK cannot be added without first deciding
what the column means and then dispositioning the rows — and dispositioning them
is data deletion, which needs its own explicit approval.

**Proof:** the audit's three-way match query returns 0 dangling and 0 ambiguous;
journal creation still works end-to-end through the Phase 1 synthetic fixture.

---

## Exit criteria

- [ ] H1 resolved — either a PK exists, or the deliberate omission is documented and the unique index proven sufficient
- [ ] M18 answered — no unprotected null-key rows, and the third writer identified
- [ ] H2 — column meaning decided, dangling rows dispositioned with approval, protection in place
- [ ] Phase 1 assertions cover both, so neither can regress unnoticed
- [ ] Full suite green; synthetic replay output identical before/after except for the intended change

---

# INVESTIGATION — 2026-09-06

Nothing has been changed. Phase 2's three questions are answered, and two of
them change the finding rather than confirming it.

---

## H1 — the missing primary key was DELIBERATE, and it is documented

The audit asked the right question and this phase's README insisted it be
answered before any migration: *"Do not assume it was an accident."* It was not
an accident. `migrations/067_partition_behavior_events.sql`, lines 6-17:

> *Two deliberate schema changes forced by Postgres partitioning rules (unique
> constraints must include the partition key):*
>
> *  **No PK on the partitioned table.** The table is append-only evidence;
>    nothing joins INTO it by id. The ORM keeps its declarative id pk
>    (mapper-only); the DB keeps id as an indexed uuid column.
> *  The idempotency unique index becomes `(broker_account_id,
>    idempotency_key, detected_at)`. Semantics preserved: `detected_at` is
>    deterministic for keyed events (always the trigger trade's exit time), so
>    a retry/re-sync produces the identical tuple and still conflicts.

### The audit recorded the unique index incorrectly

| | |
|---|---|
| audit §5.2 | `uq_behavior_events_idem ... (broker_account_id, idempotency_key)` |
| **live** | `UNIQUE (broker_account_id, idempotency_key, detected_at) WHERE idempotency_key IS NOT NULL` |

It already includes the partition key, and it is partial. The audit's version
omits both facts, which is what made the omission look careless. It was not:
the same migration that dropped the PK built a partition-key-inclusive unique
index, so whoever wrote it understood the rule exactly.

### The three claims in that comment, each checked

| claim | verdict |
|---|---|
| nothing joins INTO the table by id | **TRUE.** The only two uses of `BehaviorEvent.id` are `func.count(BehaviorEvent.id)` (`prometheus_metrics.py:225`) and an existence probe filtered on `(broker_account_id, trigger_completed_trade_id)` (`trade_tasks.py:212`). Neither looks a row up by id |
| current data is clean | **TRUE.** 145 rows, 0 duplicate ids, 0 null ids |
| the unique index carries the guarantee | **TRUE for keyed rows**, and 143 of 145 are keyed |

### Verdict

**H1 is GOOD WITH NOTE, not a schema change** — the outcome this phase's README
described as the correct one if the omission turned out to be deliberate.

Adding `PRIMARY KEY (id, detected_at)` would rewrite 19 partitions to buy a
guarantee on a column nothing looks up, and would not even be the same
guarantee the ORM declares — the model says `PRIMARY KEY (id)`, which a
partitioned table cannot have.

What is worth doing instead, all cheap:

1. Move the drift entry `behavior_events.-:primary_key_mismatch` from "Phase 2
   will fix it" to **permanently accepted, with migration 067 as the reason**.
   The model/DB disagreement is real and will never be resolved, so the
   baseline should say so rather than implying a pending fix.
2. Assert in `test_live_schema_invariants.py` that the unique index **exists
   and includes the partition key**. That is the guarantee actually in force,
   and right now nothing checks it.
3. Test the load-bearing assumption the migration wrote down but never pinned:
   *`detected_at` is always the trigger trade's exit time for keyed events.*
   If that ever drifts, a retry stops colliding and the idempotency guarantee
   silently disappears — with no PK behind it to catch the duplicate.

Item 3 is the real exposure here, and it is not the one the audit named.

---

## M18 — the third writer was `death_spiral`, and it is already retired

Both NULL-key rows are the same detector:

```
b00a3f58  death_spiral  critical  2026-07-29 08:26:09
120f6f46  death_spiral  caution   2026-07-30 09:18:42
```

Every other detector in the table has zero nulls across 143 rows.

`death_spiral` was retired 2026-09-02, and `_run_death_spiral` — the
`trade_tasks` path that wrote the composite after the engine had finished — was
removed with it (`trade_tasks.py:260` records the removal). That was the third
writer the README asked us to find.

Both surviving writers build the key unconditionally, so neither can produce a
NULL:

```
behavior_engine.py:664   f"{e.event_type}:{completed_trade.id}:{discriminator or rule}"
trade_tasks.py:523       f"{trade.order_id}:ledger"
```

### Verdict

**No live path can create an unkeyed event.** The two rows are residue from a
retired detector, and A1's retirement explicitly decided historical rows are
KEPT and shown as Retired.

Tightening `idempotency_key` to NOT NULL would mean either deleting those two
rows or inventing keys for them, and would also mean making the unique index
total rather than partial — a rewrite of 19 partitions to close a hole no
writer can reach. **Recommendation: leave the column nullable, add a test that
the live writers always produce a key.** That guards the thing that could
actually regress.

---

## H2 — a foreign key is IMPOSSIBLE here, by design, and the README's hypothesis is disproved

### `trade_id` is deliberately allowed to point at nothing

`journal.py:91`:

> *For open-position journaling, `trade_id` is a synthetic per-episode id that
> does not exist in any table; `source_id` carries the real position id so
> ownership can be verified. Omitted for closed trades (`trade_id` is the
> CompletedTrade id).*

`src/lib/journalKey.ts` explains why. A `Position` row is REUSED across
episodes — the same symbol+exchange+product slot is updated in place and keeps
its id — so journaling an open position by raw position id lets a future,
unrelated position on the same contract inherit an old journal entry. The fix
was to key open-position journals by a synthetic per-episode UUID derived from
(position id + IST trading date).

**So a dangling `trade_id` is not damage. For open positions it is the design.**
An FK on this column cannot be added without removing that feature.

### The 7 "dangling" rows are two different things, and the UUID version proves it

`journalKey.ts` stamps version nibble `5`; every real id in this system is a
v4 uuid4. That is a signature, and it separates them cleanly:

```
dangling rows by UUID version:   {v4: 6, v5: 1}
resolving rows by UUID version:  {v4: 13}
```

| rows | when | version | what it is |
|---|---|---|---|
| **1** | 2026-07-30 | **v5** | a synthetic per-episode id. **Dangling by design.** The only journal entry written after the synthetic-id change landed on 2026-07-15 (`362f740`) |
| **6** | 2026-04-06 and 04-07 | v4 | real ids, written before that change, pointing at `positions` rows that no longer exist |

So the audit's "35% dangling" is 5% by design and 30% historical.

### The README's hypothesis is disproved

It asked whether the dangling rows were orphaned by the deletion of ~13k test
accounts. **No.** All 20 journal entries belong to a single broker account, and
that account is still alive:

```
account d5cf0bf0   rows=20   dangling=7   2026-03-11 .. 2026-07-30
```

Nothing was orphaned by that cleanup.

### The 7 rows are not junk

Every one carries the trader's own writing, with the trade denormalised onto
the row:

```
2026-04-06  NIFTY2640722800CE     pnl=5928      99 chars of notes   plan=yes
2026-04-06  GOLDM26APR165000CE    pnl=-6.5      27 chars            plan=no   tags=["fomo"]
2026-04-06  GOLDM26APR165000CE    pnl=-6.5      74 chars
2026-04-06  NIFTY2640722800CE     pnl=5928     135 chars
2026-04-07  BAJFINANCE26APR880CE  pnl=-4912.5   37 chars
2026-04-07  BAJFINANCE26APR880CE  pnl=-4912.5   37 chars
2026-07-30  MAXHEALTH26AUG1200CE  pnl=1312.5    18 chars            plan=yes  tags=["calm"]
```

Deleting them destroys a trader's written record to satisfy a constraint that
should not exist on this column. **Do not disposition these rows.**

### The genuine defect, which the audit did not find

`source_id` is validated and then **thrown away**. `journal.py:263-273` reads it
to verify ownership; the `JournalEntry(...)` construction at line 334 does not
include it, and there is no such column on the table.

The consequence: an open-position journal entry **cannot be traced back to the
position it was written about**. The synthetic key is deliberately
unresolvable, and the real id that was in hand at write time is discarded. The
trader's note survives; the link to what it was about does not.

That is the thing worth fixing in H2, and it is an added column rather than a
constraint.

### Verdict

| | |
|---|---|
| add an FK to `trade_id` | **NO** — incompatible with the synthetic-episode design |
| delete or rewrite the 7 rows | **NO** — they are the trader's own records |
| the column is polymorphic | **True, and deliberately so.** It is a journal KEY, not a foreign key. Worth renaming in the model's docstring, not in the schema |
| `source_id` is discarded | **Real defect. Fix by persisting it**, with an FK to `positions` on new rows. Old rows cannot be backfilled — the value was never stored |

---

## What this means for the phase

Two of the three items resolve to **no schema change**, on evidence:

| item | audit said | evidence says |
|---|---|---|
| H1 | HIGH, missing PK, needs a migration | deliberate and documented in migration 067. GOOD WITH NOTE |
| M18 | 2 unprotected rows, find the third writer | writer found and already retired; no live path can produce a null |
| H2 | HIGH, 35% dangling, add protection | an FK is impossible by design; 1 of 7 is correct behaviour, 6 are historical, none are junk. The real defect is elsewhere: `source_id` is discarded |

The work that remains is small and none of it rewrites a partition.

---

# RESOLVED — 2026-09-06

## A correction that has to come first

The investigation above concluded *"no live path can create an unkeyed
event"*. **That was wrong.** There are five `BehaviorEvent` writers, not two,
and three of them set no `idempotency_key`:

```
app/tasks/maintenance_tasks.py:533       tilt_recovery      detected_at=now
app/tasks/position_monitor_tasks.py:508  position alert     detected_at=now_utc
app/tasks/position_monitor_tasks.py:722  entry shadow       detected_at=now_utc
```

`recognize_tilt_recovery` is on a Celery beat (`celery_app.py:235`). So the
audit's sentence — *"combined with the missing PK, they have no uniqueness
guarantee of any kind"* — is correct, and retiring `death_spiral` did not
close M18.

**Why the error happened, because the cause matters more than the error.** The
plan above states *"both documented writers construct a key unconditionally
(behavior_engine.py:664, trade_tasks.py:522)"*. That was inherited and repeated
without being checked, and it was wrong twice over: `trade_tasks.py:522` is a
`PositionLedger` key, not a `BehaviorEvent` one, and two writers is not five.
A plain `grep "BehaviorEvent("` would also have missed one, because
`behavior_engine.py:71` imports the model as `BehaviorEventRecord`.

The same failure produced the wrong `why` in the Phase 1 drift baseline. Both
times: an inherited claim repeated instead of enumerated.

**The fix is not a promise to be careful.** The claim is now a test that reads
the code — `tests/test_behavior_event_writers.py` walks the AST of every module
under `app/`, resolves whatever local name each binds to the model, and fails
on any construction without an `idempotency_key`. It found all three
immediately. Any claim of the form "every X does Y" belongs in a test from here.

---

## H1 — GOOD WITH NOTE. No schema change.

The omission is deliberate and documented in
`migrations/067_partition_behavior_events.sql:6-17`. Its three claims were
checked rather than taken:

| claim | verdict |
|---|---|
| nothing joins INTO the table by id | **verified** — 0 foreign keys reference `behavior_events`; the only two uses of `BehaviorEvent.id` are a `count()` aggregate and an existence probe filtered on other columns |
| the data is clean | **verified** — 145 rows, 0 duplicate ids, 0 null ids, 0 duplicates on (account, detector, detected_at, message) |
| the unique index carries the guarantee | **verified for keyed rows**, 143 of 145 |

The audit recorded the index incorrectly — as
`(broker_account_id, idempotency_key)` rather than the live
`(broker_account_id, idempotency_key, detected_at) WHERE idempotency_key IS NOT
NULL`. It already includes the partition key. That omission is what made the
missing PK look careless.

**Actions taken:**

* The baseline entry for `behavior_events.-:primary_key_mismatch` is
  reclassified **phase 0 — permanently accepted**, quoting migration 067. It
  previously said *"Phase 2 adds it after de-duplicating the existing rows"*,
  which was the audit's conclusion copied without reading the migration. **No
  primary key is being added.**
* `test_the_behavior_events_idempotency_index_exists_and_covers_the_partition_key`
  — the index is the table's only uniqueness guarantee and **nothing was
  checking that it exists**. Dropping it would have raised no error.
* `test_keyed_behavior_events_use_the_trigger_trades_exit_time` — migration 067
  wrote down the assumption its guarantee rests on and never tested it. There
  is a live path to breaking it: `behavior_engine.py:587` reads
  `completed_trade.exit_time or now`, and `exit_time` is nullable. No such
  trade exists today; the fallback does.

## M18 — FIXED with an advisory lock (superseding the section below)

The section that follows argued for documenting the gap rather than closing
it, on the grounds that the only two options were an idempotency key (useless
here) or a deterministic `detected_at` (a semantic change). **That framing
missed the standard third option and the argument was wrong.**

The correct tool for a check-then-insert race is a **transaction-scoped
advisory lock**. No schema change, no change to what these events mean, and no
key needed. `app/core/locks.py` provides `advisory_xact_lock`, applied at the
two writers that actually do a check-then-insert:

```
_tilt_recovery         lock ('tilt_recovery', account)
_fire_position_alert   lock ('position_alert', account, pattern_type)
```

The lock key is deliberately COARSER than the dedup scope it protects, which
also separates on `rule` and `symbol`. A lock finer than its check is no
protection: two racers would take different locks and both proceed.

`_persist_shadow_events` gets no lock on purpose — it does no check-then-insert,
writing one row per detected event unconditionally, so there is no read to race.

**`pg_advisory_xact_lock`, never `pg_advisory_lock`.** This database is reached
through the Supabase transaction pooler (port 6543, PgBouncer transaction
mode). A session-scoped lock would be returned to the pool at COMMIT while
still held and later inherited by an unrelated client. The transaction-scoped
call is released by the server at COMMIT — the same boundary PgBouncer recycles
on — so the two agree exactly.

**Proved by racing it, not asserted.** `tests/test_advisory_locks.py` runs two
real transactions on two real connections and interleaves them:

| test | result |
|---|---|
| the race WITHOUT the lock, on `behavior_events` | **duplicate reproduced**, 2 rows |
| the same race WITH the lock | B blocks, then sees A's row and declines — 1 row |
| ROLLBACK between lock and write | lock released; a crashed task cannot strand it |
| the same key hashes identically | two callers naming one thing actually contend |

The first test matters as much as the second: a guard whose failure mode has
never been observed is one nobody can trust.

**A finding from building it.** The race was first attempted on
`data_quality_events` and could not be reproduced there at all — that table
carries `uq_dq_events_daily`, so the database rejects the second insert itself.
That is the rule worth keeping: **where a unique constraint is possible, use
it.** On a partitioned table keyed by an observation timestamp it is not
possible, and that is the only reason a lock is the answer here.

**The guard caught its own flaw.** `UNKEYED_WRITERS_ALLOWED` was keyed on
`file:line`, so adding the lock shifted every line and the allowlist began
excusing lines that had moved — worse than no allowlist. It is now keyed on the
enclosing FUNCTION, which survives edits and says what the writer is. Re-keying
also corrected a name I had guessed: the shadow writer is
`_persist_shadow_events`.

---

## M18 — the original analysis, kept because the reasoning is still half right

**Adding keys to the three writers would not protect them.** The unique index
is on `(broker_account_id, idempotency_key, detected_at)` and all three set
`detected_at` from the processing clock. Two runs produce two different
`detected_at` values, so the tuples differ and nothing collides — with or
without a key. Adding one would look like protection while providing none.

Making `detected_at` deterministic instead would change what these events mean:
they record a moment of observation, not a trade's exit. That is a product
decision, not a constraint fix.

Each is instead protected in application code, verified by reading it:

| writer | protection |
|---|---|
| `tilt_recovery` | explicit read-before-write directly above the insert; skips if a `tilt_recovery` event already exists for the account since the IST day start |
| position alert | written inside `_fire_position_alert`, which returns without writing when a 30-minute escalation-aware dedup window already covers the alert |
| entry shadow | `shadow=True`, `data_quality=PARTIAL`; excluded from every trader-facing surface |

All three are recorded in `UNKEYED_WRITERS_ALLOWED` with that reasoning, and
the guard fails if a **fourth** writer appears without a key, if an allowlist
reason is thin, or if a listed writer moves.

**Measured exposure:** these three have written **zero rows, ever**. The only
unkeyed rows are the 2 `death_spiral` events from the retired meta-detector.
The database has 0 duplicates of any kind.

## H2 — an FK is impossible; the real defect was elsewhere, and is fixed

`trade_id` is deliberately allowed to reference nothing. For an open position it
is a synthetic per-episode id from `src/lib/journalKey.ts`, derived from
(position id + IST trading date), because a `Position` row is reused across
episodes and keeps its id — keying by the raw id would let a later, unrelated
position on the same contract inherit an old entry.

The UUID version separates the two cases cleanly, since `journalKey.ts` stamps
version 5 and every real id here is v4:

```
dangling rows by UUID version:   {v4: 6, v5: 1}
resolving rows by UUID version:  {v4: 13}
```

| rows | when | what |
|---|---|---|
| 1 | 2026-07-30 | v5 — synthetic. **Dangling by design.** The only entry written after `362f740` landed on 2026-07-15 |
| 6 | 2026-04-06/07 | v4 — real ids from before that change, pointing at `positions` rows since gone |

**The plan's hypothesis is disproved:** all 20 entries belong to one broker
account and that account is alive. Nothing was orphaned by the deletion of
~13k test accounts.

**No row was dispositioned.** Every one carries the trader's own writing with
the trade denormalised onto it — symbol, P&L, and up to 135 characters of
notes. Deleting them to satisfy a constraint that should not exist on this
column would destroy a written record.

### The actual defect: `source_id` was verified and thrown away

`api/journal.py` read the real position id to confirm ownership, then did not
include it in the `JournalEntry(...)` construction, and no column existed for
it. An open-position entry was left holding only a key that resolves to nothing
— readable by the trader, joinable to nothing.

The model had expected this column for some time; its docstring said an entry
could be attached to *"a specific position (position_id)"* and no such column
was ever added.

**Fixed** — `migrations/094_journal_source_position.sql`:

```sql
ALTER TABLE journal_entries
    ADD COLUMN IF NOT EXISTS source_position_id UUID
        REFERENCES positions(id) ON DELETE SET NULL;
```

`ON DELETE SET NULL`, never `CASCADE`: a journal entry is the trader's own
writing, and deleting a position must not delete what they wrote about it. That
is also what makes the column safe on a table where 6 of 20 rows already point
at positions that no longer exist.

No backfill. The value was never stored, so for the 20 existing rows it cannot
be recovered, and inventing one would be worse than a NULL.

Proved through the real API rather than by inspection:
`test_open_position_journal_keeps_the_real_position_id` posts a synthetic
`trade_id` plus a real `source_id` and asserts the stored entry carries the
position id, and `test_closed_trade_journal_has_no_source_position` asserts the
counter-case stays NULL.

**Phase 1's drift check caught this change before the migration ran** — the
model gained a column the database did not have, and `test_no_new_schema_drift`
went red naming it. That is the first time the safety net caught a live change
rather than a historical one.

---

## Exit criteria

- [x] **H1 resolved** — deliberate omission documented and proven; the unique index is asserted in the live database; no PK added
- [x] **M18 answered** — the third writer was `death_spiral` and is retired, but three OTHER unkeyed writers were found; each is protected in application code and guarded by an AST test that fails on a fourth
- [x] **H2** — the column's meaning is settled (a journal key, not a foreign key), an FK is impossible by design, **no row was dispositioned**, and the real defect is fixed
- [x] **Phase 1 assertions cover both** — the idempotency index, the `detected_at` assumption, the writer enumeration, and the drift check that caught migration 094 before it ran
- [x] Full suite green; zero rows added to the application database

## What changed in production

Three files, one migration:

```
migrations/094_journal_source_position.sql   new, additive, applied via the runner
app/models/journal_entry.py                  + source_position_id, + to_dict, docstring
app/api/journal.py                           keep the verified id instead of discarding it
```

No row was deleted, rewritten or backfilled. No partition was touched. No
primary key was added.
