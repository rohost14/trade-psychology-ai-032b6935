# Money rules for F&O — trace and proposed design

**1 Sep 2026. TRACE + PROPOSAL. NO CODE WRITTEN.**

Requested: three trader-defined money rules — daily loss limit, per-trade loss
limit, capital exposure limit — each opt-in, each producing its own violation.

---

## 1. Trace — every consumer of the six fields

### `daily_loss_limit` — EXISTS, rupees, unambiguous

| consumer | use |
|---|---|
| `UserProfile.daily_loss_limit` | `Column(Float)` — *"Max loss per day (₹)"* |
| `constitution_violation` rule 1 | ladder on `session_loss / limit` |
| `session_meltdown` | **abstains** when unset (Pattern 17) |
| `api/constitution.py` usage endpoint | `usage("daily_loss", loss, limit)` |
| `api/coach.py` | quoted into the AI prompt |
| `api/goals.py` | `Goal.max_daily_loss → daily_loss_limit` |
| `api/admin/users.py` | admin read/write |
| `OnboardingWizard` / `MyRules` | opt-in (fixed today, `41bf2da`) |

**No contradiction. Rupees everywhere.**

### `max_position_size` — EXISTS, percentage, ONE latent contradiction

The DB settles it:

```python
max_position_size = Column(Float, nullable=True)
# Max capital-at-risk per trade (% of capital, e.g. 10.0)
```

| consumer | reads it as | correct? |
|---|---|---|
| `constitution_violation` rule 6 (`max_trade_risk`) | **% of capital**, vs `capital_requirement` | ✅ |
| `threshold_resolution` → `max_position_pct_caution/_danger` | **%**, feeds `excess_exposure` | ✅ |
| `api/constitution.py` schema | `Field(ge=0.1, le=100)` → **%** | ✅ |
| `api/admin/users.py` schema | `Field(ge=0.1, le=100)` → **%** | ✅ |
| `api/goals.py` | `max_position_size_percent` → **%** | ✅ |
| `MyRules.tsx` | *"Max risk per trade (% of capital)"*, step 0.5 | ✅ |
| `OnboardingWizard` | was `50000` → **rupees** | ❌ **fixed today** |
| **`api/cooldown.py:373`** | `data.order_value > profile.max_position_size` → *"exceeds your limit of ₹X"* → **rupees** | ❌ **still wrong** |

**`POST /cooldown/pre-trade-check` has NO callers** — grep across `src/` and
`backend/app/` returns only its own definition. So the contradiction is
**latent, not live**, exactly as the wizard's was for `max_trade_risk`.

### `suggested_daily_loss_limit` / `suggested_max_position_size`

Produced by `generate_defaults`; consumed **only** by `OnboardingWizard` (wired
today). `suggested_max_position_size` returns `m["risk_pct"]` — **1.0 / 2.0 /
2.5 / 3.0**, the generic percentages this brief rejects.

### `max_position_pct_caution` (5.0) / `max_position_pct_danger` (10.0)

`UNIVERSAL_SAFETY`, read only by `excess_exposure`. A declared
`max_position_size` maps onto them but **cannot loosen them** — the 2026-08-28
safety bound holds them at 5/10 as a floor. Tightening still works.

---

## 2. What the three requested rules map to

| # | requested | status |
|---|---|---|
| 1 | **Daily loss limit** — max realised loss in a day | **EXISTS.** `daily_loss_limit`, rupees, rule 1. |
| 2 | **Per-trade loss limit** — max realised loss on one trade | **DOES NOT EXIST.** New field + new rule required. |
| 3 | **Capital exposure limit** — max position exposure vs capital | **EXISTS** as `max_position_size`. |

### The semantics of #3 ARE established — no invention needed

`max_position_size` is **margin committed as a percentage of capital**:
`capital_requirement / trading_capital × 100`, computed by `quantities_for_trade`
and used identically by `excess_exposure` and `max_trade_risk`.

It is **already separate from loss**, as the brief requires. The risk layer's
own vocabulary keeps three quantities apart — entry value, P&L, capital
requirement — and deliberately does *not* have a "maximum theoretical loss".
This rule uses the third. Nothing here is being reinterpreted as a loss
percentage.

**One naming risk to note:** the column comment says *"capital-at-risk"*, which
reads loss-ish. It means capital **committed** (margin). The proposal keeps the
computation and fixes only the words the trader sees.

### All three can be independent — "any 2 of 3" is not a constraint we need

Each is a separate `RULE_FIELD`, separately nullable, and
`constitution_violation` already returns a **list**, so each produces its own
violation. Enabling any subset — including all three — works with no
architectural change.

---

## 3. Proposed changes

### A. New rule: per-trade loss limit

