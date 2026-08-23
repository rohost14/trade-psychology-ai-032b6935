# `revenge_trade` — the two open decisions

23 Aug 2026. **Analysis only. No number chosen, no consolidation changed.**

---

## Decision 1 — S2a

### What it measures, exactly

For a **long option**, `estimate_capital_at_risk` returns the **premium paid**:
`avg_entry_price × total_quantity`. That figure is *exact* and it is the
**maximum possible loss** — a long option cannot lose more than it cost.

So `S2a` is a threshold on:

```
ratio = |realized_pnl of the prior trade| / premium paid for it
```

bounded in `[0, 1]`, and it answers one question: **how much of what was staked
on that trade was destroyed.**

It does **not** claim the loss caused the re-entry. Under the frozen matrix the
ratio only sets the **A** axis — the size of the trigger — and severity comes from
the A×B pair. A large loss with no reaction structure (B1) is `caution` at most;
the reaction is what makes it revenge.

### What changes with the decision

| | S2a undecided (today) | S2a decided |
|---|---|---|
| A2 reachable | no | yes, when ratio ≥ S2a |
| (A2, B1) | — | `caution` |
| (A2, B2) | — | **`danger`** |
| (A2, B3) | — | **`danger`** |
| audit case #1 (21%, B2) | `info` | `danger` if S2a ≤ 21% |
| audit cases at 5 / 11 / 13% (B2) | `info` | `danger` if S2a ≤ that |

**The trade-off is entirely about (A2, B2).** B2 means *"came back to the same
underlying inside the window, same size"*. In the audited sample B2 holds one
likely-genuine case at 21% and three ambiguous at 5%, 11% and 13%. S2a is the
line between them, and every value converts some of those four from silent to
`danger` — skipping `caution` entirely.

**A low S2a is the dangerous direction**, and not symmetrically: at (A2,B2) the
result is `danger`, so an incautious value does not add mild noise, it adds
severe noise.

### The expiry-day problem

The concern is real and specific: **a long option expiring worthless is a 100%
loss and is a completely ordinary outcome.** Any ratio threshold below 1.0 is
crossed by every such trade. If ratio alone drove severity, expiry afternoons
would generate a wall of `danger`.

Four things already prevent that, and none is a new threshold:

1. **The ratio is not sufficient — B is required.** A 100% loss with B1 (a
   re-entry into something unrelated) is `caution`. To reach `danger` the trader
   must return to the **same underlying** inside the window. Expiring worthless
   and then trading something else is untouched.
2. **The structural gate comes first.** No loss produces anything without a
   subsequent entry inside the caution window. A trader who lets options expire
   and stops is never evaluated.
3. **Consolidation.** Repeatedly returning to one contract on expiry day is what
   `expiry_day_overtrading` and `same_symbol_obsession` describe, and both are
   ahead of or alongside `revenge_trade` in the folding order.
4. **Dedup.** One `revenge_trade` alert per 24 hours, so an expiry session cannot
   produce a stream of them.

**The residual risk, stated honestly:** an expiry-day trader who loses most of a
premium and *immediately buys the same strike again* would reach (A2, B2) →
`danger` under almost any S2a. Whether that is a false positive is a genuine
product question — it is also, arguably, exactly the behaviour this detector
exists to name.

**What the data must show before choosing:** the ratio distribution *split by
expiry day*, and specifically how often a high-ratio expiry loss is followed by a
same-underlying re-entry. If that is common in this book, S2a alone cannot
separate expiry from revenge and the decision needs a second condition. If it is
rare, S2a can stand alone.

### What kind of threshold is S2a?

**Not universal safety.** It fails the test: a universal-safety threshold states
objective harm that is dangerous whoever the trader is and may never be learned
from them. "Lost 40% of a premium" is not objectively dangerous — it is a routine
outcome for an option buyer and a severe one for someone who never lets a
position move. The number does not carry harm on its own; it carries harm only in
combination with B, which is a per-detector composition.

