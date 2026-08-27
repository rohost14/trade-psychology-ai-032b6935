# Pattern #10 — `size_escalation` · **RETIRED / COMPLETE**

27 Aug 2026. Detector `1.1.0` → **deleted**. No replacement detector, no
replacement threshold.

Evidence: `size_escalation_review.md` (review + coverage-gap addendum).

---

## Why

**Its entire claim was that the ORDER of position sizes carries information** —
three consecutive trades each larger than the last, while losing. That makes it
directly testable by permutation, and it fails.

Same trades, same sizes, same P&L, same day; only the sequence permuted, with the
**real detector** running inside the loop:

| | |
|---|---|
| observed, real order | **42** |
| shuffled, mean of 200 permutations | **49.7** |
| 95% range | [36, 65] |
| ratio observed / expected | **0.85** |
| p(shuffled ≥ observed) | **0.880** |

**The real order fires fewer times than chance ordering.** Corroborated
independently: its defining gate — three sizes strictly increasing — selects
**16.9%** of 3-trade windows against the **16.7%** three random numbers give.

The rest was already broken:

- **37 of 42 firings named an instrument absent from their own evidence.** The
  headline used `ct_underlying` while the three trades shown were the session's
  previous three: *"ICICIGI: … (TCS25APR2900PE / TCS25APR3500CE /
  HUDCO25APR230CE)"*.
- **Only 7 of 42 alerts contained the trade that raised them.** `prior` excluded
  `ct`, so it fired on trade N and described N−3…N−1.
- **"While losing" was not a condition** — `pnls[:2]` needing one loss is true
  83% of the time by base rate, and the trade at the *top* of the escalation was
  never checked.
- **It predicted nothing** — +₹69/trade, p = 0.797, sign favouring the flagged
  trade.
- `size_escalation_pct` was **never in `threshold_registry`**, so it had no
  `Kind` and no provenance, and the comment justifying 30 described per-step
  compounding (2.2×) the code never computed (it computed a single first-to-third
  ratio, so 30% meant 1.3×).

---

## The concept of dangerous sizing is NOT retired

A coverage check ran before deletion, against the four detectors that could hold
the claim.

| detector | subject | unit | trigger | status |
|---|---|---|---|---|
| `martingale_behaviour` v2.0.0 | **the current trade**, stepped from the previous closed one | **capital at risk** | ≥2 trailing consecutive losses, ≥1.5× / 2.0× | **untouched** |
| `post_loss_recovery_bet` | **the current trade** vs mean of last 3 | qty / notional | last 2 same-underlying losses, ≥2.0× / 3.0× | **untouched** |
| `adding_to_adverse_position` | one **open** position's fills | — | added while it moved against them; **size deliberately excluded** | untouched |
| `options_premium_avg_down` | re-entry on same underlying long option | premium | prior loss on that underlying | untouched |

The first two own "sized up after losing" outright, and both do it the way the
retired detector did not: **the current trade is the subject**, and the
comparison is the step the trader actually took.

**Measured overlap was low, and that is not why it was retired.** On the same
trade: martingale 2/42, post_loss_recovery 1/42, any of the four 10/42; per
session a sizing detector fired in 21 of 36. `size_escalation` selected a mostly
*different* set. The reason to retire is that **what it uniquely selected is not
a behaviour** — chance-level selection plus low overlap with real detectors means
the non-overlapping firings are residue.

**The one genuine gap is empty in practice.** A *slow ramp* — monotone growth
where every step stays under martingale's 1.5× and the current trade under
recovery's 2.0× of the recent mean, yet cumulative ≥2.0× — is mathematically
possible (1.45 × 1.45 = 2.1×). Measured across 189 sessions / 912 positions:

| window | occurrences in a full year |
|---|---|
| **3 trades** | **0** |
| 4 trades | 1 |
| 5 trades | 1 |

It exists on paper, not in the data. Building a replacement on one or two
instances would be inventing a pattern, so **none was built**.

---

## What changed

