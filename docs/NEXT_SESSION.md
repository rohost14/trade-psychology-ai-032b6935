# Next session — start here

**30 Aug 2026.** Patterns **12 through 18 are CLOSED**. Engine is at **20
detectors, 26 pattern types, 6 aliases** — `all_pattern_types()` is the
authority and the retirement suites pin all three.

**Eight retirements** (4, 6, 9, 10, 11, 14, 15, 18), every one on measurement,
never on taste. Since the last update to this file:

| # | pattern | outcome |
|---|---|---|
| 12 | `no_stoploss` | MODIFIED — the exit mechanism is now stated only when observed |
| 13 | `rapid_reentry` | KEEP AS-IS — its unreachable CAUTION path is a **design inconsistency, not a bug** |
| 14 | `panic_exit` | RETIRED — subject did not exist; short holds performed the same as long |
| 15 | `cooldown_violation` | RETIRED — precondition never occurred live; 0 firings against `constitution_violation`'s 181 |
| 16 | `excess_exposure` | DEFERRED by decision, pending live broker-margin validation |
| 17 | `session_meltdown` | MODIFIED — the undocumented 5%-of-capital fallback removed from **both** sites; abstains without a declared limit; **no replacement percentage** |
| 18 | `early_exit` | RETIRED — right measure, wrong scope; shuffle null **p = 0.610** |

## Next: review 19 = source-list #15 `winning_streak_overconfidence`

**Review order is not the source-list numbering.** It walks
`docs/patterns/00-shared/BEHAVIOURAL_PATTERNS.md` ascending and skips what is
done; review 18 was source #14, so the next unreviewed source entry is #15.

Standing protocol: review first → measure against the real book → **no code
until the behavioural decision is justified** → explicit approval before
implementing. Sections: *Current behaviour · What is correct · Problems found ·
Evidence · Recommended behavioural contract · Exact changes required · Verdict*.

**Pace, agreed 28 Aug and held since:** review → measure → decide → implement →
tests → **one** replay. If that replay is clean on the **independent**
detectors, the pattern closes. Never run a second replay to explain a composite:
`death_spiral` counts detectors, so it moves whenever one is removed — that is
arithmetic, not a regression. If infrastructure eats a replay twice, close on
the test evidence and record the gap.

**This machine has never completed a 203-session replay** — 6 attempts over two
days, all environment failures. Budget accordingly; do not plan around one.
Patterns 12-18 all closed on in-process measurement plus mutation-checked tests.

**Standing instruction from the user:** pending items go to
`docs/DEEP_REVIEW/PENDING_AND_TODO.md` for **one consolidated pass after all
reviews**. Do not interrupt the sequence to fix them.

---

# Next session — start here

> **The live checklist is now `docs/ENGINE_BACKLOG.md`** — verified findings only.
> This file remains the narrative orientation: how we got here and why.

State at end of 22 Aug 2026. Branch `dashboard-production-readiness`, clean and
pushed through `995819c`.

**22 Aug in one line:** three user-facing bugs fixed, the baseline two-writer
race closed, a contract test added that makes pattern-vocabulary drift
impossible, and 23 stale documents archived. Nothing touching capital-relative
thresholds — that decision is still open.

Earlier state (13 Aug): **716 backend tests passed** (`pytest tests/ --ignore=tests/production` — the
`tests/production/` suite needs a live server on localhost and its 35
`ConnectError` failures are environmental, not real). Was 733; the 17 removed
are exactly the tests whose subject the L3 retirement deleted. Frontend: 102
vitest tests, typecheck clean, 0 lint errors.

**Environment note:** `email-validator==2.3.0` is pinned in
`backend/requirements.txt` but was missing from `.venv` — `from app.main import
app` failed on a clean tree until it was installed. If boot fails with
`ImportError: email-validator is not installed`, that is the cause, not your
change.

Supersedes the 11 Aug note. That note's four items are addressed or reordered:
items 2 and 3 (retire `post_loss_recovery_bet`, move `time_of_day_bias`) are
still open and still cheap; item 1 (readable replay report) is still open; item
4 (extend `recall_check`) is DONE.

---

## Do this first

**Run the replay.** Two changes since it was last run are NOT replay-verified
and both move thresholds: the v2 baseline (`05962ae`) and the capital-relative
rupee floors (`91975d4`). Expect **388 alerts / 203 sessions** on the repaired
harness — the older 358/359 figures came from the harness that dropped 8.4% of
fills, fixed in `6812b3f`. A replay takes ~40 minutes, not the fifteen its
docstring claims, and only ONE may run at a time.

