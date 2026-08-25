# The behavioural engine as it exists today — all 33 pattern types

> **The membership below is stale, 26 Aug 2026 — the totals are not.** Pattern 2
> ADDED `adding_to_adverse_position` and Pattern 4 RETIRED
> `consecutive_loss_streak`, so the engine is still **27 detectors / 33 pattern
> types** but they are not the same 27. `all_pattern_types()` is the authority.
> See the REVIEW STATUS table and `../04-consecutive_loss_streak/STATUS.md`.

24 Aug 2026. Baseline for the pattern-by-pattern review.

**Revision 2 — post-hygiene.** Revision 1 was documentation only. A single
pre-pattern hygiene pass then ran against it (commit below): definite bugs,
dead machinery and stale comments only. **No behavioural definition, empirical
threshold, severity rule, detector sensitivity, personalisation strategy or
merge/overlap behaviour was changed.** Everything that looked questionable but
was not provably wrong is in **DEFERRED TO PATTERN REVIEWS** at the foot of this
document, not silently fixed.

Verification after the pass: **1,078 backend tests pass** (1,047 before, +31
new), zero failures outside `tests/production/`, which requires a live server.
`pyflakes` is clean on `behavior_engine.py`, `trading_defaults.py` and
`position_monitor_tasks.py` for everything except unused imports.

Written from the code, not from prior documents or conversation. Every claim
below was checked against the file and line cited. Where code and documentation
disagree, both are shown and neither is reconciled.

**Verified sources**

| what | source |
|---|---|
| detector list, versions, disposition | `backend/app/services/detector_registry.py` (439 lines, 27 specs + 6 aliases) |
| detection logic | `backend/app/services/behavior_engine.py` (3,256 lines, 27 `_detect_*` methods) |
| entry-time evaluation | `backend/app/services/entry_detectors.py` |
| position-monitor patterns | `backend/app/tasks/position_monitor_tasks.py` |
| meta-detector | `backend/app/services/behavior_scores_service.py` |
| constants | `backend/app/core/trading_defaults.py` (79 `COLD_START_DEFAULTS`) |
| classification | `backend/app/core/threshold_registry.py` (33 classified) |
| persistence, cap, routing | `backend/app/tasks/trade_tasks.py` |
| tests | 87 files under `backend/tests/` (excl. `_archive`) |
| production-shaped evidence | replay of the 203-session tradebook, ₹50,000, `--no-rules` |

**Replay caveat, applies to every "evidence" line below.** The replay is one
trader, one year, one capital figure, with constitution rules disabled. It ran
`--no-rules`, so `constitution_violation` and `cooldown_violation` *cannot* fire.
The harness also skips three patterns by name: `no_stoploss` (UNJUDGEABLE — the
tradebook has no order-type column) and `excess_exposure` + `session_meltdown`
(CAPITAL_DERIVED — capital moved between ₹30,000 and ₹50,000 across the period,
so a percentage of it is arithmetic on a figure nobody can state).
`replay_tradebook.py:63-74`. Absence of evidence for those five is a property of
the harness, not of the detector.

---

## Master table

388 alerts across 203 sessions. "days" = sessions on which the pattern alerted at
least once. "tests" = number of test files mentioning the pattern name (a
mention, not proof of a behavioural test — see §13 of each entry).

| # | pattern | family | disposition | trigger | replay alerts / days | tests | status | major open issue |
|---|---|---|---|---|---|---|---|---|
| 1 | `consecutive_loss_streak` | emotional | alerting | exit | 61 / 46 | 4 | IMPLEMENTED AND VERIFIED | hardcoded `0.5` of daily limit is an inline number with no key |
| 2 | `revenge_trade` | emotional | alerting | exit | 38 / 37 | 12 | IMPLEMENTED AND VERIFIED | S1/S2/P1 thresholds all undecided → account, trade and personal frames abstain for every trader today |
| 3 | `overtrading_burst` | emotional | alerting | exit | 12 / 10 | 5 | IMPLEMENTED AND VERIFIED | 30-min window is hardcoded, not a threshold key |
| 3b | `daily_overtrading` (alias) | emotional | alerting | exit | 37 / 36 | 0 | IMPLEMENTED, NOT TESTED | emitted by detector #3; zero test mentions |
| 4 | `size_escalation` | emotional | alerting | exit | 9 / 9 | 6 | IMPLEMENTED AND VERIFIED | cross-instrument fallback compares notional against a quantity-derived threshold |
| 5 | `rapid_reentry` | emotional | analytics | exit | 0 (info only) | 2 | IMPLEMENTED, evidence-only | overlaps #2 by construction |
| 6 | `panic_exit` | emotional | analytics | exit | 0 (info only) | 4 | IMPLEMENTED, NOT VERIFIABLE from tradebook | depends on `exit_order_types`, absent in replay |
| 7 | `martingale_behaviour` | risk | alerting | exit | 36 / 32 | 2 | IMPLEMENTED AND VERIFIED | second-highest danger count in the book; never reviewed |
| 8 | `cooldown_violation` | discipline | analytics | exit | 0 (rules off) | 1 | IMPLEMENTED BUT NOT YET VERIFIED | cannot fire in replay |
| 9 | `direction_instability` | emotional | alerting | exit | 10 / 9 | 1 | IMPLEMENTED AND VERIFIED | `rapid_flip_min` and `direction_confusion_window_min` are both 10 and both read |
| 10 | `excess_exposure` | risk | alerting | exit | skipped | 0 | IMPLEMENTED, NOT VERIFIED | zero test mentions AND excluded from replay |
| 11 | `session_meltdown` | risk | alerting | exit | skipped | 4 | IMPLEMENTED, NOT VERIFIED in replay | invents a limit at 5% of capital when none declared |
| 12 | `fomo_entry` | emotional | alerting | exit | 28 / 28 | 7 | IMPLEMENTED AND VERIFIED | **inline default 2 contradicts config 4** for expiry day |
| 13 | `no_stoploss` | risk | alerting | exit | skipped (UNJUDGEABLE) | 3 | IMPLEMENTED, NOT VERIFIABLE from tradebook | needs live order data |
| 14 | `early_exit` | performance | analytics | session | 0 (info only) | 3 | IMPLEMENTED, evidence-only | declared `trigger: session` but runs per trade |
| 15 | `winning_streak_overconfidence` | emotional | alerting | exit | 6 / 6 | 0 | IMPLEMENTED, NOT TESTED | zero test mentions |
| 16 | `options_premium_avg_down` | emotional | alerting | exit | 19 / 19 | 1 | IMPLEMENTED AND VERIFIED | overlaps #7 and #17 on the same trade |
| 17 | `premium_loss_event` | risk | alerting | exit | 16 / 15 | 1 | IMPLEMENTED AND VERIFIED | only source of `critical` in the whole replay (3) |
| 18 | `expiry_day_overtrading` | emotional | alerting | exit | 28 / 28 | 1 | IMPLEMENTED AND VERIFIED | message asserts an unsourced "85% loss rate" statistic |
| 19 | `opening_5min_trap` | emotional | analytics | exit | 0 (info only) | 2 | IMPLEMENTED, evidence-only | **severity is hardcoded `info`; the computed `severity` variable is dead** |
| 20 | `end_of_session_mis_panic` | emotional | alerting | exit | 2 / 2 | 1 | IMPLEMENTED AND VERIFIED | weakest alerting evidence in the book |
| 21 | `post_loss_recovery_bet` | risk | alerting | exit | 2 / 2 | 0 | IMPLEMENTED, NOT TESTED | zero test mentions, near-zero evidence |
| 22 | `profit_giveaway` | emotional | alerting | exit | 26 / 12 | 2 | IMPLEMENTED AND VERIFIED | **inline default 1000 contradicts config 1500** |
| 23 | `constitution_violation` | discipline | alerting | exit | 0 (rules off) | 1 | IMPLEMENTED BUT NOT YET VERIFIED | cannot fire in replay; 6 rules in one pattern type |
| 24 | `same_symbol_obsession` | emotional | alerting | exit | 29 / 20 | 0 | IMPLEMENTED, NOT TESTED | 20 danger alerts, zero test mentions |
| 25 | `time_of_day_bias` | performance | alerting | exit | 0 | 0 | IMPLEMENTED, NEVER FIRED | needs 30+ sessions of baseline; `baseline_sessions` has no config key |
| 26 | `win_rate_collapse` | performance | analytics | session | 0 | 0 | IMPLEMENTED, NEVER FIRED | hardcoded `0.4` and `0.5`, no keys |
| 27 | `strategy_breakdown` | performance | analytics | session | 0 | 0 | IMPLEMENTED, NEVER FIRED | hardcoded `0.4`, `0.5`, `8`, no keys |
| A1 | `death_spiral` (L2 meta) | emotional | alerting | session | 29 / 29 | 1 | IMPLEMENTED AND VERIFIED | absorbs every other alert when it fires |
| A2 | `overexposure` (monitor) | risk | alerting | entry | 0 | 3 | IMPLEMENTED, separate pipeline | `1.5×` multiplier hardcoded in the task |
| A3 | `portfolio_concentration` (monitor) | risk | alerting | entry | 0 | 1 | IMPLEMENTED, separate pipeline | 40/60/80 levels in docstring only |
| A4 | `holding_loser` (monitor) | risk | alerting | entry | 0 | 2 | IMPLEMENTED, separate pipeline | module-level constants, outside the ladder |
| A5 | `capital_mismatch` (housekeeping) | — | alerting | n/a | 0 | 2 | IMPLEMENTED, not a behaviour detector | in the vocabulary because it writes `risk_alerts.pattern_type` |

**Reviewed?** One of 33. `revenge_trade` only (version 3.0.0, rewritten
2026-08-23, and the only spec that declares `frames`). Every other detector
carries `frames=()`, which the registry documents as *"EMPTY ON EVERY ENTRY,
deliberately… a field filled in by guesswork is worse than an empty one."*

---

# Per-pattern detail

Sections 10, 11, 12 are largely shared machinery; they are described once in
**§C Shared mechanisms** and referenced rather than repeated.

## 1. `consecutive_loss_streak`

**Family** emotional · alerting · exit · notification level 2 · v1.1.0 ·
`uses_baseline`, `uses_constitution`

**Intended** — an unbroken run of losing trades inside one session.

