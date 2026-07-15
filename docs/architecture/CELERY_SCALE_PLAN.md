# Celery Workers & Notification Scale Plan
*Written: 2026-06-15. Based on full task audit.*

---

## Current State (what we have)

### Worker config
```
worker_concurrency = 4          # 4 prefork OS processes per dyno
worker_prefetch_multiplier = 1  # one task at a time per worker
2 named queues: trades, alerts
1 Beat process (separate)
12 task modules registered
```

### Task modules
| Module | Type | Notes |
|---|---|---|
| `trade_tasks` | event-driven | webhook → process → detect → alert |
| `alert_tasks` | event-driven | fires after behavior detection |
| `position_monitor_tasks` | event-driven | per fill, self-reschedules for holding_loser |
| `portfolio_sync_tasks` | on-demand | cache miss only, Redis lock |
| `checkpoint_tasks` | event-driven | |
| `reconciliation_tasks` | beat (4 AM daily) | loops all accounts |
| `report_tasks` | beat (daily/weekly) | commodity EOD, weekly summary |
| `retention_tasks` | beat (every 60s) | **APScheduler-based — bug (see below)** |
| `guardrail_tasks` | beat (every 60s) | **loops ALL accounts serially** |
| `intent_tasks` | beat (3× daily) | **loops ALL accounts serially** |
| `portfolio_radar_tasks` | event-driven | after behavior detection |
| `market_data_tasks` | beat (8:45 AM daily) | MD token refresh, no-op if unconfigured |

---

## The Core Problem: Serial Fan-Out in Beat Tasks

These beat tasks loop ALL connected accounts inside a single Celery task:

| Task | When | Problem at scale |
|---|---|---|
| `check_guardrail_rules` | every 60s market hours | At 10k users: takes >60s → overlaps with next firing → queue accumulates |
| `dispatch_reports_tick` | every 60s | Same — loops all accounts to check whose report time matches |
| `send_morning_intent_push` | 8:30 AM daily | 10k push notifications sent serially in one task |
| `send_eod_comparison_push` | 3:35 PM daily | Same |
| `send_daily_score_push` | 6:00 PM daily | Same |
| `eod_sync_all_accounts` | 3:35 PM daily | 10k Zerodha API calls + 5/min rate limit = 2000 minutes |

### What happens with the wrong pattern
```python
# CURRENT (breaks at scale)
@celery_app.task
def send_daily_score_push():
    for account in fetch_all_accounts():   # 10,000 accounts
        send_push(account)                  # serial — 10k iterations in one task
        send_whatsapp(account)             # Gupshup rate limit stalls entire task
    # one task runs for minutes
    # Beat fires again before it finishes
    # tasks stack up in queue
```

### The correct pattern (coordinator + batch sub-tasks)
```python
# CORRECT (scales to 100k+)
@celery_app.task
def send_daily_score_push():
    account_ids = fetch_all_active_account_ids()  # just IDs, fast DB query
    for batch in chunked(account_ids, 100):
        send_daily_score_batch.delay(batch)       # fire and forget into queue

@celery_app.task
def send_daily_score_batch(account_ids: list[str]):
    accounts = fetch_accounts(account_ids)
    push_tokens = [a.push_token for a in accounts if a.push_token]
    gupshup_numbers = [a.phone for a in accounts if a.guardian_phone]

    if push_tokens:
        fcm_batch_send(push_tokens, title, body)       # 1 HTTP call → 100 pushes
    if gupshup_numbers:
        gupshup_batch_send(gupshup_numbers, ...)       # batch WA messages
```

100 batches × 4 concurrent workers = fan-out in seconds, not minutes.

---

## The APScheduler Bug in retention_tasks

`backend/app/tasks/retention_tasks.py` imports and starts `AsyncIOScheduler` from APScheduler.
This runs inside the **FastAPI process** (not a Celery worker), blocking the async event loop
and making it impossible to scale the scheduler independently.

Beat schedule already has `retention-reports-tick` → this creates two scheduling systems
running in parallel and potentially double-firing retention reports.

**Fix (when doing the fan-out refactor):** Remove APScheduler entirely. Move all retention
scheduling to Celery beat. The beat entry already exists — just make the task implementation
use the Celery worker pool, not the APScheduler.

