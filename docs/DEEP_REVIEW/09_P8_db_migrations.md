# P8 — DB & Migrations (findings)

> Scope: all 72 migration files (`003`–`074`), FK/cascade graph, ghost columns, migration tracking, index
> coverage, model-vs-migration drift. **Findings-only.** Note: I can reason from the migration *files*; the
> **authoritative** applied state lives in the live DB (which I can't query) — hence the "verify with this
> query" items.

## Verdict
The schema is deliberately maintained (explicit cascade retrofits, hot-path indexes, partitioning, idempotent files). **One real P1: there is no migration framework/tracking.** DP1 (the DPDP cascade worry from P6) resolves **favorably** on paper but needs a one-line live-DB confirm.

---

## 🔴 P1

### MIG1 · No migration framework / no applied-state tracking · ops/correctness
There is **no `schema_migrations` table, no Alembic, no tracked runner** — only a one-off `scripts/db/run_migration_027.py`. Migrations are `.sql` files applied **manually**, with no record of which ran in which environment. Consequences:
- **No source of truth for applied state** → drift between dev/prod is invisible; "074 not applied" is tracked only in a human's head/memory file.
- **No ordering/idempotency guarantee** beyond each file's own `IF [NOT] EXISTS` guards.
- **DP1 can't be verified programmatically** (below) because nothing records what's actually applied.
- **Unsafe at scale / with a team** — schema changes can't be rolled out or audited reliably.
**Fix (pre-scale):** adopt Alembic (or a tracked runner with a `schema_migrations` version table) and baseline the current schema. This is a production-readiness item, not just hygiene.
> 🟡 **PARTIALLY FIXED 2026-07-26** — added a lightweight **tracked runner** `backend/scripts/db/migrate.py` (`schema_migrations` table + `--status`/`--stamp`/`--dry-run`/apply; natural version ordering; each migration in its own transaction). Pure logic unit-tested (`test_migrate_runner.py`); discovers all 72 migrations in order. **USER STEP:** run `python -m scripts.db.migrate --stamp` ONCE on the existing DB to baseline (record 003–074 as applied without re-running), then use it for 074+ onward. **Alembic remains the eventual target** for autogenerate/branching — this ends the "no tracking, apply by hand" problem safely without touching the live schema until run.

---

## 🟢 DP1 — RESOLVES FAVORABLY (verify on live DB)
The P6 worry (DPDP hard-delete depends on a complete `ON DELETE CASCADE` graph) checks out **in the migration files**:
- **`users` ← `broker_accounts`:** `032_users_table.sql:81` adds `broker_accounts.user_id → users(id) ON DELETE CASCADE`. So deleting a `users` row cascades to `broker_accounts`.
- **Early tables created without cascade** (`trades`/`positions`/`orders`/`holdings` and `020`'s `completed_trades`/`completed_trade_features`/`incomplete_positions`/`behavioral_events`) are **retrofitted**: `017_add_cascade_delete.sql` fixes the first group, `022_cascade_indexes_datetime.sql` fixes the `020` group + `risk_alerts`/`margin_snapshots`/goals/etc.
- **All per-account tables created after `020`** declare `ON DELETE CASCADE` inline (036 ledger, 037 sessions, 040/064/067 events, 041 coach, 046 strategy, 047 reports, 051 guardrail, 057 discipline, 065 constitution, 069 mutes, 070 data-quality, …).
- **Partitioned `behavior_events`** (067) declares the FK on the partitioned parent with cascade — PG cascades to all partitions.

**So the chain `DELETE users → broker_accounts → all per-account tables` is complete *if every 017/022 ALTER actually applied* (see MIG1).** Because there's no tracking, **run this on prod before trusting delete:**
```sql
SELECT c.conrelid::regclass AS child, c.confdeltype
FROM pg_constraint c JOIN pg_class p ON p.oid=c.confrelid
WHERE c.contype='f' AND p.relname IN ('users','broker_accounts')
ORDER BY 1;
-- every row's confdeltype must be 'c' (CASCADE). Any 'a'/'r'/'n' breaks or orphans the DPDP delete.
```
**Sub-item (MIG4, P3):** `016_fix_all_missing_columns.sql` adds a `broker_account_id … REFERENCES broker_accounts(id)` **without** cascade — confirm its table is in the 017/022 fix set (or in the delete path) via the query above.

---

## 🟡 P2

### MIG2 · `risk_alert.outcome` has a writer endpoint but ~zero adoption → response-stats show empty · feature-gap
Unlike the memory note "never written", `api/risk.py:168-191` **does** write `alert.outcome` (`VALID_OUTCOMES`), and `risk.py:310-312` computes response stats (`stopped` vs `took_anyway`) from it. But it needs the user to **manually record** each alert's outcome — and the project's own hard constraint says adoption of manual input is **zero** (55 alerts, 0 outcomes). So the outcome column is ~always NULL and the **alert-response analytics render empty/misleading**. Either derive the outcome from behaviour (did they trade again within cooldown?) or drop the feature — don't ship a stat that depends on input nobody gives.

---

## ⚪ P3
- **MIG3 (confirms D11)** `CompletedTrade.quality_score` is **truly dead** — the only reader is `api/_archive/analytics_dead_endpoints.py` (archived Weekly Discipline Score); **no live reader, no writer** (grep clean across pnl/ledger/sync). Harmless dead column; drop it in a cleanup migration or leave. → ledger.
- **MIG5** Two similarly-named event tables coexist historically: `behavioral_events` (020/040 shadow) vs `behavior_events` (064/067 partitioned, the live one). Confirm the old `behavioral_events` is dead/dropped and nothing writes both. (P2/P11 candidate.)
- **MIG6** Model-vs-migration drift not fully verifiable without the live DB. Spot-checks aligned (risk_alert, completed_trade, behavior_event fields match models). A full drift check = compare `Base.metadata` to `information_schema.columns` on prod (add to the ops checklist).

## ✅ Solid (credit)
Cascade retrofit was done **deliberately and completely** (017 + 022) rather than left broken; hot-path indexes present (021/031/043/067 + 073 per prior audit); migrations are **idempotent** (`IF [NOT] EXISTS`, `DROP CONSTRAINT IF EXISTS` before `ADD`); `behavior_events` partitioned with per-partition cascade; FK names follow PG defaults so the idempotent DROP/ADD retrofits match.

## For P14 (QA / ops)
Run the `pg_constraint` cascade query on prod (DP1) · **fully-populated-account delete drill** — confirm zero orphan rows across every table (DP1) · introduce migration tracking + a drift check (MIG1/MIG6) · decide `outcome`/`quality_score` fate (MIG2/MIG3).
