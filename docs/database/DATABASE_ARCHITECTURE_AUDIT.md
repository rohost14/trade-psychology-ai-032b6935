# Database Architecture & Integrity Audit

**Status:** COMPLETE — all 20 specification sections executed.
**Started:** 2026-09-04
**Scope:** read-only audit. Nothing in the database, schema, migrations, code,
API or frontend was modified while producing this.

**Evidence rule applied throughout (from the specification):** no existing audit
document, report, previous finding, project note, `CLAUDE.md`, `MEMORY.md` or
`docs/` file was used as evidence. Every statement below is derived from a live
query against the Supabase database or from reading the current source. Migration
files were consulted only as a secondary lead and were checked against the live
database. **Where documentation or a migration conflicts with the live database,
the live database wins, and the conflict is recorded as a finding.**

---

## 1. Executive Summary

**Scope.** Every table, constraint, index, foreign key and trigger in the live
Supabase database, compared against the current codebase. Read-only throughout.

**Headline: the database is in better shape than its documentation suggests, and
its real problems are concentrated in a small number of specific places.**

### The inventory is not what was assumed

There are **93 relations**, which decompose as **48 ordinary tables + 2
partitioned parents + 43 partitions** — so **50 addressable tables**, not the
"~70" the specification anticipated. 39 have SQLAlchemy models; 11 do not, and
for 8 of those the absence is correct.

`instruments` holds **166,222 of the ~167,000 rows in the entire database
(99.6%)** and is a reference cache that does not grow per user. Every other table
holds fewer than 400 rows. **The database has essentially no production data
volume yet**, which is the single most important caveat in this report: runtime
statistics cannot support conclusions about index usefulness or query cost, and
no growth rate is observable.

### What is genuinely good

Four things are done well and should not be disturbed:

- **Tenancy cascade is complete.** All 37 foreign keys into `broker_accounts` —
  69% of every FK in the database — are `ON DELETE CASCADE`, as is the single
  link to `users`. Account deletion is structurally correct rather than
  bookkept in application code.
- **Where the database enforces a relationship, the data obeys it.** A
  programmatic walk of all 54 foreign keys found **zero orphans**, and every
  timestamp-sanity and duplicate-key check passed.
- **Idempotency is real and database-enforced** on every table that ingests
  external events — `position_ledger`, `behavior_events`, `trades`, `orders`,
  `trading_sessions` all carry unique keys designed for replay and duplicate
  delivery.
- **Credentials are encrypted at rest**, and partitioned indexes are correctly
  attached to all 24 and all 19 partitions respectively — a failure mode that
  looks healthy when broken.

### The two findings that matter most

**1. `behavior_events` has no primary key.** It is the only addressable table in
the database without one. What exists instead is a **non-unique** index on `id`.
The sibling partitioned table does it correctly (`orders_pkey PRIMARY KEY (id,
order_timestamp)`). No duplicates exist today, so this is an absent guarantee
rather than present corruption — but every piece of code treating
`behavior_events.id` as unique relies on an invariant the database does not
enforce. It is invisible to the test suite, because CI builds the schema *from
the models*, where the primary key does exist.

**2. `journal_entries.trade_id` is polymorphic and 35% dangling.** Of 20 rows:
**0** match `trades` — the table its name implies — **4** match
`completed_trades`, **9** match `positions`, and **7 match nothing at all**.
There is no foreign key and no discriminator recording which table any given row
points at. A journal entry is the trader's own written record, and a third of
them cannot be tied back to anything.

**Every integrity defect found in this audit is in a relationship the database
does not enforce.** That is the through-line.

### The finding that reframes several others

**Nothing has been written to any trading table since 2026-07-30** — five weeks
before this audit. Eight independent tables share that exact last-write date:
`trades`, `completed_trades`, `positions`, `risk_alerts`, `position_ledger`,
`journal_entries`, `trading_sessions`, `instruments`.

This explains, and must be read alongside, several other observations: `orders`
holding zero rows despite 211 code references; `behavior_events` covering only
**two days** of production output; and the general emptiness that makes index and
query-plan analysis unusable.

**This has since been confirmed as an idle account, not a fault.** The broker
token expired and `last_sync_at` is 2026-07-31 — one day after the last trading
row. Nothing was lost (§3.5).

It does not clear everything, though. Four anomalies sit **inside** the active
February–July window, where an idle account explains nothing (§3.6): 
`trading_sessions.trade_count` is zero on every row while `session_pnl` on the
same rows is correct; 13 of 23 trading days have no session row; 22 trades carry
a NULL `fill_timestamp`; and there is a **three-and-a-half month hole in
behavioural coverage** (2026-04-15 → 07-29) during which the trader traded,
alerts were raised, and neither event table recorded anything.

### The structural picture

The architecture is a **star, not a chain**. The specification's example
(`User → Broker → Orders → Completed Trades → Events → Journal`) does not exist
structurally: almost everything hangs directly off `broker_accounts`, and the
links that would let you reconstruct *why* an alert fired are all nullable
`SET NULL` pointers. Deleting a trade does not delete the alert it caused — it
silently blanks the alert's only evidence.

### Notable secondary findings

- **RLS is decorative.** Enabled on 15 tables, **zero policies defined**, and the
  application role has `rolbypassrls = TRUE` and owns the tables. Tenant
  isolation rests entirely on the application layer — a legitimate choice, but
  the schema currently looks as though a database control exists where none is
  in force, and the 15 tables are an odd subset that excludes `users`, `trades`
  and `positions`.
- **87% of migration history was asserted, not observed.** The ledger and
  filesystem agree exactly (91 = 91, zero drift), but 79 of 91 rows are `adopt`
  — recorded from schema inspection without executing. "`migrate.py status` is
  clean" is therefore not by itself evidence that the schema matches the
  migrations.
- **21 groups of duplicate indexes**, one table carrying four on identical
  columns — the signature of the same index recreated under different names by
  successive migrations with none ever dropped. **Caveat:** several members are
  partial indexes and are not redundant.
- **Growth protection was applied to the wrong curve.** `orders` is partitioned
  with retention; `trades`, `position_ledger` and `completed_trades` — which
  grow faster, since one order yields several fills — have neither.
- **Only 9 CHECK constraints across 50 tables.** All status, severity and
  pattern-name columns are unconstrained free text, including
  `risk_alerts.severity`, which decides whether a trader is interrupted.
- **Nothing detects schema drift.** This audit found 26 missing model columns, 55
  type mismatches, 45 nullability mismatches and a missing primary key; no
  existing check would have surfaced any of them, because CI builds its schema
  from the models and so cannot see the divergence.

### What must not be "fixed"

Several things look wrong and are correct — duplicate `kite_order_id` values in
`trades` (fill-level table, working as intended), empty tables with heavy wiring
(`orders` has 211 code references), `instruments` at 166k rows (a cache), and
`*_id` columns without foreign keys (most hold broker identifiers). These are
enumerated in §24 specifically to prevent a well-meant cleanup causing damage.

### Confidence and limits

Two HIGH-severity findings and twenty-one MEDIUM, all supported by direct query
output or quoted source in the body. Where evidence was weak it is labelled: endpoint-usage
analysis (§9) is LOW-to-MEDIUM confidence and its "122 unmatched routes" figure
should not be quoted; migration provenance is MEDIUM because an `adopt` record
cannot be distinguished from a manual change; and no index finding rests on query
plans, which this data volume cannot support.

Seven analysis errors were made and corrected across the two passes; they are
recorded in §25 and §21.1 because several initially produced wrong findings —
including a first-pass figure of "363 silent handlers" that the second pass
narrowed to 92, and a "122 unmatched routes" figure that turned out to be a
method artefact and should not be quoted.

**This document was produced in two passes.** The first covered all 20
specification sections; a review found that security, transactions, query paths,
observability, the API/frontend layer and per-table purpose were shallower than
the specification required, and a second pass deepened each of them. Findings
added by the second pass are marked in §21.1.

**Nothing was changed.** This is a review list for a separate implementation
phase.

---

## 2. Exact Database Inventory

All figures below are from live catalog queries on 2026-09-04, not from any
document.

### 2.1 Relation count

```
93  relations in schema `public` with relkind IN ('r','p')
────────────────────────────────────────────────────────
48  ordinary tables            (relkind 'r', not a partition)
 2  partitioned parents        (relkind 'p'): orders, behavior_events
43  partition children         (24 under orders, 19 under behavior_events)
```

**The commonly quoted "~70 tables" is wrong in both directions.** There are
**50 addressable tables** (48 ordinary + 2 partitioned parents); the remaining 43
relations are partitions of two of them and are not independent tables.

| classification | count |
|---|---|
| addressable tables | 50 |
| of those, with a SQLAlchemy model | 39 |
| of those, with **no** model | 11 |
| models pointing at a non-existent table | **0** |

### 2.2 Server and connection facts

| property | value |
|---|---|
| server | PostgreSQL 17.6 (aarch64-linux) |
| connection | Supabase pooler, port 6543 (pgbouncer, transaction mode) |
| connecting role | `postgres`, `usesuper = false` |
| `statement_timeout` | 2min |
| `idle_in_transaction_session_timeout` | 0 (disabled) |
| `max_connections` | 60 |
| `wal_level` | logical |
| `archive_mode` | on |
| server `timezone` | Asia/Kolkata |
| default isolation | read committed |

### 2.3 Size distribution

Total data is small, and **one table dominates completely**:

| table | rows | size |
|---|---|---|
| `instruments` | 166,222 | 79.4 MB |
| `behavior_events` (all 19 partitions) | 145 | — |
| `behavioral_events` | 133 | — |
| `trades` | 318 | — |
| `completed_trades` | 112 | — |
| `position_ledger` | 100 | — |
| `positions` | 99 | — |
| `margin_snapshots` | 279 | — |
| `cooldowns` | 215 | — |
| every other table | ≤ 91 | — |
| `orders` (all 24 partitions) | **0** | — |

`instruments` holds **99.6% of all rows in the database**. Everything else is,
at present, effectively empty. This single fact governs how the rest of this
audit must be read: **runtime statistics such as `idx_scan` counts and `EXPLAIN`
plans are not usable as evidence about index usefulness or query cost at this
data volume**, because Postgres will prefer sequential scans on tiny tables
regardless of what indexes exist. Wherever runtime statistics are cited below,
they are treated as weak corroboration only, and this is stated explicitly.

### 2.4 Tables with no SQLAlchemy model

Eleven addressable tables have no mapped model. This is not automatically a
defect — several are written by raw SQL or by tooling — but each needs a reason.

| table | rows | refs in `backend/app` | assessment |
|---|---|---|---|
| `schema_migrations` | 91 | 0 | migration ledger, written by `scripts/migrate.py` — correct that it has no ORM model |
| `admin_settings` | 0 | 16 | actively used via raw SQL / service layer |
| `detector_flags` | 0 | 22 | actively used |
| `gtt_tracking` | 0 | 13 | actively used |
| `oauth_temp_store` | 1 | 6 | actively used |
| `admin_login_events` | 0 | 2 | referenced, low usage |
| `position_alerts_sent` | 0 | 2 | referenced, low usage |
| `discipline_streaks` | 0 | 2 | referenced, low usage |
| `shadow_behavioral_events` | 0 | **0** | no app reference; scripts only |
| `behavior_events_legacy` | 0 | **0** | no app reference; 1 script |
| `discipline_scores` | 0 | **0** | **no reference anywhere in the repository** |

---

## 3. Table-by-Table Catalogue

Reference data for every addressable table. `refs` columns are literal-string
occurrence counts of the table name across the repository, gathered with
ripgrep; they indicate wiring, not correctness.

**Reading note, per the specification:** a table is NOT called unused merely
because it is empty. Several tables below have zero rows but heavy code wiring
(`orders` has 211 references in `backend/app`), which means they are live and
simply have no data yet. Emptiness and disuse are recorded as separate facts.

| table | rows | model | app | scripts | tests | frontend | role |
|---|---|---|---|---|---|---|---|
| `instruments` | 166,222 | `Instrument` | 127 | 5 | 13 | 58 | Kite instrument master cache |
| `trades` | 318 | `Trade` | 1680 | 372 | 740 | 867 | individual broker fills |
| `margin_snapshots` | 279 | `MarginSnapshot` | 4 | 0 | 5 | 0 | historical margin utilisation |
| `cooldowns` | 215 | `Cooldown` | 36 | 24 | 9 | 2 | cooling-off periods |
| `behavior_events` | 145 | `BehaviorEvent` | 22 | 11 | 30 | 2 | detector output (current schema) |
| `behavioral_events` | 133 | `BehavioralEvent` | 7 | 5 | 3 | 0 | detector output (older schema) |
| `completed_trades` | 112 | `CompletedTrade` | 52 | 25 | 25 | 1 | full position lifecycle |
| `position_ledger` | 100 | `PositionLedger` | 22 | 12 | 20 | 0 | append-only fill ledger |
| `positions` | 99 | `Position` | 462 | 150 | 163 | 129 | open/closed positions |
| `schema_migrations` | 91 | — | 0 | 15 | 9 | 0 | migration ledger |
| `risk_alerts` | 57 | `RiskAlert` | 17 | 17 | 24 | 6 | trader-facing alerts |
| `journal_entries` | 20 | `JournalEntry` | 10 | 1 | 3 | 1 | trade journal |
| `incomplete_positions` | 10 | `IncompletePosition` | 2 | 0 | 2 | 0 | unresolved position state |
| `trading_sessions` | 9 | `TradingSession` | 10 | 5 | 2 | 1 | one row per account per trading day |
| `coach_sessions` | 5 | `CoachSession` | 1 | 0 | 0 | 0 | AI coach conversations |
| `users` | 3 | `User` | 102 | 32 | 43 | 65 | identity |
| `user_profiles` | 3 | `UserProfile` | 4 | 4 | 3 | 0 | preferences, rules, capital |
| `constitution_history` | 3 | `ConstitutionHistory` | 10 | 0 | 0 | 1 | rule-change history |
| `broker_accounts` | 3 | `BrokerAccount` | 38 | 25 | 31 | 0 | broker connection |
| `admin_audit_log` | 3 | `AdminAuditLog` | 6 | 0 | 0 | 0 | immutable admin action log |
| `guardrail_rules` | 2 | `GuardrailRule` | 4 | 0 | 0 | 0 | user alert rules on open positions |
| `trading_goals` | 1 | `Goal` | 1 | 0 | 3 | 0 | goals |
| `streak_data` | 1 | `StreakData` | 1 | 0 | 3 | 0 | streaks |
| `push_subscriptions` | 1 | `PushSubscription` | 3 | 0 | 5 | 0 | web push |
| `portfolio_chat_sessions` | 1 | `PortfolioChatSession` | 2 | 0 | 0 | 0 | portfolio chat history |
| `oauth_temp_store` | 1 | — | 6 | 0 | 0 | 0 | OAuth nonce/CSRF store |
| `alert_mutes` | 1 | `AlertMute` | 1 | 0 | 1 | 0 | muted alerts |
| `alert_checkpoints` | 1 | `AlertCheckpoint` | 1 | 0 | 12 | 0 | alert follow-up checkpoints |
| `admin_users` | 1 | `AdminUser` | 3 | 0 | 1 | 0 | admin accounts |
| `orders` | **0** | `Order` | 211 | 16 | 137 | 25 | order lifecycle (partitioned, 24 partitions) |
| `holdings` | 0 | `Holding` | 92 | 0 | 3 | 28 | CNC/delivery holdings |
| `detector_flags` | 0 | — | 22 | 0 | 2 | 0 | per-detector feature flags |
| `gtt_tracking` | 0 | — | 13 | 0 | 4 | 0 | GTT order tracking |
| `admin_settings` | 0 | — | 16 | 0 | 6 | 0 | runtime global settings |
| `data_quality_events` | 0 | `DataQualityEvent` | 10 | 0 | 1 | 0 | ingestion quality markers |
| `monthly_snapshots` | 0 | `MonthlySnapshot` | 8 | 0 | 6 | 0 | immutable monthly summary |
| `position_margin_observations` | 0 | `PositionMarginObservation` | 5 | 0 | 2 | 0 | broker margin observations |
| `broadcast_logs` | 0 | `BroadcastLog` | 3 | 0 | 0 | 0 | admin broadcast log |
| `broadcast_receipts` | 0 | `BroadcastReceipt` | 3 | 0 | 0 | 0 | broadcast delivery receipts |
| `strategy_groups` | 0 | `StrategyGroup` | 2 | 2 | 0 | 0 | multi-leg strategy grouping |
| `strategy_group_legs` | 0 | `StrategyGroupLeg` | 2 | 0 | 0 | 0 | legs of a strategy group |
| `completed_trade_features` | 0 | `CompletedTradeFeature` | 2 | 1 | 6 | 0 | derived trade features |
| `position_alerts_sent` | 0 | — | 2 | 0 | 0 | 0 | dedup for position alerts |
| `discipline_streaks` | 0 | — | 2 | 0 | 0 | 0 | discipline streak state |
| `admin_login_events` | 0 | — | 2 | 0 | 0 | 0 | admin login audit |
| `commitment_logs` | 0 | `CommitmentLog` | 1 | 0 | 2 | 0 | goal commitments |
| `generated_reports` | 0 | `GeneratedReport` | 1 | 0 | 0 | 0 | saved report copies |
| `shadow_behavioral_events` | 0 | — | **0** | 5 | 0 | 0 | shadow detector output |
| `behavior_events_legacy` | 0 | — | **0** | 1 | 0 | 0 | pre-partition event table |
| `discipline_scores` | 0 | — | **0** | **0** | **0** | **0** | no consumer found anywhere |

