# TradeMentor AI — Infrastructure, Deployment & Cost Analysis
*Session 19 — 2026-03-15. All pricing from live sources. Covers current limits, scaling path, deployment options, and full cost breakdown.*

---

## 1. CURRENT ARCHITECTURE — HOW MANY USERS CAN IT HOLD RIGHT NOW?

**With zero changes, zero spending on infrastructure:**

| Registered Users | Concurrent Active | Peak Trades/sec | Status |
|-----------------|------------------|----------------|--------|
| 100 | 10–20 | ~0.1 | ✅ Perfectly fine |
| 500 | 50–100 | ~0.5 | ✅ Fine |
| 1,000 | 100–200 | ~1 | ✅ Works, tight on Supabase free |
| 1,500 | 150–300 | ~1.5 | ⚠️ Supabase free hits connection limit |
| 2,000 | 200–400 | ~2 | ⚠️ Celery queue starts building |
| 3,000 | 300–600 | ~4 | 🔴 Celery saturated (4 workers × 6.7 tasks/sec = limit) |

**Comfortable real-world limit with current code and zero cost: ~1,000–1,500 registered users.**

The assumption throughout is realistic F&O retail behaviour:
- 5–15 trades/day (not 100)
- 20–25% of registered users active on any given day
- 30–50% of active users connected simultaneously at peak market hours

---

## 2. WHAT BREAKS AND WHEN (ROOT CAUSES)

### Breaks at ~1,500 users — Supabase free DB connections

```
Supabase free tier: 60 direct DB connections, NO PgBouncer (paid only)
SQLAlchemy NullPool: every request = new connection

At 1,500 users with typical concurrent usage:
  50–80 simultaneous DB connections → hits the 60-connection ceiling
  Supabase starts refusing connections → HTTP 500 errors
```

**Fix cost: $25/month (Supabase Pro → 200 pooler connections)**

### Breaks at ~3,000 users — Celery 4 workers

```python
# celery_app.py:53
worker_concurrency=4  ← entire bottleneck

At peak (44 trades/sec with 3k users):
  4 workers × (1 task / 0.6s) = 6.7 tasks/sec throughput
  44 tasks/sec incoming → queue grows at 37 tasks/sec
  After 60 seconds: 2,220 tasks queued, trades arriving 5 minutes late
```

**Fix cost: $0 (just change the number, same machine)**
Change `worker_concurrency=4` → `worker_concurrency=50`
Requires a machine with enough RAM: each worker ~120MB → 50 workers = 6GB RAM

### Breaks at ~5,000 users — Beat tasks never complete

```
position_monitor runs every 30s, loops 5,000 accounts sequentially
5,000 × 15ms per account = 75 seconds per run
Scheduled every 30 seconds → permanently 2–3 runs overlapping
Worker queue fills with stale beat tasks

portfolio_radar runs every 5 min, loops 5,000 accounts
5,000 × 200ms per account = 1,000 seconds (16 minutes!)
Scheduled every 300 seconds → never finishes
```

**Fix cost: $0 (code change, asyncio.gather in batches)**

### Breaks at ~8,000 users — KiteTicker connections

```
PerUserPriceStream = 1 KiteTicker WebSocket per account
8,000 users with open positions = 8,000 concurrent KiteTicker connections
Zerodha has not published a hard limit but this is well beyond intended use
```

**Fix: Requires Zerodha partnership for SharedPriceStream (1 connection total)**
OR: Rate-limit to 500 concurrent KiteTickers + HTTP LTP fallback for the rest

---

## 3. WHAT DOES THE QUICK-WIN FIX GIVE YOU?

These three changes take **under 4 hours** and cost **nothing**:

1. `celery_app.py:53` — `worker_concurrency=4` → `worker_concurrency=50`
2. Add 6 composite DB indexes (run SQL in Supabase dashboard)
3. Add `asyncio.gather` parallelization to beat tasks (position_monitor + portfolio_radar)

**Result: Comfortable limit jumps from ~1,500 → ~8,000–10,000 registered users** (at realistic trade volumes of 5–15/day, not 100).

The machine you're already running on can handle this if it has ~8GB RAM. No new infrastructure needed yet.

---

## 4. DEPLOYMENT: WHAT DO YOU ACTUALLY NEED?

### Right Now (0–2,000 users): Railway.app