**Logic** (`behavior_engine.py:855-925`). Takes the streak from
`ctx.facts.consecutive_losses` — the canonical session fact, not a local count.
Returns `None` at streak 0. Sums the absolute P&L of the last *streak* trades.
Then, in order: `streak >= danger` → **danger**; `streak >= caution` **and**
`total_loss >= daily_loss_limit * 0.5` → **danger** with
`escalated_by: loss_size`; `streak >= caution` → **caution**.

**Inputs** `session_trades` + current trade, `facts.consecutive_losses`,
`thresholds`.

**Thresholds**

| key | value | classification |
|---|---|---|
| `consecutive_loss_caution` | 3 | `fallback` (registry) |
| `consecutive_loss_danger` | 5 | **unclassified** — not in the registry |
| `daily_loss_limit` | user-declared | user value |
| *inline* `0.5` | half the daily limit | **hardcoded, no key, unclassified** |

**User-declared inputs** `daily_loss_limit` (onboarding / My Rules).

**Entry vs exit** exit only. Explicitly excluded from `ENTRY_DECIDABLE`.

**Severity/confidence** caution/danger. No confidence, no abstention — returns
`DetectedEvent`, not `DetectorResult`.

**Consolidation** suppressed by `constitution_violation` rule
`max_consecutive_losses`; in `_STRATEGY_SUPPRESSED`.

**Evidence** 61 alerts / 46 sessions — **the most frequent alerting pattern in
the book.** 54 caution, 7 danger.

**Tests** 4 files. `test_behavior_engine.py` has `test_caution_on_3_losses`,
`test_danger_on_5_losses`, `test_streak_resets_on_winner`,
`test_no_alert_on_winner` — these prove the count ladder and the reset, nothing
about the loss-size escalation branch.

**Known issue** the `0.5` escalation is an inline literal with no key, no
classification and no test. The comment says a 3-trade ₹12,000 run should not
read quieter than a 5-trade ₹1,500 run; the number chosen for that is unsourced.

**Status: IMPLEMENTED AND VERIFIED.**

## 2. `revenge_trade`

**Family** emotional · alerting · exit · level 2 · **v3.0.0** ·
frames = ACCOUNT, TRADE, PERSONAL, STRUCTURAL — the only spec that declares them.

**Intended** — a decision taken against the previous loss rather than on its own
terms.

**Logic** (`behavior_engine.py:948-1189`). Two ordinal axes and a lookup table,
`_RT_MATRIX`. No score, no weights, no counting.

- **Structural gate** — needs a prior closed trade that lost; otherwise
  `not_detected`. Missing exit time or negative gap → `abstained`.
- **A (trigger magnitude)** — the highest level any frame establishes.
  Account-relative (`loss_vs_account`), trade-relative (`loss_vs_risk_basis`,
  per instrument class), personal (own-loss percentile). A1 is reached by
  **measurability**, A2/A3 by a threshold.
- **B (reaction structure)** — B0 outside the window returns `not_detected`;
  B1 inside the window; B2 same underlying; B3 same underlying **and** larger
  quantity than the trade that lost (a plain inequality, no multiplier).
- Matrix `[A][B]`, then a declared-cooldown breach can raise severity to at
  least `caution` and never on its own to `danger`.

**Thresholds**

| key | value | classification |
|---|---|---|
| `revenge_window_caution_min` | 20 | `fallback` |
| `revenge_account_loss_pct` (S1) | **absent** | undecided |
| `revenge_trade_loss_pct_{class}` (S2) | **absent** | undecided |
| `revenge_loss_percentile` (P1) | **absent** | undecided |
| `revenge_loss_min_sample`, `revenge_gap_min_sample` | maturity requirements | — |
| `user_cooldown_min` | user-declared | user value |

**User-declared inputs** cooldown after loss.

**Entry vs exit** both. First in `ENTRY_DECIDABLE`; at entry it runs against an
`EntryView` and its output is forced `shadow=True`.

**Severity/confidence/abstention** the only detector returning a
`DetectorResult`. Emits POSITIVE / NEGATIVE / ABSTAINED. Confidence is the shared
weakest-link calculation, and answers *how well we could see this*, never how bad
it is.

**Consolidation** family "going back to the same trade" — loses to
`same_symbol_obsession`, beats `rapid_reentry`. Suppressed by the constitution
`cooldown` rule. In `_STRATEGY_SUPPRESSED`.

**Evidence** 38 alerts / 37 sessions. Separately, a full research programme
concluded no fill-level signature separates post-loss from post-win behaviour
(`docs/research/REVENGE_FINAL_EVIDENCE_REVIEW.md`, AUC 0.482). The detector is
**frozen**, not deleted.

**Tests** 12 files — by far the most covered. `test_revenge_trade_matrix.py`
pins every matrix cell; `test_detector_result.py` and
`test_detector_result_adapter.py` cover the verdict type.

**Known issue, and it is structural** — S1, S2 and P1 are all absent, and
`maturity.assess` returns UNAVAILABLE while M1 is undeclared. **The account,
trade and personal frames therefore abstain for every trader today**, so A can
only reach level 1 by measurability. In practice the detector runs on rows A0/A1
of the matrix, which is why 33 of its 38 alerts are `caution`.

**Status: IMPLEMENTED AND VERIFIED** (and frozen by decision).

## 3. `overtrading_burst` — and 3b. `daily_overtrading`

**Family** emotional · alerting · exit · level 2 · v2.0.0

**Intended** — too many positions inside a short window (burst), and too many in
the day (daily). One method, two `pattern_type`s.

**Logic** (`behavior_engine.py:1202-1371`).
*Burst:* trades whose **entry** falls in the 30 minutes ending at this trade's
entry. Counted as **structures**, not legs, via
`strategy_detector.count_structures` — a four-leg condor is one decision.
Suppressed entirely if session P&L > 0 **and** every trade in the burst was
profitable. `>= burst_danger` → danger; `>= burst_caution` → caution, with two
different messages depending on whether the session is down or merely contains
losses.
*Daily:* structures across the whole session; `>= daily_danger` → danger, else
caution, emitted as **`daily_overtrading`**.

**Thresholds**

| key | value | classification |
|---|---|---|
| `burst_trades_per_30min_caution` | 5 | `fallback` |
| `burst_trades_per_30min_danger` | 8 | **unclassified** |
| `daily_trade_limit` | 7 | **unclassified** |
| `daily_trade_danger` | 12 | **unclassified** |
| *inline* `30` minutes | window | **hardcoded, no key** |

**Entry vs exit** exit only (not in `ENTRY_DECIDABLE`).

**Consolidation** both suppressed by the constitution `daily_trades` rule.

**Evidence** burst 12 / 10; **daily 37 / 36**. The alias fires three times as
often as the spec that owns it.

**Tests** burst 5 files; **`daily_overtrading` appears in zero test files.**

**Known issue** the 30-minute window is written into the code in three places
(`timedelta(minutes=30)`, `"window_minutes": 30`, the copy string) with no
threshold key. `daily_overtrading` is a top-3 alert by volume with no test.

**Status:** #3 IMPLEMENTED AND VERIFIED; #3b IMPLEMENTED, NOT TESTED.

## 4. `size_escalation`

**Family** emotional · alerting · exit · level 1 · v1.1.0

**Intended** — position size rising across three consecutive trades while losing.

**Logic** (`behavior_engine.py:1375-1447`). Requires ≥3 session trades. Takes the
last 3 on the **same underlying** by quantity. If that is not strictly
increasing, falls back to the last 3 **of the session** by **notional**
(`qty × avg_entry_price`) and sets `cross=True`. Requires ≥1 loss in the first
two. Fires caution when `(sizes[2]-sizes[0])/sizes[0]*100 >= size_escalation_pct`.

**Thresholds** `size_escalation_pct` = 30, **unclassified**.

**Entry vs exit** both — in `ENTRY_DECIDABLE`.

**Consolidation** family "sizing after losses" — **the weakest of the three, so
it loses to both `martingale_behaviour` and `post_loss_recovery_bet`.** In
`_STRATEGY_SUPPRESSED`.

**Evidence** 9 / 9, all caution.

**Tests** 6 files.

**Known issue** the cross-instrument branch compares **rupees** against a
threshold (`30`) whose meaning was set for **quantity**. A 30% rise in notional
and a 30% rise in lots are different claims; the code comment acknowledges the
units differ ("₹10,000→₹20,000" vs "50→100→200") for the *message* but the
threshold is shared. The comment also records that the earlier version returned
before the cross-instrument branch could run — **zero firings across 61 sessions
against six occurrences found by hand.**

**Status: IMPLEMENTED AND VERIFIED.**

## 5. `rapid_reentry`

**Family** emotional · **analytics** · exit · level 0 · v2.0.0

**Logic** (`1451-1486`). Prior trade on the **same tradingsymbol**, that lost;
gap `0 <= gap <= rapid_reentry_min` → **info**.

**Thresholds** `rapid_reentry_min` = 5, `fallback`.

**Entry vs exit** both — in `ENTRY_DECIDABLE`.

**Severity** hardcoded `info`. The inline comment says *"evidence feeds revenge
confidence"* — **`revenge_trade` v3.0.0 does not read it**; its confidence comes
from `confidence.from_observables`. The comment is stale.

**Consolidation** last in the "going back to the same trade" family.

**Evidence** 0 alerts by design (analytics never becomes a `RiskAlert`).

**Status: IMPLEMENTED, evidence-only.**

## 6. `panic_exit`

**Family** emotional · analytics · exit · level 0 · v2.0.0 ·
consumes `exit_order_types`

**Logic** (`1490-1516`). Hold < `panic_exit_min` **and** a loss **and** exit not
via SL/SL-M/SLM/SL-MKT → info.

**Thresholds** `panic_exit_min` = 5, `fallback`.

**Evidence** not verifiable from the tradebook: `exit_order_types` is loaded from
`Trade.order_type` (`behavior_engine.py:535`) and the replay never sets one.

**Status: IMPLEMENTED, NOT VERIFIABLE from tradebook data.**

## 7. `martingale_behaviour`

**Family** risk · alerting · exit · level 2 · v1.1.0

**Intended** — position size increasing after consecutive losses.

**Logic** (`1556-1669`). Last 3 on the same underlying; if fewer than 2, falls
back to the last 3 of the session with `cross_instrument=True` and switches from
quantity to **notional**. Requires `loss_count >= martingale_min_losses` among
the priors. `max_ratio` = the largest step-up between consecutive priors.
`>= danger_mul` → danger, `>= caution_mul` → caution.

