# Pattern #6 — `profit_giveaway` · **RETIRED**

27 Aug 2026. Retired as a behavioural detector. **The measurements underneath it
are kept.** Decision taken on the evidence below; impact checked in
`retirement_impact.md`, evidence in `giveback_research.md`. The v2.0.0 detector
this replaces is documented in `profit_giveaway_review.md` and in git history
(`2202912`, `3293f93`).

The engine is now **26 detectors / 32 pattern types**.

---

## Why

**A drawdown from the session high-water mark is arithmetic, not behaviour.**
The peak is by definition the maximum of the running curve, so any session not
ending at its maximum has given something back. **181 of 189 sessions (96%)
contain one.**

The decisive test — the same one that retired Pattern 4 — shuffles each
session's trade P&Ls. Same trades, same day, same count, different order.
Behaviour lives in the order the trader chose to act in.

| | observed | chance (shuffled) | ratio |
|---|---|---|---|
| sessions where it would fire | **49** | **56.3** | **0.87** |
| …via green-to-red | 40 | 45.7 | 0.88 |
| …via the percentage line | 16 | 17.2 | 0.93 |
| **total money given back** | **₹624,839** | **₹616,891** | **1.01** |

> The money given back is chance to within 1%, and the detector fires **13% less
> often than a random reordering of the same trades would**. The trader's
> ordering contributes nothing.

**Every mechanism it was premised on also failed.**

| test | prediction | result |
|---|---|---|
| **House money** (Thaler & Johnson 1990) | risk per trade RISES after the peak | **failed** — fell in 54% of sessions, rose in 30%; median ₹7,315 → ₹6,737 |
| **Break-even effect** (same paper) | crossing zero changes behaviour vs an equal loss that does not | **failed** — 0.6 SE on stopping, 0.2 SE on next-position-bigger, against a ~1.4 floor |

The median giveback puts **77% of its loss in a single trade** (41% are ≥80% one
trade) — which is what a losing trade is. The peak preceding it changes nothing
about what happened.

**Caveat kept on the record: this is one trader.** The literature is
population-level, and a trader who *does* escalate after a peak would show it in
the house-money test. We acted on the evidence we have.

## What was removed

| file | change |
|---|---|
| `behavior_engine.py` | `_detect_profit_giveaway` — 188 lines |
| `detector_registry.py` | the `DetectorSpec` and its `PatternCopy`, replaced by a retirement note carrying the evidence |
| `trade_tasks.py` | the episode dedup-key branch, the `_WORSEN_METRIC` entry, both `_DEDUP_HOURS` entries |
| `trading_defaults.py` | `profit_giveaway_caution_pct` (a pure severity tier) |
| `entry_detectors.py` | two comments naming it as outcome-dependent |
| `tests/test_profit_giveaway.py` | **deleted** — 37 tests whose entire subject is gone |
| `tests/test_pattern_contract.py` | added to `RETIRED_PATTERN_NAMES` |
| `tests/test_entry_detectors.py`, `tests/test_same_symbol_obsession.py` | dropped from two lists |
| `src/contexts/AlertContext.tsx` | the `BACKEND_TO_FRONTEND_TYPE` key |
| `src/lib/demoData.ts` | the pattern-catalogue fixture entry |

## What was deliberately kept

**1. The session measurements — eleven independent readers.** `peak_pnl`,
`drawdown_from_peak` and `max_drawdown` stay in `session_facts`, which was **not
modified at all**. Readers: `api/coach.py`, `baseline_service`
(`typical_peak_pnl` and the drawdown distribution), `daily_reports_service`,
four `api/analytics.py` endpoints, `ai_service`, `pattern_prediction_service`,
`state/session_state.py`, `api/reports.py`.

**2. The four capital-relative threshold keys.** `profit_giveaway_min_peak`,
`profit_giveaway_min_erosion` and their two `_pct_capital` ratios have **no
detector reader any more and are kept anyway**: they are the only entries in
`_CAPITAL_RATIOS`, so deleting them would empty rung 4 of the resolution ladder
and remove its only remaining test vehicle (`test_threshold_resolution.py`
defines `CAPITAL_KEYS` as exactly these two and says the property under test is
the conversion, not the key). They are also the two values a declared give-back
stop would need.

**3. Everything that renders stored rows.** The frontend display name, the
`AlertDetailSheet` case, `types/patterns.ts`, `BehaviourLead`,
`BehaviourCostCard` and `report_tasks._PATTERN_LABELS` all stay — historical
alerts still carry the type, and a missing key renders a title-cased raw key.

## Verified after the deletion

