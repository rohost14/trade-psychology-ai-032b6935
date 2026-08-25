# `revenge_trade` v2 — episode model. Conceptual contract.

23 Aug 2026. **Proposal. No code. Nothing implemented.**

---

## 0. Honest assessment of the proposed direction

**B + C is right, and it is right for a reason stronger than convenience:** the
research says revenge is a distributional property of a trader over trades, and
our own 40 sessions say the genuine cases are session-shaped. Both point the same
way. This is the first direction in this review that theory and data agree on.

**But the conceptual rule as written contains a score.**

> Loss → unusually fast re-entry **and/or** increased risk **and/or** repeated
> escalation **and/or** same instrument **and/or** behaviour consistent with
> recovering → **evidence of loss-chasing increases**

Five observations, any of which *increases* evidence, and more of which increase
it *more*. That is accumulation. Counting them is a weighted score with every
weight set to one — the exact thing deleted from v1, arriving through the front
door.

The instruction "each observation must remain independent evidence; do not sum
them" is correct and is **incompatible with that rule as phrased**. Something has
to give.

**What I propose instead:** the observations do not accumulate into a quantity.
They are **the description of a state**, and severity comes from **how far that
state has progressed** — an ordinal lifecycle, not a total. Three ticked boxes
are not "more evidence" than two; a sequence that has *continued and escalated*
is a further-progressed episode than one that has not.

That keeps every observation independent, keeps the output explainable, and
introduces no weight.

**Second problem: the last clause is inferred intent.** *"Behaviour consistent
with trying to recover losses"* is a claim about motivation. It cannot come from
trade data and it is removed below — replaced, where possible, by observable
arithmetic that does not assert why.

---

## 1. What the model is

**An episode is an open mental account on one instrument.**

That is not a metaphor — it is the mechanism. Thaler's mental accounting says a
loss opens an account that stays open until recovered, and the account is
**instrument-specific**: winning elsewhere does not close it.

The model follows directly:

```
OPEN      a realized loss on instrument X
CONTINUE  re-entry into X (or its underlying) while the account is open
ESCALATE  a continuation with more exposure than the attempt that lost
CLOSE     a win on X  |  session end  |  no re-entry within the window
```

### Why this is not the streak model that failed

The streak model asked *"how many consecutive losses?"* and was refuted: genuine
cases sat at streaks 1, 1, 2, 3 while trivial ones sat at 3, 3.

The episode model asks *"how many attempts at this instrument, and did exposure
grow?"* — and **consecutive losses are irrelevant to it.** The 02-05 case has
winning trades interleaved on *other* instruments; its streak is 1, and it is the
sharpest sequence in the book.

Mental accounting predicts exactly this: **a win on a different instrument does
not close the account on this one.** The theory said streak would fail before the
data did.

---

## 2. Observable versus inferred — the line, drawn explicitly

### Observable, from trade data alone

| observation | how it is measured | needs |
|---|---|---|
| A loss was realized | `realized_pnl < 0` on a CompletedTrade | nothing |
| Re-entry into the same instrument/underlying | symbol identity | nothing |
| Attempt count on that instrument | count within the episode | nothing |
| Exposure grew | quantity, or capital-at-risk, vs the attempt that lost | nothing |
| Re-entry gap | entry time − prior exit time | nothing |
| Direction preserved | `direction` field | nothing |
| Gap unusual **for this trader** | percentile of their own post-loss gaps | maturity |
| Exposure unusual **for this trader** | percentile of their own post-loss sizes | maturity |
| Post-loss behaviour differs from post-win | two distributions compared | maturity |

### Not observable — and must never be claimed

| | why |
|---|---|
| That the trade was **intended** to recover the loss | motivation; unobservable in principle |
| That the trader was angry, frustrated, on tilt | emotional state |
| Whether they blamed luck or themselves | attribution |
| Whether they had a plan and abandoned it | no plan is recorded |

**The one borderline case, and my recommendation.** "Sized to recover" —
*would a typical move on the new position recover roughly what was lost?* — is
arithmetically computable, but it requires an assumed "typical move", which is an
invented parameter. **Leave it out.** It is the most theoretically precise
signature in the literature and the least defensible to compute. Recording it as
a known unmeasured signal is honest; approximating it is not.

**Language rule.** Copy describes the sequence and never the motive: *"you
returned to NIFTY 24750CE three times after losing on it, each time larger"* — not
*"you tried to win it back"*.

---

## 3. Testing the model against the 40-session evidence

The decisive question: does *episode shape* separate genuine from ambiguous where
magnitude and streak both failed?

| session | instrument | attempts | exposure | streak | verdict |
|---|---|---|---|---|---|
| 01-22 | SENSEX 2400CE → 2300CE | **4** | 40 → 40 → 80 → 100 → 200 | 1 and 3 | **genuine** |
| 02-24 | NIFTY 25400CE → 25500/25550 | **4** | 65 → 65 → 130 → 130 | 2 | **genuine** |
| 02-05 | SENSEX 83300PE | **3** | 100 → 120 → 200 | **1** | **genuine** |
| 02-04 | BAJFINANCE 1000CE | 2 | 750 → 750 | 1 | ambiguous |
| 03-06 | NIFTY 24750CE | 2 | 65 → 65 | 1 | ambiguous |
| 01-23 | ANGELONE 2600CE | 2 | 250 → 250 | 1 | ambiguous |

**It separates cleanly.** Genuine: **≥3 attempts with growing exposure.**
Ambiguous: **2 attempts, flat exposure.** No threshold, no rupees, no percentage
— counts and ordering only.

