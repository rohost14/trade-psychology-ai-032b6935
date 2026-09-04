# DATABASE AUDIT — RESUMABLE STATE

**Purpose of this file:** the audit runs across 8 parallel agents and may outlive a
single session. This file is the checkpoint. If the session ends, a new session
reads THIS FILE FIRST and continues from here. Nothing is lost by a session
ending — only by not writing down where things stood.

**Last updated:** 2026-09-04 — **AUDIT COMPLETE. REMEDIATION IN PROGRESS.**

> **Resuming? Read `docs/database/_START_HERE_NEXT_SESSION.md` first.**
> Phase 0 complete, Phase 0a committed (`cd0cb4e`), Phase 1 planned and awaiting
> three design decisions. — **ALL 8 AGENTS DIED ON A RATE LIMIT.**

> Every one of the 8 agents was killed mid-work by the account session limit
> (resets 16:10 IST). **Zero findings files were produced** — agents write their
> file only at the END, so all 8 domains are unfinished and none of their
> analysis survived.
>
> What DID survive: 85 query scripts and 19 raw output files in the session
> scratchpad. Those are raw live-DB query results — admissible evidence under the
> spec's rule — and can be reused rather than re-derived.
>
> **The parallel-agent strategy is what exhausted the budget.** Eight agents each
> independently dumped the same schema before starting their own domain, so the
> expensive part was paid eight times over. Do not simply relaunch 8 agents.
> See section 7 for the revised approach.

---

## 0. STATUS AT A GLANCE

| # | Domain | Spec §§ | Output file | Status |
|---|---|---|---|---|
| 1 | Schema inventory, PK/UUID identity, constraints | 1, 2, 8 | `_findings/01_schema_identity_constraints.md` | **NOT DONE** (agent killed) |
| 2 | FKs, relationships, data-flow map, data integrity | 3, 4, 7 | `_findings/02_relationships_data_integrity.md` | **NOT DONE** (agent killed) |
| 3 | DB↔model↔service↔API sync, transactions | 5, 6, 11 | `_findings/03_db_model_api_sync.md` | **NOT DONE** (agent killed) |
| 4 | Frontend ↔ API ↔ DB | 18 | `_findings/04_frontend_api_db.md` | **NOT DONE** (agent killed) |
| 5 | Security | 12 | `_findings/05_security.md` | **NOT DONE** (agent killed) |
| 6 | Indexes, query performance, scalability | 9, 10 | `_findings/06_indexes_performance_scale.md` | **NOT DONE** (agent killed) |
| 7 | Migrations/schema history, observability | 13, 14 | `_findings/07_migrations_observability.md` | **NOT DONE** (agent killed) |
| 8 | Legacy/duplicate, missing architecture, source-of-truth | 15, 16, 17 | `_findings/08_legacy_missing_sourceoftruth.md` | **NOT DONE** (agent killed) |
| — | **Consolidation + cross-check** | 19, 20 | `docs/database/DATABASE_ARCHITECTURE_AUDIT.md` | NOT STARTED |

**A file existing in `_findings/` means that agent COMPLETED.** Absence means it
did not finish, and that domain must be re-run. Update the table above as files
land.

Spec sections 1–18 are each covered exactly once. Section 19 (classification)
and 20 (report structure) are applied during consolidation, not by any agent.

---

## 1. HOW TO RESUME (read this if the session ended)

1. `ls backend/DB_audit/_findings/` — every file present is finished work. Do NOT
   redo those domains.
2. For each MISSING file, re-launch that domain only. The full agent briefs are
   reconstructable from section 3 below plus the spec.
3. When all 8 exist (or the user accepts a partial set), do the consolidation:
   cross-check the findings against each other, then write the single report to
   `docs/database/DATABASE_ARCHITECTURE_AUDIT.md` using the 25-part structure in
   spec section 20.
4. Report a concise summary in chat; the full audit lives in the document.

---

## 2. NON-NEGOTIABLE CONSTRAINTS (carried from the spec)

- **READ-ONLY.** No DDL, no DML, no migrations, no code changes, no data changes,
  no index creation, no "quick fixes" to make the audit tidier. SELECT and
  read-only catalog queries only.
- **EVIDENCE RULE (spec line 7).** Existing audit documents, reports, previous
  findings, project notes, `CLAUDE.md`, `MEMORY.md` and anything under `docs/`
  are NOT admissible as evidence. Everything must be verified directly against
  the live Supabase DB and the current code. Migration files under
  `backend/migrations/` are a secondary lead ONLY and must themselves be
  validated against the live DB. **Where documentation or a migration conflicts
  with the live DB, the live DB wins — and that conflict is itself a finding.**