**Railway is the right choice for where you are today.** No DevOps knowledge needed, deploys from GitHub in minutes, handles all three services (FastAPI + Celery workers + Celery beat) as separate services in one project.

**Setup:**
```
Project: TradeMentor
├── Service: api          (FastAPI, uvicorn --workers 4)
├── Service: worker       (celery -A app.core.celery_app worker --concurrency 50)
└── Service: beat         (celery -A app.core.celery_app beat -S redbeat.RedBeatScheduler)
```

**Railway pricing (confirmed):**

| Plan | Monthly | What you get |
|------|---------|-------------|
| Trial | $0 for 30 days | 1 vCPU / 0.5GB per service — then requires paid plan |
| Hobby | $5/mo + usage | Up to 48 vCPU / 48GB total, 6 replicas |
| Pro | $20/mo + usage | Up to 1,000 vCPU / 1TB total, 50 replicas |

**Usage billing (beyond plan credit):**
- CPU: $0.000007720/vCPU-second
- RAM: $0.000003860/GB-second

**Real cost for TradeMentor on Railway (Hobby plan):**
```
3 services × 0.5 vCPU × 0.5 GB running 24/7:
CPU: 3 × 0.5 × 2,592,000s × $0.00000772 = $30/mo
RAM: 3 × 0.5 × 2,592,000s × $0.00000386 = $15/mo
+ $5 plan fee
Total: ~$50/mo
```

At 2,000+ users, upgrade worker service to 2 vCPU / 4GB and add a second worker replica:
```
Total Railway: ~$90–120/mo
```

**No Docker required for Railway.** It reads your `requirements.txt` and `Procfile` and builds automatically from GitHub.

### Render.com — Alternative to Railway

Very similar to Railway. Slightly more expensive for the same specs.

**Key difference**: Free tier spins down after 15 minutes of inactivity → 30-60 second cold starts on first request. **Not acceptable for a trading app.** You must use paid tier ($7/month minimum per service).

TradeMentor on Render (3 services, Standard plan):
- FastAPI: $25/mo
- Celery worker: $25/mo
- Celery beat: $7/mo
- Total: **$57/mo** — slightly more than Railway for same specs

**Verdict: Railway is cheaper and simpler. Use Railway.**

---

## 5. DO YOU NEED DOCKER?

**Not immediately, but add it within 2–3 weeks.**

You don't need Docker to deploy on Railway or Render — they handle it. But a `Dockerfile` is worth adding because:

1. **Local parity**: Eliminates "works on my laptop, fails in prod" bugs. Especially important for Celery tasks that have different behaviour under asyncio
2. **Portability**: If you switch from Railway to EC2/ECS/Render, same image runs everywhere
3. **CI/CD**: GitHub Actions can build + test the Docker image before deploying
4. **Celery worker isolation**: Each worker in its own container = clean restarts, no shared state

