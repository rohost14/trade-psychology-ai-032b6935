# Pattern #8 expanded — real-time behaviour, user rules, and Pattern #12

27 Aug 2026. **Review only. No code changed.**

**Pattern 8 is NOT complete. I marked it COMPLETE prematurely and am retracting
that.** The first review measured the exit path thoroughly and treated the live
path as a footnote, and it closed before checking whether the trader's own
declared limit was used. Both were the wrong call: the live path is the half
that can change an outcome, and the declared limit exists, is collected, and is
read by nothing.

**Revised verdict: MODIFY.** Nothing measured about the *bands* has changed —
they still select the top 6% of outcomes and 35% of the losses. What is wrong is
everything around them.

---

## 1. Exactly when it fires

**Both paths exist. They are not equivalent.**

| | exit path | live path |
|---|---|---|
| entry point | `_detect_premium_loss_event`, engine, per CompletedTrade | `monitor_live_premium` Celery beat → `evaluate_live_premium_loss` |
| trigger | position **closes** | `schedule: 60.0` — a **60-second poll** |
| price source | realized exit price | Redis LTP hash, rejected if older than 2s |
| window | any time | market hours only, 09:15–15:25 IST, weekdays |
| bands | 40 / 60 / 80 (+15pp expiry) | **identical**, deliberately mirrored |
| repeat rule | yes | no — needs completed trades |
| dedup | `pattern_type` alone, 24h | `(rule, symbol)`, 30 min, escalation-aware |
| **latency** | after the fact | **0–60s, median ~30s** |

**Neither path reads the trader's declared limit.**

### The 60-second beat is the scale problem

Per cycle, `_monitor_live_premium` does:

1. one query for every connected `BrokerAccount`
2. **per account** — one query for its `Position` rows
3. **per account** — one query for its `UserProfile`, then `get_thresholds(profile)`, which is a full `resolve_thresholds` walk
4. per firing — a *new* DB session, a dedup query, an insert

At **10,000 concurrent users that is ~20,001 database round trips every 60
seconds**, in a serial `for account in accounts` loop, plus 10,000
`resolve_thresholds` computations per minute.

At 2 ms per round trip that is **40 seconds of a 60-second budget**. At the
30–50 ms I actually measured against this Supabase instance earlier today, it is
**ten minutes** — the beat cannot finish inside its own period, and beats would
pile up.

**The LTP read is already correct** — Redis hash, no Kite REST, so the 3 req/s
limit is not involved. The problem is not the prices. It is re-reading every
user's positions and rules from the database once a minute to check a number
that only changes when a price does.

## 2. Your example: ₹100 premium, price falls

**Today:**

| price | premium lost | what happens |
|---|---|---|
| ₹60 | 40% | live beat fires **caution** within 0–60s |
| ₹40 | 60% | live beat fires **danger** — escalation passes dedup |
| ₹20 | 80% | live beat fires **critical** |
| exit at ₹20 | 80% | exit path fires **critical** again |

So the answer to *"does the trader get warned before exit?"* is **yes, but up to
a minute late, and only if the beat can keep up.** At current scale it can. At
10k users it cannot.

And the fourth row is a real defect: **the same 80% event is reported twice**,
once live and once at exit, because the two paths have separate dedup scopes and
different keys. Nothing reconciles them.

## 3. The declared rule exists and is used by nothing

**Settings → Profile** collects, in plain language:

> **"I exit options when premium drops by"** — 30 / 50 / 70 / 100%, default 50
> *"Used to detect holding losers too long on options buys."*

That is `UserProfile.sl_percent_options`, *"% of premium to exit losing
options"*. It is validated (1–100), stored, and **resolved into the threshold
dict at `Source.FACT`** (`threshold_resolution.py:525`).

**Consumers: zero.** Not `premium_loss_event`, not the live check, not
`no_stoploss`, not anything. Same for `sl_percent_futures`.

