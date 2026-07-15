# TradeMentor AI — Launch TODO
*Last updated: 2026-06-15. Compiled from all session notes, memory, and working notes.*

---

## LEGEND
- 🧑 = YOUR task (you do it manually — account setup, dashboard config, etc.)
- 💻 = MY task (code change — tell me when to do it)
- ⛔ = BLOCKED (cannot proceed until dependency resolved)
- ✅ = DONE

---

## PART 1: YOUR ACTION ITEMS (do these yourself)

### 1A. Render Worker Scaling (5 min, do now)
```
1. Log into Render dashboard
2. Go to your worker service
3. Environment → Add variable:
   CELERY_CONCURRENCY = 8
4. Redeploy worker
```
No code change needed. Workers go from 4 → 8 concurrently.

---

### 1B. Firebase / FCM Setup (20 min, do now)
Push notifications currently use VAPID (browser-only, no batching, no iOS).
FCM is free and handles batching natively. Required before we have 500 users.

```
Step 1: Go to https://console.firebase.google.com
Step 2: Create project → name: tradementor-prod → skip Google Analytics
Step 3: Settings (gear icon) → Project Settings → Service Accounts tab
Step 4: Click "Generate new private key" → downloads a JSON file
Step 5: Rename it firebase-service-account.json
Step 6: Move it into the backend/ folder
Step 7: Settings → General → Your apps → Add app → Web (the </> icon)
Step 8: Copy the firebaseConfig object shown — paste it somewhere safe
        It looks like:
        {
          apiKey: "...",
          authDomain: "...",
          projectId: "...",
          messagingSenderId: "...",
          appId: "..."
        }
Step 9: Tell me you're done → I'll do all the code integration
```

---

### 1C. Add to .gitignore (2 min, do with 1B)
Add this line to your root `.gitignore`:
```
backend/firebase-service-account.json
```
Never commit that file — it's a service account credential.

---

### 1D. WhatsApp / Gupshup Setup ⛔ BLOCKED ON META
All code is ready (see `docs/WHATSAPP_GUPSHUP_MIGRATION.md` for full guide).
Blocked until Meta approves the Business Manager account + templates.

```
Your pending steps:
1. Create Meta Business Manager account (business.facebook.com)
2. Submit for Business Verification (takes 1–5 business days)
3. Create Gupshup account, connect WhatsApp number via Embedded Signup
4. Submit 3 templates for approval:
   - tradementor_report
   - tradementor_alert
   - tradementor_guardian
5. Once approved → tell me → I wire up Day 2 code in 1 session
```
Full step-by-step in `docs/WHATSAPP_GUPSHUP_MIGRATION.md` parts 1–3.

---

### 1E. Admin Panel Activation (10 min — do before launch)
Admin panel code is complete. Need env var + first user in DB.

```
Step 1: Add to backend .env on Render:
   ADMIN_JWT_SECRET = <any long random string, min 32 chars>
   Example: openssl rand -hex 32

Step 2: Add SMTP vars for admin OTP emails (also in Render env):
   SMTP_HOST = smtp.gmail.com (or your SMTP)
   SMTP_PORT = 587
   SMTP_USER = your@email.com
   SMTP_PASS = your-app-password
   EMAIL_FROM = noreply@tradementor.ai

Step 3: Run the seed script to create first admin user:
   cd backend
   python scripts/seed_admin.py

Step 4: Log in at /admin with seeded credentials
Step 5: Change password immediately after first login
```

---

### 1F. Design Review — design_v2/ Prototypes (need your decision)
Four HTML prototypes are in `design_v2/`:
- `landing.html` — marketing/landing page
- `dashboard.html` — main trading view
- `analytics.html` — 8-tab analytics
- `blowup-shield.html` — risk/shield view

```
Step 1: Open each file in Chrome (just double-click the .html file)
Step 2: Review on both dark (default) and light (toggle in top-right)
Step 3: Check at mobile width (DevTools → 390px iPhone)
Step 4: Tell me what you want changed OR say "approved, port to React"
```
Nothing from design_v2/ touches the real app until you explicitly say "port this."

---

### 1G. BehaviorEngine Validation Scripts (do after real users start trading)
10 test trade scripts exist to validate all 22 behavioral patterns fire correctly.
These must be run MANUALLY by you, one at a time, while watching logs.

```
When ready:
1. Tell me → I'll prepare the 10 scripts
2. You run Script 1, wait, check dashboard/logs
3. Repeat for each script
4. Run cleanup: DELETE FROM trades WHERE tag = 'TEST_SCENARIO'
```

