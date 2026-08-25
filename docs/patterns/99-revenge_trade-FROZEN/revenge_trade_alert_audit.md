# The 8 historical `revenge_trade` alerts, examined individually

23 Aug 2026. **Analysis only. No code, no threshold changed.**

8 → 0 established nothing about correctness. This examines every loss → re-entry
pair the old detector fired on, from the actual trade sequences, and asks whether
the new matrix can reach the ones that look real.

**Method.** The 8 differing sessions were replayed through the harness's own
machinery, so the round-trips are built by the same ledger the engine uses. The
old detector's verdict was recomputed from those same trades. 11 pairs fired; the
replay stored 8 alerts because same-day duplicates are deduplicated.

**One caveat on the run:** the analysis replay passed no profile, where the gate
runs used `--no-rules`. That gave the lab a default cooldown, so its stored events
show a `caution` floor from the declared-rule breach. The **trade sequences are
unaffected** and are what this analysis rests on.

---

## The 11 pairs

| # | date | prior loss | as % of capital at risk | gap | same symbol | bigger | B | verdict |
|---|---|---|---|---|---|---|---|---|
| 1 | 01-22 | ₹1,375 | **21%** | 5m | **yes** | no | **B2** | **likely genuine** |
| 2 | 01-22 | ₹1,208 | **33%** | 2m | **yes** | **yes** | **B3** | **likely genuine** |
| 3 | 01-23 | ₹1,300 | 5% | 10m | yes | no | B2 | ambiguous |
| 4 | 01-28 | — | — | — | no | — | B1 | likely false positive |
| 5 | 02-01 | ₹615 | 5% | 2m | no | no | B1 | likely false positive |
| 6 | 02-01 | ₹740 | 5% | 20m | no | yes | B1 | likely false positive |
| 7 | 02-02 | ₹2,588 | **162% of SPAN** | 4m | no | no | B1 | ambiguous |
| 8 | 02-04 | ₹938 | 13% | 13m | yes | no | B2 | ambiguous |
| 9 | 02-12 | ₹560 | 11% | 2m | no | no | B1 | likely false positive |
| 10 | 02-12 | ₹1,425 | 22% | 2m | no | no | B1 | likely false positive |
| 11 | 03-06 | ₹1,020 | 11% | 11m | yes | no | B2 | ambiguous |

**2 likely genuine · 4 ambiguous · 5 likely false positive.**

### Why each classification

**Genuine — #1 and #2, the same session.** The whole day reads as one sequence:
sizes **40 → 40 → 80 → 100 → 200** across four consecutive losses on the same
underlying. #1 lost 21% of the premium and went straight back into the *same
strike* five minutes later at the same size. #2 lost 33% of the premium and
returned to the *same strike* two minutes later with 25% more size, then doubled
again. Material loss, immediate return to the identical contract, escalating
size, repeated. Nothing here needs intent to be inferred.

**False positives — #4, #5, #6, #9, #10.** Every one is a re-entry into a
*different underlying*. #5, #6 and #9 follow losses of 5%, 5% and 11% of capital
at risk in sessions of 14, 14 and 8 round-trips. "The next trade happened within
twenty minutes" describes an active trader's normal tempo, not a reaction. #10 is
a larger loss (22%) but still a jump to an unrelated instrument.

**Ambiguous — #3, #7, #8, #11.** #3, #8 and #11 return to the same contract after
5%, 13% and 11% losses with no size increase, at 10–13 minutes. That is equally
consistent with a planned re-entry at a level, and the contract already accepts
systematic re-entry as an unfixable false positive. #7 is the interesting one:
the loss was **162% of the SPAN posted** — genuinely severe — but the reaction was
a different instrument with no escalation, so the structure carries nothing.

---

## Can the current matrix reach the genuine cases?

**No. Both are A1, and the A1 row is uniformly `info`.**

| case | A | B | current | pre-revision matrix |
|---|---|---|---|---|
| #1 genuine | 1 | 2 | `info` | `info` |
| #2 genuine | 1 | 3 | `info` | **`caution`** |
| all 5 FPs | 1 | 1 | `info` | `info` |
| ambiguous | 1 | 1–2 | `info` | `info` |

**The finding that matters: B, not A, is what separates the false positives here.**
All five likely-FPs are B1 and are suppressed by the reaction axis alone,
regardless of anything the magnitude axis does. A contributes nothing to
separating this sample.

**And my (A1,B3) revision removed the only genuine case the matrix could catch.**
The pre-revision matrix would have surfaced #2 — the clearest revenge sequence in
the book — while still suppressing all five false positives. I changed that cell
to fix a ₹120 scratch loss that **does not occur in the real data**: it was a
constructed test case, and across these 8 sessions B3 happened exactly once, on a
33% loss.

---

## Minimum evidence-based change

**Revert (A1, B3) to `caution`.** One cell. No threshold invented, no tuning for
volume.

The evidence, stated as evidence and not as a preference:

1. **B3 is rare** — 1 occurrence in 11 loss → re-entry pairs across 8 sessions.
2. **That occurrence is the clearest genuine case in the sample** — 33% loss,
   same strike, two minutes, size up, inside a session escalating 40→200.