**The help text is false.** It names a detection that does not read it.

This is the Pattern 4 shape exactly: the trader is asked the precise question the
detector answers with our number, their answer is stored, and nothing looks at
it. **Marking Pattern 8 complete without checking this was my error.**

### How the two layers should interact

Your framing is right and it is also what the codebase's own taxonomy already
says:

- **`premium_loss_caution_pct` is `UNIVERSAL_SAFETY`** — *"objective danger;
  never personalised"*. A trader may not raise it. That must not change.
- **`sl_percent_options` is a `USER_RULE`** — *"a commitment the trader made"*,
  the strongest reference in the engine.

They are **different statements about the same position** and both are true:

> *"This position has lost 40% of its premium."* (universal)
> *"You told us you exit at 25%."* (personal)

**Act at whichever is reached first.** A tighter personal rule fires earlier; a
looser one cannot push the universal band out, because `safety_bounds` already
enforces declared-values-may-only-tighten. That is the same `min(declared,
derived)` shape already shipped for `daily_trade_limit` in Pattern 5.

**They should be two events, not one blended threshold.** The personal crossing
is a rule breach and belongs to `constitution_violation` with a
`sl_percent_options` rule — which is how Pattern 4 resolved the identical
problem. Blending them into one number would destroy the distinction between a
commitment and a safety floor, which is the thing the `Kind` taxonomy exists to
protect.

**This requires `sl_percent_options` to become a `RULE_FIELD`** so it gets the
constitution's tighten-instantly / loosen-with-friction treatment. It is not one
today.

## 4. Recommended real-time architecture

Your sketch is the right one:

```
market tick → in-memory position state → detect threshold crossing → emit once → notification
```

**Everything needed already exists.** `price_stream_service._on_ticks` is a
single shared KiteTicker callback that already throttles to 1 tick/sec/instrument,
already batches a Redis LTP write, and already fans out to WebSockets. It is the
natural home.

### The state

One process-local map, owned by the ticker process:

```
token -> [ PositionWatch(account_id, symbol, avg_entry, qty,
                         universal_bands, personal_band,
                         highest_band_fired) ]
```

**Built from the DB only on change**, never on a tick: at process start (one
query for all open positions, not one per user), on each fill — the postback
pipeline already runs then — on position close, and on a rules change.

### The tick path

Look up the token, and for each watcher compute
`loss_pct = (avg_entry − ltp) / avg_entry × 100`, compare against
`highest_band_fired`, and emit **only when a band not yet fired is crossed**.

Cost: one dict lookup plus a few float operations per holder. No DB. No Redis
read — the price is already in hand.

### Scale, with numbers

| | today (60s poll) | proposed (tick-driven) |
|---|---|---|
| DB round trips | **20,001 / minute** = 333/s | **0** on the hot path |
| `resolve_thresholds` calls | 10,000 / minute | on change only |
| latency | 0–60 s | **sub-second** |
| DB writes | 1 per alert + 1 dedup read | 1 per crossing |

**State size:** 10k users × ~3 open option positions = 30k watchers × ~200 bytes
= **~6 MB**. Trivial.

**Tick load:** KiteTicker is capped at 3,000 instruments and ticks are throttled
to 1/sec/instrument, so ≤3,000 ticks/sec. With 30k watchers spread over 3,000
instruments that is ~10 watchers per tick → **~30k float comparisons/second**,
which is nothing.

**Event frequency:** on the reference book 6% of long options reach the 40%
band. At 30k positions/day that is ~1,800 first crossings plus perhaps 800
escalations — **~2,600 alerts/day ≈ 0.12/second.** Compare with today's 333
queries/second producing the same handful of alerts.

**Redis load is unchanged** — the LTP batch write already happens; the crossing
emit rides the existing Streams bus.

**Restart safety:** rebuild the map from one query at startup. Until it is
built, fall back to the existing beat.

