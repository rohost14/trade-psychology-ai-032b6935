# G4 — migration inventory for the 39 stranded constants

Classification only. **No detector is modified and no value changes.** Each row
says what the constant *is*, what it should resolve from, and whether that
decision belongs to a later detector review.

**A stranded constant** is one that describes the trader but has no path to
learning anything about them: it cannot resolve above rung 6 no matter how much
history exists. Measured against the resolver, there are 39 (of 87 total).

**The rule this follows:** do not force personalisation to eliminate a hardcoded
value. Scale-independence is not a defect — "lost 80% of the premium" is a
legitimate universal observation, and making it personal would be worse. What
gets flagged is a value that is an *unsupported judgement* wearing the costume
of a rule.

Kinds: `universal_safety` · `product_policy` · `user_rule` · `personal_baseline`
· `definitional` · `fallback`.

---

## Group E — not a detection threshold at all (1)

| constant | value | finding |
|---|---|---|
| `burst_trades_per_15min` | 6 | **No detector reads it.** Only `api/behavioral.py:95` and `api/profile.py:824` display it. Both live burst detectors use `burst_trades_per_30min_*`. Its own comment says "Used by RiskDetector" — `RiskDetector` is archived. |

**Kind:** `fallback` (display default). **Resolution:** none needed.
**Action:** it is a display value, not a threshold. Either retire it or point the
display at `burst_trades_per_30min_caution`, which is the number that actually
fires. **Flagged: its comment asserts a role it does not have.**

---

## Group A — already self-relative; only the multiple is a judgement (7)

These already divide by the trader's own behaviour. There is no denominator
problem here and no ladder to build — the open question is only whether the
*multiple* is right, which is per-detector evidence work.

| constant | value | current meaning | Kind | resolution | fallback | needs baseline | detector review |
|---|---|---|---|---|---|---|---|
| `martingale_caution_multiplier` | 1.5 | ≥1.5× the previous losing trade | `personal_baseline` | already self-relative | — | no (2 trades) | **yes** — is 1.5 right |
| `martingale_danger_multiplier` | 2.0 | full double | `personal_baseline` | already self-relative | — | no | yes |
| `overconfidence_size_mul_caution` | 1.3 | ≥1.3× session average, same underlying | `personal_baseline` | already self-relative | — | no (session) | yes |
| `overconfidence_size_mul_danger` | 2.0 | ≥2.0× session average | `personal_baseline` | already self-relative | — | no | yes |
| `recovery_bet_caution_mul` | 2.0 | 2× recent average after 2+ losses | `personal_baseline` | already self-relative | — | no (session) | yes |
| `recovery_bet_danger_mul` | 3.0 | 3× recent average | `personal_baseline` | already self-relative | — | no | yes |
| `size_escalation_pct` | 30 | +30% compounding over 3 post-loss trades | `personal_baseline` | already self-relative | — | no | yes |

**Upgrade available but not required:** each could become a percentile of the
trader's own size-ratio distribution (rung 1) instead of a fixed multiple. That
is a genuine improvement — 1.5× may be routine for one trader and extreme for
another — but it changes behaviour, so it belongs to detector review.

---

## Group B — percent of the trade itself (11)

Scale-free already: they work identically at ₹5k and ₹5cr. **Per instruction,
these are NOT auto-personalised.** Several are strong `universal_safety`
candidates — the question at review is which are safety, which are behavioural,
and which are hybrid.

| constant | value | current meaning | proposed Kind | resolution | needs baseline | detector review |
|---|---|---|---|---|---|---|
| `premium_loss_critical_pct` | 80 | 80% of premium gone | **`universal_safety`** | global, never learned | no | confirm only |
| `premium_loss_danger_pct` | 60 | 60% of premium gone | **`universal_safety`** | global | no | confirm only |
| `premium_loss_caution_pct` | 40 | 40% of premium gone | `universal_safety` / hybrid | global | no | **yes** — comment admits deep-OTM near expiry loses 40% routinely |
| `no_stoploss_loss_pct_danger` | 50 | >50% premium loss, no SL | `universal_safety` | global | no | confirm |
| `no_stoploss_loss_pct_caution` | 25 | >25% premium loss, no SL | hybrid | global | no | yes |
| `no_stoploss_expiry_loss_pct` | 25 | expiry variant | hybrid | global | no | yes |
| `no_stoploss_monthly_loss_pct` | 20 | monthly-expiry variant | hybrid | global | no | yes |
| `premium_avg_down_loss_pct` | 20 | prior position lost ≥20% before averaging down | `definitional` | global | no | yes — it is a *qualifier*, not a severity line |
| `opening_trap_large_loss_pct` | 30 | loss ≥30% of premium = "large" | hybrid | global | no | yes |
| `profit_giveaway_caution_pct` | 0.50 | gave back 50% of **your own** peak | `personal_baseline` | already self-relative | no | yes |
| `profit_giveaway_danger_pct` | 0.70 | gave back 70% of own peak | `personal_baseline` | already self-relative | no | yes |

