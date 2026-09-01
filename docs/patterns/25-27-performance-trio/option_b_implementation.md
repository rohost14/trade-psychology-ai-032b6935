# Option B — implemented

**1 Sep 2026.** Approved and shipped. This is the before/after record.

Retire `time_of_day_bias` as an alerting detector and remove `danger_hours`,
`danger_days`, `best_hours` and `best_days` as trader-facing behavioural or
recommendation signals — **without deleting the underlying learning and
storage**, which are preserved for future research.

---

## 1. What was verified before touching anything

**All-detector baseline on the real book: 457 firings, sha256 `5af4ec6bfd150de9`.**

## 2. What changed — 17 files

### Backend — the detector

| file | before | after |
|---|---|---|
| `behavior_engine.py` | `_detect_time_of_day_bias` — a `caution` alert at `notification_level=1` on entering a learned danger hour | **method deleted**, replaced by the retirement note carrying the measurements |
| `detector_registry.py` | `DetectorSpec` + `PatternCopy` | both removed; **17 → 16 detectors, 23 → 22 pattern types**, 6 aliases unchanged |
| `trading_defaults.py` | `tod_bias_min_sessions: 30`; `result['danger_hours']` put in both the profile and cold-start branches | threshold gone, both puts gone |
| `threshold_resolution.py` | `put("danger_hours", …)` in the profile path and the cold-start path | both gone; **the provenance note it carried was kept**, because "an EMPTY learned value is not personal knowledge" applies to every learned key, not just this one |
| `tests/test_pattern_contract.py` | — | `time_of_day_bias` added to `RETIRED_PATTERN_NAMES` |

### Backend — the trader-facing consumers

| file | before | after |
|---|---|---|
| `ai_personalization_service.py` `_calculate_predictive_windows` | built a `time_warning` 15 min before each danger hour and a `day_warning` at 09:10 on each danger day | **symbol windows only** |
| `ai_personalization_service.py` `get_predictive_alert` | *"⚠️ 12:00 is YOUR danger hour (30% win rate). Trade carefully!"* and *"⚠️ Friday is YOUR worst day (36% win rate). Consider smaller positions."* | **gone**; the check no longer reads the clock at all, only the proposed symbol |
| `ai_personalization_service.py` `get_personalized_insights` | *"Your Danger Hour"* card, recommendation *"Avoid trading at 12 PM (IST)"*; *"Your Best Hour"* card, recommendation *"Focus your trading around 2 PM (IST)"*; flat `danger_hours` / `danger_days` arrays | **all four gone**; `revenge_window_minutes` is the surviving flat field |
| `ai_personalization_service.py` | `_fmt_hour` helper | removed — its only two callers were the copy above |
| `api/personalization.py` `/time-analysis` | returned `hourly_breakdown`, `daily_breakdown` **and the four classified lists** | **breakdowns only** — raw statistics with no classification attached |
| `daily_reports_service.py` | `focus["avoid_times"] = ["12:00 IST", "15:00 IST"]` | key stays in the contract, **initialised `[]` and never filled** |
| `daily_reports_service.py` | `_generate_day_warning` — *"Friday is historically your WORST trading day (36% win rate). Consider smaller size or sitting out."* and the BEST-day mirror | **method removed**; `day_warning` no longer in the briefing payload |
| `daily_reports_service.py` | watch-out *"Avoid 12:00–12:59 IST — your win rate drops to 30% in this window"* | **gone**; symbol watch-outs unchanged |
| `intent_tasks.py` | morning push appended *"⚠️ Friday is your worst trading day historically — trade smaller."* | **gone**; the rules line is unchanged |
| `entry_detectors.py` | listed `time_of_day_bias` among the not-entry-decidable | note updated |

### Frontend

| file | before | after |
|---|---|---|
| `PredictiveContextStrip.tsx` | **"Danger hour"** — *"You historically lose at 14:00. Trade smaller or wait it out."* and **"{day} — danger day"** — *"Win rate below 35% on Fridays historically."* | **both rows removed**; the strip keeps `revenge_window` and `problem_symbol`. `Clock` and `AlertTriangle` imports dropped with them |
| `PredictiveContextStrip.tsx` | `chk.alert.type \|\| 'danger_hour'` | `\|\| 'problem_symbol'` |
| `Reports.tsx` | the `day_warning` banner, red or green by `is_danger_day` | **removed** |
| `guestMode.ts` | `danger_time` and `best_time` insight cards, and a `time_warning` predictive alert | **removed** — guest fixtures double as smoke fixtures and must mirror the real endpoint |
| `AlertContext.tsx` | `'time_of_day_bias': 'Time-of-day pattern'` | **kept**, with a comment. It was never in `BACKEND_TO_FRONTEND_TYPE`, so nothing had to be removed there |

### The timezone defect went with it

