# Pattern #7 — `fomo_entry`

27 Aug 2026. **Review only. No code changed, no threshold added or retuned, no
detectors merged.**

This is also the **mandated review** for `fomo_symbols_at_open`, which sits in
`safety_bounds.MANDATORY_REVIEW` with the provenance *"FLAGGED: measured ~4:1
over-firing; 2 is the tightest value in the detector and is justified by an
assertion about traders in general."*

**Verdict: MODIFY.** The clustering claim does not survive its null — the
trader's pairing of instrument to moment adds nothing (ratio 0.94, and 1.02 on
the branch that fires most). Two of the four thresholds are **structurally
unreachable** on this book, a third accounts for 39% of all firings on its own,
and the flagged trades **win more often than the trader's average**.

---

## 1. What it is supposed to detect, and the mechanism

Entering several **different underlyings** inside a short window. Registry copy:
*"Several unrelated instruments at once is usually chasing movement rather than
acting on a view."* The alert message is stronger: *"Scattering across
underlyings indicates FOMO — not a focused plan."*

The design is careful in one important way, and it deserves credit: it counts
**distinct underlyings, not symbols**, so buying two NIFTY strikes is a strategy
and not a scatter. `trading_defaults.py` states this explicitly.

The mechanism appealed to is fear-of-missing-out: the trader sees movement
somewhere else and reaches for it. **That is a claim about clustering in time** —
several unrelated things grabbed together — which is exactly what §4b tests.

## 2. What the implementation does, end to end

`behavior_engine.py:2147-2236`, 90 lines.

```
guard        instrument_type in (CE, PE, FUT)   — EQ never considered
window       trailing 30 min from this entry, over ctx.session_trades
count        distinct parse_symbol(...).underlying, INCLUDING the current trade
branch       expiry day        -> 4      (is_expiry_day from the SYMBOL, not weekday)
             market open  ≤30m -> 2
             pre-close    ≤30m -> 3
             otherwise         -> 3
fire         count >= threshold  ->  severity "caution", always
```

| input | value | classification |
|---|---|---|
| `fomo_window_min` | 30 | **unclassified** |
| `fomo_open_window_min` | 30 | **unclassified** |
| `fomo_close_window_min` | 30 | **unclassified** |
| `fomo_symbols_in_window` | 3 | `PERSONAL_BASELINE` → `fomo_underlyings_per_window_p75` |
| `fomo_symbols_at_open` | 2 | `PERSONAL_BASELINE`, **`MANDATORY_REVIEW`** |
| `fomo_symbols_at_close` | 3 | `PERSONAL_BASELINE` |
| `fomo_expiry_day_symbols` | 4 | `PERSONAL_BASELINE` |

**Rules / onboarding:** none reach this detector. The onboarding wizard collects
`fomo` as a *known weakness* (`user_profile.known_weaknesses`), which
`daily_reports_service` reads for report copy — but nothing in the detector
consults it.

**Severity** always `caution` — the danger tier does not exist, so this
`alerting` detector can never reach a push. **Confidence** not set; inherits the
data-quality default. **Evidence/abstention** none — returns a `DetectedEvent`.
**Notification level 1.** Soft cooldown trigger in `cooldown_service`. In
`danger_zone_service`'s `danger_patterns`. **Not** in `_STRATEGY_SUPPRESSED`, no
constitution pairing, **no consolidation family**.

### The personalisation is declared but does not exist

All four symbol-count thresholds are `Kind.PERSONAL_BASELINE` with
`resolution_source=Source.HISTORY` and a named metric. **None of
`fomo_underlyings_per_window_p75`, `_at_open_p75`, `_at_close_p75` or
`_expiry_p75` is produced anywhere** — not in `baseline_service`, not in
`behavioral_baseline_service`, and `threshold_resolution._apply_history_v2`
places none of them.

**So every trader gets the fallbacks 3 / 2 / 3 / 4, permanently.** The registry
describes an intention, not a behaviour. This is not an argument for
personalising — it is a statement that the classification currently overstates
what the system does.

## 3. Performance and purity — **KEEP AS-IS**

No `await`, no `db.`, no `select(` in the body; confirmed by source inspection
and by running it 912 times with no database connection. `parse_symbol`,
`is_expiry_day`, `get_open_time`/`get_close_time` are all pure. One list
comprehension over the session's trades per call. Negligible.

Two things here are genuinely well built and should be said plainly:

- **`is_expiry_day` reads the expiry from the symbol**, replacing a hardcoded
  `weekday() == 3`. Weekly and monthly contracts both resolve correctly, with
  holiday-adjusted monthlies handled.
