# The three non-NULL rule defaults — investigation

**1 Sep 2026. INVESTIGATION ONLY. NO CODE OR DB CHANGED.**

Every claim below is from the code, the migrations, or the live database.

---

## 0. The finding that splits the three apart

An `INSERT` does **not** behave the same way through the ORM and through raw SQL.
Tested directly against the live DB inside a transaction that was rolled back:

```
ORM  UserProfile(broker_account_id=acct)   ->  sl_percent_options  = None
                                               sl_percent_futures  = None
                                               cooldown_after_loss = 15

RAW  INSERT INTO user_profiles (id, broker_account_id)
                                           ->  (50.0, 1.0, 15)
```

**The model declares no Python-side default for the two `sl_percent` columns, so
SQLAlchemy sends an explicit `NULL` and the DB default never applies.**
`cooldown_after_loss` is different: the model carries `default=15`, so the ORM
*writes* 15 on every new profile.

> **So `sl_percent_*`'s DB default is vestigial for the application — only raw
> SQL and the migration backfill ever wrote it. `cooldown_after_loss`'s default
> is live and writes on every profile creation.**

This is confirmed by the data: the two profiles created in August (ORM path) have
`NULL`; the one created in February — before migration 028 — has the defaults.

---

## 1. `cooldown_after_loss` — DEFAULT 15

**Introduced:** `migrations/007_user_profiles.sql`, the original table creation,
plus `default=15` on the model. It has always been there.

**Was it ever intentionally a default? YES — emphatically, and it still is.**

* `ConstitutionService.generate_defaults` returns a cooldown **per experience
  level**: beginner 15, intermediate 10, experienced 5, professional 5.
* `OnboardingWizard.tsx:776-780` renders it as a **slider**, initialised to 15,
  which the trader sees and submits in the step-5 payload (line 298).
* `EnforcedRules.tsx` and `BehaviourCostCard.tsx` present it as a named rule.

**This is not the opt-in money-rule pattern.** Pattern 24 deliberately made
`daily_loss_limit`, `per_trade_loss_limit` and `max_position_size` `None` until
the trader opts in. Cooldown was never in that set: it is an **always-on rule
with a suggested starting value**, and the trader is shown that value.

**Can stored values be distinguished?** For the one real profile, **yes** —
`constitution_history` records `cooldown_after_loss: {old: 10, new: 0}`, a
`loosen` with `override_flag=True`. That is unambiguous user intent.

**Affected rows:** none, in the sense that matters. All 3 profiles are non-NULL,
values `{0: 2, 1: 1}` — **no profile is sitting on the 15 default**.

> **RECOMMENDATION: LEAVE IT EXACTLY AS IS.** It is not the same defect class.
> Making it nullable would make "no cooldown rule" expressible, which is a
> **product change** — today every trader has a cooldown and that is deliberate.
> There is nothing to back-fill and nothing to fix.

---

## 2. `sl_percent_options` — DEFAULT 50.0

**Introduced:** `migrations/028_add_threshold_fields.sql`:

```sql
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS sl_percent_options FLOAT DEFAULT 50.0;
```

In Postgres, `ADD COLUMN ... DEFAULT` **backfills every existing row**. So every
profile that existed before 028 was written 50.0 by the migration itself.

**Was it ever intentionally a default? Partly, and the meaning CHANGED under it.**

* Originally a Settings preference — *"I exit options when premium drops by"* —
  stored and **read by nothing**.
