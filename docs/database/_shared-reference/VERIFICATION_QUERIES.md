# Verification Queries — the proof behind each finding

Source: audit §25 (methodology) plus the queries that actually produced each
finding. **This is what makes "re-run the audit query and confirm zero" an
executable instruction rather than a wish.**

Run everything from `D:\trade-psychology-ai\backend`, wrapped in:

```python
import asyncio, sys
sys.path.insert(0, ".")
from sqlalchemy import text
from app.core.database import SessionLocal
async def main():
    async with SessionLocal() as db:
        print((await db.execute(text("<QUERY>"))).all())
asyncio.run(main())
```

Pipe output through `grep -v "INFO\|DEBUG"`.

---

## Two traps that produced wrong answers during the audit

**Both cost real rework. Do not repeat them.**

**1. `relkind` / `contype` arrive as Python bytes reprs.** `b'r'`, `b'f'`.
Comparing to `'r'` or `'f'` in Python or awk silently matches **nothing** — you
get an empty result and conclude the wrong thing. **Decode in SQL:**

```sql
CASE con.contype WHEN 'f' THEN 'FOREIGN KEY' WHEN 'p' THEN 'PRIMARY KEY'
                 WHEN 'u' THEN 'UNIQUE'      WHEN 'c' THEN 'CHECK' END
```

**2. Searching for a table by name alone wrongly condemns it.** Several tables
are reached only through their ORM class. `alert_checkpoints`, `guardrail_rules`
and others were nearly mis-classified as unused this way. **Always search the
table name AND the model class name.** And note that stale `.pyc` files report
phantom consumers for source that has been archived.

---

## Phase 2 — the HIGH findings

### H1 · `behavior_events` has no primary key

```sql
-- every constraint on the table; expect a 'p' row after the fix
SELECT conname, contype::text, pg_get_constraintdef(oid)
  FROM pg_constraint WHERE conrelid='behavior_events'::regclass;

-- the index that exists instead; note it is NOT unique
SELECT indexname, indexdef FROM pg_indexes WHERE tablename='behavior_events';

-- current data cleanliness. audit result: 0, 0
SELECT count(*) - count(DISTINCT id) AS dup_ids,
       count(*) FILTER (WHERE id IS NULL) AS null_ids
  FROM behavior_events;
```
**Audit result:** no `p` constraint; `idx_behavior_events_id` is a plain index.
**Expected after fix:** a primary key exists, or a documented decision that the
partition-key requirement makes it undesirable.

### M18 · null idempotency keys

```sql
SELECT count(*) AS total,
       count(*) FILTER (WHERE idempotency_key IS NULL) AS null_keys,
       count(DISTINCT idempotency_key) AS distinct_keys
  FROM behavior_events;
```
**Audit result:** `145, 2, 143`. **Expected after fix:** `null_keys = 0`.

### H2 · `journal_entries.trade_id` polymorphic and dangling

```sql
SELECT (SELECT count(*) FROM journal_entries)                        AS total,
       (SELECT count(*) FROM journal_entries WHERE trade_id IS NOT NULL) AS populated,
       (SELECT count(*) FROM journal_entries j JOIN trades t           ON t.id=j.trade_id) AS match_trades,
       (SELECT count(*) FROM journal_entries j JOIN completed_trades c ON c.id=j.trade_id) AS match_completed,
       (SELECT count(*) FROM journal_entries j JOIN positions p        ON p.id=j.trade_id) AS match_positions;
```
**Audit result:** `20, 20, 0, 4, 9` → **7 match nothing**.
**Expected after fix:** every populated `trade_id` resolves, against a single
known target table.

---

## Phase 3 — correctness

### M22 · `trade_count` never written

```sql
SELECT ts.session_date, ts.trade_count, ts.session_pnl,
       (SELECT count(*) FROM completed_trades ct
         WHERE ct.broker_account_id = ts.broker_account_id
           AND date(ct.exit_time) = ts.session_date) AS actual
  FROM trading_sessions ts ORDER BY ts.session_date;
```
**Audit result:** `trade_count = 0` on all 9 rows while `session_pnl` is correct.
**Expected:** `trade_count = actual` — or the column is dropped (D8).

### M23 · trading days with no session row

```sql
SELECT DISTINCT date(ct.exit_time) AS d FROM completed_trades ct
 WHERE NOT EXISTS (SELECT 1 FROM trading_sessions ts
                    WHERE ts.session_date = date(ct.exit_time)
                      AND ts.broker_account_id = ct.broker_account_id)
 ORDER BY 1;
```
**Audit result:** 13 days, of which **2026-06-16** falls after sessions began.
**Expected:** no day after the feature's start date is missing.

### L16 · NULL `fill_timestamp`

```sql
SELECT count(*) FILTER (WHERE fill_timestamp IS NULL) AS null_fill,
       count(*) FILTER (WHERE fill_timestamp IS NULL
                          AND exchange_timestamp IS NOT NULL) AS has_fallback
  FROM trades;
```
**Audit result:** `22, 20`. **Expected:** `null_fill = 0`, or documented.

### M6 · services committing sessions they do not own

```bash
grep -rl "await db.commit()\|await session.commit()" backend/app/services/*.py
```
**Audit result:** 19 of 61.

### M26 · optional lineage

```sql
SELECT c.relname AS child, a.attname AS col,
       CASE con.confdeltype WHEN 'c' THEN 'CASCADE' WHEN 'n' THEN 'SET NULL'
                            WHEN 'a' THEN 'NO ACTION' END AS on_delete,
       a.attnotnull AS not_null
  FROM pg_constraint con
  JOIN pg_class c ON c.oid = con.conrelid
  JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = con.conkey[1]
 WHERE con.contype='f' AND con.confdeltype='n'
 ORDER BY 1,2;
```
**Audit result:** 9 nullable `SET NULL` lineage pointers.

