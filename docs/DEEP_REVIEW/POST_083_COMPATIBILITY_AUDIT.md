# Post-083 / post-e139683 compatibility audit

**2 Sep 2026. AUDIT ONLY. NO CHANGES.**

Every producer and consumer traced across DB model → API schemas → onboarding →
Settings → MyRules → ConstitutionService → threshold resolution → live risk state
→ detectors → alert generation → background tasks → tests/fixtures.

## Compatibility table

| field | consumers | NULL behaviour | non-NULL behaviour | stale default assumption | compatible? | required change |
|---|---|---|---|---|---|---|
| **`sl_percent_options`** | `threshold_resolution:547-553` · `trading_defaults:530` · **`live_risk_state:323`** (DECLARED band) · **`position_monitor_tasks:999`** (alert tag) · `constitution_service` RULE_FIELDS + `_TIGHTEN_DIRECTION` −1 · `api/profile` schema + range validator · `ProfileTab` presets · `Settings` payload · zod | resolver returns `None` → `build_watches` gates on `if declared_raw:` → **no DECLARED band; the universal 40/60/80 ladder fires alone**. Correct and tested | DECLARED band built → crossing → `constitution_violation`, `rule="sl_percent_options"`, severity `danger`, level 4, **pre-empts the universal band** | **none in backend.** FE: `ProfileTab ?? 50` is display-only; `Settings` initial `50.0` is now gated | ✅ | none |
| **`sl_percent_futures`** | `threshold_resolution:547-549` · `trading_defaults:529` · `api/profile` schema + validator · `ProfileTab` presets · `Settings` payload · zod. **No detector, task, live path or Rules UI** | put as `None`; **nothing reads it** | put as the value; **nothing reads it** | none | ✅ | none *(product fate still open — out of scope)* |
| **`max_position_size`** | **`behavior_engine:3266`** (`max_trade_risk`) · **`position_monitor_tasks:470`** (entry arm) · `api/cooldown:373` · `admin/users:557` · `api/goals:69` (dead table) · `constitution_service` RULE_FIELDS · both resolvers | `if risk_pct_limit and capital:` → **rule not evaluated**; entry arm returns `no_declared_exposure_rule` → **no exposure alert**. Correct | ratio vs the declared limit → `danger` ≥1.00, `critical` ≥1.20, **no pre-breach rung** (091b1cc) | **the `or 10.0` fallback was REMOVED in 0602aa8.** FE `?? 10` display-only; `Settings` initial `10` now gated | ✅ | none |
| **`cooldown_after_loss`** | `threshold_resolution:476` (`revenge_window_min`) + `:501` (`user_cooldown_min`) · `trading_defaults:496,516` · `constitution_service` RULE_FIELDS `+1` · `api/constitution:284` (cooldown status) · `rule_suggestion_service:310` · `admin/users:554` · `OnboardingStep4.cooldown_after_loss: int = 15` | **never NULL by design** — model `default=15`, written by the ORM on every insert. If it were: `or None` → `user_cooldown_min=None` → cooldown rule skipped; revenge window unaffected. Safe | declared value drives `user_cooldown_min` and raises `revenge_window_caution_min` when longer | **intentional, not stale** — `generate_defaults` returns 15/10/5/5 and onboarding renders a slider the trader submits | ✅ | none |

## Hardcoded fallback classification

| location | value | class | risk |
|---|---|---|---|
| `ProfileTab.tsx` `?? 50 / ?? 1.0 / ?? 10 / ?? 15` | 50, 1.0, 10, 15 | **display-only** | shows an unset rule as selected — cosmetic, cannot persist since e139683 |
| `Settings.tsx` `useState({...})` | 50.0, 1.0, 10, 15 | **initial form state** | **was** the fabrication vector; **gated by e139683** |
| `OnboardingWizard.tsx` `cooldown_after_loss: 15` | 15 | initial form state | intentional — the slider's starting point |
| `api/profile.py` `OnboardingStep4.cooldown_after_loss: int = 15` | 15 | **persisted default** | intentional; the wizard always sends the field anyway |
| `models/user_profile.py` `default=15` | 15 | **persisted default** | intentional — cooldown is always-configured |
| `constitution_service` matrix `cooldown 15/10/5/5` | — | suggestion | intentional |
| `position_monitor_tasks` `or 10.0` | 10.0 | **was detector logic** | **REMOVED 0602aa8** |
| `trading_defaults` `max_position_pct_caution/danger 5/10` | 5, 10 | **was detector logic** | **REMOVED 0602aa8** |
| `threshold_resolution` / `trading_defaults` `sl_percent … or None` | — | none | NULL-safe |

**No hardcoded default reaches detector or decision logic for any of the four
fields.** Every remaining one is display-only, initial form state, or the
deliberate cooldown default.

## Answers, per field

**1. NULL behaviour** — all four degrade to "rule not evaluated". No exception,
no fallback, no fabricated value. **2. Non-NULL** — each drives exactly its
documented rule. **3. NULL replaced by a hardcoded default?** Not anywhere in
backend logic; the two that did (`or 10.0`, the 5/10 band) were removed in
0602aa8. **4. Stale DB-default assumptions?** None found — both resolvers were
rewritten to `... or None` / `_slo if _slo else None`, and the cold-start paths
put `None`. **5. Exception or wrong detector behaviour from NULL?** No — every
consumer guards with a truthiness or `is not None` check before use; 1,934
backend tests pass. **6. Can NULL create a rule?** No longer: e139683 closes the
Settings race and the backend's `is not None` filters refuse a null write.
**7. e139683 compatible?** Yes — it only prevents sending hardcoded values while
the profile is pending, and the backend already ignored nulls. **8. Migration 083
compatible?** Yes — it removed two column defaults the ORM never used and nulled
one field with zero consumers.

## Two pre-existing issues found while tracing — NOT caused by 083 or e139683

**A. `cooldown_after_loss = 0` is treated inconsistently.**
`threshold_resolution:476` guards `if getattr(profile, "cooldown_after_loss", None):`
— a **truthiness** check, so an explicit `0` is skipped and `revenge_window_min`
keeps its resolved value. But `:501` writes `user_cooldown_min = 0` directly. Two
keys therefore disagree about the same declared value. **Arguably protective** —
a declared 0 should not zero the engine's revenge window — but it is undocumented
and inconsistent. Profile `d5cf0bf0` holds `0`, set via an explicit
loosen+override, so this is live.

**B. `demoData.ts` stores rupees in the percent field.**
`max_position_size: 150000` (line 399), `200000` (1289), and
`{ rule: 'max_position_size', current: 186000, limit: 200000 }` (1302) — while
line 1318 has `max_position_size: 2`. The field is a **percent of capital
(0.1–100)**. This is the same units error Pattern 24 fixed in the wizard,
surviving in the guest fixtures, which double as smoke fixtures. **Display-only,
guest mode, no detector impact.**

## Verdict

> **SAFE — no dependent code changes required.**
>
> Migration 083 and e139683 are compatible with every producer and consumer of
> all four fields. No backend path assumes the removed DB defaults, no NULL can
> raise or mislead a detector, and no NULL can create a rule.
>
> The two issues above are pre-existing, unrelated to either change, and
> recorded rather than fixed.