- **Session bounds come from the instrument's own exchange.** The comment
  records why: hardcoded 09:15/15:30 made `mins_after_open` negative for MCX
  mornings, so both FOMO windows silently never fired for commodity traders.

## 4. Evidence — 189 sessions, 912 positions, corrected trade set

Measured at cold-start defaults, which — per §2 — is what every trader gets.
**74 detections on 41 of 189 sessions (22%)**, becoming **29 alerts** after
dedup, matching the stored replay exactly.

### 4a. Two of the four thresholds are unreachable

Traffic per branch, with the distribution of distinct underlyings actually seen:

| branch | threshold | entries | distinct underlyings seen | firings |
|---|---|---|---|---|
| general | 3 | 573 | 1:407 · 2:129 · **3:31 · 4:6** | **37** |
| market open | 2 | 128 | 1:91 · **2:29 · 3:7 · 4:1** | **37** |
| **expiry day** | **4** | 142 | 1:125 · 2:16 · 3:1 — **max 3** | **0** |
| **pre-close** | **3** | 50 | 1:44 · 2:6 — **max 2** | **0** |
| skipped (EQ) | — | 19 | — | — |

> **On expiry day the trader never touched 4 underlyings in 30 minutes — the
> maximum ever seen is 3, once. On the pre-close the maximum is 2.** Both
> thresholds sit above the highest value their branch has ever produced. They are
> not quiet; they cannot fire.

The expiry constant carries a comment justifying the move from 2 to 4 — *"NIFTY
plus one stock option inside half an hour on expiry day is an ordinary session,
not a scramble"* — which is a reasonable argument that 2 was too tight. It went
to a number that is unreachable instead, and 142 expiry-day entries produce
nothing.

`fomo_symbols_at_close` was separated from the open threshold on 22 Aug with the
honest note *"a pre-close scramble is plausible but unmeasured, and this knob is
where that evidence would land."* **This is that measurement: on 50 pre-close
entries the branch cannot fire at 3.**

### 4b. The null — is the scatter clustered, or just breadth?

`fomo_entry` is a **clustering** claim. The matching null preserves both
marginals of a session — the exact entry times, and the exact multiset of
instruments traded — and randomly permutes **which instrument was traded at
which moment**. Deliberate clustering is destroyed; breadth and activity are
preserved exactly. 200 permutations per session, **using the real detector**.

| | observed | chance | ratio |
|---|---|---|---|
| firings | **74** | **78.4** | **0.94** |
| sessions with any | 41 | 43.3 | 0.95 |
| general branch | 37 | 41.9 | 0.88 |
| **market-open branch** | **37** | **36.2** | **1.02** |

> **The trader's pairing of instrument to moment adds nothing.** The detector is
> counting how many underlyings were in play across a stretch of the day, not
> whether they were chased together. The market-open branch — half of all
> firings — is at chance to two decimal places.

*(A first attempt at this null hand-rolled the branch logic and produced 45
firings where the detector produces 74. A null computed against a different
firing rule measures nothing, so it was discarded and rerun with the real
detector. The 0.94 above is from the corrected run.)*

### 4c. The flagged open threshold, quantified

Of the 37 market-open firings, **29 are at exactly 2 underlyings** — 78% of that
branch, and **39% of every firing this detector produces**. Those 29 exist only
because the open window uses 2 where everything else uses 3.

That is the over-firing the `MANDATORY_REVIEW` flag recorded, now measured: 29
firings that clear the open threshold against 8 that would also clear the
general one — **3.6:1**, close to the flagged ~4:1.

For context, 2 distinct underlyings inside 30 minutes is **20.2% of all entries
in the book** (180 of 893). The open branch is firing on a state that is one
entry in five.

### 4d. The flagged trades are better than average

| | win rate | P&L |
|---|---|---|
| **all flagged trades** (n=74) | **45.9%** | −₹12,071 |
| market open (n=37) | 40.5% | −₹10,545 |
| **general (n=37)** | **51.4%** | −₹1,526 |
| **book-wide baseline** | **39.9%** | — |

**Every flagged group wins more often than this trader's 39.9% baseline, and the
general branch wins 51.4%.** The message says scattering "indicates FOMO — not a
focused plan"; on this book the trades it says that about are the trader's
better ones.

The −₹12,071 is real money and is not disputed. But 74 trades at a 45.9% win
rate is not the signature of a trader chasing wildly.

### 4e. Observability limits

