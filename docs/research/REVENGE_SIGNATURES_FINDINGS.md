# Fifteen loss-chasing signatures, measured across the full book

24 Aug 2026. **Research only. No engine code changed, no threshold created, no
rule proposed.** The frozen `revenge_trade` detector is untouched.

**Observable loss-chasing behaviour is not proven revenge trading.** Everything
below is about observable behaviour. Nothing here labels intent.

---

## Method — why there are no thresholds in this document

Every signature is measured **after a loss** and **after a win**, and the
post-win rate is the control.

That is what makes the analysis threshold-free. "Unusually fast re-entry" has no
person-independent definition — the same problem that refuted S2a — but *"faster
than this same trader after a win"* is answerable from the data with no constant
invented anywhere. If a behaviour follows losses and wins at the same rate, it is
how this trader trades, not how they react to losing.

**Book:** 175 sessions with at least one completed round-trip, 742 round-trips,
435 losses, 326 losses followed by another trade.

*(The familiar "203 sessions" counts every trading date in the tradebook. The
other 28 days carry 1–4 fills each, one-sided or carry-overs on different
symbols, so no same-day round trip can exist. Not dropped data — the two
collectors simply counted different things.)*

## The result, in one table

| # | signature | after loss | after win | diff | noise (SE) |
|---|---|---|---|---|---|
| 1 | re-entry faster than session median | 40.7% | 40.0% | +0.7pp | 4.7pp |
| 2 | next position larger (qty) | 41.1% | 39.4% | +1.7pp | 4.2pp |
| 3 | next position higher risk | 49.1% | 43.2% | **+5.9pp** | 4.2pp |
| 4 | same underlying | 31.9% | 33.6% | −1.7pp | 4.2pp |
| 5 | same underlying and direction | 31.0% | 33.2% | −2.2pp | 4.2pp |
| 6 | different instrument, larger risk | 34.0% | 30.7% | +3.3pp | 4.0pp |
| 7 | 3+ trades within 30 min of the exit | 4.9% | 5.8% | −0.9pp | 1.9pp |
| 9 | rest of session negative | 58.3% | 53.9% | +4.3pp | 4.2pp |
| 10 | next qty above session median | 29.4% | 30.7% | −1.3pp | 4.0pp |
| 14 | next trade's risk ≥ the loss taken | 97.5% | 95.6% | +1.9pp | 1.3pp |

**Not one signature clears 1.5 standard errors.** The largest, S3, is 1.4 SE.
Median re-entry gap is 12.6 min after a loss and 16.5 min after a win — a
difference in the expected direction, and inside the noise.

Signatures 8, 11, 12, 13, 15 are not rates and are reported individually below.

## Signature by signature

**S1 fast re-entry — likely normal.** +0.7pp, 0.1 SE. This trader re-enters at
much the same speed whether the last trade won or lost.

**S2 larger position / S10 above-normal size — likely normal.** +1.7pp and
−1.3pp. Size after a loss is indistinguishable from size after a win.

**S3 higher risk — ambiguous, the single best candidate.** +5.9pp at 1.4 SE. It
is the only signature pointing the right way with any weight behind it, and it is
also the one measure H2 got wrong (below). Not evidence yet; the most defensible
thing to collect more of.

**S4/S5 same instrument, same direction — likely normal, and S5 is degenerate.**
Both slightly *negative*: this trader is marginally more likely to return to the
same underlying after a **win**. And S5 cannot carry information in this book at
all — **727 of 742 round-trips are LONG** (494 CE, 230 PE). "Same direction" is
nearly always true regardless of what happened.

**S6 rotation into a different instrument with larger risk — ambiguous, weak.**
+3.3pp, 0.8 SE.

**S7 frequency burst — likely normal, arguably contrary.** Median trades within
30 minutes of an exit is 1 after a loss and 1 after a win; the 3+ rate is
*lower* after a loss.

**S8 repeated recovery attempts — real, frequent, and the most promising unit.**
Loss-run lengths: `{1: 125, 2: 65, 3: 32, 4: 11, 5: 5, 7: 1, 8: 1}` — **50 of 240
runs reach 3 or more.** Unlike every rate above, this is not diluted by a control,
because a run of consecutive losses has no post-win counterpart. It is also the
only signature that is naturally *session-level*.

**S9 session deterioration — ambiguous, and probably an artefact.** 58.3% vs
53.9%, 1.0 SE. Median rest-of-session P&L is −₹386 after a loss and −₹130 after a
win. The rest of the session is negative more often than not in **both**
branches, which says more about the book's overall edge than about reacting to a
loss.

