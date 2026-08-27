# Pattern #6 — retirement impact check and deletion plan

27 Aug 2026. **Assessment only. No code changed.** Decision taken: retire
`profit_giveaway` as a behavioural detector, keep the underlying measurements.

**Verdict: DELETE / RETIRE as a behavioural detector, measurement retained.**

---

## The evidence for retirement

| finding | figure |
|---|---|
| sessions containing a giveback at all | **181 of 189 (96%)** |
| sessions where it would fire — **observed vs shuffled order** | **49 vs 56.3 expected** (ratio 0.87 — fires *less* than chance) |
| **total money given back — actual vs shuffled** | **₹624,839 vs ₹616,891** (ratio 1.01) |
| house-money test (risk per trade after the peak) | **failed** — fell in 54% of sessions, rose in 30%; median ₹7,315 → ₹6,737 |
| break-even test (crossing zero vs size-matched loss that does not) | **failed** — 0.6 SE stopped, 0.2 SE next-bigger, against a ~1.4 floor |
| share of a post-peak giveback in its single biggest losing trade | **median 77%**; 41% are ≥80% one trade |

The giveback is arithmetic: the peak is by definition the maximum of the running
curve, so any session not ending at its maximum has one. The trader's ordering
contributes nothing to its size, and every mechanism the alert is premised on is
refuted or absent on this book. Full working in `giveback_research.md`.

**Caveat kept on the record: this is one trader.** The literature is
population-level, and a trader who *does* escalate after a peak would show it.
We act on the evidence we have.

---

## Impact check

### Backend — the detector and its wiring

| reference | disposition |
|---|---|
| `behavior_engine.py` `_detect_profit_giveaway` (~170 lines) | **remove** |
| `behavior_engine.py:45` docstring entry "23. profit_giveaway" | **remove** (numbering already noted as historical) |
| `behavior_engine.py:1382` comment "owned by profit_giveaway detector" | **reword** — it explains why `overtrading_burst` has no gains-erosion check |
| `detector_registry.py:191` `DetectorSpec` | **remove** |
| `detector_registry.py:312` `PatternCopy` | **remove** |
| `trade_tasks.py:116-119` `_pattern_dedup_key` branch | **remove** (added 27 Aug, `3293f93`) |
| `trade_tasks.py:140` `_WORSEN_METRIC` entry | **remove** |
| `trade_tasks.py:1103, 1406` `_DEDUP_HOURS` entries (both maps) | **remove** |
| `entry_detectors.py:25, 45` comments naming it as outcome-dependent | **reword**, keep the point |
| `trading_defaults.py:209` `profit_giveaway_caution_pct` | **remove** — detector-only, no other reader |

### Backend — cooldown / intervention

**No references at all.** `profit_giveaway` is absent from
`cooldown_service.COOLDOWN_TRIGGERS`, from `HIGH_DISTRESS_TYPES`, from
`danger_zone_service` in every form, and from `notification_rate_limiter`.
Nothing to unwire.

### Backend — consolidation / family

**No references.** Not in `_FAMILIES`, not in `_STRATEGY_SUPPRESSED`, not in
`_CONSTITUTION_PAIRS`. Nothing to unwire.

### `death_spiral` — measured, not assumed

`death_spiral` reads `spec.nature` off `BY_NAME`; `profit_giveaway`'s nature is
`emotional`. Removing it removes one potential domain contributor.

**Measured on the stored replay: on the 20 days carrying a `profit_giveaway`
alert, the number that would LOSE their second domain is ZERO.** Thirteen other
detectors carry `emotional` (`revenge_trade`, `overtrading_burst`,
`size_escalation`, `fomo_entry`, `same_symbol_obsession`, `panic_exit`,
`rapid_reentry`, `direction_instability`, `options_premium_avg_down`,
`winning_streak_overconfidence`, `expiry_day_overtrading`, `opening_5min_trap`,
`end_of_session_mis_panic`).

*Estimate note: the stored replay predates the v2.0.0 widening, so the day count
is the old 20 rather than 48. The conclusion — that `emotional` is
over-supplied — does not depend on that.*

### Analytics and reporting

| surface | effect |
|---|---|
| `/api/analytics/behaviour-cost` | **generic** — groups RiskAlerts by `trigger_completed_trade_id`, no hardcoded pattern list. Simply stops gaining new rows; historical rows still counted |
| `/api/risk/patterns` (catalogue) | built from `all_pattern_types()` — the entry disappears, which is correct |
| `report_tasks.py:298` `_PATTERN_LABELS` | **KEEP** — renders stored rows in weekly reports; `.get(type, fallback)` so it is safe either way |
| `prometheus_metrics.py:260-272` never-fired gauge | denominator shrinks by one automatically, no change needed |
| `daily_reports_service.py:318` `peak_pnl` | **untouched** — computed from its own timeline, not from this detector |

### Frontend

| reference | disposition |
|---|---|
| `AlertContext.tsx:146` `BACKEND_TO_FRONTEND_TYPE` | **remove** — the vocabulary contract test fails otherwise |
| `AlertContext.tsx:186` display name | **KEEP** — stored alert rows still carry the type; a missing key renders a title-cased raw key |
| `AlertDetailSheet.tsx:89` detail case | **KEEP** — same reason (and see the `erosion_pct` bug below) |
| `BehaviourLead.tsx:40`, `BehaviourCostCard.tsx:20` labels | **KEEP** — label maps over whatever the API returns for historical data |
| `types/patterns.ts:31` union member | **KEEP** — historical alerts are still typed |
| `demoData.ts:1378-1387` catalogue fixture entry | **remove** — guest fixtures mirror the real API, and the catalogue will no longer contain it |