- Findings must carry: exact table/object (+ column where relevant), quoted
  evidence, impact, confidence (HIGH/MEDIUM/LOW), classification, severity.
- Classifications: GOOD / GOOD WITH NOTE / MODIFY / INVESTIGATE / RETIRE /
  MISSING / SECURITY / PERFORMANCE / DATA INTEGRITY / CRITICAL.
- **Do not inflate severity.** Confirmed fact must stay separate from
  uncertainty. Where something could not be verified, say so rather than infer.
- The audit ENDS with a prioritised review list. Nothing gets implemented.

---

## 3. AGENT BRIEF SUMMARY (for re-launching a missing domain)

All agents were told: read the spec at `backend/DB_audit/Audit.md` first; write
throwaway query scripts into the session scratchpad and run them from
`D:\trade-psychology-ai\backend` with `python -u`, using:

```python
import asyncio, sys
sys.path.insert(0, ".")
from sqlalchemy import text
from app.core.database import SessionLocal
async def main():
    async with SessionLocal() as db:
        print((await db.execute(text("SELECT ..."))).all())
asyncio.run(main())
```

piping output through `grep -v "INFO\|DEBUG"`. Server `statement_timeout` is 2
minutes. The ONLY file each agent may write is its own findings file.

Domain-specific notes worth preserving:

- **Agent 5 (security):** no penetration testing, no destructive testing, never
  print a secret VALUE (name + location only), reason about IDOR from code
  rather than by accessing another account's data.
- **Agent 6 (performance):** the database is currently very small, so
  `idx_scan` counts and `EXPLAIN` plans are WEAK evidence about whether an index
  is used. Judge from query shapes in code and projected growth; treat runtime
  stats as corroboration only and say so. `EXPLAIN` yes, `EXPLAIN ANALYZE` never
  on a writing statement.
- **Agent 7 (migrations):** may run `python scripts/migrate.py status` (read-only)
  and nothing else from that tool. Central question is whether migration history
  actually explains the live schema — check BOTH directions (schema objects with
  no migration origin, and migrations whose effect is absent from the live DB).
- **Agent 8 (legacy):** classify, never remove. Do not call a table unused
  merely because no obvious reference was found — search the whole repo for
  table name, model class name and API path first.

---

## 4. CONSOLIDATION PLAN (step after the agents)

1. Read all 8 findings files.
2. **Cross-check overlapping domains** — this is where the real findings are:
   - agent 1 (constraints) vs agent 2 (FKs) on relationship enforcement
   - agent 2 (data integrity) vs agent 8 (source of truth) on duplicate state
   - agent 3 (model↔DB) vs agent 1 (identity) on PK/type mismatches
   - agent 6 (indexes) vs agent 2 (FKs) on unindexed foreign keys
   - agent 7 (migrations) vs agent 1 (schema) on unexplained schema objects
   - agent 4 (frontend) vs agent 8 (legacy) on tables with no consumer
3. Where two agents CONTRADICT each other, resolve by querying the live DB
   directly and record the resolution. Contradictions are signal, not noise.
4. Deduplicate findings reported by more than one agent; keep the strongest
   evidence and note the corroboration (independent agreement raises confidence).
5. Write `docs/database/DATABASE_ARCHITECTURE_AUDIT.md` with the 25 sections from
   spec section 20, including the table-by-table catalogue covering EVERY table.
6. Finish with findings-by-severity, findings-by-classification, a prioritised
   follow-up order, and an explicit "Do Not Change Yet" list.

---

## 5. WHAT HAS BEEN VERIFIED BY ME DIRECTLY (not agent output)

Recorded here only because it is live-DB evidence gathered in this session and
would otherwise be lost. Everything below is re-verifiable and should be
re-verified during consolidation rather than trusted.

- 93 relations in `public` with `relkind IN ('r','p')` at 09:0x UTC on
  2026-09-04, partitions included. That count must be re-derived, not quoted.
- Server: PostgreSQL 17.6, `statement_timeout` 2min,
  `idle_in_transaction_session_timeout` 0, `max_connections` 60,
  `wal_level` logical, `archive_mode` on, `timezone` Asia/Kolkata.
- Connection goes through the Supabase pooler on port 6543 (pgbouncer,
  transaction mode) — hence `statement_cache_size=0` in the engine config.

---

## 6. HOUSEKEEPING

- `backend/DB_audit/Audit.md` is the specification. It is the user's file; do not
  edit it.
