# START HERE — resuming the database remediation

**Last session:** 2026-09-06. **Phases 1 and 2 are done. Next step: Phase 6
(61 drift items) or Phase 3.**

**Read "Phase 1 found three live defects" and Phase 2's RESOLVED section before
trusting any audit figure — the audit's H1 and M18 descriptions were both
wrong in ways that changed the remedy.**

---

## 1. Where things stand

| | |
|---|---|
| Audit | **COMPLETE and FROZEN** — `DATABASE_ARCHITECTURE_AUDIT.md`, 2,919 lines, 25 sections. Never edit it. |
| Findings | 48 catalogued (H1–H2, M1–M27, L1–L17, N1–N2), every one assigned to a phase |
| Phase 0 | **COMPLETE** — all 8 decisions made and approved |
| Phase 0a | **COMMITTED** — `cd0cb4e`, the zero-risk subset |
| Phase 1 | **COMPLETE** — 45 tests, no production code changed. Write-up in `phase-1-safety-net/README.md` under "BUILT" |
| Phase 2 | **COMPLETE** — no primary key added (the omission was deliberate); migration 094 fixes the real H2 defect. Write-up in `phase-2-data-integrity/README.md` under RESOLVED |
| Phases 3–8 | not started |

---

## 1b. Phase 1 found three live defects — read before starting Phase 2

All three surfaced only because things were RUN rather than read. The audit
found none of them.

**1. `persist_order_event` had never executed successfully — FIXED.** Detail in
section 4 below. It invalidated a "fact" this file used to assert.

**2. The drift census is 88, not 127 — catalogued, NOT fixed.** Every one of
the 88 is still present in the database; Phase 1 recorded and pinned them, it
repaired nothing.

Original note: The audit's 127 counted rendered type
strings; 41 of them were never differences (`timestamptz` vs `TIMESTAMP` is the
same type, `text` vs an unbounded `String()` is the same storage). The 88 are
in `backend/tests/_schema_baseline.json`, each with the phase that owns it:
**1 for Phase 2, 61 for Phase 6, 26 for Phase 8.**

**3. `app/models/__init__.py` exported 35 of 37 model modules — FIXED.**
`admin_login_event` and `admin_setting` were missing, so `Base.metadata` built
from the package contained neither `admin_settings` nor `admin_login_events`.
Runtime was unaffected — every consumer imports those two straight from their
own module — but `create_all` against a fresh database would have omitted both
tables silently. Fixed by adding the two imports; kept fixed by
`test_the_models_package_exports_every_model_module`, which now fails for ANY
model module the package does not import. The drift check separately walks
`app/models/*.py` via `load_all_models()`, so it no longer depends on the
package either way.

Two audit figures were also corrected by measurement: FKs into
`broker_accounts` is 37 **only when partition children are excluded** (80 with
them), and duplicate index groups is **14**, not 21 — a partial index is not a
duplicate of a full one on the same column.

**Method note, since it happened twice:** a reasonable-looking assumption was
contradicted by execution both times. Reading the code said `orders` was simply
never exercised; running it showed the writer crashes. Reading `app/models`
said every model was registered; running the suite showed two were not.

Everything is committed and pushed on branch `dashboard-production-readiness`.

---

## 2. The immediate next action

Phase 1's three decisions were answered (JSON baseline, fail CI, fixture in
`backend/tests/`) and it is built. **Next is Phase 2 — the two HIGH findings,
H1 and H2 — which is the first phase that changes the schema.**

Two things to settle before touching it:

1. **The `persist_order_event` fix.** It is one line and it unblocks the only
   table in the pipeline that has never received a row. It belongs to Phase 3
   by theme but nothing downstream depends on Phase 3, so it can go first.
2. **H1's ordering.** `behavior_events` has no primary key in the database.
   Adding one requires the existing rows to be duplicate-free first — check
   before writing the migration, not after.

Phase 1 gives Phase 2 its proof: `tests/synthetic_pipeline.py` can drive fills
through the real path and snapshot every table, and
`tests/test_live_schema_invariants.py` already asserts the primary-key
invariant H1 violates.

---

## 3a. What was done 2026-09-06 (Phase 1)

Test-only. No production code, no schema change, no migration. Eight files, 45
tests, full write-up in `phase-1-safety-net/README.md` under "BUILT".

```
tests/schema_diff.py                    the model-vs-database comparator
tests/_schema_baseline.json             88 accepted divergences, each owned
tests/generate_schema_baseline.py       writes the initial baseline; refuses to overwrite
tests/test_schema_drift.py              F1, live drift check              (3)
tests/test_schema_diff_rules.py         the rules + their counter-examples (31)
tests/test_live_schema_invariants.py    F2, dangling refs / FK / indexes   (4)
tests/synthetic_pipeline.py             F3, the fixture
tests/test_synthetic_pipeline.py        F3 proved + boundary guard         (9)

47 tests.
```

The drift check was proved to go red three ways against the live database - a
flipped nullability, a changed type, and an added column - then restored green
each time. A check that cannot fail on the defect it describes is worthless.

---

## 3b. What was done 2026-09-04

Nine commits. The database work, in order:

```
8fb0d52  admin partition & retention panel
a4e5fa4  pin TestDailyOvertrading to a fixed clock (was failing 00:00-04:00 IST)
a883a82  092 — repair orders partitions, FK and trigger
b3b5640  assert partitions exist in the live DB; sync the Order model
d1ad262  093 drop guard; crashed detector distinguishable from abstention
e12954e  savepoint the session insert; stop tests committing into the app DB
61ff9a5  remove 13,255 leaked test users
cd0cb4e  Phase 0a — verify trade_count, archive dead service, fix orphaned mock
```

### Two incidents worth remembering

**344 order rows were destroyed** by migration 090 being re-run by hand outside
the runner. Unrecoverable — no backups on this plan, and Kite serves no order
history beyond the current day. Repaired structurally by **092**; prevented from
recurring by **093**, an event trigger that refuses `DROP` on the partitioned
trading tables unless the transaction sets `tm.allow_drop`.

**12,010 test users had leaked** into the application database since 2026-03-05
— 91% of the users table — because `test_dashboard_api` shares its session with
the app and endpoint `commit()` calls made fixture rows permanent. Fixed at the
fixture (savepoint isolation), then 13,255 rows removed with export + per-batch
verification. The full suite now adds **zero** rows.

---

## 4. Facts that are easy to get wrong — check before assuming

- **Nothing has been written to any trading table since 2026-07-30.** This is
  *not* a fault: the Zerodha account was disconnected
  (`last_sync_at = 2026-07-31`, `status = token_expired`). It explains `orders`
  being empty despite 211 code references, and `behavior_events` covering only
  two days.
- ~~**`orders` has 0 rows and that is expected.** Order-lifecycle persistence
  shipped after the last trading session, so it has never seen a live order.
  **This is the one finding whose resolution is inferred, not observed** — when
  the account reconnects, a single live order should produce rows. Re-verify then.~~
  **WRONG — corrected 2026-09-06 by running the real path, and now FIXED.**
  `orders` was empty because its writer had never worked. `persist_order_event`
  in `app/tasks/trade_tasks.py` calls `asyncio.run()`, the module had no
  `import asyncio`, and that function — alone among the nine in the file that
  call it — had no function-local one either. **Every invocation raised
  `NameError: name 'asyncio' is not defined`**, retried three times and was
  swallowed at both call sites. Shipped broken in `492f73a`. Reconnecting the
  account would not have produced a single row.

  Fixed by adding the module-level import. A synthetic postback now writes an
  `orders` row, asserted by
  `tests/test_synthetic_pipeline.py::test_an_order_event_reaches_the_orders_table`.
  **`orders` is still 0 rows in production and that is now genuinely expected**
  — no order has arrived since the account disconnected. This is the exact
  reason inference is not evidence.
- **The replay reference book is a FILE, not database rows** —
  `docs/tradebook-CY6001-FO2025-26.csv`, 2,175 fills, 203 sessions. It is
  **gitignored**; one copy exists, backed up to
  `C:\Users\being\tradementor-backups\2026-09-04\`.
- **Searching for a table by name alone will wrongly condemn it.** Several are
  reached only through their ORM class. Search the table name *and* the model
  class name. Stale `.pyc` files also report phantom consumers.
- **`relkind` / `contype` arrive as Python bytes reprs** (`b'r'`, `b'f'`).
  Comparing them to `'r'` or `'f'` silently matches nothing. Decode in SQL.
- **Two figures from the audit's first pass are wrong and must not be quoted:**
  "363 silent handlers" (correct: **92**) and "122 unmatched routes" (a method
  artefact — `api.ts` is a bare axios instance, not a function map).

---

## 5. Running things

```bash
# backend suite  (2,497 passing)
cd backend && ALLOW_TESTS_ON_THIS_DB=1 python -m pytest tests/ -q --ignore=tests/production

# frontend  (140 passing)
npm run typecheck && npm run lint && npm run test

# migration state  (88 applied, 3 skipped, 0 pending, 0 changed)
cd backend && PYTHONPATH=. python scripts/migrate.py status
```

`ALLOW_TESTS_ON_THIS_DB=1` is required — the conftest guard refuses the live
Supabase URL without it. That guard exists for a reason; the suite runs against
production.

---

## 6. Map of the documentation

```
docs/database/
├── DATABASE_ARCHITECTURE_AUDIT.md   FROZEN — the findings, never edited
├── REMEDIATION_INDEX.md             registry, phase map, ownership, validation strategy
├── _START_HERE_NEXT_SESSION.md      this file
├── _shared-reference/
│   ├── BASELINE.md                  frozen DB state + a re-runnable check script
│   ├── VERIFICATION_QUERIES.md      the query behind each finding, with expected results
│   └── RLS_FUTURE_DESIGN.md         full RLS design for a future project (D2)
├── phase-0-decisions/               COMPLETE — all 8 decided, with the investigation
├── phase-1-safety-net/              PLANNED — awaiting 3 decisions
├── phase-2 … phase-8/               not started
└── phase-9-no-action-register.md    GOOD / resolved / do-not-change
```

`backend/DB_audit/` holds the specification (`Audit.md`), the resumable state
file, and `_evidence/` — the raw live-query output every finding was derived
from.
