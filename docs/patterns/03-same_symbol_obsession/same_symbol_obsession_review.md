# Pattern #3 — `same_symbol_obsession`

24 Aug 2026. **Review only. No code changed, no threshold added or retuned, no
detectors merged, no architecture touched.**

**Verdict: MODIFY.** The detector observes something real, but its severity
switch is broken in a way that makes the same session oscillate between
`danger` and `caution`, and one of its two constants can never bind.

---

## 1. What it is supposed to detect

Chasing one underlying: coming back to the same instrument again and again
inside a session, losing on it repeatedly. The registry copy says *"Returning
to the same instrument after losses is persistence with the instrument, not
with the strategy."*

The mechanism it appeals to is **mental accounting** (Thaler): a loss opens an
account attached to *that instrument*, and the trader needs to close it *there*
rather than anywhere. A win in something else does not settle it. That is a real
and well-documented effect, and it is a different claim from martingale
(escalation across attempts) or adding-to-adverse (increasing an open loser).

**But the premise was measured during the revenge research and did not hold for
this trader.** Signature 4 — "loss → same instrument" — came out at **31.9%
after a loss against 33.6% after a win**. Returning to the same underlying is
*slightly less* likely after a loss, not more. The detector is not measuring an
elevated tendency; it is counting a thing that happens.

## 2. What the implementation does

`behavior_engine.py:3363-3414`, 52 lines, one method.

1. Take every session trade on the same **underlying** as the current trade,
   plus the current trade.
2. Count the losses among them.
3. `reentries = len(same) - 1`.
4. Fire when `losses >= obsession_min_losses` **and**
   `reentries >= obsession_min_reentries`.
5. **Severity: `danger` if the LAST quantity exceeds the FIRST, else `caution`.**

| input | value | classification | notes |
|---|---|---|---|
| `obsession_min_losses` | 3 | **unclassified** | the only binding gate |
| `obsession_min_reentries` | 2 | **unclassified** | **unreachable — see §4** |
| severity switch | `qtys[-1] > qtys[0]` | hardcoded, no key | first vs last only |

**User-declared / onboarding values consumed: none.** The registry spec sets no
baseline, constitution or position-state dependency, and the code reads no
profile field.

**Severity** caution / danger. **Confidence** not set. **Evidence/abstention**
none — returns a `DetectedEvent`, so it cannot say "I could not tell".
**Notification level 2** → a danger firing is a push.

## 3. Are the values justified?

| value | verdict | reasoning |
|---|---|---|
| `obsession_min_losses = 3` | **Definitional — KEEP.** | "Repeatedly" needs a number and 3 is the smallest that means it. The threshold inventory already classifies this family as definitional. |
| `obsession_min_reentries = 2` | **DEAD — see §4.** | Cannot bind. Not wrong; unreachable. |
| the first-vs-last severity switch | **WRONG — see §4.** | Not a threshold at all: it is a comparison that ignores everything between the endpoints. |

## 4. Evidence — 175 sessions, 740 positions

Positions rebuilt from raw fills (open → flat) so carry-forward is correct; the
replay JSON on disk predates that fix and misreads 9.2% of fills. The **real
detector method** decided every case.

**49 firings across 20 days — but only 20 distinct session-underlying
episodes.** It re-fires on every subsequent trade on that underlying:

| firings for one episode | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| episodes | 6 | 6 | 3 | 3 | 2 |

### 4a. The severity switch oscillates — the finding

`size_rising` is `qtys[-1] > qtys[0]`. As each new trade lands it becomes the
new last element, so the comparison flips. On four of the twenty episodes the
severity changes across the repeats, and it changes **back and forth**:

```
2025-08-21 NIFTY   danger -> caution -> danger -> caution -> caution
2025-06-19 NIFTY   danger -> caution -> danger -> danger  -> danger
2025-09-02 NIFTY   caution -> danger -> danger -> danger
```

Worse, it misses the escalation it exists to catch. **Eight of 49 firings peaked
in the middle and were scored `caution`:**

```
qtys = [75, 150, 375, 75]              -> caution   (a 5x spike, ignored)
qtys = [75, 150, 375, 75, 150, 75, 75] -> caution
qtys = [75, 75, 150, 150, 75]          -> caution
```

A trader who ran 75 → 150 → 375 and then came back at 75 gets the *quieter*
alert, because only the endpoints are compared.

**A correction to my own earlier note.** I previously flagged this switch as
comparing quantities "across possibly different strikes" and implied the units
were incomparable. **That was wrong**: every strike and expiry of one underlying
shares a lot size, so quantity *is* comparable here. The defect is the
endpoints-only comparison, not the unit.

### 4b. `obsession_min_reentries` can never bind

`losses` is a subset of `same`, so `len(losses) >= 3` implies `len(same) >= 3`
implies `reentries >= 2`. The second gate is satisfied by arithmetic whenever
the first is.

Confirmed on the book: **minimum attempts observed is 3**, and 10 of the 49
firings sit at exactly 3. The constant has never changed an outcome and cannot.

### 4c. "Attempts" counts concurrent positions as re-entries

**24 of 49 firings contain at least one overlapping pair** — 34 pairs in total —
where the next position was opened *before* the previous one closed.