**It is a pattern-specific threshold.** Registry `Kind`: `product_policy` — our
decision about what counts as a large loss *for the purposes of this detector*,
not a fact about the trader and not a universal safety floor.

That has a consequence worth naming: as `product_policy`, `violates_kind` forbids
it resolving from HISTORY, SESSION or POPULATION. It cannot be personalised. If
we later decide "large for this trader" is the better question, that is a
**different threshold** (P1, `personal_baseline`) reaching the same A2 level by a
second route — which the matrix already allows, since A takes the highest level
any frame establishes.

**A third possibility, not recommended but not dismissed:** S2a could be
`definitional` if we treat it as "what fraction of a premium counts as
destroyed", closer to a unit conversion than a judgement. I do not think that
survives scrutiny — every candidate value encodes a view about trading, not about
arithmetic.

---

## Decision 2 — the `same_symbol_obsession` interaction

### What happens today

`revenge_trade` sits behind `same_symbol_obsession` in the *"going back to the
same trade"* family. When both fire, the more specific description wins and
`revenge_trade` is recorded with
`_suppressed: same_story:same_symbol_obsession`.

On 2026-01-22 — the only session in the audit containing a likely-genuine revenge
sequence — that is exactly what happened. The detection was correct, scored
`caution`, and folded.

### What each detector actually says

| | claim | evidence it carries |
|---|---|---|
| `same_symbol_obsession` | you spent the session on one instrument | count of re-entries, total loss on it |
| `revenge_trade` | you returned **immediately after a loss**, and with more size | the trigger, the gap, the size change |

They overlap on *"you went back to the same thing"* and differ on *why that
matters*. `same_symbol_obsession` is the **aggregate**; `revenge_trade` is the
**trigger and the escalation**.

### What changes with the decision

| option | effect | cost |
|---|---|---|
| **A. Leave it** | one alert per session, aggregate framing | the trigger is never surfaced; on this book `revenge_trade` surfaces nothing at all |
| **B. Reverse the order** | trigger framing wins | loses the aggregate; `same_symbol_obsession` becomes the folded one and its session-level count is hidden |
| **C. Fold, but merge the evidence** | one alert carrying both | needs consolidation to compose messages rather than pick one — a real change to how folding works, affecting all families |
| **D. Do not fold this pair** | both surface | two alerts describing one behaviour, which is what consolidation exists to prevent |

**This cannot be settled from one session.** It is the only session in the sample
where both fired, so any choice made now is fitted to n=1.

### What kind of decision is it?

Product, not architectural. The mechanism is correct and general; the family
ordering is a claim about which framing helps a trader more, and that is not
derivable from the trade record. It belongs with `same_symbol_obsession`'s own
pattern review, where both sides can be argued with that detector's evidence too.

---

## Verdict

**Needs decision. No code change required.**

`revenge_trade` is architecturally complete and behaviourally silent, and both
facts are true for stated reasons:

- the detector, the frames, abstention, the matrix, the instrument classes and
  the disposition pipeline all work and are covered by tests with negative
  controls;
- it surfaces nothing on this trader's year because A2 is unreachable (S2a
  undecided) and its one qualifying detection was consolidated.

### Minimum action

| # | action | owner | blocking? |
|---|---|---|---|
| 1 | **Decide S2a** — or decide explicitly to leave it unresolved | product, with the distribution evidence | blocks recall, not correctness |
| 2 | **Decide the consolidation interaction** | product, at `same_symbol_obsession`'s review | not blocking |

**Nothing else.** No threshold to invent, no code to change, no architectural gap
outstanding.

### Evidence still needed for S2a

1. The ratio distribution across the replay, **split by expiry day** — being
   collected now.
2. How often a high-ratio loss is followed by a same-underlying re-entry, since
   that is the only path to `danger`.
3. Ideally a second trader's book. Every number in this analysis comes from one
   trader, and the gap between 13% and 21% in a four-observation sample is noise,
   not a boundary.
