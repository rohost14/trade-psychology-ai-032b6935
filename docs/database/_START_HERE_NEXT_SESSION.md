# START HERE — resuming the database remediation

**Last session:** 2026-09-04. **Next step: Phase 1.**

---

## 1. Where things stand

| | |
|---|---|
| Audit | **COMPLETE and FROZEN** — `DATABASE_ARCHITECTURE_AUDIT.md`, 2,919 lines, 25 sections. Never edit it. |
| Findings | 48 catalogued (H1–H2, M1–M27, L1–L17, N1–N2), every one assigned to a phase |
| Phase 0 | **COMPLETE** — all 8 decisions made and approved |
| Phase 0a | **COMMITTED** — `cd0cb4e`, the zero-risk subset |
| Phase 1 | **PLANNED, NOT STARTED** — blocked on 3 design decisions (below) |
| Phases 2–8 | not started |

Everything is committed and pushed on branch `dashboard-production-readiness`.

---

## 2. The immediate next action

**Phase 1 needs three answers before any code is written.** They are written up
in full in `phase-1-safety-net/README.md`; the short form:

1. **Schema-drift baseline format** — recommended: a JSON file
   (`backend/tests/_schema_baseline.json`), so Phase 6's progress shows as the
   file shrinking. *Explicitly warned against:* a count-only threshold, because
   one drift disappearing while a new one appears nets to zero and passes
   silently.
2. **Does the drift check fail CI or warn?** — recommended: **fail**. With a
   correct baseline it is green on day one, so red means genuinely new drift.
3. **Where the synthetic fixture lives** — recommended: `backend/tests/`,
   self-contained. **The backend suite deliberately does not import
   `alertlab/`** (`test_adverse_add_integration.py:43` states why), so importing
   it would break a real architectural boundary.

Once answered, Phase 1 order of work is in that same file.

---

## 3. What was done this session

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
- **`orders` has 0 rows and that is expected.** Order-lifecycle persistence
  shipped after the last trading session, so it has never seen a live order.
  **This is the one finding whose resolution is inferred, not observed** — when
  the account reconnects, a single live order should produce rows. Re-verify then.
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
