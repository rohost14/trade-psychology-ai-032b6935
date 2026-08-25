# `revenge_trade` — review close-out

23 Aug 2026. **Analysis only. No code, no threshold, no consolidation change.**

---

## 1. S2a — conclusion recorded

**Left unresolved. No provisional value.**

The evidence does not support any number in the range, and that is a finding
rather than a gap in the analysis:

> **Magnitude alone does not reliably distinguish revenge behaviour in this book.
> The B-axis — the structure of the reaction — carries more signal than the size
> of the trigger.**

The decisive observation: across 14 B2/B3 cases, **a 12% loss is likely genuine
and a 13% loss is ambiguous.** The ratio cannot separate them; the sequence can.
02-05 at 12% was a third attempt at the same strike at double size, ending
−₹5,956 — the largest single loss in the window. 02-04 at 13% was a single
re-entry at the same size.

Every threshold that avoids the ambiguous cases (≥15%) **misses the sharpest
sequence in the book**. The one that catches it (10%) admits five trivial cases.

Corroborating, and independent of any threshold:

- the deepest losses (B0: median 17%, p90 52%) are followed by **no re-entry** —
  this trader stops after a large loss, the opposite of revenge;
- ratio does not rise with reaction structure (B0 17% → B1 7% → B2 6% → B3 12%);
- expiry needs no exception: 4 of 13 expiry losses had a same-underlying
  re-entry, and two of those *are* the genuine cases.

**Explicitly not done, and not to be done quietly later:** no other magnitude
gate has been introduced in its place. `revenge_min_loss_inr` is deleted,
`_typical_loss` is not called by this detector, and no minimum-loss condition of
any kind exists in the rewritten code. If a magnitude gate reappears under
another name, that is a regression against this conclusion.

---

## 2. Is the B-axis sufficient?

**No — and the gap is specific and pattern-level, not architectural.**

### What B can see

B reads exactly one prior trade: the loss immediately before this entry. From it
comes promptness (B1), same underlying (B2) and a larger position (B3).

### What B cannot see

**Where this sits in a losing run.** The likely-genuine cases occur inside
sessions with an unmistakable shape:

| session | shape |
|---|---|
| 01-22 | 40 → 40 → **80 → 100** → 200, four straight losses |
| 02-24 | 65 → **65 → 130** → 130 → 130, four straight losses |
| 02-05 | same PE at 100 → **120 → 200**, third attempt loses ₹5,956 |

B sees none of that. It reads exactly one prior trade, so a first re-entry after
one loss and a fourth attempt inside a losing run produce identical B levels.

### CORRECTION — the obvious fix does not work either

I first wrote that the genuine cases cluster at `consecutive_losses ≥ 2` while
the ambiguous ones sit at 1, and that a streak-aware B would therefore separate
them. **Deriving the streaks from the session data shows that is false:**

| case | verdict | streak at that trade | same-contract attempt |
|---|---|---|---|
| 01-22 33% B3 | genuine | **3** | 1st |
| 01-22 21% B2 | genuine | **1** | 1st |
| 02-24 20% B3 | genuine | **2** | 2nd |
| 02-05 12% B3 | genuine | **1** | **3rd** |
| 02-04 13% B2 | ambiguous | 1 | 1st |
| 03-06 11% B2 | ambiguous | 1 | 1st |

Two of the four genuine cases sit at streak 1 — the same value as both ambiguous
ones. **Consecutive-loss count does not separate them.** Nor does same-contract
attempt count on its own: it is 3rd for one genuine case and 1st for two others.

So the gap in B is real — its memory is one trade — but **no single additional
counter fixes it**, and I should not have implied one would. The session *shape*
is what distinguishes these cases, and shape is not any of the three counters
below taken alone.

### Three things B is blind to, all already computed elsewhere

| missing context | already available as |
|---|---|
| consecutive losses before this entry | `session_facts.consecutive_losses` |
| cumulative session P&L | `session_facts.pnl` |
| repeated attempts at the same contract | derivable from `session_trades` |

**None of this needs a new measurement or a new threshold.** All three are facts
the engine already computes for other detectors, and `consecutive_losses` in
particular is the canonical session fact this work made single-definition.

### Why this is a real gap, and why it is NOT ready to act on

The gap is real: B's one-trade memory demonstrably cannot represent the sessions
where this detector is most convincing.

But the correction above matters more than the gap. The first plausible fix —
add a loss-streak condition — **is refuted by the data**, and it is exactly the
kind of change that would have looked reasonable, passed a replay, and encoded a
pattern that is not there. That is the same failure mode as S2a, one axis over.

