# Phase 1 — Safety Net

**Test-only. No production code, no schema change. Zero risk.**

This phase comes first-after-decisions for one reason: **every finding in this
audit existed because nothing would have caught it.** Until that is fixed, every
later phase is unverifiable — you would be fixing things with no way to prove
they stayed fixed.

Audit source: `../DATABASE_ARCHITECTURE_AUDIT.md` (frozen).

---

## F1 · Schema-drift detection — M9

**Audit:** §16.2, §16.6 · Classification MISSING · Severity medium · Confidence HIGH

**Why nothing caught the drift.** The test suite builds its schema from
`Base.metadata.create_all`, so in CI the models and the schema agree *by
construction*. The tests cannot observe a divergence that only exists in
production. That is precisely why the missing primary key on `behavior_events`
survived — in the test database, that primary key exists.

**What the audit found that no existing check would surface:**

```
26  DB columns missing from models
55  type / precision mismatches
45  nullability mismatches
 1  primary-key mismatch  (behavior_events: model=['id'], db=NONE)
```

**What to build:** a check that diffs `Base.metadata` against the *live*
`information_schema` and `pg_index`, failing on divergence. The mechanical diff
used during the audit already exists and is described in §25 — it imports every
model and compares column presence, type, nullability, precision and primary key.

**Design decision needed before building:** the check will immediately report
~127 known mismatches. It must therefore start from an explicit **baseline of
accepted divergences**, so that it fails only on *new* drift. Phase 6 then burns
that baseline down. Without the baseline the check is red on day one and gets
ignored, which is worse than not having it.

**Proof it works:** point it at a model with a deliberately wrong nullability and
confirm it fails; revert and confirm it passes.

---

## F2 · Live-schema assertions

**Not a numbered audit finding — this is the generalisation of several.**

`test_partition_runway.py` and `test_admin_partitions.py` assert against
migration *file text* and regexes. They answer "does the repo declare the right
partitions", which is a real question — but not "does the database have them".

A live-DB assertion file already exists (`backend/tests/test_live_partitions.py`)
covering partitions, the drop guard, FK cascade, and model/DB primary-key
agreement. This phase extends that pattern to the invariants this audit found
unguarded:

- every addressable table has a primary key — would have caught **H1**
- no `uuid` column silently accumulates dangling references — would have caught **H2**
- the FK cascade topology is unchanged — 37 FKs into `broker_accounts`, all CASCADE
- no *new* duplicate-index groups appear — baselines **M2** at 21 groups

---

## F3 · A synthetic end-to-end fixture, reusable by every later phase

**Not a numbered finding — this is the validation capability itself, and it is
the answer to "how do we validate without me trading?"**

Verified to exist already:

| capability | where |
|---|---|
| real pipeline, no Redis/Celery infrastructure | `alertlab/runner/harness.py` → `lab_environment()` |
| deterministic time | `frozen_clock()` |
| fixed synthetic identities, auto-cleaned | `ensure_lab_account()` / `teardown_lab()` |
| drives the real webhook/fill tasks | `alertlab/runner/inject.py` |
| 203-session replay of the reference book | `tradedesk/scripts/replay_tradebook.py` |
| a worked end-to-end example | `backend/tests/test_adverse_add_integration.py` |

`lab_environment()` patches Redis with a fake and runs Celery eager, so
`.delay()` executes the **real task body inline** — full ingestion through to
alert, with no worker and no Redis.

**What this phase adds:** one documented entry point that takes a list of
synthetic fills and returns the resulting rows across `orders`, `trades`,
`position_ledger`, `positions`, `completed_trades`, `behavior_events`,
`risk_alerts` and `trading_sessions` — so any later phase can assert
before/after with a single call.

**Boundary, stated honestly.** This cannot cover OAuth login, real postback
delivery, live KiteTicker ticks, the margin API, or token expiry against the
broker. Those need a live connection and are listed in `../REMEDIATION_INDEX.md`
§3 for validation whenever the account is next connected.

---

## Exit criteria

- [ ] Drift check runs in CI, fails on new divergence, passes on the recorded baseline
- [ ] Live-schema assertions cover PK presence, FK topology, dangling-uuid scan
- [ ] One-call synthetic fixture documented, with a worked example
- [ ] Full suite still green

---

