# v2 episode model — falsification review

24 Aug 2026. **Analysis only. No code, no thresholds, no implementation.**

Both v2 claims are treated as **hypotheses**, not settled:

- **H1** — an episode is an open mental account on one instrument.
- **H2** — genuine loss-chasing shows as ≥3 attempts with growing exposure.

The 40-session evidence supporting H2 is six observations. This document tries to
break both, then compares the three candidate directions.

---

## Part 1 — Legitimate behaviour that would trigger the episode model

Each is a strategy a competent trader runs on purpose. All would open, continue
and escalate an episode.

### 1.1 Averaging down / scaling in — **the most serious**

A trader who plans three tranches into one contract, adding as it moves against
them, produces **exactly** the H2 signature: same instrument, ≥3 attempts,
growing exposure, each earlier leg realized at a loss.

This is not a marginal case. Scaling into a position is a mainstream technique,
taught, and deliberate.

**Why it is worse than v1's false positives.** v1's FPs were single fast
re-entries into unrelated instruments — visibly weak evidence. This one is
*indistinguishable at the structural level*, because the structure is genuinely
identical. Only the intent differs, and intent is not observable.

**Partial defences, none sufficient**

| defence | why it does not settle it |
|---|---|
| `options_premium_avg_down` already describes this | it describes it; it does not distinguish planned from reactive |
| A planned scale-in is usually pre-sized | not recorded anywhere — no plan exists in the data |
| Ask the trader once, in Rules | plausible, and the only real answer. Post-hoc marking has zero adoption; onboarding-time declaration does not |

### 1.2 Pyramiding into a winner that dips

Add on a pullback, the pullback deepens, one leg is stopped for a loss, they add
again at a better price. Same instrument, growing exposure, ≥3 legs. Textbook
trend-following.

**Distinguishing feature that might survive:** the *session* is profitable. In our
genuine cases the session P&L was deeply negative throughout. That is observable —
but it is also close to being a magnitude gate in disguise, and §1 of the previous
review forbade exactly that. Flagged, not proposed.

### 1.3 Delta hedging and roll management

An options seller rolling a threatened strike realizes a loss on the old leg and
opens a new one on the **same underlying**, often larger. Repeatedly, on the same
underlying, through the session.

Strategy-group suppression catches this only when the legs are detected as a
structure. A roll executed as two separate orders minutes apart may not be.

### 1.4 Expiry-day scalping on one index

On expiry the liquid contracts are few. A trader working NIFTY weekly options all
afternoon will re-enter the same underlying constantly, and losses interleave with
wins. Our own book: expiry losses run **2× deeper** (median 21% vs 10%) and B3's
expiry share was **60%**.

The episode model keys on the *underlying*, and on expiry day a trader may have
only one. **This is a structural concentration risk the model does not address.**

### 1.5 The market genuinely moving

A trend day in NIFTY: a trader is stopped out, re-enters as the trend resumes,
adds as it runs. Losses early, growing exposure, one instrument. Correct trading.

### 1.6 Two strategies on one underlying

A trader running an intraday scalp *and* a positional view on NIFTY generates
interleaved trades on one underlying from two unrelated decision processes. The
model would chain them into one episode. **Nothing in the data separates them.**

---

## Part 2 — Genuine loss-chasing the model would miss

### 2.1 Rotation revenge — **the largest gap**

Loses on NIFTY, immediately trades BANKNIFTY bigger, loses, moves to SENSEX
bigger. Textbook chasing — and the episode model **never opens**, because H1 keys
on one instrument.

**This directly contradicts H1.** Mental accounting predicts instrument-specific
accounts, but the *account* a trader keeps may be **the session's P&L**, not the
instrument's. Many traders think in "I'm down ₹8,000 today", not "I'm down on that
contract".

Our own book contains a candidate: **02-02** — lost 162% of SPAN on VBL, re-entered
BDL (different underlying) four minutes later. Classified ambiguous precisely
because the structure carried nothing. Under v1 it was B1. Under v2 it is
**nothing at all** — the model is strictly *worse* here.

### 2.2 Same-size revenge

Returns to the same contract immediately, repeatedly, at the **same** size. Real
chasing; no escalation, so H2's second condition never fires. Our three ambiguous
cases are exactly this shape, and at least one may be genuine.

