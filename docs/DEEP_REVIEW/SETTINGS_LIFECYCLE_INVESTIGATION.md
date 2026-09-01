# Settings load / edit / save lifecycle — the fabrication race

**2 Sep 2026. INVESTIGATION ONLY. NO CODE CHANGED.**

---

## A. Exact reproduction

### The three parts

**1. `Settings.tsx:51` — local state seeded with concrete values**

```jsx
const [profile, setProfile] = useState<UserProfile>({
  experience_level: 'intermediate',  trading_style: 'intraday',
  risk_tolerance: 'moderate',        daily_loss_limit: undefined,
  daily_trade_limit: undefined,      max_position_size: 10,
  cooldown_after_loss: 15,           trading_capital: undefined,
  sl_percent_futures: 1.0,           sl_percent_options: 50.0,
  trading_hours_start: '09:15',      trading_hours_end: '15:30',
  push_enabled: true,                whatsapp_enabled: false,
  alert_sensitivity: 'medium',       guardian_enabled: false,
});
```

**2. The render gate covers `profileError` but not `isPending`**

```jsx
const isLoadingProfile = profileQuery.isPending;   // line 87 — NEVER USED
const profileError = profileQuery.error;           // line 91
...
{isConnected && !profileError && ( ...form + Save button... )}   // line 289
if (brokerLoading) { return <Skeleton/>; }                       // line 263
```

The comment above `profileError` (lines 88-90) states the hazard exactly:

> *"The form must never fall through to its hardcoded defaults after a failed
> load — those look exactly like saved settings, and Save would write them over
> the trader's real rules. Both the form and the Save button check this."*

**The author identified this precise failure mode and guarded the ERROR half.
The PENDING half was missed.** `isLoadingProfile` is assigned and referenced
nowhere — grep confirms it appears only in that assignment.

**3. Any edit permanently disables seeding**

```jsx
const updateProfile = useCallback((action) => {
  setProfile(action); setIsDirty(true);            // line 70-72
}, []);

useEffect(() => {
  if (!serverProfile || isDirty) return;           // line 98-101
  setProfile(prev => ({ ...prev, ...serverProfile }));
}, [serverProfile, isDirty]);
```

### The sequence

1. Trader opens Settings. `brokerLoading` resolves (broker context is often warm)
   while `profileQuery` is still pending.
2. Form renders **from hardcoded state**. Options SL shows 50%, futures SL 1%,
   max position 10%, cooldown 15 min — all as apparent selections.
3. Trader edits **anything** — a notification toggle, their display name.
   `isDirty = true`.
4. The profile response arrives. **The seeding effect returns early.** Server
   values never applied.
5. Save → the payload is built from state → 13 fields carry hardcoded values.

**No unusual timing is needed.** Any page load where the profile request has not
resolved before the first interaction reproduces it — a cold cache, a slow
connection, or simply a fast click.

---

## B. All affected fields

The payload sends 27 keys. `JSON.stringify` **drops `undefined`**, so only
initial-state keys with concrete values can be fabricated. **13 fields:**

| field | fabricated value | `RULE_FIELD`? | consequence |
|---|---|---|---|
| **`max_position_size`** | **10** | **YES** | **declares an exposure rule.** The whole Pattern 28 hierarchy rests on "no declared rule, no alert" — this creates one |
| **`sl_percent_options`** | **50.0** | **YES** | declares a severe-loss rule → `constitution_violation` at level 4, pushes, and pre-empts the universal 40/60/80 band |
| **`cooldown_after_loss`** | **15** | **YES** | overwrites a real cooldown with 15 |
| `sl_percent_futures` | 1.0 | no | stored, read by nothing — false display only |
| `experience_level` | `'intermediate'` | no | overwrites the trader's answer; feeds `generate_defaults` |
| `trading_style` | `'intraday'` | no | overwrites |
| `risk_tolerance` | `'moderate'` | no | overwrites |
| `trading_hours_start` / `_end` | `'09:15'` / `'15:30'` | no | overwrites |
| `push_enabled` | `true` | no | re-enables push |
| `whatsapp_enabled` | `false` | no | **silently disables WhatsApp** |
| `alert_sensitivity` | `'medium'` | no | overwrites |
| **`guardian_enabled`** | **`false`** | no | **silently disables the guardian** |

**Safe by accident** (`undefined` in initial state, dropped before the request):
`daily_loss_limit`, `daily_trade_limit`, `trading_capital`. **This is luck, not
design** — they were left `undefined` while their neighbours were not.

**Not in initial state at all**, therefore `undefined` and dropped:
`display_name`, `trading_since`, `preferred_instruments`, `known_weaknesses`,
`email_enabled`, all `guardian_phone/name/alert_threshold/loss_limit`,
`eod_report_time`, `morning_brief_time`.

> **So the answer to "does the race affect other fields" is yes — 13, not 4, and
> two of them (`guardian_enabled`, `whatsapp_enabled`) silently switch
> protections OFF.**

---

## C. Exact payload behaviour, per case

### Case 1 — race (edit before load), DB has real values

```json
{ "max_position_size": 10, "cooldown_after_loss": 15,
  "sl_percent_options": 50, "sl_percent_futures": 1,
  "experience_level": "intermediate", "guardian_enabled": false, ... }
```

Backend (`api/profile.py`, PUT `/`):

```python
update_data = data.model_dump(exclude_unset=True)
rule_changes = {f: update_data.pop(f) for f in list(update_data)
                if f in RULE_FIELDS and update_data[f] is not None}
if rule_changes:
    await ConstitutionService.apply_changes(profile, db, rule_changes)
for field, value in update_data.items():
    if hasattr(profile, field) and value is not None:
        setattr(profile, field, value)
```

