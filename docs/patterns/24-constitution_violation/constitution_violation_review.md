# Pattern 24 — `constitution_violation`

**Review, 1 Sep 2026. Findings only. NO CODE CHANGED.**

Review-order 24. Source-list **#23**, recorded as *"IMPLEMENTED BUT NOT YET
VERIFIED — cannot fire in replay; 6 rules in one pattern type"*.

Reviewed **alone**. (The "review them together" line in the brief is carried
over from the Pattern 21/22 template.)

The most load-bearing unreviewed detector in the engine: `notification_level=4`,
one of only two sources of `critical`, and **three retirements justified
themselves by saying this detector carries the behaviour** — Pattern 4
`consecutive_loss_streak`, Pattern 15 `cooldown_violation`, and part of Pattern
17 `session_meltdown`.

Measured against the real book — **175 sessions, 740 rounds**. Script:
`docs/patterns/_measurement/p24_constitution.py`.

---

## This detector cannot be judged like the others

**Six of its seven inputs are not our numbers.** They are the trader's own
declared rules: loss cap, trade count, consecutive-loss stop, cooldown, no-trade
windows, per-trade risk. The usual question — *is this threshold defensible* —
mostly does not apply, because we did not choose them.

The only values the product chooses are the **ladder**:
`constitution_approaching_pct` **0.80** and `constitution_severe_pct` **1.20**.

So the real questions are about **volume, inputs and plumbing**, and the
findings below are mostly *not defects in this detector's code*.

### Observability limit, and how it was handled

The reference book has **no user profile**, so the original replay recorded
"0 (rules off)". This detector cannot fire without declared rules.

**No values were invented.** Rules were supplied from the product's own sources
and each configuration is reported separately:

| source | what it sets |
|---|---|
| `constitution_service.generate_defaults` | count/time rules only — **money rules deliberately `None`** |
| `OnboardingWizard.tsx` form defaults | `daily_loss_limit` 2% of capital (floor ₹1,000), `max_position_size` **50000**, trades 10, cooldown 15, consec 3 |

**A correction to my own first measurement, recorded because it changes the
headline.** I first configured the money rules from the matrix and measured
**1,153 events, 711 of them `max_trade_risk` at critical**. That configuration
is not what the product ships — `generate_defaults` returns `None` for both
money rules on purpose. Every number below uses a configuration the product
actually produces.

---

## Current behaviour

Returns a **LIST** of events — several rules can breach on one trade.

```python
def ladder(ratio):
    if ratio >= severe (1.20): return "critical"
    if ratio >= 1.0:           return "danger"
    if ratio >= approaching (0.80): return "caution"
    return None
```

| # | rule | input | shape |
|---|---|---|---|
| 1 | `daily_loss` | `daily_loss_limit` | ladder on session loss ÷ limit |
| 2 | `daily_trades` | `user_daily_trade_limit` | ladder on count ÷ limit |
| 3 | `max_consecutive_losses` | `max_consecutive_losses` | ladder + an explicit "one away" caution |
| 4 | `cooldown` | `user_cooldown_min` | **binary danger** |
| 5 | `restricted_window` | `restricted_windows` | **binary danger** |
| 6 | `max_trade_risk` | `max_position_size` + `trading_capital` | ladder on capital-at-risk %, **abstains** when capital is not determinable |

| | |
|---|---|
| registry | `1.0.0`, `nature=discipline`, `alerting`, `trigger=exit`, **`notification_level=4`**, `guardian_eligible=True`, `uses_constitution=True` |
| consumes | `session`, `session_trades`, `completed_trade`, `thresholds`, `facts`, `broker_margin` |
| confidence | **none set** |
| dedup | **per rule** — `constitution_violation:{rule}`, 24h window, severity escalation and `_worsened` re-arm pass through |

Copy: *"Rule breach / Your own limits — loss cap, trade count, cooldown,
no-trade windows, position size — against what you actually did. / **These are
your numbers, written when the session was not running.**"*

---

## What is correct

**The subject is unimpeachable, and the copy is the best in the engine.** *"These
are your numbers, written when the session was not running"* is the entire
justification for the detector in one sentence, it makes no claim about the
trader's state of mind, and it cites no statistic. Nothing in five reviews comes
close.

**It is pure.** No database, no wall clock, no `await`. `broker_margin` is
pre-resolved on the context.