| check | result |
|---|---|
| detector method, spec and vocabulary entry gone | **PASS** — 26 detectors / 32 pattern types |
| `peak_pnl` / `drawdown_from_peak` / `max_drawdown` still on `SessionFacts` | **PASS**, `session_facts` untouched |
| `death_spiral` unchanged | **PASS** — no reference to it; 13 other detectors carry `emotional`, and 0 replay days lose their second domain |
| no other detector's dedup or re-arm wiring moved | **PASS** — `_WORSEN_METRIC` is now `constitution_violation`, `martingale_behaviour`, `premium_loss_event`; the `constitution_violation` and `same_symbol_obsession` keys are intact |
| historical rows readable | **PASS** — FE name, type union and report label all present |
| capital-ratio rung intact | **PASS** — resolves ₹6,000 at ₹200,000 capital, `Source.CAPITAL` |

## The measurement, kept and now shown

`daily_reports_service._generate_emotional_journey` already computed
`peak_pnl`, `trough_pnl` and `final_pnl` — and `Reports.tsx` rendered only the
timeline, so the numbers were computed and thrown away. Three derived fields
were added with the retirement (`given_back`, `given_back_pct`,
`finished_green`) and a **Peak vs close** block now renders them.

All three are arithmetic on values that already existed. **No threshold is
involved**, and `given_back_pct` is `None` rather than 0 or 100 when the session
never went green — there are no gains to take a percentage of, and inventing one
would be a claim.

Pinned by `tests/test_daily_report_giveback.py` (8 tests).

## Giveback as CONTEXT — RESEARCH FURTHER, not implemented

Whether the giveback should raise the confidence of detectors that already exist
was tested and **is not settled**. Full working in `giveback_as_context.md`.

| detector | controlled result | status |
|---|---|---|
| `martingale_behaviour` | 10 armed vs 4.0 expected, 2.5×, z=3.2 at the loose gate — but z=0.9 at the strict one | **interesting; needs a second, independent book** |
| `adding_to_adverse_position` | z=0.8 loose, z=3.3 strict — the reverse pattern | **insufficient evidence** |
| `same_symbol_obsession` | 2.3 SE uncontrolled → **z=0.9 controlled** | **no reliable signal** |
| `revenge_trade` | 7 alerts in total, z=0.4 / 1.5 | **no reliable signal** |

The uncontrolled version of this test looked convincing and was wrong: both
"armed" and "detector fires" rise with position in the session
(`P(armed | reached)` runs 0% → 17% across positions 1–10), the same confound
that retracted the Pattern 5 result. **Results that flip which detector they
belong to when the gate moves are what small counts look like, not what signal
looks like.**

**Nothing from this is implemented.** No severity change, no confidence change,
no new threshold, no new detector.

## OUTSTANDING — the confirmation replay has NOT run

Everything else in this retirement is verified (see the table above, plus 1,241
backend tests, 35 new regression tests, and a clean frontend). **The 203-session
confirmation replay is not among them.**

It was attempted on 27 Aug and reached **session 5 of 203 in 72 minutes** before
being killed. The cause was not the engine: the **Memurai (Redis) service was
stopped**, so every `publish_event` and every `admin_settings` read attempted
`localhost:6379`, waited for the connection to be refused, and did so dozens of
times per trade. Projected finish at that rate was about ten days.

**To run it:** start the service (`Start-Service Memurai`, needs admin), then

```
python tradedesk/scripts/replay_tradebook.py docs/tradebook-CY6001-FO2025-26.csv     --capital 50000 --no-rules
```

**Do not pipe it through `tail`** — that buffers until exit and is why the Redis
errors went unseen for 72 minutes. Redirect to a file and watch it. Do not run
pytest against the same database while it runs.

**What it should show:** `profit_giveaway` at **0 alerts**, every other detector
unchanged from the pre-retirement baseline, and the session facts and analytics
identical. The expected delta is exactly the retired pattern and nothing else.

Tracked in `docs/ENGINE_BACKLOG.md`.

## Limitations and follow-ups, recorded not closed

1. **No replacement.** Nothing in the engine watches session gains-erosion now,
   deliberately. The giveback is reported after the close and nothing acts on it
   during a session.
2. **If it should ever interrupt a session again, it needs a declared give-back
   stop** in the constitution — *"if I'm up ₹X and hand back Y%, I'm done"*.
   That field does not exist and adding it is a product decision, not an engine
   one. The four retained thresholds are what it would use.
3. **`AlertDetailSheet.tsx:92` renders `erosion_pct` as a percentage while the
   context stores a ratio** — a 51% giveback displays as "0.5%". Pre-existing;
   now only affects historical rows, which lowers its priority without making it
   correct.
4. **`peak_pnl` is the high-water mark of the REALIZED curve only.** Unrealized
   peaks are invisible. Engine-wide observability boundary, untouched.
5. **`early_exit` makes the opposite claim about this trader** — that they bank
   gains too early — and the risk-falls-after-peak finding is consistent with
   it. Read the two together at that review.
6. **The shuffle control is now a standing first test** for any detector keyed
   on a running total. It takes ~2 minutes and would have saved most of the
   Pattern 6 implementation work had it been run first.