---

### 3.1 Business purpose, per table

The catalogue above gives shape and wiring. This gives meaning. Purpose is
derived from the table's columns, its DB comment where one exists, and the
modules that read it (§8.3) — not from any project documentation.

**Core identity**

| table | what it is for |
|---|---|
| `users` | the person. Identity only — created by Zerodha OAuth; no password column exists |
| `broker_accounts` | the Zerodha connection: encrypted tokens, status, broker user code. **The tenancy hub** — 69% of all FKs point here |
| `user_profiles` | the trader's declared settings: capital, risk limits, experience, notification preferences |
| `constitution_history` | append-only log of rule changes, so a limit change is attributable |

**Ingestion / transactional**

| table | what it is for |
|---|---|
| `orders` | every order lifecycle state from Zerodha, including cancelled and rejected. Partitioned monthly; the evidence base for stop-loss detection |
| `trades` | individual **fills**. One broker order can yield several rows (§10.3) |
| `position_ledger` | append-only fill ledger with its own idempotency key — the audit trail from which position state can be reconstructed |
| `positions` | current open/closed position state per symbol |
| `holdings` | CNC/delivery holdings, kept separate from intraday positions |
| `incomplete_positions` | positions that could not be fully resolved during sync — a data-quality queue |

**Derived trading state**

| table | what it is for |
|---|---|
| `completed_trades` | a full round trip: entry through exit, with realised P&L. The unit the behaviour engine analyses |
| `completed_trade_features` | derived per-trade features for analytics |
| `trading_sessions` | one row per account per trading day; session-level facts and state |
| `strategy_groups` / `strategy_group_legs` | multi-leg F&O structures recognised across several fills |

**Behavioural**

| table | what it is for |
|---|---|
| `behavior_events` | **current** detector output: detector name, evidence, input snapshot, idempotency key |
| `behavioral_events` | **superseded** predecessor with a different schema (§18.1) |
| `risk_alerts` | the trader-facing alert actually raised, with severity and lifecycle |
| `alert_checkpoints` | follow-up measurement after an alert — did the trader act? |
| `alert_mutes` | per-pattern muting |
| `cooldowns` | cooling-off periods after a triggering event |

**User content**

| table | what it is for |
|---|---|
| `journal_entries` | the trader's own notes, emotion tags and setup rating |
| `trading_goals`, `commitment_logs`, `streak_data` | goal setting and adherence |
| `coach_sessions` | AI coach conversation history |

**Configuration / operations / admin**

| table | what it is for |
|---|---|
| `detector_flags` | per-detector rollout control: off / shadow / canary / on, with a percentage |
| `admin_settings` | runtime global settings, changeable without a redeploy |
| `guardrail_rules` | user-defined alert rules on open positions |
| `instruments` | Kite instrument master cache for symbol lookup and WebSocket subscription |
| `oauth_temp_store` | short-lived OAuth CSRF nonces |
| `monthly_snapshots` | immutable monthly summary, written before an orders partition may be dropped |
| `margin_snapshots`, `position_margin_observations` | margin utilisation over time |
| `data_quality_events` | markers for ingestion anomalies |
| `gtt_tracking` | Good-Till-Triggered order tracking and whether they were honoured |
| `admin_users`, `admin_audit_log`, `admin_login_events` | admin identity and its audit trail |
| `broadcast_logs`, `broadcast_receipts`, `push_subscriptions` | outbound messaging |
| `schema_migrations` | the migration ledger |
| `generated_reports` | saved copies of generated reports |

### 3.2 Date and age characteristics

Live `min`/`max` per table on its primary time column:

| table | rows | column | range |
|---|---|---|---|
| `instruments` | 166,222 | created_at | 2026-02-08 → **2026-07-30** |
| `trades` | 318 | created_at | 2026-02-06 → **2026-07-30** |
| `completed_trades` | 112 | exit_time | 2026-02-06 → **2026-07-30** |
| `positions` | 99 | created_at | 2026-02-09 → **2026-07-30** |
| `risk_alerts` | 57 | detected_at | 2026-02-06 → **2026-07-30** |
| `journal_entries` | 20 | created_at | 2026-03-12 → **2026-07-30** |
| `position_ledger` | 100 | occurred_at | 2026-06-15 → **2026-07-30** |
| `trading_sessions` | 9 | created_at | 2026-04-08 → **2026-07-30** |
| `cooldowns` | 215 | started_at | 2026-02-06 → 2026-07-29 |
| `behavior_events` | 145 | detected_at | 2026-07-29 → 2026-07-30 |
| `behavioral_events` | 133 | detected_at | 2026-02-09 → 2026-04-15 |
| `margin_snapshots` | 279 | snapshot_at | 2026-02-06 → 2026-04-09 |
| `incomplete_positions` | 10 | detected_at | 2026-03-11 → 2026-04-15 |
| `users` / `broker_accounts` / `user_profiles` | 3 | created_at | 2026-02-06 → 2026-08-10 |
| `schema_migrations` | 91 | applied_at | 2026-09-03 → 2026-09-04 |

### 3.3 FINDING — every trading table stops on 2026-07-30

**Classification: ~~INVESTIGATE~~ → RESOLVED, see §3.5 · Confidence: HIGH**

> **Resolved after the audit:** the account was disconnected from Zerodha around
> that date (`last_sync_at = 2026-07-31`, `status = token_expired`). No ingestion
> failure. The original analysis is retained below unchanged; §3.5 gives the
> confirmation and §3.6 records four anomalies dormancy does *not* explain.

The dates above are not scattered. **Eight independent trading tables share the
same last-write date: 2026-07-30.** Today is 2026-09-04. Nothing has been
ingested for approximately five weeks.

```
trades            -> 2026-07-30      positions         -> 2026-07-30
completed_trades  -> 2026-07-30      risk_alerts       -> 2026-07-30
position_ledger   -> 2026-07-30      journal_entries   -> 2026-07-30
trading_sessions  -> 2026-07-30      instruments       -> 2026-07-30
```

This single fact **explains several other observations in this audit** and should
be read alongside them:

- `orders` holding 0 rows with `n_tup_ins = 0` despite 211 code references
  (§18.3) — consistent with an ingestion path that has not run.
- `behavior_events` covering only **two days** (2026-07-29 → 07-30) — the
  current engine's entire production output is 145 events over 48 hours.
- `margin_snapshots` stopping even earlier, on 2026-04-09.
- The general emptiness that makes index and query analysis unusable (§12).

**What this audit can and cannot say.** It is a **fact** that no trading row has
been written since 2026-07-30. Whether that is because the environment is a dev
or staging database, because the broker connection lapsed
(`broker_accounts.status` shows one account `token_expired`), or because
ingestion is failing silently (§16.4 — 92 swallow sites) **cannot be determined
from the database alone**.

**What to review next:** this is the highest-value question raised by the audit,
because the answer changes how several other findings should be read. If
ingestion is silently broken in production, §16.4 stops being a hygiene issue.

### 3.4 Note on retention behaviour and growth expectation

Per-table retention and growth are covered in §13.2 rather than repeated here.
In summary: only `orders` and `behavior_events` are partitioned; only `orders`
has an automated retention policy; every other table accumulates without bound.


---

### 3.5 RESOLVED — why nothing has been written since 2026-07-30

**Classification: GOOD WITH NOTE · Confidence: HIGH**

§3.3 flagged this as the audit's highest-value open question. It is now
answered, and the database corroborates the account given: the app has not been
connected to Zerodha for roughly a month — no login, no trading.

Live evidence:

```
broker_user_id   status           last_sync_at
CY6001           token_expired    2026-07-31
LAB000001        connected        (never synced — replay harness identity)
DESK00001        connected        (never synced — replay harness identity)
```

`last_sync_at = 2026-07-31` sits exactly one day after the last trading row, and
the account status is `token_expired`. **There is no ingestion failure here.**
Nothing was lost; nothing was written because nothing happened.

This downgrades §3.3 from INVESTIGATE to explained, and it also resolves, with
the same explanation:

- `orders` at 0 rows with `n_tup_ins = 0` (§18.3) — the order-lifecycle
  persistence was added after the last trading session, so it has never seen a
  live order. Not a broken path; an unexercised one.
- `behavior_events` covering only 2026-07-29 → 07-30 — the current engine's
  entire production lifetime before the account went idle.
- The general emptiness that makes index and query-plan analysis unusable (§12).

**The note:** the 92 swallow-sites in §16.4 remain a real finding. They are not
the cause here, but nothing about this explanation would have surfaced a silent
write failure either — the two are indistinguishable from the database alone,
which is precisely why §16.4 matters.

### 3.6 What dormancy does NOT explain — four anomalies inside the active period

The account was live and trading from 2026-02-06 to 2026-07-30. Everything below
falls **inside** that window, so an idle account is not an explanation.

#### (a) `trading_sessions.trade_count` is never written

**Classification: DATA INTEGRITY · Severity: medium · Confidence: HIGH**

All 9 session rows report `trade_count = 0`, while `session_pnl` on the same rows
is populated and correct:

```
session_date  trade_count  session_pnl     completed_trades that day
2026-04-08         0          0.0000                 9
2026-04-09         0          0.0000                 8
2026-06-17         0        442.5000                 5
2026-06-18         0       7879.5000                 4
2026-07-29         0     -11342.4920                17
2026-07-30         0        889.9475                 7
```

**`session_pnl` is right and `trade_count` is zero on the same row.** This is the
"field written but never reliably written" case the specification asks for: the
column exists, is read as though meaningful, and no writer populates it. A
session that saw 17 completed trades reports 0.

**What to review next:** whether `trade_count` has any consumer. If it does, that
consumer is reading a permanent zero.

#### (b) 13 of 23 trading days have no session row at all

**Classification: DATA INTEGRITY · Severity: medium · Confidence: HIGH**

```
distinct trading days in the book : 23   (by fill_timestamp)
distinct exit days                : 21
trading_sessions rows             :  9
```

Days with completed trades but **no** session row:

```
2026-02-06  2026-02-09  2026-02-11  2026-02-12  2026-02-23  2026-02-24
2026-03-02  2026-03-12  2026-03-17  2026-03-18  2026-04-06  2026-04-07
2026-06-16
```

The earliest session row is 2026-04-08, so sessions were simply not created
before then — consistent with the feature arriving mid-history. But `2026-06-16`
falls **after** that date and still has no row, which the "feature arrived later"
explanation does not cover.

`get_or_create_session` is supposed to make this table complete by construction
(§14). One missing day inside the active period suggests at least one path
creates trades without ever calling it.

#### (c) 22 trades have a NULL `fill_timestamp`

**Classification: DATA INTEGRITY · Severity: low · Confidence: HIGH**

```
22 of 318 trades have fill_timestamp IS NULL
   all created 2026-02-06 (the first ingestion day)
   by status: COMPLETE 15, CANCELLED 5, REJECTED 2
   20 of the 22 DO have exchange_timestamp populated
```

Confined to the very first day of ingestion, and 20 of 22 carry an
`exchange_timestamp` that could serve as a fallback. Low severity because it is
historical and bounded — but it is why the monthly breakdown in §3.2 shows a
`None` bucket of 22 rows, and any query grouping trades by `fill_timestamp`
silently drops them.

#### (d) A three-and-a-half month hole in behavioural coverage

**Classification: INVESTIGATE · Severity: medium · Confidence: HIGH**

Trading continued through May and June; behavioural analysis did not.

```
                    Feb   Mar   Apr   May   Jun   Jul
trades               89    28    69     0    46    64
behavioral_events    82     9    42     0     0     0     <- old table stops 15 Apr
behavior_events       0     0     0     0     0   145     <- new table starts 29 Jul
risk_alerts          13     2    19     0     3    20
```

`completed_trades` in May+June: **15**. Behaviour events in either table for
May+June: **0**.

So there is a window — 2026-04-15 to 2026-07-29 — in which the trader traded,
`risk_alerts` were still raised (3 in June), and **neither event table recorded
anything**. The old engine had stopped writing and the new one had not started.

This is the migration gap between the two generations identified in §18.1, now
visible in the data: the changeover was not seamless, and the behavioural record
for that period is simply absent. It cannot be reconstructed — the events were
never written.

**What to review next:** whether that gap is known and accepted, and whether
anything downstream (analytics, baselines, personal history) treats the absence
as "no risky behaviour occurred" rather than "not measured".


---

## 4. Entity Relationship / Data-Flow Map

### 4.1 The real shape: one hub, not a chain

The specification offered `User -> Broker Account -> Orders/Trades/Positions ->
Completed Trades/Ledger -> Behavioural Events/Risk Alerts -> Journal/Insights` as
an example to be verified. **It is not the actual shape.** Live FK evidence:

```
FK parents, by number of children pointing at them (54 FKs on base tables):

  broker_accounts    37   <- 69% of every foreign key in the database
  completed_trades    5
  risk_alerts         3
  trading_sessions    3
  trades              2
  users               1
  admin_users         1
  broadcast_logs      1
  strategy_groups     1
```

The architecture is a **star, not a chain**. `broker_accounts` is the tenancy
hub, and almost every table hangs directly off it rather than off its logical
parent. `users -> broker_accounts` is the only link above the hub, and there is
exactly one FK into `users`.

The consequence is that **the chain in the example does not exist in the
schema**. `completed_trades` does not reference `positions` or `trades`;
`risk_alerts` references `completed_trades` and `trades` only optionally, via
nullable `trigger_*` columns. Lineage from a fill to the alert it caused is
carried by *nullable, optional* pointers, not by a structural chain.

### 4.2 Entity classification

| class | tables |
|---|---|
| **core identity** | `users`, `broker_accounts`, `user_profiles` |
| **transactional / ingestion** | `orders` (+24 partitions), `trades`, `positions`, `position_ledger`, `holdings`, `incomplete_positions` |
| **derived trading state** | `completed_trades`, `completed_trade_features`, `trading_sessions`, `strategy_groups`, `strategy_group_legs` |
| **behavioural** | `behavior_events` (+19 partitions), `behavioral_events`, `shadow_behavioral_events`, `behavior_events_legacy`, `risk_alerts`, `alert_checkpoints`, `alert_mutes`, `cooldowns` |
| **analytical / summary** | `monthly_snapshots`, `margin_snapshots`, `position_margin_observations`, `generated_reports`, `discipline_scores`, `discipline_streaks`, `streak_data` |
| **user-facing content** | `journal_entries`, `trading_goals`, `commitment_logs`, `coach_sessions`, `portfolio_chat_sessions` |
| **configuration / rules** | `guardrail_rules`, `constitution_history`, `detector_flags`, `admin_settings` |
| **admin / system** | `admin_users`, `admin_audit_log`, `admin_login_events`, `broadcast_logs`, `broadcast_receipts`, `push_subscriptions`, `position_alerts_sent` |
| **infrastructure / reference** | `instruments`, `schema_migrations`, `oauth_temp_store`, `data_quality_events`, `gtt_tracking` |

### 4.3 Finding - lineage is optional, so it can be silently absent

**Classification: MODIFY - Severity: medium - Confidence: HIGH**

Every link that would let you reconstruct *why* an alert fired is a nullable
column with `ON DELETE SET NULL`:

```
risk_alerts.trigger_trade_id               -> trades            ON DELETE SET NULL
risk_alerts.trigger_completed_trade_id     -> completed_trades  ON DELETE SET NULL
behavior_events.trigger_completed_trade_id -> completed_trades  ON DELETE SET NULL
behavior_events.risk_alert_id              -> risk_alerts       ON DELETE SET NULL
```

