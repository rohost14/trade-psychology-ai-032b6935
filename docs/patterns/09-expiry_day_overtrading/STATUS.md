# Pattern #9 — `expiry_day_overtrading` · **RETIRED / COMPLETE**

27 Aug 2026. Detector `1.0.0` → **deleted**. No replacement detector, no
replacement threshold.

Evidence: `expiry_day_overtrading_review.md`.

---

## Why

**It never withheld.** Of the 55 positions it was allowed to judge across the
189-session book — expiry day, `CE`/`PE`/`FUT`, entry at or after the 13:00 IST
gate — it fired on **55** and stayed silent on **0**. A detector that never says
no is not measuring anything; it is a filter on the calendar.

**The cause was a units bug.** `today_lots` summed `total_quantity`, which is
CONTRACTS (`completed_trade.py:34` — *"in units, lot_size already factored"*),
against a threshold of **10**. A NIFTY lot is 75 contracts and the smallest
position in the book was 20, so `today_lots >= 10` was not a threshold — it was
`True`. 71% of firings came from that clause alone with a trade count under five,
and the count was **1** on eight of them: a detector named *overtrading* firing
on the trader's first expiry trade of the day. The same number was displayed
beside the word "lots" — *"1 NIFTY trades / 750 lots today on expiry"*.

**Both trader-facing sentences were unsourced and both measured false.**

| shipped claim | measured on 189 sessions |
|---|---|
| *"NSE data: … structural loss rate above 85%"* (last 2 h of expiry) | **53.8%** at 14:00+, 61.8% at 13:00+, against a book-wide ~60% |
| *"Each additional trade after 13:00 … reduces your edge"* (asserts r < 0) | **r = +0.260**, p = 0.056, n = 55 — **opposite sign** |

The reversal repeats at day level (expiry-trade-count vs session P&L
**r = +0.107**, p = 0.485, n = 45), and this trader's expiry-active sessions are
their **better** sessions (**51.1% green against 38.9%**). Post-13:00 expiry
against all non-expiry trading is ₹58/trade at **p = 0.863**.

The only origin for the 85% figure anywhere in the repository was
`docs/archive/PATTERN_REFERENCE.md`, which asserts *"NSE market data shows"* and
cites nothing. It is now annotated **RETRACTED** in place.

**Fixing the units was considered and rejected.** It would have moved the pass
rate from 100% to 58% — restoring discrimination without creating a finding,
because there is no outcome difference to discriminate on.

---

## What expiry day still does

Expiry-day-ness is real and is kept **exactly where it already earns its place** —
as a modifier inside detectors that measure a decision:

| reader | effect |
|---|---|
| `premium_loss_event` | `premium_loss_expiry_shift_pct` — bands shift **+15 pp** |
| `no_stoploss` | `no_stoploss_expiry_loss_pct` / `no_stoploss_expiry_hold_min` |
| `fomo_entry` | expiry retained as a `context_note` after Pattern 7 |

`is_expiry_day` and `count_structures` both keep other readers and were not
touched.

---

## What changed

| file | change |
|---|---|
| `services/behavior_engine.py` | `_detect_expiry_day_overtrading` deleted (67 lines) + header entry; retirement note in its place |
| `services/detector_registry.py` | `DetectorSpec` and `PatternCopy` removed, retirement notes left |
| `core/trading_defaults.py` | 3 constants deleted |
| `core/threshold_registry.py` | 3 `_spec` entries deleted |
| `contexts/AlertContext.tsx` | `BACKEND_TO_FRONTEND_TYPE` entry removed — display name **kept** |
| `docs/archive/PATTERN_REFERENCE.md` | origin of the 85% claim marked RETRACTED |
| `tests/test_pattern_contract.py` | added to `RETIRED_PATTERN_NAMES` |
| `CLAUDE.md` | detector counts |

**Counts: 25 detectors, 31 pattern types** (was 26 / 32).
`all_pattern_types()` stays the authority.

### The three thresholds are gone, and unlike Pattern 6's they held nothing up

`expiry_overtrading_caution_count` (5), `_danger_count` (8), `_caution_lots` (10)
were all `Kind.PERSONAL_BASELINE` / `Source.HISTORY` against metrics
`expiry_day_trades_p75`, `_p90` and `expiry_day_lots_p75` — **produced by no
code**, verified at 0 occurrences outside the registry. The ladder always fell
through to the literals, for every trader, permanently. Declaring a value
personal when nothing can ever personalise it is a false statement in the
registry; it is the same defect Pattern 7 found in `fomo_underlyings_*`.

They were not in `_CAPITAL_RATIOS` and had no second reader, so unlike the
`profit_giveaway` keys they were deleted outright.

### Historical rows stay readable

Stored alerts still carry `pattern_type = "expiry_day_overtrading"`. Every
rendering surface keeps its label — `AlertContext.tsx` display name,
`BehaviourCostCard.tsx`, `BehaviourLead.tsx`, and the weekly report's
`"Expiry Day Overtrading"`. Only `BACKEND_TO_FRONTEND_TYPE` lost its entry,
because that map claims the engine still emits the name.

