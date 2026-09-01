# Capital utilization vs dangerous exposure — final product design

**1 Sep 2026. INVESTIGATION ONLY. NO CODE. NOTHING DECIDED. NO NEW THRESHOLD.**

The 10 / 15 / 30 / 50 rungs are not replaced, re-derived or carried across
anywhere in this document. §7 says what should happen to them.

Evidence: `p28d_utilization.py` on the validated open-book harness.

---

## 0. A measurement error I made, and the correction

My first pass reported *"25%+ of capital in one position: n=14, win 21.4%, mean
−₹12,980"* — a dramatic result. **It was wrong**, and the way it was wrong
matters for everything below.

The measurement was indexed by **opening fill**. A position built over five fills
appears five times, each row carrying the *same* round outcome. `VBL26JAN520CE`
was one position scaled from 25.8% to 43.3% of capital across five fills, and its
single −₹34,707 was counted five times.

Deduplicated to **distinct rounds**, the bucket is **n = 10**, and that one
position is **81% of its entire net loss**.

**Any per-fill measurement of a per-round outcome double-counts scaling.** That
is a general bias in this harness, not a one-off, and every number below is
per-round.

---

## The core finding

**Capital utilization does not predict anything on this book, and in this book it
moves in the *opposite* direction to concentration.**

### Utilization is not a signal

Peak book utilization per round, capital ₹1L:

| utilization | rounds | win rate | mean |
|---|---|---|---|
| 0–25% | 806 | 39.6% | −₹132 |
| 25–50% | 103 | **41.7%** | −₹446 |
| 50–80% | 3 | 66.7% | +₹3,685 |
| **80–100%** | **0** | — | — |

**The win rate is flat and if anything rises.** And the band the question is
about — **80–100% — never occurs**: this trader's maximum utilization across
1,071 opening fills is **60.6%**, with 88.9% of entries below 25%.

### Utilization and concentration point in opposite directions

| open positions | evaluations | median utilization | median share of deployed capital in the largest position |
|---|---|---|---|
| 1 | 705 | 7.0% | **100.0%** |
| 2 | 239 | 14.7% | 47.2% |
| 3 | 102 | 25.9% | 34.9% |
| 4 | 22 | 34.8% | 23.7% |
| 5 | 3 | 42.6% | 7.6% |

**Higher utilization here means *more* positions and *less* concentration.** The
trader at 42.6% utilized has their largest position at 7.6% of deployed capital;
the trader at 7.0% utilized has everything in one. **An alert on utilization
would fire hardest on the more diversified state.** That is the concentration
finding in reverse, and it is why the two must not be conflated.

### And single-position size is *not established* either

Peak single-position capital as a share of ₹1L, per round:

| bucket | rounds | win rate | mean | median |
|---|---|---|---|---|
| 0–5% | 249 | 40.2% | +₹45 | −₹125 |
| 5–10% | 369 | 37.4% | −₹216 | −₹240 |
| 10–15% | 202 | 43.1% | −₹35 | −₹208 |
| 15–25% | 82 | 43.9% | −₹283 | −₹375 |
| **25%+** | **10** | 30.0% | −₹4,289 | −₹950 |

**Across 0–25% there is no trend at all** — 40.2, 37.4, 43.1, 43.9 is noise. Only
the top bucket separates, at **n = 10** with **81% of its net from one position**.

> **INSUFFICIENT EVIDENCE — not a refutation.** This trader almost never takes a
> large single position: 82 rounds between 15–25% and 10 above 25%, out of 912.
> The book cannot test the hypothesis because the behaviour is nearly absent from
> it. That is a different statement from "the hypothesis is false", and the
> distinction is the one that separated `best_days` from `danger_hours`.

**Consequence for the whole design:** neither detector has demonstrated
behavioural value on this book. A position-size limit is therefore a **risk
convention** — a `UNIVERSAL_SAFETY` or `USER_RULE` statement — **not a measured
behavioural pattern**. That should govern how it is worded and how loudly it
speaks.

---

## 1. What should `overexposure` actually detect?

**Not utilization.** Measured above: no predictive power, never reaches the band
in question, and inversely related to concentration.

**A single position that is large relative to the trader's capital, at the moment
it is opened, when it can still be acted on.** One position, one comparison, one
moment.

Three things it should explicitly *not* be:

* **not a running total** — that is utilization, and repeated alerts as it climbs
  through 80 / 90 / 100% is precisely the spam the question is about;
* **not notional** — §0 of the design pass; futures notional is 6–10× the capital
  actually required, which produced 4-of-4 futures firing;
* **not a verdict** — *"ALL-IN BET"* is a judgement, not a mirror.

## 2. What should `excess_exposure` actually detect?

**The same thing, one moment later, where it cannot be acted on.**

That is the honest answer, and it is why §3 matters. Its only genuinely distinct
contribution today is that it runs on a `CompletedTrade`, so it is the **record**
of how large positions were, which is what Analytics needs and Alerts does not.

