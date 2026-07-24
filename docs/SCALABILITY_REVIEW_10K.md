# Scalability Review — Can we hold 10,000 concurrent users?

> Detailed architecture review, grounded in the codebase (2026-07-25). Answers: bottlenecks,
> required upgrades, code improvements, and the specific "doing all the math for all users at
> once" concern. **No implementation — findings + plan.**

---

## TL;DR verdict
**10k concurrent is achievable — but NOT on the current sizing, and NOT with the batch tasks as written.**
- The **architecture is sound where it matters** (shared market-data ticker, event-driven per-trade engine, Redis-Streams fan-out, indexed per-account queries, idempotent processing).
- The **current config is dev/small-tier** (4 Celery workers on a 512MB box, Upstash free tier, DB pool 5) — will fall over well before 10k.
- A few **specific code bottlenecks** (sequential "all-account" batch jobs, ticker instrument cap) need fixing.
- **It is NOT a rewrite** — it's infra scaling + ~4 targeted refactors + a load test.

---

## What already scales well (credit where due)
- **Shared KiteTicker** (`price_stream_service.py`): **ONE** KiteTicker connection for **all** users, subscribed to the *union* of open-position instruments, fanned out to every browser WS. The classic market-data trap ("N connections for N users") is **avoided by design**. ✅
- **Behavioural engine is PER-TRADE, event-driven** — a postback → Celery task → engine runs for **one fill**. It does **not** recompute all users. Scales with **trade volume**, distributed across market hours. ✅
- **Redis Streams event bus → WebSocket** fan-out (works across processes; replay on reconnect).
- **DB indexed** for per-account + time-windowed access (021/031/043/067 + 073); admin aggregates cached.
- **Idempotent** processing (webhook dedup, PositionLedger idempotency keys) — safe under retries/bursts.

---

## Your specific question: "doing all the math for all users at once"
Direct answer, split by path:

- **LIVE (per trade):** P&L (FIFO → CompletedTrade), features, and the 22-detector engine run **per fill**, triggered by each postback — event-driven and distributed, **never a synchronous all-users compute**. So the live engine does **not** grind through all users at once. It scales with trade volume + Celery worker count. ✅ *(This is the part you feared — it's actually fine architecturally.)*
- **NIGHTLY / BATCH:** the jobs that *do* iterate **all** users are the real "all at once" risk (below) — pattern re-learn, reconciliation, EOD reports.
- **ANALYTICS (on-demand):** computed per-user when they open a page (indexed; admin aggregates cached). Fine.

So: **the live math is fine; the batch jobs are the bottleneck.**

---

## BOTTLENECKS (ranked)

### B1 — Celery capacity 🚩 P0 (the #1 compute limit)
`worker_concurrency=4` sized for a "512MB Render free tier". 10k active traders × ~10–50 fills/day = **100k–500k engine tasks/day**, concentrated in market hours (09:15–15:30). Four workers cannot keep up → queue backlog → alert latency blows the 3s SLO.
**Fix:** horizontal scale — multiple worker instances, tuned concurrency, **autoscale on queue depth** (the watchdog already alerts on backlog > 2000). Give the heavy queues (`trades`, `alerts`) more workers (routing already exists).

### B2 — "All-account" batch tasks loop sequentially in ONE task 🚩 P0 (your concern, confirmed)
- **`intent_tasks` re-learn (18:15 IST):** loops **every** active account, calls `ai_personalization_service.learn_patterns(days_back=90)` per account, in **one task**, on **one worker**, sharing **one DB session**. At 10k accounts → runs for hours, blocks a worker, holds a long transaction/connection. `learn_patterns` may also call the LLM → **10k LLM calls back-to-back** = cost + provider rate-limit explosion.
- **`reconciliation_tasks._reconcile_all_accounts`:** sequential loop per account.
- **`report_tasks` EOD:** sequential loop per account. *(Weekly summary already fans out with `apply_async` per account — the good pattern to copy.)*
**Fix:** fan-out — dispatch **one sub-task per account** (chunked), each with its **own** DB session, on a **bounded** queue; stagger AI-heavy work + cache.

### B3 — Redis / Upstash tier 🚩 P1
The code is heavily optimized for Upstash **free tier** (60s heartbeat, skip-XREAD-when-idle, shared pools — comments cite "26M cmds/month"). 10k users **blows past** free-tier command + connection budgets.
**Fix:** paid Upstash / managed Redis with command + connection headroom; validate the budget under load.

### B4 — DB connections P1
`pool_size=5 + max_overflow=10 = 15 per process`. × (web instances + worker instances) can exceed Postgres/Supabase connection caps.
**Fix:** Supabase **pooler (pgbouncer, transaction mode)** — note asyncpg prepared-statement caveats; right-size pool per instance; do the total-connection math; consider a read replica for analytics.

### B5 — KiteTicker instrument subscription cap P1
Subscribes to the **union** of all open-position instruments. At 10k F&O traders (options = many strikes), the union can exceed KiteTicker's practical per-connection subscription limit → dropped ticks / rejected subscribes. **Not currently capped or sharded.**
**Fix:** monitor instrument count; **shard across multiple ticker connections** (Zerodha allows up to 3 per api_key) by instrument range when the union grows past a safe threshold.

### B6 — WebSocket fan-out Redis cost P1
Each web **process** runs a global consumer that `XREAD`s per-account streams; every process reads. At 10k users × N web instances, XREAD command volume + connection count must be validated (ties to B3).
**Fix:** if Redis cost is too high, move to **consumer groups** / stream sharding; keep the "skip when no local clients" optimization.

### B7 — WebSocket connection ceiling per process P2
10k concurrent WS spread across web instances; each process holds its socket set in memory (`manager.active_connections`).
**Fix:** enough web instances behind a load balancer; validate per-instance WS ceiling (file descriptors, memory, event-loop headroom).

---

## Required upgrades (infrastructure)
| Layer | Now | For 10k |
|---|---|---|
| Celery workers | 4 concurrency, 512MB free | multiple instances, tuned concurrency, autoscale on queue depth |
| Web | (small) | multiple instances behind LB |
| Redis | Upstash free | paid Upstash / managed Redis (command + connection headroom) |
| Postgres | pool 5+10/proc | pooler (pgbouncer) + right-sized DB (+ optional read replica) |
| Hosting | free/small tier | sized instances + autoscaling; off free tier |
| LLM (OpenRouter) | — | rate-limit + cost budget for batch + live load |

---

## Code improvements (the refactors — do before scale)
- **CR1 (P0):** Fan-out the sequential all-account tasks (re-learn, reconcile, EOD) → per-account sub-tasks, own sessions, bounded queue. *(Copy the weekly-summary `apply_async` pattern.)*
- **CR2 (P1):** KiteTicker instrument-count guard + shard across connections when the union exceeds a threshold.
- **CR3 (P1):** No shared long-lived DB session across account loops — per-account session/commit.
- **CR4 (P1):** Stagger + cache AI-heavy batch (re-learn's LLM calls); cap concurrency to respect OpenRouter limits.
- **CR5 (P2):** WS consumer efficiency at scale (consumer groups / sharding) if Redis cost demands it.

---

## Edge cases at scale
- **Market-open spike (09:15):** order burst → queue backlog → latency. Needs autoscale + backpressure.
- **Expiry day:** massive trade volume + instrument churn (hits B1/B2/B5 together).
- **Daily token-expiry storm (~6am):** all users' Zerodha tokens expire → reconnect storm at market open.
- **Ticker reconnect storm:** SharedPriceStream picks a new token on `noreconnect`; if the chosen token is invalid → retry churn.
- **Nightly batch overlap:** re-learn (18:15) + EOD reports + reconciliation overlapping → worker contention (worsened by B2's single-task loops).
- **LLM provider rate limits** under batch re-learn + live chat + reports simultaneously.
- **Redis eviction under memory pressure:** cache is rebuildable; lost replay = missed WS catch-up, but mitigated by on-reconnect refetch.
- **Postback delivery gaps at scale:** reconciliation must keep up — but reconciliation is itself a batch job (B2), so a backlog compounds.
- **Upstash connection cap exceeded** → failures; validate pool sizing.
- **DB hot rows:** `trading_sessions` (one per account/day) — fine, per-account, no global contention.

---

## Bottom line
- **Design: mostly right for 10k** — the hard problems (market-data fan-out, per-trade engine) are already solved well.
- **Sizing & batch jobs: not ready** — free/small tiers + sequential all-account loops will break first.
- **Path to 10k:** (1) fan-out the batch tasks [CR1, code] → (2) scale Celery/Redis/DB/web off free tiers [infra] → (3) ticker instrument sharding [CR2, code] → (4) **load test** (1k → 10k) to find the real ceiling and tune. **No rewrite.**

*This complements `PRODUCTION_READINESS_CHECKLIST.md` §C (Scale & Performance) — those checklist items map to B1–B7 / CR1–CR5 here.*