```dockerfile
# Dockerfile (minimal, gets you 90% of the benefit)
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Effort: 2 hours. Payoff: permanent.**

---

## 6. DO YOU NEED KUBERNETES?

**No. Not until 50,000+ users or $50k+/month infrastructure spend.**

Kubernetes gives you:
- Custom autoscaling (scale Celery by queue depth, not CPU)
- Multi-region deployments
- Hundreds of microservices with complex networking
- Zero-downtime rolling deploys at massive scale

What it costs you:
- 1 full-time DevOps/SRE engineer to operate it
- EKS (AWS managed K8s) control plane: $73/month just for the cluster manager
- Add 3× t3.medium worker nodes: +$112/month
- **Minimum K8s cost: ~$185/month before any workload**
- Steep learning curve, weeks to configure correctly

For TradeMentor at any realistic near-term scale:
- **0–2,000 users**: Railway (no ops overhead)
- **2,000–50,000 users**: AWS ECS Fargate (managed containers, autoscaling, no K8s complexity)
- **50,000+ users**: K8s makes sense if you have dedicated ops

**ECS Fargate (AWS, Mumbai region) for 10,000 users:**
```
3 tasks (API + worker + beat) × 0.5 vCPU / 1 GB each:
Estimate: ~$17/task/month × 3 = $51/month compute
+ ALB load balancer: ~$20/month
+ ECR (container registry): ~$1/month
Total ECS: ~$72/month
```

ECS Fargate autoscales automatically (add/remove tasks based on CPU/memory). You define min/max tasks in a JSON config. No K8s knowledge needed.

---

## 7. SUPABASE — CAN FREE TIER HANDLE IT? WHEN TO UPGRADE?

### Free Tier Reality Check

| Limit | Free Tier | Breaks At |
|-------|----------|-----------|
| Direct DB connections | 60 | ~40 concurrent users |
| PgBouncer (connection pooler) | ❌ Not available | — |
| Storage | 500 MB | ~200k trades + data |
| Bandwidth | 5 GB/month | ~300 active users |
| Project pausing | After 7 days inactivity | Dev/staging only |

**Free tier is only viable for development and testing. Never for production.**

### Upgrade Path

| Users | Supabase Tier | Monthly Cost | Connection Pooler? | Max Pooler Clients |
|-------|-------------|-------------|-------------------|-------------------|
| 0–100 | Free | $0 | ❌ | 60 direct |
| 100–2,000 | Pro | $25 | ✅ Port 6543 | 200 |
| 2,000–10,000 | Pro + Small compute | $25 + $10 = $35 | ✅ | 400 |
| 10,000–50,000 | Pro + Medium compute | $25 + $50 = $75 | ✅ | 600 |
| 50,000+ | Pro + Large or Enterprise | $25 + $100+ | ✅ | 800–1,200 |

**The $25/month Pro plan with free Nano compute gives you 200 pooler connections. This comfortably handles 5,000–8,000 registered users** with the SQLAlchemy AsyncConnectionPool fix in place.

### Is Supabase Scalable Long-Term?

**Yes, to about 50,000 users.** After that, large apps commonly migrate to:
- Self-hosted PostgreSQL on RDS (more raw performance, lower cost per connection)
- Neon (serverless Postgres, scales to zero, branching for dev)
- PlanetScale / CockroachDB (if you need horizontal sharding)

The migration is straightforward — Supabase is just PostgreSQL underneath. Your SQLAlchemy models work unchanged on any Postgres host. The only things you lose are Supabase Auth (you have your own JWT system anyway) and Supabase Realtime (you use Redis Streams, not Supabase Realtime).

**Verdict: Supabase Pro at $25/month is the right call from day one. Free tier is not for production.**

---

## 8. UPSTASH REDIS — COSTS AT SCALE

### Free Tier Reality

| Limit | Upstash Free |
|-------|-------------|
| Commands/day | 500,000 |
| Storage | 256 MB |
| Bandwidth | 10 GB/month |
| Max connections | 1 |

**500K commands/day sounds like a lot. It isn't.** At just 500 active users doing typical trading:
```
Margin cache writes: 500 × 5 trades/day × 1 write = 2,500/day
LTP cache reads/writes: 500 users × 5 positions × 3 ticks/sec × 22,500 sec = 168M operations

168M > 500K free limit by 336x
```

Even without KiteTicker LTP cache, event streams + locks + beat tasks will burn through 500K commands before 10am on a busy trading day with 200+ active users.

**Free tier: good for development only.**

### Pay-As-You-Go Pricing (Recommended for production)

| Commands | Cost |
|---------|------|
| Per 100K commands | $0.20 |
| Storage (per GB beyond 256MB) | $0.25/GB/month |

**Realistic monthly costs:**

| Users | Commands/month estimate | Storage | Monthly cost |
|-------|------------------------|---------|-------------|
| 100 | 5M | ~50 MB | ~$10 |
| 500 | 25M | ~150 MB | ~$50 |
| 1,000 | 50M | ~300 MB | ~$100 + $0.25 storage |
| 5,000 | 250M | ~700 MB | ~$500 + storage |
| 10,000 | 500M–1B | ~1.5 GB | ~$1,000–2,000 |

**The LTP cache is the main cost driver.** With the batched LTP write fix (1 MSET per second instead of 1 SET per tick), you reduce Redis commands by ~99% for price data:
```
Without fix: 10,000 users × 5 positions × 3 ticks/sec × 22,500 sec = 3.375B commands/month
With fix: 50 instruments × 1 MSET/sec × 22,500 sec/day × 30 days = 33.75M commands/month

