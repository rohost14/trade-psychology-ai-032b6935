# Pattern #1 — `martingale_behaviour`

24 Aug 2026. **Review only. No code changed, no threshold added or retuned, no
detectors merged, no architecture touched.**

**Verdict: MODIFY** — the alert states three things the trades often do not show.
The correctness fix is separable from the sensitivity question, and the
sensitivity question is **RESEARCH FURTHER**, not settled here.

---

## 1. What this is supposed to detect

A martingale is a betting system: after a loss you raise the stake so that one
win recovers everything lost. In trading, the analogue is raising position size
on the trade taken **after** a loss, because that trade now has to carry the
previous one as well as itself.

The mechanism is documented and specific — Thaler & Johnson's **break-even
effect** (1990): after a loss, people prefer gambles that offer a chance to
return to the reference point, and will accept worse odds to get it. The
observable consequence is not "size drifts up during a bad patch" but
**"the size of the position taken after the loss is larger than the one that
lost."** The step the trader took is the behaviour.

The detector's own docstring says the same thing in the same words:
*"I lost, so I'll go bigger"* … *"a real tradebook shows people rotating
instruments while escalating."* Its message says
*"Each loss was followed by a larger position."*

## 2. What the implementation actually does

`behavior_engine.py:_detect_martingale_behaviour`

1. Requires ≥3 trades in the session.
2. Takes the **last 3 prior trades on the same underlying**. If fewer than 2
   exist, falls back to the **last 3 of the session** and sets
   `cross_instrument = True`, which switches the size measure from **quantity**
   to **notional rupees**.
3. `loss_count` = how many of those priors lost. Requires
   `>= martingale_min_losses` (2).
4. `max_ratio` = the largest step-up **between two consecutive priors**.
5. `>= martingale_danger_multiplier` (2.0) → **danger**; `>= caution` (1.5) →
   **caution**.
6. The message prints `priors + current` as one sequence, correctly labelled
   `₹` when cross-instrument.

**The current trade is displayed but takes no part in any decision.** It is not
required to be larger, and it is not required to be a loss.

| input | value | classification | reader |
|---|---|---|---|
| `martingale_min_losses` | 2 | **unclassified** | this detector only |
| `martingale_caution_multiplier` | 1.5 | **unclassified** | this detector only |
| `martingale_danger_multiplier` | 2.0 | **unclassified** | this detector only |
| `_notional` | `qty × avg_entry_price` | shared static method | 4 detectors |

**User-declared / onboarding values consumed: none.** The registry spec sets
`uses_baseline=False`, `uses_constitution=False`, `uses_position_state=False`,
and the code reads no profile field. Nothing in My Rules reaches this detector,
and no constitution rule is paired with it in `_CONSTITUTION_PAIRS`.

**Severity** caution / danger. **Confidence** not set (`None`). **Evidence /
abstention** none — returns a `DetectedEvent`, not a `DetectorResult`, so it
cannot say "I could not tell". **Notification level 2** → a danger firing is a
push.

## 3. Are the values justified?

| value | verdict | reasoning |
|---|---|---|
| `martingale_min_losses = 2` | **Definitional — KEEP.** | You cannot have a progression from one loss. This is what the word means, not a sensitivity setting. |
| `1.5` / `2.0` multipliers | **Defensible as ratios; the operand is the problem.** | A multiple is scale-free and cannot be gamed by account size — the failure that killed `revenge_min_loss_inr` cannot happen here. Neither number is derived from anything, but no evidence in this review says either is wrong. **What they are applied to is wrong (§4).** Retuning them is not proposed. |
| quantity → notional switch | **Record, do not change.** | 32 of 58 firings (55%) run on rupees. Unlike `size_escalation`, martingale **labels the units correctly** in its message. A 2× is a 2× in either unit, so this is not obviously wrong — but the context dict does not record which unit was used, so a reader cannot tell. |

## 4. Evidence — replay, 175 sessions, 742 round-trips