# Phase 1 — Implementation Plan (for approval, nothing written yet)

Planned 2026-09-04. **Test-only. No production code, no schema change, no data
change.** This is the only phase with zero risk, and it is what makes every
later phase provable.

---

## What already exists — do not rebuild

`backend/tests/test_live_partitions.py` (31 tests, added during the audit)
already proves the *pattern* works. It covers:

```
partitioning         parent is relkind 'p', has partitions, DEFAULT exists,
                     covers today, >=6 months runway, no gaps, nothing in DEFAULT,
                     bounds tile without seams
indexes              attached to every partition (a parent index with 0 children
                     indexes nothing while looking healthy)
FK topology          orders still cascades from broker_accounts
model vs DB          primary key and nullability — but ONLY for `orders`
drop guard           093 installed, blocks unannounced DROP, allows announced
```

**Phase 1 generalises this from one table to all 50.** It does not start from
scratch.

---

## F1 · Schema-drift detection — M9

### The problem, precisely

The suite builds its schema from `Base.metadata.create_all`, so **in CI the
models and the schema agree by construction**. No test can observe a divergence
that exists only in production. That is why H1 — `behavior_events` having no
primary key — survived: in the test database that key exists.

### Current drift, measured today (this is the baseline)

```
models pointing at a table that does not exist ....  0
model columns missing from the DB .................  0
DB columns missing from the model ................. 26
type / precision mismatches ....................... 55
nullability mismatches ............................ 45
primary-key mismatches ............................  1
                                                   ---
total .............................................127
```

### What gets built

A test that imports every model, diffs `Base.metadata` against the **live**
`information_schema` + `pg_index`, and fails on anything not in a recorded
baseline. The diff logic already exists — it produced the numbers above during
the audit and can be lifted from the audit's §25 methodology.

### DECISION NEEDED — how the baseline is stored

The check reports 127 mismatches on day one. Without a baseline it is red
immediately, gets ignored, and is worse than nothing.

| option | pro | con |
|---|---|---|
| **(a) JSON file**, e.g. `tests/_schema_baseline.json` | diffable in review; Phase 6 burns it down visibly; a new drift shows as a file change | one more file to keep current |
| (b) inline dict in the test | no extra file | 127 entries inside a test is unreadable |
| (c) count-only threshold ("fail if > 127") | trivial | **useless** — one drift disappearing and another appearing nets to zero |

**My recommendation: (a).** (c) is actively dangerous — it would let a new
primary-key mismatch hide behind a fixed nullability mismatch.

### DECISION NEEDED — does it fail CI, or warn?

**My recommendation: fail.** With a correct baseline it is green on day one, so
failing means genuinely new drift. A warning-only check is a check nobody reads.

---

## F2 · Live-schema assertions, generalised

Extends the existing file's pattern to the invariants the audit found unguarded:

| assertion | would have caught |
|---|---|
| every addressable table has a primary key | **H1** |
| no `uuid` column accumulates dangling references | **H2** |
| FK cascade topology unchanged — 37 into `broker_accounts`, all CASCADE | silent cascade change |
| no *new* duplicate-index groups beyond the recorded 21 | **M2** regressions |
| every `*_id` uuid column either has an FK or is on a recorded exception list | **H2**-class defects |

The dangling-reference scan is the valuable one and is cheap at this data
volume: for every `uuid` column with no FK, count rows whose value matches no
row in the plausible target. `journal_entries.trade_id` returns 7 today — that
is the check working, so it starts baselined at 7 and Phase 2 drives it to 0.

---

## F3 · The synthetic end-to-end fixture

### A constraint I found while planning, which changes the design

**The backend suite deliberately does not import `alertlab/`.** From
`test_adverse_add_integration.py:43`:

> *"Built here rather than imported from the alertlab harness so the backend
> suite has no dependency outside backend/ — this test must run wherever the
> rest of them do."*

That is a real architectural boundary, and my earlier Phase 1 write-up ignored
it. `alertlab/runner/inject.py` has exactly the helpers a fixture wants —
`round_trip`, `losing_trade`, `winning_trade`, `structure`, `partial_fills` —
but backend tests cannot reach them without breaking that boundary.

### DECISION NEEDED — where the fixture lives

