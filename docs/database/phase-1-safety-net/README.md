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

## Three decisions needed before I start

1. **Baseline as a JSON file** (recommended) — or inline?
2. **Drift check fails CI** (recommended) — or warns?
3. **Fixture in `backend/tests/`, self-contained** (recommended) — or import
   alertlab and drop the boundary?