Savings: 3.375B → 33.75M = 100x reduction
Monthly cost drops from $6,750 → $68 just for LTP
```

**With LTP batching fix: Upstash cost at 10,000 users ≈ $150–300/month.**
**Without the fix: $3,000–6,000/month on Redis alone.**

This is a **critical code fix, not an infrastructure upgrade**.

---

## 9. WHATSAPP ALERTS — THE COST THAT WILL SURPRISE YOU

This is the single largest cost at scale. Most founders don't model this until it's too late.

### Twilio WhatsApp Pricing (India destination, 2025)

Two fees stack on every message:
1. **Twilio fee**: $0.005/message (always)
2. **Meta conversation fee**: ~$0.004–0.006/conversation for India utility messages

**Total per WhatsApp message to India: ~$0.009–0.011**

### Rate Limits

| Scope | Limit |
|-------|-------|
| Single WhatsApp Business number | 1,000 conversations/day to start, scales to 10,000/day |
| After quality rating established | Up to 100,000 conversations/day |

### Monthly Cost Estimates

| Users with WhatsApp enabled | Alerts/user/day | Messages/month | Monthly cost (Twilio) |
|----------------------------|----------------|---------------|----------------------|
| 100 (all users) | 2 | 6,000 | $66 |
| 500 | 2 | 30,000 | $330 |
| 1,000 | 2 | 60,000 | $660 |
| 3,000 | 2 | 180,000 | $1,980 |
| 5,000 | 2 | 300,000 | $3,300 |
| 10,000 | 2 | 600,000 | $6,600 |

**WhatsApp is a premium feature. At 10k users it costs more than all your infrastructure combined.**

### How to Control WhatsApp Costs

**Strategy 1: Only send truly critical alerts** (danger severity, not caution)
- Reduces alerts from 2/day to ~0.3/day
- 10k users × 0.3 × 30 × $0.011 = **$990/month** (from $6,600)

**Strategy 2: Batch into daily digest** (already partially done with cooldowns)
- "Today's summary: 2 revenge trades, 3 caution alerts"
- 1 message/day instead of 3–5
- 10k users × 1 × 30 × $0.011 = **$3,300/month**

**Strategy 3: WhatsApp opt-in rate reality**
- In practice 30–50% of users actually connect WhatsApp
- Real addressable base at 10k: 3,000–5,000 users
- Cost naturally halves

**Strategy 4: Meta direct API (skip Twilio middleman)**
- Go directly to Meta's Cloud API (no Twilio fee)
- Only pay Meta's conversation fee: ~$0.006/message for India
- 10k users × 2 × 30 × $0.006 = **$3,600/month** (vs $6,600 via Twilio)
- More setup work, need a Business Solution Provider (BSP) or self-managed WABA
- Best BSPs for India: Gupshup (~$0.007/msg all-in), Wati (~$49/month + per-message)

**Strategy 5: Make WhatsApp a paid feature**
- Free tier: in-app notifications only (free)
- Premium tier: WhatsApp alerts (charge ₹199–499/month)
- This turns your cost center into a revenue driver

### FCM Push Notifications: Free at Any Scale

Firebase Cloud Messaging is genuinely **free with no message limit**. 10,000 users × 10 push notifications/day = 3 million pushes/month = **$0**.

Use FCM for all routine alerts and notifications. Reserve WhatsApp only for the highest-severity alerts that need guaranteed delivery (danger patterns, margin calls). This is already how it's architectured in the codebase — good design.

---

## 10. OPENROUTER / AI COSTS

### Per-Message Cost

| Model | Input/1M tokens | Output/1M tokens |
|-------|----------------|-----------------|
| Claude 3 Haiku | $0.25 | $1.25 |
| Claude 3.5 Haiku | $0.80 | $4.00 |
| Claude Haiku 4.5 | $1.00 | $5.00 |

### Monthly estimates (10 chat messages/day per user, 60% cache hit rate)

| Users | Model | Monthly AI Cost |
|-------|-------|----------------|
| 100 | Claude 3 Haiku | ~$5 |
| 1,000 | Claude 3 Haiku | ~$47 |
| 10,000 | Claude 3 Haiku | ~$465 |
| 10,000 | Claude Haiku 4.5 | ~$1,860 |

**Recommendation:** Use Claude 3 Haiku for high-volume endpoints (behavioral summaries, pattern descriptions, coach insight generation). Use Claude 3.5 Haiku only for interactive chat where quality matters. The 15-minute cache on coach insight (already in place) significantly reduces API calls.

AI costs are manageable. **This is not a concern until 5,000+ users.**

---

## 11. FULL COST BREAKDOWN AT EACH STAGE

### Stage 1: Launch / Beta (0–500 users)

| Service | Cost | Notes |
|---------|------|-------|
| Railway Hobby | $5–30/mo | 3 services (API + worker + beat) |
| Supabase Pro | $25/mo | Required for production |
| Upstash (pay-as-you-go) | ~$15–30/mo | With LTP batching fix |
| Twilio WhatsApp | ~$55–330/mo | 2 alerts/day, all users opted in |
| FCM Push | $0 | Free |
| OpenRouter (Claude 3 Haiku) | ~$5–25/mo | With caching |
| Domain + SSL | ~$15/mo | Let's Encrypt SSL is free |
| Sentry (free tier) | $0 | Up to 10k errors/month |
| **Total** | **~$120–425/mo** | |

**Realistic: ~$150–200/month at 500 users** (WhatsApp opt-in is rarely 100%)

---

### Stage 2: Growth (500–3,000 users)

| Service | Cost | Notes |
|---------|------|-------|
| Railway Pro | $20 + ~$80 usage = $100/mo | More vCPU for workers |
| Supabase Pro | $25/mo | Same tier, handles this range |
| Upstash | ~$50–150/mo | With LTP batching |
| Twilio WhatsApp | ~$330–2,000/mo | 2 alerts/day, 50% opt-in |
| FCM Push | $0 | |
| OpenRouter | ~$25–150/mo | |
| Sentry Team | $29/mo | |
| **Total** | **~$560–2,454/mo** | |

**WhatsApp already dominates costs at 1,000 users.**

---

### Stage 3: Scale (3,000–10,000 users)

| Service | Cost | Notes |
|---------|------|-------|
| AWS ECS Fargate (Mumbai) | ~$150–200/mo | API + 2 worker services, autoscaling |
| Supabase Pro + Small compute | $35/mo | 400 pooler connections |
| Upstash | ~$150–300/mo | With all optimizations |
| WhatsApp (Twilio) | ~$2,000–6,600/mo | **dominant cost** |
| WhatsApp (Meta direct / Gupshup) | ~$1,100–3,600/mo | **recommended instead** |
| FCM Push | $0 | |
| OpenRouter | ~$150–465/mo | |
| Sentry | $29/mo | |
| AWS ALB + misc | ~$25/mo | |
| **Total (Twilio)** | **~$2,539–7,659/mo** | |
| **Total (Meta direct)** | **~$1,639–4,659/mo** | |

---

### Cost Summary Table

| Users | Infra | Redis | WhatsApp (Twilio) | AI | **Total** |
|-------|-------|-------|------------------|----|-----------|
| 100 | $35 | $15 | $66 | $5 | **~$121/mo** |
| 500 | $55 | $30 | $330 | $25 | **~$440/mo** |
| 1,000 | $100 | $60 | $660 | $47 | **~$867/mo** |
| 3,000 | $150 | $120 | $1,980 | $140 | **~$2,390/mo** |
| 10,000 | $235 | $225 | $6,600 | $465 | **~$7,525/mo** |

**With Meta direct API and WhatsApp opt-in rate of 40%:**

| Users | **Realistic total** |
|-------|---------------------|
| 100 | ~$80/mo |
| 500 | ~$200/mo |
| 1,000 | ~$350/mo |
| 3,000 | ~$700/mo |
| 10,000 | ~$2,200/mo |

---

## 12. WHAT TO DO AND IN WHAT ORDER

### Right Now (Before Any Real Users)

**Cost: $0 extra. Time: 1 week.**

These are production readiness fixes (see `PRODUCTION_READINESS_AUDIT.md`):
1. React Error Boundary in App.tsx
2. JWT silent refresh in BrokerContext
3. Replace `detail=str(e)` with generic error messages
4. Celery retry exponential backoff
5. `asyncio.wait_for` timeout on WebSocket sends

**Also apply these 4-hour quick wins (scalability):**
1. `worker_concurrency=4` → `worker_concurrency=50` in celery_app.py
2. Run the 6 composite SQL indexes in Supabase dashboard
3. Parallelize beat tasks with asyncio.gather
4. Apply LTP batch write fix (reduces Redis cost 100x)

**Deploy to Railway Hobby ($5/month).** Connect Supabase Pro ($25/month). Total: $30/month.

---

### At First 100 Paying Users

**Switch Twilio sandbox → production WhatsApp Business Account.**
Apply for a WABA through Meta Business Manager. Free to set up. Approval takes 1–7 days.
Budget: ~$80–150/month total.

**Add Docker** (`Dockerfile` + `docker-compose.yml`) — 2 hours, permanent benefit.

---

### At 500 Users

**Upgrade Railway Hobby → Railway Pro** ($20/month).
Increase Celery worker service to 2 vCPU / 4GB RAM.

**Add Sentry Team** ($29/month) — you need real error tracking now.

**Decide on WhatsApp strategy:**
- Keep Twilio (simpler) and price WhatsApp as premium feature (₹299/month), or
- Migrate to Gupshup/Wati (cheaper per-message BSP), or
- Start Meta direct API integration

Budget: ~$250–350/month total.

---

### At 2,000–3,000 Users

**Migrate from Railway to AWS ECS Fargate** (or stay on Railway Pro — still works).
ECS gives you autoscaling (Celery workers scale up at 9:15am, down at 3:30pm).
Start with ECS if you want cost optimization; stay on Railway if you want simplicity.

**Upgrade Supabase Pro + Small compute add-on** ($35/month) for 400 pooler connections.

**Switch DATABASE_URL to Supabase Transaction Pooler** (port 6543, not 5432).
Update `database.py` to `AsyncConnectionPool` instead of `NullPool`.

**Add read replica** for analytics queries — Supabase supports this on Pro.

Budget: ~$600–900/month total.

---

### At 5,000–10,000 Users

**Implement SharedPriceStream** (requires Zerodha partnership or internal arrangement).
This is the architectural step you cannot skip — 10,000 KiteTicker connections is not viable.

**Multi-instance WebSocket** — 3 FastAPI instances behind ALB with sticky sessions.
Subscriptions sharded by `hash(account_id) % 3`.

**Upstash Pro or self-hosted Redis** on EC2 for cost predictability.

**Consider moving WhatsApp to Meta Cloud API directly** — saves ~45% per message.

Budget: ~$1,500–2,500/month (without WhatsApp) or ~$4,000–7,000/month (with Twilio WhatsApp).

---

## 13. THE SINGLE MOST IMPORTANT BUSINESS DECISION

**WhatsApp notifications will be your largest expense at scale. Bigger than all your infra combined.**

Your options in order of cost:

| Option | Cost at 10k users | Effort |
|--------|-----------------|--------|
| Twilio (current) | ~$6,600/mo | Already done |
| Meta direct / Gupshup BSP | ~$3,600/mo | 2 weeks dev |
| FCM push only (no WhatsApp) | $0 | Already done |
| Charge users for WhatsApp (₹299/mo) | Revenue | Product decision |
| WhatsApp for critical alerts only (1/week) | ~$440/mo | Config change |

**Recommended: Make WhatsApp a paid add-on feature from day one.** It is genuinely more valuable than push notifications (higher open rate, direct to their phone number traders actually watch). Charge ₹199–499/month for it. At 1,000 users paying ₹299/month for WhatsApp: ₹2.99 lakh/month revenue covering all your infra costs.

---

## 14. SUMMARY: THE PRACTICAL PLAN

```
Today         → Fix production readiness (1 week) + quick wins (4 hours)
                Deploy to Railway Hobby: $30/month total
                Comfortable capacity: 1,500–8,000 registered users

First revenue  → Railway Pro + Supabase Pro: $60/month total
users          → Apply for WhatsApp Business Account (free)
                Capacity: 3,000–5,000 users

500 users      → Add Docker, Sentry, upgrade Railway: $150/month
                Make WhatsApp a paid feature (₹299/mo)
                Capacity: 5,000–8,000 users

2,000 users    → Switch to AsyncConnectionPool + port 6543
                Supabase Pro + Small compute: $35/month
                Budget: $300–400/month
                Capacity: 8,000–12,000 users

5,000 users    → Migrate to ECS Fargate, implement SharedPriceStream
                Multi-instance WebSocket
                Budget: $800–1,200/month (excl. WhatsApp)

10,000 users   → Full distributed architecture
                Meta direct WhatsApp API
                Budget: $2,000–2,500/month (excl. WhatsApp)

No Kubernetes until 50,000+ users.
No AWS until 2,000+ users (Railway handles it fine until then).
```
