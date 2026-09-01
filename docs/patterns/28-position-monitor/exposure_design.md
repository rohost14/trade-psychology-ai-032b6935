# `overexposure` vs `excess_exposure` — design pass

**1 Sep 2026. DESIGN ONLY. NO CODE CHANGED. NOTHING DECIDED.**

**The 10 / 15 / 30 / 50 rungs are NOT touched anywhere in this document.** They
belong to the notional implementation. If the measurement changes they need a
fresh evidence-based decision, and §4 explains why this book cannot supply one.

Measurement: `p28c_quantities.py`, on the validated open-book harness.

---

## 0. A correction to my own review, before anything else

The review said *"`overexposure` divides notional by capital, and the quantity is
wrong"*. **That is too broad, and the measurement says so.**

| | opening fills | notional computable | capital_requirement usable |
|---|---|---|---|
| CE LONG | 762 | 762 | **762** |
| PE LONG | 304 | 304 | **304** |
| CE SHORT | 1 | 1 | **0** |
| FUT LONG | 4 | 4 | **0** |
| **total** | **1,071** | 1,071 | **1,066 (99.5%)** |

**On 908 of 1,066 entries (85.2%) the two quantities are the identical number**,
and every one of them is `loss_ceiling` — a bought option, where *the premium IS
the capital*. That is definitional, not coincidence, and it holds on any exchange
including MCX.

The remaining 158 "differences" are **not** a quantity difference either: they
are a **price-basis** difference. `_exposure_value` marks the whole position at
the latest fill price; `quantities_for_trade` values it at the position's
weighted average entry. Both are premium × qty × multiplier.

**So the corrected finding is narrower and sharper:** the quantity is wrong
**only where the position is not a bought option** — futures and short options.
On this book that is **5 entries of 1,071**, and it produced **4 of 4 futures
firing at every capital level**. The defect is real and the futures finding
stands unchanged; the claim that it is pervasive does not.

---

## 1. What should each detector mean?

There are **two different questions**, and today's two detectors do not cleanly
own one each.

| question | quantity | true statement |
|---|---|---|
| **A. Did I commit too much of my capital to one position?** | `capital_requirement / trading_capital` | what left the account, or was blocked, for this position |
| **B. Is my market exposure large?** | `notional / trading_capital` | the contract value I am exposed to |

**Both are legitimate. Only A is what either detector's copy claims.**

* `overexposure` says *"₹574,950 exposure (575.0% of capital, your limit 10%)"* —
  it computes B and frames it as A.
* `excess_exposure` says *"₹X at risk — Y% of capital on a single trade"* — it
  computes A and calls it "at risk", which is **also wrong**, for a different
  reason: see §8.

**Recommendation: the product should have ONE capital-relative meaning, and it
should be A.** Question B is not a risk statement for a bought option (you cannot
lose more than the premium, so notional exposure overstates nothing but explains
nothing) and is actively misleading for futures, where notional is 6–10× the
capital actually required.

**Not proposed:** deleting B as a *concept*. Notional is the right denominator
for questions about market direction and delta, and `_exposure_value` is good
code. What is proposed is that **no trader-facing capital claim uses it**.

---

## 2. Entry-time vs exit-time — redundant?

**Not redundant in timing. Redundant in subject, if both move to quantity A.**

| | `overexposure` | `excess_exposure` |
|---|---|---|
| moment | opening fill, position **open** | `CompletedTrade`, position **closed** |
| actionable? | **yes** — the copy says so: *"Raised while the position is open, because that is while it can still be acted on"* | no — it is a record |
| ladder | limit ×1.5 / ×2 / 30% / 50% | 5% / 10% |
| escalation | emotional bump (recovery-bet / martingale / revenge in 12h) | none |

**The entry-time intervention is the valuable half and must be preserved.** The
whole philosophy is *"convert an automatic action into a deliberate one"*, and an
alert after the position is closed cannot do that.

**Three coherent shapes.** I am not choosing between them:

1. **One detector, entry-time only.** `excess_exposure` retires; the size story is
   told once, when it can be acted on. Cleanest, loses the closed-trade record.
2. **One measurement, two dispositions.** Entry-time `alerting`; exit-time
   demoted to `analytics`/`info` — evidence for Analytics, no `RiskAlert`. This
   matches the closed INFO/evidence rule and the page-ownership split (*Analytics
   owns quantified cost, Alerts owns the live loop*).
3. **Keep both alerting, dedup by episode.** See §6. Weakest — two alerts about
   one position is what `_consolidate` already exists to prevent.

**I lean 2.** It preserves the intervention, keeps the historical record
Analytics needs, and creates no duplicate alert by construction.

---

## 3. Should both use `capital_requirement / trading_capital`?

**Yes for the capital claim — and on an options book the change is nearly free.**

Because the two quantities are already identical on 85.2% of entries, switching
`overexposure` to `capital_requirement` **changes almost nothing on this book
except the futures**, which is exactly the defect.

**But it converts a wrong alert into no alert, and that must be a stated choice.**

`capital_requirement` is DEFINITIONAL only for bought options and long cash
equity. For **futures, short options and short equity it requires a margin
figure**, and:

