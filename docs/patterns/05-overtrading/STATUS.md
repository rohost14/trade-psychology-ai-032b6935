# Pattern #5 — `overtrading_burst` + `daily_overtrading` · **STATUS**

26 Aug 2026. Review approved with constraints; `daily_overtrading` changed,
`overtrading_burst` **DEFERRED and untouched**. Evidence in
`overtrading_review.md`.

---

## Current logic

One method, `_detect_overtrading_burst` (`behavior_engine.py:1185-1385`),
emitting two pattern types.

### `overtrading_burst` — UNCHANGED, DEFERRED

30-minute rolling window on entry times, structures not legs. Caution at 5,
danger at 8, suppressed entirely when the session is up and every trade in the
window was profitable. Reads `burst_trades_per_30min_caution` / `_danger`.

**Deliberately not touched.** 13 detections / 12 alerts / 10 of 189 sessions,
and it never once fired alone. n is far too small to move a threshold in either
direction, and being rare is not a reason to delete something.

### `daily_overtrading` — CHANGED

```
declared = thresholds["user_daily_trade_limit"]     # what the trader SAID
if not declared:            -> no event at all
if structures_today >= declared -> caution
```

**One severity. One rung. No default.**

| | before | after |
|---|---|---|
| threshold | `daily_trade_limit` — p75-derived, blended from history | **`user_daily_trade_limit` — declared by the trader** |
| nothing declared | fires at 7 (repo default) | **nothing fires** |
| second tier | `danger` at `daily_trade_danger` = 12 | **none** |
| copy | "the day stops being a series of decisions and becomes momentum" | "You set a limit on how many positions you take in a day. This is where you reached it." |
| context key | `daily_caution`, `daily_danger` | `declared_limit` |

## Why

**A p75 line is a quota, not a finding.** `daily_trade_limit` resolves from
history as `daily_trades_p75`. A threshold at a trader's 75th percentile alerts
on 25% of their sessions **by construction** — any trader, forever, regardless
of behaviour. Measured: 26%, 52 alerts. Halve your trading and the p75 halves
with you and still takes a quarter of your sessions.

**And the claim was contradicted.** Past the line this trader was **slower**
(median gap 4 → 9 min), **smaller** (median risk ₹8,044 → ₹7,213) and no worse
(win rate 44.7% → 42.6%, 0.4 SE). Heavy days were 26% of sessions and **2% of
the book's loss**; the 141 positions taken past the line **made ₹1,265**. Heavy
days already differ at position **one** (+14.9pp win rate), so the count is a
symptom of the kind of day it is, not a cause.

## Measured effect on the reference book (189 sessions, 912 positions)

| declared limit | `daily_overtrading` detections | days | `overtrading_burst` |
|---|---|---|---|
| **none** (replay condition, every new user) | **0** — was 132 | **0** — was 49 | 13 / 10 days (unchanged) |
| 5 | 274 | 84 | 13 / 10 |
| **10** (onboarding default) | 26 | 13 | 13 / 10 |
| 15 | 0 | 0 | 13 / 10 |

**52 alerts → 0** on the book as replayed. `overtrading_burst` is byte-identical
in behaviour at every setting.

## The consequence nobody asked for, verified not assumed

When a limit *is* declared, `daily_overtrading` fires at `>= limit` — and so
does `constitution_violation`'s `daily_trades` rule, at `ratio >= 1.0`, i.e.
**the same position**. That is `danger`, and
`_CONSTITUTION_PAIRS["daily_trades"]` already lists `daily_overtrading` as
suppressed on a breach.

Verified by running both detectors on one context:

```
daily_overtrading  : caution | 10 positions today — your limit is 10.
constitution       : daily_trades danger | Your daily trade limit breached: 10 of 10 trades.
```

**So `daily_overtrading` now produces no notification in either case** — no
event when nothing is declared, and a suppressed event when something is. It is
recorded as a `BehaviorEvent` and is available to analytics and reporting, which
is what the approval asked for in the undeclared case and turns out to be true
in both.

**This is the consolidation question, arriving early.** Two detectors now say
the same sentence about the same declared number, and the existing suppression
picks the constitution one. Deciding which should be the voice is the family
decision that was deferred — nothing here pre-empts it.

## Limitations, recorded not closed

1. **Three surfaces read the declared daily trade limit.**
   `constitution_violation` (exit, engine), `position_monitor_tasks:1431`
   (entry, fires `constitution_violation` with rule `daily_trade_limit`), and
   now `daily_overtrading`. No consolidation family covers them.
2. **They do not count the same way.** `constitution_violation` counts **legs**
   (`len(ctx.session_trades) + 1`); `daily_overtrading` counts **structures**
   (`count_structures`). Identical on this book — it collapses only 8 legs of
   912 — but they will disagree for a multi-leg trader, against the same
   declared number.
3. **`daily_trade_danger` = 12 still exists** in `trading_defaults.py` and is
   still resolved. It has no detector reader now. Not removed: it is surfaced by
   `api/constitution.py` and `api/behavioral.py`.
4. **`daily_trade_limit` (p75-derived) still exists and is still resolved** —
   read by `/api/risk`, `/api/behavioral`, the Rules page and
   `rule_suggestion_service`. Only the alerting path stopped using it.
5. **The SEBI attribution is unchanged.** `trading_defaults.py` records
   `daily_trade_limit 7 SEBI FY2023 (>6/day → 94% loss probability)` and **no
   source document for it exists in the repo**. Out of scope for this change;
   still wrong to leave.
6. **The burst check's silent fall-through** (≥ caution, session flat or up, no
   losers) produces no event and no record.
7. **No replay re-run.** The change removes events on a `--no-rules` book, so
   the expected delta is exactly −52 `daily_overtrading` alerts and nothing
   else. That is an expectation, not a measurement.

## Tests

- `tests/test_daily_overtrading_declared_limit.py` — 20 tests: no limit (×3
  counts), `None` limit, the p75 line no longer read, derived-vs-declared
  conflict, firing at the declared limit, one below, no second tier, the line
  following each trader's own number (×8), two traders one day, raising your
  limit, and `overtrading_burst` still firing with no profile.
- `tests/test_engine_hygiene.py::TestDailyOvertrading` rewritten with its
  contract. `test_daily_danger_tier` deleted — its subject, the 12-tier, no
  longer exists; replaced by
  `test_there_is_no_second_tier_above_the_declared_limit`.
