# Globals layer — structural findings

Findings only. Nothing in this document has been implemented.

Scope: the machinery that sits *around* every detector — alert consolidation,
the session cap, the dedup window, the per-account lock, and the notification
gate. These belong to no single pattern, so the pattern-by-pattern pass will
never reach them.

Ordered by severity. Each finding states what is provable from the code, what
is inferred, and what the production impact is at scale.

---

## B1 — The session cap silently drops critical alerts *and* silences the UI

`backend/app/tasks/trade_tasks.py:1452`

```python
if session_alert_count >= HARD_CAP:
    ...
    return []          # every alert in the batch, regardless of severity
```

No severity check. The ninth alert of a session is discarded whether it is
`caution` or `critical`.

**The part that is worse than it looks.** The caller rebinds its list to this
function's return value:

```python
new_alerts = await _apply_alert_consolidation(broker_account_id, new_alerts, db)
...
if new_alerts:
    publish_event(str(broker_account_id), "alert_update", {...})
```

So an empty return suppresses the **`alert_update` WebSocket event** as well as
push and WhatsApp. The alert row exists in `risk_alerts`, but the dashboard is
never told, and the trader sees nothing until they manually refresh. The cap is
documented as a notification guard; it is in practice a real-time-UI guard.

The ninth alert of a session is the one most likely to matter — a session that
has produced eight alerts is the definition of a deteriorating day, and
`death_spiral` is by construction late.

**Severity: HIGH.** Correctness, and it fires on exactly the sessions the
product exists for.

---

## B2 — The cap keys off wall-clock today, not the alert's session

`trade_tasks.py:1436`

```python
today_ist = datetime.now(pytz.timezone("Asia/Kolkata")).date()
... TradingSession.session_date == today_ist
```

The alert belongs to `completed_trade.exit_time` (`detected_at` is the trade's
time, deliberately, not the processing time). The cap looks up a session by the
*processing* date.

**Correcting an earlier, stronger claim of mine:** I initially reported this as
a backfill hole. It is not. `run_behavior_engine_full_session` selects only
`exit_time >= today_start_utc`, so the bulk path also works on today's trades
and the two dates normally agree. The real exposure is narrower:

- A postback processed after IST midnight for the previous session — reachable
  because failed tasks retry with `countdown`, and `run_behavior_detection_retry`
  requeues at +10s from a path that may already be late.
- Any future path that replays or re-evaluates a historical session.

When they diverge, the session lookup misses, `session_alert_count` falls back
to `0`, the cap does not apply, and `if notifiable and session` means the
counter is never incremented either — so the day's budget silently resets.

**Severity: MEDIUM.** Narrow trigger, silent failure, and it becomes HIGH the
moment anything re-evaluates a past session.

---

## B3 — `alerts_fired` is a read-modify-write, not an atomic update

`backend/app/services/trading_session_service.py:174`

```python
session = await db.get(TradingSession, session_id)
session.alerts_fired += count
```

Classic lost update. Two concurrent detections on one account both read 5, both
write 6, and the cap under-counts.

`add_session_pnl` (line 182) has the identical shape and is **worse**, because
`session_pnl` is read by detectors — `session_meltdown` thresholds on it and
`revenge_trade` scores a `session_red` signal from it. A lost update there does
not just miscount alerts, it changes what the engine detects.

Currently mitigated by the per-account Redis lock (below), so this is latent
rather than live. It goes live the instant anything runs detection outside that
lock — see B5 and B6.

**Severity: MEDIUM latent / HIGH if the lock is bypassed.**

---

## B4 — The Redis lock has no fencing token; release is unconditional

`trade_tasks.py:313-325`

```python
def _acquire_lock(redis_client, key, ttl_seconds):
    return bool(redis_client.set(key, "1", nx=True, ex=ttl_seconds))

def _release_lock(redis_client, key):
    redis_client.delete(key)
```

The value is the constant `"1"` and release is an unconditional `DELETE`. The
standard failure: worker A acquires with a 60s TTL, detection runs long, the
TTL expires, worker B acquires the same key, then A reaches its `finally` and
deletes **B's** lock. Two workers now run detection on one account
concurrently, which activates B3 and can duplicate alerts.

Probability scales with detection latency against the TTL. The webhook path
holds this lock for the *entire* detection — context load, 27 detectors,
persistence, death-spiral check, consolidation — with `ttl_seconds=60`.

**Severity: MEDIUM-HIGH at scale.** Rare per event, inevitable across millions.

---

