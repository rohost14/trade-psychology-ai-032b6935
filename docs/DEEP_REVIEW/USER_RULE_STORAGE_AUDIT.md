# User-defined rules — storage architecture audit

**1 Sep 2026. AUDIT ONLY. NO CODE CHANGED.** Verified against the code and the
live database, not against the models alone.

---

## 1. Where every user-configurable rule is stored

**All enforced rules live in one table: `user_profiles`.** Verified against
`information_schema`:

| rule | column | type | nullable | **DB default** |
|---|---|---|---|---|
| daily loss limit | `daily_loss_limit` | double precision | yes | **none** |
| per-trade loss limit | `per_trade_loss_limit` | double precision | yes | **none** |
| exposure limit | `max_position_size` | double precision | yes | **none** |
| max trades/day | `daily_trade_limit` | integer | yes | **none** |
| max consecutive losses | `max_consecutive_losses` | integer | yes | **none** |
| cooldown after loss | `cooldown_after_loss` | integer | yes | **`15`** ⚠ |
| restricted windows | `restricted_windows` | jsonb | yes | `'[]'` |
| options stop-loss | `sl_percent_options` | double precision | yes | **`50.0`** ⚠ |
| futures stop-loss | `sl_percent_futures` | double precision | yes | **`1.0`** ⚠ |
| trading capital *(input, not a rule)* | `trading_capital` | double precision | yes | none |

`RULE_FIELDS` in `constitution_service.py` is the authoritative list of what
counts as a *rule*: the eight above minus `sl_percent_futures` and
`trading_capital`.

**Two other tables hold rule-shaped values that are NOT enforced:**

| | where | status |
|---|---|---|
| `guardian_loss_limit` | **`users` table**, not `user_profiles` | a notification threshold for the guardian feature, not a detector input |
| `Goal.max_daily_loss`, `max_trades_per_day`, `max_position_size_percent`, `max_risk_per_trade_percent`, `min_time_between_trades_minutes`, `require_stoploss` | `Goal` model | **the `goals` table DOES NOT EXIST in the database** — see §5 |

---

## 2. Is there a single authoritative table?

**Yes for enforcement: `user_profiles`.** No detector, threshold resolver or
alert path reads any other table for a rule value. `Goal` is write-through only
(`_apply_goals_to_profile` copies into `user_profiles`), and nothing reads it
back for enforcement.

**But there are three writers into `user_profiles`, and they do not agree:**

| writer | routes through the constitution gate? |
|---|---|
| `PUT /api/profile/` and `PUT /api/constitution/` | **yes** — `ConstitutionService.apply_changes`, tighten instantly / loosen 409 |
| `PUT /api/goals/` → `_apply_goals_to_profile` | **no** — direct attribute assignment |
| `PATCH /api/admin/users/{id}/limits` | **no** — direct attribute assignment |

---

## 3. End-to-end trace — `daily_loss_limit`

```
UI            src/components/onboarding/OnboardingWizard.tsx
              (opt-in checkbox; My Rules uses src/components/rules/*)
                  |  api.put('/api/constitution/', {daily_loss_limit: 10000})
                  v
API           backend/app/api/constitution.py
                  -> _FIELD_MAP  (line 183: name -> UserProfile attribute)
                  -> ConstitutionService.apply_changes()
                       backend/app/services/constitution_service.py
                       - RULE_FIELDS gate
                       - _TIGHTEN_DIRECTION: daily_loss_limit = -1 (lower = tighter)
                       - tighten -> applied now; loosen -> 409 override_required,
                         parked in UserProfile.constitution_pending
                  v
DB            user_profiles.daily_loss_limit           <-- SOURCE OF TRUTH
                  v
LOAD          the engine reads the row per CompletedTrade
              backend/app/services/behavior_engine.py  (run_for_completed_trade)
                  v
RESOLVE       backend/app/core/threshold_resolution.py :: resolve_thresholds()
                  _apply_profile_facts ->
                      put("daily_loss_limit", profile.daily_loss_limit,
                          Source.FACT, 1.0)
                  (parallel resolver: core/trading_defaults.py :: get_thresholds)
                  v
DETECT        behavior_engine._detect_constitution_violation()
                  th.get("daily_loss_limit"); if falsy -> RULE NOT EVALUATED
                  ratio = loss / limit
                  ladder(ratio) -> caution 0.80 / danger 1.00 / critical 1.20
                  v
ALERT         backend/app/tasks/trade_tasks.py
                  _pattern_dedup_key -> "constitution_violation:daily_loss"
                  ev.severity == "info" -> no RiskAlert; otherwise a row is written
                  is_notifiable() -> only danger/critical push
```

**No cache anywhere on this path.** `resolve_thresholds` and `get_thresholds`
contain no Redis and no memoisation — the profile row is read per evaluation.

---

## 4. NULL semantics, and where they break

**The intended contract:** `NULL` = the trader has not configured the rule, and
an unconfigured rule is never evaluated. Every detector gates on
`if th.get(...)`, so `None` and `0` both mean "skip".

**It holds for five rules** — `daily_loss_limit`, `per_trade_loss_limit`,
`max_position_size`, `daily_trade_limit`, `max_consecutive_losses`. All are
nullable with no DB default, `ConstitutionService.generate_defaults` returns
`None` for the money rules, and the onboarding wizard no longer overrides that.

### ⚠ FINDING 1 — three columns have a non-NULL DB default, so "unset" is unrepresentable

```
cooldown_after_loss  DEFAULT 15
sl_percent_options   DEFAULT 50.0
sl_percent_futures   DEFAULT 1.0
```