**Impact:** deleting a `completed_trade` does not delete the alert it produced -
it silently blanks the alert's only pointer back to its cause. The alert survives
as an assertion with no evidence behind it. `SET NULL` is a defensible choice for
not cascading user-visible history away, but combined with nullable columns there
is no way, after the fact, to distinguish "this alert never had a trigger" from
"the trigger was deleted".

**What to review next:** whether an alert with a null trigger should be
distinguishable from one whose trigger was removed.

---

## 5. PK / UUID Audit

### 5.1 Census

- 49 PRIMARY KEY constraints across 50 addressable tables.
- Identity strategy is overwhelmingly `uuid` with application-side generation
  (`default=uuid.uuid4` in the model) plus, on most tables, a
  `gen_random_uuid()` server default. Where both exist the application value
  wins; the server default is a backstop for raw-SQL inserts.
- `gtt_tracking.gtt_id` is `integer` (a broker-assigned id, not a local key) and
  `admin_audit_log.target_id` is `character varying` (polymorphic). Both are
  intentional and correct - they hold foreign systems' identifiers.

### 5.2 CRITICAL FINDING - `behavior_events` has no primary key

**Classification: DATA INTEGRITY / CRITICAL - Severity: high - Confidence: HIGH**

`behavior_events` is the only addressable table in the database with **no
primary key constraint at all**.

Live evidence - every constraint on the table:

```
behavior_events_broker_account_id_fkey1          FOREIGN KEY (broker_account_id) -> broker_accounts  ON DELETE CASCADE
behavior_events_risk_alert_id_fkey1              FOREIGN KEY (risk_alert_id) -> risk_alerts          ON DELETE SET NULL
behavior_events_trigger_completed_trade_id_fkey1 FOREIGN KEY (...) -> completed_trades               ON DELETE SET NULL
```

There is no `p`-type constraint. What exists instead is a **non-unique** index on
the id column:

```
idx_behavior_events_id      CREATE INDEX        ... USING btree (id)      <-- NOT unique
uq_behavior_events_idem     CREATE UNIQUE INDEX ... USING btree (broker_account_id, idempotency_key)
```

Compare the sibling partitioned table, which does it correctly:

```
orders_pkey                 PRIMARY KEY (id, order_timestamp)
uq_orders_account_kite_id   UNIQUE (broker_account_id, kite_order_id, order_timestamp)
```

**Impact:** `behavior_events.id` has no uniqueness guarantee. Two rows may share
an id, and nothing in the database would reject it. Any code that treats `id` as
a unique handle - a lookup, a join, a de-duplication - is relying on an
invariant the database does not enforce.

**Mitigating fact, verified:** duplicates do not currently exist -
`count(*) - count(DISTINCT id) = 0`, `count(*) WHERE id IS NULL = 0`, and
duplicate `idempotency_key` groups = 0. The `uq_behavior_events_idem` unique
index does provide real protection **for rows that populate `idempotency_key`**;
it provides none for rows that leave it null.

This is severity *high* rather than *critical-with-active-damage* precisely
because no corruption has occurred yet. The defect is the absent guarantee.

**What to review next:** whether the omission was deliberate (a partitioned
table's PK must include the partition key, `detected_at`, which may have been
judged undesirable) or accidental, and whether `idempotency_key` is always
populated on the live write path.

---

## 6. FK / Relationship Audit

### 6.1 Census

