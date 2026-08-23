# Scalability at 50,000 users — where it breaks, in order

23 Aug 2026. Analysis only; nothing here was changed. Every configuration figure
was read out of the code, and every performance figure was measured. Where a
number is assumed, it says so.

This is deliberately **separate** from the per-trade runtime work. Those
measurements establish that the cost of analysing one trade is bounded and that
detector count is not the problem. They say nothing about queue throughput,
worker concurrency, connection capacity or real-time latency at scale, and they
must not be quoted as if they did.

---

## 1. What is actually configured today

| | value | where |
|---|---|---|
| Worker processes | **1** | `Procfile` |
| Worker concurrency | **4** prefork | `celery_app.py:73` |
| Prefetch | 1 (`worker_prefetch_multiplier`) | `celery_app.py:72` |
| Queues on that one worker | `celery, trades, alerts, reports, bulk` | `Procfile` |
| Worker DB pool | **NullPool** — connect and close per checkout | `database.py:34` |
| Web DB pool | 5 + 10 overflow = 15 per process | `database.py:37` |
| Event fan-out | 2 `XADD` per event (account + global stream) | `event_bus.py:125,128` |
| WS subscriber | one async loop per web process, `XREAD count=20 block=2s` | `event_bus.py:217` |
| WS registry | in-process dict, `account_id -> set[socket]` | `websocket.py:35` |
| Kite REST | **3 req/s per API key, shared by every user** | Model A, one platform app |

Measured, per completed trade (real database):

```
_load_context          median  51.6ms   p90  68.2ms
_run_all_detectors     median   3.2ms   p90   5.4ms
analyze() end-to-end   median  73.0ms   p90  89.9ms
```

## 2. The load model

Stated so it can be argued with rather than assumed.

- 50,000 registered users; **20% trade on any given day** = 10,000 active.
- 12 completed round-trips per active trader per day = **120,000 CompletedTrades/day**.
- ~2.5 fills per round-trip = **300,000 postbacks/day**.
- Market window 09:15–15:30 = 22,500 seconds → **13.3 postbacks/second average**.
- F&O volume clusters at the open and the close. **Peak ≈ 3× average = 40/s.**

`analyze()` is 73ms, but the task that wraps it (`process_webhook_trade`) also
upserts the trade, applies the ledger fill, builds the CompletedTrade, writes the
feature row, runs strategy detection, persists alerts and publishes events.
**Assume 300ms per postback** — measured only for the 73ms core, so this is the
softest number here and the first thing to measure properly.

---

## 3. The ceilings, in the order they are hit

### Ceiling 1 — worker concurrency. Hit at roughly today's average load.

4 slots ÷ 300ms = **13.3 tasks/second**. The average is 13.3/s. Peak is 40/s.

So a single worker at concurrency 4 is at exactly 100% utilisation on the
average and **3× oversubscribed at the peak** — and `worker_prefetch_multiplier=1`
means no buffering absorbs it. The queue grows through the open, drains through
the midday lull, grows again at close.

The consequence is not lost work — `task_acks_late=True` and the queue is
durable. It is **latency**: a behavioural alert that arrives forty minutes after
the trade is not a mirror, it is a report. The entire product claim is that the
alert lands while the decision is still live.

Needed at peak: 40 × 0.3 = **12 concurrent slots**, plus headroom for the EOD
fan-out that shares this worker → **4–6 worker processes at concurrency 4**.

This is the cheapest ceiling to raise and should be raised first, because
everything below it is masked until it is.

### Ceiling 2 — database connections, and specifically NullPool.

The worker uses `NullPool`: a connection is opened and closed per checkout. That
was a correct choice for the bug it solves (asyncpg connections are not safe to
reuse across event loops, and a pool starves under burst) — but it converts
concurrency into **connection churn**.

At 12–24 concurrent tasks each opening its own connection, sustained 40/s means
**40 new Postgres connections per second**, each paying TCP plus TLS setup to
Supabase. Supabase's pooler caps concurrent client connections in the low
hundreds; the churn rate matters as much as the ceiling.

This is the ceiling that will be reached *while raising ceiling 1*, and it is the
one most likely to present as something else — timeouts, "database is slow",
intermittent task failures — rather than as an obvious connection error.

The fix is not to abandon NullPool casually: the loop-affinity bug it prevents is
real. A per-worker-process pool with `pool_pre_ping` and an event loop that lives
for the process lifetime is the usual answer, and it needs to be verified against
the original failure rather than assumed.

### Ceiling 3 — WebSocket delivery is head-of-line blocked.

`send_to_account` awaits each socket in turn with a **2-second timeout each**,
and it is called from inside the single event-subscriber loop:

