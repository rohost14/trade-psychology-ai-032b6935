# `sl_percent_options` / `sl_percent_futures` — fabrication risk

**2 Sep 2026. INVESTIGATION ONLY. NO CODE, DB, UI OR TESTS CHANGED.**

---

## 0. A correction to my own reconciliation

I said the `??` fallbacks in `ProfileTab.tsx` "make the UI show a selection the
trader never made" and implied that is what persists. **The first half is true,
the second half is wrong, and the real mechanism is elsewhere.**

`ProfileTab` uses `??` only in the *highlight comparison*:

```jsx
(profile.sl_percent_options ?? 50) === pct ? 'selected' : 'unselected'
onClick={() => setProfile({ ...profile, sl_percent_options: pct })}
```

It **never writes into state**. A NULL value renders as "50 looks selected" and
stays `null` in state unless the trader clicks. `max_position_size` is the same:
`value={profile.max_position_size ?? 10}` on a range input is display-only.

**The fabrication risk is real, but it comes from `Settings.tsx`, not
`ProfileTab.tsx`.**

---

## A. Exact reproduction path — `sl_percent_options` becomes 50

Three facts combine.

**1. `Settings.tsx:51` seeds local state with hardcoded values:**

```jsx
const [profile, setProfile] = useState<UserProfile>({
  ...
  max_position_size: 10,
  cooldown_after_loss: 15,
  sl_percent_futures: 1.0,
  sl_percent_options: 50.0,
  ...
});
```

**2. The loading guard does not cover the profile query.** `Settings.tsx:263`:

```jsx
if (brokerLoading) { return <Skeleton .../>; }
```

`isLoadingProfile = profileQuery.isPending` is assigned at line 87 and
**never used anywhere** — confirmed by grep, it appears only in that assignment
and in a stale comment. `profileError` *is* guarded (289/322/331), so a failed
fetch hides the form. **A pending fetch does not.**

**3. The seeding effect is permanently disabled once the form is dirty.**
`Settings.tsx:98-101`:

```jsx
useEffect(() => {
  if (!serverProfile || isDirty) return;
  setProfile(prev => ({ ...prev, ...serverProfile }));
}, [serverProfile, isDirty]);
```

### The path

1. Trader opens **Settings**.
2. `brokerLoading` resolves first (broker context is often already warm) while
   `profileQuery` is still pending.
3. The form renders **from hardcoded state**: options SL shows **50%** selected,
   futures SL **1%**, max position **10%**, cooldown **15 min**.
4. Trader edits **anything at all** — display name, a notification toggle —
   which sets `isDirty = true`.
5. The profile response arrives. **The seeding effect now returns early and the
   server values are never applied.** The hardcoded defaults remain in state.
6. Trader clicks **Save**. `Settings.tsx:120-152` builds the payload from state
   and sends **every field**, including `sl_percent_options: 50`.
7. `PUT /api/profile/` → `ConstitutionService.apply_changes` (it is a
   `RULE_FIELD`) → `user_profiles.sl_percent_options = 50.0`.

**A rule now exists that the trader never selected.** And because 50 is
*tighter* than nothing, the constitution gate accepts it instantly with no
friction — loosening is what triggers the 409.

### What that value then does

`sl_percent_options` is read at `live_risk_state.py:323` and becomes the
**DECLARED** band on every long-option position watch. On a crossing:

* `Crossing(kind=DECLARED, severity="danger")` — hardcoded danger, so it is
  **notifiable** and pushes;
* `position_monitor_tasks.py:~995` emits `pattern_type="constitution_violation"`,
  `details["rule"] = "sl_percent_options"`, at **`notification_level=4`**;
* message: **"You set your options exit at 50% of premium. {SYMBOL} is 70% down."**
* it takes **precedence over the universal band** — the universal crossing is
  demoted to `details["also_crossed"]`. Since 50 sits between universal caution
  (40) and danger (60), it pre-empts the real safety finding.

---

## B. Exact reproduction path — `sl_percent_futures` becomes 1.0

**Identical, same step 5-6.** The payload carries `sl_percent_futures: 1.0`.

Two differences:

* It is **not** in `RULE_FIELDS`, so it bypasses the constitution gate entirely
  and is written by direct attribute assignment.
* **Nothing reads it**, so the fabricated value produces no alert. The harm is
  confined to a false display: Settings will then show "1%" as a genuine
  selection, and the trader has no way to tell it apart from a real one.

---

## C. Is the existing `50.0` row fabricated? — evidence and confidence

**The origin is proven, by dates.**

| | |
|---|---|
| profile `a7927997` created | **2026-02-06 15:05** |
| migration 028 (`ADD COLUMN ... DEFAULT 50.0`) first committed | **2026-03-08** |
| ProfileTab's `sl_percent` UI added | 2026-04-10 |
| profile last updated | 2026-07-30 |