**Multi-worker:** the map lives in the single ticker process, which is already
the one shared connection for all users. Emitting to Streams means any worker
can do the DB write.

## 5. Crossing 40 → 60 → 80, and what happens after

| situation | today | should be |
|---|---|---|
| crosses 40 | live caution, ≤60 s | caution, sub-second |
| then 60 | danger — escalation always passes the 30-min dedup | same |
| then 80 | critical — escalation passes | same |
| **sits at 82%** | silent: same severity, `_scope` matches | silent — correct |
| **recovers to 30%, falls to 45% again** | fires caution again if >30 min | **should not** — the band was already reported for this position |
| **exits at 80%** | **exit path fires critical AGAIN** | should be suppressed — already said live |
| **adds to the position** | `avg_entry` falls, `loss_pct` falls, **detector goes quiet** | recorded in `STATUS.md`; needs a decision |

**`highest_band_fired` per position epoch is the fix for the first three rows.**
The concept already exists in this codebase — Pattern 2's position-epoch dedup,
keyed on the ledger's `OPEN`/`FLIP` timestamp — and reusing it means the counter
resets when the position genuinely restarts, not on a clock.

**The exit/live double-report needs one shared dedup scope.** The live path
already keys on `(rule, symbol)`; the exit path keys on `pattern_type` alone.
Aligning the exit path to `(pattern_type, symbol)` fixes both this and the
already-recorded bug where a second bleeding position is swallowed — **7 of 48
detections suppressed on the book, including a critical at 86.7%.**

## 6. What else is missing — the audit I should have done first

| area | state |
|---|---|
| user rules | **`sl_percent_options` collected, resolved, read by nothing.** False help text |
| real-time trigger | exists but is a 60 s poll that does not scale |
| threshold resolution | universal bands correct and `UNIVERSAL_SAFETY`; no personal layer |
| live/open-position path | present, mirrors bands, **cannot see the declared rule** |
| expiry behaviour | +15pp on both paths, consistent; magnitude unsourced |
| severity | 40/60/80 correct; **conflicts with `no_stoploss` — see §7** |
| notification | level 3, **not guardian-eligible** |
| dedup | **exit path account-scoped; live path symbol-scoped; the two never reconcile** |
| tests | 31, exit path only — **no test covers the live path at all** |
| observability | live path skips silently when LTP is stale; no counter for how often |
| scale | **fails at 10k users** |

## 7. Pattern #12 — `no_stoploss`, reviewed alongside

### What it is supposed to detect

A leveraged position exited **manually** at a loss with no stop-loss order on
record. Primary gate: if `exit_order_types` contains SL or SL-M, the mechanism
worked and it stays silent.

### It measures the same quantity as Pattern 8

For a long option, `no_stoploss` computes
`|pnl| / (entry_price × qty) × 100` — which **is** the percentage of premium
lost. Same numerator, same denominator, same population as
`premium_loss_event`. Only the bands differ: **25 / 50 against 40 / 60 / 80.**

Measured on the book (upper bound — a Console tradebook carries no order type,
so the SL gate can never fire and every trade looks stop-less):

| | |
|---|---|
| both fire on the same trade | **44** |
| only `premium_loss_event` | 4 |
| only `no_stoploss` | 52 |
| **share of Pattern 8's firings that are also Pattern 12** | **92%** |

**And they disagree about severity on the same number.** `NIFTY26FEB25750CE` at
59.8% of premium: `premium_loss_event` says **caution** (below its 60 danger),
`no_stoploss` says **danger** (above its 50). Same trade, same percentage, two
alerts, two different severities.

### Can it work in real time? Not today, and the codebase says why

`live_checks.py` records it precisely:

> *"It needs to know whether an open position has a stop-loss order resting
> against it, and the `orders` table is only populated by `sync_orders_to_db` on
> a manual or end-of-day sync — a stop placed thirty seconds ago is not in it.
> Shipping it would tell disciplined traders who use SL-M orders that they have
> no stop, which is exactly backwards."*

