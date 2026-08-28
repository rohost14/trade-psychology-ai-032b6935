# Pattern #11 — `direction_instability` · **RETIRED / COMPLETE**

28 Aug 2026. Detector `2.0.0` → **deleted**. No replacement detector, no
replacement threshold.

Evidence: `direction_instability_review.md`, `discrimination_followup.md`.

---

## Why

**It could not tell an emotional reversal from a change of view — and what it
selected looked like the change of view.**

Every CE↔PE transition on one underlying across the 189-session book:

| kind | n | detector |
|---|---|---|
| simultaneous — legs overlap (hedge / structure) | 10 | correctly excluded |
| **rapid** — sequential, gap < 10 min | **16** | **FLAGGED** |
| slow — sequential, gap ≥ 10 min | 48 | not flagged |

So its only discriminator was the clock — and the clock sorted backwards:

| | n | win rate | mean P&L |
|---|---|---|---|
| **flagged** flip trade | 16 | **56.2%** | **+₹276** |
| not flagged, same transition | 48 | 41.7% | −₹73 |
| the position being exited (flagged) | 16 | 31.2% | **−₹284** |
| the position being exited (not flagged) | 48 | 54.2% | +₹35 |

**The trader reversed fast when a position had gone badly and slowly when it had
not.** That is cutting a loser.

Sessions containing a flip ended **+₹1,305** against **−₹860** for no-flip
sessions in the same trade-count band (p = 0.129). Rest-of-session after the
first flip was **+₹953** against **−₹112** matched (**p = 0.095**) — the premise
predicts deterioration, the measurement showed improvement. Flagged flips were
flat-sized (median ratio 1.03), so there was no escalation story. `revenge_trade`
already fired on **10 of the 18** firings.

Nothing reached p < 0.05 at n=16, but five independent measures pointed the same
way. **An alert that fires on good decisions is worse than one that fires on
noise.**

## The concept is NOT retired permanently

**Level 1 — a same-symbol LONG↔SHORT reversal — was never testable here.** The
book is **911 LONG against 1 SHORT**, with zero same-symbol opposite-direction
pairs at any gap. That branch would be live for a futures trader or an option
seller. **Revisit with a book that contains shorts.** Losing an unmeasured branch
is the honest cost of this retirement, recorded rather than argued away.

---

## What changed

| file | change |
|---|---|
| `services/behavior_engine.py` | detector deleted (~100 lines); removed from `_STRATEGY_SUPPRESSED`; the `options_direction_confusion` merge note annotated; retirement note in its place |
| `services/detector_registry.py` | `DetectorSpec` and `PatternCopy` removed, retirement notes left |
| `core/trading_defaults.py` | `rapid_flip_min` (both `COLD_START_DEFAULTS` and `UNIVERSAL_FLOORS`) and `direction_confusion_window_min` deleted |
| `core/threshold_registry.py` | `rapid_flip_min` `_spec` and its floor entry deleted |
| `tests/test_behavior_engine.py` | its two `direction_instability` tests **deleted with their subject** |
| `tests/test_foundation_f3_f5.py` | the classification guard **deleted with its last subject** — see below |
| `tests/test_pattern_contract.py` | added to `RETIRED_PATTERN_NAMES` |
| `CLAUDE.md` | detector counts |

**Counts: 23 detectors, 29 pattern types** (was 24 / 30).
`all_pattern_types()` stays the authority.

**Never had a `BACKEND_TO_FRONTEND_TYPE` entry** — unlike the other retirements,
there was nothing to remove there. A test pins that one is not added later.
Frontend display labels are kept so stored rows still render.

### Two tests deleted with their subjects, neither weakened

1. `test_direction_instability_detected` / `test_no_flip_on_same_direction` in
   `test_behavior_engine.py` exercised the deleted method. Worth noting the first
   asserted `level == 1` — the branch that **never fired once on the real book**,
   so its only coverage was ever synthetic.
2. `test_declaring_direction_never_overwrites_an_existing_classification` in
   `test_foundation_f3_f5.py` named the keys carrying a prior classification and
   required them to keep it. `revenge_window_danger_min` went in August;
   `rapid_flip_min` was its last remaining key. The dict would now be empty and
   the test would loop over nothing and pass — which **its own docstring calls
   out as worse than no test**. It was deliberately **not** repointed at another
   key: the audit below found the registry's `Kind` labels are wrong across the
   board, so any key chosen today would pin a false classification.
   **This guard must be restored as part of that relabel.**

### The death_spiral guard fired, correctly

The `>= 5` danger-capable-emotional assertion added during Pattern 10 **failed on
this change, and was right to**. Unlike `size_escalation` (caution-only, and so
invisible to `death_spiral`), `direction_instability` emitted `danger` at 3+
session flips and could contribute a domain.

Measured: it produced **exactly one danger event** across 189 sessions, so **at
most one session** could lose its emotional domain to this retirement.

Both assertions are now pinned to the **explicit set** rather than a count —
`{overtrading_burst, winning_streak_overconfidence, opening_5min_trap,
same_symbol_obsession}`. A bare number went stale twice (`>= 12`, then `>= 5`)
and cannot catch a substitution.

---

## Replay

**Not run.** Six attempts across two days failed on environment during Patterns 9
and 10 (network drops, task reaping, a 3h20m I/O hang); the machine has not
completed a 203-session run.

Expectation if it is ever run: **`direction_instability` 10 → 0**, everything
else unchanged **except `death_spiral`, which may fall by at most 1** on the
single day this detector produced a `danger` event. Anything else is a
regression.

---

## Tests — 22 for the retirement, mutation-checked

`tests/test_direction_instability_retired.py`, in four groups: it cannot produce
new events (method, registry, vocabulary, counts, both thresholds gone and unread,
dropped from `ENTRY_DECIDABLE` and `_STRATEGY_SUPPRESSED`); the adjacent
detectors that own the real story survive (`revenge_trade`, `same_symbol_obsession`,
`rapid_reentry`, `options_premium_avg_down`); historical rows stay readable; no
other detector's wiring moved.

Three mutations were introduced and each was caught: the detector returned to
`ENTRY_DECIDABLE`, `rapid_flip_min` restored to defaults, and `revenge_trade`
dropped from the suppression set. All reverted.

**Backend 1,522 passed, 0 failed** (excluding `tests/production`, which needs a
live server). **Frontend typecheck clean, 102 tests, 0 lint errors.**

---

## Limitations, recorded not closed

1. **Level 1 is untested and now unavailable.** The dominant limitation. This
   book cannot produce a same-symbol reversal.
2. **n = 16 flagged transitions.** No test reached p < 0.05; the case rests on
   five measures agreeing in direction, not on any one of them.
3. **No confirmation replay** — see above.
4. **The classification guard in `test_foundation_f3_f5.py` is gone** and should
   return with the registry relabel.
5. **`revenge_trade` now carries this story alone** on the days both fired, and
   it is FROZEN by decision — so the "reversed after a loss" reading is owned by
   a detector nobody is currently allowed to change.