- **EQ is excluded by design** (`instrument_type in CE/PE/FUT`), so scatter into
  cash equities is invisible. 19 entries in this book.
- **Carried positions evaluate alone.** A position opened yesterday has
  yesterday's `entry_time`, so no trade in today's `session_trades` falls inside
  its 30-minute window and the count is always 1. Correct, but it means the
  first trades of a carried-position day cannot contribute.
- **The window is entry-to-entry within `session_trades`**, which the engine
  populates with *closed* trades. A position still open does not appear, so a
  scatter that is still open is undercounted at the moment it is happening.

## 5. Overlap and whether the alert is meaningful

**Fired alone on 4 of its 29 alert-days.**

| co-fires with | days | share |
|---|---|---|
| `daily_overtrading` | 18 | **62%** |
| `consecutive_loss_streak` (retired) | 16 | 55% |
| `martingale_behaviour` | 13 | 45% |
| `size_escalation` · `adding_to_adverse_position` | 11 | 38% |
| `death_spiral` | 10 | 34% |
| `overtrading_burst` | 7 | 24% |

The 62% overlap with `daily_overtrading` is the one that matters: **breadth and
pace are close to the same story on this book**, and `fomo_entry` is the third
pace-flavoured detector after `overtrading_burst` and `daily_overtrading` — none
of which share a consolidation family.

**Is it meaningful?** The fact is true and is not available elsewhere: no other
detector counts distinct underlyings. But the alert asserts a *reason* —
chasing, not planning — that the null does not support and the win rate points
against.

## 6. Are the values justified?

| value | justified? |
|---|---|
| **counting underlyings, not symbols** | **Yes.** The best decision in this detector. Explicitly reasoned in `trading_defaults.py` and correct. |
| `fomo_window_min` 30 | **Unclassified, no source.** Untested against any alternative; 30 minutes is a round number. |
| `fomo_symbols_in_window` 3 | Fires on 37 of 573 general entries. Not absurd — 3+ underlyings is 5.2% of entries — but the null says the timing carries nothing. |
| `fomo_symbols_at_open` 2 | **No.** Flagged for mandatory review, and the flag is confirmed: 39% of all firings, 3.6:1 against the general threshold, at a state that is 20% of all entries. Its own registry provenance says it is *"justified by an assertion about traders in general."* |
| `fomo_symbols_at_close` 3 | **Unreachable** — max observed in that branch is 2. |
| `fomo_expiry_day_symbols` 4 | **Unreachable** — max observed on expiry day is 3, once, across 142 entries. |
| the three window lengths | **All unclassified.** |

**Research note:** FOMO in trading is well described qualitatively but I found no
source — in this repo or in literature I can cite with confidence — that fixes a
number of instruments, or a window length, at which breadth becomes chasing. The
`trading_defaults` comment block is an argument, not a citation, and the file's
own convention is that an unmarked number is unsourced.

## 7. Verdict — **MODIFY**

Not KEEP AS-IS: two thresholds cannot fire, a third produces 39% of all output
on its own and is already flagged for mandatory review, and the clustering claim
is at chance.

Not DELETE: unlike Patterns 4 and 6, **the underlying measurement is not
arithmetic**. Breadth across underlyings is a real, deliberate property of how a
session was traded, it is not forced by any accounting identity, and nothing
else in the engine sees it. What fails is the *timing* claim wrapped around it
and three of the four numbers.

Not RESEARCH FURTHER: 912 positions were enough to settle every question asked
here.

Not DEFER: unlike `overtrading_burst` (n=13), this has 74 detections across 41
sessions. There is enough to act on.

---

## Current behaviour

Fires `caution` when a trade's trailing 30 minutes contains at least N distinct
underlyings, N being 4 on expiry day, 2 in the opening 30 minutes, 3 pre-close
and 3 otherwise. 74 detections → 29 alerts on 41 of 189 sessions. Only two
branches ever fire.

## What is correct

- **Counting distinct underlyings rather than symbols.** Two NIFTY strikes is a
  strategy, not a scatter — reasoned explicitly and implemented correctly.
- **`is_expiry_day` from the symbol**, not `weekday() == 3`; weeklies, monthlies
  and holiday-shifted monthlies all handled.
- **Session bounds from the instrument's own exchange**, with the MCX bug that
  motivated it recorded in place.
- **Including the current trade in the count**, so a threshold of N means N
  total rather than N+1.
- **Purity.** No DB, negligible cost.
- The subject is real and unique: no other detector measures breadth.

## Problems found

1. **`fomo_expiry_day_symbols` = 4 is unreachable** — 142 expiry entries, maximum
   3 underlyings seen once.