- A previous `_schema_snapshot.md` in this directory was deleted at the user's
  request before the audit began. Do not resurrect it — the evidence rule wants
  live queries, not a cached digest.
- Agent scratch scripts live in the session temp scratchpad and are disposable.


---

## 7. REVISED APPROACH (after the 8-agent failure)

**Why the first attempt failed:** 8 parallel agents, each independently querying
the live schema before touching its own domain. The schema-discovery cost was
paid 8 times. That, not the analysis, exhausted the session budget.

**The replacement approach — sequential, incremental, resumable:**

1. **Gather facts ONCE, to disk.** Run a single pass of live-DB queries writing
   raw results into `backend/DB_audit/_evidence/*.txt`. This is NOT a
   "document" in the sense the evidence rule forbids — it is this pass's own
   live query output, timestamped, and it satisfies the rule because it came
   from the live DB rather than from prior notes. Re-run it if it ages.
2. **Analyse one spec section at a time**, appending findings straight into
   `docs/database/DATABASE_ARCHITECTURE_AUDIT.md` as each section completes.
3. **The report file is the checkpoint.** Because sections are appended as they
   finish, a session ending mid-audit loses at most one section, never the lot.
4. Update the status table in this file after each section lands.

Sections in dependency order (later ones reuse earlier facts):
inventory → identity/PK → constraints → FKs/relationships → data-flow map →
model↔DB sync → API/layer sync → data integrity → indexes → scalability →
transactions → migrations → observability → security → frontend↔API↔DB →
legacy/duplicate → missing architecture → source-of-truth → classification.

**If agents are used again**, give them a shared pre-gathered evidence directory
and forbid them from re-dumping the schema. One agent per domain, facts handed
in, analysis only.


---

## 8. SEQUENTIAL PASS — LIVE PROGRESS

Evidence gathered ONCE into `backend/DB_audit/_evidence/` (live queries, this pass):
`e01_relations` `e02_columns` `e03_constraints` `e04_indexes` `e05_triggers`
`e06_table_stats` `e07_ledger` `e08_objects` `e09_rls` `e10_rowcounts`
`e11_settings` `c01_models` `c02_model_columns` `c03_model_constraints`
`c04_routes` `c05_table_usage` `w_catalogue`.

Report: `docs/database/DATABASE_ARCHITECTURE_AUDIT.md` — appended per section, so
an interrupted session loses at most one section.

| spec § | report section | status |
|---|---|---|
| 25 | Methodology / evidence rule | DONE (header) |
| 1 | 2. Exact Database Inventory | **DONE** |
| 1 | 3. Table-by-Table Catalogue | **DONE** |
| 3, 4 | 4. ER / data-flow map | **DONE** |
| 2 | 5. PK / UUID audit | **DONE** |
| 3 | 6. FK / relationship audit | **DONE** |
| 5 | 7. DB ↔ model sync | **DONE** |
| 6 | 8. DB ↔ backend/API sync | next |
| 18 | 9. Frontend ↔ API ↔ DB | pending |
| 7 | 10. Data integrity findings | **DONE** |
| 8 | 11. Constraints & invariants | **DONE** |
| 9 | 12. Index & query audit | **DONE** |
| 10 | 13. Scalability | **DONE** |
| 11 | 14. Transactions & concurrency | pending |
| 12 | 15. Security | **DONE** |
| 13 | 16. Observability | pending |
| 14 | 17. Migration/schema history | **DONE** |
| 15 | 18. Legacy / duplicate / unused | **DONE** |
| 16 | 19. Missing architecture | pending |
| 17 | 20. Source-of-truth map | pending |
| 19 | 21-24. Severity, classification, follow-up, do-not-change | pending |
| — | 1. Executive Summary | LAST |

### Established facts so far (all live-verified this pass)
- **93 relations = 48 ordinary tables + 2 partitioned parents + 43 partitions.**
  50 addressable tables. The "~70 tables" figure is wrong.
- 39 mapped models; **11 tables with no model**; **0 models pointing at a missing table**.
- `instruments` = 166,222 rows / 79.4 MB = **99.6% of all rows**. Everything else is tiny.
- `orders` has **0 rows** across all 24 partitions despite 211 references in `backend/app`.
- **Two event tables with non-overlapping date ranges and different schemas:**
  `behavioral_events` (133 rows, 2026-02-09 → 2026-04-15, columns `event_type`/
  `trigger_trade_id`/`context`/`delivery_status`) versus `behavior_events`
  (145 rows, 2026-07-29 → 2026-07-30, columns `detector`/`evidence`/
  `input_snapshot`/`idempotency_key`/`shadow`). Predecessor and successor.
