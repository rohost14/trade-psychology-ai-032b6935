# Next session — start here

State at end of 12 Aug 2026. Branch `dashboard-production-readiness`, pushed
through `c919f92`. 733 backend tests pass (`pytest tests/ --ignore=tests/production`
— the `tests/production/` suite needs a live server on localhost and its 35
`ConnectError` failures are environmental, not real).

Supersedes the 11 Aug note. That note's four items are addressed or reordered:
items 2 and 3 (retire `post_loss_recovery_bet`, move `time_of_day_bias`) are
still open and still cheap; item 1 (readable replay report) is still open; item
4 (extend `recall_check`) is DONE.

---

## Do this first

**Verify the regression replay.** A clean run was in flight when the session
ended. Run it, then diff:

```
python tradedesk/scripts/replay_tradebook.py docs/tradebook-CY6001-FO2025-26.csv \
    --capital 50000 --no-rules
python tradedesk/scripts/replay_diff.py <baseline>.json \
    docs/tradebook-CY6001-FO2025-26-replay.json
```

Expected: 359 alerts, 203 sessions, REPRODUCIBLE. Ordering may differ on a
handful of days — that is cosmetic (`created_at` is wall-clock and breaks ties
between alerts sharing a trade's `detected_at`).

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
it. Full detail in `docs/GLOBALS_STRUCTURAL_FINDINGS.md`.

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

### 1. Globals — the constants (analysis DONE, nothing implemented)

`docs/GLOBAL_CONSTANTS_FINDINGS.md`. Headline: **the audit undercounted, it is
~148 constants, not 109.**

- **G0** `RISK_DELTAS` in `behavior_engine.py` holds **36 more** weights, in a
  different file from `trading_defaults.py`, with no citations — and they are
  the entire input to the session risk score and the multiplier in every driver
  score. Plus 3 inline literals in `behavior_scores_service.py` (`75` default
  confidence, `0.5` noise floor, `10` default weight).
- **G1 (real defect, fix is small and unambiguous)** `capital_mismatch` is a
  live pattern with **no weight**, and the two consumers disagree on what a
  missing key means: `RISK_DELTAS.get(x, Decimal("0"))` in the engine,
  `RISK_DELTAS.get(x, 10)` in the scores service. Same event moves one score by
  0 and the other by 10. Four dead entries also exist for retired patterns
  (harmless).
- **G2** three band systems, and two of them read the SAME number: `new_risk`
  is computed once and fed both to `_behavior_state` (cuts 20/40/60/80,
  hardcoded in `behavior_engine.py`) and to `update_risk_score` (cuts 40/70/90,
  hardcoded in `trading_session_service.py`). A score of 45 is simultaneously
  "caution" and "Tilt Risk". The third (`score_band_*`, 30/60/80) is a
  different computation. Only that one is in `trading_defaults`, which is why
  the audit missed the others.
- **G3** signal stacking exists in **one detector of twenty-seven**
  (`revenge_trade`). Everything else leaves `confidence=None`, which resolves
  to data quality — `GOOD` = 100 on any live postback. So
  `confidence_alert_gate` (50) is dead code for 26 detectors, and `confidence`
  in the score formula is ~always 1.0: a four-factor formula behaving as three.
- **G5** `death_spiral` is the strongest anti-signal measured, and its
  `critical` path requires five simultaneous conditions. `critical` is exactly
  the severity now exempted from the cap — **if it never reaches critical in a
  year, that exemption protects nothing.** Countable from the sidecar, free.

**Next concrete step (agreed):** count from the existing sidecar first — no
replay needed. Death-spiral severities, `capital_mismatch` frequency, and how
often the three band systems disagree. That decides whether G1 and G5 are worth
acting on. Then fix G1, then sweep `confidence_alert_gate` (40/50/60) and
`score_halflife_min` (45/90/180) and measure what actually changes.

**The framing that makes this cheap:** a constant whose value changes NOTHING
across a year of real trading is not a threshold, it is decoration — delete it
rather than argue about it.

**What cannot be answered without more labels:** whether 50 is the *right*
gate. Sensitivity says whether a constant is load-bearing; only outcomes say
where it belongs. 300 labelled alerts from one trader is enough to rank
detectors, not to fit a coefficient.

### 2. Then pattern by pattern

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

### 3. Cheap items that fall out along the way

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
- `docs/THRESHOLD_AUDIT.md`, `docs/GLOBAL_CONSTANTS_FINDINGS.md`,
  `docs/GLOBALS_STRUCTURAL_FINDINGS.md`, `docs/DETECTOR_ASSUMPTIONS.md`