| file | change |
|---|---|
| `services/behavior_engine.py` | detector deleted (84 lines); removed from the header list, `_STRATEGY_SUPPRESSED` and the `"sizing after losses"` family; retirement note in its place |
| `services/detector_registry.py` | `DetectorSpec` and `PatternCopy` removed, retirement notes left |
| `core/trading_defaults.py` | `size_escalation_pct` deleted |
| `services/entry_detectors.py` | removed from `ENTRY_DECIDABLE` |
| `tasks/report_tasks.py` | removed from `_COMMON_PATTERNS`; **label kept** |
| `api/analytics.py` | **`SIZING` set kept** — it tags historical days from stored events |
| `contexts/AlertContext.tsx` | `BACKEND_TO_FRONTEND_TYPE` entry removed; **display name kept** |
| `scripts/validate/06_size_escalation.py` | **archived** to `validate/_archive/`; the 05→07 chain re-pointed |
| `models/strategy_group.py` | comment annotated — the hedge-leg rationale still applies to the survivors |
| `tests/test_engine_hygiene.py` | its `size_escalation` test **deleted with its subject** (see below) |
| `tests/test_pattern_contract.py` | added to `RETIRED_PATTERN_NAMES` |
| `CLAUDE.md` | detector counts |

**Counts: 24 detectors, 30 pattern types** (was 25 / 31).
`all_pattern_types()` stays the authority.

**`_notional` survives** — `post_loss_recovery_bet` and a martingale-adjacent
detector both read it.

### One test was deleted, not weakened

`test_size_escalation_cross_instrument_reports_rupees_not_qty` in
`test_engine_hygiene.py` pinned a real fix — a notional sequence must not be
labelled `"qty"` — but it exercised the deleted detector and could now only fail
on an `AttributeError`. **Deleted with its subject**, with a note in place
explaining what it covered. No test was changed to make it pass.

`test_profit_giveaway_retired.py`'s dedup parametrize named `size_escalation`
under *"every other pattern still keys on its type alone"*; it was swapped for
`post_loss_recovery_bet`, a live pattern, so the list keeps meaning what it says.

### Historical rows stay readable

Stored alerts still carry `pattern_type = "size_escalation"`. Every rendering
surface keeps its label — `AlertContext.tsx` display name,
`BehaviourCostCard.tsx`, `BehaviourLead.tsx`, `AlertDetailSheet.tsx`'s `case`,
the weekly report's `"Size Escalation"`, and `analytics.py`'s `SIZING` day-tag
set. Only `BACKEND_TO_FRONTEND_TYPE`, `_COMMON_PATTERNS` and `ENTRY_DECIDABLE`
lost their entries, because each of those asserts the engine still emits it.

---

## Replay — 203 sessions

*(filled in from the confirmation run)*

---

## Tests

`tests/test_size_escalation_retired.py`, in four groups:

1. **it cannot produce new events** — method gone, absent from every registry
   structure, counts are 24 / 30, threshold gone and unread by any live module,
   dropped from `ENTRY_DECIDABLE` and `_STRATEGY_SUPPRESSED`
2. **the surviving sizing detectors are untouched** — both still exist, the
   family keeps its two members *in order*, `_notional` survives with readers,
   and `recovery_bet_*` / `martingale_min_losses` are intact
3. **historical rows stay readable** — report label, analytics day-tag, four
   frontend surfaces; `BACKEND_TO_FRONTEND_TYPE` and `_COMMON_PATTERNS` do not
4. **no other detector moved** — `_WORSEN_METRIC`, the other two families,
   `_COMPOSITES`, and every surviving spec resolves

---

## Limitations, recorded not closed

1. **One trader, 189 sessions, 42 firings.** The outcome tests are underpowered
   alone. The shuffle null does not depend on outcomes — it tests the detector's
   premise with the detector's own code — which is what makes the retirement
   safe.
2. **`adding_to_adverse_position` could not be measured in the CSV harness** — it
   reads a fill sequence the reconstruction does not carry, so its 0/42 in the
   coverage table is a tool limit, not a finding. The replay shows it firing 99
   times, and on 11 of the 30 `size_escalation` days, so true session coverage is
   **higher** than the 26 of 36 reported.
3. **A harness bug was caught mid-check and is worth remembering.** The first
   coverage run reported martingale covering 0 of 42; `martingale` v2.0.0 returns
   a `DetectorResult`, which wraps *positive* findings too, and the check treated
   every `DetectorResult` as non-firing. The correct predicate is
   `DetectorResult.fired`. Caught only by validating raw in-process counts
   against the replay's alert counts first — do that before trusting any
   in-process detector comparison.
4. **`demoData.ts` gives this pattern `critical` and `danger` severities it could
   never emit** (it was always `caution`). Untouched here; the vocabulary
   contract checks fixture severities are *in* the vocabulary, not that they
   match what a detector can produce.
5. **Family consolidation is per-trade, not per-session.** Two members of one
   family firing on different trades in a day both reach the trader. Affects the
   remaining families generally; recorded for a later review.