## B5 — A Redis outage fails closed on one path and open on the other

Webhook path (`~line 636`): if `_get_redis_client()` returns `None`,
`_acquire_lock` calls `None.set(...)` → `AttributeError` → the trade task
fails and retries. Fails closed, loudly, and the trade is not processed.

Bulk path (`~line 1234`):

```python
if _redis is not None and not _lock_acquired:
    ...abort
```

When Redis is down `_redis` **is** `None`, so the abort is skipped and bulk
detection **proceeds with no lock at all**. Fails open, silently.

Two paths into the same critical section with opposite outage semantics, and
the one that fails open is the one that processes a whole session at once.

**Severity: MEDIUM.**

---

## B6 — `run_risk_detection` enters the critical section unlocked

`trade_tasks.py:862`. A registered Celery task that calls
`run_risk_detection_async` directly with no lock acquisition. It is exported in
`app/tasks/__init__.py` and currently has no in-repo caller — but it is a live
task name, invocable by `.delay()` from any future code, an ops console, or a
retry policy.

**Severity: MEDIUM (footgun).** Harmless today, and it removes every guarantee
B3/B4 depend on the moment somebody calls it.

---

## B7 — The cap counts saved rows, not delivered ones

Already documented in the function's own docstring.
`RiskAlert.delivered_push_at` / `delivered_whatsapp_at` exist and are written
only by the merged-push branch, so a saved-but-suppressed alert still consumes
the session budget. It errs quiet, which is the safe direction, but it means an
alert that was muted, stale-gated, or capped still spends the budget of one
that reached the trader.

**Severity: LOW-MEDIUM.**

---

## B8 — The engine is not reproducible: 355 vs 359 alerts on identical input

The same tradebook, the same flags, the same code produced 355 alerts on
11 Aug and 359 on 12 Aug. Unexplained.

Leading hypotheses, in order: the 24h dedup cutoff uses
`datetime.now(timezone.utc)` and is compared against `detected_at`, so its
behaviour depends on wall clock relative to the frozen clock; the 5-minute
consolidation bucket has the same shape; `teardown_lab` may not clear
everything between days.

**Why this is not cosmetic.** Every threshold experiment from here on measures
a difference against a baseline that moves by ±4 alerts on its own. Calibration
is not possible on a non-reproducible engine, and this is the pass where we
start calibrating.

**Severity: MEDIUM, blocking for the calibration work.**

---

## B9 — Cosmetic: cap logs a warning for an empty batch

Observed in the replay: `session alert cap reached (8/8). Suppressing: []`. The
cap check runs before testing whether there is anything to cap. Noise in ops
logs, no behavioural effect.

---

# Scalability analysis

The user's requirement: the fix must hold "no matter how many users, trades".

## What already scales, and should not be changed

- **Everything is scoped by `broker_account_id`**, and the hot queries are
  indexed — `idx_risk_alerts_broker_detected (broker_account_id, detected_at)`
  covers both the dedup window and the 5-minute bucket;
  `uq_trading_session_account_date` makes the session lookup a unique-index
  single-row hit.
- **The lock is per account**, so accounts are mutually independent and Celery
  scales horizontally on user count. User count is not a bottleneck.
- **Detection is per completed trade**, not per fill, which is roughly a 3:1
  reduction on this tradebook (2,175 fills → 693 round trips).

## Where the cost actually is

Per detection, the path issues roughly ten database round trips: context load,
24h dedup select, flush, event persist, commit, death-spiral evaluation,
session lookup, 5-minute bucket select, counter increment, alert-mute select.

- The **24h dedup** does `select(RiskAlert)` — whole ORM rows, not columns —
  and materialises them into three Python dicts. Bounded by the cap in practice
  (~8/session), so small; but it runs on every trade, inside the lock.
- **Lock hold time equals full detection time.** This bounds a *single*
  account's throughput and is the input to B4's TTL race.

**Load estimate.** 10,000 active users × ~20 completed trades/day ≈ 200k
detections/day ≈ 2.3/sec average. Postgres is untroubled by that. The risk is
not the average — it is the **15:15–15:30 IST square-off burst**, when a large
share of all intraday positions close within minutes. Locks are per account so
there is no lock contention, but connection-pool size and Celery concurrency
become the binding constraint, and every detection in that burst holds a
connection for its whole duration.

---

# Proposed fixes

Design goals: constant work per alert regardless of user or trade count, no
new hot-path round trips, correct under concurrency without relying on the
lock, and no new migration (074 and 077 are still unapplied).

