# Phase 9 — No-Action Register

Not a work phase. This exists so that **"nothing was left out" is verifiable
rather than asserted**: every audit finding that requires no work is recorded
here, with the reason.

Audit source: `../DATABASE_ARCHITECTURE_AUDIT.md` (frozen).

---

## 1. Resolved after the audit — 2 findings

### M15 · Every trading table stops writing on 2026-07-30

**Audit:** §3.3 → resolved in §3.5 · Confidence HIGH

Originally the audit's highest-value open question: eight independent trading
tables sharing the same last-write date, five weeks before the audit.

**Resolved.** The account was disconnected from Zerodha around that date. Live
evidence:

```
broker_user_id   status           last_sync_at
CY6001           token_expired    2026-07-31    <- one day after the last trading row
```

No ingestion failure. Nothing lost. Nothing written because nothing happened.

**Retained caveat:** the 92 swallow-sites (M20, Phase 7) remain a real finding.
They are not the cause here — but nothing about this explanation would have
surfaced a silent write failure either. An idle account and a silently-broken
ingestion path look **identical** from the database, which is exactly why M20
matters.

### M14 · `orders` has 211 code references and zero rows

**Audit:** §18.3 → resolved by §3.5 · Confidence HIGH

`n_tup_ins = 0`, `seq_scan = 0`, `idx_scan = 0` despite heavy wiring, 24
partitions, six correctly-attached indexes and an event-trigger guard.

**Resolved by the same explanation.** Order-lifecycle persistence was added
*after* the last trading session, so the table has never seen a live order. It is
an **unexercised** path, not a broken one.

**This is the one to re-verify when the account is next connected** — it is the
only finding whose resolution is inferred rather than directly observed. A single
live order should produce rows.

---

## 2. Verified GOOD — no action required

Recorded so these are not re-litigated in a later review.

### Schema and relationships

- **Tenancy cascade is complete and consistent** — all 37 FKs into
  `broker_accounts` are `ON DELETE CASCADE`, as is the single FK to `users`.
  Account deletion is structurally correct rather than bookkept in application
  code. (§6.2)
- **Zero orphans across all 54 FK-enforced relationships** — every FK was walked
  programmatically. Where the database enforces a relationship, the data obeys
  it. (§10.1)
- **All timestamp-sanity checks pass** — no `exit_time < entry_time`, no future
  timestamps, no `updated_at < created_at`. (§10.1)
- **No duplicate natural keys** in `positions` or `trading_sessions`; no
  duplicate `behavior_events.id` or `idempotency_key`. (§10.1)
- **No model points at a missing table; no model column is missing from the
  DB.** (§7.1)

### Partitioning

- **Partitioned indexes are correctly attached** — `orders` 6/6 across 24
  partitions, `behavior_events` 4/4 across 19. A parent index attached to no
  children indexes nothing while looking healthy in `\d`; verified correct. (§12.3)
- **Migration ledger and filesystem agree exactly** — 91 files, 91 rows, zero
  orphans, zero checksum drift. (§17.1)

### Ingestion and concurrency

- **Database-enforced idempotency on every external-ingest table** —
  `position_ledger`, `behavior_events`, `trades`, `orders`, `trading_sessions`
  all carry unique keys designed for replay and duplicate delivery. (§14.3)
- **Idempotency keys are deterministic, not random**, so a retry collides with
  the original rather than inserting a twin. The engine key includes a
  discriminator specifically so the multi-event constitution detector does not
  collapse its own events. (§14.5)
- **Savepoints are used where nesting is needed** — 8 `begin_nested()` sites
  across 5 modules, including all four conflict-prone paths in
  `trade_sync_service`. (§14.7)
- **Redis FIFO lock serialises P&L per account**, with token-checked release
  that avoids the free-another-worker's-lock bug. (§14.4)
- **Celery retries are bounded with backoff**, and `alert_tasks` carries
  `time_limit`/`soft_time_limit`. (§14.9)

### Security

- **216 of 229 handlers carry an auth dependency.** All 13 without one were
  assessed individually; none is an unintended exposure. (§15.6)
- **The webhook is HMAC-verified** with `hmac.compare_digest` — constant-time,
  with both body- and header-checksum paths. (§15.6)
- **Broker and admin credentials are encrypted at rest** via Fernet;
  `password_hash` and `totp_secret_enc` likewise. (§15.2)
- **Impersonation is read-only, enforced centrally** in middleware
  (`main.py:310`) rather than per-endpoint. (§15.9)
- **No user-facing IDOR found.** (§15.7)
- **68 of 72 raw-SQL uses are parameterised**; three of the remaining four
  interpolate trusted internal constants. (§15.8)
- **`tm_protect_partitioned_tables`** is a genuine database-level guard against
  dropping partitioned trading tables, independent of the client issuing the
  statement. (§15.4)

---

## 3. Explicit "Do Not Change Yet" — §24

Carried verbatim in intent. **Each of these looks wrong and is not.** Changing
any of them without reading the reasoning would cause damage.

| item | why it must not be "fixed" |
|---|---|
| `trades` rows sharing a `kite_order_id` | **Correct.** One broker order legitimately produces several fills. `order_id` is unique at 318/318 (§10.3) |
| The 21 "duplicate" index groups | Several members are **partial** indexes covering different row subsets. The grouping was computed on column list, which cannot see a predicate. Dropping on that basis alone removes real indexes (§12.2) |
| Empty tables with heavy wiring | `orders` (211 refs), `holdings` (92), `detector_flags` (22) are live and simply have no data. Not retirement candidates (§18.3) |
| `instruments` at 166,222 rows | A reference cache refreshed wholesale, **not** per-user growth. Not a scaling problem (§13.1) |
| The 122 "unmatched" API routes | A literal-string matching artefact. All 52 admin routes are explained by the `BASE` prefix pattern; webhooks and OAuth callbacks correctly have no frontend caller (§9.1, §9.3) |
| `*_id` columns without FKs | Most hold **broker** identifiers (varchar/integer) and cannot have one. Verified by type (§6.4) |
| `behavioral_events` 133 rows | The only surviving record of detector output for Feb–April 2026. Retire only after deciding that history is expendable (§18.1) |
| Migration files | 91 files = 91 ledger rows, zero drift. Do not re-run or re-adopt anything (§17.1) |
| Stale `.pyc` files | `portfolio_chat.py` and `portfolio_concentration_service.py` exist only as bytecode; source is in `_archive/`. Any usage search counting `.pyc` hits reports phantom consumers (§8.5) |
| Searching by table name alone | Will wrongly condemn tables accessed only through their ORM class. `alert_checkpoints`, `guardrail_rules` and others were nearly mis-classified this way (§8.4) |
| `rag_service.py:280` | A latent SQL interpolation, but unreachable today. Do not treat as an active vulnerability — but parameterise it **before** RAG is ever enabled (§15.8) |
| The 13 unauthenticated endpoints | All assessed individually; none is an unintended exposure (§15.6) |

---

## 4. Method corrections carried forward

Three first-pass figures were wrong and were corrected in the second pass. They
are recorded here because the wrong numbers are memorable and could be quoted
later:

| wrong | correct | why |
|---|---|---|
| "363 log-and-continue handlers" | **92** that swallow after a DB write | the 363 counted network/cache handlers where swallowing is correct |
| "122 routes with no frontend match" | **unusable — do not quote** | `api.ts` is a bare axios instance, not a function map |
| several tables appeared to have no consumer | **all ACTIVE** | the first search used table names only; re-running with **model class names** found them |
