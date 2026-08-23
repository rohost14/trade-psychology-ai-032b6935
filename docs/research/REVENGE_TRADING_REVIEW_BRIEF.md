# Revenge trading — human review brief

23 Aug 2026. Research and analysis for the decision *"what evidence should a
revenge detector require?"* **No code, no design proposed as settled.**

Written because the implementation review ended with four refutations and no
replacement: magnitude alone insufficient, streak alone insufficient, the
one-trade B-axis insufficient, no defensible alternative found in the data.

**Citation note.** Findings below are from memory of the literature. Direction and
substance I am confident about; exact figures, years and effect sizes should be
checked against the papers before any of it is quoted externally or shown to a
trader.

---

## Part 1 — What revenge trading actually is

### The plain definition

A trade taken **because of a previous loss rather than on its own merits** — the
decision is made against the loss, not against the market.

That definition contains the entire measurement problem: *"because of"* is a
statement about **motivation**, and motivation is unobservable. Everything below
is about what observable behaviour is *consistent with* it.

### It is not one bias — it is at least four, stacked

| mechanism | what it contributes | key work |
|---|---|---|
| **Reflection effect** | risk *seeking* in the domain of losses — the opposite of the risk aversion the same person shows in gains | Kahneman & Tversky, prospect theory (1979) |
| **Break-even effect** | after a loss, people accept bets they would otherwise refuse, *specifically* those offering a route back to even | Thaler & Johnson (1990) |
| **Mental accounting** | the loss opens an "account" that stays open until recovered; closing it in the red is what hurts | Thaler |
| **Escalation of commitment** | continued investment in a failing course of action, to justify the prior commitment | Staw (1976) |

The stack matters. Prospect theory explains *why risk appetite flips*; the
break-even effect explains *which* bet is chosen; mental accounting explains *why
the same instrument*; escalation explains *why it repeats*.

### The finding that matters most for us: the realization effect

**Imas (2016), "The Realization Effect"** — the sharpest result in this
literature for our purposes.

> After a **realized** loss, people take **more** risk.
> After an equivalent **unrealized (paper)** loss, they take **less**.

The act of *closing* the position is the trigger, not the loss itself. Booking it
converts a fluid situation into a settled fact, and the settled fact is what
provokes recovery-seeking.

**Direct implication for the detector, and it is already right:** keying on
`CompletedTrade` — a *realized* loss — is theoretically correct. A detector that
fired on unrealized drawdown would be measuring the wrong thing, and the
literature predicts the *opposite* behaviour there.

### The closest thing to field evidence

**Coval & Shumway (2005)**, CBOT proprietary traders: traders who lose in the
morning take **significantly more risk in the afternoon**, and this afternoon
risk-taking does not earn a return. Real market participants, real money, and the
effect is intraday — the same window our detector works in.

**Frino, Grant & Johnstone (2008)** find break-even behaviour in futures traders.
**Locke & Mann (2005)** find professional futures traders differ mainly in
*discipline* rather than in predictive skill. **Barber & Odean (2000)** and
**Barber, Lee, Liu & Odean (2014, Taiwan day traders)** establish the backdrop:
active retail trading destroys returns on average.

### Physiology and arousal

**Lo & Repin (2002)** measured physiological responses in real traders;
**Lo, Repin & Steenbarger (2005)** found more emotionally reactive day traders
performed worse. **Coates & Herbert (2008)** found cortisol rising with market
variance among London traders.

Why it matters here: arousal shortens deliberation. Under high arousal, decision
time collapses and System-1 responses dominate. **Speed is therefore not merely
correlated with revenge — it is a plausible physiological marker of the state.**

**Caveat:** ego depletion — the "willpower is a finite resource" account often
invoked for post-loss discipline failure — has **failed large replication
attempts** and should not be leaned on.

---

## Part 2 — What triggers it

Ordered by how well supported and how observable each is.

| trigger | support | observable in our data? |
|---|---|---|
| A **realized** loss | strong (Imas) | **yes** — CompletedTrade |
| Loss larger than that trader expects | strong (prospect theory: reference-dependence) | **partly** — needs their own distribution |
| Loss on an instrument they had conviction in | mental accounting | **proxy** — same-instrument re-entry |
| A losing *run* rather than one loss | escalation of commitment | **yes** — session facts |
| Time pressure — session ending, account must be recovered *today* | deadline effects | **yes** — time of day |
| A winning streak broken | contrast effect | **yes** |
| Loss attributed to bad luck rather than a bad decision | attribution theory | **no** — unobservable |
| Identity threat ("I am a good trader") | self-concept literature | **no** |

**The reference point is the crux.** Prospect theory is reference-*dependent*:
"large loss" means large *relative to that person's expectation*, not relative to
premium, capital, or anything universal.

That is a theoretical explanation for our empirical failure. **S2a asked "what
fraction of premium is a big loss?" — a question the theory says has no
person-independent answer.** A 12% loss and a 13% loss are not distinguishable in
the abstract; they are distinguishable relative to what *that trader* usually
loses, and to what they expected on *that* trade.

---

## Part 3 — What people actually do

