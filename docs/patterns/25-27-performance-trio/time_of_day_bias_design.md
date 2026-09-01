# `time_of_day_bias` — persistence trace and validation

**1 Sep 2026. DESIGN PASS. NO CODE WRITTEN.**

---

## 0. CORRECTION — my central finding in the review was WRONG

The review said `detected_patterns["time_patterns"]` **has no writer** and called
the detector *"mis-wired / dead on arrival"*. **That is false.** The chain is
live end to end:

```
celery beat 18:15 IST daily          celery_app.py:207
  -> refresh_personalization_patterns  intent_tasks.py:291
  -> learn_patterns(days_back=90)      ai_personalization_service.py:40
  -> _learn_time_patterns(trades)      computes danger_hours
  -> _store_learned_patterns(...)      LINE 142 — writes the whole dict
  -> profile.detected_patterns         includes "time_patterns"
  -> threshold_resolution.py:509       reads danger_hours
  -> _detect_time_of_day_bias          fires
```

**How I got it wrong.** I grepped for `["time_patterns"] =` — an assignment to
that key. The write is a whole-dict assignment (`profile.detected_patterns =
patterns`), so my pattern could not match it, and I reported absence of evidence
as evidence of absence. The nightly caller's `logger.info(...)` reinforced the
mistake: I read the call site, saw only logging, and did not check whether
`learn_patterns` persisted internally before returning. It does, on line 142.

**This changes the verdict, and it changes it in the more serious direction.**
The detector is not dead. **It is live, and for any trader with 30+ sessions it
is firing today on the signal validated below.** The review's zero was the same
artefact as `win_rate_collapse`'s — a CSV tradebook carries no profile.

---

## 1. The persistence questions, answered

| question | answer |
|---|---|
| where is `time_patterns` persisted? | `user_profiles.detected_patterns` (JSONB), key `"time_patterns"` |
| which path owns it? | `ai_personalization_service._store_learned_patterns`, line 142 |
| refresh frequency? | **nightly, 18:15 IST**, Celery beat — 15 min after the daily score push, deliberately, to avoid DB contention |
| historical window? | **90 days** (`learn_patterns(days_back=90)`) |
| what gates on it? | `baseline_sessions >= 30`, and that count comes from a **different** producer (`behavioral_baseline_service`, also 90 days, sync-triggered with a 24h throttle) |

**Nothing needs to move.** The ownership is already sensible: the learner owns
its own output and writes it on a schedule.

### The one real plumbing defect — a clobbering writer

Three writers touch `detected_patterns`, and they do not agree on whether to
merge:

| writer | behaviour |
|---|---|
| `behavioral_baseline_service:143` | **MERGES** — `patterns = dict(existing); patterns['baseline'] = ...` ✅ |
| `ai_personalization_service:532` | **REPLACES** the whole dict with `learned_patterns` |
| **`api/profile.py:637`** (`POST /profile/detect-style`) | **REPLACES** with a three-key dict — `avg_trades_per_day`, `total_trades`, `active_days` |

`POST /profile/detect-style` would **destroy `time_patterns` and `baseline`
both**, silently, and the next nightly run would only restore the first.

**It has no callers** — grep across `src/` returns nothing — so it is latent,
the same class as `pre-trade-check`. Recorded, not a reason to act now.

The second row is also worth noting: the personalization service replaces rather
than merges, so it carries its *own* `baseline` computation and will overwrite a
fresher one from `behavioral_baseline_service` if it runs later. Both compute the
same thing from the same source, so today this is a redundancy rather than a
bug.

---

## 2. Are the learned danger hours stable enough to drive alerts?

**No. This is the finding that matters, and it is unambiguous.**

### Stability — no hour survives into a second period

| period | danger hours learned |
|---|---|
| full book | **12, 15** |
| first half (363 trades) | 11, 12, 15 |
| **second half (377 trades)** | **none at all** |
| **flagged in BOTH halves** | **NONE** |

By quarter:

```
  Q1: [9, 11]
  Q2: [11, 12, 15]
  Q3: [12, 13]
  Q4: []
  appearing in all four: NONE
```

**Five different hours are flagged across four quarters and not one of them
persists.** The second half of the book produces no danger hour whatsoever —
so a trader alerted about their 12 PM hour in month 3 would have had that hour
silently withdrawn by month 6, with no message saying so.

### Multiple comparisons — the flagged count is what chance produces

Shuffling the hour labels across trades, keeping every trade's own result, and
re-applying the producer's exact filter (`win rate < 35%`, `n >= 5`):

| hours flagged by chance | frequency |
|---|---|
| 0 | 23.4% |
| 1 | 45.2% |
| **2** | **26.5%** |
| 3 | 4.5% |
| 4 | 0.4% |

**p(chance flags ≥ 2) = 0.314.** The real book flags 2. That is the single most
likely outcome region under pure noise.