---

## Phase 4 — security

### M1 · RLS is decorative

```sql
SELECT count(*) FILTER (WHERE relrowsecurity) AS rls_on,
       count(*) FILTER (WHERE NOT relrowsecurity) AS rls_off
  FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind IN ('r','p');
SELECT count(*) FROM pg_policies WHERE schemaname='public';
SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user;
```
**Audit result:** `15 on / 35 off`, **0 policies**, `rolbypassrls = TRUE`.

### L9 · latent SQL interpolation reachability

```sql
-- both must stay absent for the finding to remain unreachable
SELECT to_regclass('public.knowledge_base') AS kb_table;
SELECT extname FROM pg_extension WHERE extname = 'vector';
```
**Audit result:** both empty. **If either becomes non-empty, L9 becomes live and
must be parameterised first.**

### M17 · audit coverage

```bash
grep -rc "await audit(" backend/app/api/admin/*.py
```
**Audit result:** 28 `audit()` calls across 33 mutating admin routes.

---

## Phase 5 — performance

### M2 · duplicate index groups — **run the predicate check too**

```sql
-- the grouping that found 21 (column list only — CANNOT see a predicate)
SELECT c.relname, string_agg(ic.relname, ' | ' ORDER BY ic.relname), count(*)
  FROM pg_index i
  JOIN pg_class c  ON c.oid = i.indrelid
  JOIN pg_class ic ON ic.oid = i.indexrelid
 WHERE c.relnamespace='public'::regnamespace
   AND c.relname !~ '_y[0-9]{4}m[0-9]{2}$' AND c.relname !~ '_default$'
 GROUP BY c.relname, i.indkey HAVING count(*) > 1;

-- MANDATORY before dropping anything: does a member have a predicate?
SELECT ic.relname, i.indisunique, pg_get_expr(i.indpred, i.indrelid) AS predicate
  FROM pg_index i JOIN pg_class ic ON ic.oid = i.indexrelid
 WHERE i.indrelid = '<table>'::regclass;
```
**A non-null `predicate` means the index is partial and is NOT redundant.**

### L5 · FK columns with no index

```sql
SELECT c.relname, a.attname
  FROM pg_constraint con
  JOIN pg_class c ON c.oid = con.conrelid
  JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = con.conkey[1]
 WHERE con.contype='f' AND c.relnamespace='public'::regnamespace
   AND NOT EXISTS (SELECT 1 FROM pg_index i
                    WHERE i.indrelid = con.conrelid AND i.indkey[0] = a.attnum);
```
**Audit result:** 8 columns.

---

## Phase 6 — schema hygiene

### The model↔DB diff (M4, L1, L2, L3, and H1's corroboration)

The full script is in audit §25. Its shape:

```python
import app.models                      # registers every model
from app.core.database import Base
# compare Base.metadata.tables against information_schema.columns:
#   presence, data_type, is_nullable, numeric precision/scale, primary key
```
**Audit result:** 0 missing tables, 0 missing model columns, **26** DB columns
missing from models, **55** type mismatches, **45** nullability mismatches,
**1** PK mismatch.
**Expected:** the count falls as Phase 6 proceeds; Phase 1's drift check holds
the line.

### M11 / L7 · vocabulary

```sql
SELECT 'risk_alerts.severity' AS col, severity AS value, count(*)
  FROM risk_alerts GROUP BY 2
UNION ALL
SELECT 'risk_alerts.pattern_type', pattern_type, count(*) FROM risk_alerts GROUP BY 2
UNION ALL
SELECT 'behavior_events.detector', detector, count(*) FROM behavior_events GROUP BY 2
ORDER BY 1, 3 DESC;
```
Settle the legal value set here **before** adding any CHECK constraint — historic
values must be included or the constraint cannot be applied.

---

## Phase 7 — observability

### M20 · writes that can fail silently

```python
# except Exception preceded by a DB write, with no re-raise in the next 3 lines
# audit result: 92
```
Full script shape in audit §16.4.

### M3 · migration provenance

```sql
SELECT applied_by, count(*) FROM schema_migrations GROUP BY 1;
```
**Audit result:** `adopt 79, runner 9, skip 3`.

---

## Phase 8 — retirement

### Reachability — **table name AND model class**

```python
# for each candidate table, search backend/app, backend/scripts, backend/tests, src
# for BOTH the table name and its model class name.
# Ignore __pycache__ — stale .pyc files report phantom consumers.
```
**Audit result:** `behavior_events_legacy`, `shadow_behavioral_events`,
`discipline_scores`, `discipline_streaks`, `portfolio_chat_sessions`,
`position_alerts_sent` all reach **0 live consumers**.

### Pre-drop export — mandatory, there are no backups

```sql
SELECT count(*) FROM <table>;      -- record it
-- export rows to file BEFORE any drop
```

---

## Whole-system regression, after every phase

1. `BASELINE.md`'s check script — everything not deliberately changed is unchanged.
2. Full backend suite: `ALLOW_TESTS_ON_THIS_DB=1 python -m pytest tests/ -q --ignore=tests/production`
   (2,492 tests at audit time).
3. Synthetic replay through `alertlab/runner/harness.py` → `lab_environment()`.
4. `tradedesk/scripts/replay_tradebook.py` against the 203-session book.