| option | pro | con |
|---|---|---|
| **(a) `backend/tests/_pipeline.py`**, self-contained | respects the boundary; runs wherever the suite runs; follows the existing precedent | re-implements a thin slice of `inject.py` |
| (b) import from `alertlab/` | no duplication; richer helpers | breaks a deliberate boundary; backend suite gains an external dependency |
| (c) move the shared part into `backend/` and have alertlab import it | one implementation, correct direction | largest change; touches alertlab, which is outside this remediation |

**My recommendation: (a) now, (c) later if the duplication ever hurts.** The
duplicated slice is small — building a postback payload and calling
`process_webhook_trade.apply()` — and `test_adverse_add_integration.py` already
does exactly this successfully.

### What it provides

One call that takes synthetic fills and returns the resulting rows across
`orders`, `trades`, `position_ledger`, `positions`, `completed_trades`,
`behavior_events`, `risk_alerts`, `trading_sessions` — so any later phase can
assert before/after in one line.

### Honest boundary

Cannot cover: OAuth login, real postback delivery over the network, live
KiteTicker ticks, the margin API, token expiry against the broker. Those need a
live connection and are listed in `../REMEDIATION_INDEX.md` §3.

---

## What Phase 1 explicitly does NOT do

- No production code changes.
- No schema or data changes.
- Does **not** fix any of the 127 drift items — it records them so Phase 6 can
  burn them down measurably.
- Does **not** remove the `AlertCheckpoint` model. That changes what
  `create_all` builds, which is what this phase's baseline is computed from.
  Model removal is Phase 8, deliberately after this.

---

## Order of work

1. Drift check + baseline file → confirm green on the recorded 127.
2. Prove it catches drift: deliberately break one model's nullability, confirm
   red, restore, confirm green. *(Same technique used on the trade_count test in
   Phase 0a — a check that cannot fail on the defect it describes is worthless.)*
3. Generalise the live-schema assertions (F2).
4. Build and document the synthetic fixture (F3), with one worked example.
5. Full suite + confirm the run still adds zero rows.

---

# BUILT — 2026-09-06

All three decisions were answered as recommended: a JSON baseline, the drift
check **fails** CI, and the fixture is self-contained under `backend/tests/`
with no `alertlab` import. The user added one constraint: test and demo
scaffolding must stay clearly separable from production code, and remediation
fixes must land in the real production code — enforced by a test, not a
convention (`test_no_production_code_imports_the_test_package`).

## What shipped

| file | what it is |
|---|---|
| `backend/tests/schema_diff.py` | the comparator. Pure functions over a schema snapshot, no database, so the rules are unit-testable |
| `backend/tests/_schema_baseline.json` | 88 accepted divergences, each with `db`, `model`, `phase` and `why` |
| `backend/tests/generate_schema_baseline.py` | writes the initial baseline. **Refuses to overwrite an existing one** |
| `backend/tests/test_schema_drift.py` | F1 — the live-database drift check (3 tests) |
| `backend/tests/test_schema_diff_rules.py` | the normalisation rules, each with its counter-example, plus the model-loading guard (31 tests) |
| `backend/tests/test_live_schema_invariants.py` | F2 — dangling references, FK topology, duplicate indexes (4 tests) |
| `backend/tests/synthetic_pipeline.py` | F3 — the fixture |
| `backend/tests/test_synthetic_pipeline.py` | F3 proved, plus the production/test boundary guard (9 tests) |

**47 new tests.** No production code changed, no schema changed, no migration.

## The 127 was not 127 real differences

The audit's figure counted rendered type strings. Re-measured with the
normalisation rules written down:

```
                                    audit    measured    what changed
DB columns missing from the model      26          26    -
model columns missing from the DB       0           0    -
nullability mismatches                 45          47    +2, see below
type / precision mismatches            55          14    see below
primary-key mismatches                  1           1    -
                                      ---         ---
                                      127          88
```

The 41 that disappeared were never differences:

```
 69  timestamptz vs TIMESTAMP     the same type. str(DateTime(timezone=True))
 46  timestamptz vs DATETIME      prints DATETIME and drops the flag entirely
 40  text vs VARCHAR              String() with no length IS text in Postgres
  8  ARRAY vs ARRAY               the generic sqlalchemy.ARRAY was not resolved
```