The three rule fields go to `ConstitutionService`; the rest are set directly.
**All 13 are written.** And because 50 / 10 are *tighter* than nothing, the
constitution gate accepts them **instantly with no friction** — only loosening
raises the 409.

### Case 2 — normal load, DB value genuinely NULL, trader edits an unrelated field

The merge `{...prev, ...serverProfile}` applies the server's explicit `null`
(`to_dict()` emits every key, no `response_model`, no `exclude_none` — verified),
so state becomes `null`. Payload:

```json
{ "max_position_size": null, "sl_percent_options": null, ... }
```

Backend: `update_data[f] is not None` **excludes them from `rule_changes`**, and
`value is not None` **skips them in the setattr loop**.

> **Nothing is written. NULL survives. This case is SAFE today.**

**But the same guard means `/api/profile` can never write NULL to anything —
a rule cannot be cleared through Settings.** Not part of this bug; recorded.

### Case 3 — trader explicitly clicks a preset

State gets the real number, payload carries it, `ConstitutionService` applies it,
history row written. **Works correctly and must keep working.**

### Case 4 — existing stored value, no edit to that field

Merge loads it, payload echoes it back unchanged, backend re-writes the same
value. No-op in effect. **Note this is also why no save can ever *prove* intent
for an already-stored value** — the value round-trips whether or not the trader
looked at it.

---

## D. Smallest safe fix

### The fix — one condition

**Gate the form on the profile query exactly as it is already gated on the
error.** `isLoadingProfile` exists and is unused:

```jsx
{isConnected && !profileError && !isLoadingProfile && ( ...form... )}
```

That is the whole persistence fix. It closes the window for **all 13 fields at
once**, and it satisfies every constraint:

| requirement | met? |
|---|---|
| NULL stays NULL for optional rules | ✅ Case 2 already safe; unchanged |
| `max_position_size` NULL must not become 10 | ✅ the only path that did is closed |
| `sl_percent_options` NULL must not become 50 | ✅ same |
| `cooldown_after_loss` semantics unchanged | ✅ nothing about it is touched |
| no blanket removal of defaults | ✅ none removed |
| explicit selection still persists | ✅ Case 3 untouched |
| existing stored value loads and persists | ✅ Case 4 untouched |
| unrelated save cannot manufacture a rule | ✅ |
| `sl_percent_futures` fate undecided | ✅ untouched |

**Why not remove the hardcoded initial state instead?** It would also work, but
it is larger and riskier: those values are what the controls render before any
data exists, several are non-rule display fields, and changing them touches
components beyond the bug. The gate is one boolean and needs no reasoning about
which defaults are safe.

### Second, separate change — display truthfulness

**Yes, an unset optional rule should render as unset.** Three controls currently
show a value the trader never chose:

| control | today | should be |
|---|---|---|
| `max_position_size` | slider `?? 10`, label *"Default: 10%"* | **unset state** — no value, an explicit "Not set" |
| `sl_percent_options` | presets, `?? 50` highlighted | **no preset highlighted when NULL** |
| `sl_percent_futures` | presets, `?? 1.0` highlighted | same *(pending its product decision)* |
| `cooldown_after_loss` | presets, `?? 15` highlighted | **leave as is** — the column is never NULL by design, so highlighting the stored value is honest |

**`MyRules` already does this correctly** (`value={draft[field] ?? ''}` renders
blank), so the two surfaces currently disagree about the same field. This is a
display bug, **not** the persistence bug, and is worth separating.

**Also worth fixing while there, and unrelated to persistence:** both `sl_percent`
helper texts are false. `sl_percent_futures` claims *"Used to detect no-stop-loss
behavior on futures trades"* — `_detect_no_stoploss` never reads it.
`sl_percent_options` claims *"Used to detect holding losers too long"* — it
actually drives the declared severe-loss band.

---

## E. Regression cases that must be added

**Frontend**

1. **Form does not render while the profile query is pending** — the core fix.
2. **Form does not render on profile error** — the existing guard, currently
   unpinned by any test.
3. **Editing during pending cannot produce a save** — no Save button exists to
   click.
4. **After load with NULL values, saving an unrelated field sends `null`** for
   `max_position_size` and `sl_percent_options`, not 10 / 50.
5. **After load with stored values, an unrelated save round-trips them unchanged.**
6. **An explicit preset click persists that value.**
7. **A NULL optional rule renders as unset** — no preset highlighted, slider not
   showing 10 as if chosen.
8. **`cooldown_after_loss` still renders its stored value highlighted** — proving
   the display fix did not change its always-configured semantics.

**Backend** *(characterisation — these pin today's behaviour, which is correct
for this bug but surprising)*

9. **`PUT /api/profile` with `{"sl_percent_options": null}` writes nothing** and
   leaves an existing value intact.
10. **`PUT /api/profile` with a real value routes it through
    `ConstitutionService`** and writes a `constitution_history` row.
11. **A tightening value is applied with no override**, a loosening one raises
    409 — so it is visible that fabricating 50 *tightens* and therefore meets no
    friction.

**Contract**

12. **Every key in the Settings payload is either present in the seeded initial
    state as `undefined`, or covered by the pending guard.** This is the test
    that stops a future field being added to the payload with a concrete default
    and re-opening the hole.

---

## Out of scope, recorded

* `/api/profile` cannot clear a rule to NULL (`value is not None` on both paths).
  A trader can tighten or change a rule through Settings but never remove one.
* The existing `sl_percent_options = 50.0` row remains unclassifiable — see
  `SL_PERCENT_FABRICATION_INVESTIGATION.md` §C.
* `sl_percent_futures`' product fate is still undecided.