- `discipline_scores`: 0 rows, no model, **0 references anywhere in the repo**.
- Server: PG 17.6, pgbouncer :6543, role `postgres` non-superuser,
  statement_timeout 2min, max_connections 60, timezone Asia/Kolkata.

### Confirmed findings so far
- **CRITICAL/DATA INTEGRITY:** `behavior_events` has NO primary key — only a
  NON-UNIQUE `idx_behavior_events_id`. Sibling `orders` has `PRIMARY KEY
  (id, order_timestamp)`. No duplicates exist today (verified), so the defect is
  the absent guarantee, not present corruption.
- **DATA INTEGRITY:** `journal_entries.trade_id` (uuid, no FK) is polymorphic and
  35% dangling — 20 rows: 0 match `trades`, 4 match `completed_trades`, 9 match
  `positions`, **7 match nothing**.
- **Architecture:** the DB is a STAR not a chain. `broker_accounts` is the parent
  of 37 of 54 FKs (69%). The `User -> Broker -> Orders -> Completed -> Events`
  chain in the spec's example does NOT exist structurally.
- FK ON DELETE: 44 CASCADE, 9 SET NULL, 1 NO ACTION
  (`behavioral_events.trigger_trade_id`, the lone inconsistency).
- Only 9 CHECK constraints across 50 tables.
- 16 `*_id` columns without FK; most correctly so (broker identifiers, verified
  by type). Real candidates: `journal_entries.trade_id`,
  `cooldowns.trigger_alert_id`, `risk_alerts.trigger_position_id`.

### Section 7 findings (model vs live DB, mechanical diff)
- 0 models point at a missing table; 0 model columns missing from DB. GOOD.
- **26 DB columns missing from models**, 23 of them on `alert_checkpoints`
  (DB 41 cols vs model 18 — the ORM sees 44% of the table). Only live consumer is
  `app/services/alert_checkpoint_service.py`; the other is in `_archive/`.
- 55 type mismatches. 52 are VARCHAR(model)/text(db) = harmless at runtime but CI
  builds stricter columns than production. 3 are semantic:
  `completed_trades.pnl_pct` Numeric(8,2) vs **double precision**;
  `completed_trades.quality_score` Integer vs **smallint**;
  `trades.raw_payload` JSON vs **jsonb**.
- 45 nullability mismatches, both directions. ~35 model-stricter (NULL can exist
  where code assumes it cannot), ~10 model-looser.
- **PK mismatch `behavior_events`: model=['id'], db=NONE** — independently
  corroborates the section 5.2 CRITICAL finding. Consequence: CI builds the table
  WITH a PK, so no test can ever detect production's missing constraint.

### Sections 10/11/17 findings
- **0 orphans across all 54 FK-enforced relationships**; all timestamp-sanity and
  duplicate-natural-key checks pass. Every integrity defect found is in a
  relationship the DB does NOT enforce.
- `trades` duplicate kite_order_id is **NOT a defect**: 318 rows / 318 distinct
  `order_id` (unique enforced) / 269 distinct `kite_order_id` — fill-level table,
  many fills per broker order. Recorded so it is not later mistaken for one.
- Stored vocabulary drift: `risk_alerts.pattern_type` holds BOTH `overtrading`
  and `overtrading_burst`; `behavior_events.detector` holds
  `consecutive_loss_streak` vs risk_alerts' `consecutive_loss`. No CHECK on either.
- **Only 9 CHECK constraints across 50 tables**, 6 of them on 2 tables. All
  status/severity/pattern vocabulary columns are unconstrained free text —
  including `risk_alerts.severity`, which decides whether a trader is interrupted.
- Migration ledger: **91 files = 91 rows, 0 drift**. But `applied_by` =
  **79 adopt / 9 runner / 3 skip** — 87% asserted from schema inspection, never
  observed running. `migrate.py status` being clean is therefore not by itself
  evidence the schema matches the migrations.

### Sections 12/13/15/18 findings
- **21 exact-duplicate index groups** (trading_sessions has FOUR on identical
  columns). Signature = same index created under different names by successive
  migrations, none ever dropped. CAVEAT recorded: some pairs are partial indexes
  (`idx_positions_open`, `idx_risk_alerts_undelivered`) and are NOT redundant —
  per-group predicate check still required before any removal.
- Partitioned indexes correctly attached: orders 6/6 to 24/24, behavior_events
  4/4 to 19/19. GOOD.