## 3. Are they genuinely different behaviours?

**No. They are one concept at two moments.**

| | `overexposure` | `excess_exposure` |
|---|---|---|
| subject | one position vs capital | one position vs capital |
| moment | opening fill, **open** | completed trade, **closed** |
| quantity | notional | capital requirement |
| actionable | **yes** | no |

The quantity difference is a **defect**, not a distinction — and on 85.2% of this
book the two quantities are already the identical number, because for a bought
option the premium *is* the capital.

**Recommendation: one capital-relative concept, with a disposition split.**
Entry-time `alerting`; exit-time `analytics`/`info` — evidence only, no
`RiskAlert`, no `danger_zone` influence, per the closed INFO/evidence rule. This
also matches the page-ownership split: **Analytics owns quantified cost, Alerts
owns the live loop.**

This creates no duplicate alert by construction, and it preserves the record.

## 4. How should ordinary high utilization be presented?

**As a number on a screen the trader chose to look at. Never as an alert, and
never as a series.**

* **Where:** the Dashboard's position area or Analytics — a **pull** surface.
* **What:** deployed capital, capital remaining, and the split across positions.
* **Never:** a push notification, a `RiskAlert` row, or `danger_zone` input.
* **Never a ladder.** No 80 / 90 / 100% rungs. A level crossing a line is not an
  event; the evidence shows the level does not predict anything.

The one framing that survives the measurement is **composition, not level**:
*"₹40,000 deployed of ₹50,000 — 78% of it in one position"* says something the
raw 80% does not, and it is the quantity that at least points the right way.

**Caveat that must travel with any utilization display — see §6:** for a naked
short option the margin posted is **not** the potential loss. A utilization
figure that mixes bought options and naked shorts adds a loss ceiling to a margin
deposit and calls the total "capital at risk". That sentence would be false.

## 5. What should qualify as a behavioural alert rather than information?

On the evidence here, **information is the default and an alert needs a reason
beyond size**. Four candidate qualifiers, with what is known about each:

| candidate | status |
|---|---|
| **A declared rule was crossed** | **Strongest.** Factual, needs no behavioural claim, and the trader set the line. `constitution_violation` already owns this shape and is the most load-bearing detector in the engine. |
| **Size is extreme relative to the trader's own history** | **Plausible, not established.** Percentile-in-own-history is the only capital-invariant anchor and is already the `BEHAVIOUR_SYSTEM_DESIGN` direction — but §Core shows this book cannot calibrate it. |
| **Size arrived with an emotional marker** | **Already implemented and the best-motivated part of the current detector** — the bump on a `danger` recovery-bet / martingale / revenge event in 12h. "Large" is a level; "large, straight after chasing a loss" is a behaviour. **Not separately validated here.** |
| **Utilization crossed a level** | **Rejected.** No predictive power, band never reached, inversely related to concentration. |

**The distinction in one line:** a *level* informs; a *transition* that the
trader's own rules or history mark as unusual can alert.

## 6. Futures and naked short options when margin is unavailable

**Abstain. Silently. And this is not a small carve-out today.**

> `position_margin_observations` is **empty — 0 rows**. The Kite postback carries
> no margin and `/margins/orders` is prospective only. So for futures and short
> options `capital_requirement` is **UNAVAILABLE in production right now**.

The governing rule is the project's own: *a wrong confident answer is worse than
no answer.* The alternative is what today's detector does — substitute notional
and tell a trader their CIPLA future is *"575.0% of capital"*.

**But naked short options need a second statement, and it is not about
availability.** Even with a perfect margin figure, `denominator_kind` is
`MARGIN_POSTED` — *"loss NOT bounded by what was committed"*. So:

* **utilization understates the risk of a naked short**, structurally and
  permanently;
* **`excess_exposure`'s current copy — *"₹X at risk"* — is false for one**: it
  names the margin and calls it the risk;
* a display that sums a bought option's premium (a loss ceiling) with a naked
  short's margin (a deposit) is **adding two different things**.

**Multi-leg: do not invent grouping.** Pattern 24 measured `strategy_group` as
unusable for netting — 45% of grouped rounds have no closed sibling at their own
exit, 29 of 48 candidate pairs are the same option type. Both detectors are
position-level and each leg of a spread is judged alone, overstating what the
spread actually required. **Recorded as a known limitation, not solved.**

## 7. What happens to 10 / 15 / 30 / 50 if the quantity changes?

**They are retired with the quantity, not translated.** They were calibrated
against notional; against capital requirement they describe a different
distribution and would silently mean something else.

What is known, and it is not a replacement: `capital_requirement` at ₹1L runs
p50 **7.07%**, p90 **14.88%**, p99 **27.81%**, max **43.26%**. At ₹500k the
maximum in the entire book is **8.65%** — so a 30% rung **can never fire** for
that trader on identical trades.