3. **It cannot reintroduce the false positives.** All five are B1 and are
   unaffected by any B3 cell.
4. **The scratch-loss risk that motivated the revision did not materialise.** It
   was hypothesised in a unit test; in this book B3 never co-occurred with a
   trivial loss.

**Keep (A1, B2) at `info`.** B2 is genuinely mixed — it holds one likely-genuine
case (#1, 21%) and three ambiguous ones (5%, 13%, 11%). Separating those is
exactly what a significance threshold is for, and one sample of four is not
enough to set one.

### What this leaves

**1 of 2 genuine cases caught. 0 of 5 false positives. Ambiguous cases silent.**

That is worse than the old detector on recall and much better on precision — and
unlike the old detector, the missed case is missed for a stated reason with the
evidence recorded, so it can be re-scored the day S2a is decided.

### What this is evidence FOR, without deciding it

Case #1 — 21% of premium, same strike, five minutes — is the argument for S2a.
With a long-option significance threshold anywhere below 21%, it becomes A2, and
(A2, B2) is already `danger` in the frozen matrix. The ambiguous B2 cases sit at
5%, 11% and 13%.

**I am not proposing a number.** Four B2 observations cannot support one, and the
gap between 13% and 21% in a sample this size is noise, not a boundary. It does
say the decision is reachable from evidence rather than from taste, and what
evidence would settle it: more sessions, and ideally a second trader's book.

---

## Honest limits of this audit

- **One trader, 8 sessions, 11 pairs.** Every classification is mine, from
  observable evidence only — no intent was inferred and the trader was not asked.
- **"Likely genuine" is not "confirmed".** Only the trader can say whether #1 and
  #2 felt like revenge, and post-hoc marking has already been shown to have zero
  adoption in this product.
- **The sample is drawn from what the OLD detector fired on**, so it cannot show
  what the old detector *missed* — false negatives are invisible to this method
  entirely.

---

## Addendum — tracing the "unexplained" caution (23 Aug 2026)

The audit above reported an unsuppressed `caution` that produced no `RiskAlert`
for an unknown reason. Traced end to end, it was two separate things.

### 1. Not a bug — it was an entry-time detection

`entry_detectors.py` runs the same detector against a position that has just
been opened and marks **every** entry-time event `shadow`. Shadow never alerts,
by design. The event was correct.

What was wrong was the audit tooling: nothing in the stored record distinguished
*"ran, judged, deliberately not shown"* from *"silently lost"*, so a correct
entry-time finding looked like a pipeline defect.

### 2. Underneath it, a real defect

`_persist_events` discards `info` events from `alerting` detectors that carry no
suppression marker. That is sound when `info` means confidence-demoted noise —
its stated purpose, halving write volume for near-zero read value.

It is wrong when a detector **states** `info` as its verdict. `revenge_trade` is
an `alerting` detector, so:

- every **A1-row detection** was dropped and never written, making the
  contract's justification for that row — *recorded, countable, not shouted* —
  **false in production**; and
- **every abstention it produced was dropped**, so the machinery built in Step 1
  specifically to make "could not tell" countable recorded nothing at all.

**Fixed** by marking a `DetectorResult`'s verdict as deliberate (`_verdict`:
`stated` or `abstained`) and exempting those from the gate. Demoted-to-info is
still discarded, suppressed evidence is still kept, analytics detectors are
untouched.

### The five dispositions

A finding now ends in exactly one, each readable from the stored row:

| disposition | how it reads | reaches the trader |
|---|---|---|
| `surfaced` | `risk_alert_id` set | yes |
| `consolidated` | `_suppressed: same_story:…` / `absorbed:…` | no |
| `deduped` | `_suppressed: dedup` | no |
| `shadow` | `shadow = True` | no, by design |
| `stated` | `_verdict` set, severity `info` | no, by design |

Nothing may be dropped without one of them. `tests/test_event_disposition.py`
holds that, with a negative control: removing the verdict check from the gate
fails six of its ten tests.

---

## The `same_symbol_obsession` consolidation case — documented, not changed

On 2026-01-22 the exit-time detection at (A1, B3) — the clearest genuine revenge
sequence in the book — was folded with `_suppressed: same_story:same_symbol_obsession`.

That is consolidation working as designed. `revenge_trade` sits behind
`same_symbol_obsession` in the *"going back to the same trade"* family, and
`same_symbol_obsession/danger` did fire that session, so the trader **was** told
they kept returning to one instrument.

**The open question, not decided here:** does `revenge_trade` carry information
`same_symbol_obsession` does not? Both describe returning to the same contract.
`revenge_trade` adds the *trigger* — that the return followed a loss, how quickly,
and whether size increased — and `same_symbol_obsession` adds the *aggregate* —
that it happened repeatedly across the session.

The family ordering is hand-picked and unvalidated, and on the one day with a
genuine sequence it is what decided the trader saw the aggregate framing rather
than the trigger framing. **No change made.** This is a product decision that
belongs with `same_symbol_obsession`'s own review, and it cannot be settled from
one session.
