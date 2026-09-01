# Clearing an optional rule — investigation

**2 Sep 2026. INVESTIGATION ONLY. NO CODE OR DB CHANGED.**

Intended lifecycle under examination:

```
NULL   = the trader has not configured this rule
value  = the trader explicitly configured it
```

---

## 1. Why `/api/profile` cannot write NULL

`api/profile.py`, PUT `/`:

```python
update_data = data.model_dump(exclude_unset=True)          # line 501
...
rule_changes = {f: update_data.pop(f) for f in list(update_data)
                if f in RULE_FIELDS and update_data[f] is not None}
...
for field, value in update_data.items():
    if hasattr(profile, field) and value is not None:
        setattr(profile, field, value)
```

**Two independent `is not None` guards.** A rule field arriving as `null` is
excluded from `rule_changes`, then skipped by the setattr loop. It reaches
neither write path.

**The information needed to do better is already there and thrown away.**
`exclude_unset=True` means only keys the client actually sent are present — so
an explicit `null` *is* distinguishable from an omitted field at that point. The
`is not None` filter discards that distinction one line later.

## 2. Can `/api/constitution` clear the same rule?

**No, and the reason is written down.** `api/constitution.py`, PUT `/`:

```python
new_values = {
    f: getattr(payload, f)
    for f in RULE_FIELDS
    if getattr(payload, f, None) is not None
       or f == "restricted_windows" and payload.restricted_windows is not None
}
# Explicit None handling: pydantic None means "not provided" here — rule
# REMOVAL goes through restricted PUT with explicit override in a later
# iteration; out of scope for Phase 2 backend.
```

> **That comment is the answer to question 7: this is a DOCUMENTED, DELIBERATE
> DEFERRAL, not an oversight.** Rule removal was scoped out of Phase 2 and
> assigned to a later iteration.

Two notes on that filter:

* It uses **no** `exclude_unset` / `model_fields_set`, so unlike `profile.py` it
  genuinely cannot tell "omitted" from "explicitly null". The comment is accurate
  *for this endpoint as written*.
* The `restricted_windows` clause is **redundant**: `[] is not None` already
  satisfies the first condition. It changes nothing.

## 3. THE SERVICE LAYER IS ALREADY BUILT FOR CLEARING

`constitution_service.classify_change`:

```python
# Removing a rule entirely (value -> None) is always loosening;
# adding a rule (None -> value) is always tightening.
if new is None:
    return "loosen"
if old is None:
    return "tighten"
```

**Clearing is already modelled, already classified, and already routed** — a
removal is a *loosen*, so it would correctly attract the 409 override and the
next-session-pending flow. That is exactly the right friction for a trader
removing a protection.

**Nothing in `ConstitutionService` needs designing. The blockage is entirely in
the two API filters.**

## 4. Does the UI offer a way to clear?

### MyRules — offers one, and it silently does nothing

`MyRules.tsx:369-373` renders each rule as an empty-able number input:

```jsx
value={draft[field] ?? ''}
onChange={(e) => setDraft(d => ({
  ...d, [field]: e.target.value === '' ? null : Number(e.target.value),
}))}
```

Clearing the box sets `null`; `save()` sends `{...draft}`, so the payload
contains `field: null`; the backend filter drops it; `apply_changes` receives
nothing for that field and returns `change_type: "none"`.

**And the trader is told nothing.** The toast chain is:

```jsx
if (outcome.pending && ...)        toast.info(...)
else if (change_type === 'tighten') toast.success('Rules tightened...')
else if (change_type !== 'none')    toast.success('Rules updated.')
```

`"none"` matches no branch — **no toast at all**. The dialog closes, `load()`
refetches, and the field visibly snaps back to its old value.

> **This is worse than having no affordance.** The control accepts the input,
> the save appears to succeed, and the rule is unchanged.

### Settings — no clear affordance for anything

| control | why it cannot clear |
|---|---|
| `max_position_size` | range slider, `min={1}` — cannot reach null |
| `sl_percent_options` | preset buttons — a click sets, nothing un-sets |
| `sl_percent_futures` | same |
| `cooldown_after_loss` | same *(and it should not — always-configured by design)* |