> **No replacement number is proposed, and none should be chosen from this book.**
> §Core shows the outcome evidence is insufficient at exactly the sizes a
> threshold would sit at (n = 82 and n = 10). A line drawn here would be
> invented, which is the thing five retirements were about.

**The two defensible ways to set one, neither costed here:** the trader's own
declared rule (`USER_RULE`, and then it needs no evidence — it is theirs), or a
`UNIVERSAL_SAFETY` floor stated as policy and never described as "yours".

## 8. Insufficient evidence — stated

* **Position size does not have an established relationship with outcome on this
  book.** n = 82 at 15–25%, n = 10 above 25%, one position carrying 81% of the
  latter's effect. Not refuted, not established.
* **Utilization above 60.6% is unobserved.** Nothing can be said about 80–100%.
* **The emotional bump is unvalidated.** Plausible and well-motivated; not
  measured.
* **The abstention paths are untested** — zero contract-resolution failures
  occurred, because the book is NFO throughout.
* **Futures: n = 4. Naked shorts: n = 1.** Nothing about either is measurable
  here.

---

# Recommendations

## Recommended product semantics

**One capital-relative concept: *how much of my capital is committed to this one
position*.** Measured as `capital_requirement / trading_capital`, at the moment
the position opens, with abstention wherever the capital figure is not
trustworthy.

**Utilization is a separate, informational quantity.** It is a level, it is not
predictive here, and it moves opposite to concentration. It never alerts.

## What the trader should see

**Informational, pull, always available:**

> *"₹40,000 of ₹50,000 deployed. 78% of that is in VBL26JAN520CE."*

Composition first, because that is the part that at least points the right way.

**Alerting, push, only on a qualifying condition (§5):**

> *"VBL26JAN520CE — ₹25,800 committed, 26% of your capital. Your limit is 15%."*

And with an emotional marker present:

> *"…26% of your capital, opened 4 minutes after a ₹12,000 loss."*

**Never:** *"ALL-IN BET"*, *"575% of capital"*, or *"your limit 10%"* when the
trader set no limit.

## What alerts vs what only informs

| | treatment |
|---|---|
| Book utilization at any level | **inform only** — no alert, no ladder, no push |
| Single position vs capital, no declared rule | **inform** — or a `UNIVERSAL_SAFETY` floor worded as a general floor |
| Single position vs a **declared** rule | **alert** — factual, the trader set the line |
| Single position + emotional marker | **alert** — the best-motivated case, unvalidated |
| Any of the above at exit | **evidence only** — `analytics`/`info`, no `RiskAlert` |

## Treatment by instrument type

| position | capital figure | may it be summed into utilization? | alert? |
|---|---|---|---|
| **Bought option** | premium — definitional, works on MCX | **yes** — it is a true loss ceiling | yes |
| **Long cash equity** | notional delivery value | yes | yes |
| **Future** | margin — **unavailable today** | only with a real figure, and labelled as margin | **abstain today** |
| **Naked short option** | margin — **unavailable today** | **never silently** — margin is not the loss | **abstain today** |
| **MTF equity** | abstains — part-funded, no financing figure | no | no |
| **Short equity** | abstains — ~20% margin, unbounded loss | no | no |
| **Unresolved contract** | abstains | no | no |
| **Multi-leg** | per-leg only; **no grouping invented** | overstates — known limitation | per-leg, overstating |

## Relationship between `overexposure` and `excess_exposure`

**One concept, two moments, two dispositions.** `overexposure` keeps the
entry-time alert — the actionable half, and the whole point of the product's
philosophy. `excess_exposure` becomes the exit-time evidence record:
`analytics`/`info`, no `RiskAlert`, feeding Analytics' quantified-cost story.
Both switch to `capital_requirement`. They share one dedup identity via the
existing `position_epoch()`, so one position produces at most one alert per
severity rung.

**The alternative — retiring `excess_exposure` outright — is defensible** and
turns on whether Analytics needs the closed-trade size record. That is a product
call, not an evidence one.

## Exact unresolved decisions

1. **One concept or two?** Recommended: one. Everything above assumes it.
2. **Does `excess_exposure` become evidence-only, or retire?** Turns on whether
   Analytics needs the record.
3. **Does the trader get an alert with no declared rule?** §5/§7 — abstain, or a
   `UNIVERSAL_SAFETY` floor. **If a floor, its number is undecided and cannot
   come from this book.**
4. **Futures and naked shorts lose coverage** until margin observations exist.
   Accept the gap, or prioritise capturing margin?
5. **The emotional bump** — keep, and validate separately?
6. **Where does the utilization display live**, and does it ship at all?
7. **`portfolio_concentration` is retiring**, but the composition line in the
   utilization display is a concentration statement. Is that acceptable as
   *information* when it was rejected as an *alert*? **I think yes** — the
   objection was that a fixed share threshold cannot withhold on a small book,
   and a display sets no threshold. **Flagged rather than assumed.**

**Nothing is implemented. No threshold is proposed. Awaiting decisions.**
