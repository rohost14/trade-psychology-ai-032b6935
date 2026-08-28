# Pattern #11 — follow-up: can it distinguish flipping from a change of view?

28 Aug 2026, requested before implementing. **It cannot — and what it selects
looks like good decision-making.** This reverses the review's MODIFY
recommendation. No code changed.

---

## A. Every CE↔PE transition on one underlying, classified

| kind | n | detector |
|---|---|---|
| **simultaneous** — legs overlap (hedge / structure) | 10 | excluded, negative gap ✅ |
| **rapid** — sequential, gap < 10 min | **16** | **FLAGGED** |
| **slow** — sequential, gap ≥ 10 min | 48 | not flagged |

74 transitions total; **0** had a non-LONG leg, so Level 2's both-LONG condition
excludes nothing here. The hedge/structure case is handled correctly and twice
over — `_STRATEGY_SUPPRESSED` plus the negative-gap rule.

**So the only thing separating a flagged flip from an unflagged one is the
clock.** 48 of 64 sequential transitions are excluded purely by elapsed minutes.

## B. The clock separates — in the wrong direction

| | n | win rate | mean P&L |
|---|---|---|---|
| **FLAGGED** — the flip trade, gap < 10 m | 16 | **56.2%** | **+₹276** |
| not flagged — same transition, gap ≥ 10 m | 48 | 41.7% | −₹73 |
| simultaneous legs (hedge/structure) | 10 | 40.0% | −₹340 |

diff +₹349/trade, p = 0.383. **The trades it flags do better than the ones it
ignores**, and better than the book's ~40% win rate.

The trade being reversed *out of* explains why:

| | n | win rate | mean P&L |
|---|---|---|---|
| FLAGGED prior | 16 | **31.2%** | **−₹284** |
| not-flagged prior | 48 | 54.2% | +₹35 |

**The trader reverses fast when the position went badly, slowly when it did
not.** That is what cutting a loser looks like.

## C. Repeated flipping — sessions end BETTER

| flips in session | days | mean trades | mean session P&L |
|---|---|---|---|
| 0 | 179 | 4.7 | **−₹863** |
| 1 | 6 | 7.2 | **+₹1,900** |
| 2+ | 4 | 7.2 | +₹411 |

Flip sessions are longer, so controlling for the position-in-session confound
against no-flip sessions in the same 2–11 trade band:

| | n | win rate | mean |
|---|---|---|---|
| sessions **with** a flip | 10 | 60.0% | **+₹1,305** |
| no-flip, same trade-count band | 156 | 42.9% | −₹860 |

diff **+₹2,165/session, p = 0.129**.

**Deterioration test** — rest of session after the first flip, against the same
trade index in a matched no-flip session:

| | n | mean rest-of-session |
|---|---|---|
| after the first flip | 10 | **+₹953** |
| matched index, no flip | 159 | −₹112 |

diff **+₹1,065, p = 0.095**. The premise is that behaviour deteriorates after a
flip. Measured, it **improves** — and this is the closest any test came to
significance.

## D and E. No escalation story either

Flip after a loss: **+₹37** (n=11). After a win: **+₹802** (n=5). Both positive.

Size ratio flip ÷ prior: flagged **median 1.03**, larger in 8 of 16; not-flagged
median 0.76. A flagged flip is **flat-sized**, so "reversing while sizing up" is
absent.

## F. Overlap — the majority are already alerted

Of the 18 firings, on the **same trade**:

```
revenge_trade                10 / 18
options_premium_avg_down      7 / 18
same_symbol_obsession         6 / 18
martingale_behaviour          1 / 18
```

**`revenge_trade` fires on the majority.** The "reversed emotionally after a
loss" reading is already owned by a detector with its own severity — and
`revenge_trade` is FROZEN by decision, so this pattern adds a second alert to a
story the engine has already decided how to tell.

---

## What this changes

The review said the evidence was insufficient and nothing pointed the wrong way.
**With the discrimination test run, something does.** Five independent measures —
flip-trade outcome, prior-trade outcome, session P&L, matched rest-of-session,
size ratio — all point the same way: the flagged behaviour is **cutting a loser
and taking the other side**, and it travels with this trader's better sessions.

None reaches p < 0.05 at n=16. The pattern of signs is what matters, and it is
the same argument that retired Patterns 4, 6 and 10 — with the sign now *against*
the detector rather than merely absent.

**An alert that fires on good decisions is worse than one that fires on noise.**
A useless alert costs attention; this one would coach the trader away from the
few fast reversals that worked, under the label *"Direction flip-flop"* and the
explanation *"reversing repeatedly usually tracks the price rather than a view
about it"* — which this book contradicts.

## Registry audit (no changes made)

1. **`rapid_flip_min`** — `Kind.PERSONAL_BASELINE`, `Source.SESSION`, metric
   `flip_interval_p25`, **0 producers**. Permanently resolves to the hardcoded
   10. A false declaration.
2. **`direction_confusion_window_min`** — absent from `threshold_registry`
   entirely, despite being one of the two values that decide every firing.

Both are moot if the detector is deleted, and not worth a separate change if it
is kept — see the sweep below.

---

## Verdict — DELETE

Changed from the review's MODIFY, on the discrimination evidence.

1. **It cannot distinguish** a legitimate change of view from an emotional one.
   Its only discriminator is a 10-minute clock; the hedge/structure case was
   already excluded by other means.
2. **The subset it selects performs better**, not worse, on every measure —
   including a near-significant *improvement* in rest-of-session (p = 0.095)
   where the premise predicts deterioration.
3. **What it flags reads as risk management**: prior −₹284 at 31% win, reversed
   within minutes, flat size, next trade +₹276 at 56% win.
4. **`revenge_trade` already fires on 10 of 18**, so the emotional reading is
   covered where it belongs.
5. **Level 1 remains untestable** here (911 LONG vs 1 SHORT). Deleting loses an
   unmeasured branch — the honest cost, recorded rather than argued away.

**If you would rather keep it for other trading styles, the alternative is
RESEARCH FURTHER, not KEEP.** It should not ship as-is while its own book says
the behaviour helps. Deciding it properly needs a futures or option-seller book,
which we do not have.

**Recommended alongside either choice:** one **registry-wide sweep** for
`PERSONAL_BASELINE` specs whose metric has no producer — now four for four (P7
`fomo_underlyings_*`, P9 `expiry_day_trades_*`, P10 unregistered, P11
`flip_interval_p25`). Fixing them one pattern at a time is the expensive way.