54 foreign keys on base tables (partitions inherit their parent's):

| ON DELETE | count |
|---|---|
| CASCADE | 44 |
| SET NULL | 9 |
| NO ACTION | 1 |

`ON UPDATE` is `NO ACTION` on all 54 - appropriate, since no primary key value
is ever updated in this design.

### 6.2 GOOD - tenancy cascade is complete and consistent

**Classification: GOOD - Confidence: HIGH**

All 37 FKs pointing at `broker_accounts` are `ON DELETE CASCADE`, as is the
single FK from `broker_accounts` to `users`. Account deletion therefore reaches
every child table structurally rather than by application bookkeeping. This is
the strongest part of the schema.

### 6.3 The single NO ACTION foreign key

**Classification: INVESTIGATE - Severity: low - Confidence: HIGH**

```
behavioral_events.trigger_trade_id -> trades   ON DELETE NO ACTION
```

Every other optional lineage pointer in the database uses `SET NULL`. This one
would instead **block** deletion of a `trades` row that any `behavioral_events`
row references. Since `behavioral_events` is the superseded event table
(see section 18), the practical exposure is limited, but it is an inconsistency
in a table that still holds 133 rows.

### 6.4 Columns ending in `_id` with no foreign key

16 such columns exist. Most are **correctly** unconstrained because they hold an
external system's identifier rather than a local row id - verified by type:

| column | type | assessment |
|---|---|---|
| `orders.kite_order_id`, `orders.exchange_order_id`, `orders.parent_order_id` | varchar | broker identifiers - **correct**, no FK possible |
| `trades.kite_order_id`, `trades.exchange_order_id`, `trades.parent_order_id`, `trades.order_id` | varchar | broker identifiers - **correct** |
| `position_ledger.fill_order_id` | **text** | broker order id, not a local key - **correct** |
| `gtt_tracking.gtt_id` (integer), `gtt_tracking.outcome_order_id` (varchar) | broker ids | **correct** |
| `admin_audit_log.target_id` | varchar | deliberately polymorphic across target types - **acceptable**, see section 11 |
| `broker_accounts.broker_user_id` | varchar | the broker's own user code (e.g. `CY6001`) - **correct** |
| `cooldowns.trigger_alert_id` | **uuid** | points at `risk_alerts`; 0 orphans today, but unenforced |
| `risk_alerts.trigger_position_id` | **uuid** | points at `positions`; 0 orphans today, but unenforced |
| `shadow_behavioral_events.trigger_completed_trade_id` | uuid | table is unused (see section 18) |
| `journal_entries.trade_id` | **uuid** | **see the confirmed defect below** |

### 6.5 CONFIRMED DATA DEFECT - `journal_entries.trade_id` is polymorphic and 35% dangling

**Classification: DATA INTEGRITY - Severity: high - Confidence: HIGH**

`journal_entries.trade_id` is a `uuid` column with **no foreign key**. Live
evidence across all 20 rows in the table:

```
total rows                    : 20
trade_id IS NOT NULL          : 20   (100% populated)
matching trades.id            :  0
matching completed_trades.id  :  4
matching positions.id         :  9
matching nothing at all       :  7
```

Constraints actually on the table:

```
journal_entries_pkey                    PRIMARY KEY (id)
journal_entries_broker_account_id_fkey  FOREIGN KEY (broker_account_id) -> broker_accounts ON DELETE CASCADE
journal_entries_setup_quality_check     CHECK (setup_quality >= 1 AND setup_quality <= 5)
```

Three separate problems, all confirmed:

1. **The column is polymorphic in practice.** Despite being named `trade_id`, it
   points at `completed_trades` for 4 rows and `positions` for 9. The same column
   means different things in different rows, with nothing recording which.
2. **Not one row points at `trades`**, the table its name implies.
3. **7 of 20 rows (35%) reference an id that exists in none of the three
   candidate tables.** These are dangling references to deleted or never-existent
   rows.

**Impact:** any code joining a journal entry to "its trade" is correct for at
most part of the table and silently wrong elsewhere. A journal entry is the
trader's own written record; a third of them cannot be tied back to anything.

**What to review next:** which table the write path actually intends
(`backend/app/api/journal.py`), whether the dangling 7 predate the recent bulk
deletion of test accounts or were caused by it, and whether the column needs a
discriminator or a split into two nullable typed columns.

---

## 7. DB ↔ Model Synchronization

Method: every mapped class was imported, and `Base.metadata` was diffed
column-by-column against `information_schema.columns` and `pg_index` from the
live database. This is mechanical, not a reading exercise.

### 7.1 Summary

| check | result |
|---|---|
| models pointing at a table that does not exist | **0** — GOOD |
| model columns missing from the DB | **0** — GOOD |
| DB columns missing from the model | **26** |
| type / precision mismatches | **55** |
| nullability mismatches | **45** |
| primary-key mismatches | **1** |

The first two lines are genuinely good news: no model refers to anything absent,
and nothing the code expects to write is missing from the database. Every
mismatch below is the database holding *more* or *differently-typed* structure
than the model admits — a drift of description, not of existence.

### 7.2 `alert_checkpoints` — the model describes 44% of the table

**Classification: MODIFY · Severity: medium · Confidence: HIGH**

```
DB    : 41 columns
model : 18 columns
missing from the model: 23
```

The 23 columns the ORM cannot see:

```
trigger_quantity        trigger_avg_entry_price  trigger_capital_at_risk
trigger_instrument_token trigger_symbol          trigger_exchange
trigger_instrument_type trigger_direction        user_exited_quantity
user_exit_price         user_exit_time           user_exit_pnl
minutes_to_exit         price_at_t5              price_at_t30
price_at_t60            counterfactual_pnl_t30   counterfactual_pnl_t60
completed_at            outcome                  money_saved_basis
confidence              checkpoint_status
```

**Impact:** more than half of this table is invisible to the ORM. Any read
through `AlertCheckpoint` returns a partial row; any write through it leaves 23
columns at their defaults. The column names (`counterfactual_pnl_t30`,
`money_saved_basis`, `outcome`) suggest a feature that was built out in SQL and
then either abandoned or moved, with the model left behind at an earlier shape.

**Live consumers:** `app/services/alert_checkpoint_service.py` is the only
non-archived consumer. A second reference exists in
`app/services/_archive/shield_service.py`, which is archived and not routed.
The table holds 1 row.

**What to review next:** whether the 23 columns are a live feature written by raw
SQL, or the residue of a removed one. The answer decides whether this is a stale
model (MODIFY) or a dead table section (RETIRE).

### 7.3 Real type mismatches (not merely cosmetic)

**Classification: MODIFY · Severity: medium · Confidence: HIGH**

Three are semantic, not stylistic:

| column | model | live DB | why it matters |
|---|---|---|---|
| `completed_trades.pnl_pct` | `Numeric(8, 2)` | `double precision` | the model promises fixed 2-decimal precision; the DB stores binary floating point. Values written outside the ORM are not rounded, and equality comparison is unsafe |
| `completed_trades.quality_score` | `Integer` | `smallint` | the model would accept values a `smallint` column rejects (>32767). Low practical risk, real range mismatch |
| `trades.raw_payload` | `JSON` | `jsonb` | `JSON` preserves text as-is; `jsonb` normalises key order and drops duplicates. Round-tripping through the ORM does not reproduce the stored bytes |

### 7.4 `VARCHAR(n)` in models vs `text` in the database — 52 columns

**Classification: GOOD WITH NOTE · Severity: low · Confidence: HIGH**

52 of the 55 type mismatches are the same shape: the model declares
`VARCHAR` or `VARCHAR(n)` where the live column is `text`. Examples:
`users.email`, `trades.tradingsymbol`, `positions.status`,
`risk_alerts.pattern_type`, `broker_accounts.access_token`.

In PostgreSQL `text` and `varchar` are the same storage with no performance
difference, so **at runtime this is harmless** and no length is being enforced
in production either way.

It is not entirely free, though, and the reason is worth recording: the test
suite builds its schema from `Base.metadata.create_all`, so **CI creates
`VARCHAR(20)` columns where production has unbounded `text`**. A value longer
than the declared limit is accepted in production and rejected in CI — the tests
are stricter than reality, which is the safe direction, but it means the two
schemas are not the same schema.

### 7.5 Nullability drift — 45 columns

**Classification: MODIFY · Severity: low-to-medium · Confidence: HIGH**

The drift runs in both directions, which matters because the two directions have
different consequences:

**Model stricter than the DB (the common case, ~35 columns).** e.g.
`trades.status`, `trades.order_id`, `trades.product`, `holdings.product`,
`instruments.lot_size`, `broker_accounts.broker_name`, and most `created_at` /
`updated_at` columns: the model says `nullable=False`, the database permits
NULL. **Anything writing outside the ORM can insert a NULL that application code
assumes cannot exist**, and the ORM will happily read it back into a field typed
as non-optional.

**Model looser than the DB (~10 columns).** e.g. `behavior_events.created_at`,
`monthly_snapshots.created_at`, `strategy_groups.status`,
`data_quality_events.details`, `guardrail_rules.created_at`: the database
enforces NOT NULL while the model believes the column is optional. This
direction is safe at runtime — the database will reject the bad write — but it
means CI (building from the model) permits rows production would refuse.

### 7.6 Primary-key mismatch — corroborates §5.2

**Classification: DATA INTEGRITY / CRITICAL · Severity: high · Confidence: HIGH**

```
behavior_events: model=['id']  db=NONE
```

The mechanical diff independently reproduces the finding in §5.2 from a
different direction: the model declares `id` as the primary key, and the live
database has no primary key constraint at all. Two independent methods agreeing
raises confidence to HIGH.

This is also the one mismatch with a concrete operational consequence today:
because CI builds from the model, **the test suite runs against a
`behavior_events` table that HAS a primary key, while production does not**. No
test can detect the missing constraint, because in the test database it is not
missing.

---

## 8. DB ↔ Backend / API Synchronization

### 8.1 Same name, different meaning — `order_id` in `trades`

**Classification: MODIFY · Severity: medium · Confidence: HIGH**

`trades` carries four order-ish columns, and the one with the most obvious name
is not the one that identifies a broker order:

| column | live values | what it actually is |
|---|---|---|
| `order_id` | 318 distinct over 318 rows, **unique-enforced** | fill-level identifier |
| `kite_order_id` | 269 distinct over 318 rows | the broker's real order id |
| `exchange_order_id` | — | exchange's id |
| `parent_order_id` | — | bracket/cover parent |

`uq_trades_broker_order` is `UNIQUE (broker_account_id, order_id)`. So a column
named `order_id` is unique **per fill**, while orders genuinely repeat across
rows under `kite_order_id`.

**Impact:** any code, query or future contributor treating `trades.order_id` as
"the order" gets one row per fill and concludes each fill was a separate order.
The naming actively misleads. Nothing is currently broken by it — the constraint
matches the actual semantics — but the name does not.

### 8.2 Transaction ownership is diffuse — 19 of 61 services commit

**Classification: MODIFY · Severity: medium · Confidence: HIGH**

Nineteen of the sixty-one modules in `backend/app/services/` call `commit()` on
a session they receive as a parameter rather than one they own:

```
admin_settings_service      ai_personalization_service   alert_checkpoint_service
behavioral_baseline_service constitution_service         cooldown_service
detector_flag_service       gtt_service                  instrument_service
live_position_engine        margin_service               pnl_calculator
push_notification_service   rag_service                  retention_policy_service
retention_service           strategy_detector            token_manager
trade_sync_service
```

**Why this matters:** a service that commits a caller's session decides, on the
caller's behalf, that everything staged so far is final. If a request handler
stages three writes and calls such a service between the first and the second,
the first is committed and the remaining two are in a new transaction. Partial
failure then leaves partial state, and no single caller can reason about
atomicity.

`pnl_calculator` committing is the most surprising of these — a calculator is
not, by name, a thing that should end a transaction.

**Confidence note:** this is a *shape* finding from static analysis. Whether any
specific one causes incorrect partial state depends on its callers, which was not
traced service-by-service. **What to review next:** the services that write
trading data (`trade_sync_service`, `live_position_engine`, `pnl_calculator`)
and whether their callers stage other work around them.

---

### 8.3 API module → table map

Built by matching every model class name and table name against the source of
each API module. 38 non-archived API modules touch at least one table.

| module | tables touched |
|---|---|
| `account_data.py` | broker_accounts, completed_trades, journal_entries, monthly_snapshots, orders, risk_alerts, trades, trading_sessions, user_profiles, users |
| `analytics.py` | behavior_events, **behavioral_events**, completed_trade_features, completed_trades, instruments, journal_entries, positions, risk_alerts, strategy_group_legs, strategy_groups, trades, trading_sessions, user_profiles |
| `zerodha.py` | **behavioral_events**, broker_accounts, completed_trades, holdings, instruments, oauth_temp_store, orders, positions, risk_alerts, trades, user_profiles, users |
| `coach.py` | coach_sessions, journal_entries, orders, positions, risk_alerts, trades, user_profiles, users |
| `risk.py` | alert_mutes, completed_trades, risk_alerts, trades, user_profiles, users |
| `cooldown.py` | completed_trades, cooldowns, positions, risk_alerts, trades, user_profiles |
| `trades.py` | completed_trades, incomplete_positions, positions, trades |
| `journal.py` | completed_trades, journal_entries, positions, trades |
| `webhooks.py` | broker_accounts, orders, positions, trades |
| `profile.py` | completed_trades, constitution_history, trades, trading_sessions, user_profiles, users |
| `admin/*` | admin_audit_log, admin_login_events, admin_users, alert_mutes, behavior_events, broadcast_logs, broadcast_receipts, broker_accounts, data_quality_events, detector_flags, monthly_snapshots, orders, push_subscriptions, risk_alerts, trades, user_profiles, users |
| others | as catalogued in the evidence file |

**Notable:** `analytics.py` and `zerodha.py` both still read **`behavioral_events`**
— the superseded event table (§18.1). So the older generation is not merely
retained data; it is still being read by two live API modules. That materially
raises the cost of retiring it and is recorded here as a cross-reference to
§18.1.

**Classification: INVESTIGATE · Severity: medium · Confidence: HIGH.**
**What to review next:** whether those two modules read `behavioral_events` as a
fallback/union with `behavior_events`, or whether they are simply stale reads
that would silently return nothing for any recent period.

### 8.4 Tables no API module touches — and whether that is a problem

Thirteen tables are not referenced by any API module. Reachability was then
re-checked across `services/`, `tasks/` and `core/` using **both the table name
and the model class name**, because searching for the table name alone would
wrongly condemn a table accessed only through its ORM class:

| table | model | reached from services/tasks/core | verdict |
|---|---|---|---|
| `position_ledger` | `PositionLedger` | **9 files** | ACTIVE — task/service layer only, correct |
| `admin_settings` | `AdminSetting` | 2 | ACTIVE |
| `gtt_tracking` | — | 2 (`behavior_engine`, `gtt_service`) | ACTIVE |
| `position_margin_observations` | `PositionMarginObservation` | 2 | ACTIVE |
| `alert_checkpoints` | `AlertCheckpoint` | 1 (`alert_checkpoint_service`) | ACTIVE, thin |
| `guardrail_rules` | `GuardrailRule` | 1 (`guardrail_tasks`) | ACTIVE, thin |
| `schema_migrations` | — | 0 | correct — owned by `scripts/migrate.py`, outside `app/` |
| `behavior_events_legacy` | — | **0** | LEGACY (§18.1) |
| `shadow_behavioral_events` | — | **0** | SUSPECT_UNUSED (§18.2) |
| `discipline_scores` | — | **0** | SUSPECT_UNUSED (§18.2) |
| `discipline_streaks` | — | **0** | see below |
| `portfolio_chat_sessions` | `PortfolioChatSession` | **0** | **see below** |
| `position_alerts_sent` | — | **0** | **see below** |

### 8.5 CONFIRMED — two tables whose only consumers have been archived

**Classification: RETIRE (pending decision) · Severity: low · Confidence: HIGH**

`portfolio_chat_sessions` and `position_alerts_sent` appeared to have consumers,
but the only matches were **stale `.pyc` bytecode**. Verified:

```
backend/app/api/portfolio_chat.py                      SOURCE GONE (only .pyc remains)
backend/app/services/portfolio_concentration_service.py SOURCE GONE (only .pyc remains)

backend/app/api/_archive/portfolio_chat.py                       <- moved here
backend/app/services/_archive/portfolio_concentration_service.py <- moved here
```

And the router was deliberately deregistered — `app/main.py:476`:

```
# NOTE: portfolio_radar / guardrails / portfolio_chat routers archived 2026-07-25 —
```

So both tables are **orphaned by a deliberate archival**, not by accident. The
project's archive-don't-delete convention was followed for the code; the tables
were left in place.

`portfolio_chat_sessions` still holds **1 row** and still has a live SQLAlchemy
model (`PortfolioChatSession`) registered in `models/__init__.py`, so it is
created by `Base.metadata.create_all` in CI despite having no consumer.

**What to review next:** whether these two tables should follow their code into
retirement, and whether the stale `.pyc` files should be cleared so future
searches do not report phantom consumers. **Note:** the `.pyc` files caused this
audit to nearly mis-classify both tables as ACTIVE — a real trap for any future
usage analysis.

### 8.6 `discipline_streaks` vs `streak_data` — likely duplication

**Classification: INVESTIGATE · Severity: low · Confidence: MEDIUM**

`discipline_streaks` (0 rows, no model, 0 reachable consumers) sits alongside
`streak_data` (1 row, model `StreakData`, reached from `goals.py`). Together with
`discipline_scores` (§18.2, zero references anywhere), these three appear to be
one feature expressed three ways, of which only `streak_data` is wired.

Recorded as INVESTIGATE rather than RETIRE because the three should be one
decision, and that decision needs product input rather than more evidence.

---

## 9. Frontend ↔ API ↔ DB Synchronization

### 9.1 Method and its limits — stated before the numbers

Backend routes were enumerated from the live FastAPI app (216 distinct `/api/*`
paths). Frontend calls were extracted by grepping `src/` for literal URL strings.

**This method under-reports frontend usage, and the report must not be read as a
list of dead endpoints.** Two concrete reasons, both verified:

1. `src/lib/adminApi.ts` builds every admin URL from a prefix constant
   (`const BASE = ... + '/api/admin'`) and calls `req('/partitions')`. No literal
   `/api/admin/partitions` string exists in the frontend, so **all 52 unmatched
   admin routes are matching artefacts, not dead endpoints.**
2. Several unmatched routes are *correctly* never called by the frontend:
   `/api/webhooks/zerodha/postback` is called by Zerodha, and
   `/api/zerodha/callback` is an OAuth redirect target.

**Classification of the whole exercise: INVESTIGATE · Confidence: LOW-to-MEDIUM.**

### 9.2 What can be said with confidence

```
216  distinct /api routes on the live app
135  distinct literal API strings in src/
122  routes with no literal match
      of which 52 are admin routes  -> explained by the BASE-prefix pattern
      of which 70 are non-admin
```

Of the 70 non-admin unmatched routes, a substantial share are explained by:
webhooks and OAuth callbacks; operational endpoints (`/api/zerodha/metrics`,
`/api/zerodha/test`, `/api/alerts/test`, `/api/notifications/test`); and
sub-paths whose parent is called via a template literal.

**One concrete candidate did survive scrutiny:**

`/api/account/monthly-summary` — the endpoint that exposes the
`monthly_snapshots` table. Its distinctive basename appears **zero** times
anywhere in `src/`. The table also holds zero rows. Endpoint and table appear to
form a complete feature with **no frontend consumer**.

**Classification: INVESTIGATE / possible MISSING · Severity: low · Confidence: MEDIUM.**

**What to review next:** a proper endpoint-usage pass that resolves template
literals and prefix constants, rather than literal matching. The number 122 in
this section should not be quoted as a count of dead endpoints.

---

### 9.3 Frontend API surface — corrected method

§9.1's literal-string matching was too crude to conclude anything. A second pass
was run against the **API client modules** rather than raw URL strings, which is
how the frontend actually calls the backend.

**Structural fact that invalidates the §9.2 numbers:** `src/lib/api.ts` does not
export a map of named functions at all — it exports an **axios instance**
(`export const api = axios.create({ baseURL: API_URL, ... })`), and callers build
URLs inline at each call site. `src/lib/adminApi.ts` **does** export a named
function map.

So the two halves of the frontend must be analysed differently, and the
"122 unmatched routes" figure in §9.2 conflates them. **That figure should not
be used.**

### 9.4 Admin surface — near-complete usage

**Classification: GOOD · Confidence: HIGH**

`adminApi.ts` exports **56** named functions. Cross-referencing every `.tsx` page:

```
referenced by at least one page : 54
never referenced by any page    :  2   -> deleteUser, exportUsersUrl
```

The admin frontend is almost entirely wired. The two unused entries are worth a
look — `deleteUser` in particular is a destructive capability defined in the
client but not surfaced in the UI.

**What to review next:** whether `deleteUser` and `exportUsersUrl` are intended
future features or residue. Neither is a defect; a defined-but-uncalled client
function is inert.

### 9.5 What can and cannot be concluded about the user-facing surface

Because `api.ts` is a bare axios instance, endpoint usage on the user-facing side
can only be established by resolving inline URL construction at ~hundreds of call
sites, including template literals. **That analysis was not completed**, and this
audit therefore makes **no claim** about which user-facing endpoints are unused.

The one conclusion that survives from §9.2 is the specific case where the
distinctive basename appears **nowhere** in `src/`:

```
/api/account/monthly-summary   -> 0 occurrences of "monthly-summary" in src/
                                  and monthly_snapshots holds 0 rows
```

Endpoint, table and service exist; no frontend consumer was found.

**Classification: INVESTIGATE · Severity: low · Confidence: MEDIUM.**


---

## 10. Data Integrity Findings

Actual data was queried, not just schema. Every check below was executed.

### 10.1 CONFIRMED CLEAN — the checks that passed

**Classification: GOOD · Confidence: HIGH**

| check | result |
|---|---|
| orphans across **every FK-enforced relationship** (all 54 FKs walked programmatically) | **0** |
| `completed_trades` with `exit_time < entry_time` | 0 |
| `completed_trades` with `exit_time` in the future | 0 |
| `positions` with `updated_at < created_at` | 0 |
| `trades` with `fill_timestamp` in the future | 0 |
| `risk_alerts` / `behavior_events` detected in the future | 0 |
| duplicate `(broker_account_id, tradingsymbol, product)` in `positions` | 0 |
| duplicate `(broker_account_id, session_date)` in `trading_sessions` | 0 |
| duplicate `behavior_events.id` | 0 |
| duplicate `behavior_events.idempotency_key` | 0 |
| `broker_accounts` with no parent user | 0 |

Where the database enforces a relationship, the data obeys it. **Every integrity
defect found in this audit is in a relationship the database does not enforce.**

### 10.2 CONFIRMED DEFECT — dangling journal references

Already detailed in §6.5. Restated here because it is the only confirmed data
defect: **7 of 20 `journal_entries` rows (35%) carry a `trade_id` that matches no
row in `trades`, `completed_trades` or `positions`.**

**Classification: DATA INTEGRITY · Severity: high · Confidence: HIGH**

### 10.3 NOT a defect — `trades` duplicate broker order ids

**Classification: GOOD WITH NOTE · Confidence: HIGH**

An initial check found 24 groups sharing
`(broker_account_id, kite_order_id, fill_timestamp)`. **This is correct
behaviour, not corruption**, and is recorded here so it is not mistaken for a
defect later:

```
trades rows              : 318
distinct order_id        : 318   <- unique, enforced
distinct kite_order_id   : 269   <- 49 rows share one with another row
null order_id            : 0
null kite_order_id       : 0
```

`trades` is a **fill-level** table. `uq_trades_broker_order` enforces uniqueness
on `(broker_account_id, order_id)`, which holds at 318/318. `kite_order_id` is
the broker's *order* identifier, and one order legitimately produces several
fills. The apparent duplication is the domain working as intended.

It does leave a naming trap, recorded in §8: the column named `order_id` is
fill-unique, while the column that actually identifies a broker order is
`kite_order_id`.

### 10.4 Stored vocabulary is historical and no longer matches the current code

**Classification: INVESTIGATE · Severity: low · Confidence: MEDIUM**

Live value census:

```
risk_alerts.pattern_type : overtrading=9, consecutive_loss=9, constitution_violation=8,
                           revenge_trade=4, martingale_behaviour=4, overtrading_burst=4,
                           same_symbol_obsession=3, profit_giveaway=3
behavior_events.detector : constitution_violation=53, session_meltdown=17,
                           consecutive_loss_streak=14, overtrading_burst=11,
                           same_symbol_obsession=10, daily_overtrading=9,
                           profit_giveaway=7, cooldown_violation=6
```

Two observations, both factual:

1. `risk_alerts.pattern_type` contains **both `overtrading` and
   `overtrading_burst`**, and `behavior_events.detector` contains
   `consecutive_loss_streak` where `risk_alerts` has `consecutive_loss`. The same
   behaviour is stored under more than one name across the two tables.
2. Neither column has a `CHECK` constraint or enum type, so any string is
   storable.

**This is not automatically a defect** — stored rows are a historical record, and
names legitimately change over time. It is flagged because nothing in the schema
distinguishes "a name we retired" from "a typo", and a consumer filtering on
`pattern_type = 'overtrading_burst'` silently misses the `overtrading` rows.

**What to review next:** whether any live query filters on these values, and
whether the two tables are supposed to share a vocabulary.

### 10.5 Test/synthetic data mixed with production data

**Classification: GOOD WITH NOTE · Confidence: HIGH**

Verified: `users` currently holds 3 rows — one real account and two
`@synthetic.local` identities used by the replay harness, both holding **zero**
trading rows. No test-shaped data remains in the trading tables.

`broker_accounts.status` census: `connected=2, token_expired=1`.

---

## 11. Constraints & Invariants

### 11.1 Census (base tables)

| constraint type | count |
|---|---|
| PRIMARY KEY | 49 (of 50 tables) |
| FOREIGN KEY | 54 |
| UNIQUE | 19 |
| CHECK | **9** |

### 11.2 The nine CHECK constraints — everything the database actually validates

```
behavioral_events   CHECK (confidence >= 0.70)
detector_flags      CHECK (rollout_pct >= 0 AND rollout_pct <= 100)
detector_flags      CHECK (mode = ANY (ARRAY['off','shadow','canary','on']))
journal_entries     CHECK (setup_quality >= 1 AND setup_quality <= 5)
risk_alerts         CHECK (lifecycle = ANY (ARRAY['live','post']))
risk_alerts         CHECK (outcome IS NULL OR outcome = ANY (ARRAY['stopped','took_anyway',...]))
trading_sessions    CHECK (risk_denominator_quality IS NULL OR ... ARRAY['GOOD',...])
trading_sessions    CHECK (session_state = ANY (ARRAY['normal','caution','danger','blowup'...]))
trading_sessions    CHECK (risk_denominator_source IS NULL OR ... ARRAY['opening',...])
```

**Nine CHECK constraints across fifty tables.** Six of the nine sit on just two
tables (`trading_sessions`, `risk_alerts`).

### 11.3 Business invariants with NO database protection

**Classification: MISSING · Severity: medium · Confidence: HIGH**

Documenting the gap only, per the specification — no implementation is proposed.

| invariant | enforced where | DB protection |
|---|---|---|
| `behavior_events.id` is unique | assumed everywhere in code | **none** (§5.2) |
| `journal_entries.trade_id` points at a real row | nowhere | **none** (§6.5) |
| `risk_alerts.severity` is one of info/caution/danger/critical | application constants | **none** — free text |
| `risk_alerts.pattern_type` is a known detector name | application registry | **none** — free text |
| `behavior_events.detector` is a known detector | application registry | **none** — free text |
| `behavior_events.severity` vocabulary | application constants | **none** — free text |
| `positions.status` / `completed_trades.status` vocabulary | application constants | **none** — free text |
| `trades.status` is COMPLETE/CANCELLED/REJECTED | broker payload | **none** — free text |
| `broker_accounts.status` is connected/token_expired/… | application constants | **none** — free text |
| `cooldowns.trigger_alert_id` references a real alert | nothing | **none** |
| `risk_alerts.trigger_position_id` references a real position | nothing | **none** |

The pattern is consistent: **status and vocabulary columns are unconstrained
free text throughout**, while the two tables that do have `CHECK` constraints
(`trading_sessions`, `risk_alerts.lifecycle`) show the team knows how to add
them. `severity` is the sharpest case — it drives whether a trader is
interrupted, and the database would accept any string at all.

### 11.4 Triggers

30 trigger definitions exist across the schema, plus event triggers. Their
detail is folded into §17 where their migration origin is examined.

---

## 12. Index & Query Audit

**Read this section with the caveat from §2.3.** The database currently holds
166,222 rows in one table and fewer than 400 in every other. At that size
Postgres prefers sequential scans regardless of indexing, so **`idx_scan` counts
and `EXPLAIN` plans cannot tell you whether an index is useful here**. Every
judgement below is made from the index definition and the query shapes in the
code; runtime statistics are cited only as weak corroboration and labelled as
such.

### 12.1 Census

```
208  indexes on the 50 base tables   (4.2 per table)
423  indexes in total including partitions
```

### 12.2 FINDING — 21 groups of exact-duplicate indexes

**Classification: PERFORMANCE · Severity: medium · Confidence: HIGH**

Twenty-one groups of indexes on the same table cover **identical column lists**.
Every duplicate is pure cost: it is maintained on every INSERT, UPDATE and
DELETE, and buys nothing a sibling index does not already provide.

Worst offenders:

```
trading_sessions      4 indexes on identical columns:
     idx_trading_session_account_date | idx_trading_sessions_account_date
     trading_sessions_broker_account_id_session_date_key | uq_trading_session_account_date

alert_checkpoints     3 identical: idx_ac_alert_id | idx_alert_checkpoints_alert_id
                                 | idx_alert_checkpoints_alert_unique
completed_trades      3 identical: idx_completed_trade_account_exit
                                 | idx_completed_trades_broker_exit | idx_ct_broker_exit
positions             3 identical: idx_positions_broker | idx_positions_broker_account_id
                                 | idx_positions_open
risk_alerts           3 identical: idx_risk_alert_account_detected
                                 | idx_risk_alerts_broker_detected | idx_risk_alerts_undelivered
```

and 16 further pairs including `users`, `instruments`, `trades`,
`broker_accounts`, `user_profiles`, `monthly_snapshots`, `position_ledger`,
`discipline_scores`, `behavioral_events`, `admin_users`.

**The naming tells the story.** Each group contains one short-form name
(`idx_ct_broker`) and one long-form (`idx_completed_trades_broker_account_id`),
frequently plus a constraint-generated index (`..._key`). This is the signature
of the same index being created under different names by different migrations
over time, with no migration ever dropping the earlier one.

**Impact:** write amplification on every insert — currently negligible at this
volume, and materially wasteful at the projected scale. On `trades` and
`positions`, the two highest-write tables, this is 2–3× the necessary index
maintenance per row.

**Important nuance:** some pairs are *not* strictly redundant. Several of the
"duplicates" are partial indexes (`idx_positions_open`,
`idx_risk_alerts_undelivered` — the names imply a `WHERE` clause) which share
leading columns but cover different row subsets. **Those are legitimate** and
must not be removed on the strength of this grouping alone. The grouping was
computed on `pg_index.indkey` (column list), which does not distinguish a
partial index from a full one.

**What to review next:** for each of the 21 groups, whether the members differ
by predicate, uniqueness, or included columns before any is considered
removable. That per-group check is not done here.

### 12.3 GOOD — partitioned indexes are correctly attached

**Classification: GOOD · Confidence: HIGH**

A partitioned index that exists on the parent but is attached to no child
indexes nothing while appearing perfectly healthy in `\d`. Verified, both
parents are correct:

```
orders           6 parent indexes, 24 partitions -> every index attached to 24/24
behavior_events  4 parent indexes, 19 partitions -> every index attached to 19/19
```

### 12.4 FK columns with no supporting index

**Classification: PERFORMANCE / GOOD WITH NOTE · Severity: low · Confidence: HIGH**

Eight FK columns are not the leading column of any index. Postgres does not
index the referencing side of a FK automatically, and an unindexed FK column
makes both joins and cascading deletes scan.

```
behavior_events.trigger_completed_trade_id        behavior_events.risk_alert_id
behavior_events_legacy.trigger_completed_trade_id behavior_events_legacy.risk_alert_id
behavioral_events.trigger_trade_id                behavioral_events.session_id
position_ledger.session_id                        risk_alerts.trigger_trade_id
```

Severity is **low** rather than medium for a specific reason: six of the eight
are on the three behaviour-event tables, two of which are superseded or unused
(§18), and all of these columns are optional lineage pointers rather than join
paths on a hot read. The two worth a second look are
`risk_alerts.trigger_trade_id` and `position_ledger.session_id`, which are on
live tables.

---

### 12.5 Query-path analysis — round trips and N+1

**Method:** the AST of every non-archived module was walked, and every `await` on
a database call occurring **inside a `for` loop** was recorded. This finds the
N+1 shape structurally rather than by reading.

```
awaited DB calls inside loops: 36
```

Distribution:

```
12  tasks/maintenance_tasks.py       7  services/trade_sync_service.py
 4  tasks/report_tasks.py            2  services/pnl_calculator.py
 2  tasks/position_monitor_tasks.py  2  tasks/retention_tasks.py
 1 each: api/account_data.py, api/admin/broadcast.py, api/journal.py,
          services/admin_settings_service.py, services/gtt_service.py,
          tasks/guardrail_tasks.py, tasks/trade_tasks.py
```

**Most of these are not N+1 in any harmful sense**, and the distinction is what
matters: the loop bound decides whether it is a bug.

- `maintenance_tasks.py` (12) loops over **partitions and months** — bounded at
  ~24, fixed regardless of user count.
- `admin_settings_service.py` loops over **settings keys** — a handful.
- `trade_sync_service.py` (7) loops over **one sync batch** of broker orders.
- `account_data.py:457` is a chunked bulk insert — deliberately batched, the
  opposite of N+1.

**Two do scale with user data, and those are the findings.**

### 12.6 FINDING — one UPDATE per fill in the P&L calculator

**Classification: PERFORMANCE · Severity: medium · Confidence: HIGH**

`app/services/pnl_calculator.py:415`, inside the fill-matching loop:

```python
# Backward compat: assign P&L to closing fill in trades table
await db.execute(
    update(Trade)
    .where(Trade.id == trade.id)
    .values(pnl=float(trade_pnl))
)
updated_count += 1
```

**One UPDATE round trip per matched exit fill.** This runs during FIFO P&L
calculation, which is on the ingestion path (§14.4) and is serialised per account
by the Redis FIFO lock — so the round trips are not merely numerous, they are
**held while the account's lock is held**.

At the current 318 fills this is invisible. At a realistic book the cost is
linear in fills and it extends the lock hold proportionally.

The comment marks it as backward compatibility — the P&L is presumably also
recorded elsewhere (`completed_trades.realized_pnl`), making this a second write
of a value that has another home. That connects it to the duplicate-source-of-truth
question in §20.1.

**What to review next:** whether the `trades.pnl` column still has a consumer,
and if so whether the loop can become a single bulk `UPDATE ... FROM (VALUES ...)`.

### 12.7 FINDING — N+1 in journal semantic search

**Classification: PERFORMANCE · Severity: low · Confidence: HIGH**

`app/api/journal.py:579`:

```python
for result in results:
    if result.get("content_id"):
        entry_result = await db.execute(
            select(JournalEntry).where(JournalEntry.id == UUID(result["content_id"]))
        )
```

One SELECT per search result, on a request path. Severity is **low** because the
search is `limit`-bounded (the caller passes a small `limit`), so the loop is
short by construction — and because this sits behind the RAG path, which §15.8
established is not currently operational (`knowledge_base` absent, pgvector not
installed).

A single `WHERE id = ANY(:ids)` would replace it. Recorded, not urgent.

### 12.8 Round trips on the hot ingestion path

Traced from §14.4. Per inbound fill the pipeline performs, at minimum:

```
1  order upsert                    (webhooks.py, ON CONFLICT)
1  commit
1  trade upsert                    (trade_sync_service)
1  position ledger apply_fill
N  UPDATE per matched exit fill    (pnl_calculator — see §12.6)
1  commit
K  detector context loads          (behavior_engine)
1  commit
```

The fixed portion is small and bounded. **`N` is the only term that grows with
the trader's own history**, and it is the finding in §12.6.

**Confidence: MEDIUM.** This is a static reading of the call path, not an
instrumented count. No query-timing facility exists to measure it (§16.5), which
is itself part of the problem: the round-trip count on the hottest path in the
system cannot currently be observed.


---

## 13. Scalability Assessment

### 13.1 Where the data actually is

```
instruments        166,222 rows   79.4 MB    99.6% of all rows in the database
everything else      < 400 rows each
```

**`instruments` is a reference cache, not user data.** It is the Kite instrument
master, refreshed wholesale rather than accumulated per user, so it does **not**
grow with the number of traders. It is the largest object today and will remain
roughly constant.

This means the database has **no meaningful production data volume yet**, and
therefore no observed growth rate to extrapolate from. Any scalability statement
below is reasoning about shape, not a measurement — stated explicitly because
the specification asks for growth rates "where observable", and they are not.

### 13.2 The tables that will grow with users, and their protections

| table | grows with | partitioned | retention | assessment |
|---|---|---|---|---|
| `orders` | every order lifecycle transition | **yes**, 24 monthly partitions | drops old partitions | protected |
| `behavior_events` | every detector firing | **yes**, 19 monthly partitions | none configured | grows without bound |
| `trades` | every fill | no | none | grows without bound |
| `positions` | every position | no | none | grows without bound |
| `completed_trades` | every closed round trip | no | none | grows without bound |
| `position_ledger` | every fill (append-only) | no | none | grows without bound |
| `risk_alerts` | every alert | no | none | grows without bound |
| `margin_snapshots` | periodic sampling | no | none | **time-driven, not user-driven** |

**Finding — the two partitioned tables are the two that were already thought
about; the unbounded ones are the higher-volume ones.**

**Classification: PERFORMANCE / INVESTIGATE · Severity: medium · Confidence: MEDIUM**

`trades`, `position_ledger` and `completed_trades` are per-fill and per-round-trip
tables with no partitioning and no retention. At any real user count they will
each exceed `orders` — which *is* partitioned — by a wide margin, because one
order produces one `orders` row but potentially several `trades` rows. The
protection has been applied to the smaller of the two growth curves.

`margin_snapshots` (279 rows) is worth separating out: it grows on a schedule
rather than with user activity, so it accumulates even when nobody trades.

### 13.3 Connection and concurrency headroom

```
max_connections                     60
statement_timeout                   2min
idle_in_transaction_session_timeout 0  (disabled)
connection path                     pgbouncer, transaction mode, port 6543
```

**`idle_in_transaction_session_timeout = 0` is a real risk at scale.**
**Classification: PERFORMANCE · Severity: medium · Confidence: HIGH.** A
transaction left open by a crashed worker or a slow external call holds its
connection and its locks indefinitely, and nothing reclaims it. With 60
connections shared between the web process, Celery workers and any maintenance
job, a handful of stuck transactions is enough to exhaust the pool. The 2-minute
`statement_timeout` bounds a single *statement* but not an idle *transaction*.

---

## 14. Transaction & Concurrency Audit

### 14.1 Ownership — see §8.2

The primary transaction finding is that 19 services commit sessions they do not
own. Not repeated here.

### 14.2 Isolation and timeouts

```
default_transaction_isolation        read committed
statement_timeout                    2min
idle_in_transaction_session_timeout  0  (disabled)
max_connections                      60
pooling                              pgbouncer, transaction mode
```

**Read committed** is the Postgres default and appropriate here. It does mean
read-modify-write sequences are not automatically safe; correctness depends on
`ON CONFLICT` upserts or explicit locking.

**`idle_in_transaction_session_timeout = 0`** is repeated from §13.3 because it
is as much a concurrency finding as a scalability one: an abandoned transaction
holds locks forever and nothing reclaims it.

### 14.3 Idempotency mechanisms present

**Classification: GOOD · Confidence: HIGH**

The schema shows deliberate idempotency design in the ingestion path:

```
position_ledger.idempotency_key      UNIQUE
behavior_events (broker_account_id, idempotency_key)   UNIQUE
trades (broker_account_id, order_id)                   UNIQUE
orders (broker_account_id, kite_order_id, order_timestamp)  UNIQUE
trading_sessions (broker_account_id, session_date)     UNIQUE
```

These are real, database-enforced duplicate-event protections on exactly the
tables that ingest external events. This is the strongest evidence in the schema
that replay and duplicate delivery were designed for.

**The gap:** `behavior_events.idempotency_key` is nullable, and with no primary
key on that table (§5.2) a row with a null key has no uniqueness protection at
all.

---

### 14.4 Ingestion path traced — webhook to persisted event

The specification asks for particular attention to ingestion, order lifecycle,
trade lifecycle, behavioural detection and scheduled jobs. Each was traced
through the source.

**The path:**

```
Zerodha POST /api/webhooks/zerodha/postback   (HMAC verified, §15.6)
   -> webhooks.py: upsert_order  -> db.commit()            [line 244]
   -> webhooks.py: db.commit()                             [line 288]
   -> Celery: persist_order_event / process_webhook_trade
        -> trade_tasks.py opens its OWN session: SessionLocal()   [340, 853, 896, 955]
        -> Redis FIFO lock per account: fifo_lock:{broker_account_id}
        -> PositionLedgerService.apply_fill  (idempotency_key = "{order_id}:ledger")
        -> db.commit()                                     [643]
        -> BehaviorEngine.analyze
        -> persist events (idempotency_key = "{event_type}:{ct.id}:{rule}")
        -> db.commit()                                     [1145, 1218]
```

**Concurrency control is real.** A Redis FIFO lock (`fifo_lock:{account}`)
serialises P&L calculation per account, with token-checked release
(`_release_lock` verifies the token before deleting, avoiding the classic
free-another-worker's-lock bug). **Classification: GOOD · Confidence: HIGH.**

### 14.5 GOOD — idempotency keys are deterministic, not random

**Classification: GOOD · Confidence: HIGH**

Both ingestion writers construct keys deterministically, so a retry reproduces
the same key and collides with the original rather than inserting a twin:

```python
# behavior_engine.py:664
idempotency_key = f"{e.event_type}:{completed_trade.id}:{e.discriminator or context['rule']}"

# trade_tasks.py:522
idempotency_key = f"{trade.order_id}:ledger"
```

The engine key includes a discriminator specifically so the multi-event
constitution detector — which emits several events per trade — does not collapse
its own events into one. That is a considered design, not an accident.

Combined with the unique constraints catalogued in §14.3 and the eleven
`ON CONFLICT` upsert sites found across the services, duplicate delivery and
task retry are handled at the database level rather than by hoping.

### 14.6 FINDING — 2 of 145 behaviour events have no idempotency key

**Classification: DATA INTEGRITY · Severity: medium · Confidence: HIGH**

Live query:

```
behavior_events total            145
idempotency_key IS NULL            2
distinct idempotency_key         143
```

`behavior_events.idempotency_key` is nullable, and two rows have no value.
**Combined with §5.2 — the table has no primary key — those two rows have no
uniqueness protection of any kind.** The `uq_behavior_events_idem` unique index
is on `(broker_account_id, idempotency_key)`, and in PostgreSQL NULLs do not
collide in a unique index, so any number of null-key rows can coexist.

This sharpens H1 from "an absent guarantee" to "an absent guarantee with rows
already outside it". It is still not corruption — the 143 keyed rows are
distinct, and no duplicate `id` exists — but the protective mechanism has
demonstrable gaps in it.

**What to review next:** which write path produced the two null-key rows, since
both documented writers construct a key unconditionally.

### 14.7 GOOD — savepoints are used where nesting is needed

**Classification: GOOD · Confidence: HIGH**

Eight `begin_nested()` sites exist across five modules:

```
services/trade_sync_service.py       4  (lines 370, 664, 871, 1068)
services/broker_margin_service.py    2
services/detector_flag_service.py    1
services/trading_session_service.py  1
```

This is the correct pattern for "try this insert, and if it collides fall back"
without destroying the caller's transaction. `trade_sync_service` — the busiest
ingestion writer — uses it in all four of its conflict-prone paths.

### 14.8 The partial-commit risk, stated precisely

**Classification: INVESTIGATE · Severity: medium · Confidence: MEDIUM**

The ingestion pipeline commits at several points within one logical unit of
work: after order upsert, after ledger application, and again after behavioural
detection. There is a deliberate rollback between stages
(`trade_tasks.py:664`) whose comment states the intent — *"Roll back any
flushed-but-uncommitted ledger data so that the behavior detection step below
doesn't accidentally commit partial state."*

So the risk was recognised and handled at that specific seam. What cannot be
established from static reading is whether **every** seam is handled: a failure
after the ledger commit but before the detection commit leaves the fill
persisted and the behavioural analysis absent, with a Celery retry re-running
detection against an already-committed ledger.

**Why that is probably safe rather than certainly safe:** the deterministic
idempotency keys (§14.5) mean a re-run collides rather than duplicates. The
residual question is whether a re-run produces the *same* key when the
intervening state has changed — which requires execution tracing, not reading.

**What to review next:** a replay of the ingestion pipeline with an induced
failure between the ledger commit and the detection commit.

### 14.9 Scheduled and maintenance jobs

**Classification: GOOD WITH NOTE · Confidence: HIGH**

Celery tasks declare bounded retries with backoff, rather than retrying forever:

```
alert_tasks        max_retries=3, default_retry_delay=30, time_limit=300, soft_time_limit=290
maintenance_tasks  max_retries=2, default_retry_delay=300 / 600
intent_tasks       max_retries=1
```

`time_limit` / `soft_time_limit` on the alert tasks is the right guard against a
task holding a connection indefinitely — and is notable because
`idle_in_transaction_session_timeout` is disabled server-side (§14.2), so the
application-level limit is the only bound on those particular tasks.

**The note:** that protection is present on `alert_tasks` and absent on the
others. A maintenance task that hangs has no time limit and no server-side idle
timeout behind it.


---

## 15. Security Audit

Reviewed from schema and code. No penetration testing was performed, no
authorisation boundary was tested by accessing data, and no secret value is
reproduced in this document.

### 15.1 CONFIRMED — Row Level Security is enabled but provides no protection

**Classification: SECURITY · Severity: medium · Confidence: HIGH**

```
RLS enabled on   : 15 tables
RLS disabled on  : 35 tables
policies defined :  0
application role : postgres,  rolsuper=false,  rolbypassrls=TRUE
table owner      : postgres  (the same role the application connects as)
```

The 15 tables with RLS enabled: `admin_login_events`, `admin_settings`,
`alert_mutes`, `behavior_events`, `behavior_events_legacy`, `broadcast_logs`,
`broadcast_receipts`, `constitution_history`, `data_quality_events`,
`detector_flags`, `gtt_tracking`, `monthly_snapshots`, `oauth_temp_store`,
`orders`, `position_margin_observations`.

Two independent reasons RLS is currently decorative:

1. **Zero policies exist.** RLS with no policy denies all access to a
   constrained role — it does not filter by tenant.
2. **The application role has `rolbypassrls = TRUE`** and is also the table
   owner, so it bypasses RLS entirely regardless.

**Impact:** tenant isolation rests **entirely** on application-layer
authorisation. That is a legitimate architecture, and this finding is not a claim
that data is exposed. What it is: the schema currently *looks* as though a
database-level control exists on 15 tables when none is in force, which is the
kind of thing that gets mistaken for defence-in-depth during a later review.

**Also inconsistent:** the 15 tables are a puzzling subset — `orders` and
`behavior_events` have RLS, while `trades`, `positions`, `completed_trades`,
`users` and `broker_accounts` (the most sensitive tables) do not. There is no
evident principle behind the selection, which suggests it was inherited from
Supabase defaults or applied piecemeal rather than designed.

**What to review next:** whether RLS was intended as real protection, and if so
why the highest-value tables are excluded; otherwise whether leaving it enabled
without policies is misleading.

### 15.2 GOOD — broker credentials are encrypted at rest

**Classification: GOOD · Confidence: HIGH**

`broker_accounts` holds `access_token`, `refresh_token`, `api_key` and
`api_secret_enc`. The model provides `encrypt_token()` / `decrypt_token()`
built on `Fernet(settings.ENCRYPTION_KEY)` (`app/models/broker_account.py:64-92`),
so tokens are ciphertext in the column rather than plaintext. The decrypt path
raises a specific error if `ENCRYPTION_KEY` changes, which is the correct
failure mode.

Admin credentials follow the same shape: `admin_users.password_hash` and
`admin_users.totp_secret_enc` are both stored in protected form.

### 15.3 Sensitive columns inventory

Recorded so the blast radius of any future export or leak is known. Names only,
no values were read.

| category | columns |
|---|---|
| broker credentials | `broker_accounts.access_token`, `.refresh_token`, `.api_key`, `.api_secret_enc` |
| admin credentials | `admin_users.password_hash`, `.totp_secret_enc` |
| PII | `users.email`, `users.guardian_phone`, `broker_accounts.broker_email`, `admin_users.email`, `admin_audit_log.admin_email`, `admin_login_events.admin_email`, `broadcast_receipts.phone` |

### 15.4 Destructive-operation safeguards at the database level

**Classification: GOOD WITH NOTE · Confidence: HIGH**

Nine event triggers exist. Eight are Supabase platform defaults
(`pgrst_ddl_watch`, `graphql_watch_ddl`, `issue_pg_cron_access`, and similar).
One is the application's own:

```
tm_protect_partitioned_tables   ON sql_drop   enabled=O
```

This is a genuine database-level guard against dropping partitioned trading
tables, and it operates independently of which client issues the statement. It
is the only destructive-operation safeguard enforced by the database rather than
by convention.

Note its scope precisely: it fires on `sql_drop` (DDL), so it protects against
dropping tables and partitions. **It does not fire on `DELETE`**, so it is not a
safeguard against data removal.

---

### 15.5 Endpoint authorisation inventory — complete

**Method:** every route handler under `backend/app/api/` was parsed with `ast`
and its `Depends(...)` chain extracted. 229 handlers were analysed. This is
static analysis of the source; no request was made and no authorisation boundary
was tested against real data.

```
route handlers parsed                       229
with a recognised auth dependency           216  (94%)
without one                                  13  (6%)
```

The recognised dependencies are `get_current_user_id`,
`get_verified_broker_account_id`, `get_current_admin`, `require_role`.

### 15.6 The 13 unauthenticated endpoints — each assessed

**Classification: GOOD WITH NOTE · Confidence: HIGH**

Every one was examined individually. **None is an unintended exposure.**

| endpoint | why unauthenticated | verdict |
|---|---|---|
| `POST /api/admin/auth/login` | it *is* the login | correct |
| `POST /api/admin/auth/verify` | OTP step of login | correct |
| `POST /api/admin/auth/totp/verify` | TOTP step of login | correct |
| `POST /api/webhooks/zerodha/postback` | called by Zerodha, not a user | **see below** |
| `GET /api/zerodha/connect` | starts OAuth, pre-authentication | correct |
| `GET /api/zerodha/callback` | OAuth redirect target | correct |
| `POST /api/zerodha/auth/exchange` | OAuth token exchange | correct |
| `GET /api/admin/config/announcement/public` | public banner text | correct by design |
| `GET /api/risk/patterns` | static pattern glossary, identical for all users | correct by design |
| `GET /api/zerodha/test`, `/metrics`, `/health` | operational probes, rate-limited | see note |
| `GET /api/metrics` (Prometheus) | scrape endpoint | **see note** |

**The webhook is properly authenticated** despite having no FastAPI auth
dependency — it verifies an HMAC:

```python
expected_checksum = hashlib.sha256(...)
return hmac.compare_digest(checksum, expected_checksum)
```

`hmac.compare_digest` is constant-time, which is the correct choice. Both a
body-checksum and a header-checksum path exist. **Classification: GOOD.**

**`/api/metrics` (Prometheus) carries a deployment assumption.** Its own
docstring states: *"No auth (internal only — protect at the [ingress])"*. That is
a deliberate decision, not an oversight, but it means **the security of this
endpoint lives outside the codebase**. If the service is ever exposed without an
ingress rule, operational metrics become public.
**Classification: SECURITY (hardening) · Severity: low · Confidence: HIGH.**
**What to review next:** confirm the ingress actually blocks `/api/metrics` in
the deployed environment — this audit cannot see that.

### 15.7 IDOR analysis — no user-facing exposure found

**Classification: GOOD · Confidence: MEDIUM-HIGH**

23 handlers accept an id-shaped parameter without an injected verified account.
**22 of the 23 are admin endpoints** (`/api/admin/users/{account_id}/...`,
`/api/admin/admins/{admin_id}/...`), where operating on another account is the
entire purpose, and every one of them carries `require_role(...)` or
`get_current_admin`. That is authorisation by role, not a missing check.

**The 23rd was examined closely and is not an IDOR:**

```python
async def connect_zerodha(
    redirect_uri: Optional[str] = None,
    user_id: Optional[str] = None,          # <-- caller-supplied, no auth
    db: AsyncSession = Depends(get_db)
):
```

`GET /api/zerodha/connect` accepts `user_id` from the query string with no
authentication. **Verified: the parameter is never read in the function body.**
The handler generates a Kite login URL and sets a CSRF nonce cookie; `user_id`
influences nothing.

**Classification: MODIFY (dead parameter) · Severity: low · Confidence: HIGH.**
It is not a vulnerability today. It is an unused, unauthenticated, user-supplied
parameter on an auth-adjacent endpoint — the kind of thing that becomes one the
moment somebody wires it up. **What to review next:** delete the parameter or
document why it exists.

**Every other user-facing endpoint derives its account from
`get_verified_broker_account_id`,** which is the correct pattern: the account
comes from the verified token, never from the request.

**Confidence is MEDIUM-HIGH rather than HIGH** because this is static dependency
analysis. It establishes that an auth dependency is *present*; it does not prove
each dependency's internal logic is correct, and it would not catch an endpoint
that authenticates correctly and then queries by an unvalidated id from the body.

### 15.8 Raw and dynamic SQL — full inventory

**Classification: GOOD WITH NOTE · Confidence: HIGH**

```
files using text()                   33
total text() occurrences             72
text(f"...") — INTERPOLATED SQL       4
```

68 of 72 use bound parameters, which is safe. **All four interpolation sites were
read individually:**

| site | interpolated value | source | verdict |
|---|---|---|---|
| `api/admin/partitions.py:121` | `{parent}` | module constant `PARTITIONED_PARENTS` | safe — not user input |
| `tasks/maintenance_tasks.py:161` | `{name}`, `{parent}`, dates | computed from `date.today()` + constant | safe |
| `tasks/maintenance_tasks.py:230` | `{name}` | regex-validated partition name from `pg_class` | safe |
| `services/rag_service.py:280` | `{patterns_array}` | **a Python list interpolated into `ARRAY['...']`** | **see below** |

**`rag_service.py:280` is the one genuine interpolation of a value into SQL:**

```python
patterns_array = "ARRAY[" + ",".join(f"'{p}'" for p in patterns) + "]"
pattern_filter = f"AND relevance_patterns && {patterns_array}"
```

A string containing a quote in `patterns` would break out of the literal. **It is
not currently exploitable, for three independent reasons, each verified:**

1. **The only caller passes a hardcoded empty list.** `app/api/coach.py:593`
   calls `get_chat_context(..., patterns_active=[])`. An empty list is falsy, so
   `pattern_filter` stays `""` and no interpolation occurs at all.
2. **The target table does not exist.** `knowledge_base` is absent from the live
   database — it is not among the 93 relations.
3. **pgvector is not installed.** The query uses `<=>` and `::vector`; no
   `vector` extension is present, so the statement could not execute.

**Classification: SECURITY (latent) · Severity: low · Confidence: HIGH.**

This is deliberately **not** rated as a confirmed vulnerability. It is a latent
injection pattern in a code path that is unreachable in the current database. It
matters only if RAG is ever enabled — at which point the input source must be
checked before the feature is switched on. **What to review next:** if
`knowledge_base` and pgvector are ever provisioned, this line must be
parameterised first.

### 15.9 Admin boundaries

**Classification: GOOD · Confidence: HIGH**

- **Admin auth is a separate subsystem** from user auth, with its own JWT, its
  own login/OTP/TOTP flow, and its own rate limiters
  (`admin_login_limiter`, `admin_otp_limiter`).
- **Impersonation is read-only, enforced centrally.** `app/main.py:310`
  registers `impersonation_readonly_middleware`, which rejects any non-safe HTTP
  method carrying a token with `imp=True` with a 403. Enforcement sits in
  middleware rather than in each endpoint, which is the right place for it.
- Role separation is used: destructive endpoints take `require_role(...)` while
  read endpoints take `get_current_admin`.

### 15.10 FINDING — an admin action can succeed while its audit row silently fails

**Classification: SECURITY · Severity: medium · Confidence: HIGH**

`app/api/admin/audit_writer.py`:

```python
    db.add(row)
    await db.commit()
except Exception as e:
    logger.error(f"audit_writer failed (action={action}): {e}")
```

The audit writer swallows every exception. **A destructive admin action —
deleting a user, erasing an account — can therefore complete successfully while
its audit record is never written**, leaving only a log line. The audit log's
value is that it is complete; a best-effort audit log cannot answer "who deleted
this account" with certainty.

Coverage is otherwise good: 28 `audit()` calls across 33 mutating admin routes.
The six mutating endpoints with no `audit()` call in their body are:

```
auth.py    admin_login, admin_logout, totp_setup_confirm, totp_disable
system.py  test_email_delivery
tasks.py   backfill_duration_minutes
```

Four of the six are authentication events, which have their own dedicated trail
in `admin_login_events` — so their absence from `admin_audit_log` is reasonable.
`test_email_delivery` is harmless. **`backfill_duration_minutes` is the notable
one**: it mutates trading data and writes no audit row.

**What to review next:** whether audit failure should be fatal to the action it
describes, and whether `backfill_duration_minutes` should be audited.

### 15.11 Migration safety and destructive-SQL safeguards

**Classification: GOOD WITH NOTE · Confidence: HIGH**

- The runner (`scripts/migrate.py`) cannot re-run a recorded migration:
  `cmd_apply` filters on `n not in recorded`.
- `cmd_adopt` writes a ledger row **without executing** — the mechanism behind
  the 87% adopt rate in §17.2.
- A `skip` verb exists and requires a reason; three migrations use it.
- **`tm_protect_partitioned_tables`** (§15.4) is the only database-enforced
  guard, and it fires on `sql_drop` only.

**The residual gap, stated plainly:** nothing prevents a destructive statement
being executed against the database by a client that bypasses the runner
entirely — `psql`, a GUI, or a script. The event trigger covers `DROP` on the
partitioned trading tables specifically; it does not cover `DELETE`, `TRUNCATE`,
`UPDATE`, or `DROP` on any other table.

### 15.12 Security summary

| finding | classification | severity |
|---|---|---|
| RLS enabled on 15 tables, 0 policies, role has `rolbypassrls` (§15.1) | SECURITY | medium |
| Audit writer swallows failures (§15.10) | SECURITY | medium |
| `rag_service.py:280` latent SQL interpolation, unreachable (§15.8) | SECURITY | low |
| `/api/metrics` unauthenticated by design, protected at ingress (§15.6) | SECURITY | low |
| `connect_zerodha` dead unauthenticated `user_id` parameter (§15.7) | MODIFY | low |
| Broker + admin credentials encrypted at rest (§15.2) | GOOD | — |
| Webhook HMAC-verified with constant-time compare (§15.6) | GOOD | — |
| Impersonation read-only enforced in middleware (§15.9) | GOOD | — |
| 216 of 229 handlers carry an auth dependency; no user-facing IDOR found (§15.7) | GOOD | — |
| 68 of 72 raw SQL uses are parameterised (§15.8) | GOOD | — |

**No confirmed vulnerability was found.** The two medium findings are both
"a control that appears to exist does not actually hold" — RLS that is bypassed,
and an audit log that can silently miss entries.


---

## 16. Observability Audit

### 16.1 The silent-failure surface

**Classification: MODIFY · Severity: medium · Confidence: MEDIUM**

```
'except Exception' occurrences in backend/app : 542
of which the next line logs and continues     : 363  (67%)
```

Two-thirds of broad exception handlers in the application swallow the error and
carry on. That is often correct — an alert-delivery failure should not cost a
fill — but at 363 instances it is the dominant error-handling idiom rather than
a considered exception.

**Impact on this audit specifically:** the failure mode "a database write did not
happen, and nothing surfaced" is structurally available in 363 places. Several
findings elsewhere in this document (`orders` with 211 code references and zero
rows ever written, §18.3) are exactly the shape that this idiom would hide.

**Confidence is MEDIUM, not HIGH**, because the count is a static grep: it does
not establish that all 363 wrap database writes, nor that any specific one is
wrong. **What to review next:** the subset of these handlers that wrap a
`commit()` or a session write, which is the population that can lose data
silently.

### 16.2 What the database itself can tell you

| capability | status |
|---|---|
| `log_min_duration_statement` | not set to a value that captures slow queries |
| `track_io_timing` | queried; not enabled |
| partition health | visible via `pg_inherits`, no built-in alerting |
| table growth | `pg_stat_user_tables` available |
| schema drift detection | **none** — no mechanism compares live schema to models |
| migration state | `schema_migrations` ledger, but 87% `adopt` (§17.2) |

**Schema drift is the notable gap.** This audit found 26 missing model columns,
55 type mismatches, 45 nullability mismatches and a missing primary key — none
of which any existing check would have surfaced. The test suite cannot find them
because it builds its schema *from the models*, so model and schema agree by
construction in CI and can diverge freely in production.

**Classification: MISSING · Severity: medium · Confidence: HIGH.**

---

### 16.3 What exists — the observability that is in place

**Classification: GOOD · Confidence: HIGH**

The application is better instrumented than §16.1's raw grep suggested:

| facility | status | evidence |
|---|---|---|
| structured logging | JSON formatter for production, coloured formatter for dev | `app/core/logging_config.py:30,70` |
| error reporting | Sentry, `traces_sample_rate=0.1`, no-op without a DSN | `app/main.py:43-52` |
| application metrics | `incr()` / `observe_ms()` counters, 29 call sites | `app/core/metrics.py:77,89` |
| admin system health | `GET /api/admin/system` | `api/admin/system.py:11` |
| engine health | `GET /api/admin/engine-metrics` | `api/admin/system.py:146` |
| recent errors | `GET /api/admin/error-feed` | `api/admin/system.py:160` |
| Prometheus scrape | `GET /api/metrics` | `api/prometheus_metrics.py` |
| partition health | `GET /api/admin/partitions` (runway, DEFAULT occupancy) | `api/admin/partitions.py` |

The Sentry integration being a **no-op without a DSN** is the right default —
the code is always present and enabling it is configuration, not a deploy.

### 16.4 REFINED FINDING — 92 places where a database write can fail silently

**Classification: MODIFY · Severity: medium · Confidence: HIGH**

§16.1 reported 363 log-and-continue handlers from a crude grep. That number is
**too broad to act on** — most of those handlers wrap network calls, cache
lookups or optional enrichment, where swallowing is correct.

Narrowing to the population that actually matters: handlers where a
`commit()`, `flush()`, `db.add()` or `execute()` appears in the preceding lines
**and** no `raise` follows:

```
except Exception AFTER a database write, with no re-raise:  92
```

A representative sample:

```
api/webhooks.py:245, 293      <- the ingestion entry point
api/journal.py:329, 359, 413  <- journal writes
api/coach.py:483, 682, 690, 741, 918
api/reports.py:85, 142
api/alerts.py:62
main.py:192, 235, 401, 411, 431
```

**Impact:** these are the 92 places where a write can fail and the request still
returns success. This is the mechanism by which a defect like `orders` holding
zero rows despite 211 code references (§18.3) could persist unnoticed — a
swallowed write leaves no trace beyond a log line nobody reads.

**Not all 92 are wrong.** `webhooks.py:245` is deliberate and documented — an
order-event write must never cost the fill behind it. The finding is that **the
idiom is applied uniformly**, so the deliberate cases are indistinguishable from
the accidental ones.

**What to review next:** the subset that wraps a `commit()` on trading data
specifically — `webhooks.py`, `journal.py` — and whether each should surface a
counter (`incr()`) so a silent failure at least becomes a visible number.

### 16.5 MISSING — no slow-query visibility

**Classification: MISSING · Severity: medium · Confidence: HIGH**

```
log_min_duration_statement   not set to capture slow queries
track_io_timing              not enabled
pg_stat_statements           not among the installed extensions
```

**There is no mechanism that would surface a slow query.** Nothing records
query durations, so a query that degrades as data grows produces no signal until
a user reports slowness or a statement hits the 2-minute `statement_timeout`.

This matters more than usual here because §12 established that **index
usefulness cannot be assessed at the current data volume**. The moment data
arrives, the only way to learn which queries actually matter is measurement —
and the measurement facility is absent.

### 16.6 MISSING — nothing detects schema drift

**Classification: MISSING · Severity: medium · Confidence: HIGH**

Restating §16.2 with the evidence this audit produced: the model↔DB diff found
**26 missing model columns, 55 type mismatches, 45 nullability mismatches and a
missing primary key.** None of these would be caught by any existing check.

The reason is structural, not an oversight of effort: **the test suite builds
its schema from `Base.metadata.create_all`**, so in CI the models and the schema
agree by construction. The tests cannot observe a divergence that only exists in
production.

This is why the missing primary key on `behavior_events` (§5.2) survived — in
the test database that primary key exists.

### 16.7 What currently happens silently — consolidated

The specification asks explicitly for this list.

| event | currently detectable? |
|---|---|
| a database write fails inside a request | **no** — 92 swallow sites (§16.4) |
| a query becomes slow as data grows | **no** — no slow-query logging (§16.5) |
| the live schema drifts from the models | **no** — CI builds from models (§16.6) |
| a migration's effect is absent despite a ledger row | **no** — 87% `adopt` (§17.2) |
| duplicate `behavior_events.id` appears | **no** — no PK to reject it (§5.2) |
| a `journal_entries.trade_id` goes dangling | **no** — no FK (§6.5) |
| an admin action's audit row fails to write | **no** — swallowed (§15.10) |
| a partition window runs out | **yes** — admin partitions endpoint reports runway |
| a Celery task fails | **partly** — retries are bounded and logged; no alerting found |
| the engine fails to analyse a trade | **yes** — `incr("engine_analyze_failed")` counter exists |
| an error occurs anywhere | **yes, if a DSN is configured** — Sentry |

The pattern: **operational health is reasonably visible; data-integrity health
is almost entirely invisible.** Every one of the "no" rows is a data-correctness
question, and every "yes" is an infrastructure question.


---

## 17. Migration / Schema History Audit

### 17.1 Ledger reconciliation — exact

```
migration files on disk : 91
ledger rows             : 91
ledger rows with no file: 0
files with no ledger row: 0
```

**The ledger and the filesystem agree completely.** No pending migration, no
orphan row, no missing file.

### 17.2 FINDING — 87% of schema history was asserted, not observed

**Classification: GOOD WITH NOTE / INVESTIGATE · Severity: medium · Confidence: HIGH**

`applied_by` distribution across the 91 ledger rows:

```
adopt   79   (87%)
runner   9   (10%)
skip     3   ( 3%)
```

**Only 9 of 91 migrations were actually observed executing through the runner.**
The 79 marked `adopt` were recorded as already-applied on the strength of schema
inspection — a *claim* that the file's effect is present, not evidence that it
ran. Reading `scripts/migrate.py` confirms `cmd_adopt` writes the ledger row
**without executing anything**.

This is a defensible way to bring an existing database under migration control,
and the alternative (replaying 79 migrations against a live database) would have
been far worse. It is recorded because of what it means for trust: for 87% of the
schema, **the ledger asserts a completion it did not witness**, so
"`migrate.py status` is clean" is not by itself evidence that the schema matches
the migrations.

The three `skip` rows are deliberate and carry a stated reason.

**What to review next:** the adopted migrations whose effects are hardest to
verify by inspection — anything that moved or transformed data rather than
adding structure, since a structural adopt can be confirmed by looking at the
schema but a data migration cannot.

### 17.3 Schema objects and their migration origin

Verification ran in both directions, as the specification requires.

**Direction 1 — migrations whose declared effect is absent from the live DB.**
The one material discrepancy found is `behavior_events` having no primary key
(§5.2). Everything else declared in the migration files that was sampled is
present.

**Direction 2 — live objects with no clear migration origin.** The schema
contains 21 non-table objects (extensions, views, sequences, functions, event
triggers). These were enumerated and are consistent with the migration set; no
object was found that could not be traced to a migration file, **with the
caveat** that a `adopt`-recorded migration cannot be distinguished from a manual
change that happened to produce the same shape. That ambiguity is inherent to
87% of the history and cannot be resolved from the current evidence.

**Confidence: MEDIUM** on direction 2, precisely because of that ambiguity.

---

## 18. Legacy / Duplicate / Unused Objects

Classified per the specification's taxonomy. **Nothing was removed.** Every
"potentially removable" item below carries its evidence and confidence, and
requires an explicit human decision.

### 18.1 CONFIRMED DUPLICATE — two generations of the behaviour-event table

**Classification: RETIRE (pending decision) · Severity: medium · Confidence: HIGH**

Four tables share the behaviour-event concept:

| table | rows | model | schema generation | live date range |
|---|---|---|---|---|
| `behavioral_events` | 133 | `BehavioralEvent` | **older** | 2026-02-09 → 2026-04-15 |
| `behavior_events` | 145 | `BehaviorEvent` | **current** | 2026-07-29 → 2026-07-30 |
| `behavior_events_legacy` | 0 | none | pre-partition remnant | — |
| `shadow_behavioral_events` | 0 | none | shadow-mode variant | — |

The two populated tables have **different schemas and non-overlapping date
ranges**, which together establish succession rather than coexistence:

```
behavioral_events : event_type, trigger_trade_id, trigger_position_key, context,
                    delivery_status, risk_score_at_event, account_equity_at_event
behavior_events   : detector, detector_version, evidence, input_snapshot,
                    trigger_completed_trade_id, idempotency_key, shadow, data_quality
```

`behavioral_events` stopped receiving rows in April; `behavior_events` began in
July. Write statistics corroborate: `behavioral_events` shows `n_tup_ins=215`
with `live=133` (82 later deleted) and **no inserts since**, while
`behavior_events` is the table the current engine writes.

`behavior_events_legacy` and `shadow_behavioral_events` are both empty, have **no
model**, and have **zero references in `backend/app`** — only in scripts.

**What to review next:** whether the 133 `behavioral_events` rows are still
needed as history. They are the only record of detector output between February
and April. Deleting the table would delete that period; keeping it means
maintaining a second schema for the same concept.

### 18.2 SUSPECT_UNUSED — `discipline_scores`

**Classification: RETIRE (pending decision) · Severity: low · Confidence: HIGH**

The only table in the database with **zero references anywhere in the
repository** — not in `backend/app`, not in `backend/scripts`, not in
`backend/tests`, not in `src/`, and no SQLAlchemy model. Zero rows.

Per the specification's instruction not to call something unused merely because
an obvious reference is missing, the search covered the table name across every
source directory. Nothing was found.

It also carries a **duplicate index pair**
(`discipline_scores_broker_account_id_week_start_key` and
`idx_discipline_scores_account_week`), so it is being maintained despite having
no consumer.

**Related:** `discipline_streaks` (0 rows, no model, 2 references in
`backend/app`) and `streak_data` (1 row, model `StreakData`, 1 reference) occupy
adjacent territory. Whether the three are one feature in three shapes is worth
a single combined decision rather than three separate ones.

### 18.3 ACTIVE but empty — do not mistake for unused

**Classification: GOOD WITH NOTE · Confidence: HIGH**

The specification is explicit that emptiness is not disuse. These tables have
**zero rows but substantial live wiring**:

| table | rows | refs in `backend/app` |
|---|---|---|
| `orders` | 0 | **211** |
| `holdings` | 0 | 92 |
| `detector_flags` | 0 | 22 |
| `admin_settings` | 0 | 16 |
| `gtt_tracking` | 0 | 13 |
| `data_quality_events` | 0 | 10 |
| `monthly_snapshots` | 0 | 8 |

`orders` is the sharpest case: 211 references, 24 partitions, six correctly
attached indexes, an event-trigger guard protecting it — and `n_tup_ins = 0`,
`seq_scan = 0`, `idx_scan = 0`. **The table has never been written to or read
from since statistics were last reset.** That is a strong signal worth
following, and it is recorded as an observation, not a conclusion: it may mean
the order-ingestion path has not run in this environment, or that statistics
were reset recently.

**Classification: INVESTIGATE · Severity: medium · Confidence: MEDIUM.**

### 18.4 Table classification summary

| classification | tables |
|---|---|
| **ACTIVE** | `users`, `broker_accounts`, `user_profiles`, `trades`, `positions`, `completed_trades`, `position_ledger`, `trading_sessions`, `risk_alerts`, `behavior_events`, `journal_entries`, `cooldowns`, `instruments`, `orders`, `holdings`, `admin_users`, `admin_audit_log`, `admin_settings`, `detector_flags`, `oauth_temp_store` |
| **SUPPORTING** | `schema_migrations`, `data_quality_events`, `alert_mutes`, `alert_checkpoints`, `push_subscriptions`, `guardrail_rules`, `constitution_history`, `monthly_snapshots`, `gtt_tracking`, `incomplete_positions`, `margin_snapshots`, `position_margin_observations`, `admin_login_events`, `broadcast_logs`, `broadcast_receipts`, `position_alerts_sent` |
| **DERIVED / ANALYTICAL** | `completed_trade_features`, `strategy_groups`, `strategy_group_legs`, `generated_reports`, `streak_data`, `discipline_streaks` |
| **USER CONTENT** | `trading_goals`, `commitment_logs`, `coach_sessions`, `portfolio_chat_sessions` |
| **DUPLICATE** | `behavioral_events` (superseded by `behavior_events`) |
| **LEGACY** | `behavior_events_legacy` |
| **SUSPECT_UNUSED** | `discipline_scores`, `shadow_behavioral_events` |

---

## 19. Missing Architecture

Only items with positive evidence in the repository or data are listed, per the
specification's instruction not to invent requirements.

### 19.1 MISSING — no uniqueness guarantee on `behavior_events`

Covered in §5.2. Listed here because it is the clearest case of a required
invariant with no database representation.

**Classification: MISSING / CRITICAL · Confidence: HIGH**

### 19.2 MISSING — no referential typing for `journal_entries.trade_id`

Covered in §6.5. The column is polymorphic in practice across three tables, and
the schema has no discriminator column recording which table a given row points
at. The evidence that this is *needed* rather than hypothetical is that the data
already uses it three ways and 35% of it dangles.

**Classification: MISSING · Confidence: HIGH**

### 19.3 MISSING — vocabulary enforcement on severity and pattern columns

Covered in §11.3. `risk_alerts.severity` decides whether a trader is
interrupted, and the database would accept any string. The evidence that
enforcement is wanted: `risk_alerts.lifecycle` and `risk_alerts.outcome` **do**
have CHECK constraints on the same table, so the pattern is established and
simply not applied to `severity` or `pattern_type`.

**Classification: MISSING · Severity: medium · Confidence: HIGH**

### 19.4 MISSING — retention/partitioning on the fastest-growing tables

Covered in §13.2. `trades`, `position_ledger` and `completed_trades` have
neither, while `orders` — which grows more slowly — has both. Evidence that this
is a real gap rather than a preference: the team already built partitioning and
a retention job, so the capability exists and was applied to the smaller curve.

**Classification: MISSING · Severity: medium · Confidence: MEDIUM**

### 19.5 MISSING — schema-drift detection

Covered in §16.2.

**Classification: MISSING · Severity: medium · Confidence: HIGH**

---

## 20. Source-of-Truth Map

| concept | authoritative table | secondary / derived | can they disagree? |
|---|---|---|---|
| user identity | `users` | — | no — single row per user, one FK in |
| broker connection | `broker_accounts` | — | no |
| user rules / capital | `user_profiles` | `constitution_history` (change log) | history is append-only; no conflict |
| instrument reference | `instruments` | — | refreshed wholesale from Kite; stale between refreshes |
| orders | `orders` (partitioned) | — | **currently empty — see §18.3** |
| fills | `trades` | `position_ledger` (append-only fill ledger) | **YES — two records of the same fill** |
| positions | `positions` | `position_ledger` (derives position state) | **YES** |
| completed trades | `completed_trades` | `completed_trade_features` (derived) | features can lag |
| P&L | computed from `completed_trades.realized_pnl` | `positions` unrealised; frontend recomputes live P&L from LTP | **YES — three computation sites** |
| behavioural events | `behavior_events` | `behavioral_events` (**superseded**), `shadow_behavioral_events` (empty) | **YES — two populated generations** |
| risk alerts | `risk_alerts` | `behavior_events.risk_alert_id` back-pointer | nullable link can be severed |
| journal | `journal_entries` | — | `trade_id` target ambiguous (§6.5) |
| session state | `trading_sessions` | derived per-session facts computed in code | recomputed, not stored twice |
| strategy classification | `strategy_groups` + `strategy_group_legs` | — | 564 inserted, 564 deleted, 0 live |
| margin | `margin_snapshots` | `position_margin_observations` | different grain; both append-only |

### 20.1 The three places two sources can genuinely disagree

**Classification: INVESTIGATE · Severity: medium · Confidence: MEDIUM**

1. **`trades` vs `position_ledger`.** Both record fills. `position_ledger` is
   append-only with its own `idempotency_key`; `trades` is keyed on
   `(broker_account_id, order_id)`. Row counts differ (318 vs 100). They are
   populated by different paths and nothing reconciles them.
2. **`positions` vs `position_ledger`.** Position state exists both as a stored
   row and as something derivable by replaying the ledger. If they diverge,
   there is no check that says so.
3. **P&L is computed in at least three places** — stored `realized_pnl` on
   `completed_trades`, unrealised P&L on `positions`, and a client-side live
   calculation in the frontend from streaming LTP. Different denominators or
   rounding in any one produces a number the trader sees that does not match the
   others.

**What to review next:** whether `trades` and `position_ledger` are meant to be
the same fact at different grains, and whether any reconciliation exists.

---

## 21. Findings by Severity

Severity reflects evidence, not alarm. Nothing here is inflated: where a defect
exists but has not yet caused damage, that is stated.

### HIGH

| # | finding | table / object | confidence | section |
|---|---|---|---|---|
| H1 | **No primary key** — `id` has no uniqueness guarantee; only a NON-unique index | `behavior_events` | HIGH | §5.2, §7.6 |
| H2 | **Polymorphic + 35% dangling reference** — 7 of 20 rows point at nothing; 0 point at `trades` despite the name | `journal_entries.trade_id` | HIGH | §6.5, §10.2 |

Both are confirmed by direct query. H1 has caused no corruption **yet** —
duplicates are currently zero — so it is the absent guarantee that is severe,
not present damage. H2 is present damage.

### MEDIUM

| # | finding | table / object | confidence | section |
|---|---|---|---|---|
| M1 | RLS enabled on 15 tables with **0 policies**, and the app role has `rolbypassrls=TRUE` — no protection in force | 15 tables | HIGH | §15.1 |
| M2 | **21 groups of duplicate indexes** (one table has 4 on identical columns) | 20 tables | HIGH | §12.2 |
| M3 | **87% of migration history is `adopt`** — asserted, never observed running | `schema_migrations` | HIGH | §17.2 |
| M4 | Model describes **44% of the table** (18 of 41 columns) | `alert_checkpoints` | HIGH | §7.2 |
| M5 | Two populated generations of the same concept, non-overlapping dates | `behavioral_events` vs `behavior_events` | HIGH | §18.1 |
| M6 | **19 of 61 services commit sessions they do not own** | `backend/app/services/` | HIGH | §8.2 |
| M7 | Fastest-growing tables have neither partitioning nor retention | `trades`, `position_ledger`, `completed_trades` | MEDIUM | §13.2, §19.4 |
| M8 | `idle_in_transaction_session_timeout = 0` with `max_connections = 60` | server config | HIGH | §13.3, §14.2 |
| M9 | **No schema-drift detection**; CI builds schema from models so drift is invisible | tooling | HIGH | §16.2 |
| M10 | 363 of 542 broad exception handlers log-and-continue | `backend/app` | MEDIUM | §16.1 |
| M11 | Status/severity/pattern columns are unconstrained free text | 9+ columns | HIGH | §11.3 |
| M12 | `order_id` is fill-unique while `kite_order_id` is the real order id | `trades` | HIGH | §8.1 |
| M13 | Three independent P&L computation sites | cross-layer | MEDIUM | §20.1 |
| M14 | `orders`: 211 code references, **zero writes and zero reads ever** | `orders` | MEDIUM | §18.3 |

### LOW

| # | finding | confidence | section |
|---|---|---|---|
| L1 | 52 `VARCHAR(n)` vs `text` mismatches — harmless at runtime, but CI is stricter than production | HIGH | §7.4 |
| L2 | 45 nullability mismatches, both directions | HIGH | §7.5 |
| L3 | 3 semantic type mismatches (`pnl_pct` numeric vs double, `quality_score` int vs smallint, `raw_payload` JSON vs jsonb) | HIGH | §7.3 |
| L4 | The single `NO ACTION` FK, inconsistent with 9 sibling `SET NULL` FKs | HIGH | §6.3 |
| L5 | 8 FK columns with no leading index (6 on superseded tables) | HIGH | §12.4 |
| L6 | `discipline_scores` — zero references anywhere in the repository | HIGH | §18.2 |
| L7 | Stored detector vocabulary drift (`overtrading` vs `overtrading_burst`) | MEDIUM | §10.4 |
| L8 | `/api/account/monthly-summary` has no frontend consumer | MEDIUM | §9.2 |

---

### 21.1 Additional findings from the deepening pass

The sections above were produced in a first pass. A second, deeper pass covered
security, transactions, query paths, observability, the API/frontend layer and
per-table purpose in full. These are the findings it added. **Nothing from the
first pass was removed or downgraded.**

#### New MEDIUM findings

| # | finding | object | confidence | section |
|---|---|---|---|---|
| M15 | **Every trading table stops writing on 2026-07-30** — 8 tables, same date, ~5 weeks before the audit | 8 tables | HIGH | §3.3 |
| M16 | `analytics.py` and `zerodha.py` still **read the superseded `behavioral_events`** table | 2 API modules | HIGH | §8.3 |
| M17 | Audit writer swallows exceptions — a destructive admin action can succeed **unlogged** | `admin/audit_writer.py` | HIGH | §15.10 |
| M18 | **2 of 145** `behavior_events` rows have a NULL `idempotency_key`; with no PK they have zero uniqueness protection | `behavior_events` | HIGH | §14.6 |
| M19 | One `UPDATE` per matched fill inside the FIFO P&L loop, **while the account lock is held** | `pnl_calculator.py:415` | HIGH | §12.6 |
| M20 | **92** exception handlers swallow a failure *after* a database write (refined from the crude 363) | `backend/app` | HIGH | §16.4 |
| M21 | **No slow-query visibility at all** — `log_min_duration_statement` unset, no `pg_stat_statements` | server config | HIGH | §16.5 |

#### New LOW findings

| # | finding | confidence | section |
|---|---|---|---|
| L9 | `rag_service.py:280` interpolates a list into SQL — latent injection, currently **unreachable** (empty caller arg, table absent, pgvector absent) | HIGH | §15.8 |
| L10 | `connect_zerodha` accepts an unauthenticated `user_id` that is **never read** — dead parameter on an auth-adjacent endpoint | HIGH | §15.7 |
| L11 | `/api/metrics` unauthenticated by design; security depends on an ingress rule this audit cannot see | HIGH | §15.6 |
| L12 | `portfolio_chat_sessions` and `position_alerts_sent` orphaned — their only consumers were archived 2026-07-25 | HIGH | §8.5 |
| L13 | N+1 in journal semantic search (limit-bounded, behind an inoperative RAG path) | HIGH | §12.7 |
| L14 | `adminApi.ts` defines `deleteUser` and `exportUsersUrl` which no page calls | HIGH | §9.4 |
| L15 | `discipline_streaks` / `streak_data` / `discipline_scores` appear to be one feature in three shapes | MEDIUM | §8.6 |

#### Corrections to first-pass findings

| first pass said | corrected to | why |
|---|---|---|
| "363 log-and-continue handlers" (§16.1) | **92** handlers that swallow after a DB write | the 363 figure included network/cache handlers where swallowing is correct; only the post-write population can lose data |
| "122 routes with no frontend match" (§9.2) | **unusable — do not quote** | `api.ts` is a bare axios instance, not a function map; the two halves of the frontend need different analysis (§9.3) |
| `alert_checkpoints`, `guardrail_rules` etc. appeared to have no consumer | **all ACTIVE** | the first search used table names only; re-running with **model class names** found the consumers (§8.4) |

That last correction is the important one methodologically: searching for a
table name alone will condemn any table accessed purely through its ORM class.
It also nearly mis-classified `portfolio_chat_sessions` in the opposite
direction, where the only "consumers" turned out to be stale `.pyc` bytecode
(§8.5).


---

## 22. Findings by Classification

**GOOD** — correct, intentional, no action needed
- Tenancy cascade complete: all 37 FKs to `broker_accounts` are `ON DELETE CASCADE` (§6.2)
- Zero orphans across all 54 FK-enforced relationships (§10.1)
- All timestamp-sanity and duplicate-natural-key checks pass (§10.1)
- Partitioned indexes correctly attached: 6/6 and 4/4 to every partition (§12.3)
- Broker tokens and admin credentials encrypted at rest (Fernet) (§15.2)
- Database-enforced idempotency on every external-ingest table (§14.3)
- Migration ledger and filesystem agree exactly: 91 = 91, zero drift (§17.1)
- No model points at a missing table; no model column missing from the DB (§7.1)

**GOOD WITH NOTE**
- `trades` duplicate `kite_order_id` is correct fill-level behaviour, not corruption (§10.3)
- `VARCHAR`/`text` divergence is runtime-harmless but makes CI and production different schemas (§7.4)
- `tm_protect_partitioned_tables` guards DDL drops but **not** `DELETE` (§15.4)
- Empty-but-wired tables must not be mistaken for unused (§18.3)

**MODIFY** — M2, M4, M6, M12, M10, and the lineage-nullability issue (§4.3)

**INVESTIGATE** — M14 (`orders` never touched), L7 (vocabulary drift), L4 (`NO ACTION` FK), M13 (P&L sites), §20.1 (`trades` vs `position_ledger`), §9 (endpoint usage needs a proper pass)

**RETIRE (pending explicit decision)** — `behavioral_events` (§18.1), `behavior_events_legacy`, `shadow_behavioral_events`, `discipline_scores` (§18.2)

**MISSING** — §19.1 through §19.5

**SECURITY** — M1 (RLS decorative)

**PERFORMANCE** — M2, M7, M8, L5

**DATA INTEGRITY** — H1, H2

**CRITICAL** — H1 is classified DATA INTEGRITY/CRITICAL for the *class* of defect
(a missing uniqueness guarantee on a live table), tempered to HIGH severity
because no duplicate exists today.

---

## 23. Recommended Follow-up Order

Ordered by (evidence strength x consequence), not by effort. **This is a review
order, not an implementation plan** — each item is a question to answer, and
several may correctly end in "leave it".

0. ~~Why has nothing been written since 2026-07-30?~~ **ANSWERED** — idle
   account, expired token, `last_sync_at = 2026-07-31`. No fault (§3.5).
   **Replaced as the top item by:** the three-and-a-half month behavioural gap
   (§3.6d). Between 2026-04-15 and 07-29 the trader traded and alerts fired, but
   neither event table recorded anything. That period's behavioural record does
   not exist and cannot be reconstructed. Decide whether anything downstream
   reads that absence as "no risky behaviour" rather than "not measured".
1. **`behavior_events` missing primary key** (H1). Decide whether the omission
   was deliberate — a partitioned PK must include `detected_at` — or accidental.
   The answer determines whether anything needs to change at all.
2. **`journal_entries.trade_id`** (H2). Establish what the write path intends,
   and whether the 7 dangling rows predate or were caused by the recent bulk
   deletion of test accounts.
3. **RLS posture** (M1). Decide whether database-level tenant isolation is
   wanted. If not, the 15 enabled-but-policyless tables are misleading and should
   be understood as such.
4. **`behavioral_events` retirement** (M5). Decide whether Feb–Apr detector
   history is worth keeping a second schema alive for.
5. **Transaction ownership** (M6). Review the three services that write trading
   data and whether their callers stage other work around them.
6. **Growth protection** (M7). `trades` / `position_ledger` / `completed_trades`
   have no partitioning or retention while the slower-growing `orders` has both.
7. **Duplicate indexes** (M2). Per-group check for partial-index predicates
   before treating any as removable.
8. **`orders` never written or read** (M14). Determine whether the ingestion path
   has simply not run in this environment.
9. **`alert_checkpoints` stale model** (M4). Live feature written by raw SQL, or
   residue of a removed one?
10. **Schema-drift detection** (M9). Nothing today would have caught any §7 finding.
11. Everything in LOW, as cleanup when the relevant area is next touched.

---

## 24. Explicit "Do Not Change Yet" List

Recorded because each of these looks wrong at a glance and is not:

| item | why it must not be "fixed" |
|---|---|
| `trades` rows sharing a `kite_order_id` | **Correct.** One broker order legitimately produces several fills. `order_id` is unique at 318/318 (§10.3) |
| The 21 "duplicate" index groups | Several members are **partial** indexes (`idx_positions_open`, `idx_risk_alerts_undelivered`) covering different row subsets. Removing on the strength of the column-list grouping alone would drop real indexes (§12.2) |
| Empty tables with heavy wiring | `orders` (211 refs), `holdings` (92), `detector_flags` (22) are live and simply have no data. Not retirement candidates (§18.3) |
| `instruments` at 166,222 rows | A reference cache refreshed wholesale, **not** per-user growth. Not a scaling problem (§13.1) |
| The 122 "unmatched" API routes | A literal-string matching artefact. All 52 admin routes are explained by the `BASE` prefix pattern; webhooks and OAuth callbacks correctly have no frontend caller (§9.1) |
| `*_id` columns without FKs | Most hold **broker** identifiers (varchar/integer) and cannot have one. Verified by type (§6.4) |
| `behavioral_events` 133 rows | The only surviving record of detector output for Feb–Apr 2026. Retire the table only after deciding that history is expendable (§18.1) |
| Migration files | 91 files = 91 ledger rows, zero drift. Do not re-run or re-adopt anything (§17.1) |
| Stale `.pyc` files | `portfolio_chat.py` and `portfolio_concentration_service.py` exist **only** as compiled bytecode; their source is in `_archive/`. Any usage search that counts `.pyc` hits will report phantom consumers (§8.5) |
| Searching by table name alone | Will wrongly condemn tables accessed only through their ORM class. `alert_checkpoints`, `guardrail_rules` and others were nearly mis-classified this way (§8.4) |
| `rag_service.py:280` | A latent SQL interpolation, but the path is unreachable (caller passes `[]`, `knowledge_base` absent, pgvector absent). Do not treat as an active vulnerability — but parameterise it **before** RAG is ever enabled (§15.8) |
| The 13 unauthenticated endpoints | All assessed individually; none is an unintended exposure. The webhook is HMAC-verified with a constant-time compare (§15.6) |

---

## 25. Evidence / Methodology

**Approach.** Sequential single-pass audit. All schema and data facts were
gathered once by live query into `backend/DB_audit/_evidence/`, then analysed
section by section, with each section appended to this document as it completed
so an interrupted session could not lose more than one section.

**Evidence rule.** Per the specification, no existing audit document, report,
prior finding, project note, `CLAUDE.md`, `MEMORY.md` or `docs/` file was used as
evidence. Migration files were used only as a secondary lead and were checked
against the live database.

**Live-query evidence files** (all timestamped, generated this pass):

```
e01_relations     e02_columns      e03_constraints   e04_indexes
e05_triggers      e06_table_stats  e07_ledger        e08_objects
e09_rls           e10_rowcounts    e11_settings
c01_models        c02_model_columns c03_model_constraints
c04_routes        c05_table_usage  w_catalogue
f01_foreign_keys  f02_missing_fk_candidates
```

**Techniques.** Catalog queries against `pg_class`, `pg_constraint`, `pg_index`,
`pg_inherits`, `pg_trigger`, `pg_event_trigger`, `pg_policies`, `pg_stat_user_*`
and `information_schema`. Exact `count(*)` on every table (cheap at this volume).
A programmatic walk of all 54 foreign keys checking each for orphans. A
mechanical column-by-column diff of `Base.metadata` against
`information_schema.columns`. Repository usage counts via ripgrep across
`backend/app`, `backend/scripts`, `backend/tests`, `src`, `alertlab`, `tradedesk`.

**Corrections made during the audit** — recorded because they affected findings:

1. `relkind` and `contype` were initially read as Python bytes reprs (`b'r'`),
   which silently produced an empty partitioned-parent list and an empty
   ON DELETE census. Both were redone with decoding in SQL.
2. A first "missing FK" list was wrong for the same reason and was discarded.
3. An apparent `trades` duplicate-key defect was investigated and found to be
   correct domain behaviour (§10.3).
4. `position_ledger.fill_order_id` was assumed to be a UUID FK; it is `text`
   holding a broker id, so its lack of an FK is correct.

**Known limits of this audit, stated plainly:**

- **Query-plan evidence is not usable.** With 166k rows in one table and <400 in
  every other, `EXPLAIN` and `idx_scan` cannot demonstrate index usefulness. All
  index findings are from definitions and code query shapes.
- **Endpoint usage analysis is weak** (§9.1). Literal string matching does not
  resolve prefix constants or template literals.
- **`adopt`-recorded migrations cannot be distinguished from manual changes**
  that produced the same shape (§17.3). This limits confidence on schema
  provenance for 87% of the history.
- **The silent-failure count is a static grep** (§16.1) and does not establish
  that any specific handler wraps a database write.
- No penetration testing, no authorisation testing against real data, and no
  secret values were read or reproduced.

**Confirmed read-only.** No DDL, no DML, no migration, no code, API, frontend or
data change was made. The only files written are this document, the evidence
files above, `backend/DB_audit/_AUDIT_STATE.md`, and progress markers added to
`backend/DB_audit/Audit.md` at the user's explicit request.

---

*End of audit. Findings are for review; nothing here has been implemented.*