The message says "6 attempts today". Some of those were held simultaneously,
which is a different thing from going back six times. Holding two NIFTY strikes
at once may be a structure rather than a chase, and the detector cannot tell.

### 4d. Only 6 of 49 are actually one instrument

Distinct symbols per firing: `{1: 6, 2: 15, 3: 17, 4: 9, 5: 2}`. **43 of 49
span two to five different strikes** of the underlying.

That is defensible — the underlying is the thing being chased — but the
frontend copy says *"Repeat trades on one instrument"*, which is not what is
being counted.

### 4e. It does not require the current trade to be a loss

16 of 49 fired on a winning current trade. Consistent with the other two
patterns: it reports a fact and makes no predictive claim.

### 4f. Where it fires, it fires on the worst sessions

```
2026-02-24 NIFTY  [danger] 4/4 attempts  Rs 7,784  qtys=[65, 65, 130, 130]
2026-02-27 NIFTY  [danger] 3/3 attempts  Rs 7,745  qtys=[65, 65, 195]
2025-08-13 NIFTY  [danger] 5/6 attempts  Rs 6,251  qtys=[75, 75, 300, 300, 225, 375]
2025-09-16 NIFTY  [danger] 6/6 attempts  Rs 6,116  qtys=[225, 375, 225, 225, 300, 300]
```

These are among the worst sessions in the book. Whatever the premise says about
averages, the tail this detector lands on is real.

## 5. Overlap and whether the alert is meaningful

Measured on the same trade:

| detector | co-fires | survives consolidation? |
|---|---|---|
| `revenge_trade` | **25 of 49 (51%)** | **No** — same family, and `same_symbol_obsession` **wins** |
| `size_escalation` | 7 (14%) | Yes — different family |
| `rapid_reentry` | 6 (12%) | No — same family, loses |
| `martingale_behaviour` | 6 (12%) | Yes — different family |
| `adding_to_adverse_position` | **not measured** | — |

The family machinery is working: the 51% overlap with `revenge_trade` is
suppressed by design, and this detector is the more specific claim.

**The `adding_to_adverse_position` overlap is unmeasured**, not zero — that
detector needs `ctx.position_fills`, which this offline harness does not
populate. It should be measured before either detector's scope is finalised.

**Is the alert meaningful?** The *finding* is — "four attempts on NIFTY, three
lost, ₹7,784" is checkable and specific. The **severity is not**: a trader who
sees `danger` on one trade and `caution` on the next, for the same worsening
session, learns that the severity means nothing.

## 6. Performance and purity

**Pure.** No `await`, no `db.`, no `select(` in the body — verified by
inspection, and it ran 740 times in this review with no database connection.

**Cost:** one filter and one sort over the session's trades, O(n log n) per
trade with n the session length. Negligible.

**KEEP AS-IS.**

## 7. Verdict — **MODIFY**

Not DELETE: it lands on genuinely bad sessions, the finding is factual, and it
is the most specific claim in its family. Not KEEP AS-IS: the severity switch
oscillates and misses the escalation it exists to catch. Not DEFER: the defect
is provable now and needs no further evidence.

### Recommended behavioural contract

> **`same_symbol_obsession` reports one fact: the trader returned to the same
> underlying repeatedly in one session and lost on it repeatedly.**
>
> - The unit is the **underlying**, not the contract — and the copy should say
>   so.
> - "Repeatedly" is a **count of losses**, which is definitional.
> - Severity, if it varies at all, must reflect **the whole sequence**, not its
>   endpoints. A size that peaked and came back down still peaked.
> - It states what happened. It makes no predictive claim: the premise —
>   returning to an instrument after losing on it — was measured at 31.9% after
>   a loss against 33.6% after a win, so it is not an elevated tendency for this
>   trader.

### Exact changes required — for approval, not implemented

| # | change | why | effect |
|---|---|---|---|
| 1 | severity must consider the whole quantity sequence, not `last > first` | it oscillates danger/caution on the same worsening session, and scores a 5× mid-session spike as `caution` | 8 firings currently mis-scored; severity stops flipping |
| 2 | delete `obsession_min_reentries`, or make it independent of `min_losses` | it cannot bind — `losses >= 3` implies `reentries >= 2` | none; it has never changed an outcome |
| 3 | record whether the counted attempts **overlapped** | 24 of 49 firings count concurrent positions as re-entries, and the message says "attempts today" | none to firing; the alert stops implying sequence it has not checked |
| 4 | frontend copy: "one instrument" → the underlying | 43 of 49 span 2-5 strikes | copy only |

**No threshold is added, removed or retuned.** `min_losses` stays 3. The
severity rule changes shape, not sensitivity — and **what shape it should take
is deliberately not decided here**, because choosing between "any rise",
"peak vs first" or an ordinal on the sequence needs its own evidence and would
be inventing.

### Recorded for later reviews, not fixed here

- Repetition: 49 firings for 20 episodes. The 24h DB dedup collapses most of
  them, but the same **position-epoch** treatment just built for Pattern 2 would
  fit here — the episode being `(session, underlying)`. Not proposed; Pattern 2
  shipped it hours ago and it should earn its keep first.
- The `adding_to_adverse_position` overlap is unmeasured.
- `obsession_min_losses` and `obsession_min_reentries` are both unclassified in
  the threshold registry; classify when the severity rule is settled.
