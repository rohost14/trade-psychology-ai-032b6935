# `revenge_trade` — STATUS: architecturally complete, behaviourally unresolved

23 Aug 2026. **Implementation stopped.** The next step is a human review of what
evidence a correct revenge detector should require — not more code, and not
another pattern.

---

## The conclusion, in four statements

**1. Magnitude alone is insufficient.**
Across 14 B2/B3 cases in 40 sessions, a 12%-of-premium loss is likely genuine and
a 13% loss is ambiguous. Every threshold that avoids the ambiguous cases (≥15%)
misses the sharpest sequence in the book; the one that catches it (10%) admits
five trivial cases. No value in the range is defensible.

**2. Streak alone is insufficient.**
Consecutive losses at the moment of detection:

| | streak values |
|---|---|
| 4 likely-genuine | **1, 1, 2, 3** |
| 2 ambiguous | 1, 1 |
| 2 trivial (6% losses) | **3, 3** |

Two genuine cases sit at streak 1. Two *trivial* cases sit at streak 3 — higher
than three of the four genuine ones. A streak condition would rank noise above
signal.

**3. The current B-axis cannot distinguish the strongest sequences.**
B reads exactly one prior trade, so a first re-entry after one loss and a fourth
attempt inside a losing run produce identical levels. The sessions where this
detector is most convincing have a shape — 40→40→80→100→200 across four straight
losses; the same strike re-entered a third time at double size — and B has a
memory of one trade.

**4. No defensible replacement has been identified.**
Not magnitude, not streak, not same-contract attempt count (3rd for one genuine
case, 1st for two others), and not any combination tested against this data. The
distinguishing feature appears to be *session shape*, and no single counter
available today represents it.

---

## What must not happen next

Recorded because each would be easy, would pass a replay, and would be wrong:

- **No replacement magnitude gate** under another name — cumulative session loss,
  loss versus session median, "meaningful loss" by any other spelling.
- **No streak rule**, refuted above.
- **No score, weight, multiplier or composite** to raise alert volume. The
  detector surfacing nothing is a finding, not a bug to be tuned away.
- **No further redesign** of the matrix or the B-axis until the human review
  decides what evidence a revenge detector should require.

The reason to write this down: three separate times in this review a plausible
fix looked reasonable and was refuted only by going back to the data. A fourth
would not announce itself either.

---

## What is actually done

| | state |
|---|---|
| Capital as a suppression gate | **removed** — was 8 alerts at ₹50k, 0 at ₹5L; now capital-invariant |
| Points-based confidence score | **deleted** |
| Severity / confidence separation | **done** — table read, confidence from observability |
| Frames, abstention, maturity, instrument class, account risk | **first consumer** |
| Disposition accounting | **50 of 50 findings explained, 0 unexplained** |
| Tests | 1038 passing, with negative controls |
| Replay | ₹50k and ₹5L, every difference classified |

**Behaviour today:** surfaces nothing on this trader's year — 28 entry-time
shadow, 20 stated `info`, 2 consolidated. Honest silence, and visible.

---

## Open, by decision

| | status | owner |
|---|---|---|
| S2a | unresolved; magnitude judged the wrong instrument | human review |
| B-axis sequence awareness | gap confirmed, no defensible design | human review |
| `same_symbol_obsession` consolidation | unchanged; settled only by a session where revenge fires and obsession does not, of which there are zero | that detector's review |

---

## What the review should decide

Not "what threshold", but **what evidence a revenge detector is entitled to
require**. Three questions this work could not answer from trade data alone:

1. Is revenge a property of a **single re-entry**, or only of a **session**? Every
   convincing case here was the latter, and the current detector is built for the
   former.
2. If it is a session-level property, is it a different detector from
   `same_symbol_obsession`, or the same one better named?
3. What would count as confirmation? No trade-derived signal separated genuine
   from ambiguous. `heeded` — whether the trader stopped after being told — is the
   only measure that could, and it needs live data nobody has yet.

---

## Method note

The pattern-by-pattern approach worked, and this is the evidence: one detector
surfaced a foundation defect, two contract defects, a production write-gate bug
that was silently discarding every abstention, and the finding that the threshold
everyone assumed was needed is probably the wrong instrument.

All of it at detector one, before twenty-six others inherited any of it.