**The per-rule dedup key is right, and the reason is documented.** A cooldown
breach must not suppress a later daily-loss breach, so `rule` joins the key. The
same care was extended to `same_symbol_obsession`'s underlying.

**The ladder distributes properly on the count rules** (intermediate profile):

| rule | caution | danger | critical |
|---|---|---|---|
| `daily_trades` | 42 | 11 | 3 |
| `max_consecutive_losses` | 50 | 18 | 11 |
| `daily_loss` | 19 | 26 | 130 |

**The "one away" special case is a genuine fix, correctly reasoned.** Its comment
explains that a percentage ladder cannot express "one more loss breaks it" on a
small integer: 0.80 × 3 = 2.4 and 0.80 × 4 = 3.2 both round up to the limit
itself, so for limits of 2–4 the warning rung could never fire — and the
onboarding default is 3. The fix uses `streak == limit - 1`, which has an exact
meaning rather than a chosen multiplier.

**`max_trade_risk` abstains rather than guessing** (F17), and its abstention is
rare: capital is not determinable on **16 of 740 trades (2%)**.

**The two retirements that lean on it are VALIDATED by measurement.**

| retired detector | lands on | measured |
|---|---|---|
| Pattern 4 `consecutive_loss_streak` | rule 3 | **194** events at a declared limit of 3 |
| Pattern 15 `cooldown_violation` | rule 4 | **181** events at a declared 15-minute cooldown |

**181 is exactly the number Pattern 15's retirement cited** against that
detector's own 0. Reproducing it independently here confirms the retirement's
central claim rather than taking it on trust.

---

## Problems found

### P1. `max_trade_risk` is DEAD in production — a units contradiction upstream

The detector reads `max_position_size` as a **percentage of capital**:

```python
risk_pct = risk / float(capital) * 100
ratio    = risk_pct / float(risk_pct_limit)
```

Three surfaces disagree on what that field means:

| surface | value | unit |
|---|---|---|
| `constitution_service.generate_defaults` | `1.0 / 2.0 / 2.5 / 3.0` | **percent** |
| `MyRules.tsx` | label *"Max risk per trade (% of capital)"*, step `0.5` | **percent** |
| **`OnboardingWizard.tsx`** | **`max_position_size: 50000`** | **rupees** |

The wizard's form default is never overridden, because the merge is
`max_position_size: rec.max_position_size ?? d.max_position_size` and
`generate_defaults` deliberately returns `None`. So the profile is written with
**50000**, the detector reads it as **50,000 percent**, every ratio is ~0.0002,
and the rule **fires 0 times**.

**Measured: `max_trade_risk` = 0 firings** under the real onboarded
configuration.

**The detector is not the party in error** — its reading matches both
`generate_defaults` and `MyRules`. The wizard is the outlier. But the
consequence is that one of six rules is silently inert for every trader who
completed onboarding without editing that field by hand.

### P2. The wizard defeats the "money rules are suggested, never applied" policy

`constitution_service` returns `daily_loss_limit: None` on purpose, and its
comment is unusually explicit:

> *"F&O has fixed lot sizes — you cannot buy 0.4 of a NIFTY lot. On ₹50,000 of
> capital these defaults allow ₹500-1,000 a trade while one option lot costs
> ₹5,000-15,000, so the minimum tradeable unit is 10-30× the limit and EVERY
> trade breaches on contact. Replaying a real tradebook produced 212 rule
> violations across 61 sessions, 54% of all alerts, none of which described
> behaviour."*

**The wizard sets it anyway.** Its slider computes
`max(1000, round(capital * 0.02 / 500) * 500)` and submits it — so on ₹50,000
the trader gets a **₹1,000** daily loss limit, which is the very number the
owning service refuses to set.

**Measured at that configuration: `daily_loss` fires 175 times.**

And the comment's warning is confirmed independently. Capital requirement per
trade on this book:

| p10 | p25 | median | p75 | p90 |
|---|---|---|---|---|
| ₹2,516 | ₹4,599 | **₹7,580** | ₹11,358 | ₹14,880 |

**For the median trade to sit inside a 2% per-trade rule, the trader would need
₹378,981 of capital.** Below roughly that, a percent-of-capital rule is not
strict — it is *unsatisfiable by any F&O position at all*.

If `max_position_size` were ever fixed to the correct unit **without** also
addressing this, the rule would flip from firing 0 times to firing **critical on
97% of trades**. That is measured, not projected:

| capital | 2% allows | over | critical |
|---|---|---|---|
| ₹50,000 | ₹1,000 | 98% | **97%** |
| ₹200,000 | ₹4,000 | 79% | 74% |
| ₹500,000 | ₹10,000 | 32% | 22% |
| ₹1,000,000 | ₹20,000 | 3% | 1% |

**P1 and P2 are therefore coupled, and fixing P1 alone would be actively
harmful.**

### P3. It is the largest single source of alerts in the engine

Under the real onboarded configuration at ₹50,000:

| | |
|---|---|
| raw detector events | **606** |
| after per-rule 24h dedup | **383** *(lower bound — `_worsened` re-arm not modelled)* |
| sessions producing an alert | **126 of 175 (72%)** |
| alerts on a firing session | mean **3.0**, max **8** |

**Every other detector in the engine combined fires 457 times on this book.** So
this one detector accounts for roughly **46% of all alerts**, at
`notification_level=4` — the highest in the system.

That is not obviously wrong: if a trader declares "stop after 3 consecutive
losses" and takes a 4th, that *is* a breach, and the copy is right that these
are their own numbers. **But it is a product question that has never been asked
explicitly**, and it is the same shape as the 54%-of-all-alerts figure that
caused `daily_loss_limit` to be pulled from `generate_defaults`.

### P4. The `suggested_*` keys have no readers

`generate_defaults` returns `suggested_daily_loss_limit` and
`suggested_max_position_size`. **Neither name appears anywhere else in the
backend or the frontend.** The mechanism intended to offer a money rule for the
trader to confirm was built and never wired, which is *why* the wizard's own
defaults ended up filling the gap (P2).

### P5. The cooldown rule spells CONCLUDED inline, as `<=`

```python
prior_losses = [t for t in ctx.session_trades
                if t.exit_time and t.exit_time <= ct.entry_time ...]
```

`EngineContext.concluded_before_entry` exists for exactly this and uses `<`.
Carried over from the temporal-contract work, where this detector was
deliberately left out of scope.

**Measured impact: 0.** The two predicates select different sets on **0 of 740**
trades — they can differ only when a close and an entry share a timestamp. It is
a consistency defect, not a live one.

### P6. `max_trade_risk`'s abstention is a `return`, not a `continue`

```python
if not rq.usable_for_capital_rules:
    logger.debug(...)
    return events or None
```

**Correct today**, because `max_trade_risk` is the last rule. But it is a
`return` from inside a rule block: any rule added after it would be silently
skipped whenever capital is not determinable — on 2% of trades today, and on
100% of them for an exchange the risk layer must abstain on (MCX, CDS, BFO).

### P7. Neither ladder constant has a `THRESHOLD_SPECS` record

`constitution_approaching_pct` (0.80) and `constitution_severe_pct` (1.20) are
the *only* numbers this detector chooses, and they exist solely in
`COLD_START_DEFAULTS` with no `Kind`, no provenance, no maturity.

**Eighth instance** of this class across the review sequence — and the one where
it matters most, because these two decide when a trader's own rule becomes a
`critical`, `guardian_eligible` alert.

### P8. Multi-rule firing is common and each event is a separate alert row

| rules on one trade | trades | share |
|---|---|---|
| 1 | 425 | 59% |
| 2 | 185 | 26% |
| 3 | 88 | 12% |
| 4 | 21 | 3% |
| 5 | 2 | 0% |

Per-rule dedup is the right call (P-correct above), but **41% of firing trades
breach more than one rule at once**, and nothing groups them into a single
"you broke 3 of your rules on this trade" statement.

---

## Evidence

| question | answer | strength |
|---|---|---|
| does it fire? | **606 raw / 383 deduped**, 126 of 175 sessions, at the real onboarded config | measured |
| share of all engine alerts | **~46%** (383 against 457 for everything else) | measured |
| does Pattern 4's behaviour land here? | **yes — 194** events at a declared limit of 3 | measured |
| does Pattern 15's behaviour land here? | **yes — 181**, exactly the figure that retirement cited | measured |
| does `max_trade_risk` work? | **no — 0 firings**; the wizard writes 50000 into a percent field | measured |
| would fixing that unit help? | **no — it would fire critical on 97% of trades** at ₹50k | measured |
| is a 2% per-trade rule satisfiable? | **not below ~₹379,000 of capital** (median requirement ₹7,580) | measured, n=724 |
| does the ladder distribute? | **yes** on the count rules; `daily_loss` is 74% critical | measured |
| does `<=` vs `<` bite? | **no — 0 of 740** | measured |
| how often does it abstain? | **16 of 740 (2%)** | measured |
| is it pure? | **yes** | verified |
| do the ladder constants have provenance? | **no spec for either** | verified |