So the comparator reads the type OBJECT, never `str(type_)`, and every
equivalence rule is pinned by two tests — one proving it treats an equivalent
pair as equal, one proving the neighbouring non-equivalent pair still fails.
`text` equals `String()`; `text` does **not** equal `String(20)`.

## The 86, by owning phase

| phase | count | what |
|---|---|---|
| **2** | 1 | H1 — `behavior_events` has no primary key in the database |
| **6** | 61 | schema hygiene: nullability and type drift |
| **8** | 26 | `alert_checkpoints`, retired by Phase 0 decision D3 |

### The 26 are one dead table

`alert_checkpoints` has two generations of columns stacked in the database: 18
the model declares, and 23 it does not. Those 23 (`trigger_*`, `user_exit*`,
`counterfactual_pnl_t30`, `money_saved`, `money_saved_basis`, `confidence`,
`checkpoint_status`) are the first-generation money-saved design, and searching
the whole repo for `trigger_avg_entry_price` across `.sql` and `.py` returns
nothing.

**No migration and no code anywhere in the repo creates them.** They were
applied out-of-band and the source is gone — the same shape as the 090
incident. The table holds 1 row and D3 already retires it, so they are
baselined to Phase 8 rather than synced into the model.

### The 45 nullability mismatches split by direction, and the direction matters

| direction | count | risk |
|---|---|---|
| DB nullable, model `NOT NULL` | 32 | model stricter. No ORM write can corrupt anything; a migration, script or console write can leave a NULL the app then breaks on |
| DB `NOT NULL`, model nullable | 15 | **model looser.** The app believes NULL is fine and the database rejects the INSERT at runtime |

The 15 are mostly `created_at`/`updated_at` on eleven tables that have a
`server_default` and no `nullable=False`; `strategy_groups.status` and
`data_quality_events.details` need a look. The 32 concentrate in `trades` (13)
and `holdings` (6) — built early by migration, tightened later in the models
only.

### The 14 genuine type mismatches

```
completed_trades.pnl_pct        double precision  vs  Numeric(8,2)   <- correctness
completed_trades.quality_score  smallint          vs  Integer
trades.raw_payload              jsonb             vs  JSON           <- not equivalent
positions.tradingsymbol/status/product/exchange/instrument_type
position_ledger.entry_type
trading_sessions.session_state
data_quality_events.tradingsymbol/exchange/kind
alert_checkpoints.calculation_status                text vs VARCHAR(n)
```

`pnl_pct` is the correctness one. The `text` vs `String(n)` group is a length
ceiling the model believes in and the database does not enforce.

## F2 — two audit figures corrected by measurement

| | audit prose | measured 2026-09-06 | why |
|---|---|---|---|
| FKs into `broker_accounts` | 37, all CASCADE | **37, all CASCADE** | confirmed — but only when partition children are excluded. Counting them gives 80, because each `orders` partition carries its own copy |
| duplicate index groups | 21 | **14** | grouped by (table, columns, uniqueness, partial predicate, expression), which is when two indexes are genuinely interchangeable. A partial index is not a duplicate of a full one on the same column, and three tables have exactly that pair |
| dangling `journal_entries.trade_id` | 7 of 20 | **7 of 20** | confirmed |
| `*_id` uuid columns with no FK | — | **4** | `cooldowns.trigger_alert_id`, `journal_entries.trade_id`, `risk_alerts.trigger_position_id`, `shadow_behavioral_events.trigger_completed_trade_id` |

Each is asserted in **both** directions. A count going down because a phase
fixed something must update the file, or the improvement is invisible and the
next regression re-hides it. The unprotected-uuid list is asserted as a SET,
not a count, so a new one appearing while an old one is fixed cannot net to
zero.

## F3 — the fixture, and what building it found

`synthetic_account()` is an async context manager that commits a throwaway
user + broker account, drives the real webhook tasks, snapshots eight tables,
and deletes everything in a `finally`. Cleanup runs even when the body raises,
which is asserted directly.

Two things surfaced only because the fixture ran the real path:

**1. `trading_capital` is on `UserProfile`, not `User` — a trap, not a
production defect.** Setting it on the user succeeds silently, because
assigning an undeclared attribute to a mapped instance is just a Python
attribute set, and the value never reaches the database. The first version of
this fixture did that and every capital-relative detector abstained while
looking configured. **Production does not make this mistake** — checked: both
`app/api/constitution.py:220` and `app/tasks/maintenance_tasks.py:398` go
through the profile. Recorded because the silence is the dangerous part, not
because anything is broken.