**S11 combinations — no compounding.** Co-occurrence of {fast, larger, same
underlying, same direction}: 4-of-4 in 3.4% after a loss vs 1.7% after a win
(n = 11 vs 4), but 3-of-4 is *lower* after a loss (15.6% vs 17.8%). Stacking
these signals does not sharpen anything — consistent with the standing position
that counting signals is a weighted score with all weights set to one.

**S12 next-day chasing — contrary evidence.** After a losing day: 100 sessions,
median 3 trades. After a winning day: 74 sessions, median **4** trades. Median
first-trade size is identical (325). This trader trades *less* the day after a
loss, not more.

**S13 abandoning stops — UNOBSERVABLE. Settled; do not re-attempt.** The tradebook
CSV has no order-type column and the replay never sets one, so `exit_order_types`
is empty for all sessions — the only field `_detect_no_stoploss` reads. Needs live
order data.

**S14 recovery-target sizing — a tautology, not a signature.** 97.5% vs 95.6%,
because **median next-trade risk is 12.3× the loss just taken** (p10 is 3.0×).
Capital deployed is almost always larger than one trade's P&L. The question was
malformed; discard it.

**S15 rotation revenge — likely a false positive.** Three different underlyings
with rising risk: **14 sequences starting from a loss, 12 starting from a win.**
The pattern exists and is visually compelling — 2025-11-26 CONCOR → UNITDSPR →
PGEL, ₹5,938 → ₹8,600 → ₹17,255, ending −₹2,520 — but it is almost as common
after winning trades. This is what a portfolio rotation looks like, not what
revenge looks like.

## The 14-episode problem — resolved

H2 (≥3 attempts + exposure grew) fired on 14 sessions. Two reasons, one of them a
defect in H2's own evidence.

**1. `exposure_grew` was computed on quantity, not capital at risk.**

```python
"exposure_grew": any(b > a for a, b in zip(qtys, qtys[1:]))
```

For options quantity is not exposure. **2025-07-28 SENSEX: 5 attempts, quantity
flat at 20 throughout, capital at risk 593 → 5600 (9.45×), −₹3,605** — recorded
as `exposure_grew: False`.

| exposure measure | flagged | H2 (≥3 attempts) |
|---|---|---|
| quantity growth (as measured) | 32 / 92 | **14** |
| any risk step-up | 54 / 92 | 17 |
| risk higher at end than start | 47 / 92 | 10 |

**Switching to risk is not a fix, and no binary is.** "Any step-up" fires on
9845 → 9940 — a different strike, not an escalation. Max single-step risk
multiple across the 92 episodes: **p50 1.03× · p75 1.43× · p90 2.97× · p95 4.09×
· max 9.45×.** One continuous tail with no gap to place a cut in. Same shape that
refuted S2a.

**2. The attempt count is the larger filter.** 71 of 92 candidates have exactly
two attempts, so `≥3` discards 77% before exposure is even consulted.

**3. The same-instrument restriction is not the culprit.** Episodes chain by
underlying, but S4 shows returning to the same underlying is *not* elevated after
a loss (31.9% vs 33.6%), and S15 shows cross-instrument rotation is near-identical
after wins. Relaxing this would add candidates without adding signal.

**4. A timing assumption that does matter: trades overlap.** The next entry
happens **before** the previous exit in **17.8% of post-loss cases** (25.3% after
wins). A model that reads "loss → next trade" as a reaction cannot apply when the
position was already open. Any episode definition built on sequencing is
undefined for roughly a fifth of the book.

**And escalation does not predict loss here:** 6 of the 10 largest escalations
ended in a win; 8 of the 14 H2 firings ended in a win.

## Personal ground truth — candidates, deliberately unlabelled

**No labels have been assigned.** These are cases where the observables are most
extreme in each direction, so the trader's own recollection is worth the most.
Group D matters as much as Group A: if the trader recalls revenge on days where
the engine saw nothing, the observables are wrong, not the trader.

### Group A — largest exposure escalation after a loss

| date | underlying | attempts | capital at risk | step-up | episode / session P&L |
|---|---|---|---|---|---|
| 2025-07-28 | SENSEX | 5 | 593 → 5600 → 605 → 685 → 749 | 9.4× | −3,605 / −3,405 |
| 2025-11-06 | SENSEX | 2 | 1,232 → 7,404 | 6.0× | −1,679 / −4,828 |
| 2025-05-20 | VOLTAS | 2 | 777 → 4,005 | 5.2× | −532 / −6,376 |
| 2025-09-09 | NIFTY | 3 | 679 → 3,101 → 2,531 | 4.6× | −1,245 / −2,967 |
| 2026-02-04 | SENSEX | 3 | 3,440 → 2,867 → 11,700 | 4.1× | +842 / −2,222 |

