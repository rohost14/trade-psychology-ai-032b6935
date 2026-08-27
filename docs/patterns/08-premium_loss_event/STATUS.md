# Pattern #8 — `premium_loss_event` · **COMPLETE**

27 Aug 2026. Detector `2.0.0` → `3.0.0`. **It is no longer a behaviour detector.**
It is a real-time **risk-state** detector that supplies facts to the detectors
that judge behaviour.

Design: `event_contract.md`. Evidence: `premium_loss_event_review.md`,
`three_layer_contract.md`, `realtime_review.md`.

---

## What it is now

```
LIVE      tick -> in-memory watch -> band crossing? -> dispatch async -> alert
EXIT      closed position -> `info` BehaviorEvent -> analytics. Never an alert.
```

**The bands are unchanged: 40 / 60 / 80 percent of premium, +15pp on expiry
day, `UNIVERSAL_SAFETY`.** Nothing numeric moved.

| layer | owner | fires |
|---|---|---|
| magnitude | **Pattern 8** | live, on a band crossing |
| the trader's declared line | **`constitution_violation`**, rule `sl_percent_options` | live, on crossing |
| behaviour around the loss | **Pattern 2** | on the add |
| protection | **Pattern 12** | unchanged, still exit-only |

## Why the alert exists

**Safety notification, not behavioural intervention and not an action prompt.**
A large premium loss is a market outcome; every test that could have tied loss
magnitude to a decision has failed. The job is narrow: **close the gap between
what is true about the position and what the trader currently knows.** That gap
exists only when they are not looking — anyone watching has the number already,
because the frontend computes live P&L from this same tick stream. So it speaks
on a **crossing**, never on a state, and never at exit, where the trader
necessarily knows because they just closed it.

## What changed

| | before | after |
|---|---|---|
| live check | 60-second Celery beat, re-reading every account | **tick-driven, in-memory** |
| DB round trips | **~20,001/minute** at 10k users, serial | **0 on the hot path** |
| latency | 0–60 s | **sub-second** |
| exit path | `caution`/`danger`/`critical`, `notification_level=3` | **`info`, analytics-only** |
| the trader's declared rule | collected, resolved, **read by nothing** | a `RULE_FIELD`, live |
| dedup | `pattern_type` alone, account-scoped | **per position epoch, per band** |
| spec | `2.0.0 risk alerting notify=3` | **`3.0.0 risk analytics notify=0`** |

**Files:** `services/live_risk_state.py` (new), `tasks/position_monitor_tasks.py`
(rebuild + dispatch), `services/price_stream_service.py` (tick hook + refresh),
`core/celery_app.py` (beat deleted), `services/behavior_engine.py` (exit → info),
`services/detector_registry.py` (spec + copy), `services/constitution_service.py`
(`sl_percent_options` becomes a rule).

## Layer.SAFETY is preserved by carrying, never by dropping

> *"SAFETY findings may never be suppressed by anything learned from the trader,
> because a habit is not a licence."*

When the declared line and a universal band cross on the same price, **one**
alert fires — the constitution one — carrying `also_crossed` in its evidence and
*"That is past the 40% safety level"* in its sentence. Merging is not
suppressing when the number still reaches the trader.

## Replay — 203 sessions, before and after

| detector | before | after | note |
|---|---|---|---|
| `adding_to_adverse_position` | 99 | **99** | unchanged |
| `consecutive_loss_streak` | 78 | 0 | Pattern 4 retired |
| `daily_overtrading` | 52 | 0 | Pattern 5, declared limit only (`--no-rules`) |
| `profit_giveaway` | 48 | 0 | Pattern 6 retired |
| **`premium_loss_event`** | **41** | **0** | **exit path is analytics now** |
| `martingale_behaviour` | 39 | **39** | unchanged |
| `death_spiral` | 39 | 20 | *consequence* — see below |
| `size_escalation` · `options_premium_avg_down` | 30 · 30 | **30 · 30** | unchanged |
| `fomo_entry` | 29 | 19 | Pattern 7 |
| `expiry_day_overtrading` · `same_symbol_obsession` | 28 · 22 | **28 · 22** | unchanged |
| everything else | — | **identical** | |
| **total** | 578 | **330** | |

**`death_spiral` 39 → 20 is arithmetic, not a regression.** It counts distinct
nature-domains at danger+ per session. `premium_loss_event` was the `risk`
domain's main contributor and now emits nothing at exit; three other detectors
stopped emitting entirely. Fewer domains, fewer spirals. **Every other detector
is unchanged to the alert.**

**The measurement is preserved, not deleted.** Verified against the replay
database: `premium_loss_event` writes `info` BehaviorEvents (kept, because the
disposition is now `analytics`) and **zero RiskAlerts**, down from 41.

**The replay cannot test the live path** — it has no tick stream. That is what
the end-to-end tests are for.

## Tests — 106 for this pattern

| file | n | what |
|---|---|---|
| `test_live_risk_state.py` | 36 | crossings, band memory, both layers, build |
| `test_live_risk_dispatch.py` | 16 | consolidation, independence, failure containment |
| `test_live_risk_end_to_end.py` | **27** | **real binary frames through `_handle_binary`** |
| `test_premium_loss_event.py` | 34 | the exit path, retargeted to `info` |

**Full backend 1,455 passed. Frontend typecheck clean, 102 tests, 0 lint errors.**

### The zero-I/O property is proven, not asserted

`TestTheHotPathDoesNoIO` patches `SessionLocal`, `get_sync_redis`,
`ltp_cache.read`, `get_thresholds`, `resolve_thresholds` and `socket.connect` to
**fail the test if called**, then runs an evaluation. A separate test blocks
`_fire_position_alert` on an event and asserts `_handle_binary` **returns within
one second while the write is still blocked** — one slow write cannot stall the
price stream.

*Precision: the tick handler still performs a Redis **write** (`ltp_cache.write_batch`).
That predates this change, feeds other consumers, and is not part of the risk
evaluation. Zero Redis **reads**.*

### The tests were mutation-checked

27/27 passing first time is when a suite is most likely to be vacuous, so three
mutations were introduced and confirmed to fail: a `SessionLocal()` added to the
hot path, consolidation emitting both alerts, and band memory removed. All
reverted; clean run green.

## Limitations, recorded not closed

1. **No ticker means no live premium alerts.** The 60-second beat is gone, so
   the tick stream is the only source. This is the same exposure that already
   exists for live prices, and the ticker has reconnect logic — but it is a new
   dependency for this pattern and it is not covered by a test.
2. **No test drives a real Zerodha socket.** Frames are synthesised to the exact
   wire layout `_handle_binary` parses; the socket itself is not exercised.
3. **`sl_percent_futures` has the same unused-field problem** and no detector
   reads it. Untouched here.
4. **Pattern 12 stays exit-only.** Live stop-loss state needs the
   `TRIGGER PENDING` order events that `order_stream_service` discards. Until
   then Pattern 8 cannot carry protection as context, and the two remain 92%
   duplicated on the same denominator with conflicting severities.
5. **Averaging down still quietens it** — `loss_pct` is measured against
   `avg_entry_price`. Pattern 2 fires on the add, so the engine is not blind.
6. **The repeat rule's promotion is gone** with the severity it operated on. The
   count survives in the evidence.
7. **40 / 60 / 80 remain unsourced round numbers** that select the top 6% of
   outcomes and 35% of the losses on one trader's book.