**What the evidence cannot say.** Every number depends on which rules a trader
declared, and this book has no profile — so all of it is "what a trader with
*these* rules would have seen", not "what users see". The configurations are the
product's own, but a real population would spread across edited values. **The
structural findings (P1, P4, P5, P6, P7) do not depend on the configuration; the
volume findings (P2, P3, P8) entirely do.**

---

## Recommended behavioural contract

> **Subject.** The trader's own written rules, against what they actually did.
> Not our judgement of what a limit should be — theirs.
>
> **The rules it enforces must be ones a trader can keep.** A percent-of-capital
> per-trade rule that no single F&O lot can satisfy is not a discipline rule; it
> is a statement about account size, and enforcing it teaches the trader to
> ignore the alert.
>
> **One meaning per field, across every surface that writes it.** A field read as
> a percentage must not be written as rupees anywhere.
>
> **Suggested is not set.** A money rule offered for confirmation must not become
> an enforced rule by default, through any path.
>
> **Says nothing about intent.** It reports the number they wrote and the number
> they hit. The current copy already does exactly this.

---

## Exact changes required

**None inside this detector.** Its logic is correct, its abstention is right, its
dedup key is right, and its copy is the best in the engine. The defects are in
what it is *given* and in two pieces of plumbing.

Recorded for the consolidated pass, **P1+P2 together and first**:

1. **`max_position_size` units contradiction** (P1) — the wizard writes `50000`
   into a field the detector, `MyRules` and `generate_defaults` all treat as a
   percentage. One rule of six is inert.
2. **The wizard defeats the money-rule policy** (P2) — and **fixing 1 without 2
   flips `max_trade_risk` from 0 firings to critical on 97% of trades.** They
   must be decided together.
3. **`suggested_*` keys have no readers** (P4).
4. **The cooldown rule should read `concluded_before_entry`** (P5) — 0 measured
   impact; consistency only.
5. **The abstain `return` should not be able to skip a later rule** (P6).
6. **Neither ladder constant has a `THRESHOLD_SPECS` record** (P7).
7. **Multi-rule breaches are not grouped** (P8) — 41% of firing trades break more
   than one rule.

**No value is proposed for any of these.** In particular, nothing here suggests
what a per-trade risk rule *should* be for an F&O account — the measurement says
the current form is unsatisfiable below ~₹379k, not what to replace it with.

---

## Verdict — **KEEP AS-IS** (the detector), with P1+P2 flagged as the highest-priority input defect found in this review sequence

**Not DELETE, and not close to it.** Its subject is the trader's own declared
rules — the one subject in the engine that needs no behavioural evidence to
justify it. It is the sole home of two retired detectors' behaviour, and this
review reproduced both figures independently (194 and 181, the latter matching
Pattern 15's own number exactly).

**Not MODIFY.** Every defect worth acting on is upstream of the detector or is
plumbing: a units contradiction in the onboarding wizard, an unwired suggestion
mechanism, an inline `<=` with zero measured impact, a fragile `return`, and two
constants missing spec records. The rule logic itself is sound and the "one away"
fix is the most carefully reasoned piece of threshold work in the codebase.

**Not RESEARCH FURTHER.** The measurements that matter are done, and what they
turn on — which rules a trader declared — is not a research question.

**Not DEFER.** It is live, it is the largest alert source in the engine, and the
input defects are actionable now.

**Two things must not be lost from this review:**

**`max_trade_risk` is silently dead in production** and has been for as long as
the wizard has shipped `50000`. It is one of six rules, it is the only one that
speaks to position size, and no test or alert would ever have revealed it —
a rule that fires zero times looks exactly like a trader with good discipline.

**And it must not be "fixed" on its own.** Correcting the unit without deciding
the F&O question would turn a silently dead rule into a `critical`,
`guardian_eligible` alert on 97% of trades — which is precisely the failure
`generate_defaults` already documents and deliberately avoids for
`daily_loss_limit`. That is the single most consequential finding in this review
sequence so far, and it belongs to onboarding, not to this detector.
