# What is profit giveaway, really? — research and re-test

27 Aug 2026. **Research only. No code changed.** Prompted by a direct objection:
*100 alerts across 189 sessions is too many — traders lose and regain money all
day, and we cannot alert on every drawdown.*

**The objection is correct, and the evidence is worse than that.** On the only
book we have, `profit_giveaway` fires **less often than chance**, the money it
names is **identical to chance**, and **every psychological mechanism it is
premised on is refuted or absent** for this trader.

---

## 1. The scale of the objection

**181 of 189 sessions (96%) contain a giveback from the session peak.** That is
not a finding about a trader; it is a property of a running total. The peak is by
definition the maximum of the curve, so any session that does not end at its
maximum has given something back.

The current detector narrows that to 48 sessions with 100 alerts. The question
is whether the narrowing selects *behaviour* or just *bigger arithmetic*.

## 2. What the literature actually claims

Four mechanisms are invoked, in this repo or in the general framing of "giving
back gains". They predict different, testable things.

| mechanism | source | what it predicts |
|---|---|---|
| **House money** | Thaler & Johnson (1990), *Management Science* | After a gain, people accept gambles they would otherwise refuse → **risk per trade should RISE after the session peak** |
| **Break-even effect** | Thaler & Johnson (1990), same paper | After a loss, people become risk-seeking when there is a chance to get back to level → **crossing zero should change behaviour** relative to an equal loss that does not cross |
| **Reference dependence** | Kahneman & Tversky (1979); Arkes et al. (2008) on reference-point adaptation | A peak is partially adopted as a new reference, so falling from it *feels* like a loss → explains why givebacks are salient, but fixes **no threshold** |
| **Disposition / realization utility** | Shefrin & Statman (1985); Odean (1998); Barberis & Xiong (2012) | Traders realize gains **too early** — this predicts the *opposite* of giving back, and is the mechanism behind `early_exit` |

Two honest caveats before testing:

- **These are population-level findings about risk appetite**, mostly measured on
  unrealized gains inside a position or in laboratory gambles. Our detector
  measures a session's *realized* curve. The mapping is not tight.
- **Coval & Shumway (2005)** — CBOT traders who lose in the morning take more
  risk in the afternoon — is the closest real-market analogue and is already
  cited in this repo for `consecutive_loss_streak`. It concerns losses, not
  peaks.

Notice what none of them says: *"a fall of 50% from a session high-water mark is
a behaviour."* That number has no source, which the review already recorded.

## 3. The decisive test — is the giveback behaviour or arithmetic?

The same test that retired Pattern 4, adapted. **Behaviour lives in the order the
trader chose to act in**, not in the multiset of outcomes. So: shuffle each
session's trade P&Ls — same trades, same day, same count — and re-run.

2,000 shuffles per session:

| | observed | chance | ratio |
|---|---|---|---|
| sessions where the detector would fire | **49** | **56.3** | **0.87** |
| …via green-to-red | 40 | 45.7 | 0.88 |
| …via the percentage line | 16 | 17.2 | 0.93 |
| **total money given back** | **₹624,839** | **₹616,891** | **1.01** |

> **The trader's ordering contributes nothing.** The money given back is chance
> to within 1%. And the detector fires **13% LESS often than a random reordering
> of the same trades would** — this trader's actual sequencing is, if anything,
> marginally better than shuffling.

There is no way to read that as a behaviour being detected.

## 4. House money — refuted for this trader

If prior gains loosened risk appetite, risk per trade should rise after the peak.
Measured across the 50 sessions with a qualifying peak and trades after it:

| | sessions | share |
|---|---|---|
| risk per trade **rose** after the peak | 15 | 30% |
| risk per trade **fell** after the peak | **27** | **54%** |
| unchanged (±5%) | 8 | 16% |

Median capital at risk **₹7,315 before the peak → ₹6,737 after**.

**This trader sizes DOWN after their best moment of the day.** The same
direction was found in Pattern 5, where trades past the daily count line were
slower and smaller. Two independent measurements, same conclusion: this trader
does not escalate on good days.

## 5. Break-even effect — nothing at the crossing

The one mechanism that could survive §3, because it predicts a *transition*
rather than a magnitude, and the design of record explicitly treats "first
crossing today" as alertable.

533 losing trades, split by what the loss did to the session total, then
**size-matched** (controls restricted to the crossing group's loss range,
₹95–₹8,775):

| the loss… | n | stopped for the day | next position bigger | next gap |
|---|---|---|---|---|
| **crossed zero (green→red)** | 42 | 23.8% | 43.8% | 10 min |
| stayed in profit, same size | 145 | 28.3% | 46.2% | 9 min |
| already in loss, same size | 315 | 20.0% | 41.3% | 9 min |