**Flagged — unsupported judgement:** `premium_loss_expiry_shift_pct` and the
40% caution line. The file's own comment states *"deep OTM near expiry loses 40%
routinely without any behavioral failure"* — so the constant is documented as
producing false positives in a known, common case, and the shift exists to
patch it. That is a modelling gap, not a threshold to tune.

---

## Group C — absolute counts (9)

The genuine gap. Each answers "how many is too many", which is exactly the
question a trader's own distribution answers better than a fixed number.

| constant | value | current meaning | Kind | proposed resolution | fallback | needs baseline | review |
|---|---|---|---|---|---|---|---|
| `fomo_symbols_in_window` | 3 | 3+ underlyings in 30 min | `personal_baseline` | rung 1: percentile of own distinct-underlyings-per-window | current value | **yes** | yes |
| `fomo_symbols_at_open` | 2 | 2+ in the opening 30 min | `personal_baseline` | rung 1, open-window distribution | current | yes | **yes — priority** |
| `fomo_symbols_at_close` | 3 | 3+ pre-close | `personal_baseline` | rung 1, close-window distribution | current | yes | yes |
| `fomo_expiry_day_symbols` | 4 | 4+ on expiry day | `personal_baseline` | rung 1, expiry-day distribution | current | yes | yes |
| `expiry_overtrading_caution_count` | 5 | 5+ trades on one underlying, expiry | `personal_baseline` | rung 1: own expiry-day trade counts | current | yes | yes |
| `expiry_overtrading_danger_count` | 8 | 8+ | `personal_baseline` | rung 1 | current | yes | yes |
| `expiry_overtrading_caution_lots` | 10 | 10+ lots | `personal_baseline` | rung 1: own lot distribution | current | yes | yes |
| `overconfidence_win_streak_caution` | 3 | 3 consecutive wins | `definitional` | global — a streak of 3 is a streak of 3 | — | no | confirm |
| `overconfidence_win_streak_danger` | 5 | 5 consecutive wins | `definitional` | global | — | no | confirm |
| `end_session_mis_caution_count` | 2 | 2 MIS entries after 15:00 | `personal_baseline` | rung 1 if the trader does this at all | current | yes | yes |
| `end_session_mis_danger_count` | 3 | 3+ | `personal_baseline` | rung 1 | current | yes | yes |

**Flagged — unsupported judgement:** `fomo_symbols_at_open: 2`. Measured to
over-fire roughly 4:1, and 2 is the tightest value in the detector. The comment
justifies it by "market open rush", which is an assertion about traders in
general, not this one. **Highest-value candidate in the whole inventory.**

**Not flagged:** the win-streak counts. "Three wins in a row" is a definition,
not a claim about what is normal — personalising it would produce the absurd
result that a trader with many streaks needs a longer streak to be noticed.

---

## Group D — clock and hold time (8)

Mixed. Some define *what is measured*; others assert how fast is fast, which is
trader-specific — and rung 2 already solves exactly this for `panic_exit_min`
and `rapid_reentry_min`.

| constant | value | current meaning | Kind | proposed resolution | fallback | needs baseline | review |
|---|---|---|---|---|---|---|---|
| `revenge_window_danger_min` | 5 | re-entry inside 5 min = danger | `personal_baseline` | rung 2/1: low percentile of own re-entry gaps | current | session (3–5) | **yes** — its caution twin is already personalised; this one was left behind |
| `rapid_flip_min` | 10 | direction reversal inside 10 min | `personal_baseline` | rung 2: own flip-interval distribution | current | session | yes |
| `early_exit_winner_max_min` | 60 | winner held < 60 min absolute | `personal_baseline` | rung 1: own winner-hold distribution | current | yes | yes |
| `opening_trap_quick_exit_min` | 15 | exit within 15 min = reactive | `personal_baseline` | rung 2: own hold distribution | current | session | yes |
| `early_exit_ratio` | 0.40 | winner hold < 40% of loser hold | `personal_baseline` | **already self-relative** — ratio of the trader to themselves | — | no | yes (ratio value only) |
| `no_stoploss_hold_min` | 5 | exclude sub-5-min scalps | `definitional` | global — a noise floor, and the comment says the primary gate is exit order type | — | no | confirm |
| `no_stoploss_expiry_hold_min` | 5 | same, expiry | `definitional` | global | — | no | confirm |
| `no_stoploss_monthly_hold_min` | 5 | same, monthly | `definitional` | global | — | no | confirm |
| `premium_loss_fast_hold_min` | 30 | context flag for "fast collapse" | `definitional` | global — labels evidence, does not gate an alert | — | no | confirm |