**2. `persist_order_event` has never worked. Not once.**

```
app/tasks/trade_tasks.py::persist_order_event   calls asyncio.run()
app/tasks/trade_tasks.py                        has NO module-level import asyncio
persist_order_event                             has NO function-local one either
```

Eight of the nine tasks in that file that call `asyncio.run()` import it
locally. This one does not, so **every invocation raises
`NameError: name 'asyncio' is not defined`**, retries three times, and is
swallowed at both call sites. Shipped in `492f73a`.

This corrects a fact recorded in `_START_HERE_NEXT_SESSION.md`:

> *"`orders` has 0 rows and that is expected — order-lifecycle persistence
> shipped after the last trading session, so it has never seen a live order.
> This is the one finding whose resolution is inferred, not observed."*

The inference was wrong. `orders` is empty because **the writer crashes on
every call**, and reconnecting the account would not have produced a single
row. The fix is one line; it is production code and therefore outside this
phase, recorded in `KNOWN_BROKEN_STEPS` with
`test_known_broken_steps_are_still_broken` failing the moment it starts
working, so the fixture cannot go on quietly excusing it.

**FIXED the same day, on approval.** One line: `import asyncio` at module scope
in `app/tasks/trade_tasks.py`. The guard did exactly its job — it went red the
moment the task started succeeding, forcing the entry out of
`KNOWN_BROKEN_STEPS`, which is now empty. A synthetic postback writes an
`orders` row, asserted by `test_an_order_event_reaches_the_orders_table`.

`orders` remains at 0 rows in production, and that is now genuinely expected:
no order has arrived since the account disconnected on 2026-07-31.

## A third defect, in this phase's own work

The drift check passed on its own and **failed in the full suite**, reporting
two differences that had not been there minutes earlier:

```
admin_login_events.created_at : nullable_db_strict
admin_settings.updated_at     : nullable_db_strict
```

Cause: it did `import app.models` and trusted the package to register every
model. It does not. `app/models/__init__.py` imports **35 of the 37** model
modules — `admin_login_event` and `admin_setting` are missing from it — so
`Base.metadata` held two fewer tables when the check ran alone than when it ran
after some other test happened to import them.

A check whose result depends on what else ran in the same process is not a
check. Fixed by `load_all_models()`, which walks `app/models/*.py` and imports
every module, so the model set is the same whatever else has run and a model
added tomorrow is covered whether or not anyone remembers to export it. Pinned
by `test_every_model_module_is_loaded_not_just_the_exported_ones`, and the
specific two-module gap is named in
`test_loading_every_model_registers_more_tables_than_the_package_alone` so
closing it in `__init__.py` shows up as a deliberate change rather than
silently making the test vacuous.

The baseline is therefore **88**, not the 86 first generated: the two extra are
both `nullable_db_strict` on tables that were previously invisible to it.

Worth recording as a method note: **this is the second time in this phase that
running the real thing contradicted a reasonable-looking assumption.** The
first was `orders` being empty for a completely different reason than the audit
inferred. Both were found by executing, not by reading.

Separately, `app/models/__init__.py` not exporting two of its models is a real
defect in production code and is **not fixed**. Measured consequence:

```
import app.models
'admin_settings'      in Base.metadata.tables  ->  False
'admin_login_events'  in Base.metadata.tables  ->  False
```

Runtime is unaffected — every consumer imports those two straight from their
own module (`app/api/admin/admins.py:33`, `app/services/admin_settings_service.py:95`)
— but anything that builds a schema from the models, `create_all` against a
fresh database included, would silently omit both tables. Two lines to fix.

## How this behaves from here

| event | what happens |
|---|---|
| a model changes without a migration | `test_no_new_schema_drift` fails, naming the column |
| the schema changes without a model | same test, same message |
| the change was intentional | add a baseline entry in the same commit, with a `why` and a phase. A reviewer sees the line |
| Phase 6 fixes a drift | `test_no_stale_baseline_entries` fails until the entry is removed — the file must shrink |
| someone tries to silence a drift | a bare name is rejected; `db`, `model`, `phase` and `why` are all required, and an empty `why` fails |
| someone regenerates the baseline | the generator refuses to overwrite |