---

## Replay — 203 sessions · CLEAN

| detector | before | after | note |
|---|---|---|---|
| `adding_to_adverse_position` | 99 | **99** | unchanged |
| `martingale_behaviour` | 39 | **39** | unchanged |
| `options_premium_avg_down` · `size_escalation` | 30 · 30 | **30 · 30** | unchanged |
| `same_symbol_obsession` | 22 | **22** | unchanged |
| `fomo_entry` | 19 | **19** | unchanged |
| **`expiry_day_overtrading`** | **28** | **0** | **intended** |
| `death_spiral` | 20 | 16 | *consequence* — see below |
| **total** | **330** | **298** | |

203/203 sessions, zero errors.

### `death_spiral` 20 → 16 is arithmetic, and here is why that is settled

`death_spiral` is a **composite**: it counts distinct nature-domains carrying an
event at danger+. It is explicitly built *from* other detectors, so removing one
mechanically changes it. `expiry_day_overtrading` was `nature="emotional"` and
did emit `danger`, so it could and did supply that domain on some days.

**The decisive evidence is that nothing else moved.** Every other detector is
identical to the alert. If the deletion had broken anything real, a detector that
measures behaviour would have shifted; none did. The only two changes are the
detector removed and the composite that counts detectors.

**A day was spent trying to prove the exact magnitude and it was not worth it.**
The attempted reconciliation compared danger-event counts from a CSV
reconstruction against the replay's own CompletedTrade builder — different
inputs, and dedup hides extra danger *events* behind a single danger *alert*, so
the two were never comparable. Five baseline-replay attempts failed on
environment (network drop, task reaping ×2, a 3h20m I/O hang, then abandoned).
**The number was never able to change the decision**, and treating a definitional
consequence as a possible regression is what turned a closed question into a
day's work. Recorded as a limitation below, not as a blocker.

---

## Tests — 24 for the retirement

`tests/test_expiry_day_overtrading_retired.py`, in five groups:

1. **it cannot produce new events** — method gone, absent from `REGISTRY` /
   `BY_NAME` / `ALIASES` / `all_pattern_types()`, no spec points at the deleted
   method, counts are 25 / 31, thresholds gone, **phantom metrics referenced
   nowhere**
2. **the invented statistics cannot come back** — no shipping module or frontend
   file *asserts* `"structural loss rate"`, `"last 2 hours of expiry"` or
   `"reduces your edge"` in a string literal (retirement comments may discuss
   them), and the archived origin is marked RETRACTED
3. **historical rows stay readable** — report label and three frontend surfaces
   keep their entries; `BACKEND_TO_FRONTEND_TYPE` does not
4. **expiry-day-ness survives** — the three modifier thresholds intact,
   `is_expiry_day` and `count_structures` still exist and still have readers
5. **no other detector moved** — `_WORSEN_METRIC`, the two per-episode dedup
   keys, `death_spiral`'s domains, and every surviving spec resolves

**Backend 1,479 passed** (1,455 + 24), 0 failed excluding `tests/production/`,
which needs a live server. **Frontend typecheck clean, 102 tests, 0 lint
errors.**

---

## Limitations, recorded not closed

0. **The exact per-day mechanism of `death_spiral` 20 → 16 was never traced.**
   It is arithmetic in kind and no other detector moved, which is why the pattern
   closed; the four specific days were not individually attributed. If a future
   change makes composite accounting matter, generate a baseline artifact BEFORE
   the change — `docs/*-replay.json` is gitignored and is destroyed by the next
   run, which is what made this expensive.

1. **n = 55 eligible positions, 45 expiry-active sessions, one trader.** No
   single test here would be decisive alone. What makes the retirement safe is
   consistency of sign across four independent looks — trade level, trade
   sequence, day level, day type — all against the detector's own hypothesis.
2. **A market-wide claim about retail expiry losses may still be true.** SEBI's
   F&O studies say most retail derivative traders lose money. That was never what
   this detector said: it said *this trader's* expiry afternoon is dangerous and
   each additional trade makes it worse, with a number we invented. The 100%
   pass rate is independent of any market fact.
3. **Not tested:** intraday timing within the afternoon, hold duration on expiry,
   and whether expiry-day behaviour differs during a drawdown. If expiry ever
   returns as a subject it should be one of these, not a trade count.
4. **`opening_5min_trap` carries the same defect class** — *"NSE data: 78% of
   retail opening-5-min derivative trades are unprofitable"*, sourced to the same
   archived document. Untouched here; to be checked on its own review.
5. **`alert.message` reaches the AI coach prompt** (`AlertDetailSheet.tsx:208`
   pastes it verbatim). Whatever the engine writes becomes model context. Worth a
   policy decision independent of this pattern.
6. **The copy contract does not cover detector messages.**
   `test_copy_carries_no_invented_statistics` checks `PatternCopy.observes` and
   `.explanation` only — which is exactly why the registry copy here was clean
   while the shipped message carried two fabricated statistics. The new tests
   close this for Pattern 9's specific sentences, not for the class.
