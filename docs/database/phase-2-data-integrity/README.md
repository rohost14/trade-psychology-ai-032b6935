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