> **`position_margin_observations` is EMPTY — 0 rows.** `broker_margin_service`
> has nothing to resolve from. The Kite postback carries no margin and
> `/margins/orders` is prospective only.

So today, switching the quantity means **futures and short options get no
capital-relative alert at all** until either the margin model is wired in as
`COMPUTED` or broker observations start being captured.

**That is the correct direction under the project's own governing rule** — *a
wrong confident answer is worse than no answer* — but it is a **product
decision**, because it removes coverage from precisely the instruments where
position size matters most. It should be taken deliberately, not as a side
effect of a bug fix.

---

## 4. Can thresholds be derived from real F&O margin data?

**Partly, and the honest answer to the question as posed is NO — not from this
book.** Here is what the data does and does not support.

`capital_requirement` as a share of capital, on the 1,066 usable entries:

| declared capital | p50 | p75 | p90 | p99 | max |
|---|---|---|---|---|---|
| ₹100,000 | 7.07% | 11.13% | 14.88% | 27.81% | **43.26%** |
| ₹200,000 | 3.54% | 5.57% | 7.44% | 13.91% | 21.63% |
| ₹500,000 | 1.41% | 2.23% | 2.97% | 5.56% | **8.65%** |

**The distribution is real and derivable. A threshold on it is not**, for one
reason that no amount of data fixes:

> **Any absolute %-of-capital line is a function of declared capital, not of
> behaviour.** At ₹1L the maximum position in the entire book is 43.26%; at ₹500k
> it is 8.65%. A `critical` rung at 30% flags the top ~0.7% of entries for one
> trader and **can never fire at all** for the other. Same trades.

That is the same 115× swing the review found, and it is structural.

**What the data CAN support:**

* **Where a candidate line sits in the trader's own distribution.** Anyone
  choosing a number can be told: "this would flag the top N% of your entries."
  That is evidence about consequences, not a derivation of the number.
* **A capital-invariant anchor.** Percentile-in-the-trader's-own-history is the
  only formulation measured here that does not move with a self-reported field —
  and it is already the stated direction in `BEHAVIOUR_SYSTEM_DESIGN.md`
  (severity = percentile, danger ≈ p80, critical ≈ p95).
* **A universal safety floor**, which is a policy statement rather than a
  measurement, and which the `Kind` taxonomy already has a slot for
  (`UNIVERSAL_SAFETY`, may be tightened, never loosened).

**What it cannot support, and what I am therefore not proposing:** any specific
replacement for 10 / 15 / 30 / 50. **Those numbers are not re-derived here and
must not be carried across to a different quantity.**

---

## 5. What happens per instrument type

Straight from `risk_quantities._capital_for` and `_denominator_kind`, confirmed
against the measurement:

| position | `capital_requirement` | `denominator_kind` | needs margin? | MCX? |
|---|---|---|---|---|
| **Long option** | premium paid — **definitional** | `LOSS_CEILING` | no | **yes, works** |
| **Short option** | margin posted | `MARGIN_POSTED` | **yes** → abstains today | no (MCX unsupported) |
| **Future** | margin posted | `MARGIN_POSTED` | **yes** → abstains today | no |
| **Long cash equity** | notional (delivery value) | `NOTIONAL` | no | n/a |
| **Long equity, MTF** | **abstains** — part-funded, no financing figure | — | — | n/a |
| **Short equity** | **abstains** — ~20% margin against unbounded loss | `UNRELIABLE` | — | n/a |
| **Unresolved contract** | **abstains** | `UNRELIABLE` | — | — |

**Spreads / multi-leg.** Neither detector nets legs. Both are **position-level**,
and margin benefit from hedging is a *portfolio* property — the margin model
reproduces it only by joint scanning. Two legs of one spread are therefore two
independent alerts, each overstating the capital the spread actually required.
**This is the same limitation Pattern 24 recorded for `per_trade_loss_limit`**
(`strategy_group` grouping was measured unusable for netting: 45% of grouped
rounds have no closed sibling at their own exit). **Not solved here.**

**MCX.** The asymmetry is worth stating plainly, because it is easy to get
backwards: a **bought** MCX option works — the premium is the capital regardless
of MCX's unsourced scan ranges — while an MCX **future or short option abstains**
via `may_compute_capital`. `exchange_support` is NFO-only for margin.

**Unresolved instruments.** Both detectors already abstain, and
`portfolio_concentration` abstains for the *whole book* on one bad leg, which is
the right call. **This path is untested on the reference book** — zero
abstentions occurred, because the book is NFO throughout.

---

## 6. Preserving the entry-time intervention without duplicate alerts

**The mechanism already exists and was written with this review in mind.**

`position_monitor_tasks.position_epoch()` identifies a position by the timestamp
of the `OPEN`/`FLIP` that took it away from zero — stable for the position's
life, and changing the instant the trader flattens and re-enters.
`_already_alerted_at_or_above()` then suppresses a repeat at the same or lower
severity, so **one open position yields at most one alert per severity rung, by
construction rather than by a cap**.

Its docstring hands the problem to this review explicitly:

> *"Deliberately NOT part of `_fire_position_alert`. That function's 30-minute
> window is shared with `holding_loser`, `overexposure` and
> `portfolio_concentration`, and changing it would alter three detectors that
> have not been reviewed."*

**Two of those three are in this review**, and `portfolio_concentration` is
retiring. So the episode rule can be extended to `overexposure` as a scoped
change — but note the shared 30-minute window would still govern `holding_loser`,
which is `RESEARCH FURTHER` and must not be altered by this pass.

**Cross-detector duplication** is separate and already handled: `overexposure`
and `excess_exposure` sit in the same `_consolidate` group (*"the position is too
big"*), so the trader receives one message even when both fire. **That is
presentation-level dedup, not measurement-level** — both still write
`BehaviorEvent` rows, and both still count toward `death_spiral`'s domain count.
Shape 2 in §2 removes the problem at the source.

---

## 7. What if the trader has configured no capital or exposure rule?

**Today the behaviour is wrong in a way this project has already fixed twice.**

```python
max_size = thresholds.get("max_position_size") or 10.0
...
f"({exposure_pct:.1f}% of capital, your limit {max_size:.0f}%)"
```

**It invents 10%, then calls it *"your limit"*.** That is precisely the defect
Pattern 24 fixed (the wizard wrote `max_position_size: 50000` — rupees into a
percent field) and Pattern 17 fixed (`session_meltdown`'s undocumented
`capital * 0.05` fallback, removed with **no replacement percentage
substituted**). Money rules are **opt-in and None until the trader opts in**;
describing an invented default as the trader's own contradicts a decided policy.

`excess_exposure` is closer to correct: it **abstains** without
`trading_capital` — measured at 0 firings without capital, 231 with — but it
still uses `max_position_pct_caution/danger` defaults of 5/10 when no rule is
declared.

**Three options, none chosen here:**

| | behaviour | precedent |
|---|---|---|
| **A** | **Abstain** with no declared rule | Pattern 17 (`session_meltdown`), Pattern 24 (money rules opt-in) |
| **B** | Fire on a **UNIVERSAL_SAFETY** bound, worded as a **general** floor and never as *"your limit"* | the `Kind` taxonomy already supports it; `excess_exposure`'s 5/10 band is described as one |
| **C** | Fire only when a rule is declared, and **prompt** for it once in Rules | the standing product finding: ask once up front, infer everything else |

**Whatever is chosen, the copy must not say "your limit" about a number the
trader never set.** That part is not a judgement call.

---

## 8. What the trader-facing wording should say

**The wording must follow `denominator_kind`, because the true sentence is
different for each — and today it does not.**

**Bought option (`LOSS_CEILING`).** The premium is both the capital and the most
that can be lost, so this is the one case where "at risk" is literally true:

> *"NIFTY24800CE cost ₹12,400 — 12% of your capital, and the most this position
> can lose."*

**Future or short option (`MARGIN_POSTED`).** The margin is what was blocked; the
loss is **not** bounded by it. `excess_exposure`'s current *"₹X at risk"* is
**wrong here** — it names the margin and calls it the risk:

> *"CIPLA26JANFUT blocked ₹86,000 of margin — 43% of your capital. A futures
> loss is not limited to the margin posted."*

Never *"575% of capital"*, which is what notional produces.

**Three rules that fall out of the existing layer:**

1. **Never present `COMPUTED` as `BROKER`.** `MarginSource` exists for this, and
   the measured error is +5–7% on short options. Copy must be hedged accordingly
   — *"about ₹86,000"*, not *"₹86,000"* — when the figure is computed.
2. **"Maximum theoretical loss" is deliberately not a quantity** and must not
   appear.
3. **Abstain silently.** An unresolved contract or a missing margin figure
   produces **no message**, not a hedged one.

**And the frame should follow the philosophy.** *"Mirror, not blocker"* — the
current *"ALL-IN BET"* label and *"your limit 10%"* are a verdict and an invented
rule. A mirror states the fact and the trader's own comparison, and says nothing
when it has neither.

---

## 9. What this pass does NOT decide

* **No threshold.** 10 / 15 / 30 / 50 are untouched. §4 shows why this book
  cannot re-derive them for a different quantity.
* **No verdict on `overexposure`.** The review's **MODIFY** stands, still blocked.
* **No change to `excess_exposure`'s deferral.** Its live broker-margin
  validation is still open, and §3 shows why it now matters more, not less:
  `position_margin_observations` is empty, so the margin path abstains in
  production today.
* **No multi-leg netting.** Recorded as a shared limitation with Pattern 24.
* **`holding_loser` untouched.** The shared 30-minute window in
  `_fire_position_alert` must not move in this pass.

## 10. The decision that unlocks everything else

**Does the product make one capital-relative claim or two?**

Everything above follows from it. If **one** (recommended, quantity A,
`capital_requirement`): `overexposure` switches quantity, `excess_exposure`
becomes its exit-time evidence twin or retires, thresholds get re-derived once
against the new quantity, and futures lose coverage until margin is available.
If **two**, then each needs its own copy, its own thresholds and a clear reason
why a trader should receive both — and I have not found that reason.