| difference, crossing vs control | stopped | next bigger |
|---|---|---|
| vs stayed in profit | −4.5pp, **0.6 SE** | −2.4pp, **0.2 SE** |
| vs already in loss | +3.8pp, **0.6 SE** | +2.5pp, **0.3 SE** |

Against a noise floor this series has set at ~1.4 SE — and 2.6 SE as the bar for
"real" — **crossing zero shows nothing at all.** The trader behaves the same
way after a loss that turns the day red as after an identical loss that does not.

## 6. What the giveback actually is

Of the 37 measurable post-peak givebacks, the **median 77% of the loss sits in a
single trade**, and 41% are essentially one trade (≥80%).

So the typical "profit giveaway" on this book is: *the trader had a good moment,
then took one losing trade.* Which is what a losing trade is. Nothing about the
peak preceding it changes what happened.

## 7. Where that leaves the detector

| claim the detector makes | status |
|---|---|
| the giveback reflects the trader's choices | **refuted** — ratio 1.01 vs shuffle |
| gains loosen risk-taking (house money) | **refuted** — risk falls after the peak |
| crossing zero changes behaviour | **not detectable** — 0.6 SE |
| a 50% fall from peak is meaningful | **unsourced**, no break in the distribution (recorded in the review) |
| the money is real | **true** — and it is the only surviving claim |

This is the evidential position that retired `consecutive_loss_streak`: the
facts in the alert are true, and the behavioural claim around them is not
supported.

**One caveat I will not paper over: this is one trader.** The literature is
population-level, and a trader who *does* escalate after a peak would light up
§4. We can only act on the evidence we have, and the evidence we have says this
detector is naming arithmetic.

## 8. Options, with volumes

| option | sessions alerted | % of 189 |
|---|---|---|
| every session with any giveback | 181 | 96% |
| **current detector** | **48** (100 alerts) | **25%** |
| green→red transition, once per session | 41 | 22% |
| giveback above the trader's own **p80** (₹5,000) | 37 | 20% |
| giveback above own **p90** (₹8,459) | 19 | 10% |
| giveback above own **p95** (₹9,930) | 10 | 5% |
| green→red **and** above own p80 | 13 | 7% |
| green→red **and** above own p90 | 3 | 2% |

Percentile gating is the design of record's own answer (severity by percentile
in the trader's own history, plus transition, plus factual recall) and it is the
only one of these that adapts across account sizes without a chosen rupee
figure. **But note what §3 established: percentile-gating selects bigger
arithmetic, not behaviour.** It would make the detector quiet and honest, not
correct.

## 9. Recommendation

**Preferred — treat it the way Pattern 4 was treated.**

1. **Stop alerting on the behavioural claim.** The mechanism is refuted three
   ways on this book. Keep the measurement: `daily_reports_service` and Analytics
   can say *"you gave back ₹X across the year, ₹Y of it on days that finished
   red"* from the trades themselves, which is true, useful, and needs no
   detector event.
2. **If it is to interrupt a session, it must be against a commitment the
   trader made** — a declared give-back stop (*"if I'm up ₹X and hand back Y% of
   it, I'm done"*). That is a real and common trading rule, it does not exist in
   the constitution today, and it would be the honest successor. It needs an
   onboarding/Rules field, which is a product decision, not an engine one.
3. **If neither of those is wanted**, the least indefensible interim is the
   **green→red transition, once per session, gated at the trader's own p80** —
   13 sessions, 7%, one alert each. It is quiet, self-relative, and states a
   true fact at a moment the trader can act on. **It is not supported as
   behaviour**, and shipping it means accepting that.

**What I would not do:** keep the current form. 100 alerts, 25% of sessions, on
a quantity measured to be indistinguishable from chance.

## 10. Verdict

**MODIFY — down to a measurement, or up to a declared rule. Not the current
alert.**

The subject is real in the sense that the money is real. The *behaviour* the
alert asserts is not supported: the giveback is chance-ordered, house money runs
backwards for this trader, and the zero-crossing is behaviourally invisible.

**Nothing here is implemented.** The episode-key change approved earlier stands
on its own — it is a correctness fix to the dedup and is unaffected by whichever
of the above is chosen.

## Recorded for later

- **`early_exit` may have the opposite problem.** Realization utility (Barberis
  & Xiong 2012) and the disposition effect predict this trader banks gains too
  early — §4 shows them sizing down after a peak, which is consistent. That is
  `early_exit`'s review, not this one, but the two patterns make opposing claims
  about the same trader and should be read together.
- The shuffle control used here (permute a session's trade P&Ls, preserving the
  multiset) is the right first test for **any** detector keyed on a running
  total. It cost ~2 minutes to run and would have saved most of the Pattern 6
  implementation work.
