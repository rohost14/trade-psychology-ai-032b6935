# Pattern #3 — `same_symbol_obsession`, final contract

24 Aug 2026. **IMPLEMENTED.** v2.0.0, shipped after the two validation
challenges below. No threshold invented; one constant removed.
Follows `same_symbol_obsession_review.md`, which returned MODIFY.

---

## The criterion used to choose

Not "which rule alerts more". **An episode only ever grows**, so a severity that
can *fall* as trades are added tells the trader their situation improved when it
did not. That is measurable, and it is what the current rule fails.

Four candidates, run over all 20 episodes in the book:

| candidate | danger rate | **episodes where severity FALLS** |
|---|---|---|
| **A. `last > first`** — the current rule | 67% | **2** |
| B. `peak > first` | 84% | **0** |
| C. any step-up between consecutive attempts | 84% | **0** |
| D. `peak >= 2 × first` | 73% | 0 |

A is eliminated on evidence, not taste. D is eliminated for a different reason:
the `2` is a number nobody has justified, and this review is not permitted to
invent one. B and C are both stable and both free of invented constants; **B is
chosen** because it says something the trader can check against the episode as a
whole ("it got bigger than where you started") rather than something about one
adjacent pair.

## Severity — validated, and simpler than first proposed

Two challenges were put to the first draft. One survived, one did not.

### Challenge 1: is `peak > first` meaningful, or only stable? — **MEANINGFUL**

Stability is necessary and not sufficient. A rule that is stable but almost
always true, or that fires on marginal changes, carries no information. So:
**how much bigger did it actually get?**

Every rise in the book, sorted:

```
1.67  1.67  2.00  2.00  2.00  3.00  3.00  3.00  5.00  5.00  5.00  5.00  5.00  10.00  10.00
```

**Minimum 1.67×. Median 3.00×. Not one rise under 1.5×.** There is no marginal
population at all — in these episodes size either stays flat or it multiplies.
The rule is not separating "went up a bit" from "stayed level"; it is separating
"stayed level" from "tripled".

And the two groups are materially different episodes:

| | size rose | size flat |
|---|---|---|
| attempts (median) | 6 | 4 |
| losses (median) | 4 | 3 |
| **total loss** | **₹3,911** | **₹1,537** |
| peak exposure ÷ first exposure | **1.78×** | **1.00×** |

**One honest nuance that changes how the caution tier should be read.** The flat
group starts *larger* — median first exposure ₹5,760 against ₹2,948 — and ends
at a similar peak (₹6,120 against ₹6,669). So `caution` does not mean "small".
It means **committed at full size from the first attempt and staying there**,
which is a different failure from ramping up, not a milder one.

### Challenge 2: is the 3 → 4 loss boundary justified? — **NO. It is dropped.**

Loss count per episode: `{3: 11, 4: 6, 5: 2, 6: 1}`. A smooth decay. **No gap,
no mode, no break at 4 or anywhere else.**

What the data *does* show is that more losses cost materially more:

| losses | episodes | median total loss |
|---|---|---|
| 3 | 11 | ₹1,695 |
| 4 | 6 | ₹3,911 |
| 5 | 2 | ₹6,251 |
| 6 | 1 | ₹6,116 |

That is monotone and steep — four losses cost 2.3× what three cost — but it is
**continuous**. It supports "more is worse". It does not support "4 is the
line". Putting the boundary at 4 because it is one more than 3 would be a choice
wearing the costume of a fact, which is the exact move this review has refused
everywhere else.

**So the loss-count axis is removed.** The count stays in the message as a fact;
it does not decide severity.

### The resulting rule — one axis, no invented number

```
caution   the behaviour occurred: 3+ losses on one underlying in a session
danger    and the position size at some point exceeded the first attempt
```

`max(qty) > qty[0]`. The comparison is the identity, not a chosen multiple.
Quantity is comparable because every strike and expiry of one underlying shares
a lot size.

**Split over the book: 15 danger, 5 caution.** Sanity-checked against the worst
episodes:

```
2025-09-16 NIFTY  6 losses  [225, 375, 225, 225, 300, 300]      danger
2025-08-13 NIFTY  5 losses  [75, 75, 300, 300, 225, 375]        danger
2025-09-02 NIFTY  4 losses  [150, 150, 150, 375, 300, 1500]     danger
2025-07-28 SENSEX 4 losses  [20, 20, 20, 20, 20]                caution
```

The last is right: four losses at constant size is persistence without
escalation, which is the caution case and this detector's unique contribution.

This is a stronger position than the two-axis table it replaces — **one
definitional comparison, zero constants to defend** — and it is simpler to
implement and to explain.

## What Pattern #3 uniquely contributes

Measured across the 20 episodes, against every neighbour:

| detector | episodes it also fires on |
|---|---|
| `revenge_trade` | 14 of 20 — **same family, suppressed; this is the more specific claim** |
| `adding_to_adverse_position` | 6 of 20 |
| `rapid_reentry` | 5 of 20 — same family, loses |
| `martingale_behaviour` | 5 of 20 |
| **no other detector fires at all** | **4 of 20** |

Those four are the answer to "what is this for":

```
2025-08-25  SENSEX  qtys = [40, 40, 40]                        3 losses
2026-02-01  NIFTY   qtys = [65, 65, 65]                        3 losses
2025-12-15  NIFTY   qtys = [150, 75, 75, 75, 75, 75, 75]       3 losses
2025-09-08  NIFTY   qtys = [75, 75, 150, 75, 150, 75, 150, 75] 3 losses
```

**Repeated losing attempts on one underlying at flat or falling size.** No
escalation, so martingale is silent. Nothing added to an open position, so
Pattern 2 is silent. Not fast enough to be `rapid_reentry`. **Nothing else in
the engine detects persistence without escalation** — and note these are exactly
the `caution` cells, so the tier that looks least dramatic is the one carrying
the unique signal.

## The contract

### Trigger
**Exit.** The unit is a completed losing attempt, so the detector cannot know an
attempt happened until the position closes. Unlike Pattern 2 there is nothing to
say at fill time — the trader has not yet done the thing.

### Episode
**One episode = `(session date, underlying)`.**

- **Multiple strikes are one episode.** 43 of 49 firings span two to five
  strikes; the underlying is what is being returned to. The frontend copy must
  stop saying "one instrument".
- **Overlapping positions count as attempts, and the fact is recorded.** 24 of
  49 firings contain at least one pair where the next position opened before the
  previous closed. Excluding them would need a rule about what "concurrent"
  means that no evidence supports; counting them silently while the message says
  "attempts today" is the thing to fix. **The count stays; the context gains
  `concurrent_pairs` and the copy must not imply a sequence that was not
  checked.**
- The episode ends with the session. It does not cross days.

### Required conditions
- `losses >= obsession_min_losses` (3) on the underlying, within the session.
- Nothing else. **`obsession_min_reentries` is removed** — see below.

### Exclusions
- No underlying (unparseable symbol) → no detection, as today.
- Nothing else is excluded. In particular a **winning current trade does not
  suppress it**: 16 of 49 firings had one, and the episode's losses happened
  regardless. This detector reports a fact and makes no predictive claim.

### Alert timing
On the exit that first satisfies the conditions, and again only on a genuine
escalation of severity within the episode.

### Dedup
**Episode-based, exactly as Pattern 2 does it.** One alert per severity level
per `(session, underlying)` episode.

Today 49 firings represent **20 episodes — a 2.5× repetition**, and severity
oscillates within four of them. With episode dedup the ceiling is two alerts per
episode and the realistic count is **20 to 28** for the year.

Reusing Pattern 2's mechanism is deliberate: it is proven, it lives in the
calling task rather than in the shared 30-minute path, and it changes no other
detector. **It is not a threshold and adds no state** — the episode key rides in
the alert's own details.

### Overlap boundaries

| | claim | can co-fire with #3? |
|---|---|---|
| `martingale_behaviour` | escalating risk across **attempts** after a closed loss | **yes** — different family. Both true when the trader chased *and* escalated |
| `adding_to_adverse_position` | increasing an **open** position moving against them | **yes** — different family, different unit entirely |
| `revenge_trade` | a trade taken straight after a loss | **no** — same family, and #3 wins as the more specific claim |
| `rapid_reentry` | re-entering the same symbol within minutes | **no** — same family, loses |