| | |
|---|---|
| field | `per_trade_loss_limit` — `Column(Float, nullable=True)`, **rupees** |
| migration | one nullable column; no backfill, no default |
| `RULE_FIELDS` | add it |
| `_TIGHTEN_DIRECTION` | `-1` (lower = tighter), same as `daily_loss_limit` |
| threshold key | `per_trade_loss_limit`, resolved from the profile like the others |
| detector | **a 7th rule** in `constitution_violation`, ladder on `abs(realised_loss) / limit` for the trade being analysed |
| suggestion | **none.** No value is suggested — see §4. |

It is a *realised* loss on a closed trade, so it fits the existing
`trigger="exit"` shape exactly. No new detector, no new architecture.

### B. `suggested_max_position_size` — remove the generic percentages

`generate_defaults` returns 1.0/2.0/2.5/3.0. The brief rejects a generic
risk-per-trade percentage for F&O, and Pattern 24 measured why: at ₹50k a 2%
rule allows ₹1,000 while the median lot needs ₹7,580, so it is unsatisfiable
below ~₹379k of capital.

**Proposed: stop suggesting it.** Return `None`, and let the onboarding screen
present the rule with no recommended number. The trader's own figure is the only
one with standing.

`suggested_daily_loss_limit` (2% of capital, in rupees) is a different case — it
is satisfiable at any account size and is not a per-trade risk percentage.
**Proposed: keep it**, still as a suggestion, still opt-in.

### C. `api/cooldown.py:373` — the latent rupee comparison

Compares an order value against a percentage. Unreachable today (no callers).
**Proposed: fix the comparison to use the percentage semantics**, so the field
means one thing everywhere — the brief's explicit requirement.

### D. Onboarding — a risk-rules step showing all three

Extends the block shipped today: three rules, each with its own explanation,
checkbox and input. Unchecked → `None` → no violations. Reviewed before finish.

### E. My Rules — the same three, editable

`MyRules.tsx` already lists `daily_loss_limit` and `max_position_size` with
correct units. Add `per_trade_loss_limit` and align the exposure label.

---

## 4. What I will NOT do without a decision from you

### The ladder — 0.80/1.20 → 0.60/1.00/1.20

**The structure already supports three stages.** `ladder()` returns
`caution` ≥ 0.80, `danger` ≥ 1.0, `critical` ≥ 1.20 — which is exactly
approaching / reached / exceeded. **No architectural change is needed for the
three-stage model.**

The only change requested is **0.80 → 0.60**, and that is a value change with
consequences:

- It was classified **`PRODUCT_POLICY`** today (`ba8bf62`), so by that
  classification moving it is a product decision, not a tuning exercise.
- It governs **every** ladder rule — daily loss, trade count, consecutive
  losses, per-trade risk — not just the money ones.
- It would fire earlier on all of them. Pattern 24 measured
  `constitution_violation` as already ~46% of all engine alerts.

**I have no evidence that 0.60 is better than 0.80, and I will not manufacture
one.** Options, for you to pick:

1. **Keep 0.80.** Three stages already work; ship the rules, leave the ladder.
2. **Move to 0.60 as a product decision**, recorded as such, with the alert-volume
   increase measured first and reported before it lands.
3. **Per-rule ladders** — money rules at 0.60, count rules at 0.80. Cleanest
   semantically, but it is new architecture (the ladder is currently one shared
   closure), so I would want that decided explicitly rather than slipped in.

### Suggested value for the per-trade loss limit

There is no defensible source for one. `revenge_min_loss_inr` (500) is a
detector threshold for a different question and the brief forbids borrowing it.
The book's median loss is ₹628 and p75 is ₹1,238 — descriptive, not a
recommendation. **Proposed: no suggestion. The trader types their own or leaves
it off.** Say if you want a suggestion derived some other way.

---

## 5. Blast radius

| area | change |
|---|---|
| DB | **1 migration**, one nullable column |
| `constitution_service` | `RULE_FIELDS` + `_TIGHTEN_DIRECTION` + `generate_defaults` |
| `behavior_engine` | **one new rule** inside `constitution_violation`; no other detector touched |
| `trading_defaults` / `threshold_resolution` | resolve the new key |
| `api/profile.py`, `api/constitution.py`, `api/admin/users.py` | accept the new field |
| `api/cooldown.py` | fix the latent unit bug |
| frontend | `OnboardingWizard`, `MyRules` |
| **untouched** | `excess_exposure`, the universal safety bounds, every other detector, the 0.80/1.20 values, multi-rule grouping |

**Expected firing impact:** none on any existing rule. The new rule fires only
when a trader declares a per-trade loss limit, which nobody has today, so the
default path is unchanged — measurable as 267 raw / 184 alerts, capital-invariant.

---

## 6. What I need from you

1. **The ladder** — option 1, 2 or 3 in §4.
2. **Per-trade loss limit: no suggested value** — confirm.
3. **Dropping `suggested_max_position_size`** (the 1–3% generic) — confirm.
4. **`per_trade_loss_limit` as the field name and rupees as the unit** — confirm,
   since it becomes a DB column and a public API field.

Everything else in §3 follows from the existing product and I am ready to build
it on your word.