---

## Scale Analysis

### 100 users — current setup is fine
- 4 workers handle concurrent fills comfortably
- Beat tasks loop 100 accounts in < 1s each
- EOD sync (5/min limit): 100 accounts = 20 minutes — tight but OK
- No changes needed now

### 1,000 users — starts breaking
| Issue | Impact |
|---|---|
| `check_guardrails` every 60s | Starts overlapping — queue accumulates |
| EOD sync 5/min rate limit | 1000 accounts = 200 min processing → runs to 7 PM |
| Intent push tasks (morning/EOD/score) | Serial loop is slow — last users get push minutes late |
| 4 workers | During 9:15–15:30 with concurrent fills → queue backs up |

**Fix needed before 1,000 users:** Fan-out refactor + concurrency env var + split worker dynos.

### 10,000 users — broken
| Issue | Impact |
|---|---|
| `check_guardrails` every 60s | Task takes many minutes. Dozens of instances overlap. DB hammered. |
| EOD sync | 10k × 5/min = 2,000 minutes. Unusable. |
| All fan-out beat tasks | Serial loops run for hours. Beat fires again and again. Tasks pile up. |
| 4 workers | Wholly insufficient. Needs 20–50 concurrent workers minimum. |

---

## Push Notifications: VAPID vs FCM

### What we use now: VAPID (Web Push)
- Works only in browsers that have visited the site at least once
- Sends one HTTP request per notification (no batching)
- No iOS Safari support (limited)
- Delivery not guaranteed — if browser is closed too long, push expires
- We manage our own VAPID keys (already set in `.env`)

### What large apps use: Firebase Cloud Messaging (FCM)
- Free for unlimited messages
- Batch API: 500 notifications in 1 HTTP call (vs 1 call per notification with VAPID)
- Works on iOS, Android, web browser
- Google manages delivery, retry, queuing
- Platform: `https://firebase.google.com` → no cost

### Migration impact
VAPID → FCM requires:
1. Firebase project + service account key (your part — see below)
2. Frontend: replace `pushManager.subscribe()` with Firebase SDK `getToken()`
3. Backend: replace `pywebpush` calls with `firebase-admin` SDK batch calls
4. Existing VAPID tokens become invalid — users re-subscribe on next visit

For us: FCM is better in every dimension. Do this before 500 users.

---

## How to Increase Celery Workers

### Option 1: Concurrency env var (do now, takes 2 minutes)
In `celery_app.py` line 72, change:
```python
worker_concurrency=4,
```
to:
```python
worker_concurrency=int(os.getenv("CELERY_CONCURRENCY", "4")),
```
Then set `CELERY_CONCURRENCY=8` in Render dashboard. No deploy needed.

### Option 2: Gevent pool (best for our I/O-heavy tasks)
Our tasks are mostly I/O (DB, Redis, API calls). Gevent uses async green threads instead of
OS processes — same memory, 10–25× more concurrency:
```bash
celery -A app.core.celery_app worker --pool=gevent --concurrency=50
```
50 concurrent I/O tasks on one dyno vs 4 with prefork.
Requires: `pip install gevent` (add to requirements.txt).

### Option 3: Split queues into separate worker dynos (Render)
```yaml
# render.yaml (when ready to add second dyno)
services:
  - type: worker
    name: worker-trades
    startCommand: celery -A app.core.celery_app worker -Q trades,celery --pool=gevent --concurrency=50
    
  - type: worker
    name: worker-alerts  
    startCommand: celery -A app.core.celery_app worker -Q alerts --pool=gevent --concurrency=50
    
  - type: worker
    name: celery-beat
    startCommand: celery -A app.core.celery_app beat -S redbeat.RedBeatScheduler
```

Trade processing and alert delivery no longer compete for the same workers.

---

## Does Celery Work at Production Scale?

Yes. Large production users of Celery:
- **Instagram** — Django + Celery + RabbitMQ (before migrating parts to custom infra)
- **Pinterest** — Celery at millions of tasks/day
- **Robinhood** — Celery for trade processing pipelines
- **Coursera** — Celery for content processing
- **Zapier** — Celery for workflow automation

The tool is not the problem. The **pattern** inside the tasks is the problem.
Celery + Redis handles 100k users comfortably if fan-out is done correctly.