**No merge is proposed.** #3's subject is *the session's relationship with one
underlying*; the others are about a trade, a position, or a pair of trades.

### Constants, and why each exists

| constant | value | kind | why |
|---|---|---|---|
| `obsession_min_losses` | **3** | **definitional — KEEP** | "Repeatedly" needs a number and 3 is the smallest that means it. Unchanged. |
| `obsession_min_reentries` | 2 | **DELETE — unreachable** | `losses` is a subset of the attempts, so `losses >= 3` implies `attempts >= 3` implies `reentries >= 2`. Minimum attempts observed across the whole book: **3**. It has never changed an outcome and cannot. |
| severity rule | `max(qty) > qty[0]` | definitional | the identity, not a multiple. The loss-count axis was proposed and then **dropped**: the distribution has no break at 4 or anywhere else, so any boundary would be a choice presented as a fact |

**Nothing is added, and one thing is removed.**

## What shipped

| # | change | measured effect |
|---|---|---|
| 1 | severity `max(qty) > qty[0]`, replacing `last > first` | **0 firings now peak mid-episode and score caution** — was 8. Severity can no longer fall as an episode grows |
| 2 | `obsession_min_reentries` deleted | none — it could never bind |
| 3 | dedup key gains the underlying; the `total_loss` re-arm removed | one alert per severity level per episode |
| 4 | `concurrent_pairs`, `size_first`, `size_peak` in context | none to firing |
| 5 | copy: "one instrument" → "one underlying — any strike or expiry" | copy only |

Firing-level severity moved from 33 danger / 16 caution to **41 / 8**; at
episode level, which is what survives dedup, it is **15 danger / 5 caution**.
Detection is unchanged — the gate did not move, only how it is scored and
reported.

**23 tests** in `tests/test_same_symbol_obsession.py`, including one that walks
a real ladder attempt by attempt and asserts severity never falls. Suite: 1,203
passing.

## Superseded — the original change list

| # | change | effect |
|---|---|---|
| 1 | severity = `peak > first`, replacing `last > first` | stops the danger↔caution oscillation; 8 firings currently mis-scored; **15 danger / 5 caution** over the book |
| 2 | delete `obsession_min_reentries` and its check | none — it cannot bind |
| 3 | episode dedup on `(session, underlying)`, one alert per severity level | 49 firings → 20-28 alerts |
| 4 | record `concurrent_pairs` in context; copy must not imply sequence | none to firing |
| 5 | frontend copy: "one instrument" → the underlying | copy only |

## What remains uncertain

- **The premise is not supported by the book's averages.** Returning to an
  underlying was measured at 31.9% after a loss against 33.6% after a win —
  *less* likely, not more. The detector counts a thing that happens rather than
  an elevated tendency. It is kept because the tail it lands on is real
  (₹7,784 · ₹7,745 · ₹6,251) and the finding is factual, not because the
  behaviour is proven to be a bias for this trader.
- **The corrected 203-session replay is still running** and is slower than
  expected — carry-seeding replays each carried position's full history, giving
  roughly nine hours rather than forty minutes. Every number here comes from the
  offline harness, which uses the **real detector method** over positions rebuilt
  from raw fills with carry handled by construction. The replay will add
  consolidation, DB dedup and the alert cap; it will not change which episodes
  the detector finds.
- **Redis was intermittently unavailable during that replay** (`10061`). The fill
  pipeline falls through to an inline path when that happens, so entry checks
  still run but uncoalesced. Pattern 2's counts from that run should be read with
  that in mind; Pattern 3 is exit-triggered and unaffected.

## Follow-ups recorded, not done here

- Both obsession constants are unclassified in `threshold_registry`. Classify
  when the severity rule is settled.
- The 2.5× repetition would suit episode dedup across other exit-time detectors
  too. Not proposed — Pattern 2's mechanism shipped hours ago and should earn
  its keep first.
- Patterns 1 and 2 are untouched by all of the above.