And note 02-05: **streak 1, three attempts, exposure doubled.** The case that
refuted the streak model is the case the episode model handles best.

### What I do not want to oversell

n = 6. Three genuine episodes and three ambiguous pairs, one trader, 40 sessions.

The rule is *structural* rather than tuned — counts and ordering cannot be
fitted the way a percentage can — which makes it less fragile than a threshold.
It is still six observations. **This is a hypothesis the model makes testable, not
a validated finding**, and it must be replayed and stated as such.

**A specific worry:** "≥3 attempts" is a number. It is not a threshold on a
*measurement* — it is the point at which repetition becomes a pattern rather than
a pair — but it is still a line drawn where the data happens to have a gap. It
needs to be argued from the mechanism, not from these six cases. My argument
would be: two attempts is a re-try, three is a refusal to stop. I do not think
that is strong enough on its own, and I flag it rather than bury it.

---

## 4. Personas

| persona | behaviour | model response |
|---|---|---|
| **Scalper** | 40 trades/day, fast everywhere | Episodes need *same-instrument repetition with growing exposure*, not speed. Their tempo alone opens nothing. Personal gap percentiles, once mature, further protect them |
| **Systematic re-entry at a level** | plans three entries into one contract | **Genuine false positive, unchanged.** Structurally identical to revenge. Intent is unobservable. Accept and state it |
| **Positional, 2 trades/week** | rarely re-enters | Episodes rarely open; never matures for the personal layer. Structural detection still works |
| **Options seller, spreads** | legs seconds apart | Strategy-group suppression, unchanged |
| **Averaging-down strategist** | adds to losers by design | **Opens an episode every time.** This is the persona most at risk of being mislabelled, and it is exactly what `options_premium_avg_down` already describes — a consolidation question, not a detection one |
| **New trader, no baseline** | — | Structural episode works from day one. The personal layer abstains |

**The averaging-down persona is the sharpest new risk in this model** and did not
arise under v1, because v1 looked at one re-entry. An episode model will fire on
deliberate averaging-down, and only the trader knows which it is.

---

## 5. The mirror (C) — supporting evidence, no threshold

Computed per trader, shown as fact, never as a verdict:

| statistic | example |
|---|---|
| median gap after a loss vs after a win | *"4 minutes after a loss, 21 after a win"* |
| median exposure after a loss vs after a win | *"1.6× larger after a loss"* |
| same-instrument re-entry rate, post-loss vs post-win | *"you go back to the same contract 3× as often after losing on it"* |

**This is the only part of the whole design that needs no threshold at all** — it
is a within-person comparison of two distributions, which is precisely what the
research measures. It requires maturity and nothing else.

It also does the job the episode alert cannot: it says *how unusual this is for
you*, which is the reference-dependence prospect theory demands and which no
universal number can supply.

---

## 6. Severity — how it is set without summing

**Proposal: severity is the episode's stage, not a count of its features.**

| stage | condition | claim |
|---|---|---|
| **opened** | a loss, no re-entry yet | nothing said |
| **continued** | one re-entry into the same instrument | recorded, not notified |
| **escalated** | a continuation with greater exposure | notified |
| **compounding** | escalation repeated | notified, higher |

Each stage is a strictly stronger structural claim than the one before, and each
is reached by observation, not by accumulation. The independent observations
(gap, personal unusualness, direction) travel **as evidence attached to the
alert**, describing it — they do not raise its stage.

**The account-relative safety frame is unchanged and stays independent.** An
account-threatening loss is still its own claim, still cannot be suppressed by
anything personal, and still needs S1.

**No stage number, no points, no multiplier.** If two episodes are equally
progressed, they are equally severe, however many optional observations each
carries.

---

## 7. What is measurable, what needs maturity, what cannot be inferred

| | |
|---|---|
| **Measurable today** | episode open/continue/escalate/close; attempt count; exposure change; gap; direction; instrument identity |
| **Needs personal maturity** | is this gap unusual *for them*; is this exposure unusual *for them*; the entire mirror |
| **Cannot be inferred, ever** | intent, emotion, attribution, plan abandonment, "sized to recover" without an invented parameter |

---

## 8. Implementation plan — if approved

| step | | replay gate |
|---|---|---|
| 1 | Episode identification as a **pure function** over session trades — open/continue/escalate/close, no persistence, no state machine | no (inert) |
| 2 | Shadow-mode detector emitting episodes alongside v1, changing no alert | **yes** — must be a no-op on alerts |
| 3 | Compare v1 and v2 findings across the 40 sessions, classified by the audit's genuine/ambiguous labels | analysis |
| 4 | Cut over only if v2 separates where v1 did not | **yes** |
| 5 | The mirror, as an analytics surface, independent of all of the above | separate |

**The episode lifetime is the session**, and that is a real limitation: an
overnight position carries an open account into the next day and this model will
not see it. Stated rather than solved, exactly as it was when `EpisodeHint` was
defined and deliberately not built.

---

## 9. What I would want challenged in review

1. **Is "≥3 attempts" defensible from mechanism, or is it my six data points?** I
   am not comfortable with it and have said so.
2. **Averaging-down.** The model cannot distinguish it from revenge. Is that
   acceptable, or does it belong to `options_premium_avg_down` entirely?
3. **Does an episode alert arrive too late to be useful?** By definition it fires
   on the *third* trade. The product claim is that an alert converts an automatic
   action into a deliberate one — the third trade may be past that point.
4. **Should the mirror ship first, alone?** It needs no threshold, no episode
   model and no new architecture, and it is the part the research supports most
   directly. Shipping it first would also generate the evidence the episode model
   needs.