An `INSERT` that omits the column **writes the default into the row**. The value
is then indistinguishable from one the trader typed, and
`_apply_profile_facts` marks it `Source.FACT, confidence 1.0` — the provenance
reserved for a declared rule.

**This is the same defect I fixed at the resolver on 2026-09-01, and the fix is
incomplete.** That change made an undeclared `sl_percent_options` resolve to
`None` — but only when the column is `NULL`. **Live data, 3 profiles:**

```
sl_percent_options values: {None: 2, 50.0: 1}
cooldown_after_loss:       NOT NULL in 3/3
```

**One profile has `50.0` stored.** For that trader the resolver still returns
50.0 at `Source.FACT`, the live severe-loss path still raises a
`constitution_violation` at `notification_level=4` reading *"You set your options
exit at 50% of premium"*, and it still pre-empts the universal 60% band. **The
row-level fix landed; the column-level default did not.**

`cooldown_after_loss` is the same shape and always has been: it can never be
NULL, so "no cooldown rule" cannot be expressed. (The two live values are 0 and
1, so nothing is currently sitting on the 15 default — but a fresh insert would.)

### ⚠ FINDING 2 — onboarding vs My Rules cannot disagree, but Goals could

Both onboarding and My Rules write through `/api/constitution/` → `_FIELD_MAP` →
`ConstitutionService`, so they share one mapping and one gate. **No divergence.**

`PUT /api/goals/` is different and would have diverged:

```python
goals = Goal(broker_account_id=...)          # ALL non-null defaults
update_data = updates.model_dump(exclude_unset=True)   # only what the user sent
...
await _apply_goals_to_profile(broker_account_id, goals, db)   # the WHOLE object
```

`_apply_goals_to_profile` then does `if goals.max_daily_loss is not None:` — and
the untouched default `5000.0` is not None. **Editing any single goal field would
have written `daily_loss_limit=5000`, `daily_trade_limit=10` and
`max_position_size=5.0` into the profile — three rules the trader never set,
bypassing the constitution gate entirely.**

**It cannot fire today** (§5), but the code is live and would do this the moment
the table existed.

### ⚠ FINDING 3 — `api/cooldown.py` reads a percent as rupees

`api/cooldown.py:373-376`:

```python
if profile.max_position_size and data.order_value:
    if data.order_value > profile.max_position_size:
        reasons.append(f"Position size exceeds your limit of ₹{profile.max_position_size:,.0f}")
```

`max_position_size` is a **percent of capital**; `order_value` is **rupees**.
A declared 10% limit becomes "₹10", so any order over ₹10 warns. Previously
recorded as latent — **still latent** (`/pre-trade-check` has no frontend
caller), and re-confirmed here.

---

## 5. Is the DB the source of truth?

**Yes, and there is no cache to drift from it.** No Redis layer, no memoised
thresholds, no server-side duplicate. The frontend holds React Query state only,
refetched from the same endpoints.

### ⚠ FINDING 4 — the `Goal` model is mapped to a table that does not exist

```
table goals            exists: False
table commitment_logs  exists: True
table streak_data      exists: True
```

Its two siblings from the same model file exist; `goals` does not. So
`GET /api/goals/` and `PUT /api/goals/` both `SELECT ... FROM goals` and would
raise `UndefinedTableError` → 500.

**Nothing calls them.** `src/lib/goalsApi.ts` and `src/hooks/useGoals.ts` exist,
but **no page or component imports `useGoals`**, and there is no Goals page in
`src/pages/` or in `_archive/`. So the whole surface — model, table, API,
frontend client — is dead in three different ways at once.

**That is what makes Finding 2 safe today, and it is a fragile reason.**

---

## 6. Is the design appropriate?

**The core is right, and I would not change it.**

* **One table, one row per broker account, one column per rule.** For ~8 scalar
  rules read on every completed trade, a wide row is the correct shape — no join,
  no assembly, and the whole rule set arrives with the profile the resolver
  already loads.
* **`RULE_FIELDS` + `_TIGHTEN_DIRECTION` + `ConstitutionService.apply_changes`
  is a genuinely good design.** Tighten instantly, loosen behind a 409 and a
  pending record — that is the product's psychology expressed in the write path,
  not bolted on afterwards.
* **Provenance is first-class.** `Source.FACT / HISTORY / CAPITAL / GLOBAL` with
  confidence means the UI can distinguish "your number" from "our starting
  guess", and `violates_kind` stops a learned value moving a safety line.
* **No cache** is the right call at this scale.

### The minimum changes I would propose — NOT made

1. **Drop the three non-NULL column defaults** (`cooldown_after_loss` 15,
   `sl_percent_options` 50.0, `sl_percent_futures` 1.0) and backfill the stored
   defaults to `NULL`. This is the *completion* of the 2026-09-01 fix — without
   it, "unset" is unrepresentable for three rules and one live profile is
   already carrying a rule its owner never declared. **Needs a decision on the
   backfill**, because a stored 50.0 cannot be distinguished from a typed 50.0;
   the honest options are to null everything matching the exact default, or to
   null nothing and only fix new rows.
2. **Make every writer go through `ConstitutionService`.** Two bypass it today.
   The admin path may be deliberate — an operator overriding a trader's rule is a
   different act — but it is undocumented, and the goals path is simply wrong.
3. **Decide the fate of the Goals surface.** Model, table, API and frontend
   client disagree about whether it exists. Either build it properly or archive
   it; leaving a live endpoint that 500s and would corrupt rules if its table
   appeared is the worst of the three states.
4. **A contract test that every `RULE_FIELDS` column is nullable with no DB
   default**, so this class cannot return.

**None of these is urgent except (1)**, which has a trader-visible effect today
on one of three profiles.