At 10M+ users Zerodha/NSE-scale: custom Kafka consumers, but that is not our problem yet.

---

## Alternatives to Celery (for reference, not switching now)

| Tool | Best for | Why not now |
|---|---|---|
| **Celery + RabbitMQ** | >50k users, need durability guarantees | More infra ops overhead |
| **ARQ** | Async-native Python, simple | No beat equivalent, immature |
| **Dramatiq** | Simpler config than Celery | Smaller ecosystem |
| **Temporal** | Google/Netflix-scale complex workflows | Heavy infra, steep learning curve |

Stick with Celery + Redis until 50k users. Fix the fan-out pattern first.

---

## Implementation Roadmap

### Before 500 users (your part first — see below)
- [ ] FCM project setup (Firebase Console)
- [ ] `CELERY_CONCURRENCY` env var in Render

### Before 1,000 users (code changes)
- [ ] Make `worker_concurrency` read from env var
- [ ] Add `gevent` to `requirements.txt`, switch to gevent pool
- [ ] Refactor all fan-out beat tasks to coordinator + batch sub-task pattern:
  - `send_morning_intent_push`
  - `send_eod_comparison_push`
  - `send_daily_score_push`
  - `check_guardrail_rules`
  - `dispatch_reports_tick`
  - `eod_sync_all_accounts`
- [ ] Remove APScheduler from `retention_tasks.py`, consolidate to Celery beat
- [ ] Fix EOD sync: dispatch one task per account, let Celery annotation enforce rate limit
- [ ] Migrate push from VAPID to FCM batch API

### Before 10,000 users (infra changes)
- [ ] Split trades/alerts into separate worker dynos (render.yaml)
- [ ] Guardrail scan: filter to only accounts with active rules (not all connected)
- [ ] Consider Celery + RabbitMQ if Redis message loss becomes a concern
- [ ] DB read replica for analytics queries (don't block write path)

---

## YOUR ACTION ITEMS (do these now)

### Step 1: Set CELERY_CONCURRENCY in Render (5 min)
1. Go to Render dashboard → your worker service
2. Environment → Add env var: `CELERY_CONCURRENCY` = `8`
3. Redeploy worker
4. Done. Workers go from 4 → 8 with no code change.

### Step 2: Set up Firebase project for FCM (20 min)
1. Go to `https://console.firebase.google.com`
2. Create project → name it `tradementor-prod`
3. Skip Google Analytics (not needed)
4. In project: Settings (gear icon) → Project Settings → Service Accounts tab
5. Click "Generate new private key" → downloads a JSON file
6. Rename the JSON to `firebase-service-account.json`
7. Put it in `backend/` folder (add to `.gitignore` — never commit this)
8. Also go to: Project Settings → General → Your apps → Add app → Web
9. Copy the `firebaseConfig` object shown (you'll need this for frontend)
10. Tell me you've done this — I'll do the code integration

### Step 3: Add Firebase to .gitignore (2 min)
Add this line to your `.gitignore` (root):
```
backend/firebase-service-account.json
```

### Step 4: Tell me when steps 1–3 are done
I'll then:
- Add `firebase-admin` to `requirements.txt`
- Replace VAPID push calls with FCM batch API (backend)
- Replace `pushManager.subscribe()` with Firebase SDK `getToken()` (frontend)
- Update service worker for FCM

---

## Files changed in this analysis session (2026-06-15)

### Bugs fixed
- `backend/app/api/websocket.py` — removed stale `manager.subscriptions.setdefault()` call (AttributeError on every WS connect)
- `src/components/dashboard/OpenPositionsTable.tsx` — removed `isConnected` reference (was undefined after WebSocket price removal)

### Architecture changes (from previous session)
- `price_stream_service.py` — `on_tick_callback=None` in SharedPriceStream (ticks to Redis LTP only, no redistribution)
- `websocket.py` — removed `broadcast_price`, subscription tracking; `notify_price_update` is a no-op stub
- `WebSocketContext.tsx` — removed prices state, price buffer, subscribe function
- `OpenPositionsTable.tsx` — P&L uses `p.last_price` from positions API (not WebSocket)
- `Dashboard.tsx` — `unrealizedTotal` uses `p.last_price` from position data