### Tests and fixtures

| file | disposition |
|---|---|
| `tests/test_profit_giveaway.py` (37 tests) | **delete** — its entire subject is removed. Say so in the commit |
| `tests/test_pattern_contract.py` | **add** `"profit_giveaway"` to `RETIRED_PATTERN_NAMES` |
| `tests/test_entry_detectors.py:164` | remove from the "never asked at entry" tuple; the test's subject survives |
| `tests/test_same_symbol_obsession.py:236` | remove from the `_WORSEN_METRIC`-intact parametrize; two entries remain |
| `tests/test_engine_hygiene.py:48` | **comment only** — a historical note about an inline default. Leave it |
| `tests/test_threshold_resolution.py` | **DO NOT TOUCH** — see below |

---

## What must NOT be removed

### 1. `peak_pnl`, `drawdown_from_peak`, `max_drawdown` — 11 independent readers

None of these belong to this detector. Verified readers:

| reader | uses |
|---|---|
| `api/coach.py:311-313` | peak and drawdown in the coach's session summary |
| `services/baseline_service.py:288-303, 377` | `typical_peak_pnl` metric and the drawdown distribution |
| `services/daily_reports_service.py:318` | `peak_pnl` in the daily report timeline |
| `api/analytics.py:457-464, 785-814, 903, 1291` | `max_drawdown` on several endpoints |
| `services/ai_service.py:461, 552` | `max_drawdown` in generated commentary |
| `services/pattern_prediction_service.py:129, 241` | `drawdown_from_peak` |
| `services/state/session_state.py:51-93` | the live session state object |
| `api/reports.py:225` | `drawdown_from_peak` |

**All stay untouched. `session_facts` is not modified at all.**

### 2. `profit_giveaway_min_peak` / `profit_giveaway_min_erosion` — the capital-ratio rung

These two are **the only entries in `_CAPITAL_RATIOS`**
(`threshold_resolution.py:634-639`). Deleting them empties Rung 4 of the
resolution ladder — the mechanism that converts absolute rupee floors into
ratios of the trader's capital — and removes its **only remaining test
vehicle**. `test_threshold_resolution.py` defines
`CAPITAL_KEYS = ("profit_giveaway_min_peak", "profit_giveaway_min_erosion")` and
its own docstring says *"the property under test is the conversion, not the
key"*; the third key, `revenge_min_loss_inr`, was already deleted in August.

They are also exactly the two values a declared give-back rule would need.

**Recommendation: keep all four keys** (`_min_peak`, `_min_erosion`, and their
two `_pct_capital` ratios), with a comment recording that they currently have no
detector reader and exist to hold the capital-ratio rung and its test. Removing
`profit_giveaway_caution_pct` is safe — it is the only one that was purely a
tier.

*This is the same call made for `daily_trade_danger` in Pattern 5 and
`consecutive_loss_caution/_danger` in Pattern 4: a threshold with no detector
reader is not automatically dead.*

---

## The smallest clean deletion

**Nine files.**

| # | file | change |
|---|---|---|
| 1 | `app/services/behavior_engine.py` | remove `_detect_profit_giveaway`; drop the docstring line; reword the `overtrading_burst` cross-reference |
| 2 | `app/services/detector_registry.py` | remove the spec and its copy; add a retirement note with the evidence |
| 3 | `app/tasks/trade_tasks.py` | remove the dedup-key branch, the `_WORSEN_METRIC` entry, both `_DEDUP_HOURS` entries |
| 4 | `app/core/trading_defaults.py` | remove `profit_giveaway_caution_pct`; annotate the four surviving keys |
| 5 | `app/services/entry_detectors.py` | reword two comments |
| 6 | `tests/test_pattern_contract.py` | add to `RETIRED_PATTERN_NAMES` |
| 7 | `tests/test_entry_detectors.py`, `tests/test_same_symbol_obsession.py` | drop it from two lists |
| 8 | `tests/test_profit_giveaway.py` | delete the file — subject removed |
| 9 | `src/contexts/AlertContext.tsx`, `src/lib/demoData.ts` | drop the `BACKEND_TO_FRONTEND_TYPE` key and the catalogue fixture entry |

**Counts after: 26 detectors / 32 pattern types** (from 27 / 33).

**Expected alert delta on the reference book: −100 `profit_giveaway` alerts
across 48 sessions, and nothing else.** `death_spiral` unchanged (measured),
`behaviour-cost` keeps its history, no cooldown or family wiring exists to break.

## What replaces it

Nothing in the engine. The measurement is already available without a detector:
`daily_reports_service` and Analytics compute peak and drawdown from the trades
themselves, so *"you gave back ₹X this year, ₹Y of it on days that finished
red"* remains true and reportable.

**If it is ever to interrupt a session again, it must be against a commitment
the trader declared** — a give-back stop in the constitution. That field does
not exist; adding it is a product decision, not an engine one. The two
capital-relative thresholds being kept are what it would use.

## Recorded, still not fixed

- `AlertDetailSheet.tsx:92` renders `erosion_pct` as `${fmtN(x)}%` while the
  context stores a **ratio** — a 51% giveback displays as "0.5%". Pre-existing.
  It will now only ever affect historical rows, which lowers its priority but
  does not make it correct.
- `early_exit` claims the opposite about this trader (banking gains too early)
  and the risk-falls-after-peak finding is consistent with it. Read the two
  together at that review.
- The shuffle control (permute a session's trade P&Ls, preserving the multiset)
  is now a standing first test for any detector keyed on a running total.
