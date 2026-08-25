# Pattern #4 — `consecutive_loss_streak` · **RETIRED**

26 Aug 2026. Decision: **DELETE the behavioural detector. Keep and improve the
user-declared rule.** Taken by the user on the evidence below; implemented the
same day.

---

## What changed

| | before | after |
|---|---|---|
| behavioural detector `consecutive_loss_streak` | live, 33 pattern types | **gone** |
| who alerts on a losing run | this detector (our count of 3/5) **and** `constitution_violation` (the trader's count) | **only `constitution_violation`** |
| warning before the breach at limits 2, 3, 4 | **impossible** — see the defect below | fires at `limit − 1` |

## Why it was deleted

**The trigger was chance. Not close to chance — chance.**

189 sessions, 912 positions, win rate 39.9%. Shuffling each session's outcomes
2,000 times at that rate, preserving session lengths:

| run length | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| **observed** | 135 | 81 | 42 | 12 | 7 | 2 | 2 | 2 |
| **chance** | 146.4 | 73.9 | 36.4 | 17.3 | 7.4 | 3.1 | 1.5 | 0.6 |

> **Sessions containing a 3+ loss run: observed 63. Expected by chance 63.0. Of 189.**

A run of three losses in this book is exactly what a 39.9% win rate produces on
its own. The danger tier at 5 is the same story — 7 observed against 7.4
expected. Measured twice, on two independent trade sets (the contaminated
742-position set during the revenge research, and the corrected 912-position
set).

This does **not** mean the trader is calm during a losing run. It means **the run
is not evidence** of a changed state, so a detector whose finding *is* the run
asserts something the data denies. It was the engine's loudest voice — 78 alerts
after dedup, more than any other pattern — and it was loud about noise.

The one branch that was not a count (`total_loss >= daily_loss_limit × 0.5`)
**fired 0 times in 106**, because `daily_loss_limit` is `None` for anyone who has
not declared one and `resolve_thresholds` supplies no fallback.

## What replaced it — and why that is not the same thing

`constitution_violation`'s `max_consecutive_losses` rule reads the **same
canonical session fact** (`ctx.facts.consecutive_losses`) and compares it to the
number **the trader declared at onboarding**.

The distinction that matters:

- The deleted detector claimed *"a losing streak means psychological
  deterioration."* The data does not support that claim.
- The surviving rule claims *"you are approaching / have crossed the limit you
  explicitly told us you don't want to cross."* That claim is true by
  construction — it needs no evidence about tilt, because it is a statement about
  a commitment, not a prediction about a state.

This also removes a duplicate alert source: the two detectors read the same
streak, one against the trader's number and one against ours, and nothing
consolidated them beyond a one-way suppression.

## The defect found while implementing it

**`approaching` was unreachable for limits of 2, 3 and 4 — including the
onboarding default of 3.**

The shared ladder is `caution` at 80% of the rule, `danger` at 100%, `critical`
at 120%. A streak moves in whole trades:

| declared limit | 80% of it | first integer streak ≥ that | its ratio | tier reached |
|---|---|---|---|---|
| 2 | 1.6 | 2 | **1.00** | danger — no warning |
| **3** (onboarding default) | 2.4 | 3 | **1.00** | **danger — no warning** |
| 4 | 3.2 | 4 | **1.00** | danger — no warning |
| 5 | 4.0 | 4 | 0.80 | caution ✓ |
| 10 | 8.0 | 8 | 0.80 | caution ✓ |

Every trader on the default went from silence straight to a breach.

**Fix: `streak == limit − 1` also produces `caution`.** No multiplier is invented
— "approaching" has an exact meaning for a whole-number rule: *one more loss
breaks it*. The percentage ladder is untouched and still wins where it fires
earlier (limit 10 still warns at 8, not 9). Message becomes *"One more loss
breaks your consecutive-loss rule: 3 losses in a row (your stop point: 4)."*

Pinned by `backend/tests/test_constitution_consecutive_losses.py` (11 tests).

## Replay evidence for the surviving rule

The book declares no rules (`--no-rules`), so these are computed by applying a
declared limit to the same 189 sessions / 912 positions, net −₹141,494.

| declared limit | warns at | sessions warned | sessions breached | trades taken after breach | **realized P&L of those trades** |
|---|---|---|---|---|---|
| 3 | 2 | 117 (62%) | 58 | 141 | **−₹11,117** |
| **4** | **3** | **58 (31%)** | **23 (12%)** | **61** | **−₹2,492** |
| 5 | 4 | 23 | 11 | 26 | −₹1,363 |
| 6 | 5 | 11 | 5 | 8 | −₹3,099 |
| 8 | 7 | 4 | 1 | 0 | ₹0 |

At a limit of 4: of the 61 trades taken after the breach, **35 lost and 26 won**.
Worst session after a breach: 2025-09-16, −₹4,822 over 4 trades. The trader
stopped at the warning in 19 of 58 warned sessions, and at the breach in 4 of 23.

**Stated honestly: −₹2,492 is 2% of the book's net loss, and it is the realized
P&L of trades actually taken after the line the trader drew — not "what you would
have saved".** Knowing that would require knowing what they would have done
instead. 26 of those 61 trades won.

**The consequence for expectations: a consecutive-loss rule at any setting
governs a small share of this trader's losses.** It is worth having because the
trader set it, not because the damage concentrates there.

## Files touched

| file | change |
|---|---|
| `backend/app/services/detector_registry.py` | `DetectorSpec` and `PatternCopy` removed; retirement note in place of the spec |
| `backend/app/services/behavior_engine.py` | `_detect_consecutive_loss_streak` (74 lines) removed; dropped from `_STRATEGY_SUPPRESSED` and `_CONSTITUTION_PAIRS`; `max_consecutive_losses` rule gains the one-away rung |
| `backend/app/tasks/trade_tasks.py` | removed from both `_DEDUP_HOURS` maps |
| `backend/app/services/cooldown_service.py` | removed from the trigger→cooldown map; **kept** in `HIGH_DISTRESS_TYPES`, which reads stored rows |
| `backend/app/api/analytics.py` | removed from the `REVENGE` day-tag set |
| `backend/app/tasks/report_tasks.py` | removed from `_PATTERN_LABELS` |
| `backend/tests/test_pattern_contract.py` | added to `RETIRED_PATTERN_NAMES` |
| `src/contexts/AlertContext.tsx` | removed from `BACKEND_TO_FRONTEND_TYPE`; **display name kept** for stored rows |
| `src/lib/demoData.ts` | fixtures no longer name a dead pattern |

Four tests were deleted with their subject (`test_no_alert_on_winner`,
`test_caution_on_3_losses`, `test_danger_on_5_losses`,
`test_streak_resets_on_winner`) and a note left in their place.

## Known limitations, recorded not closed

1. **`danger_zone_service` still makes the deleted claim.** It reads
   `consecutive_loss_caution` / `consecutive_loss_danger` independently of the
   engine and returns *"5 consecutive losses. Take a break."* at `DANGER`,
   wired live through `/api/danger-zone` and the post-sync path in
   `api/zerodha.py`. **That is the same count-based assertion this decision
   removed, on a different surface.** Not changed here — it is a separate
   service with its own thresholds and API contract, and it needs its own
   review. **The two thresholds stay in `trading_defaults.py` because of this
   reader**; they are dead to the engine but not to the product.
2. **`daily_trades` has the identical unreachable-warning defect.**
   `ceil(0.80 × 3)` is 3 for a trade limit as well. Left for the
   `overtrading_burst` / `daily_overtrading` review, which owns that rule.
3. **The surviving rule reports a count, not money.** The review found loss size
   carries a real signal (2.6 SE on "did the trader stop") where the count does
   not. Adding the run's P&L to the rule's message was not done — out of scope
   for a retirement.
4. **No replay was re-run after the deletion.** The change removes a detector
   and adds a rung to a rule that cannot fire on a `--no-rules` book, so the
   expected delta is exactly −78 alerts and nothing else. That is an
   expectation, not a measurement.