`PredictiveContextStrip.tsx` was **the only file in the codebase** comparing
IST-derived values against browser-local time:

```js
const nowHour = new Date().getHours();   // browser local
if (ins.danger_hours?.includes(nowHour)) // IST-derived
const today = days[new Date().getDay()]; // browser local
if (ins.danger_days?.includes(today))    // IST-derived
```

Both comparisons are deleted. `EodComparisonCard`, `MarketRail` and
`MorningIntentCard` already convert first; `guestMode.ts` uses
`new Date().getHours()` only to *generate* a fixture and compares nothing;
`my_record.py` is server-side IST throughout. **No timezone regression remains.**

---

## 3. What was deliberately NOT changed

**The learner and its storage.** `_learn_time_patterns` still computes all four
classified lists plus `hourly_breakdown` and `daily_breakdown`;
`_store_learned_patterns` still persists them at
`ai_personalization_service.py:142`; the nightly 18:15 IST beat is untouched.
Three tests pin this — if the data a future evidence pass needs is ever thrown
away, they fail.

**`win_rate_collapse` and `strategy_breakdown`.** Neither reads `time_patterns`;
both depend on `detected_patterns["baseline"]`, written by a different service on
a different path. Pinned untouched, including a source-level check that neither
detector body mentions any of the four signals.

**`api/my_record.py`.** Excluded by instruction, recorded as a separate product
review in `PENDING_AND_TODO.md`, and pinned untouched by a test.

**One consumer left in place and raised instead:**
`daily_reports_service._calculate_readiness_score` subtracts 20 from a numeric
0–100 score on a learned danger day. Removing it changes the score and can flip
its status band — a product behaviour change outside this decision's scope. It
is the only site in the product still reading a retired list, and a test pins
that it stays the only one. Detail in `PENDING_AND_TODO.md`.

---

## 4. Verification

| check | result |
|---|---|
| all-detector replay, real book | **457 firings, sha256 `5af4ec6bfd150de9` — byte-identical to the baseline** |
| per-detector counts | unchanged: `revenge_trade` 182, `adding_to_adverse_position` 64, `no_stoploss` 52, `same_symbol_obsession` 49, `fomo_entry` 32, `martingale_behaviour` 26, `premium_loss_event` 17, `rapid_reentry` 14, `overtrading_burst` 13, `post_loss_recovery_bet` 7, `end_of_session_mis_panic` 1 |
| backend tests | **1,882 passed** (was 1,854; +28 from the new retirement suite) |
| frontend tests | **102 passed** |
| typecheck | clean |
| lint | **0 errors**, 71 warnings — unchanged from before |
| backend boot | 230 routes |

**The zero delta on the reference book is the expected result, not a null
finding.** A CSV tradebook carries no `UserProfile`, so `danger_hours` was always
empty in replay and the detector could never fire there. That artefact is exactly
what made the first review call it "never fired". **For a real trader with 30+
sessions it was live**, and supplying this book's own baseline reproduces the
equivalent of **81 alerts** — 62% of which no other detector saw, so the volume
was additive rather than duplicated.

**Removed for a real trader:** the alert, the dashboard strip row, the daily
report's `avoid_times` line, its day-warning banner, its hourly watch-out, the
morning push line, and the two insight cards.

---

## 5. Two failed test-authoring attempts, recorded

**The retirement notes quote the predicates they replaced**, so a source-scanning
test matches its own explanation. Both the daily-report scan and the strip's
timezone check had to strip comment lines before asserting. This narrows what the
tests inspect; it does not weaken what they assert. It is the same trap that
appeared in the `early_exit`, `winning_streak_overconfidence` and
`options_premium_avg_down` retirements, and it is now three for three.

---

## 6. The distinction this retirement turns on

**Insufficient evidence is not proof that time-of-day effects do not exist.**
Intraday seasonality is real in markets and plausible in traders. What is retired
is *this method of finding it on this book*, and every trader-facing claim built
on its output.

The four signals do not license the same statement, and the record keeps them
apart:

| signal | what the measurement licenses |
|---|---|
| `danger_hours` | **measured and contradicted** — flagged, chance-reproducible (p = 0.309), no persistence, ranks uncorrelated (rho = +0.071) |
| `best_hours` | **measured, unstable** — one hour (14:00), present in the second half only |
| `danger_days` | **measured, flat** — zero on the full book; weekdays span 36.0–42.6% around a 39.5% book rate. The first half alone flagged Friday and Wednesday and neither survived |
| `best_days` | **unvalidated, not invalidated** — zero firings at every slice, which is no evidence either way |

And the correction stays in the record because it changed the verdict's
seriousness: the first review called this detector mis-wired and dead on arrival,
claiming `detected_patterns["time_patterns"]` had no writer. **That was wrong.**
It is written on a nightly beat. The detector was live and firing on a signal
measured here as chance.