## F1 — Make the cap a single atomic statement keyed on the alert's own session

Replaces the read-compare-increment sequence (fixes **B2** and **B3**, and
removes the cap's dependence on the lock):

```sql
UPDATE trading_sessions
   SET alerts_fired = alerts_fired + :n,
       updated_at   = now()
 WHERE broker_account_id = :account
   AND session_date      = :session_date
RETURNING alerts_fired;
```

- `:session_date` derived from the **alert's** `detected_at` in IST, never
  `datetime.now()`. That is the whole of B2.
- Atomic read-modify-write in one statement — no lost update, B3 gone, and it
  stays correct even if the lock is bypassed.
- Single-row update on a unique index. **O(1) in users and trades.**
- `RETURNING` gives the post-increment count, so the decision needs no second
  query; net round trips *decrease* by one.

The same treatment applies to `add_session_pnl`, which is the more dangerous of
the two because detectors read the value.

Ordering note worth deciding explicitly: incrementing before deciding means a
capped batch still consumes budget. Reserving-then-releasing is more correct
and more complex. Recommend increment-then-decide, with the cap comparing
`alerts_fired - n` so the batch that trips the cap is judged on the state
before it.

## F2 — Exempt `critical` from the cap, and always emit the WebSocket event

Two independent changes to B1:

1. Partition rather than discard — return `critical` alerts even when capped,
   drop the rest. A severity floor is the minimum; the more defensible rule is
   that the cap governs *interruption* (push/WhatsApp) and never *visibility*.
2. Publish `alert_update` based on what was **persisted**, not on what survived
   consolidation. The dashboard should always learn that something happened;
   whether the phone buzzes is a separate decision. This is a one-line
   separation of two concerns that are currently the same list.

Scale impact: none. It is the same work on a differently-partitioned list.

Note for the product decision you already flagged: this is *not* the volume cap
you rejected. Your position — 2–4 alerts a day is fine — concerns the cap's
*value* (8) and the process-vs-outcome question. F2 concerns whether a
`critical` can be silently dropped at all, which is a correctness question
independent of where the number sits.

## F3 — Fence the lock

Store a per-acquisition token and release with a compare-and-delete Lua script,
the standard pattern:

```python
token = uuid4().hex
acquired = redis.set(key, token, nx=True, ex=ttl)
# release:
#   if redis.call("get", KEYS[1]) == ARGV[1] then return redis.call("del", KEYS[1]) end
#   return 0
```

Fixes **B4**. One extra Redis round trip on release, constant cost.

Separately, the 60s TTL should be justified against measured detection latency
(`alert_e2e_lag_ms` already exists) rather than chosen. A watchdog that extends
the lock while work is in flight is the fuller answer; the token is the
cheap 90% and should come first.

## F4 — One outage policy, stated once

Fixes **B5**. Make both paths do the same thing when Redis is unavailable, and
write down which it is. Recommendation: **fail closed and requeue.** The
webhook path already has `run_behavior_detection_retry`; the bulk path is
explicitly documented as safe to rerun. Running detection unlocked is the one
option that produces silent duplicate alerts and corrupt session P&L, and it is
currently what happens.

## F5 — Close the unlocked entry point

Fixes **B6**. Either delete `run_risk_detection` (nothing calls it) or have it
acquire the same lock. Deleting is cleaner; per project convention it moves to
`_archive/` rather than being removed.

## F6 — Pin down reproducibility before calibrating

Fixes **B8**, and it gates the rest of the threshold work. Method: run the
replay twice, diff the two sidecars day by day, and identify the first day that
differs. The sidecar already carries per-day alerts with timestamps, so the
diff is mechanical. Expect the answer to be a wall-clock read that should be
reading the frozen clock.

## F7 — Trim the hot path (optional, deferred)

Not a bug, and only worth doing if the square-off burst shows real pressure:
select only the columns the dedup needs rather than whole `RiskAlert` rows, and
fold the alert-mute lookup into a cached per-account set. Both are constant-
factor wins, neither changes complexity. **Recommend deferring** until there is
a measured problem — the current cost is already O(1) per detection.

---

# Suggested order

1. **F6** — reproducibility, because every later measurement depends on it.
2. **F1 + F2** — correctness, no migration, reduces round trips.
3. **F3 + F4** — concurrency safety under real load.
4. **F5** — close the footgun.
5. **F7** — only if measurement justifies it.

None of this touches a detector or a threshold, so it is independent of the
pattern-by-pattern work and can land before it.