---

## PART 2: CODE TASKS (I do these — tell me when)

### Priority: BEFORE 500 USERS

#### 2A. FCM Integration (after you do 1B + 1C)
- Add `firebase-admin` to `requirements.txt`
- Replace `pywebpush` calls with FCM batch API (`firebase_admin.messaging.send_multicast`)
- Replace `pushManager.subscribe()` in frontend with Firebase SDK `getToken()`
- Update `public/sw.js` service worker for FCM message handling
- Migrate existing VAPID tokens — users re-subscribe on next visit (one-time churn)

#### 2B. Worker Concurrency from Env Var (small, can do anytime)
Change `celery_app.py` line 72:
```python
worker_concurrency=4,  # current
# →
worker_concurrency=int(os.getenv("CELERY_CONCURRENCY", "4")),
```
Lets you scale workers from Render dashboard without code deploy.

#### 2C. Gevent Pool for Celery Workers
Add `gevent` to `requirements.txt`.
Change worker start command to:
```bash
celery -A app.core.celery_app worker --pool=gevent --concurrency=50
```
Our tasks are I/O-heavy (DB, Redis, API calls). Gevent = 50 concurrent vs 4 with prefork.
Same memory cost, 10× throughput.

---

### Priority: BEFORE 1,000 USERS

#### 2D. Celery Fan-Out Refactor (biggest scaling fix)
All beat tasks that loop users need coordinator + batch sub-task pattern:
- `send_morning_intent_push` → dispatch 1 sub-task per 100-user batch
- `send_eod_comparison_push` → same
- `send_daily_score_push` → same
- `check_guardrail_rules` → only query accounts WITH active rules, then batch
- `dispatch_reports_tick` → already dispatches but verify it's per-user not serial
- `eod_sync_all_accounts` → dispatch 1 task per account, let Celery rate limit handle it

#### 2E. Remove APScheduler from retention_tasks.py
`retention_tasks.py` uses `AsyncIOScheduler` from APScheduler running inside FastAPI process.
This blocks the async event loop and can't be scaled independently.
Fix: remove APScheduler, ensure everything goes through Celery beat (entry already exists).

#### 2F. EOD Sync Rate Limit Fix
Current: `eod_sync_all_accounts` loops 1000 users serially + Celery annotation does nothing
(annotation only works per-task, not inside a loop).
Fix: dispatch `sync_trades_for_account.delay(account_id)` per account.
Celery `rate_limit="5/m"` annotation then actually enforces 5/min.

#### 2G. Split Worker Dynos on Render
Create `render.yaml` with separate services for trades queue, alerts queue, and beat.
Currently all share one worker dyno — high-priority trade processing competes with
low-priority report sending.

---

### Priority: BEFORE 10,000 USERS

#### 2H. Phase 4 Redis Streams — XREADGROUP Consumer Groups
`event_bus.py` uses basic XREAD. At 50+ users, need XREADGROUP for:
- Guaranteed delivery (messages not lost if worker crashes)
- Multiple consumer group instances (horizontal scaling)
- XACK-based acknowledgement so events aren't reprocessed
Trigger: when Sentry shows "max clients reached" or replay reliability issues.

#### 2I. Guardrail Scan Bucketing
`check_guardrail_rules` every 60s currently queries all connected accounts.
At 10k users: needs user-shard bucketing OR filter to only accounts with active rules.

#### 2J. DB Read Replica
Analytics queries (SummaryTab, patterns, edge map, journal) compete with trade write path.
At 5k+ users: add Supabase read replica for analytics routes.

---

## PART 3: PRODUCT FEATURES NOT YET BUILT

### P1 — Must have at launch

#### WhatsApp Day 2 Code ⛔ BLOCKED ON META
Full spec in `docs/WHATSAPP_GUPSHUP_MIGRATION.md` sections 6.1–6.4.
When Meta approves templates → 1 session to wire everything up.

#### Razorpay Payments ⛔ NOT STARTED
Free → Pro upgrade flow. Nothing built yet.
```
Your steps first:
1. Create Razorpay account (razorpay.com)
2. Get API Key ID and API Key Secret (Test mode first)
3. Tell me → I'll build checkout flow, webhook handler, plan gating
```

#### Morning Intent Push — Dynamic Personalization
Current push is same template for all users. Should vary based on:
- Recent streak (3 green days vs just blew up yesterday)
- Pattern-specific nudge ("Your last 3 Fridays had revenge trades")
- Whether user hit limit yesterday
Need your input on what "dynamic" means to you before I build.
See `docs/architecture/CELERY_SCALE_PLAN.md` for context.