Run it, then diff:

```
python tradedesk/scripts/replay_tradebook.py docs/tradebook-CY6001-FO2025-26.csv \
    --capital 50000 --no-rules
python tradedesk/scripts/replay_diff.py <baseline>.json \
    docs/tradebook-CY6001-FO2025-26-replay.json
```

Expected: **388 alerts, 203 sessions**. Ordering may differ on a handful of days
— that is cosmetic (`created_at` is wall-clock and breaks ties between alerts
sharing a trade's `detected_at`). A COUNT difference is real and means one of the
two unverified changes above moved a threshold; that is expected, and the job is
to decide whether the movement is right, not to assume a regression.

**If it reports COUNT or PATTERN differences, do not assume a code regression.**
Three times in one session I diagnosed one and was wrong every time. Check in
this order: (1) was a second replay running — they share one synthetic account
and deadlock on `INSERT INTO risk_alerts`, showing up as days with zero trades;
(2) is the comparison baseline from the same code. There is now a lockfile
guard (`tradedesk/.replay.lock`) that refuses a concurrent run, so cause (1)
should be impossible. Note `ps aux` in Git Bash does NOT see native Windows
Python — use PowerShell `Get-Process python`.

---

## What was done today

### Measurement

**Recall is now measured per day, not by comparing totals.** The old table
counted "31 martingale alerts against 40 days of the behaviour", which is two
different units — two sets can overlap on twenty days and still read 78%.
`replay_tradebook.py` writes a `-replay.json` sidecar of what fired on which
day; `recall_check.py --engine <sidecar>` intersects the day sets.

Every number that had an old estimate got **worse** once days had to match:

| pattern | behav days | engine days | both | recall | old estimate |
|---|---|---|---|---|---|
| premium_loss_event | 17 | 13 | 13 | 76% | — |
| fomo_entry | 7 | 28 | 5 | 71% ⚠ over-fires | — |
| consecutive_loss_streak | 63 | 44 | 44 | 70% | — |
| daily_overtrading | 48 | 32 | 30 | 62% | — |
| martingale_behaviour | 40 | 31 | 25 | 62% | ~78% |
| same_symbol_obsession | 37 | 20 | 19 | 51% | ~65% |
| expiry_day_overtrading | 34 | 23 | 17 | 50% | — |
| revenge_trade | 58 | 33 | 27 | 47% | ~59% |
| death_spiral | 56 | 25 | 21 | 38% | — |
| end_of_session_mis_panic | 11 | 4 | 4 | 36% | — |
| winning_streak_overconfidence | 15 | 4 | 3 | 20% | — |
| profit_giveaway | 30 | 8 | 6 | 20% | ~70% |
| options_premium_avg_down | 48 | 18 | 9 | 19% | — |
| size_escalation | 16 | 8 | 3 | 19% | ~50% |
| overtrading_burst | 48 | 9 | 6 | 12% | — |
| post_loss_recovery_bet | 26 | 2 | 1 | 4% | ~8% |
| direction_instability | 3 | 15 | 3 | 100% ⚠ over-fires | — |

`recall_check.py` went from 6 behaviours to 17 — every pattern that fired at
least once in the year. Eleven had nothing measuring what they missed.

**Outcome labelling, inferred from trades, nothing asked**
(`backend/app/services/alert_outcome_service.py`,
`tradedesk/scripts/outcome_check.py`). `risk_alerts.outcome` has existed since
migration 069 with an adoption rate of zero. Two labels, deliberately separate:
`heeded/ignored` (did behaviour change — product question) and `warranted`
(did it keep costing money — calibration question). **An alert can be ignored
and still be right, so only `warranted` can move a threshold.** 300 of 359
alerts carry a usable label. Nothing is written to `risk_alerts.outcome` — that
column means "the trader told us" and an inference in it would destroy the
difference between a fact and a guess. No migration; it is all derivable.

**Lift against a matched base rate.** A raw `warranted_rate` is meaningless
without a null. Computed from the tradebook: at a random trade boundary the
rest of the session is negative **56%** of the time; after a loss 58%; after
two losses 62%; on a busy day (≥8 trades) **48%**.

| pattern | warranted | matched null | lift | n |
|---|---|---|---|---|
| expiry_day_overtrading | 64% | 48% | **+16** | 11 |
| profit_giveaway | 71% | 56% | **+15** | 14 |
| daily_overtrading | 62% | 48% | **+14** | 16 |
| consecutive_loss_streak | 71% | 62% | +9 | 28 |
| size_escalation | 67% | 62% | +5 | 6 |
| revenge_trade | 56% | 58% | −2 | 23 |
| martingale_behaviour | 59% | 62% | −3 | 17 |
| fomo_entry | 52% | 56% | −4 | 25 |
| overtrading_burst | 43% | 48% | −5 | 7 |
| options_premium_avg_down | 46% | 58% | −12 | 11 |
| death_spiral | 43% | 62% | **−19** | 14 |
| direction_instability | 33% | 56% | **−23** | 9 |
| same_symbol_obsession | 35% | 62% | **−27** | 17 |
| premium_loss_event | 20% | 56% | −36 | 5 |

Caveats that must travel with this table: one trader, one year, n of 5–28 per
pattern. `warranted` is rest-of-session P&L, a proxy — a behaviour can be
destructive over months and fine that afternoon. And **anti-predictive is not
false**: "you have lost 3 times on NIFTY today" is true whatever happens next,
and the product's philosophy is facts, not forecasts. What a negative lift does
challenge is whether it earns an *interruption*.

**Busy days end negative 48% of the time versus 56% overall, median +₹24.** For
this trader a high-trade day is LESS likely to end badly than an average one.
SEBI's ">6 trades/day → 94% loss probability" does not reproduce here. One
trader against a population study, but it is a direct argument for making
`daily_trade_limit` personal rather than fixed.

### Structural fixes (B1–B9, all closed, `27c7c6d`)

The machinery around the detectors — consolidation, cap, dedup, lock,
notification gate. Belongs to no pattern, so pattern-by-pattern never reaches
it. Full detail in `docs/archive/GLOBALS_STRUCTURAL_FINDINGS.md`.

- **B1** cap returned `[]` for the whole batch with no severity check, dropping
  criticals; and the caller rebound its list to that return, so `alert_update`
  over WebSocket was suppressed too — the row existed and the dashboard was
  never told. Cap now governs interruption, never visibility.
- **B2/B3** budget looked up by wall-clock today and incremented read-modify-
  write. Now one atomic `UPDATE ... RETURNING` keyed on the alert's own session
  date (`TradingSessionService.consume_alert_budget`).
- **B4** lock stored a constant and released with unconditional DELETE — a
  holder whose TTL expired would delete the next holder's lock. Fenced with a
  token + Lua compare-and-delete.
- **B5** Redis down failed closed on the webhook path and **open** on the bulk
  path (`_redis is not None and not _lock_acquired` — when Redis is down
  `_redis` IS None). Both fail closed and requeue now.
- **B6** `run_risk_detection` was a registered task with no lock. Takes it now.
- **B7** cap counted rows saved, not interruptions. A caution has no channel, a
  stale alert is never pushed, a muted pattern is muted — all three spent
  budget, so **muting a noisy pattern reduced how many other alerts the trader
  could receive**. One predicate `_would_interrupt` now answers this for both
  the charge and the dispatch. It also exposed that the bulk path never applied
  mutes at all.
- **B8 WITHDRAWN — the engine is NOT nondeterministic.** I reported 355 vs 359
  by comparing a saved report from a previous session against a fresh run,
  which is not the same experiment. Two runs of the same code: 359 both times,
  identical on all 203 sessions.
- **B9** empty-batch guard moved to the top of consolidation.

### Regression the replay caught (`2eae675`)

The fenced lock broke the alertlab harness: `FakeRedis` has no `eval`, so every
release raised `AttributeError` — caught and logged as non-fatal — and that
fake also ignores `ex`, so the lock never expired. First acquire succeeded,
every one after was refused, and a whole replayed year came back with zero
trades and zero alerts. Production was never affected. **A fake that silently
disables the thing under test is worse than no fake**, and a handler that
downgrades an exception to a log line turns a loud failure into a silent one.

---

## Open, in the order agreed

### 1. Globals — DONE 13 Aug. L3 retired.

`docs/GLOBALS_DERIVATION.md` is the record — it derives the constants from the
tradebook instead of citing them, and it supersedes the open items that
`docs/archive/GLOBAL_CONSTANTS_FINDINGS.md` listed as G0–G5.

**What the year of trades said:**

(All recomputed on the repaired harness — see the §7 table in
`GLOBALS_DERIVATION.md` for what moved.)

- the 36 `RISK_DELTAS` weights ranked **0 of 14** against measured cost. Their
  means do carry a weak signal in the right direction (20.0 for patterns that
  predict loss vs 16.7 for those that do not) — so "no information at all" was
  overstated; "does not rank" is the defensible claim;
- **severity orders backwards** — `caution` +3 lift, `danger` −11. At fixed
  horizon caution is +16 and danger **−2**: approximately null, *not* the −12
  inversion first reported. Not a heeding effect either way — in a replay the
  trader saw none of these alerts;
- `score_halflife_min` 90 outlives the signal ~3× — lift is +4 at 30 min and
  gone by 45;
- the L2 co-occurrence premise fails: 0 domains open **+5**, 1 domain −10,
  2 domains −7. The most informative moment of the day is the *first* danger
  event with nothing else open.

**What was removed (2026-08-13):** `RISK_DELTAS`, `_behavior_state`,
`_trajectory`, `update_risk_score` + the 40/70/90 ladder, `compute_scores` /
`get_today_scores`, `score_band_*`, `score_halflife_min`, `score_sev_mult_*`,
`headline_other_weight`, `GET /api/risk/scores`, `behavior_score`, `peak_risk`,
and the two unmounted components that read them. **L1's 27 detectors and L2's
`death_spiral` are untouched** — verified by replay diff, byte-identical alerts.

`risk_score` / `peak_risk_score` **columns remain** on `trading_sessions`;
dropping them needs a migration and you apply those manually.

**Still open from that group, deliberately:**

- **G1** `capital_mismatch` has no weight and the two consumers disagreed on
  the missing-key default (0 vs 10). Moot now — both consumers are gone. If a
  weight is ever reintroduced, do not reintroduce this.
- **G3** `confidence_alert_gate` (50) is still dead code for 26 of 27
  detectors, because only `revenge_trade` sets confidence. Left alone: it gates
  alerts, so it is not L3. Decide whether to build the axis out or delete it.
- **G5** `death_spiral` reached `critical` **zero** times in 203 sessions (2
  criticals all year, both `premium_loss_event`), so the cap's critical
  exemption protects 0.6% of alerts. The detector still fires and still
  measures −17 lift. It is now a **pattern-pass item**, not a globals one.

### 2. Fix the adaptive layer — AGREED 13 Aug, and it now comes BEFORE patterns

`docs/ARCHITECTURE_REVIEW_2026-08.md`. The order changed deliberately: tuning 27
detectors against global constants and *then* switching the reference to each
trader's own distribution means doing the work twice.

The engine is designed to personalise (`get_thresholds` implements a continuous
confidence blend, no activation cliff). It substantially does not run:

- **two writers, one JSONB key, incompatible shapes.**
  `behavioral_baseline_service` writes a flat dict on sync;
  `ai_personalization_service` writes `{"metrics": {...}}`. Both write
  `detected_patterns["baseline"]`, and `get_thresholds` picks its algorithm by
  sniffing the shape — so which personalisation a trader gets depends on which
  service wrote last. Each writer's 24h freshness guard can also be satisfied by
  the other's `computed_at`.
- **the legacy branch drops 2 of its 5 values on a name mismatch** —
  `burst_trades_per_15min` vs `burst_trades_per_30min_caution`, and
  `revenge_window_min` vs `revenge_window_caution_min`. No error, no log.
- **nothing recomputes on a schedule.** `api/profile.py:804` says "nightly";
  there is no beat entry for either service.
- **`uses_baseline` is wrong in 4 of 27.** `consecutive_loss_streak` and
  `expiry_day_overtrading` declare it and read only unblended constants;
  `revenge_trade` does not declare it and *is* blended;
  `winning_streak_overconfidence` uses a session-local average.
- **9 metrics computed, 3 wired.** `typical_drawdown` and
  `median_position_risk_pct` — the two most useful for sizing/risk patterns —
  are computed, stored and read by nothing.

Order: **C1** one writer, one versioned shape (kills the race and the dropped
keys) → **C2** one nightly batched beat task → **C3** thresholds become
self-describing `{value, source, confidence}` so `uses_baseline` is derivable
rather than hand-maintained, and cold start is inspectable.

### 3. Then redefine severity — AGREED 13 Aug

**Severity = the size of the fact against the trader's OWN distribution**, not a
forecast: `caution` = within your normal range, `danger` ≈ your p80, `critical`
≈ your p95. Certainty (data quality, hedge-leg suppression) becomes a *separate*
gate. Priority becomes a computed L4 policy, not a stored field:

> interrupt when magnitude ≥ your p80 **and** certainty is good **and** it is the
> first time today for that pattern — otherwise record it, show it, never push.

Why: severity today is already a threshold crossing (a magnitude measure), but
the line is a global constant and the word implies a forecast the data does not
support — `danger` measures −11 lift against `caution`'s +3, i.e. the classes
are ordered the wrong way round. The engine is
already drifting this way by hand — see the comment inside
`_detect_consecutive_loss_streak` about ₹12,000 in three trades reading as
caution while ₹1,500 in five reads as danger.

Side effect worth having: `critical` becomes a real class (~5% per pattern
instead of 2 alerts in a year), so the cap's critical exemption starts meaning
something.

Depends on §2 — personal percentiles need a working baseline pipeline. Cold
start still falls back to the default prior and must *say* so.

### 4. Then pattern by pattern

Ranked by value (lift × missed days), not by gap size alone:

1. **`profit_giveaway`** — +15 lift and only 20% recall. Precise and blind: the
   clearest "loosen it" case in the set, and the detector already broken twice
   by moving two thresholds at once.
2. **`same_symbol_obsession`** — −27 lift, 17 alerts, fires before good outcomes.
3. **`death_spiral`** — −19 lift, suppresses its own inputs when it fires.
4. **`revenge_trade`** — no lift, high volume, 31 missed days.
5. **`martingale_behaviour`** — no lift despite the cross-instrument fix.
6. **`fomo_entry`** — over-fires 4:1 (`fomo_symbols_at_open: 2` is the suspect).
7. **`post_loss_recovery_bet`** — 4% recall, retire rather than repair.

Method per detector: what does it assume → does that hold in the tradebook →
does the naive checker agree → read the days where they disagree.
`docs/DETECTOR_ASSUMPTIONS.md` is the partial first pass.

Per-detector constants get fixed INSIDE their pattern's pass, with the missed
days open — not in a batch beforehand, which is guessing with a different
guesser.

### 5. Cheap items that fall out along the way

- Retire `post_loss_recovery_bet` (duplicate of revenge, 4% recall).
- `time_of_day_bias` is dispositioned `alerting` and should be `analytics`.
- A readable one-page replay report — the current one is 2,379 lines.
- 5 open `flood` findings from the alert audit.
- 3 unresolved assumptions in `DETECTOR_ASSUMPTIONS.md`.

---

## Things I got wrong today — do not repeat

1. **Diagnosed a code regression from a contaminated replay, three times.**
   Two replays share one synthetic account and deadlock. Always check the
   lockfile and that the baseline came from the same code.
2. **Reported B8 (nondeterminism) without running the experiment** — compared a
   stale artifact against a fresh run. Run the same thing twice before calling
   something nondeterministic.
3. **Claimed `add_session_pnl` losing an update "changes what the engine
   detects"** — it has zero call sites; `behavior_engine.py:464` computes
   `session_pnl` fresh.
4. **Claimed `delivered_push_at` is written only by the merged-push branch** —
   stale; there is a full receipts system on both channels.
5. **Recommended capping alerts to 1/session.** The user's correction stands: 2–4
   a day is fine, traders make mistakes. And green/red is the wrong axis
   entirely — ₹300 made over 10 trades, or +₹2k after losing ₹8k on ₹20k
   capital, are bad process with a good outcome. **Session verdicts are about
   process; P&L does not enter it.**

## Tools

- `tradedesk/scripts/replay_tradebook.py` — engine over a real tradebook; now
  writes a JSON sidecar and refuses to run concurrently
- `tradedesk/scripts/replay_diff.py` — reproducibility; separates real
  differences from cosmetic ordering
- `tradedesk/scripts/recall_check.py` — 17 behaviours counted independently of
  the engine, deliberately a second implementation
- `tradedesk/scripts/outcome_check.py` — labels a year of alerts from trades
- `alertlab/scripts/audit.py` — alert quality across 108 scenarios
- `docs/archive/THRESHOLD_AUDIT.md`, `docs/archive/GLOBAL_CONSTANTS_FINDINGS.md`,
  `docs/archive/GLOBALS_STRUCTURAL_FINDINGS.md`, `docs/DETECTOR_ASSUMPTIONS.md`
