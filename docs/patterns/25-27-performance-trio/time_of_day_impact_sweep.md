# Option B — complete impact sweep before implementation

**1 Sep 2026. SWEEP ONLY. NO CODE WRITTEN.**

Approved: remove the hour-based signal from trader-facing behavioural/decision
surfaces; keep the learning and storage for future research.

---

## 1. The four signals, measured SEPARATELY

Instructed not to assume the other three are invalid because `danger_hours` is.
Each was measured with its own filter (`<35%` danger / `>55%` best, `n >= 5`),
split across the two halves of the book.

| signal | full book | first half | second half | **in BOTH** | chance p |
|---|---|---|---|---|---|
| `danger_hours` | `[12, 15]` | `[11, 12, 15]` | `[]` | **NONE** | **0.309** |
| `best_hours` | `[14]` | `[]` | `[14]` | **NONE** | 0.138 |
| `danger_days` | `[]` | `[Friday, Wednesday]` | `[]` | **NONE** | n/a |
| `best_days` | `[]` | `[]` | `[]` | **NONE** | n/a |

**Not one of the four produces a signal present in both halves.**

### What each result actually licenses — they are not the same finding

**`danger_hours` — MEASURED AND CONTRADICTED.** Flags 2 hours; chance reproduces
2+ hours 31% of the time; nothing survives to the second half; descriptive ranks
correlate at rho = 0.071. This is positive evidence against.

**`best_hours` — MEASURED, UNSTABLE.** One hour (14:00) flagged, and only in the
second half — absent from the first. p = 0.138 is not damning on its own, but a
signal that appears in one half and not the other cannot support a claim about a
trader's habits.

**`danger_days` — MEASURED, PRODUCES NOTHING HERE, UNSTABLE WHEN IT DOES.**
Zero on the full book. But the first half alone flagged **Friday and Wednesday**,
so the methodology does fire on subsets and those flags did not survive. The
day-of-week distribution is flat:

| day | n | win rate |
|---|---|---|
| Monday | 137 | 41.8% |
| Tuesday | 140 | 41.3% |
| Wednesday | 141 | 36.0% |
| Thursday | 173 | 42.6% |
| Friday | 135 | 37.8% |

Everything sits within a few points of the 39.5% book rate; nothing approaches
the 35% cut on the full sample.

**`best_days` — UNVALIDATED, NOT INVALIDATED.** It fires **zero times at every
slice**. That is *no evidence either way* about whether the concept works — this
book simply never triggers it. **Marking it unvalidated rather than concluding
anything**, as instructed.

> **A footnote worth recording:** the day breakdown shows **Sunday, n = 14**.
> Indian equity/F&O markets do not trade Sundays. Either these are a special
> session or there is a timestamp defect. **Not investigated here** — recorded.

---

## 2. Every consumer — the complete list

The sweep found **more than the design pass did**, including a whole second
implementation.

### Backend — producer and storage (KEEP, per the approval)

| file | role |
|---|---|
| `ai_personalization_service.py:146-240` `_learn_time_patterns` | computes all four signals + `hourly_breakdown` / `daily_breakdown` |
| `ai_personalization_service.py:142` `_store_learned_patterns` | persists to `detected_patterns` |
| `intent_tasks.py:291` + `celery_app.py:207` | nightly 18:15 IST refresh |

### Backend — trader-facing consumers (CHANGE)

| file:line | what it does |
|---|---|
| **`behavior_engine.py:3399-3430`** | `_detect_time_of_day_bias` — the `caution` alert |
| **`threshold_resolution.py:509-513, 682`** | puts `danger_hours` into the threshold set (+ cold start) |
| **`trading_defaults.py:512-513, 538`** | same, the parallel resolver |
| **`api/personalization.py:144-147`** | `/time-patterns` returns all four |
| **`ai_personalization_service.py:698-710`** | `/insights` flattens to `danger_hours: list[int]`, `danger_days: list[str]` |
| **`ai_personalization_service.py:476-500`** | `_calculate_predictive_windows` builds windows FROM danger hours/days |
| **`ai_personalization_service.py:565-585, 630-655`** | further readers — worst/best hour narratives |
| **`daily_reports_service.py:475-476`** | `focus["avoid_times"] = ["12:00 IST", …]` — **a prescription in the daily report** |
| **`daily_reports_service.py:650-665, 757-758, 886`** | danger/best days and hours in report copy |
| **`intent_tasks.py:80`** | morning intent push includes today if it is a "danger day" |

### Frontend (CHANGE)

| file:line | what it does |
|---|---|
| **`PredictiveContextStrip.tsx:87-105`** | *"Danger hour — You historically lose at 14:00. Trade smaller or wait it out."* and the same for days |

### NOT in scope, but found and must be stated

**`api/my_record.py:205-270` is a SECOND, INDEPENDENT hourly implementation.**
It does not read `time_patterns` at all — it computes from trades directly.

```
"Right now is your weakest window on NIFTY: 5 trades, 20% win rate, −₹14,270 net."
```

