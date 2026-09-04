# Phase 7 — Observability

The audit's summary of this area: **operational health is reasonably visible;
data-integrity health is almost entirely invisible.**

Audit source: `../DATABASE_ARCHITECTURE_AUDIT.md` (frozen).

---

## M20 · 92 places where a database write can fail silently

**Audit:** §16.4 · MODIFY · Severity medium · Confidence HIGH
**Supersedes M10** — the first pass reported 363 from a crude grep; that number
included network and cache handlers where swallowing is correct and **should not
be used**.

Narrowed to the population that can actually lose data — a `commit()`,
`flush()`, `db.add()` or `execute()` in the preceding lines, and no `raise`
after:

```
except Exception AFTER a database write, with no re-raise:  92
```

Representative sites:

```
api/webhooks.py:245, 293      <- the ingestion entry point
api/journal.py:329, 359, 413  <- journal writes
api/coach.py:483, 682, 690, 741, 918
api/reports.py:85, 142
api/alerts.py:62
main.py:192, 235, 401, 411, 431
```

**Not all 92 are wrong.** `webhooks.py:245` is deliberate and documented — an
order-event write must never cost the fill behind it. **The finding is that the
idiom is applied uniformly**, so the deliberate cases are indistinguishable from
the accidental ones.

**Why this matters more than it looks.** This is the mechanism by which a defect
like `orders` holding zero rows despite 211 code references could persist
unnoticed. It is also why the recent five-week gap in writes was ambiguous: an
idle account and a silently-failing ingestion path **look identical** from the
database. That ambiguity is the cost of this pattern.

**Proportionate scope:** start with the subset wrapping a `commit()` on trading
data — `webhooks.py`, `journal.py`. Each should at minimum increment a counter
(`incr()`), so a silent failure becomes a visible number. Do not attempt all 92.

---

## M21 · No slow-query visibility at all

**Audit:** §16.5 · MISSING · Severity medium · Confidence HIGH

```
log_min_duration_statement   not set to capture slow queries
track_io_timing              not enabled
pg_stat_statements           not among the installed extensions
```

**Nothing records query durations.** A query that degrades as data grows produces
no signal until a user reports slowness or a statement hits the 2-minute
`statement_timeout`.

This matters more here than in most systems because Phase 5 established that
**index usefulness cannot be assessed at the current data volume**. The moment
real data arrives, measurement is the only way to learn which queries matter —
and the measurement facility is absent. Installing it *before* volume arrives is
much cheaper than diagnosing after.

---

## M3 · 87% of migration history was asserted, not observed

**Audit:** §17.2 · GOOD WITH NOTE / INVESTIGATE · Severity medium · Confidence HIGH

```
adopt   79   (87%)
runner   9   (10%)
skip     3   ( 3%)
```

**Only 9 of 91 migrations were observed executing through the runner.** The 79
`adopt` rows were recorded as already-applied on the strength of schema
inspection — a *claim* that the file's effect is present, not evidence that it
ran. `cmd_adopt` writes the ledger row **without executing anything**.

This is a defensible way to bring an existing database under migration control,
and replaying 79 migrations against a live database would have been far worse.
It is recorded for what it means for trust: for 87% of the schema, **the ledger
asserts a completion it did not witness**, so "`migrate.py status` is clean" is
not by itself evidence that the schema matches the migrations.

The ledger and filesystem otherwise agree exactly — 91 files, 91 rows, zero
drift, zero checksum changes.

**Practical action:** the adopted migrations whose effects are hardest to verify
by inspection are the ones that **moved or transformed data** rather than adding
structure. A structural adopt can be confirmed by looking at the schema; a data
migration cannot. Identify that subset and decide whether any needs verification.

---

## What already exists — do not rebuild

| facility | where |
|---|---|
| structured JSON logging (prod) + coloured (dev) | `app/core/logging_config.py:30,70` |
| Sentry, `traces_sample_rate=0.1`, no-op without DSN | `app/main.py:43-52` |
| `incr()` / `observe_ms()` counters, 29 call sites | `app/core/metrics.py:77,89` |
| admin system health | `GET /api/admin/system` |
| engine health | `GET /api/admin/engine-metrics` |
| recent errors | `GET /api/admin/error-feed` |
| partition health incl. runway and DEFAULT occupancy | `GET /api/admin/partitions` |
| engine failure counter | `incr("engine_analyze_failed")` |

Sentry being a no-op without a DSN is the right default — enabling it is
configuration, not a deploy.

---

## What currently happens silently — the consolidated list

| event | detectable today? | addressed by |
|---|---|---|
| a database write fails inside a request | **no** | M20 |
| a query becomes slow as data grows | **no** | M21 |
| the live schema drifts from the models | **no** | Phase 1 / F1 |
| a migration's effect is absent despite a ledger row | **no** | M3 |
| duplicate `behavior_events.id` appears | **no** | Phase 2 / H1 |
| a `journal_entries.trade_id` goes dangling | **no** | Phase 2 / H2 |
| an admin action's audit row fails to write | **no** | Phase 4 / M17 |
| a partition window runs out | yes | — |
| a Celery task fails | partly — retries bounded and logged; no alerting found | M20 |
| the engine fails to analyse a trade | yes — counter exists | — |
| an error occurs anywhere | yes, if a DSN is configured | — |

Every "no" is a data-correctness question. Every "yes" is an infrastructure
question. That asymmetry is the finding.

---

## Exit criteria

- [ ] M20 — trading-data write failures surface a counter; deliberate swallows marked as such
- [ ] M21 — slow-query visibility enabled before real volume arrives
- [ ] M3 — data-transforming adopted migrations identified and dispositioned
- [ ] The "silently" table above has fewer "no" rows, and the remaining ones are deliberate
