# Exposure hierarchy — verification before implementation

**1 Sep 2026. INVESTIGATION ONLY. NO CODE CHANGED.**

All twelve cases below were **executed against live code**, not reasoned about.

---

## 1. The severe-loss ladder — traced

**It is 40 / 60 / 80, not 60 / 80 / 100.** Correcting that before anything else,
because the decision names numbers that are not in the code.

| | |
|---|---|
| **where** | `services/live_risk_state.py` — live, on the tick path. The exit-time `_detect_premium_loss_event` is **`analytics`/`info` since 2026-08-27** (Pattern #8) and raises no alert; it was demoted precisely because it duplicated the live one. |
| **denominator** | **premium paid** — `(avg_entry_price − ltp) / avg_entry_price × 100`. Clamped at 100%. |
| **bands** | `premium_loss_caution_pct` **40** / `danger_pct` **60** / `critical_pct` **80**, `Kind.UNIVERSAL_SAFETY`, **+15 on expiry day** |
| **plus a DECLARED band** | from `sl_percent_options`, reported separately and never merged with the universal one |
| **instruments** | **long options only.** `build_watches` skips anything not `CE`/`PE` and anything with `qty <= 0` — *"short options: premium received, not destroyed"* |

**Does it apply correctly per instrument?**

| | covered | why |
|---|---|---|
| Bought option | **yes** | premium is the loss basis and the loss ceiling |
| Future | **no** | not `CE`/`PE`; a future has no premium basis |
| Naked short option | **no** | `qty <= 0` skipped; premium received, not paid |

**Does it work with no user exposure rule?** **Yes — verified in case G.** It never
reads `max_position_size`, `trading_capital` or `capital_requirement`.

**Can a user's exposure rule suppress it?** **No — verified in case H.** No shared
threshold, no shared code path, no shared dedup scope.

> **The hierarchy you specified is cleanly supported by the existing severe-loss
> layer.** Exposure and severe loss are already independent. **No change is
> needed there, and I propose none.**

**One thing found while tracing, reported not actioned:** `sl_percent_options`
resolves as `getattr(profile, ...) or 50.0` — so the **DECLARED** band fires at
50% for every trader, including those who declared nothing (visible in case G,
`boundary 50.0`). That is the same invent-a-default-and-call-it-declared shape
Pattern 24 and Pattern 17 fixed. **Out of scope** — it is the severe-loss layer,
not an exposure threshold. Recorded.

---

## 2. A–L: what fires TODAY

Capital ₹1L throughout. `capital_requirement` from `quantities_for_trade`.

| case | declared | position | what fires today | producer |
|---|---|---|---|---|
| **A** | none | 30% of capital | `excess_exposure` **danger**<br>`overexposure` **critical** | universal 5/10<br>notional vs invented 10% |
| **B** | none | 90% | `excess_exposure` **danger**<br>`overexposure` **critical** | same |
| **C** | 40% | 35% | `excess_exposure` **danger** ⚠️<br>`max_trade_risk` **caution** | universal 5/10 (bound held)<br>ratio 0.87 |
| **D** | 40% | 45% | `excess_exposure` **danger**<br>`max_trade_risk` **danger** | **DUPLICATE** |
| **E** | 80% | 75% | `excess_exposure` **danger** ⚠️<br>`max_trade_risk` **caution** | universal 5/10<br>ratio 0.94 |
| **F** | 80% | 85% | `excess_exposure` **danger**<br>`max_trade_risk` **danger** | **DUPLICATE** |
| **G** | none | 7.5%, loss 70% of premium | `excess_exposure` caution<br>severe-loss **[declared]** danger @50<br>severe-loss **[universal]** danger @60 | severe loss works with no rule ✓ |
| **H** | 80% | 75%, loss 70% | `excess_exposure` **danger** ⚠️<br>`max_trade_risk` caution<br>severe-loss **[declared]** + **[universal]** danger | **rule does not suppress severe loss ✓** |
| **K** | none | **FUTURES**, margin unavailable | `excess_exposure` **abstains** ✓<br>`overexposure` **critical — "575.0%"** ❌ | the notional defect |
| **L** | none | **NAKED SHORT**, margin unavailable | `excess_exposure` **abstains** ✓<br>`overexposure` **critical 30%** ❌<br>**no severe-loss watch built** | the coverage gap |

⚠️ = fires while the trader is **inside** their own declared rule.
❌ = fires on notional where capital requirement is unavailable.

**I and J** are structural rather than single-case:

* **I (entry breach → exit)** — today `overexposure` fires at entry under its own
  `pattern_type` and `max_trade_risk` fires at exit under
  `constitution_violation`. **Different pattern types, so `_pattern_dedup_key`
  never joins them: two alerts for one rule breach.** Cases D and F above are the
  exit half of exactly that.
* **J (emotional bump)** — lives **only** in `_overexposure_task`
  (`position_monitor_tasks.py:~470`): a `danger`/`critical`
  `post_loss_recovery_bet` / `martingale_behaviour` / `revenge_trade`
  `BehaviorEvent` in the last 12h raises severity one rung. **`max_trade_risk`
  has no equivalent.** Any routing of entry-time enforcement through the
  constitution rule **loses it** unless carried across deliberately.

## 3. Can the old 5/10/15/30/50 still generate alerts anywhere?

Complete consumer map, verified by grep:

| threshold | read by | anything else? |
|---|---|---|
| `max_position_pct_caution` (5.0) | `_detect_excess_exposure` only | no |
| `max_position_pct_danger` (10.0) | `_detect_excess_exposure` only | no |
| `max_size × 1.5 / × 2 / 30 / 50` | `_overexposure_task`, and dead legacy `_check_position` | no |

**Removing them is contained to two detectors.** `quantities_for_trade` itself is
untouched, so `constitution_violation.max_trade_risk` — its other consumer —
does not move.

**Two knock-on sites** that exist only to feed them:

* `threshold_resolution.py:532-536` maps a declared `max_position_size` onto
  both universal keys;
* `safety_bounds.py` then clamps that mapping so a declared value may only
  tighten — the mechanism producing the ⚠️ rows in C, E and H.

---

# THE CONFLICT — stopping here

**Your decisions leave `excess_exposure` with no trigger condition, and I will not
pick one for you.**

The two instructions in combination:

1. *"Remove/retire the old 5%/10% exposure thresholds. Do not replace them."*
2. *"Do not retire `excess_exposure` … unless a separate correctness issue makes
   that necessary"*, and it is *"analytics/evidence only"*.

`excess_exposure`'s **only** trigger is `risk_pct > caution_pct` / `> danger_pct`.
Remove those two numbers and nothing decides when it produces anything. The three
possible readings are materially different:

| | reading | consequence |
|---|---|---|
| **A** | **Retire it.** Its alerting job is `max_trade_risk`'s; its evidence job has no consumer today — `CompletedTrade` stores no capital-requirement column, and nothing reads an exposure evidence row. | Cleanest. But it is the retirement you said to report before doing. |
| **B** | **Keep as `info`, no threshold — record the exposure % on every trade.** | Fires on **1,066 of 1,071** entries. That is a data dump, not evidence of a pattern, and every one writes a `BehaviorEvent`. |
| **C** | **Keep as `info`, gated on the declared rule.** Records *"this trade used 45% against your 40% rule"* for Analytics while `max_trade_risk` raises the alert. | No duplicate **alert** (info never alerts). But it duplicates the **evaluation**, and it means `excess_exposure` still needs the declared rule — which is the mechanism you said not to duplicate. |

**I lean C** — it satisfies "no exposure `RiskAlert` without a user rule",
"no duplicate alert", and keeps an exit-time record — **but it is a genuine
reading of your words, not a derivation from them**, and B and A are equally
consistent with what you wrote.

**A second, smaller question rides on it:** if `max_position_pct_caution/danger`
are deleted from the registry, then `threshold_resolution.py:532-536` and the
`safety_bounds.py` clamp that governs them have nothing left to govern.
**Deleting that mapping is required by reading A or B; under reading C it stays,
because the info band still needs the declared value.** `safety_bounds.py`'s
documented rationale (*"declaring 40 moved the caution line to 40 and danger to
80, so the detector went quiet for exactly the traders taking the largest
positions"*) becomes **historical** either way, since the universal line it
protected is going.

---

## What is already settled and needs no further input

* **Severe loss is independent of exposure** — verified in G and H. No change.
* **The ladder is 40/60/80**, long options only, premium-denominated. Futures and
  naked shorts have **no severe-loss coverage**, and cannot until margin/MTM
  exists.
* **`overexposure`'s notional must go** — K and L show it firing "575.0%" and
  "30%" on positions where the capital requirement is explicitly unavailable.
* **The emotional bump lives only in `_overexposure_task`** and must be carried
  across deliberately or it is lost.
* **Utilization stays informational.** Nothing in A–L computes it today.

**Tell me A, B or C and I will implement the whole hierarchy in one pass.**