### 2.3 Revenge by holding

Refuses to cut the next loser, holding it far longer than usual to avoid booking
a second loss. No re-entry at all — the episode never opens. The literature's
**disposition effect** predicts this is common, and it is arguably the *same*
underlying impulse.

### 2.4 Next-day revenge

Loses heavily Friday, opens Monday at triple size. The session-bounded episode
cannot see it. Whether the account survives overnight is an open empirical
question the model simply asserts away.

### 2.5 Revenge that stops at two

Loses, re-enters bigger, loses bigger, stops. Two attempts — below H2's line. The
trader may have stopped *because* the second loss was severe, which is the
outcome we most want to interrupt before it happens.

**H2's "≥3 attempts" means the model cannot fire until the third trade** — after
two losses have already been taken.

---

## Part 3 — What survives

| claim | status |
|---|---|
| Realized loss is the trigger, not paper loss | **survives** — theory and mechanism both support it |
| A win in the instrument closes the account | **survives** — observed in 2 of 3 genuine sessions |
| Episodes are session-bounded | **assumed, untested** — 2.4 is unaddressed |
| **H1** one instrument = one account | **damaged** — 2.1 is a real and common pattern the model cannot see |
| **H2** ≥3 attempts + growing exposure | **damaged** — 1.1 is structurally identical legitimate behaviour; 2.2 and 2.5 are misses |

**Neither hypothesis should be frozen.** H1 is probably *a* mechanism rather than
*the* mechanism, and H2 is a description of three sessions in one book.

---

## Part 4 — The three directions compared

| | episode detection | distributional mirror | mirror first |
|---|---|---|---|
| Needs a threshold | yes (attempt count) | **none** | none |
| Needs personal maturity | no | **yes** | yes |
| Works at cold start | yes | no | no |
| Real-time | yes | no | no |
| False positives | **1.1 unresolved** | n/a — makes no claim | n/a |
| Misses | 2.1–2.5 | n/a | n/a |
| Evidence supporting it | 6 observations | the entire literature | as mirror |
| Can be validated now | **no** — needs `heeded` | **yes** — self-consistent statistics | yes |
| Generates evidence for the other | no | **yes** | **yes** |

### Why the mirror is stronger than it looks

It is the only option that **cannot be wrong about a trade**, because it makes no
per-trade claim. *"After a loss you re-enter in 4 minutes; after a win, 21"* is
arithmetic on that trader's own record.

It is also the only one that **directly measures what the research measures** — a
within-person distribution shift, post-loss versus post-win. Every falsification
in Parts 1 and 2 attacks a *classification*. None of them touches a statistic.

And it answers 2.1, 2.2 and 2.3, which the episode model cannot: rotation, flat-size
repetition and holding all show up as distribution shifts without needing to be
labelled.

### What the mirror cannot do

Interrupt anything in the moment. It is a report. If the product's value is
converting an automatic action into a deliberate one *while it is happening*, the
mirror does not do that — it changes what the trader knows before tomorrow.

---

## Part 5 — Recommendation

**Ship the mirror first. Do not build episode detection yet.**

1. It needs **no threshold, no episode model, no new architecture** — only
   baselines that already exist.
2. It is **validatable now**, against the trader's own record, with no `heeded`
   data.
3. It **generates exactly the evidence the episode model lacks.** After a month it
   can answer: how often does this trader re-enter the same instrument after a
   loss; does exposure actually grow; is rotation more common than repetition —
   which is H1's central question and currently unanswered.
4. Every falsification above attacks classification. **None of them lands on a
   statistic.**
5. It fits the product philosophy without straining: *mirror, not blocker*.

**What I would not do:** freeze "≥3 attempts + growing exposure", build an episode
state machine, or treat the one-instrument account as architecture. On the
evidence, H1 is one plausible mechanism among at least two, and the alternative —
a session-level P&L account — is equally consistent with the literature and would
produce a different detector.

**What would change my view:** the 203-session data now being collected. If
episode candidates are rare and cluster on losing sessions, H2 strengthens. If
they are common and appear on profitable sessions, 1.1 and 1.2 are confirmed as
dominant and the episode model is not viable as an alert.