`daily_loss_limit` is **in the Settings payload but has no editor** — it is
passed through from state. `per_trade_loss_limit` is not in the Settings payload
at all.

## 5. Every optional rule, and whether it is affected

| field | set? | clear? | notes |
|---|---|---|---|
| `daily_loss_limit` | ✅ | ❌ | onboarding opt-in + MyRules; no Settings editor |
| `per_trade_loss_limit` | ✅ | ❌ | onboarding opt-in + MyRules; absent from Settings entirely |
| `max_position_size` | ✅ | ❌ | onboarding opt-in, MyRules, Settings slider |
| `daily_trade_limit` | ✅ | ❌ | always sent by onboarding, so rarely NULL in practice |
| `max_consecutive_losses` | ✅ | ❌ | always sent by onboarding |
| `sl_percent_options` | ✅ | ❌ | **Settings only** — not editable in MyRules, so no clear path even in principle |
| `cooldown_after_loss` | ✅ | **n/a** | intentionally always-configured; NULL is not a valid state |
| `restricted_windows` | ❌ | n/a | **no editor anywhere**; the backend would accept `[]` |

**So the answer to question 5 is: every optional rule has the problem.** It is
not specific to the two `sl_percent` fields.

## 6. Complete trace for a clear attempt

```
MyRules: trader empties "Max risk per trade"
   draft.max_position_size = null
        |
   api.put('/api/constitution/', {...draft, override_confirmed: false})
        |  body: { "max_position_size": null, ... }
        v
api/constitution.py  PUT /
   new_values = {f: ... if getattr(payload, f) is not None}
   -> max_position_size DROPPED here
        v
ConstitutionService.apply_changes(profile, db, new_values)
   -> field absent; classify_change never called
   -> no tightens, no loosens
   -> returns change_type "none"; NO ConstitutionHistory row
        v
DB: user_profiles.max_position_size UNCHANGED
        v
MyRules: no toast (the "none" branch matches nothing), dialog closes,
         load() refetches, the input snaps back to the old value
```

**Had the null reached `apply_changes`, the existing code would have handled it
correctly**: `classify_change` → `"loosen"` → 409 `override_required` → the
trader confirms → applied, or queued to next session during market hours, with a
`ConstitutionHistory` row recording `{old: 25, new: None}`.

## 7. Intentional decision or implementation gap?

**Both, and the split is clean:**

| | verdict |
|---|---|
| **The backend not supporting removal** | **Intentional and documented** — the comment scopes it out of Phase 2 explicitly |
| **MyRules presenting a clear affordance that silently fails** | **A gap.** The UI was built as if removal worked. Nothing documents this, and the trader gets no feedback |
| **`change_type: "none"` producing no toast** | **A gap**, and it is what makes the first gap invisible |

---

## Recommended fix — NOT implemented

**Small, because the hard part is already built.** In order of value:

1. **Tell the trader when nothing changed.** Add an `else` to the MyRules toast
   chain. One line, no semantics touched, and it makes the current behaviour
   honest immediately — *"No changes to save"* rather than silence.
2. **Distinguish "omitted" from "explicitly null" at the API.** `profile.py`
   already has `exclude_unset=True` and only needs its `is not None` filters
   relaxed for keys the client actually sent. `constitution.py` needs
   `payload.model_fields_set` to gain the same ability. **Both then pass `None`
   through to `apply_changes`, which already does the right thing.**
3. **Route a clear as a loosen** — which happens automatically once (2) lands,
   because `classify_change` already returns `"loosen"` for `value → None`. A
   trader removing a protection gets the 409 confirmation and a history row, the
   same friction as relaxing one. That is the correct product behaviour.
4. **Give `sl_percent_options` a clear affordance** — it is settable only via
   Settings presets, which have no "off". Either a "Not set" option beside the
   presets, or make it editable in MyRules with the other rules.
5. **Decide `restricted_windows`** — it is enforced but has no editor at all.
   Separate from clearing; recorded.

**Not recommended:** removing the `is not None` guards wholesale. That would let
an *omitted* field null a rule, which is the opposite failure and worse.

**Out of scope, untouched:** `sl_percent_futures` and its product status.