### Group B — longest consecutive-loss runs

| date | run | underlyings | losses | session P&L |
|---|---|---|---|---|
| 2025-09-16 | **8** | CONCOR, NIFTY, DALBHARAT, NIFTY ×5 | 62, 338, 1999, 956, 1114, 165, 2228, 1316 | −5,495 |
| 2025-08-13 | **7** | HAL, NIFTY ×5, BAJFINANCE | 405, 668, 4545, 420, 338, 281, 225 | −6,548 |
| 2026-01-05 | 5 | NIFTY, EXIDEIND, SIEMENS, NIFTY, CIPLA | 1573, 1080, 35, 439, 1650 | −4,139 |
| 2025-11-17 | 5 | BAJAJ-AUTO, IREDA, BAJAJ-AUTO, MAZDOCK, OIL | 345, 345, 416, 1050, 490 | −2,252 |
| 2025-11-20 | 5 | IREDA, KPITTECH, SUZLON, COLPAL, BIOCON | 414, 620, 960, 900, 1250 | **+165** |

2025-11-20 is deliberately included: five straight losses on a session that
finished **positive**. If the trader recalls that day as revenge, outcome is not
the signal.

### Group C — worst single losses and what followed

| date | loss | → next | risk change | gap | rest of session |
|---|---|---|---|---|---|
| 2025-11-25 | 8,835 NIFTY | PRESTIGE | 16,241 → 8,550 | overlapping | +382 |
| 2026-02-06 | 4,579 NIFTY | COALINDIA | 23,484 → 5,265 | overlapping | −878 |
| 2025-08-13 | 4,545 NIFTY | NIFTY | 11,745 → 4,920 | 13 min | −1,264 |
| 2026-02-02 | 3,640 BDL | COLPAL | 12,215 → 8,820 | overlapping | +3,654 |

In every one of the four largest losses, the next position was **smaller**.

### Group D — controls: bad sessions with no observable chasing

| date | session P&L | trades |
|---|---|---|
| 2026-01-23 | −8,234 | 9 |
| 2026-02-24 | −5,275 | 5 |
| 2026-01-22 | −4,144 | 5 |
| 2025-05-09 | −3,916 | 3 |
| 2025-09-22 | −2,859 | 3 |

## Conclusion

**Which signals are genuinely useful:** on this book, at population level,
**none of the trade-level ones.** Fourteen measurable signatures, and not one
separates post-loss behaviour from post-win behaviour by more than 1.4 standard
errors. Several point the wrong way — the trader returns to the same underlying
more often after wins, bursts less after losses, and trades *less* the day after
a losing day.

**Which create noise:** S5 (98% of the book is LONG — no information to carry),
S14 (a tautology, median 12.3×), S15 (14 after losses vs 12 after wins — a
rotation, not a reaction), S11 (stacking does not sharpen; 3-of-4 is *lower*
after losses).

**What H2 captures and misses:** it captured 14 sessions using an exposure test
computed on the wrong quantity. Corrected to risk it captures 17, but only because
the corrected test also admits 1%-changes. Its real filter was never exposure — it
was `≥3 attempts`, which alone removes 77% of candidates.

**Trade, episode, or session?** The evidence points to **session-level**, and to
one unit specifically: **the consecutive-loss run** (S8). It is the only signature
that is frequent (50 of 240 runs reach 3+), not diluted by a post-win control, and
not undefined when positions overlap — which the trade-level model is for ~18% of
post-loss cases. The episode model sits between two stools: it inherits the
trade-level sequencing assumption while restricting to one underlying, and the
data supports neither restriction.

**What this does not prove.** A null at population level does not mean revenge
never happened. It means revenge is **not detectable as an average shift in these
observables** for this trader. The SENSEX 9.4× escalation may well be genuine
revenge; it simply cannot be found by a rule that also has to leave the other 174
sessions alone. That is precisely why the ground-truth list exists.

**What evidence is still required before anything is implemented:**

1. **The trader's own labels on Groups A–D**, especially D. Recollection on days
   where the engine saw nothing is the only thing that can show the observables
   are looking in the wrong place.
2. **`heeded` from live alerts.** The standing position is unchanged and now has
   more support: rest-of-session P&L ranks detectors but cannot judge the
   product. An alert's job is to convert an automatic action into a deliberate
   one, and only response data measures that.
3. **Live order data** if S13 is ever to be answered.
4. **Nothing else.** Specifically, no new threshold, no exposure ratio, and no
   Pattern #2 — S3 at 1.4 SE is the strongest thing in this document and it is
   not enough to build on.
