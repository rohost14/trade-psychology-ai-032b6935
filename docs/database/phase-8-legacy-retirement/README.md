# Phase 8 — Legacy Retirement

**Destructive. Last by design.** Every item here deletes something, and every one
is blocked on a Phase 0 decision. Nothing in this phase should be started before
those answers exist.

Audit source: `../DATABASE_ARCHITECTURE_AUDIT.md` (frozen).
Blocked on: **D1, D3, D5, D6, D7, D8**.

---

## Standing constraints for this phase

- **No table is dropped without an explicit, recorded decision** — the audit
  classifies these as "RETIRE (pending decision)", never as "delete".
- **The project rule is archive-don't-delete for source files.** Phase 8 should
  follow the same instinct for data: export before dropping.
- **There are no database backups on this plan.** Anything dropped is gone. That
  raised the cost of every item below.
- Migration `093` installs an event trigger that refuses `DROP` on
  `orders`/`behavior_events` and their partitions unless the transaction sets
  `tm.allow_drop`. It does **not** fire on `DELETE`.

---

## R1 · `behavioral_events` — the superseded event table — M5, blocked by M16

**Audit:** §18.1, §8.3 · RETIRE (pending decision) · Severity medium · Confidence HIGH
**Blocked on D1.**

```
behavioral_events   133 rows   2026-02-09 → 2026-04-15   old schema
behavior_events     145 rows   2026-07-29 → 2026-07-30   current schema
```

Different schemas, non-overlapping dates — succession, not coexistence.

**The blocker, and it is a real one: `analytics.py` and `zerodha.py` still read
this table.** It is on live read paths, not merely retained history. Retiring it
without changing those two modules would break them, or silently return nothing.

**Sequence:** D1 decides → update the two readers → export the 133 rows → then
retire. Not before.

If retired, **L4 (the lone `NO ACTION` foreign key) disappears with it**, and six
of the eight unindexed FK columns in L5 become moot.

---

## R2 · `behavior_events_legacy` and `shadow_behavioral_events`

**Audit:** §18.1, §18.2 · Severity low · Confidence HIGH

Both empty, both with no model, both with **zero references in `backend/app`**.
`behavior_events_legacy` appears in 1 script; `shadow_behavioral_events` in 5.

Lower risk than R1 — no rows to lose. Confirm the scripts that reference them are
not something you still run, then retire.

---

## R3 · `discipline_scores` — L6, and the streak family — L15

**Audit:** §18.2, §8.6 · Severity low · Confidence HIGH / MEDIUM
**Blocked on D5 and D7.**

| table | rows | model | consumers |
|---|---|---|---|
| `streak_data` | 1 | `StreakData` | `goals.py` — **wired, keep** |
| `discipline_streaks` | 0 | none | none reachable |
| `discipline_scores` | 0 | none | **none anywhere in the repository** |

`discipline_scores` is the only table in the database with zero references
anywhere — and it carries a **duplicate index pair**, so it is being maintained
for nothing.

Treat all three as **one decision** (D7), not three.

---

## R4 · `portfolio_chat_sessions` and `position_alerts_sent` — L12

**Audit:** §8.5 · Severity low · Confidence HIGH
**Blocked on D6.**

Both tables' only consumers were **deliberately archived on 2026-07-25**:

```
backend/app/api/_archive/portfolio_chat.py
backend/app/services/_archive/portfolio_concentration_service.py
app/main.py:476  # NOTE: portfolio_radar / guardrails / portfolio_chat routers archived 2026-07-25
```

`portfolio_chat_sessions` holds 1 row and still has a live model registered in
`models/__init__.py`, so CI creates it on every run.

**Do this regardless of the retirement decision:** clear the stale `.pyc` files
for the two archived modules. They caused this audit to nearly mis-classify both
tables as ACTIVE and will mislead any future usage analysis in exactly the same
way.

---

## R5 · `alert_checkpoints` — M4, conditional

**Audit:** §7.2 · Severity medium · Confidence HIGH
**Blocked on D3.**

Only lands in this phase **if D3 answers "abandoned"**. If the feature is live or
paused, this belongs in Phase 6 (sync the model) and not here.

23 of 41 columns are invisible to the ORM. 1 row. One non-archived consumer
(`alert_checkpoint_service.py`), one archived.

---

## R6 · `trading_sessions.trade_count` — M22, conditional

**Audit:** §3.6a · Severity medium · Confidence HIGH
**Blocked on D8.**

Lands here **only if D8 answers "nothing reads it"**, in which case dropping the
column is correct and populating it would be wasted work. Otherwise it stays in
Phase 3 as a fix.

---

## R7 · Endpoints and client functions with no consumer

**Audit:** §9.2, §9.4 · Severity low · Confidence MEDIUM

- **L8** — `/api/account/monthly-summary`: the distinctive basename appears
  **zero** times in `src/`, and `monthly_snapshots` holds 0 rows. Endpoint,
  service and table exist with no frontend consumer.
- **L14** — `adminApi.ts` defines `deleteUser` and `exportUsersUrl`, which no
  page calls. `deleteUser` is a destructive capability defined in the client but
  not surfaced in the UI.

Both are inert rather than harmful. **Note the confidence caveat:** §9 established
that the endpoint-usage method is weak, and the "122 unmatched routes" figure
from the first pass is a method artefact that must not be used. These two
survived closer scrutiny; anything else in that list has not.

---

## R8 · The endpoint-usage analysis is incomplete — L17

**Audit:** §9.5 · INVESTIGATE · Severity low · Confidence LOW

**This is a gate on R7, not a finding in itself.**

Because `src/lib/api.ts` is a bare axios instance rather than a named-function
map, user-facing endpoint usage can only be established by resolving inline URL
construction across hundreds of call sites, including template literals. **That
analysis was not completed**, and the audit therefore makes **no claim** about
which user-facing endpoints are unused.

Only two candidates survived closer scrutiny and appear in R7 (L8, L14).
**Anything else that looks like a dead endpoint has not been verified** — and the
first-pass figure of "122 unmatched routes" is a method artefact that must not be
used as a work list.

**Before retiring any endpoint beyond L8/L14:** complete a proper usage pass that
resolves prefix constants and template literals.

---

## Exit criteria

- [ ] Every retirement traces to a recorded Phase 0 decision
- [ ] Data exported before any drop — there are no backups
- [ ] R1 sequenced correctly: readers updated **before** the table goes
- [ ] Stale `.pyc` files cleared for archived modules
- [ ] Phase 1 assertions updated to match the new expected schema
- [ ] Full suite green; synthetic replay unaffected