2. **`fomo_symbols_at_close` = 3 is unreachable** — 50 pre-close entries, maximum
   2. This is the measurement its own comment asked for.
3. **`fomo_symbols_at_open` = 2 produces 39% of all firings**, 3.6:1 against the
   general threshold, on a state occurring in 20% of all entries. Confirms the
   `MANDATORY_REVIEW` flag.
4. **The clustering claim is at chance** — 0.94 overall, **1.02** on the
   market-open branch.
5. **Flagged trades win 45.9% against a 39.9% baseline**; the general branch
   wins 51.4%. The message asserts a reason the data contradicts.
6. **The personalisation is declared but does not exist** — all four
   `PERSONAL_BASELINE` metrics are produced by nothing, so every trader gets the
   fallbacks forever.
7. **The three window-length constants are unclassified and unsourced.**
8. **62% overlap with `daily_overtrading`**, fired alone on 4 of 29 days, and no
   consolidation family covers the three pace/breadth detectors.
9. **An `alerting` detector that can only ever emit `caution`** — it has no
   danger tier, so it can never reach a notification.

## Evidence

§4 in full. Headlines: 74 detections / 29 alerts / 41 of 189 sessions; branch
traffic 573 general, 142 expiry, 128 open, 50 pre-close with firings 37 / 0 / 37
/ 0; null ratio 0.94 overall and 1.02 at the open; 29 of 74 firings exist only
because of the open threshold; flagged-trade win rate 45.9% vs 39.9% book-wide,
51.4% on the general branch; fired alone on 4 of 29 days.

## Recommended behavioural contract

> **`fomo_entry` reports one fact: how many different underlyings this session
> has touched in a short space of time.**
>
> - **Breadth is the finding; timing is not.** The permutation test says the
>   trader's pairing of instrument to moment carries no information, so the
>   alert must not claim the instruments were chased *together*.
> - It makes **no claim about the quality of the trades**. On this book they win
>   more often than average, and the copy must not assert otherwise.
> - **A threshold that cannot be reached is not a conservative threshold, it is
>   an absent one.** Every branch must be able to fire on the distribution it
>   governs, or it should not exist as a branch.
> - Where a context has no measured behaviour of its own, it should share the
>   general threshold rather than invent a tighter or looser one.

## Exact changes required — for approval, not implemented

| # | change | why |
|---|---|---|
| 1 | **Resolve the two unreachable branches.** Either give expiry and pre-close thresholds their branches can reach, or remove the branches and let both fall through to the general threshold. **Removing them is the change that invents nothing.** | §4a |
| 2 | **Resolve `fomo_symbols_at_open` = 2**, its mandatory review now being complete. On the evidence it should share the general threshold; keeping 2 needs a justification that measurement does not currently supply. | §4c |
| 3 | **The message must stop asserting a cause.** *"Scattering across underlyings indicates FOMO — not a focused plan"* is contradicted by the null and by the win rate. State the breadth. | §4b, §4d |
| 4 | **Correct the `PERSONAL_BASELINE` classification** on all four keys, or produce the metrics. Right now the registry claims a personalisation the system does not perform. | §2 |
| 5 | Classify the three window-length constants, or record them as unsourced in the manner `trading_defaults.py` already uses. | §6 |
| 6 | Decide whether an `alerting` detector with no danger tier should be `analytics` instead. | §5 |

**No replacement threshold is proposed**, and none should be taken from this
book: the evidence says which numbers are wrong and which branches cannot fire,
not where a correct number would sit.

## What is NOT proposed

Deleting the detector. Merging it with `daily_overtrading` or
`overtrading_burst`. Adding a consolidation family — that is a families
question, not a Pattern 7 one. Personalising the counts. Touching `is_expiry_day`
or the exchange-bounds logic, both of which are correct.

## Recorded for later reviews, not fixed here

- The three pace/breadth detectors (`fomo_entry`, `overtrading_burst`,
  `daily_overtrading`) overlap heavily and share no family. Same finding as
  Pattern 5 §5, now with a second detector attached to it.
- `pattern_prediction_service` computes a `fomo` probability from an unsourced
  ladder (`fomo_prob = 10` base, +20/+15/+15) and writes it under a key the
  engine cannot emit. Already recorded as `ENGINE_BACKLOG` M0.
- `user_profile.known_weaknesses` can contain `fomo`, read only by
  `daily_reports_service` for copy. Whether a declared weakness should reach the
  detector is a product question and would be the trader's own input — the one
  kind of personalisation this series has repeatedly found defensible.