And this is a **lower bound** on the false-positive rate: trades within a session
are not independent, and clustering makes streaks in any one hour more likely
than the shuffle assumes.

### Do the flagged trades actually do worse? Directionally, not significantly

| | n | win rate | mean | median |
|---|---|---|---|---|
| in a danger hour | 79 | **29.1%** | **−₹295** | −₹328 |
| every other hour | 659 | 40.8% | −₹23 | −₹158 |

Difference −₹272, **permutation p = 0.071**.

The direction is right and the gap is not trivial. But it is measured **on the
same data that chose the hours** — the selection and the test are not
independent, so 0.071 overstates the evidence, and §Stability shows the
selection does not survive out of sample at all.

Per hour:

```
  12:00   n=68   win 29.9%   avg -Rs 261
  15:00   n=13   win 25.0%   avg -Rs 423     <- thin
```

**15:00 rests on 13 trades.** It clears the producer's `>= 5` gate and would
drive `caution` alerts at `notification_level=1`.

---

## 3. Are the 81 firings meaningful events, or just reachability?

**Reachability, and worse.** They are 81 alerts derived from a selection that:

* names different hours in every period of the book,
* is produced at a rate chance reproduces 31% of the time,
* and includes an hour resting on 13 trades.

**62% of them (50 of 81) are seen by no other detector**, so the volume is
genuinely additive rather than duplicated:

| co-firing | share |
|---|---|
| `same_symbol_obsession` | 17% |
| `revenge_trade` | 16% |
| `martingale_behaviour` | 9% |
| `adding_to_adverse_position` | 7% |
| **nothing else** | **62%** |

Additive volume on an unstable signal is worse than duplicated volume, not
better.

---

## 4. Is the trader-facing copy still valid?

> *"Entered NIFTY…CE at 12:04 — historically your 12 PM hour runs a 30% win rate
> over 68 trades (avg −₹261)."*

**Every number in it is true**, and it is one of the more honest messages in the
engine: hour, rate, sample size and average, no claim about intent.

**But "historically" is doing work the data cannot support.** It implies a
standing property of the trader. Measured, the property does not stand — it is
absent from the second half of this book entirely. The sentence would be
accurate and misleading at the same time.

---

## 5. Recommendation — and it is NOT the one-line fix

The review recommended MODIFY: persist `time_patterns`. **That recommendation is
withdrawn** — there is nothing to persist, it already is.

The real question is the one the validation answers: **should a `caution` alert
at `notification_level=1` be driven by a filter whose output is indistinguishable
from chance and does not survive into a second time period?**

Measured, no. And because the chain is live, **this is not a proposal to change
future behaviour — it is a finding about behaviour happening now** for any trader
with 30+ sessions.

### Options, none of which I will pick alone

| | option | what it costs |
|---|---|---|
| **A** | **Leave it exactly as is.** | Live alerts on an unstable signal continue. Honest only if we decide the signal is acceptable. |
| **B** | **Demote to `analytics`/`info`** — same computation, no alert. | Keeps the measurement, stops acting on it. Consistent with how `win_rate_collapse` treats a similar-strength performance signal. |
| **C** | **Raise the producer's evidence bar** — a stability requirement across periods, or a larger per-hour sample, or a correction for testing 7 hours. | **Requires choosing numbers, which this pass will not invent.** Would need its own evidence work. |
| **D** | **Retire it.** | The subject may be real for some trader; this book cannot show it, and neither can this filter. |

**I lean B**, because it is the only option that neither invents a threshold nor
keeps alerting on a signal we have just measured as chance-like — and because
the engine already has a category for exactly this (`analytics`, no reader yet,
recorded as its own open question). But it is a product decision about what
deserves a trader's attention, and the evidence supports "not this, as
currently computed" rather than any specific replacement.

### What I am NOT proposing

* No new threshold, sample gate or correction factor.
* No change to `win_rate_collapse` or `strategy_breakdown`.
* No fix to `POST /profile/detect-style` — recorded as latent.
* No change to the refresh schedule or the 90-day window; both are sensible and
  neither is implicated.

---

## 6. Open items recorded, not actioned

1. **`POST /profile/detect-style` clobbers `detected_patterns`** with an
   incompatible three-key shape, destroying `time_patterns` and `baseline`. No
   callers; latent.
2. **`ai_personalization_service` replaces rather than merges**, and computes its
   own `baseline` alongside `behavioral_baseline_service`'s. Redundant today
   because both derive it identically; fragile if either changes.
3. **Two producers, two windows, one gate.** `danger_hours` comes from
   `learn_patterns` (90 days, nightly); `baseline_sessions` — which gates the
   detector — comes from `behavioral_baseline_service` (90 days, sync-triggered,
   24h throttle). They agree today by coincidence of configuration, not by
   construction.
4. **No test asserts which keys `detected_patterns` must contain.** Three writers,
   four readers, two shapes. This is the thread running under all of §1, and it
   is what let my grep mislead me.