**Thresholds** `martingale_min_losses` 2, `martingale_caution_multiplier` 1.5,
`martingale_danger_multiplier` 2.0 — **all three unclassified.**

**Entry vs exit** both — in `ENTRY_DECIDABLE`.

**Consolidation** **wins** the "sizing after losses" family. In
`_STRATEGY_SUPPRESSED`.

**Evidence** 36 / 32, **26 of them danger** — the largest single source of
`danger` in the replay.

**Tests** 2 files, neither a behavioural test of the ladder
(`test_alert_outcome_service.py`, `test_pattern_vocabulary_contract.py`).

**Known issue** `max_ratio` is computed over the **priors only** — the current
trade's size is added to the display sequence (`all_sizes`) but never enters the
ratio. So the alert can say "…→₹20,000" while the ratio that triggered it
concerned two earlier trades. The largest danger source in the book has no
behavioural test.

**Status: IMPLEMENTED AND VERIFIED** (fires heavily; ladder untested).

## 8. `cooldown_violation`

**Family** discipline · analytics · exit · level 0 · consumes `active_cooldowns`

**Logic** (`1673-1693`). If any active `Cooldown` DB row exists, emit info with
the remaining minutes. **No threshold at all.** Distinct from the constitution
`cooldown` rule, which is user-declared and fires danger.

**Evidence** cannot fire in the replay (`--no-rules`).

**Status: IMPLEMENTED BUT NOT YET VERIFIED.**

## 9. `direction_instability`

**Family** emotional · alerting · exit · level 1 · v2.0.0. Phase-4 merge of
`rapid_flip` + `options_direction_confusion`.

**Logic** (`1697-1795`). Level 1 = same symbol, opposite direction, gap <
`rapid_flip_min`. Level 2 = same underlying, CE↔PE, both LONG, gap <
`direction_confusion_window_min`. Level 3 = ≥3 flips this session → danger.

**Thresholds** `rapid_flip_min` 10 (`personal_baseline`),
`direction_confusion_window_min` 10 (**unclassified**). Inline `3` for the
session-flip count has no key.

**Entry vs exit** both — in `ENTRY_DECIDABLE`. In `_STRATEGY_SUPPRESSED`
(straddle legs are CE+PE by design).

**Evidence** 10 / 9.

**Known issue** two keys with the same value 10 and different classifications
control two branches of one detector. The Level-3 count `3` is inline.

**Status: IMPLEMENTED AND VERIFIED.**

## 10. `excess_exposure`

**Family** risk · alerting · exit · level 2 · v1.0.0 · `uses_constitution`

**Logic** (`1799-1843`). `estimate_capital_at_risk(...) / trading_capital * 100`,
compared to caution 5% / danger 10%.

**Thresholds** `max_position_pct_caution` 5.0 and `max_position_pct_danger` 10.0
— both `universal_safety`. `trading_capital` is user-declared.

**Consolidation** family "the position is too big" — **wins** over
`overexposure`, `portfolio_concentration`, `capital_mismatch`. Suppressed by the
constitution `max_trade_risk` rule.

**Evidence** excluded from the replay as CAPITAL_DERIVED.

**Tests** **zero mentions.**

**Known issue** the only alerting detector with neither a test nor replay
evidence.

**Status: IMPLEMENTED, NOT VERIFIED.**

## 11. `session_meltdown`

**Family** risk · alerting · exit · **level 4, guardian-eligible** · v1.0.0

**Logic** (`1847-1910`). Skips a losing leg inside a net-profitable strategy
group. If no `daily_loss_limit` is declared, **invents one at 5% of capital** and
sets `limit_is_declared=False`, which changes the copy but not the firing.
`session_pnl < -(limit * danger_pct)` → danger; `* caution_pct` → caution.

**Thresholds** `meltdown_caution_pct` 0.40, `meltdown_danger_pct` 0.75 — both
**unclassified**. Inline `0.05` of capital for the derived limit has no key.

**Consolidation** suppressed by the constitution `daily_loss` rule. **Removed
from `_COMPOSITES`** — the code records that it had been absorbing every other
alert on 41 of 61 real sessions, and that *"a consolidation rule that silences
the product on exactly the days it matters most is worse than the noise it was
written to fix."*

**Evidence** excluded from the replay as CAPITAL_DERIVED.

**Tests** 4 files, including three specifically about whether the copy may call
an invented limit "yours".

**Status: IMPLEMENTED, NOT VERIFIED in replay.**

## 12. `fomo_entry`

**Family** emotional · alerting · exit · level 1 · v1.0.0

**Logic** (`1919-2004`). Counts **distinct underlyings** entered in a rolling
window ending at this entry, including the current trade. Threshold varies by
context, checked in order: expiry day → open window → close window → general.
Session bounds come from the instrument's own exchange
(`exchange_constants.get_open_time/get_close_time`), fixed after MCX traders
never triggered either window.

**Thresholds**

| key | config | inline default | classification |
|---|---|---|---|
| `fomo_window_min` | 30 | 30 | unclassified |
| `fomo_symbols_in_window` | 3 | 3 | `personal_baseline` |
| `fomo_symbols_at_open` | 2 | 2 | `personal_baseline` |
| `fomo_symbols_at_close` | 3 | 3 | `personal_baseline` |
| `fomo_expiry_day_symbols` | **4** | **2** | `personal_baseline` |
| `fomo_open_window_min` / `fomo_close_window_min` | 30 / 30 | 30 / 30 | unclassified |

**Known issue — a live code/config disagreement.** `behavior_engine.py:1933`
reads `ctx.thresholds.get("fomo_expiry_day_symbols", 2)` while
`trading_defaults.py` and `threshold_registry.py` both say **4**. The resolved
value wins, so the effective expiry threshold is 4 — **less** sensitive than the
general threshold of 3, which inverts the stated intent that expiry day is
riskier. The inline `2` is dead and misleading.

**Evidence** 28 / 28, all caution.

**Tests** 7 files — the widest coverage after `revenge_trade`.

**Status: IMPLEMENTED AND VERIFIED**, with a live discrepancy.

## 13. `no_stoploss`

**Family** risk · alerting · exit · level 2 · consumes `exit_order_types`

**Logic** (`2011-2105`). CE/PE/FUT only, losing trades only. Returns early if
the exit order type was SL/SL-M/SLM/SL-MKT. Denominator is premium for options,
`estimate_capital_at_risk` for futures. Three threshold pairs by expiry kind
(monthly / weekly-expiry / ordinary). Requires **both** a minimum hold and a
minimum loss percentage. Danger above `no_stoploss_loss_pct_danger`.

**Thresholds** `no_stoploss_loss_pct_caution` 25 (`fallback`),
`no_stoploss_loss_pct_danger` 50 (`universal_safety`), `no_stoploss_hold_min` 5
(`fallback`); `_expiry_loss_pct` 25, `_expiry_hold_min` 5,
`_monthly_loss_pct` 20, `_monthly_hold_min` 5 — **all four unclassified**.

**Evidence** UNJUDGEABLE in the replay — `exit_order_types` is empty for all 203
sessions because the tradebook CSV has no order-type column. In production the
field is populated from `Trade.order_type`.

**Status: IMPLEMENTED, NOT VERIFIABLE from tradebook data.**

## 14. `early_exit`

**Family** performance · analytics · **trigger declared `session`** · level 0

**Logic** (`2112-2155`). Only on a winning current trade. Needs
`early_exit_min_samples` winners **and** losers with durations. Fires info when
`avg_winner_hold < avg_loser_hold * early_exit_ratio` **and**
`avg_winner_hold < early_exit_winner_max_min`.

**Thresholds** `early_exit_ratio` 0.40 and `early_exit_winner_max_min` 60 (both
`personal_baseline`), `early_exit_min_samples` 3 (**unclassified**).

**Known issue** the registry declares `trigger="session"` but the method is
called from the same per-CompletedTrade loop as every other detector — the
registry docstring says session-triggered detectors *"will move to EOD evaluation
in Phase 4+"*, which has not happened. **DOCUMENTED BUT NOT IMPLEMENTED** for the
trigger field specifically.

**Status: IMPLEMENTED, evidence-only.**

## 15. `winning_streak_overconfidence`

**Family** emotional · alerting · exit · level 1 · v1.1.0 · `uses_baseline`

**Logic** (`2162-2281`). Streak = last N prior exits all profitable, any
instrument. Size baseline = average quantity of priors on the **same
underlying**; if fewer than 2 such priors, falls back to **notional** across all
priors. Danger = 5-win streak **and** size ≥ 2× baseline. Caution = 3-win streak
**and** size ≥ 1.3× baseline. If the danger streak holds but the size test fails,
falls through to the caution check.

**Thresholds** `overconfidence_win_streak_caution` 3 and `_danger` 5 (both
`definitional`); `overconfidence_size_mul_caution` 1.3 and `_danger` 2.0 (both
**unclassified**).

**Evidence** 6 / 6, all caution — **the danger tier never fired in 203 sessions.**

**Tests** **zero mentions.**

**Status: IMPLEMENTED, NOT TESTED.**

## 16. `options_premium_avg_down`

**Family** emotional · alerting · exit · level 1

**Logic** (`2297-2349`). Current trade must be a LONG CE/PE. Scans session trades
for prior LONG option losers on the **same underlying** whose loss exceeded
`premium_avg_down_loss_pct` of premium paid. Any match → caution, quoting the
worst.

**Thresholds** `premium_avg_down_loss_pct` 20 — **unclassified**.

**Evidence** 19 / 19, all caution.

**Known issue** overlaps `martingale_behaviour`, `same_symbol_obsession` and
`revenge_trade` on the same underlying after the same loss, and is in **none** of
the three consolidation families — so it can fire alongside all of them.

**Status: IMPLEMENTED AND VERIFIED.**

## 17. `premium_loss_event`

**Family** risk · alerting · exit · **level 3** · v2.0.0. Phase-4 merge of
`iv_crush_behavior` + `premium_destruction`.

**Logic** (`2368-2457`). LONG CE/PE only. Uses stored `pnl_pct` when present.
**Caps `loss_pct` at 100** and logs a warning, because a long option cannot lose
more than its premium. Expiry day shifts all three levels up by
`premium_loss_expiry_shift_pct`. A second trade past the danger level in the same
session escalates danger → critical. `fast_collapse` is a context flag only.