* **On 2026-08-27 (Pattern #8) it was promoted to a `RULE_FIELD`**, and the live
  premium-loss path began raising it as a `constitution_violation`. A value that
  had been an inert preference became an **enforced rule**, retroactively, for
  every row already carrying it.

**Can stored values be distinguished? NO, and this is the crux.**

`ProfileTab.tsx:211` renders presets `[30, 50, 70, 100]` and highlights the
selected one as `(profile.sl_percent_options ?? 50)`. So:

* **50 is both the fallback shown as selected AND a legitimate preset choice.**
  A trader who clicked "50%" and one who never opened Settings produce the same
  stored value — or the same NULL, depending on whether they saved.
* `constitution_history` cannot settle it either. The one profile holding 50.0
  was last updated **2026-07-30**, and the field only became a `RULE_FIELD` on
  **2026-08-27** — so a Settings save at that time would **not** have gone
  through `ConstitutionService` and would have written no history row. **Absence
  of history is not evidence of absence of choice.**

**Affected rows: 1 of 3** — `d5cf0bf0`, the only account with real trades (318),
holding `sl_percent_options = 50.0` and `sl_percent_futures = 1.0`, both exactly
their defaults.

**Weak circumstantial evidence for "backfill, not choice":** the profile predates
migration 028, so the backfill definitely wrote it; and *both* values sit exactly
on their defaults, which is what a backfill produces and what a coincidence of
two independent preset clicks would also produce. **Not conclusive.**

---

## 3. `sl_percent_futures` — DEFAULT 1.0

Same migration, same shape, **with one difference that matters: nothing reads
it.** It is resolved into the threshold dict by both resolvers and consumed by no
detector, no task and no live path — `build_watches` uses only
`sl_percent_options`. `constitution_service.RULE_FIELDS` does **not** include it.

**So its stored value is inert.** It cannot produce an alert, correct or false.

---

## 4. Is `PUT /api/goals` truly dead, and can it write rule fields?

**Reachable but non-functional. It cannot write anything today.**

| check | result |
|---|---|
| router mounted? | **yes** — `main.py:470-471`, `/api/goals`, authenticated |
| `goals` table exists? | **NO** — `to_regclass('goals')` is NULL (siblings `commitment_logs` and `streak_data` both exist) |
| any `create_all` that could create it? | **none anywhere in `app/`** |
| frontend caller? | `goalsApi.ts` and `useGoals.ts` exist; **no component imports `useGoals`**; no Goals page in `src/pages/` or `_archive/` |

**Why it cannot write:** the handler's first statement is
`select(Goal).where(...)` — *before* any `Goal(...)` construction and before
`_apply_goals_to_profile`. That `SELECT` raises `UndefinedTableError`, the
enclosing `except Exception` rolls back and returns 500. **The failure happens
strictly before the write path.**

**What it WOULD write if the table existed.** `TradingGoalUpdate` accepts
`max_daily_loss`, `max_trades_per_day`, `max_position_size_percent` and
`starting_capital`; `_apply_goals_to_profile` maps them onto
`daily_loss_limit`, `daily_trade_limit`, `max_position_size` and
`trading_capital` **by direct attribute assignment, bypassing
`ConstitutionService` entirely** — no tighten/loosen gate, no history row. And
because `Goal`'s columns carry non-NULL defaults (5000.0 / 10 / 5.0) while the
handler applies only `exclude_unset` fields to the object it then passes whole,
editing **any single goal field** would write three rules the trader never set.

> **Verdict: dead in three independent ways — no table, no UI caller, no
> create_all. Not urgent. But it is one migration away from being a live
> rule-corruption path, and that is a fragile place to leave it.**

---

## 5. Decision table

| field | current default | intended semantics | existing affected rows | safe backfill | recommended action |
|---|---|---|---|---|---|
| **`cooldown_after_loss`** | DB `15` **+ model `default=15` (live on every ORM insert)** | **Always-on rule with a suggested value.** Offered per experience level, shown as a slider, submitted by the trader. Never opt-in. | **0** — all 3 profiles hold user-set values (`{0:2, 1:1}`); one is proven by `constitution_history` (`10→0`, loosen+override) | **none needed** | **LEAVE AS IS.** Not the same defect class. Making it nullable is a product change, not a fix. |
| **`sl_percent_options`** | DB `50.0` (**vestigial** — ORM writes NULL; only migration 028's backfill wrote it) | Was an inert Settings preference; **retroactively promoted to an enforced `RULE_FIELD` on 2026-08-27** | **1 of 3** — `d5cf0bf0`, the only real trader, holds exactly `50.0` | **NOT determinable from data.** 50 is both the UI's `?? default` and a valid preset; the profile predates the RULE_FIELD promotion so absence of a history row proves nothing | **DROP THE COLUMN DEFAULT** (code-side, safe, no behaviour change since the ORM already sends NULL). **DO NOT auto-backfill the one row — ASK THE TRADER.** There is exactly one, and a wrong guess either invents a rule or discards a real one. |
| **`sl_percent_futures`** | DB `1.0` (**vestigial**, same mechanism) | Never promoted to a rule; **read by nothing** | 1 of 3 holds `1.0`, but the value is **inert** — no detector, task or live path consumes it | **NULL is safe** — nothing can change behaviour, because nothing reads it | **DROP THE COLUMN DEFAULT and NULL the row.** Zero risk. Or leave it; the only cost is a misleading value in the Settings UI. |
| *(context)* **`PUT /api/goals`** | `Goal` defaults 5000.0 / 10 / 5.0 | Superseded by the constitution system | **0 today** — table absent, so it 500s before any write | n/a | **DECIDE: build or archive.** It bypasses `ConstitutionService` and would write three unset rules on any single-field edit. |

---

## 6. What I would want before touching the one ambiguous row

Exactly one question to one trader: *"Your options stop-loss is set to 50% of
premium. Did you choose that?"* There is **one affected profile**, it is the
owner's own account, and the answer is decisive where the data is not.

**Failing that, the conservative order is:** drop the two vestigial column
defaults first (no behaviour change, prevents recurrence), leave the stored 50.0
alone, and treat the "did you set this?" question as a Settings prompt rather
than a migration.

**Nothing here is urgent except that one row's alert**, which is live today: that
trader receives a `notification_level=4` `constitution_violation` reading *"You
set your options exit at 50% of premium"* whenever a long option loses 50%, and
it pre-empts the universal 60% band.