```python
for websocket in conns:
    await asyncio.wait_for(websocket.send_json(message), timeout=2.0)
```

One trader on a bad mobile connection therefore stalls the subscriber loop for up
to two seconds — and that loop is delivering **every other user's alerts**. With
several slow sockets the delay compounds. At 50k users this is not a tail risk,
it is the normal case: some fraction of sockets is always in a bad state.

This is a correctness problem for a real-time product before it is a throughput
one, and it exists **today at one user's scale** — it simply cannot be observed
with one user.

### Ceiling 4 — every web process reads the entire global stream.

The WS registry is per-process memory, so cross-process routing works only
because *every* process subscribes to `stream:events` and filters by account.
With N web processes, every event is read N times.

At 50k users, ~50k concurrent sockets, and a realistic 5–10k sockets per uvicorn
process, that is **5–10 processes each reading every event**. The per-account
streams (`stream:<account_id>`) already exist and are already written — the
subscriber just does not use them. Routing each process to only the accounts it
holds removes the amplification entirely, at the cost of dynamic subscription
management.

### Ceiling 5 — Kite's 3 req/s, shared across all users. The hard one.

This is not tunable by adding hardware. One platform API key, three requests per
second, for everybody.

Prices stream over the shared KiteTicker and postbacks are pushed, so the live
path is mostly clear of it. What is not clear of it is **anything per-user over
REST**:

> 50,000 users × 1 margin fetch/day ÷ 3 req/s = **4.6 hours** of continuous,
> exclusive API budget.

There is no version of this that runs before the open. It means per-user REST
calls cannot be part of any daily cycle at 50k, and the design has to assume
that — not discover it.

---

## 4. The gap this analysis found in work just completed

**`margin_snapshots` has no scheduled producer.**

`MarginSnapshot` rows are written in exactly one place —
`margin_service.get_margin_status` (`margin_service.py:295`) — which is reached
only from the `GET /api/zerodha/margins` endpoint. Nothing writes a snapshot on a
schedule.

That matters because the account-risk denominator wired into the engine
yesterday resolves like this:

1. `opening_balance` from a snapshot taken **today** → GOOD
2. most recent snapshot, under the staleness limit → PARTIAL
3. declared capital → PARTIAL
4. abstain → UNKNOWN

Rung 1 is only ever reached **if the trader happened to open a page that fetched
their margins that day**. The engine's best-quality account measurement is
therefore contingent on a UI visit, which is not a property anyone designed.

And the obvious fix — a daily job that snapshots every account before the open —
is exactly what ceiling 5 forbids at 50k: 4.6 hours of API budget for a
15-minute window.

The honest options, none of which should be chosen without the product decision:

- **Snapshot on the day's first postback**, per account. Cost scales with active
  traders (10k), not registered users, and it happens when the account is
  demonstrably in use. Still 10,000 ÷ 3/s = 55 minutes, spread across the
  session rather than before it — so the first trades of the day resolve at
  PARTIAL and later ones at GOOD, which is at least honest and is recorded.
- **Accept declared capital as the normal path** and treat GOOD as a bonus. This
  is closest to today's behaviour, and `capital_mismatch` already exists to
  detect when the declared figure has drifted.
- **Abstain by default**, and let the trade-relative and structural safety
  families carry cold start — which they already do, by design.

I am not proposing one. It is a product decision about what the engine is allowed
to claim, and it interacts with the frozen capital-relative constants.

---

## 5. What is NOT a ceiling

Worth recording, because these get raised repeatedly and the measurements settle
them:

- **The 27 detectors.** 3.2ms of a 73ms trade. Detector count is not a
  performance question and has not been one at any point.
- **`_load_context` growing with session length.** Query count is constant in
  session size, and a test fails the build if that changes.
- **Redis command volume for events.** ~60,000 `XADD`s per day at the load model
  above, against streams already capped by `maxlen`. Trivial.
- **The KiteTicker 3,000-instrument cap.** Real, already documented, and
  deferred by decision: three connections is ~9,000 instruments of runway.

---

## 6. What this analysis does not establish

It is a capacity model built from configuration and one measured number. It is
not a load test. Specifically unproven:

- the 300ms-per-postback assumption (only the 73ms core is measured);
- actual Supabase connection and write limits on the current plan;
- uvicorn socket capacity per process on the deployed instance size;
- behaviour under sustained backlog — whether latency degrades gracefully or
  the queue never drains within a session;
- Upstash command limits on the current tier at 5–10 subscribing processes.

Each of those is a measurement someone can take. None should be asserted from
this document.
