# Pattern 15 — `cooldown_violation`

**Review, 29 Aug 2026. CLOSED — DELETED.**

The blocking question below was answered: system-imposed cooldowns will not run
from the live pipeline, so the detector was retired the same day. Shared cooldown
infrastructure is untouched — `cooldown_service`, the `Cooldown` model and table,
the `/cooldown` API, the danger zone's use of them, and the trader's
`cooldown_after_loss` rule all remain.

Review-order 15. Source-list **#8**, recorded as *"IMPLEMENTED BUT NOT YET
VERIFIED — cannot fire in replay"*. That note is confirmed below, and the reason
turns out to matter more than the note did.

Measured against the real book — **175 sessions, 740 rounds** — running the real
detectors in process.

---

## Current behaviour

**What it is supposed to detect.** Trading while a cooldown is in force.

**Mechanism, end to end.**

```python
if not ctx.active_cooldowns: return None
cooldown = ctx.active_cooldowns[0]
if cooldown.started_at and ct.entry_time < cooldown.started_at: return None   # F18
-> DetectedEvent(severity="info", "Traded during active cooldown (Nmin remaining)")
```

| | |
|---|---|
| registry | `nature=discipline`, `disposition=analytics`, `trigger=exit`, v1.0.0, `notification_level=0` |
| severity | **always `info`** — hardcoded |
| thresholds | **none of its own** |
| consumes | `active_cooldowns`, `completed_trade` |
| evidence | remaining minutes, cooldown reason |
| confidence | none set |

**Where the cooldowns come from.** `ctx.active_cooldowns` is loaded in
`_load_context` from the `cooldowns` table: unexpired and not skipped, **with no
ordering**, and the detector takes `[0]`.

Rows are created in exactly one place — `danger_zone_service.trigger_intervention`
— reachable from exactly two call sites:

- `POST /danger-zone/trigger-intervention` (explicit API call)
- `POST /sync/all` (the manual full-sync endpoint)

**`trigger_intervention` is called from no Celery task.** The live pipeline —
postback → `process_webhook_trade` → engine — never creates a cooldown.

---

## What is correct

**F18's fix is right and is doing real work.** The detector now checks that the
trade was *entered* after the cooldown began. Without it, a position opened
hours earlier and merely closed during a cooldown was reported as a violation —
the opposite of the truth, since closing is what a cooldown wants.

**It is pure of database access.** 42 lines, reads only `ctx`, no `await`, no
query, no I/O.

**It has no thresholds of its own**, so there is nothing unsourced to defend.
The duration lives on the `Cooldown` row that already exists.

**The severity is honest for what it is.** `info` + `analytics` + `notification_level=0`
is consistent, and under the now-closed INFO rule it correctly never notifies.

---

## Problems found

### 1. Its subject does not occur on the live path

Cooldowns exist only if someone hits `/sync/all` or the explicit trigger
endpoint **while already in danger or critical**. The per-trade pipeline that
runs this detector never creates one.

So in ordinary operation the detector's precondition is absent, and it returns
`None` on the first line.

### 2. The registry copy describes a different detector

> *"Time between a losing exit and your next entry, **against the cooldown you
> set**."*

That is **not what this detector does**. It reads a system-imposed `Cooldown`
row created by a danger-zone intervention. It never reads the trader's declared
`cooldown_after_loss` and never measures a gap.

The copy accurately describes **`constitution_violation`'s cooldown rule**,
which is a different detector — see below. The description was written for the
behaviour, and attached to the wrong implementation of it.

### 3. Complete overlap with a detector that does it better

`constitution_violation` (behavior_engine ~3218) has a **`cooldown` rule**:

```python
cooldown_min = th.get("user_cooldown_min")      # the trader's DECLARED rule
gap = entry_time - last_loss.exit_time
if 0 <= gap < cooldown_min:  add("cooldown", "danger", ...)
```

| | `cooldown_violation` | `constitution_violation` / cooldown |
|---|---|---|
| source of the rule | system, danger-zone intervention | **the trader's own declared value** |
| severity | `info` — invisible | **`danger`** |
| fires on this book | **0** | **181** |
| message | *"Traded during active cooldown"* | *"Your 15-minute cooldown rule violated: entered X 3 min after a ₹2,400 loss"* |

Measured at a declared value of 15 minutes, `constitution_violation` raised
**181 events, all `danger`** — exactly the population that falls inside the
window. **The behaviour is fully covered, at a notifying severity, by the rule
the trader actually set.**

A third consumer exists: `revenge_trade` reads `user_cooldown_min` to raise its
own severity to at least `caution` on a declared breach.

### 4. It is not time-pure

`remaining_min` is computed from `datetime.now(timezone.utc)`. The event's
message and evidence therefore depend on **when the detector runs**, not only on
the trade. A re-run days later would produce a different, negative "remaining"
figure. No database access, but not deterministic.