**Flagged — unsupported judgement:** `revenge_window_danger_min: 5`. Its sibling
`revenge_window_caution_min` already resolves from the trader's own p25 gap;
this one stayed fixed. So one detector currently measures its caution line
against the trader and its danger line against a constant — an internal
inconsistency, not a design.

**Not flagged:** the three `no_stoploss_*_hold_min` values. The file states the
primary gate is exit order type and these only exclude micro-scalps. A noise
floor of 5 minutes is definitional.

---

## Summary

| group | n | disposition |
|---|---|---|
| A — already self-relative | 7 | no ladder needed; multiple is per-detector evidence |
| B — percent of trade | 11 | mostly `universal_safety`; **not** auto-personalised |
| C — absolute counts | 11 | the real gap; rung 1 with current value as fallback |
| D — clock | 9 | 5 personalisable, 4 definitional |
| E — not a threshold | 1 | retire or repoint |

**Kind distribution:** `personal_baseline` 20 · `universal_safety` 5 ·
`definitional` 8 · hybrid-to-decide 5 · `fallback` 1.

**Only 11 of 39 genuinely need baseline data.** The rest are already
self-relative, definitional, or legitimately universal — which is a much smaller
migration than "39 hardcoded values" suggested, and is the point of classifying
before building.

### Flagged as unsupported judgement (4)

1. **`fomo_symbols_at_open: 2`** — measured 4:1 over-firing; justified by an
   assertion about traders in general.
2. **`revenge_window_danger_min: 5`** — its caution twin is personalised, this
   is not; one detector measuring two lines two different ways.
3. **`premium_loss_caution_pct: 40`** — documented as firing routinely on deep
   OTM near expiry without behavioural failure.
4. **`burst_trades_per_15min: 6`** — comment claims a detection role it has not
   had since `RiskDetector` was archived.

### IMPLEMENTED 23 Aug 2026

`app/core/threshold_registry.py` holds a `ThresholdSpec` for each of the 16
migrated constants, declaring: **Kind · current fallback · resolution source ·
metric · percentile · maturity · provenance**, plus `review_required` for the
flagged ones.

`Resolved.kind` is now populated from the registry on **every** resolution -
never from the caller, so what a threshold IS cannot depend on which code path
resolved it. `violates_kind()` is asserted against real resolutions in tests.

**`personalise=False` on every entry.** The path exists; nothing is switched on.
A test fails if any entry is enabled, so it cannot happen without a detector
review. A named metric records that personalisation is *available*, not that it
is correct - whether it makes a given detector more accurate is evidence work at
that detector's review, and several of the 20 `personal_baseline` constants will
be better left universal.

Also enforced: a spec whose fallback drifts from the live constant fails the
suite, and a spec naming a metric must state a maturity requirement - a
percentile over no observations is noise, not personalisation.

**`burst_trades_per_15min` retired** (default and its universal floor). Readers
checked exhaustively: no detector, only two display endpoints, both repointed to
`burst_trades_per_30min_caution` - the value that actually fires. Its entry is
kept in `MANDATORY_REVIEW` so the reason survives the constant. Constants: 87 ->
86 defaults, 11 -> 10 floors.

**A regression found while doing it.** `/api/profile/behavioral-insights` and
`/api/behavioral/baseline` both read v1 flat baseline keys, which share NOTHING
with the v2 shape introduced by the H1 merge (`05962ae`). Every guard failed
silently, so both endpoints returned empty - the first one's docstring calls it
"the product differentiator". Introduced by me in H1 and missed at the time.
Both now read v2 metrics with a v1 fallback for baselines not yet recomputed.

### What is deliberately NOT built

No metric computation. The specs name metrics that `baseline_service` does not
yet produce; computing distributions nothing reads would be waste. Each metric
is added when its detector's review decides personalisation actually helps.

Groups A and B are untouched, as instructed.

### Superseded plan (kept for the record)

For the 11 in Group C plus the 5 personalisable in Group D: add the metric to
`baseline_service`, register the ladder entry with its `Kind`, and **default the
resolution to the current value** so behaviour is unchanged. The personal path
becomes available; switching each one on is detector-review work, with a replay
behind it and the differences classified rather than suppressed.