**Thresholds** `premium_loss_caution_pct` 40, `_danger_pct` 60, `_critical_pct`
80 (all `universal_safety`); `premium_loss_expiry_shift_pct` 15 and
`premium_loss_fast_hold_min` 30 (**both unclassified**).

**Evidence** 16 / 15 — **the only source of `critical` in the entire replay (3).**

**Status: IMPLEMENTED AND VERIFIED.**

## 18. `expiry_day_overtrading`

**Family** emotional · alerting · exit · level 2 · `uses_baseline`

**Logic** (`2465-2526`). Expiry day for this symbol only. Counts structures and
lots on the same underlying. **Returns None before 13:00 IST.** Danger on count;
caution on count **or** lots.

**Thresholds** `expiry_overtrading_caution_count` 5, `_danger_count` 8,
`_caution_lots` 10 — all `personal_baseline`. The **13:00 cutoff is inline with
no key.**

**Evidence** 28 / 28.

**Known issue** the danger message asserts *"NSE data: retail option activity in
the last 2 hours of expiry day has a structural loss rate above 85%"* and the
caution message asserts *"statistically reduces your edge"* — unsourced
statistics presented as measurement, which the registry's own copy rules forbid
(*"No statistics… the frontend previously shipped precise unsourced claims…
presented as measurement"*). The registry copy for this pattern is clean; the
**detector message is not**, and the detector message is what ships.

**Status: IMPLEMENTED AND VERIFIED**, with a copy-vs-policy contradiction.

## 19. `opening_5min_trap`

**Family** emotional · analytics · exit · level 0 · v2.0.0

**Logic** (`2534-2620`). Entry inside `opening_trap_window_end_min` of a
hardcoded 09:15, losing trades only. Two triggers: quick reactive exit
(`duration <= opening_trap_quick_exit_min`) or large loss
(`loss_pct >= opening_trap_large_loss_pct`).

**Thresholds** `opening_trap_window_end_min` 10 and `opening_trap_large_loss_pct`
30 (**unclassified**), `opening_trap_quick_exit_min` 15 (`personal_baseline`).

**Known issue — dead code.** Line 2582 computes
`severity = "danger" if (is_quick_reactive and is_large_loss) else "caution"`,
and the returned `DetectedEvent` then hardcodes `severity="info"` (line 2605).
**The computed severity is never used.** Separately, market open is hardcoded to
09:15 here, unlike `fomo_entry` and `end_of_session_mis_panic`, which were both
fixed to derive it from the exchange — so this detector is still wrong for MCX.
The name says 5 minutes, the threshold is 10, and the message says 09:15–09:25.

**Status: IMPLEMENTED, evidence-only, with dead code.**

## 20. `end_of_session_mis_panic`

**Family** emotional · alerting · exit · level 1 · v2.0.0

**Logic** (`2629-2718`). MIS/INTRADAY only. Square-off time and panic window
derived per exchange: NFO/BFO 15:25 with panic from 15:00; MCX/CDS/BCD close−5
with panic from squareoff−25; NSE/BSE 15:15 from 15:00. Counts late MIS entries.
If **all** late trades are profitable and the session is green: danger becomes
`info`, and the caution tier returns `None` entirely.

**Thresholds** `end_session_mis_caution_count` 2, `_danger_count` 3 — both
`personal_baseline`. The 25-minute run-up and the 15:00 anchor are inline.

**Evidence** 2 / 2 — **the weakest evidence of any alerting pattern that fired.**

**Status: IMPLEMENTED AND VERIFIED** (barely).

## 21. `post_loss_recovery_bet`

**Family** risk · alerting · exit · level 2 · v1.1.0

**Logic** (`2726-2812`). Needs ≥2 priors on the same underlying, and the **last
two must both be losses**. Baseline = average of the last 3 priors, by quantity
within one underlying or by notional when the trader moved between them.
`size_ratio >= danger_mul` → danger, `>= caution_mul` → caution.

**Thresholds** `recovery_bet_caution_mul` 2.0 and `_danger_mul` 3.0 — both
**unclassified**.

**Entry vs exit** both — in `ENTRY_DECIDABLE`. In `_STRATEGY_SUPPRESSED`.

**Consolidation** middle of the "sizing after losses" family — loses to
`martingale_behaviour`, beats `size_escalation`.

**Evidence** 2 / 2.

**Tests** **zero mentions.**

**Status: IMPLEMENTED, NOT TESTED.**

## 22. `profit_giveaway`

**Family** emotional · alerting · exit · level 2

**Logic** (`2828-2932`). Peak and running P&L from `ctx.facts`. Gates on
`peak_pnl >= min_peak` and `erosion >= min_erosion`. `min_erosion` is raised to
the trader's own median losing trade when `_typical_loss` has ≥3 losses. Three
outcomes: **sign flip** (session crossed from profit to loss, erosion ≥ 100% of
peak) → danger with its own message; `erosion_pct >= danger_pct` → danger;
`>= caution_pct` → caution. No first-crossing guard — relies on 24h DB dedup.

**Thresholds**

| key | config | inline default | classification |
|---|---|---|---|
| `profit_giveaway_min_peak` | **1500** | **1000** | unclassified |
| `profit_giveaway_min_erosion` | 500 | 500 | unclassified |
| `profit_giveaway_caution_pct` | 0.50 | 0.50 | unclassified |
| `profit_giveaway_danger_pct` | 0.70 | 0.70 | unclassified |

`profit_giveaway_min_peak_pct_capital` and `_min_erosion_pct_capital` exist in
`COLD_START_DEFAULTS` and are consumed by `_CAPITAL_RATIOS` in
`threshold_resolution.py:636-638` — so these two rupee floors scale with declared
capital.

**Evidence** 26 alerts across only **12 sessions** — the highest alerts-per-day
ratio in the book (2.2), despite the comment claiming DB dedup limits it to once
per session.

**Known issues** (a) inline default 1000 vs config 1500; (b) `_typical_loss`
reads `ctx.session_trades` — **today's** losses, not a cross-session history,
despite the docstring describing it as the trader's own stable loss size;
(c) 26/12 suggests the dedup claim in the comment does not hold in replay.

**Status: IMPLEMENTED AND VERIFIED**, with three open questions.

## 23. `constitution_violation`

**Family** discipline · alerting · exit · **level 4, guardian-eligible** ·
returns a **list**

**Logic** (`2945-3071`). One `pattern_type` for six user-declared rules, each in
`context["rule"]`. Ladder: `>= severe` critical, `>= 1.0` danger, `>= approaching`
caution. Binary rules (cooldown, restricted_window) fire danger directly with no
approaching tier.

| rule | source | measure |
|---|---|---|
| `daily_loss` | `daily_loss_limit` | session P&L vs limit |
| `daily_trades` | `user_daily_trade_limit` | count vs limit |
| `max_consecutive_losses` | `max_consecutive_losses` | `ctx.facts.consecutive_losses` |
| `cooldown` | `user_cooldown_min` | gap since last losing exit |
| `restricted_window` | `restricted_windows` | entry time in "HH:MM-HH:MM" |
| `max_trade_risk` | `max_position_size` + `trading_capital` | risk % vs limit |

**Thresholds** `constitution_approaching_pct` 0.80 and `constitution_severe_pct`
1.20 — both **unclassified**.

**Consolidation** several breaches on one trade merge into the most severe, with
`also_breached` in context. A breached rule at danger+ suppresses its paired
behavioural pattern (`_CONSTITUTION_PAIRS`).

**Evidence** cannot fire in the replay (`--no-rules`).

**Status: IMPLEMENTED BUT NOT YET VERIFIED.**

## 24. `same_symbol_obsession`

**Family** emotional · alerting · exit · level 2

**Logic** (`3078-3129`). All session trades on the same underlying plus the
current one. Needs `len(losses) >= obsession_min_losses` **and**
`reentries >= obsession_min_reentries`. Danger when the last quantity exceeds the
first, else caution.

**Thresholds** `obsession_min_losses` 3, `obsession_min_reentries` 2 — **both
unclassified.**

**Consolidation** **wins** the "going back to the same trade" family, over
`revenge_trade` and `rapid_reentry`.

**Evidence** 29 alerts / 20 sessions, **20 of them danger** — third-largest
danger source.

**Tests** **zero mentions.**

**Known issue** `size_rising` compares only first vs last quantity across
possibly different strikes, and raises severity a whole tier on that alone.
No test.

**Status: IMPLEMENTED, NOT TESTED.**

## 25. `time_of_day_bias`

**Family** performance · alerting · exit · level 1 · `uses_baseline`

**Logic** (`3137-3169`). Requires learned `danger_hours` and
`baseline_sessions >= tod_bias_min_sessions`. Fires caution quoting the trader's
own win rate for that hour.

**Thresholds** `tod_bias_min_sessions` 30 (**unclassified**). `baseline_sessions`
is not in `COLD_START_DEFAULTS`, but **it is resolved** — `threshold_resolution.py:514`
puts it from the baseline's `sessions_analyzed` at `Source.FACT`, and `:680` puts
0 when there is no profile.

*Correction to revision 1, which said this key "has no config key" and implied the
gate was broken. It is not: the detector is correctly silent until a baseline
exists. It has still never fired.*

**Evidence** never fired in 203 sessions. **Tests** zero mentions.

**Status: IMPLEMENTED, NEVER FIRED.**

## 26. `win_rate_collapse`

**Family** performance · analytics · trigger `session` · level 0

**Logic** (`3179-3205`). Needs a `baseline_win_rate` with confidence ≥ 0.5 and
≥ 8 trades today. Fires info when deterioration ≥ 0.4 of baseline.

**Thresholds** **none from config.** `0.5`, `8` and `0.4` are all inline
literals. Confidence is passed through from the baseline.

**Evidence** never fired. **Tests** zero mentions.

**Status: IMPLEMENTED, NEVER FIRED.**

## 27. `strategy_breakdown`

**Family** performance · analytics · trigger `session` · level 0

**Logic** (`3212-3252`). Requires both `baseline_win_rate` and
`baseline_profit_factor` at confidence ≥ 0.5, ≥ 8 trades, and **both** win-rate
deterioration ≥ 0.4 **and** profit factor ≤ 0.5× baseline. Confidence = min of
the two baseline confidences — the weakest-link rule, applied here and nowhere
else outside `revenge_trade`.

**Thresholds** none from config; `0.5`, `8`, `0.4`, `0.5` inline.

**Evidence** never fired. **Tests** zero mentions.

**Status: IMPLEMENTED, NEVER FIRED.**

---

# The six alias pattern types

## A1. `death_spiral` — L2 meta-detector

`behavior_scores_service.py:62-130`. A pure function over today's
`BehaviorEvent`s, **suppressed included**. Groups danger+ events by the
`nature` of their spec (with `_ALIAS_NATURE` filling in for alias names).
Fires when ≥ `spiral_warning_domains` distinct domains are present; escalates at
`spiral_critical_domains`. Adds time compression (`spiral_window_min`) and a
"continued escalation" flag once discipline **and** risk have both fired.

**Constants** `spiral_warning_domains` 2, `spiral_critical_domains` 3,
`spiral_window_min` 180, `spiral_domain_min_severity` "danger" — **all four
unclassified**, read directly from `COLD_START_DEFAULTS`, bypassing the
resolution ladder entirely.

**Evidence** 29 alerts / 29 sessions, **all danger**. The only `_COMPOSITES`
member: when it fires, **every other live alert on that trade is suppressed as
`absorbed:death_spiral`.**

The surrounding code records that `compute_scores` and the four driver scores
were removed 2026-08-13 because the weights did not rank with measured cost and
the severity multiplier had the wrong sign; death_spiral itself was left
unchanged and never read those scores.

**Status: IMPLEMENTED AND VERIFIED.**

## A2–A4. Position-monitor patterns — a separate pipeline

`position_monitor_tasks.py`, Celery beat every 30 seconds, 09:15–15:25 IST,
weekdays. These do **not** go through `BehaviorEngine`, the threshold ladder, the
registry loop, or `_consolidate`.

| pattern | trigger | constants |
|---|---|---|
| `holding_loser` | open position down ≥ 0.5% held ≥ 30 min | `HOLDING_LOSER_MIN_DURATION = 30`, `HOLDING_LOSER_MIN_LOSS_PCT = 0.5` — module-level literals |
| `overexposure` | `exposure_pct > max_size * 1.5` | the `1.5` is inline; `max_size` is the user's declared limit |
| `portfolio_concentration` | largest underlying / total exposure, docstring says levels 40/60/80%, requires 2+ open underlyings | levels not visible as named constants |

Dedup is scoped by `(rule, symbol)` (`position_monitor_tasks.py:501-509`) —
account-scoped when both are absent, which the comment notes is correct for
`portfolio_concentration` because that *is* an account-level statement.

`AVERAGING_DOWN_SIZE_INCREASE_PCT = 50` is defined at module level; no pattern
type in the vocabulary corresponds to it. **DEAD/UNUSED or UNKNOWN** — not
resolved here.

**Status: IMPLEMENTED, separate pipeline, outside every engine guarantee.**

## A5. `capital_mismatch`

Emitted by `maintenance_tasks.check_capital_reality`. Not a behaviour detector —
a housekeeping nudge that the declared trading capital no longer matches what the
account can deploy. It is in the vocabulary because it writes
`risk_alerts.pattern_type`, and the registry comment records that the contract
test is what found it missing from the map.

Participates in the "the position is too big" consolidation family, last.

---

# A. Cross-pattern duplicated logic

1. **Underlying extraction.** `parse_symbol(...).underlying` wrapped in
   try/except is re-implemented inline in at least eight detectors (#4, #7, #9,
   #12, #15, #16, #21, #24), three of them defining a local `_u`/`_underlying`
   helper. **NOT centralised — DEFERRED, and this is the finding.** They are
   *not* mechanically identical: #4 falls back to `ct.tradingsymbol or ""` when
   `underlying` is falsy, while #15 falls back to
   `_ps(...).underlying or ct.tradingsymbol or ""`. Those differ for any symbol
   the parser returns an empty underlying for. Centralising would silently pick
   one behaviour for eight detectors, which is exactly the kind of change this
   pass must not make.
2. ~~**Notional.** `_notional` defined as a static method AND re-defined as an
   identical local closure inside `_detect_martingale_behaviour`.~~ **FIXED.**
   The duplicate closure is deleted; martingale calls `self._notional`. The two
   bodies were character-identical, so this is arithmetic-preserving.
3. **The same-underlying-then-cross-instrument fallback** appears in four sizing
   detectors (#4, #7, #15, #21), each with its own trigger for switching
   (`len(prior)<3`, `len(prior)<2`, `len(prior_same)<2`, `len({underlyings})>1`)
   and each switching units from quantity to rupees mid-comparison.
4. **Expiry detection.** `is_expiry_day(symbol, date)` is called independently by
   #12, #13, #17, #18, with #13 additionally deriving monthly-vs-weekly from
   `len(parsed.expiry_key) == 7`.
5. **Session-bound derivation.** #12 and #20 derive exchange open/close from
   `exchange_constants`; **#19 hardcodes 09:15. NOT fixed — DEFERRED.** Aligning
   it would change which trades the detector flags on MCX, which is a
   behavioural change however obviously correct it looks.
6. ~~**SL order-type set** written out twice, in #6 and #13.~~ **FIXED.**
   Both now read the module constant `_STOP_ORDER_TYPES`; the values are
   unchanged and `test_stop_order_types_defined_once` asserts the literal
   appears only in the definition.
7. **Structure counting.** `count_structures` is called by #3 (twice) and #18.

# B. Shared constants and thresholds

**78 `COLD_START_DEFAULTS`. 33 classified in `threshold_registry`. 45 unclassified.**
(79/46 before the hygiene pass removed `confidence_alert_gate`.)

**Deliberately not reduced further.** A `Kind` is a claim about what a number
*is*; assigning 45 of them in a bulk pass would be guesswork wearing the
appearance of a decision — the same reason `DetectorSpec.frames` is empty on 26
of 27 specs. Each is classified at its own detector's review.

**The kind guard is real and was verified.** `violates_kind` is called inside
`put()` (`threshold_resolution.py:247`) and *refuses* the resolution, keeping
whatever was already there and recording the refusal, rather than accepting it
silently. A `universal_safety`, `product_policy` or `user_rule` threshold cannot
be resolved from HISTORY, SESSION or POPULATION. **KEEP AS-IS.**

Classification breakdown of the 33: `personal_baseline` 13 · `fallback` 8 ·
`universal_safety` 6 · `product_policy` 4 · `definitional` 2.

Keys read by more than one detector:

| key | readers |
|---|---|
| `daily_loss_limit` | #1 (escalation), #11 (meltdown), #23 (rule) |
| `trading_capital` | #10, #11, #23 |
| `user_cooldown_min` | #2, #23 |
| `max_consecutive_losses` | #23 (and #1 via the canonical streak) |
| `daily_trade_limit` / `daily_trade_danger` | #3 (and #23 via `user_daily_trade_limit`) |

**The 46 unclassified keys** (no `Kind`, so `violates_kind()` cannot protect them
and the ladder cannot know whether they may be personalised):

`baseline_target_sessions`, `baseline_target_trades`,
`burst_trades_per_30min_danger`, `consecutive_loss_danger`, `constitution_approaching_pct`,
`constitution_severe_pct`, `daily_trade_danger`, `daily_trade_limit`,
`direction_confusion_window_min`, `early_exit_min_samples`,
`fomo_close_window_min`, `fomo_open_window_min`, `fomo_window_min`,
`martingale_caution_multiplier`, `martingale_danger_multiplier`,
`martingale_min_losses`, `meltdown_caution_pct`, `meltdown_danger_pct`,
`no_stoploss_expiry_hold_min`, `no_stoploss_expiry_loss_pct`,
`no_stoploss_monthly_hold_min`, `no_stoploss_monthly_loss_pct`,
`obsession_min_losses`, `obsession_min_reentries`,
`opening_trap_large_loss_pct`, `opening_trap_window_end_min`,
`overconfidence_size_mul_caution`, `overconfidence_size_mul_danger`,
`premium_avg_down_loss_pct`, `premium_loss_expiry_shift_pct`,
`premium_loss_fast_hold_min`, `profit_giveaway_caution_pct`,
`profit_giveaway_danger_pct`, `profit_giveaway_min_erosion`,
`profit_giveaway_min_erosion_pct_capital`, `profit_giveaway_min_peak`,
`profit_giveaway_min_peak_pct_capital`, `recovery_bet_caution_mul`,
`recovery_bet_danger_mul`, `size_escalation_pct`, `spiral_critical_domains`,
`spiral_domain_min_severity`, `spiral_warning_domains`, `spiral_window_min`,
`tod_bias_min_sessions`.

**Numbers with no key at all** (inline literals that decide severity or firing):
`0.5` of daily limit (#1) · `30`-minute burst window (#3) · `3` session flips
(#9) · `0.05` of capital (#11) · `13:00` expiry cutoff (#18) · `09:15` market
open (#19) · `100` premium cap (#17) · `0.4`, `0.5`, `8` (#26, #27) ·
`1.5` exposure multiplier, `30`, `0.5`, `50` (A2–A4).

**`confidence_alert_gate` is gone** (hygiene pass) — it had zero readers and a
comment describing behaviour the engine does not have. Absent by decision, not
by oversight; `test_engine_hygiene.py::test_confidence_alert_gate_is_gone_and_stays_gone`
asserts it is not quietly reintroduced.

# C. Shared mechanisms

- **Feature flags** (migration 068). `detector_flags.resolve(name, account, flags)`
  → `off` (method not called) / `shadow` (runs, every event tagged
  `shadow=True`) / `on`. Registry `default_mode` is `"on"` for all 27.
- **Threshold recording.** When `ctx.thresholds` is a `RecordingThresholds`, the
  engine records which keys each detector actually read and attaches the
  provenance to the event as `thresholds_used`.
- **Strategy suppression.** `_STRATEGY_SUPPRESSED` (8 detectors: #2, #7, #4, #1,
  #5, #13, #21, #9) — when the trade belongs to a detected multi-leg structure,
  the event is marked `strategy_group:<type>` rather than dropped.
- **Constitution suppression.** A user rule breached at danger+ suppresses its
  paired behavioural pattern's notification. The event is still recorded.
- **Consolidation** (`_consolidate`, `785-851`): composites absorb; within a
  family the most specific wins; multiple rule breaches merge into one. Nothing
  is deleted — folded events keep a `_suppressed` marker. Explicitly **not** a
  cap.
- **Session alert cap.** `alert_session_hard_cap` = 8, applied in
  `trade_tasks.py:1656`, **after** consolidation, via an atomic
  `consume_alert_budget`. Past the cap only `critical` survives. A missing
  session row means "budget unknown" and the cap is **not** applied.
- **Write gate.** `_persist_events` (`trade_tasks.py:120+`) drops `info` events
  from **alerting**-disposition detectors unless they carry `_suppressed` or
  `_verdict`. Analytics-disposition info is always kept.
- **Notification routing.** Guardian-eligible alerts (`session_meltdown`,
  `constitution_violation`, `death_spiral`) get their own push; other pushable
  alerts are merged into one notification when there is more than one.
- **Hot path.** Per CompletedTrade, `_load_context` issues roughly four queries:
  `UserProfile`, active `Cooldown`s, `Trade.order_type` for exit types, plus
  session trades. Detectors themselves issue **no** DB queries and make **no**
  external calls — every detector is pure over `ctx`.

# D. Consolidation relationships

```
COMPOSITE   death_spiral  ──absorbs──▶  every other live non-info alert

FAMILY  "sizing after losses"
        martingale_behaviour  ▶  post_loss_recovery_bet  ▶  size_escalation

FAMILY  "going back to the same trade"
        same_symbol_obsession  ▶  revenge_trade  ▶  rapid_reentry

FAMILY  "the position is too big"
        excess_exposure  ▶  overexposure  ▶  portfolio_concentration  ▶  capital_mismatch

CONSTITUTION PAIRS (breached rule silences the behavioural twin)
        cooldown               → revenge_trade
        max_consecutive_losses → consecutive_loss_streak
        daily_trades           → overtrading_burst, daily_overtrading
        max_trade_risk         → excess_exposure
        daily_loss             → session_meltdown
```

# E. Patterns that appear to overlap but are in no family

- **`options_premium_avg_down` (#16)** vs `martingale_behaviour`,
  `same_symbol_obsession`, `revenge_trade` — all four can describe one re-entry
  into a losing underlying. #16 belongs to no family and is not paired with any
  constitution rule, so it fires alongside whichever of the others survives.
- **`premium_loss_event` (#17)** vs **`no_stoploss` (#13)** — both fire on a
  large percentage loss on the same long option, with different denominators
  (premium in both cases for CE/PE) and different ladders (40/60/80 vs 25/50).
- **`expiry_day_overtrading` (#18)** vs **`daily_overtrading`** and
  **`overtrading_burst`** — three count-based pace patterns, all
  structure-counted, no family between them.
- **`consecutive_loss_streak` (#1)** vs **`session_meltdown` (#11)** — #1's
  loss-size escalation branch and #11 both measure cumulative loss against
  `daily_loss_limit`, at 0.5 and 0.40/0.75 respectively.
- **`direction_instability` Level 2** vs **`options_premium_avg_down`** — a
  CE→PE flip on one underlying after a loss satisfies both.

# F. Patterns with no or weak production evidence

| pattern | alerts in 203 sessions | why |
|---|---|---|
| `time_of_day_bias` | 0 | needs 30+ baseline sessions; correctly silent without a baseline, not broken |
| `win_rate_collapse` | 0 | needs a confident baseline; ≥8 trades/day is rare in this book |
| `strategy_breakdown` | 0 | needs two confident baselines and both collapses |
| `cooldown_violation` | 0 | rules disabled in replay |
| `constitution_violation` | 0 | rules disabled in replay |
| `no_stoploss` | skipped | tradebook has no order-type column |
| `excess_exposure` | skipped | capital-derived, unvalidatable |
| `session_meltdown` | skipped | capital-derived, unvalidatable |
| `post_loss_recovery_bet` | 2 | fires, but twice in a year |
| `end_of_session_mis_panic` | 2 | fires, but twice in a year |
| `overexposure`, `portfolio_concentration`, `holding_loser`, `capital_mismatch` | 0 | different pipeline, not exercised by replay |

**Zero test mentions** (8): `daily_overtrading`, `excess_exposure`,
`post_loss_recovery_bet`, `same_symbol_obsession`, `strategy_breakdown`,
`time_of_day_bias`, `win_rate_collapse`, `winning_streak_overconfidence`.

Two of those — `daily_overtrading` (37 alerts) and `same_symbol_obsession`
(29 alerts, 20 danger) — are among the highest-volume patterns in the book.

# G. Implementation-vs-contract discrepancies

Shown as found; not reconciled.

1. ~~**`fomo_expiry_day_symbols`** — inline default 2 vs configured 4.~~
   **FIXED.** Inline default aligned to 4. `resolve_thresholds` always supplies
   the key, so the 2 was unreachable and behaviour is unchanged. *Whether 4 is
   the right number — it is less sensitive than the general threshold of 3 on
   the day the comments treat as most dangerous — is DEFERRED to the `fomo_entry`
   review.*
2. ~~**`profit_giveaway_min_peak`** — inline default 1000 vs configured 1500.~~
   **FIXED.** Aligned to 1500. Same reasoning: the resolved value has always
   been 1500 and scales with capital via `_CAPITAL_RATIOS`.
3. ~~**`opening_5min_trap` severity** — computed then discarded.~~ **FIXED.**
   The dead `severity = "danger" if ... else "caution"` line is removed. The
   event has returned `"info"` since the Phase 4 analytics flip and still does;
   the two flags still select the message. *Whether this detector should alert
   at all is DEFERRED to its review.*
4. ~~**`rapid_reentry` comment** — claimed its evidence "feeds revenge
   confidence".~~ **FIXED (comment only).** `revenge_trade` 3.0.0 takes its
   confidence from `confidence.from_observables` and never reads this event.
5. **`trigger="session"`** — the registry declares it for `early_exit`,
   `win_rate_collapse`, `strategy_breakdown` and documents that such detectors
   *"will move to EOD evaluation in Phase 4+"*. All three are called from the
   per-CompletedTrade loop. **DOCUMENTED BUT NOT IMPLEMENTED.**
6. **`trigger="entry"`** — registry says *"'entry' arrives with Phase 6"*, and
   all 27 specs still say `exit`. But 10 detectors already run at entry via
   `entry_detectors.ENTRY_DECIDABLE`, and three alias patterns run entry-time in
   `position_monitor_tasks`. The registry's `trigger` field does not describe
   current behaviour.
7. **`expiry_day_overtrading` copy** — the detector message ships unsourced
   statistics ("loss rate above 85%", "statistically reduces your edge"), which
   the registry's own copy rules forbid in writing.
8. **`profit_giveaway` dedup** — the comment at `2867` says DB-level dedup
   *"prevents this from firing more than once per session"*; the replay shows
   26 alerts across 12 sessions.
9. **`martingale_behaviour` ratio** — the displayed sequence includes the current
   trade; the `max_ratio` that decides severity does not. **NOT FIXED — DEFERRED.**
   Which trades should enter the ratio is a detector-definition question, not a
   typo. Now pinned by `test_ratio_is_computed_from_priors_only`, which asserts
   current behaviour so the review can change it deliberately.
10. ~~**`confidence_alert_gate`** — defined with a comment describing alert
    suppression it no longer performs; zero readers.~~ **FIXED.** The definition
    and its stale "signal points" header are removed from `COLD_START_DEFAULTS`
    (78 constants now, was 79). Verified not recreated by any floor or default
    loop. The gate stays **absent** and global confidence suppression stays
    **DEFERRED** — see `docs/contracts/confidence_alert_gate_CLOSED.md`. Nothing
    was restored and no replacement was designed.
11. **`frames`** — declared on 1 of 27 specs. The registry documents this as
    deliberate, so it is a known gap rather than a contradiction, but it means
    the "normal is not safe" invariant is machine-checkable for `revenge_trade`
    only.
12. **`AVERAGING_DOWN_SIZE_INCREASE_PCT = 50`** in `position_monitor_tasks.py`
    with no corresponding pattern type. **UNKNOWN** — not traced in this pass.

---

## Status summary

| status | count | patterns |
|---|---|---|
| IMPLEMENTED AND VERIFIED | 13 | #1, #2, #3, #4, #7, #9, #12, #16, #17, #18, #20, #22, death_spiral |
| IMPLEMENTED BUT NOT YET VERIFIED | 6 | #8, #10, #11, #23, #13, #6 |
| IMPLEMENTED, NOT TESTED (fires in replay) | 4 | #3b, #15, #21, #24 |
| IMPLEMENTED, NEVER FIRED | 3 | #25, #26, #27 |
| IMPLEMENTED, evidence-only (analytics) | 3 | #5, #14, #19 |
| IMPLEMENTED, separate pipeline | 4 | overexposure, portfolio_concentration, holding_loser, capital_mismatch |
| DOCUMENTED BUT NOT IMPLEMENTED | — | `trigger` semantics (session/entry) across 6 specs |
| DEAD/UNUSED | 2 | `confidence_alert_gate`; computed severity in #19 |
| UNKNOWN | 1 | `AVERAGING_DOWN_SIZE_INCREASE_PCT` |

**Reviewed: 1 of 33.**

---

# H0. Hygiene pass — full audit table

Every finding the pass produced, with its classification. The nine rows marked
FIX NOW are detailed in H below; everything else is in the DEFERRED register.

| Finding | Evidence | Classification | Action | Behaviour changed? | Tests | Pattern review required? |
|---|---|---|---|---|---|---|
| `fomo_expiry_day_symbols` inline default 2 vs configured 4 | `resolve_thresholds` returns 4, so the inline value is unreachable | **FIX NOW** | inline default to 4 | **No** | `test_inline_defaults_agree_with_cold_start_defaults` | **Yes** — is 4 right when the general threshold is 3? |
| `profit_giveaway_min_peak` inline default 1000 vs configured 1500 | resolves to 1500.0; also scales via `_CAPITAL_RATIOS` | **FIX NOW** | inline default to 1500 | **No** | same contract test | No |
| `opening_5min_trap` computes a severity and discards it | `pyflakes` L2582 `local variable 'severity' is assigned to but never used` | **FIX NOW** | dead line removed | **No** | `TestOpeningTrapSeverity` (3) | **Yes** — should it alert at all? |
| `size_escalation` computes `cross` and never reads it, so a rupee sequence prints as "qty" | `pyflakes` L1417 | **FIX NOW** | message labels rupees; `cross_instrument` added to context | **Message only** | `test_size_escalation_cross_instrument_reports_rupees_not_qty` | **Yes** — 30% threshold applied to notional |
| `_notional` re-defined as a local closure in martingale | bodies character-identical | **FIX NOW** | closure deleted | **No** | `TestMartingaleLadder` (4) | No |
| SL order-type set written out in two detectors | 2 sites, identical literal | **FIX NOW** | module constant `_STOP_ORDER_TYPES` | **No** | `test_stop_order_types_defined_once` | No |
| `confidence_alert_gate` defined with a comment describing suppression it no longer performs | 0 readers across `backend/` and `src/` | **FIX NOW** | constant + stale header removed | **No** — verified not recreated by any floor/default loop | `test_confidence_alert_gate_is_gone_and_stays_gone` | No — stays DEFERRED |
| `rapid_reentry` comment claims it "feeds revenge confidence" | `revenge_trade` 3.0.0 uses `confidence.from_observables` | **FIX NOW** | comment corrected | **No** | n/a | No |
| `_holding_loser_task` queries `UserProfile` and calls `get_thresholds()`, reads neither | `pyflakes` L279 | **FIX NOW** | dead block removed | **No alert change**; one fewer DB round-trip | `pyflakes` clean | No |
| Underlying extraction re-implemented in 8 detectors | fallbacks **differ**: #4 to `""`, #15 to the symbol | **DEFER** | not centralised | — | — | **Yes** |
| Same-underlying to cross-instrument fallback in 4 detectors | 4 switch conditions, 3 unit changes | **DEFER** | none | — | — | **Yes** |
| 09:15 hardcoded in `opening_5min_trap` | #12 and #20 derive it from `exchange_constants` | **DEFER** | none — fixing changes what fires on MCX | — | — | **Yes** |
| `martingale` `max_ratio` excludes the current trade | displayed sequence includes it | **DEFER** | pinned, not changed | — | `test_ratio_is_computed_from_priors_only` | **Yes** |
| `same_symbol_obsession` `size_rising` compares first vs last qty across strikes | raises severity a full tier alone | **DEFER** | none | — | `TestSameSymbolObsession` (3) | **Yes** |
| ~~`consecutive_loss_streak` `0.5`-of-limit escalation~~ | inline literal, no key | **CLOSED 26 Aug** | deleted with its detector — it had fired 0 times in 106 | — | — | No |
| `expiry_day_overtrading` unsourced statistics in shipped copy | "loss rate above 85%" | **DEFER** | none | — | — | **Yes** |
| `expiry_day_overtrading` 13:00 cutoff | inline literal | **DEFER** | none | — | — | **Yes** |
| `direction_instability` 3-flip count; two keys both = 10 | inline literal | **DEFER** | none | — | — | **Yes** |
| `session_meltdown` invents a limit at 5% of capital | inline `0.05` | **DEFER** | none | — | — | **Yes** |
| `profit_giveaway` `_typical_loss` reads today's losses only | docstring describes a cross-session figure | **DEFER** | none | — | — | **Yes** |
| `profit_giveaway` fires 26 times on 12 days | comment claims once-per-session dedup | **DEFER** | none | — | — | **Yes** |
| `winning_streak_overconfidence` danger tier never fired | 0 in 203 sessions | **DEFER** | none | — | `TestWinningStreakOverconfidence` (4) | **Yes** |
| `options_premium_avg_down` in no consolidation family | can fire beside every pattern describing the same re-entry | **DEFER** | none | — | — | **Yes** |
| 45 constants with no `Kind` | `THRESHOLD_SPECS` covers 33 of 78 | **DEFER** | not bulk-classified | — | — | Per detector |
| `trigger` field says `session`/`exit` where execution differs | 6 specs say `session` but run per trade; 10 detectors already run at entry | **DEFER** | recorded only | — | — | Architecture |
| `AVERAGING_DOWN_SIZE_INCREASE_PCT = 50` | module-level, no matching pattern type | **UNKNOWN** | recorded, not traced | — | — | **Yes** |
| `no_stoploss`, `panic_exit` unverifiable | tradebook has no order-type column | **RESEARCH REQUIRED** | none | — | — | Blocked on live order data |
| `excess_exposure`, `session_meltdown` unverifiable | capital moved 30k-50k across the period | **RESEARCH REQUIRED** | none | — | — | Blocked on a stateable capital figure |
| `time_of_day_bias`, `win_rate_collapse`, `strategy_breakdown` never fired | 0 in 203 sessions | **RESEARCH REQUIRED** | guards pinned so "correctly silent" is distinguishable from "unreachable" | — | `TestPerformanceDetectorGuards` (6) | Yes, after evidence |
| `revenge_trade` | AUC 0.482, no fill-level signature separates | **RESEARCH REQUIRED** | **FROZEN** — untouched | **No** | 12 files | Last, and only with new data |
| Kind guard blocks personal sources on safety/policy thresholds | `violates_kind` called inside `put()`, refuses and records | **KEEP AS-IS** | none | — | verified | No |
| `RecordingThresholds` captures reads | verified for both `.get()` and `[]` | **KEEP AS-IS** | none | — | verified | No |
| Structure counting via `count_structures` | already one shared helper | **KEEP AS-IS** | none | — | — | No |
| Expiry detection via `is_expiry_day` | already one shared helper | **KEEP AS-IS** | none | — | — | No |

**Totals — A. FIXED NOW 9 · B. DEFERRED 20 · C. RESEARCH REQUIRED 4 · D. KEEP AS-IS 4.**

---

# H. Hygiene pass — what changed, 24 Aug 2026

Nine changes. Every one is a bug fix, a dead-code removal or a comment. **No
behavioural definition, threshold value, severity rule, sensitivity, merge rule
or personalisation strategy was touched.**

| # | what was wrong | what changed | source of truth | behaviour changed? | proof |
|---|---|---|---|---|---|
| 1 | `fomo_entry` read inline default **2**; config and registry say **4** | inline default to 4 | `COLD_START_DEFAULTS` and `THRESHOLD_SPECS` agree on 4 | **No** — `resolve_thresholds` always supplies the key, so the 2 was unreachable | `test_inline_defaults_agree_with_cold_start_defaults` |
| 2 | `profit_giveaway` read inline default **1000**; config says **1500** | inline default to 1500 | `COLD_START_DEFAULTS`, and the key scales via `_CAPITAL_RATIOS` | **No** — same reason | same contract test |
| 3 | `opening_5min_trap` computed a severity and discarded it | dead line removed; returned `"info"` unchanged | Phase 4 analytics disposition in the registry | **No** | `TestOpeningTrapSeverity`, both branches |
| 4 | `size_escalation` computed `cross` and never read it, printing a **rupee** sequence labelled **"qty"** | message labels rupees when cross-instrument; `cross_instrument` added to context | the labelling `martingale_behaviour` already does | **Message only.** Detection, threshold and severity untouched | `test_size_escalation_cross_instrument_reports_rupees_not_qty` |
| 5 | `_notional` re-defined as an identical local closure in martingale | closure deleted, calls `self._notional` | bodies were character-identical | **No** | `TestMartingaleLadder` |
| 6 | the SL order-type set written out in two detectors | module constant `_STOP_ORDER_TYPES` | values unchanged | **No** | `test_stop_order_types_defined_once` |
| 7 | `confidence_alert_gate` defined with a comment describing suppression it no longer performs; zero readers | constant and its stale "signal points" header removed | `confidence_alert_gate_CLOSED.md` | **No** — verified not recreated by any floor/default loop | `test_confidence_alert_gate_is_gone_and_stays_gone` |
| 8 | `rapid_reentry` comment claimed its evidence "feeds revenge confidence" | comment corrected | `revenge_trade` 3.0.0 uses `confidence.from_observables` | **No** — comment only | n/a |
| 9 | `_holding_loser_task` ran a `UserProfile` query and `get_thresholds()` and read neither | dead block removed | `pyflakes`: `thresholds` assigned, never used | **No alert change.** One fewer DB round-trip per check | `pyflakes` clean |

**Two traps this pass walked into and out of, recorded so the next pass does not
repeat them.** The `profile`/`thresholds` block appears **four** times in
`position_monitor_tasks.py` and only the one at line 279 is dead — a whole-file
replace would have broken three live call sites. And the underlying-extraction
helpers *look* identical across eight detectors but are not (see A.1). Both were
caught by checking readers rather than trusting a match.

**Tests added: 31**, in `backend/tests/test_engine_hygiene.py`. Suite went from
1,047 to 1,078 passing.

The most valuable of them is not a detector test.
`test_inline_defaults_agree_with_cold_start_defaults` parses every
`ctx.thresholds.get(key, N)` in the engine and fails if any `N` contradicts
`COLD_START_DEFAULTS`. That closes the whole class rather than the two instances.

---

# DEFERRED TO PATTERN REVIEWS

Nothing here is fixed. Nothing here is hidden.

### Detector-definition questions — need the pattern's own evidence

| item | pattern | question |
|---|---|---|
| expiry threshold is **4** vs general **3** | `fomo_entry` | expiry day is treated as *less* sensitive than an ordinary window. Intended? |
| `max_ratio` excludes the current trade | `martingale_behaviour` | the displayed sequence includes it. Which is the claim? Pinned by test |
| 30% escalation applied to **notional** in the cross-instrument branch | `size_escalation` | a threshold whose meaning was set for lots, applied to rupees |
| `size_rising` = last qty > first qty, across possibly different strikes | `same_symbol_obsession` | raises severity a whole tier on that alone |
| hardcoded 09:15 market open | `opening_5min_trap` | patterns 12 and 20 derive it per exchange; this does not, so it is wrong for MCX. Fixing changes what fires |
| name says 5 minutes, threshold is 10, message says 09:15-09:25 | `opening_5min_trap` | three different windows in one detector |
| should it alert at all? | `opening_5min_trap` | currently analytics-only with a hardcoded `info` |
| unsourced statistics in the shipped message | `expiry_day_overtrading` | "loss rate above 85%", "statistically reduces your edge" — the registry's own copy rules forbid this |
| `_typical_loss` reads **today's** losses only | `profit_giveaway` | the docstring describes a stable cross-session loss size |
| 26 alerts across 12 sessions | `profit_giveaway` | the comment claims DB dedup limits it to once per session |
| the `0.5`-of-daily-limit escalation branch | `consecutive_loss_streak` | inline literal, no key, no test, decides a danger tier |
| the 13:00 expiry cutoff | `expiry_day_overtrading` | inline literal |
| the `3`-flip Level 3 count | `direction_instability` | inline literal; two keys of value 10 drive the two windows |
| `0.05` of capital as an invented daily limit | `session_meltdown` | fires on a number the trader never set |
| the danger tier has never fired | `winning_streak_overconfidence` | 5 wins **and** 2x size never co-occurred in 203 sessions |
| no family membership | `options_premium_avg_down` | can fire alongside every pattern describing the same re-entry |

### Infrastructure deferred

| item | why not now |
|---|---|
| centralising underlying extraction | the eight implementations differ in their fallback (A.1) |
| centralising the same-underlying to cross-instrument fallback | four detectors, four switch conditions, three unit changes |
| classifying the remaining 45 constants | a `Kind` is a claim; assigning them in bulk is guesswork |
| `trigger` field semantics (`session` / `entry`) | the registry describes a Phase 4+/Phase 6 plan; 6 specs say `session` but run per trade, and 10 detectors already run at entry. Changing the field is documentation; changing execution is architecture |
| `AVERAGING_DOWN_SIZE_INCREASE_PCT = 50` | **UNKNOWN.** Module-level in `position_monitor_tasks.py` with no corresponding pattern type. Not traced |
| unused imports in `position_monitor_tasks.py`, `behavior_scores_service.py` | cosmetic; left to avoid widening the diff |

### Research required

| item | what evidence would settle it |
|---|---|
| `no_stoploss`, `panic_exit` | live order data — the tradebook has no order-type column, so 203 sessions say nothing about either |
| `excess_exposure`, `session_meltdown` | a stateable capital figure; capital moved 30k-50k across the period |
| `time_of_day_bias`, `win_rate_collapse`, `strategy_breakdown` | a trader with a mature baseline and 8-trade days. Guards are now pinned, so "correctly silent" is distinguishable from "unreachable" |
| `revenge_trade` | **FROZEN by decision.** No new threshold, no 3-attempt episode rule, no score, no replacement detector, no global confidence gate. Findings stand in `docs/research/REVENGE_FINAL_EVIDENCE_REVIEW.md`. Revisit after other reviews and potentially after order-level data |

---

# REVIEW STATUS — updated as each pattern moves

The live tracker. One row per pattern, in review order. Status values:
**NOT STARTED · IN PROGRESS · ON HOLD · COMPLETE · FROZEN**.

Updated at every state change, not at the end. If a pattern goes ON HOLD the
reason goes in the notes column, not into someone's head.

| # | pattern | status | started | finished | notes |
|---|---|---|---|---|---|
| — | *(shared foundation)* | **COMPLETE** | — | 23 Aug 2026 | F1–F5; `session_facts`, threshold ladder, maturity, confidence, instrument risk |
| — | *(pre-pattern hygiene)* | **COMPLETE** | 24 Aug 2026 | 24 Aug 2026 | 9 fixed, 20 deferred, commit `1a0940f` |
| 2 | `adding_to_adverse_position` | **COMPLETE** | 24 Aug 2026 | 24 Aug 2026 | v2.0.0. **Corrected replay: 99 alerts / 56 days, 4/4 checks PASS, episode dedup verified in the real path.** `patterns_1_2_3_replay_closeout.md` |
| 1 | `martingale_behaviour` | **COMPLETE** | 24 Aug 2026 | 24 Aug 2026 | v2.0.0. **Corrected replay: 39 alerts / 36 days, 5/5 definition checks PASS, multipliers hold unchanged.** `patterns_1_2_3_replay_closeout.md` |
| 3 | `same_symbol_obsession` | **COMPLETE** | 24 Aug 2026 | 24 Aug 2026 | v2.0.0. Persistence on one underlying - the only detector that sees it WITHOUT escalation (4 of 20 episodes are invisible to everything else). Severity = peak vs first, stable by construction; `obsession_min_reentries` deleted as unreachable. 23 tests. **Corrected replay: 22 alerts / 21 days.** Entry-triggering measured and rejected — later in 14/20 episodes, never in 6. `same_symbol_obsession_contract.md` |
| 5 | `overtrading_burst` + `daily_overtrading` | **`daily_overtrading` DONE · `overtrading_burst` DEFERRED** | 26 Aug 2026 | 26 Aug 2026 | `daily_overtrading` **MODIFY**: the line is the trader's own p75, so it alerts on 25% of sessions by construction; and heavy days are this trader's BEST days — 2% of the book's loss across 26% of sessions, the 141 positions past the line net **+Rs 1,265**, and all three momentum markers point the wrong way. `overtrading_burst` **DEFER**: 12 alerts, never fired alone, n too small to judge. `05-overtrading/` |
| 4 | `consecutive_loss_streak` | **RETIRED — DELETED** | 26 Aug 2026 | 26 Aug 2026 | Trigger is chance: 63 sessions with a 3+ run observed, 63.0 expected of 189. Detector deleted; the trader's own `max_consecutive_losses` rule under `constitution_violation` keeps the behaviour and gained the warning rung that was unreachable at limits 2/3/4 — including the onboarding default of 3. `04-consecutive_loss_streak/STATUS.md` |
| 5 | `overtrading_burst` + `daily_overtrading` | NOT STARTED | — | — | reviewed together — one method, two pattern types |
| 6 | `profit_giveaway` | NOT STARTED | — | — | 26 alerts / 12 days |
| 7 | `fomo_entry` | NOT STARTED | — | — | expiry threshold question inherited from hygiene |
| 8 | `premium_loss_event` | NOT STARTED | — | — | only source of `critical` |
| 9 | `expiry_day_overtrading` | NOT STARTED | — | — | copy breaks the no-unsourced-statistics rule |
| 10 | `size_escalation` | NOT STARTED | — | — | after #1 decides the family |
| 11 | `direction_instability` | NOT STARTED | — | — | |
| 12 | `session_meltdown` | **ON HOLD** | — | — | blocked: capital not stateable for the replay period |
| 13 | `excess_exposure` | **ON HOLD** | — | — | blocked: same |
| 14 | `no_stoploss` | **ON HOLD** | — | — | blocked: tradebook has no order-type column |
| 15 | `rapid_reentry` | NOT STARTED | — | — | analytics-only |
| 16 | `panic_exit` | **ON HOLD** | — | — | blocked: needs order types |
| 17 | `early_exit` | NOT STARTED | — | — | analytics-only |
| 17 | `opening_5min_trap` | NOT STARTED | — | — | three windows in one detector |
| 18 | `time_of_day_bias` | **ON HOLD** | — | — | blocked: never fired, needs a mature baseline |
| 19 | `win_rate_collapse` | **ON HOLD** | — | — | blocked: same |
| 20 | `strategy_breakdown` | **ON HOLD** | — | — | blocked: same |
| 21 | `cooldown_violation` | NOT STARTED | — | — | cannot fire under `--no-rules` |
| 22 | `constitution_violation` | NOT STARTED | — | — | 6 rules in one pattern type |
| 23 | `options_premium_avg_down` | NOT STARTED | — | — | in no consolidation family |
| 24 | `end_of_session_mis_panic` | NOT STARTED | — | — | 2 alerts |
| 25 | `winning_streak_overconfidence` | NOT STARTED | — | — | danger tier has never fired |
| 26 | `post_loss_recovery_bet` | NOT STARTED | — | — | 2 alerts |
| M | `death_spiral` (meta) | NOT STARTED | — | — | after #1–#4; consumes their output |
| P | `overexposure` / `portfolio_concentration` / `holding_loser` | NOT STARTED | — | — | separate pipeline, reviewed as a group |
| H | `capital_mismatch` | NOT STARTED | — | — | housekeeping, not a behaviour detector |
| 27 | `revenge_trade` | **FROZEN** | 23 Aug 2026 | — | by decision. No new threshold, no episode rule, no score, no replacement, no global confidence gate. `docs/research/REVENGE_FINAL_EVIDENCE_REVIEW.md` |

---

# Recommended order for the pattern reviews

Ordered by *evidence available per unit of risk carried* — patterns that fire
often, decide `danger`, and can actually be measured against the replay first.

| order | pattern | why here |
|---|---|---|
| 1 | `martingale_behaviour` | 36 alerts, **26 danger** — the largest danger source. Two open definition questions (ratio excludes the current trade; the unit switch). Rich evidence |
| 2 | `same_symbol_obsession` | 29 alerts, **20 danger**, no tests until now. Overlaps pattern 1's family and wins the other one |
| 3 | `consecutive_loss_streak` | 61 alerts, the most frequent. One inline literal decides a danger tier |
| 4 | `overtrading_burst` + `daily_overtrading` | 49 combined; the alias out-fires its own spec 3:1. Review together — one method, two pattern types |
| 5 | `profit_giveaway` | 26 alerts on 12 days; a dedup claim the replay contradicts and a `_typical_loss` that does not match its docstring |
| 6 | `fomo_entry` | 28 alerts, widest test coverage, one live semantic question |
| 7 | `premium_loss_event` | the only source of `critical`; the instrument-derived alternative belongs to it |
| 8 | `expiry_day_overtrading` | 28 alerts, and its shipped copy breaks the project's own no-unsourced-statistics rule |
| 9 | `size_escalation` | 9 alerts; already loses its family to pattern 1, so review after that family is decided |
| 10 | `direction_instability` | 10 alerts, two windows of equal value, one inline count |
| 11-13 | `session_meltdown`, `excess_exposure`, `no_stoploss` | blocked on evidence, not on thinking — schedule after the measurable ones |
| 14+ | analytics-only and never-fired | `rapid_reentry`, `panic_exit`, `early_exit`, `opening_5min_trap`, `time_of_day_bias`, `win_rate_collapse`, `strategy_breakdown` |
| last | `revenge_trade` | frozen by decision; revisit only with new data |

`death_spiral` should be reviewed **after** at least 1-4, because it consumes
their output and absorbs every other alert when it fires. The three
position-monitor patterns are a separate pipeline and should be reviewed as a
group, not interleaved.