**No redesign proposed.** The honest statement is that B's one-trade memory is a
limitation the audit exposed, the missing context already exists as canonical
facts, and whether to use it is a contract change requiring its own review,
evidence and replay — exactly the process S2a just went through.

### The trap to avoid

A "repeated loss" condition could easily become **a magnitude gate wearing a
sequence costume** — for instance requiring cumulative session loss above some
figure. That would reintroduce precisely what §1 rejected. Any future B change
must rest on **counts and ordering**, which need no threshold, not on rupees.

---

## 3. The `same_symbol_obsession` consolidation question — resolved

**Resolution: leave the current behaviour unchanged. The question is real, and
this sample cannot settle it.**

### What the evidence shows

Both fired together on exactly **one** session in the window (01-22), where
`revenge_trade` was folded with `_suppressed: same_story:same_symbol_obsession`.

That is n=1. Any reordering justified by it would be fitted to a single day.

### What each detector uniquely carries

| | unique contribution |
|---|---|
| `same_symbol_obsession` | the session-level count and total loss on one instrument |
| `revenge_trade` | the **trigger** — that the return followed a loss, how fast, and whether size grew |

They genuinely differ. `revenge_trade` is not redundant.

But note what §2 established: the sequences where `revenge_trade` is most
convincing are *repeated attempts at one contract inside a losing run* — which is
**close to what `same_symbol_obsession` describes**. On the evidence, the two
detectors are more overlapping than the frozen contract assumed, and the trader
did receive a `danger` alert about that behaviour on 01-22.

### Why leaving it is the right call now

1. **n=1.** Reordering on one session is fitting.
2. **The trader was told.** `same_symbol_obsession/danger` fired. This is not a
   case of a behaviour going unreported — it is a question of framing.
3. **Reordering has a symmetric cost.** Putting `revenge_trade` first hides the
   session-level count, which on 01-22 is the stronger fact: it happened four
   times, not once.
4. **It interacts with §2.** If B becomes sequence-aware, `revenge_trade` moves
   *closer* to `same_symbol_obsession`, and the right answer might be merging
   their evidence rather than ordering them. Deciding the order now would
   pre-empt that.

### What would settle it

A session where `revenge_trade` fires and `same_symbol_obsession` does **not** —
i.e. a fast escalating re-entry that never becomes session-long obsession. That
is the case where folding loses information outright. There are zero such
sessions in this window; the question stays open until one appears, or until a
second book provides them.

**Recorded for `same_symbol_obsession`'s own pattern review.**

---

## 4. Verdict

### `revenge_trade`: **COMPLETE — with two decisions deliberately left open**

Not "blocked": nothing prevents shipping it, and nothing further is required of
this detector. Not "incomplete": every item in its contract is implemented,
tested and replay-verified.

**What was delivered**

- Capital removed from the suppression path — the defect that silenced the
  detector entirely at ₹5L. Now capital-invariant, measured 0 vs 0 where it was
  8 vs 0.
- The points-based confidence score deleted; severity read from a two-axis
  table, confidence computed from observability alone.
- First consumer of the shared foundation: frames, abstention, maturity,
  instrument classes, account risk, `DetectorResult`.
- Two contract defects found and fixed during implementation (B0 emitting
  evidence for unrelated trades; A1 unreachable), each stopped and reported
  rather than patched silently.
- One production defect found and fixed: **stated `info` verdicts and every
  abstention were being dropped before they were written**, which made the
  contract's "recorded, countable" claim false and left the Step-1 abstention
  machinery recording nothing.
- A disposition pipeline that accounts for **50 of 50 findings with zero
  unexplained**.

**What it does today**

Surfaces nothing on this trader's year. Every finding has a stated disposition:
28 entry-time shadow, 20 stated `info`, 2 consolidated. That is honest silence,
not failure — and it is visible rather than hidden.

**Open, by decision, not by omission**

| | status |
|---|---|
| S2a | unresolved — evidence says magnitude is the wrong axis |
| B sequence-awareness | gap confirmed; the obvious fix (streak count) refuted by the data. Needs a different idea, not an implementation |
| consolidation ordering | unchanged. Belongs to `same_symbol_obsession`'s review |

### What this says about the pattern-by-pattern method

It worked. One detector surfaced: a foundation defect, two contract defects, a
production write-gate bug, and a substantive finding that the threshold everyone
assumed was needed is probably the wrong instrument. All at one detector, before
twenty-six others inherited any of it.

**Stopping here.**