### 5. `active_cooldowns[0]` is arbitrary

The loader applies no `ORDER BY`. With more than one active cooldown the
detector reports whichever row the database returned first. In practice
concurrent cooldowns are unlikely, and this has never been observed — recorded,
not asserted as harmful.

---

## Evidence

| question | answer | strength |
|---|---|---|
| does it fire on the reference book? | **0** — no cooldown rows exist in a tradebook | conclusive for replay, silent on production |
| can it fire in production? | **yes, but only** after `/sync/all` or an explicit API call while in danger | verified by tracing every writer |
| is the behaviour real? | **yes** — 181 of 449 post-loss entries (40%) fall inside a 15-minute window | measured |
| is it already covered? | **yes, completely** — `constitution_violation` raises 181 at `danger` | measured |
| is the copy accurate? | **no** — it describes `constitution_violation`'s rule | verified |
| is it pure? | DB-free, but **time-dependent** | verified |
| are its thresholds justified? | **it has none** | verified |

**What the evidence cannot say:** whether this detector produces useful records
in production. Zero firings here is a property of the tradebook, not proof of
absence — and there is no other data to consult.

---

## Recommended behavioural contract

> **Subject.** A cooldown the SYSTEM imposed after a danger-zone intervention
> was in force, and a position was **entered** anyway.
>
> **Not the subject.** The trader's own declared `cooldown_after_loss`. That is
> a *commitment*, it belongs to `constitution_violation`, and it already fires
> there at `danger` with the trader's own number in the message.
>
> **Fires when** an unexpired, unskipped cooldown existed and the entry occurred
> at or after it began.
>
> **Claims nothing about outcome**, and cannot: it has never fired on any data
> available to us.
>
> **Disposition: evidence.** Records, never notifies.

The contract's value depends entirely on whether system-imposed cooldowns are
something the product intends to keep. **That is a product question, not a
detector question.**

---

## Exact changes required

**None to the detector's logic.**

One defect is unambiguous and bounded: **the registry copy describes a different
detector's mechanism.** Correcting it would mean saying "a cooldown the system
imposed was breached", not "the cooldown you set". That is a copy fix, and it
does not depend on the verdict below.

Recorded for later reviews, **not** fixed here:

- **The trader's declared `cooldown_after_loss` does not drive cooldown
  duration.** `_calculate_duration` uses `config.base_duration_minutes` or an
  `ESCALATION_LADDER`. The declared value feeds `revenge_window_min`,
  `revenge_window_caution_min` and `user_cooldown_min` instead. So a
  system-imposed cooldown is not the trader's cooldown — which is *why* the copy
  is wrong, and is a `cooldown_service` question.
- `active_cooldowns[0]` with no ordering.

---

## Verdict — **DEFER** → **DELETED** (approved same day)

Not KEEP AS-IS: the copy is provably wrong, and a detector whose precondition
never occurs on the live path is not in a steady state worth confirming.

Not MODIFY: fixing the copy would leave a detector that still cannot fire.

**Not DELETE — but that is the likely destination, and it needs one answer
first.** The case for deleting is strong: total overlap with a detector that
uses the trader's own rule at `danger`, an invisible severity, a wrong
description, and zero observations. The case against is single and real: if
danger-zone interventions ever move onto the live path, this is the only thing
that would record a system cooldown being breached, and `constitution_violation`
would not cover it — that rule reads the *declared* value, not the imposed one.

**The blocking question, for you and not for me:** are system-imposed cooldowns
staying in the product, and will `trigger_intervention` ever run from the live
pipeline?

- **If no** → this is a **DELETE**, and the sweep is small: no thresholds, no
  aliases, no families, no shared constants.
- **If yes** → it becomes a **MODIFY**: fix the copy, and revisit once real
  cooldowns exist to measure against.

I am not answering that on your behalf, and the evidence here cannot answer it
either.


---

## Retirement, 29 Aug 2026

**Removed:** the detector method, its registry spec, its `PATTERN_COPY` entry,
and the context plumbing that existed solely for it — `EngineContext.active_cooldowns`
had exactly one reader, so the per-trade `select(Cooldown)` query went with it.
**One fewer database round-trip on every completed trade.**

**Preserved, and pinned by tests:** `cooldown_service`, the `Cooldown` model,
table and factory, the `/cooldown` API, `danger_zone_service.trigger_intervention`
still starting cooldowns, and the trader's `cooldown_after_loss` still resolving
to `user_cooldown_min` and `revenge_window_min`.

**`constitution_violation`'s cooldown rule is untouched** and a test now proves
it still fires at `danger` with the trader's own number in the message — that is
what makes this retirement safe.

Counts: **21 detectors, 27 pattern types.**

Frontend display entries kept, as with every prior retirement, so stored alert
rows still render a name.