---

### P2 — Nice to have before launch

#### Deep OTM Lottery Detection (Pattern G7) ⛔ BLOCKED
Needs spot price at time of trade entry to detect "buying ₹5 lottery tickets."
Currently we don't store spot price at trade time.
Options: (a) store from webhook payload, (b) look up from instruments table at trade time.
Deferred until webhook payload is confirmed to include spot reference.

#### Strategy Pivot Confusion Analytics (G8)
Analytics showing when a trader switches strategies mid-session.
Requires `strategy_detector.py` integration with analytics pipeline.
Not urgent — a "nice to know" pattern.

---

## PART 4: TECHNICAL DEBT / CLEANUP (low priority, do before major refactor)

| Item | File | Action |
|---|---|---|
| Dead code: `usePriceStream.ts` | `src/hooks/usePriceStream.ts` | Not imported anywhere. Can delete. |
| Legacy: `PerUserPriceStream` | `price_stream_service.py` | Kept for rollback. Delete once SharedPriceStream stable for 30 days. |
| Stale: `monitor_open_positions` | `position_monitor_tasks.py` | Legacy beat task kept "for reference." Delete it. |
| Unused: `PredictiveContextStrip.tsx` | `src/components/dashboard/` | Removed from Dashboard but file kept (archive rule). OK to leave. |
| Stale docstring | `price_stream_service.py:1-40` | Still mentions `broadcast_price()` and fan-out. Update to reflect current architecture. |
| `portfolio_radar_tasks` | Beat schedule | Runs every 5 min (300s). Archived page `/portfolio-radar` but task still runs. Disable beat entry if radar page is archived. |

---

## PART 5: KNOWN BUGS / ISSUES

| Bug | Status | Notes |
|---|---|---|
| `websocket.py` — `manager.subscriptions` AttributeError | ✅ FIXED (2026-06-15) | Stale `subscriptions` reference removed |
| `OpenPositionsTable.tsx` — `isConnected` ReferenceError | ✅ FIXED (2026-06-15) | Live badge removed; `isConnected` was undefined |
| NSE data redistribution via WebSocket | ✅ FIXED (2026-06-15) | `on_tick_callback=None`, broadcast removed |
| `UserProfile.user_id` FK missing | Open | FK from user_profiles to users table missing. Needed for multi-account. Deferred. |
| `margin_risk` pattern unimplemented | Open | Needs live Kite margin API call at detection time. Intentionally skipped. |

---

## PART 6: INFRASTRUCTURE CHECKLIST (before going public)

```
[ ] ADMIN_JWT_SECRET set in Render env         (see 1E above)
[ ] SMTP configured for admin OTP              (see 1E above)
[ ] CELERY_CONCURRENCY = 8 in Render env       (see 1A above)
[ ] ZERODHA_API_KEY set in Render env          (needed for KiteTicker)
[ ] ENCRYPTION_KEY set in Render env           (Fernet — NEVER lose this)
[ ] SENTRY_DSN set (for error monitoring)
[ ] Supabase migrations 035–060 all applied    (confirmed applied)
[ ] Next migration to create: 061
[ ] VAPID keys set in backend .env             (confirmed set 2026-06-12)
[ ] Upstash Redis URL configured (rediss://)   (confirmed working)
[ ] Push notifications working end-to-end test
[ ] Admin panel login test after seed
[ ] Zerodha webhook URL configured in Kite Connect dashboard
    → POST https://your-backend.onrender.com/api/webhooks/zerodha/postback
```

---

## PART 7: LAUNCH SEQUENCE (suggested order)

```
Week 1 (do now):
  🧑 1A — Render CELERY_CONCURRENCY=8
  🧑 1B + 1C — Firebase project + .gitignore
  💻 2B — worker_concurrency from env var (tiny change)
  🧑 1E — Admin panel activation

Week 2:
  🧑 1F — Review design_v2/ prototypes, give feedback
  💻 2A — FCM integration (after 1B done)
  🧑 1D — WhatsApp Meta BM submission (start the clock on approval wait)

Week 3–4:
  💻 Design porting (React, one page at a time, after 1F approval)
  🧑 Razorpay account creation
  💻 Razorpay payment integration

Week 5+ (scale prep):
  💻 2C — Gevent pool
  💻 2D — Celery fan-out refactor
  💻 2E — APScheduler removal
  💻 2F — EOD sync fix
```