**But the data arrives and is discarded.** `order_stream_service` states:
*"Intermediate updates (OPEN, TRIGGER PENDING, PUT ORDER REQ RECEIVED, …) carry
no new fill and are ignored."* Zerodha's postback stream **does** deliver
`TRIGGER PENDING` for a resting SL-M. Keeping those events in the same in-memory
map proposed in §4 would give live stop-loss state with **no new infrastructure
and no new DB load** — which also matches the order-history gap already recorded
from the revenge research.

### Complementary or duplicate?

**Complementary in principle, duplicate in practice.** *"You are down 60% of
premium"* and *"you had no stop on it"* are genuinely different sentences — the
second is about preparation, the first about state. But at 92% co-firing on the
same denominator with conflicting severities, the trader receives them as one
event said twice.

**Pattern 8 should use stop-loss state as CONTEXT, not merge.** *"Down 60% of
premium, and there is no stop resting on it"* is one alert carrying both facts.
That is a families question and needs its own evidence — **and it is not
available until the live SL state above exists.**

---

## What is correct today

- The **bands** — unchanged by this review, still selecting 6% of outcomes and
  35% of the losses, still `UNIVERSAL_SAFETY`.
- **The live path exists at all**, mirrors the exit bands exactly and deliberately,
  and reads prices from Redis rather than Kite REST.
- **The 2-second staleness rejection.** A fabricated percentage on a real
  position would be the worst false positive this system could produce.
- **The live dedup scope** `(rule, symbol)`, escalation-aware over 30 minutes —
  the exit path should copy it.
- **`no_stoploss`'s primary gate.** Reading the exit order type is the right
  primary signal and correctly stays silent when the mechanism worked.
- The recorded reason live `no_stoploss` was not shipped: it is right, and it is
  documented where the next person will find it.

## What is missing

1. The declared per-trade option loss limit is **collected and never used**, and
   its help text promises otherwise.
2. The live path is a **60-second poll that re-reads every user's positions and
   rules from the DB** — 20,001 round trips/minute at 10k users, which does not
   fit in its own period.
3. **No test covers the live path.**
4. **Exit and live paths double-report** the same crossing.
5. **Exit-path dedup is account-scoped**, swallowing a second bleeding position —
   7 of 48 on the book, including a critical.
6. **No per-position band memory**, so recovery-then-relapse re-alerts.
7. **Averaging down silences the detector** while the rupee loss grows.
8. **92% duplication with `no_stoploss`, with conflicting severities.**

## What must change

**Before Pattern 8 can be called complete**, in dependency order:

1. **`sl_percent_options` becomes a `RULE_FIELD`** and reaches both paths as a
   personal layer beside the universal bands. Two events, act at whichever is
   reached first, universal never loosened.
2. **Move the live check onto the tick path** with in-memory state and
   crossing-only emission.
3. **One dedup scope shared by both paths**, keyed on `(pattern_type, symbol)`
   with per-position-epoch band memory.
4. **Tests for the live path**, including staleness, crossing, escalation and
   no-repeat.
5. Fix or delete the two false help texts.

**Not changing:** 40 / 60 / 80, the expiry shift, the repeat rule, severity
mapping, `UNIVERSAL_SAFETY`.

## Pattern 8 verdict — **MODIFY** (retracting COMPLETE)

The bands survive. The plumbing around them does not: no personal layer, a
polling live path that fails at scale, two unreconciled dedup scopes, and no
live-path tests.

## Pattern 12 preliminary verdict — **RESEARCH FURTHER, blocked**

Its primary gate is sound and its subject is real, but it is **92% duplicated
with Pattern 8 on the same denominator with conflicting severities**, and the
question that would resolve it — whether a stop is actually resting — cannot be
answered until `TRIGGER PENDING` order events stop being discarded. **Do not
review Pattern 12 to a verdict until that exists**, and do not merge the two on
current evidence.