Method: the **real detector method** was run against the replay's own per-trade
data, offline, with session state rebuilt the way `_load_context` builds it
(`session_trades = trades[:i]` in exit order). No logic was reimplemented — the
engine's own code decided. 58 raw detections across 33 days; the replay's 36
alerts on 32 days are the same detections after dedup and the session cap.

### 4a. The alert states three things. Each is often false.

| the message says | how often it is false | measured |
|---|---|---|
| "after **consecutive** losses" | **23 of 58 (40%)** | fewer than 2 *trailing consecutive* losses among the priors — the code counts any 2 of the last 3, which is not the same thing. 13 firings had **zero** trailing consecutive losses |
| "each loss was followed by a **larger** position" | **29 of 58 (50%)** | the current position is **smaller** than the one immediately before it |
| implied: this trade is the escalation | **26 of 58 (45%)** | the current trade was a **winner** |
| **at least one of the three is false** | **46 of 58 (79%)** | |
| all three true *and* the current trade ≥1.5× the previous | **11 of 58 (19%)** | |

### 4b. The clearest case

```
2025-08-21  NIFTY   sizes 75 → 150 → 375 → 75
            priors  −₹296, −₹1,065, −₹581      current  +₹1,102
            max_ratio 2.5  →  DANGER  →  push notification
```

The trader escalated 75 → 150 → 375 across three losses, **then cut back to 75
and won ₹1,102.** The alert fires on the trade that *ended* the martingale, and
tells them "Each loss was followed by a larger position."

Eleven firings have that exact shape: danger severity, current position smaller
than the previous one, current trade profitable.

### 4c. False negatives — it misses the events it was built for

Applying the detector's **own** multiples (1.5 / 2.0) to the step the trader
actually took — previous trade → current trade, after two consecutive losses:

**22 sequences the detector misses. 18 of them at ≥2.0×. Across 21 days.**

```
2026-01-05  CIPLA       ₹9,864 → ₹5,73,750   58.2×   after −35, −439     −₹1,650
2025-08-07  CDSL        ₹2,794 → ₹13,466      4.8×   after −619, −499    −₹1,069
2025-08-13  NIFTY        75 → 300 lots        4.0×   after −405, −668    −₹4,545
2026-02-27  NIFTY        65 → 195 lots        3.0×   after −283, −390    −₹7,072
2025-11-06  SENSEX       20 → 60 lots         3.0×   after −262, −275    −₹1,404
```

The last two are among the worst single trades in the book. **The detector is
silent on them and fires instead on trades that de-escalated.**

### 4d. Does the behaviour exist at all? Post-win control

The detector's exact claim, tested with the control this project uses
throughout — the same measurement after two consecutive **wins**:

| step-up | after 2 losses | after 2 wins | diff | noise (SE) |
|---|---|---|---|---|
| any increase | 62.9% | 56.5% | +6.4pp | 6.8 |
| ≥1.25× | 34.1% | 32.9% | +1.1pp | 6.6 |
| ≥1.5× | 25.0% | 28.2% | **−3.2pp** | 6.1 |
| ≥2.0× | 19.7% | 21.2% | **−1.5pp** | 5.6 |
| ≥3.0× | 9.8% | 12.9% | **−3.1pp** | 4.4 |

n = 132 after two losses, 85 after two wins. Median step is **1.0 in both**.

**At every multiple the detector actually uses, stepping up after two losses is
no more likely than after two wins — and slightly less likely.**

This does **not** say martingale never happens: 75 → 150 → 375 is real and the
trader would recognise it. It says **stepping up is not specific to losses for
this trader**, so a trigger conditioned on losses-plus-step-up will catch
ordinary sizing variation at about the same rate as loss-chasing.

**Observability limits, stated plainly.** One trader, one year. SE ≈ 6pp, so a
difference smaller than roughly 12pp is undetectable here. Position size is
observable and reliable; *why* it changed is not, and no fill data will supply
it. This is the same wall the revenge research hit
(`REVENGE_FINAL_EVIDENCE_REVIEW.md`, AUC 0.482), and the two results agree:
signature 2 there — "loss → larger next position" — measured +1.7pp at 4.2 SE.

## 5. Overlap and whether the alert is meaningful

Other detectors firing on the **same trade**:

| detector | co-fires | survives consolidation? |
|---|---|---|
| `same_symbol_obsession` | **25 of 58 (43%)** | **Yes — different family.** Both alert |
| `size_escalation` | 14 of 58 (24%) | No — same family, martingale wins |
| `post_loss_recovery_bet` | 6 of 58 (10%) | No — same family, martingale wins |

The family machinery works for two of the three. **`same_symbol_obsession` is in
the "going back to the same trade" family, martingale is in "sizing after
losses", so on 43% of firings the trader receives both** — two alerts describing
one session on one instrument. Recorded for the `same_symbol_obsession` review
(Pattern #2), which is next and should decide it.

**Is the alert meaningful to a trader?** As written, on 79% of firings it makes a
statement the trader can check against their own screen and find wrong. That is
worse than silence: the philosophy is "mirror, not blocker", and a mirror that
shows something that did not happen costs the credibility of every other number
in the product.

## 6. Performance and purity

**Pure — proven, not asserted.** This review ran the detector 742 times with **no
database connection at all**. It reads only `ctx`; the one import inside the body
(`parse_symbol`) is a module lookup. No DB access, no external calls, no I/O.

**Cost** two sorts of at most the session's trades, then O(1) arithmetic over at
most 3 priors. Negligible on the hot path, and it does not grow with session
length in any way that matters.

**No change recommended here. KEEP AS-IS.**

## 7. Verdict — **MODIFY**

Not DELETE: the behaviour is real when it happens, individual sequences are
factual and recognisable, and a mirror does not need predictive power to be
honest. Not KEEP AS-IS: 79% of firings contain a false statement. Not DEFER: the
false statements are provable now and do not need more evidence.

The sensitivity question — *should this alert at all, given the post-win
control?* — is **RESEARCH FURTHER** and is not answered by this review.

### Recommended behavioural contract

> **`martingale_behaviour` reports one fact: the position taken after a run of
> losses was materially larger than the position that just lost.**
>
> - The unit of measurement is **the step the trader took** — previous trade to
>   current trade — because that is the decision the behaviour names.
> - It requires losses that are **consecutive**, because that is what the word
>   and the message both claim.
> - It does not fire when the current position is not larger, because there is
>   then no escalation to report.
> - It states what happened. It does not claim what will happen: the post-win
>   control gives no basis for a predictive claim.

### Exact changes required — for approval, not implemented

| # | change | why | effect |
|---|---|---|---|
| 1 | `max_ratio` measures **previous → current**, not the largest step among priors | the step the trader took is the behaviour; §4b shows the current form fires on de-escalation | 29 firings that de-escalated stop; 22 real escalations start |
| 2 | require the losses to be **trailing consecutive**, not any 2 of the last 3 | the message and docstring both say "consecutive" | removes the 23 firings where it was not true |
| 3 | do not fire when the current position is not larger than the previous | follows from 1; no separate rule | — |
| 4 | record `cross_instrument` in context, as `size_escalation` now does | a reader cannot currently tell lots from rupees | none |
| 5 | message may not say "each loss was followed by a larger position" unless it was | it is checkable and often wrong | none |

**No threshold is added, removed or retuned.** `min_losses` stays 2, the
multiples stay 1.5 and 2.0. Only the operand and the loss condition change.

**Measured effect of 1 + 2 together:** 58 firings across 33 days → **33 firings
across 28 days** (26 danger, 7 caution). 11 of today's firings are retained, 47
stop, 22 start. Replay is a mandatory gate before any of this ships.

**Not proposed, deliberately:** any change to the multiples, personalising them,
merging with `size_escalation` or `post_loss_recovery_bet`, or adding a
confidence or abstention path. Each needs its own evidence.

### Recorded for later reviews, not fixed here

- `same_symbol_obsession` co-fires on 43% of martingale firings and survives
  consolidation → **Pattern #2**.
- The three constants are unclassified in `threshold_registry`; classifying them
  is a claim about their kind and belongs with change 1, once the operand is
  settled.
- `_notional` is shared by four sizing detectors with four different rules for
  when to switch to it → the sizing-family review.