| | `time_patterns` path | `my_record.py` |
|---|---|---|
| timezone | IST-derived, compared to **browser-local** in the strip | **`now_ist.hour`** — correct |
| sample gate | `n >= 5`, invisible to the trader | `MIN_SAMPLE = 5`, and the count is **in the sentence** |
| delivery | **push** — alert, dashboard strip, daily report | **pull** — the trader opens My Record and asks |
| claim | *"You historically lose at 14:00"* | *"Right now is your weakest window… 5 trades"* |

**It carries the same instability risk** — "weakest window" is a ranking, and
rankings are what rho = 0.071 says do not hold. But it is materially different in
product terms: the trader asked, and the answer states its own sample.

**I am not proposing to change it**, because it is outside the approved scope and
the push/pull distinction is defensible. **Recording it so the inconsistency is a
decision rather than an oversight.**

---

## 3. Timezone — the requirement, and what satisfies it

**Only `PredictiveContextStrip.tsx` compares an IST-derived hour to browser-local
time:**

```js
const nowHour = new Date().getHours();        // browser local
if (ins.danger_hours?.includes(nowHour))       // IST-derived
const today = days[new Date().getDay()];       // browser local
if (ins.danger_days?.includes(today))          // IST-derived
```

Every other component already converts first — `EodComparisonCard`, `MarketRail`
and `MorningIntentCard` all use `ist.getHours()`. **The correct pattern exists in
the codebase; this file is the sole outlier.**

**After the change both comparisons are deleted**, so no IST-derived hour or day
is compared to browser-local time anywhere. `guestMode.ts:269-270` uses
`new Date().getHours()` but only to *generate* a demo fixture — it compares
nothing — and `my_record.py` is server-side IST throughout.

---

## 4. Exact files that change, and the before/after

| # | file | change | before → after |
|---|---|---|---|
| 1 | `behavior_engine.py` | retire `_detect_time_of_day_bias` | a `caution` alert at `notification_level=1` on entering a "danger hour" → **nothing** |
| 2 | `detector_registry.py` | remove `DetectorSpec` + `PatternCopy`; keep display name | 17 → **16** detectors, 23 → **22** pattern types |
| 3 | `trading_defaults.py` | remove `tod_bias_min_sessions`; stop putting `danger_hours` | threshold present → absent |
| 4 | `threshold_resolution.py` | remove the `danger_hours` put (2 sites) | same |
| 5 | **`PredictiveContextStrip.tsx`** | remove the `danger_hour` and `danger_day` items | *"You historically lose at 14:00. Trade smaller or wait it out."* → **item not rendered**; the strip keeps its other items |
| 6 | `api/personalization.py` | stop returning the four keys from `/time-patterns` | four arrays → `hourly_breakdown` / `daily_breakdown` only |
| 7 | `ai_personalization_service.py` | stop returning `danger_hours`/`danger_days` from `/insights`; drop the narrative readers at 565-585, 630-655 | flattened lists → absent |
| 8 | `ai_personalization_service.py` | `_calculate_predictive_windows` no longer builds windows from danger hours/days | predictive windows include hour/day windows → **only the non-time windows remain** |
| 9 | `daily_reports_service.py` | remove `avoid_times`, danger/best day and hour copy | *"Avoid: 12:00 IST, 15:00 IST"* → **line absent** |
| 10 | `intent_tasks.py:80` | morning push no longer flags a "danger day" | day-based line → absent |
| 11 | `AlertContext.tsx` | remove routing; keep display name for stored rows | — |
| 12 | tests | retirement suite; repin counts in 9 files | — |

**Kept, deliberately:** `_learn_time_patterns` still computes all four signals and
`_store_learned_patterns` still persists them. `hourly_breakdown` and
`daily_breakdown` remain available via `/time-patterns` as raw statistics with no
classification attached — **no consumer renders them today**, so keeping them
creates no trader-facing interpretation.

**Expected firing impact on the reference book: zero.** The detector already
fires 0 in replay for want of a profile. For real traders with 30+ sessions this
removes the 81-equivalent alerts, the dashboard item, the daily-report lines and
the morning-push line.

---

## 5. Open questions I am NOT deciding

1. **`best_days` is unvalidated, not invalidated.** Removing its surface follows
   from removing the others, but the evidence for it specifically is *absent*,
   not *against*. Say if you want it treated differently.
2. **`my_record.py`'s "weakest window"** makes a ranking claim on the same kind of
   data, correctly time-zoned and with its sample stated, on a pull surface.
   Out of scope; flagged.
3. **`hourly_breakdown` / `daily_breakdown` stay in the API** with no reader. If
   a future surface renders them, the stability finding applies again.
4. **Sunday, n = 14** in the day breakdown. Unexplained.

## 6. Confirmations

**`win_rate_collapse` — untouched.** **`strategy_breakdown` — untouched.** Neither
reads `time_patterns`; both depend on `detected_patterns["baseline"]`, written by
a different service on a different path. Nothing in this list touches either.

**No new methodology, threshold or recommendation is introduced anywhere.**