From practitioner literature (Mark Douglas, *Trading in the Zone*; Brett
Steenbarger's work on trader performance) and consistent with the academic
mechanisms:

1. **Re-enter faster than usual.** Deliberation collapses.
2. **Size up.** The break-even effect selects the bet that can recover the loss —
   which usually means a bigger one.
3. **Return to the same instrument.** The mental account is instrument-specific:
   winning it back elsewhere does not close it. Douglas frames this as needing the
   market to "pay you back", personifying it as an adversary.
4. **Abandon the plan.** Stops widened or removed — the position must be given
   room to recover.
5. **Trade more frequently** — a burst rather than a single trade.
6. **Size to the loss.** The new position is sized so that a plausible move
   recovers roughly the amount lost. This is the most *specific* signature in the
   whole literature and, as far as I know, nobody operationalises it.

**Observation about our own data.** Every likely-genuine sequence we found
displays 1, 2, 3 and 5 together — faster, bigger, same contract, repeated —
across a session. None of the ambiguous ones displays more than two.

---

## Part 4 — The methodological problem, stated plainly

**The academic literature never labels an individual trade as revenge.**

Every result above is a **distributional** claim: *this population takes more risk
after realized losses*; *these traders take more risk in the afternoon after
morning losses*. The unit of analysis is a trader over many trades, or a
population, and the finding is a **shift in a distribution**.

We have been attempting something the science does not attempt: **per-event
classification of a state that is only measurable as a tendency.**

That reframes every failure in the implementation review:

- magnitude did not separate → because "large" is reference-dependent and we used
  a universal denominator;
- streak did not separate → because escalation is a *tendency*, not a threshold
  crossed at trade *n*;
- the one-trade B-axis did not separate → because the object being measured is a
  change in behaviour, and a change needs two states to compare.

**The detector is trying to answer a question of a kind that the evidence base
answers only in aggregate.**

---

## Part 5 — What this suggests, as options for the review

Not recommendations. Four framings, each with what it would require and what it
would cost.

### Option A — Per-trade classification, made personal

Keep per-trade alerts, but replace every universal denominator with a
*self-relative* one: this loss versus their own loss distribution; this gap
versus their own gaps; this size versus their own sizes after losses.

*Requires:* mature personal baselines (M1, P1, P2 — all unresolved).
*Costs:* nothing for a new trader; the cold-start case gets no revenge detection
at all.
*Theoretical fit:* good — matches reference-dependence.
*Our evidence:* untested; the replay could not exercise personal frames.

### Option B — Session-state detection

Stop classifying trades. Detect the **state**: "since your loss at 11:04 you have
traded faster, larger and returned to the same contract three times."

*Requires:* a session-level detector, and an episode concept — which was defined
and deliberately not built.
*Costs:* the alert arrives later, after the pattern establishes. Less
interruptive, possibly less useful in the moment.
*Theoretical fit:* strongest. It matches how the phenomenon is actually
characterised and how our own genuine cases look.
*Our evidence:* every convincing case was session-shaped; no single-trade feature
separated them.

### Option C — Distributional mirror, no alert at all

Do not classify anything. Report the trader's own statistic:

> *"After a losing trade you re-enter in 4 minutes on average. After a winner,
> 21 minutes. Your position is 1.6× larger after a loss."*

*Requires:* only the baselines; no threshold whatsoever.
*Costs:* not real-time. It informs rather than interrupts.
*Theoretical fit:* exactly what the literature measures — a within-person
distribution shift, post-loss versus post-win.
*Product fit:* this is *"mirror, not blocker"* almost verbatim.
*Our evidence:* directly computable from data we already store, and it would have
described the 01-22 session accurately without needing to classify any single
trade.

### Option D — Accept the detector cannot be validated, and say so

Keep it structural, keep it quiet, and let `heeded` decide once live.

*Costs:* indefinite silence.
*Honest merit:* it is where we are now, and it is not obviously wrong.

---

## Part 6 — What I would want the review to settle

1. **Is revenge a property of a trade, or of a trader in a session?** The
   literature says the latter. Our data says the latter. The detector is built for
   the former.
2. **If session-level, is it a different detector from `same_symbol_obsession`, or
   the same one with a better name and a trigger?**
3. **Are we willing to be personal-only?** Reference-dependence implies a
   universal threshold cannot work. Accepting that means no revenge detection
   until a baseline matures — a real product cost, honestly stated.
4. **Alert or mirror?** Option C requires no threshold, matches the product
   philosophy, and is computable today. It is also not an alert, and the engine is
   built to alert.
5. **What would count as confirmation?** No trade-derived signal separated genuine
   from ambiguous in 40 sessions. `heeded` — did they stop after being told — is
   the only measure that could, and it needs live users.

---

## Part 7 — Limits of this brief

- Almost none of the research is on **Indian retail F&O options traders**. Weekly
  expiries, lot sizes and premium decay make this a different instrument
  environment from CBOT futures or US equities.
- Lab studies use **gambles**, not markets. Field studies use **professionals**,
  who are not this population.
- Effect sizes are **modest**. These are tendencies, not signatures.
- **One trader, 40 sessions** on our side. Every empirical claim about our own
  data carries that limit.
- I have deliberately not proposed a threshold, a rule or a design. The point of
  this brief is to establish what question the detector should be asking before
  anyone answers it.