The profile predates the migration by a month. `ALTER TABLE ... ADD COLUMN ...
DEFAULT` backfills existing rows, so **that row was written 50.0 by the
migration itself, with no user involved. This is certain, not inferred.**

**What is not certain** is whether a later Settings save re-confirmed it. The UI
existed from April; the profile was updated in July.

**And here is the part that matters: no save could ever settle it.** Even a
*correctly seeded* form loads the stored 50.0 into the control, so a save of
unrelated changes writes 50.0 back. **A value that already exists cannot be
distinguished from a value the trader chose, by any subsequent save.** The 2026-09-01
provenance fix and migration 083 both stop *new* fabrication; neither can
retro-classify this row.

> **Confidence: HIGH that the value originated from the migration backfill —
> that is date-proven. UNKNOWN whether the trader ever affirmed it, and
> unknowable from data. The one thing that is certain is that it was never
> required to be a deliberate choice.**

---

## D. Correct intended semantics

**`sl_percent_options`** — a genuine **USER_RULE**, and the product already
treats it as one (`RULE_FIELDS`, tighten/loosen gate, `constitution_violation`
at level 4).

* `NULL` **must** mean "the trader has not configured this rule", and no
  declared band may be built from it. *(Already true in the resolver since
  2026-09-01, and in the column since migration 083.)*
* **Only an explicit selection may create it.** A rule that carries a push
  notification and pre-empts a universal safety band must not be creatable as a
  side effect of saving an unrelated setting.
* The UI must **not** present an unset rule as selected.

**`sl_percent_futures`** — currently claims to be a rule, is not one, and
nothing consumes it.

---

## E. Recommended fix for each — NOT implemented

**Shared root cause first**, because both fields and two others ride on it:

1. **Guard the form on the profile query.** `isLoadingProfile` already exists and
   is unused; rendering the skeleton until the profile resolves closes the window
   entirely. **This is the one change that fixes the class**, and it also protects
   `max_position_size` (10) and `cooldown_after_loss` (15), which fabricate the
   same way today.
2. **Stop seeding local state with values.** Initialise the rule fields to
   `undefined`/`null` so that even if the form renders early it cannot invent a
   number. `undefined` is dropped by `JSON.stringify`, so an unseeded field
   would simply not be sent.
3. **Render an unset rule as unset** — no preset highlighted, or an explicit
   "Not set" chip — so "50 looks chosen" stops being the resting state.

**`sl_percent_options` specifically:** nothing further. With the window closed
and the fallback removed, `NULL` means unset end to end.

**`sl_percent_futures` specifically:** see F.

**Not recommended:** touching the existing `50.0` row programmatically. Section C
shows it cannot be classified from data. Asking the trader remains the only
sound resolution, and there is exactly one.

---

## F. Should either field stay in the product?

**`sl_percent_options` — KEEP.** It is a real declared exit rule, it is
consumed, and the concept is sound: the trader's own stop is a stronger
reference than a universal band when it is tighter. Its problems are the
fabrication window (E1-E3) and **its copy**, which says *"Used to detect holding
losers too long on options buys"* — that describes `holding_loser`, not what this
value does. It drives the declared severe-loss band.

**`sl_percent_futures` — DOES NOT BELONG AS IT STANDS.** Verified definitively:

| checked | result |
|---|---|
| any detector | **no** — `_detect_no_stoploss` reads `instrument_type`, `pnl`, `ctx.exit_order_types` and its own `no_stoploss_loss_pct_danger`. It never touches `sl_percent_futures` |
| any task / live path | **no** |
| `RULE_FIELDS` | **not present** |
| Rules UI display | **absent** |
| indirect use via dynamic threshold keys | **none** — no `thresholds.items()` / key iteration anywhere |
| total references | `api/profile.py` schema + range validator, the two resolvers, the model, and its own Settings control |

**Its UI claim is false.** *"Used to detect no-stop-loss behavior on futures
trades"* — `no_stoploss` does not read it, and never has.

**But "remove it" is not automatic**, and I am not deciding it here. Two honest
options:

* **Remove** — the Settings control, the schema field, both resolver puts. The
  column stays (never delete data), and the trader stops being asked for
  something nobody uses and told a false reason for it.
* **Wire it** — `no_stoploss` currently judges a futures trade by loss magnitude
  against a universal band. A trader's declared typical stop is exactly the kind
  of personal reference the engine's design favours, and the field already
  collects it. That would be a **new detector behaviour** needing its own
  evidence, not a cleanup.

**What is not defensible is the current state:** collected, validated, gated,
stored, displayed with a false explanation, and read by nothing.

---

## Also found — same mechanism, two more fields

`max_position_size: 10` and `cooldown_after_loss: 15` sit in the same hardcoded
`useState` and fabricate by the same path. `max_position_size` is the exposure
rule the whole Pattern 28 hierarchy rests on — *"no declared rule, no alert"* —
and this path can declare one for the trader. **Not fixed here; recorded because
any fix to A must cover them.**