- 8 FK columns without a leading index; 6 of 8 are on superseded event tables.
- `instruments` = 99.6% of rows but is a REFERENCE CACHE — does not grow per user.
  Real growth tables (`trades`, `position_ledger`, `completed_trades`) have NO
  partitioning and NO retention, while `orders` (smaller curve) has both.
- `idle_in_transaction_session_timeout = 0` with `max_connections = 60`.
- **SECURITY:** RLS enabled on 15 tables, **0 policies**, and app role has
  `rolbypassrls=TRUE` and owns the tables — RLS is entirely decorative. The 15
  are also an odd subset (orders/behavior_events yes; users/trades/positions no).
- Broker tokens ARE Fernet-encrypted (`broker_account.py:64-92`). GOOD.
- `tm_protect_partitioned_tables` event trigger is the only DB-level destructive
  guard; fires on sql_drop only, NOT on DELETE.
- **DUPLICATE confirmed:** `behavioral_events` (133 rows, Feb-Apr, old schema) is
  superseded by `behavior_events` (145 rows, Jul, new schema). Plus 2 empty
  variants with no model. `discipline_scores` = 0 refs anywhere in repo.
- `orders`: 211 code refs but ins=0/seq_scan=0/idx_scan=0 — never written or read
  since stats reset. INVESTIGATE.


---

## 9. AUDIT COMPLETE

All 20 specification sections executed. Report:
`docs/database/DATABASE_ARCHITECTURE_AUDIT.md` — 1,771 lines, 25 parts in
specification order.

Headline findings: 2 HIGH, 14 MEDIUM, 8 LOW.
  H1 `behavior_events` has NO primary key (non-unique index on `id` instead).
  H2 `journal_entries.trade_id` polymorphic, 7 of 20 rows dangle.

Nothing was modified: no DDL, DML, migration, code, API, frontend or data change.
Files written: the report, `_evidence/*`, this state file, and progress markers
added to `Audit.md` at the user's request.

### DEEPENING PASS (after user challenge on thoroughness)
User correctly identified that ~4 sections were shallower than spec. Deepening
in place, nothing deleted:
- **§15 Security — DONE.** 229 handlers ast-parsed: 216 authed / 13 not (all 13
  assessed individually, none an unintended exposure). IDOR: 23 id-taking
  handlers, 22 are admin-with-require_role, the 23rd (`connect_zerodha`) takes an
  unauthenticated `user_id` that is NEVER READ = dead param, not IDOR. Raw SQL:
  72 uses, 68 parameterised, 4 interpolated — 3 interpolate trusted constants,
  the 4th (`rag_service.py:280`) is a latent injection BUT unreachable (caller
  passes hardcoded [], `knowledge_base` table absent, pgvector not installed).
  NEW: audit_writer swallows exceptions -> destructive admin action can succeed
  unlogged. 28 audit() calls / 33 mutating admin routes.
- **§14 Transactions — DONE.** Ingestion path traced webhook->task->engine.
  Redis FIFO lock per account with token-checked release. Deterministic
  idempotency keys. 8 begin_nested() savepoint sites. NEW FINDING: **2 of 145
  behavior_events have NULL idempotency_key** — with no PK, those rows have zero
  uniqueness protection (NULLs don't collide in a unique index).
- Remaining to deepen: §8 API layer trace, §9 frontend, §12 query paths,
  §16 observability, §3 per-table purpose.

### DEEPENING PASS COMPLETE (all 6 shallow areas now done)
§15 security, §14 transactions, §16 observability, §12 query paths, §8 API-table
map, §9 frontend, §3 per-table purpose+dates — all deepened IN PLACE, nothing
removed. Report now 2,738 lines / 25 sections.
NEW headline: **all 8 trading tables last written 2026-07-30** (~5 weeks stale).
Totals now: 2 HIGH, 21 MEDIUM, 15 LOW.


---

## 10. HANDOFF — 2026-09-04 end of session

Audit finished and frozen. Remediation planned across 9 phases in
`docs/database/`. Phase 0 (decisions) complete and approved; Phase 0a (the
zero-risk subset) committed as `cd0cb4e`.

**Next action: Phase 1**, blocked only on three design decisions listed in
`docs/database/phase-1-safety-net/README.md`.

State of the tree: everything committed and pushed on
`dashboard-production-readiness`. Backend 2,497 tests passing, frontend 140,
typecheck and lint clean, migrations 88 applied / 3 skipped / 0 pending / 0 changed.
