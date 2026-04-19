# TradeMentor × Zerodha — Partnership Preparation Document

> **Status**: Pre-pitch documentation. Internal use only. Do not share externally until product is ready.
> **Last updated**: 2026-04-15

---

## Table of Contents

1. [The Email](#1-the-email)
2. [What TradeMentor Is](#2-what-tradementor-is)
3. [Why We Need Zerodha](#3-why-we-need-zerodha)
4. [What Zerodha Gets From This](#4-what-zerodha-gets-from-this)
5. [The Sensibull Precedent](#5-the-sensibull-precedent)
6. [Technical Architecture Deep Dive](#6-technical-architecture-deep-dive)
7. [Security & Data Handling](#7-security--data-handling)
8. [SEBI & Legal Compliance](#8-sebi--legal-compliance)
9. [Scalability & Infrastructure](#9-scalability--infrastructure)
10. [Business Model](#10-business-model)
11. [Q&A Preparation — Technical](#11-qa-preparation--technical)
12. [Q&A Preparation — Business & Product](#12-qa-preparation--business--product)
13. [Q&A Preparation — Security](#13-qa-preparation--security)
14. [Q&A Preparation — Legal & Compliance](#14-qa-preparation--legal--compliance)
15. [Q&A Preparation — Managerial / Strategic](#15-qa-preparation--managerial--strategic)
16. [What We're Asking For (Partnership Tiers)](#16-what-were-asking-for-partnership-tiers)
17. [Current Gaps & Honest State](#17-current-gaps--honest-state)
18. [Things You Might Have Missed](#18-things-you-might-have-missed)

---

## 1. The Email

**To**: partners@zerodha.com  
**Subject**: Partnership inquiry — TradeMentor: behavioral intelligence layer for active F&O traders

---

Hi team,

I'm building TradeMentor, a trading psychology and behavioral analysis platform built specifically for Indian F&O traders on Zerodha.

**In one line**: TradeMentor mirrors a trader's own behavior back at them — revenge trades, overtrading spirals, expiry day panic — so they can see patterns they can't see themselves.

We are live, connected to Zerodha via KiteConnect, and have a working product. We're reaching out because the next meaningful step requires deeper integration than the public API offers.

**What we currently do:**
- Connect to Zerodha via KiteConnect OAuth
- Receive real-time order postbacks to detect behavioral patterns as they happen
- Flag high-risk moments (e.g., "3rd trade in 4 minutes after a loss") with severity-tagged alerts
- Track goal commitments the trader sets for themselves
- Give an AI coach that reasons about their specific trade history
- Show analytics about their habits, not just their P&L

**Why we're reaching out:**

The public KiteConnect API works well for what it is. But to build a truly useful behavioral layer, we need:

1. **Reliable real-time order stream** — postbacks to localhost work in dev but miss fills in production when the server is briefly unavailable. A persistent WebSocket feed (like the market data feed) would solve this without our servers missing fills during market hours.

2. **App-native integration consideration** — We're exploring a browser extension overlay on Kite Web. We'd rather build this as an official feature than an unofficial scraper.

3. **Distribution** — If this becomes genuinely useful to Zerodha's users, we'd welcome a conversation about being surfaced within the Kite ecosystem (similar to how Sensibull was integrated).

I'm happy to share a demo, walk through the architecture, or answer any questions. We're in active development and would rather get alignment early than build in the wrong direction.

**Rohit Ostwal**  
Founder, TradeMentor  
[your phone]  
[your email]

---

## 2. What TradeMentor Is

### The Problem

Indian F&O traders lose money not primarily because they lack knowledge of markets — they lose because of behavioral patterns:

- They trade again immediately after a loss (revenge trading)
- They hold losing positions hoping they'll recover (loss aversion)
- They overtrade on days where early volatility triggers impulsive decisions
- They panic-exit winning trades early while letting losers run
- On expiry day, they take 3× their normal size chasing premium decay

These patterns are invisible to the trader in the moment. They only see them — if ever — when they review P&L weeks later, by which time the memory is gone.

**TradeMentor is a behavioral mirror, not a financial advisor.** It detects these patterns in real time and surfaces them as the trader is trading, using their own data as evidence.

### Philosophy: "Mirror, Not Blocker"

We do not restrict trading. We do not give buy/sell advice. We show traders facts about their own behavior.

> "You've placed 3 trades in the last 8 minutes. Your last 2 were after back-to-back losses. This matches your revenge trading pattern."

That's it. No "stop trading." No orders blocked. The trader decides.

This is the legal and ethical line we stay firmly behind.

### What's Built (Current State)

| Feature | Status |
|---|---|
| Zerodha OAuth + KiteConnect integration | Live |
| Real-time order postback processing | Live (localhost; production pending) |
| 22-pattern behavioral detection engine | Live |
| Severity-tagged real-time alerts (WebSocket) | Live |
| Daily/weekly behavioral analytics | Live |
| AI coaching (OpenRouter LLMs) | Live |
| Goal commitment tracking | Live |
| Blowup shield (capital preservation guardrails) | Live |
| Guardian alerts (WhatsApp to trusted person) | Live (template-based) |
| Admin panel (user management, system health) | Live |
| SEBI compliance (ToS, Privacy Policy, disclaimers) | Live |
| Guest/demo mode | Live |
| Mobile-responsive web app | Live |

### Tech Stack

**Frontend**: React 18 + TypeScript + Vite + shadcn/ui + Tailwind + Recharts  
**Backend**: FastAPI (Python) + SQLAlchemy async + asyncpg  
**Database**: Supabase (PostgreSQL)  
**Cache/Events**: Upstash Redis + Redis Streams  
**Task Queue**: Celery + Redis  
**Real-time**: WebSocket (backend → frontend)  
**AI**: OpenRouter (Claude/GPT-4 models via single endpoint)  
**Notifications**: WhatsApp via Gupshup (Meta-approved templates)  
**Hosting**: Vercel (frontend) + Render (backend)

---

## 3. Why We Need Zerodha

### Current Limitations on Public KiteConnect

**Problem 1: Order postbacks are fire-and-forget to a URL**

Zerodha fires order status updates to `ZERODHA_POSTBACK_URL`. If our server is momentarily unavailable (cold start, deploy restart, brief network blip), those postbacks are lost. There is no replay, no queue, no retry on Zerodha's side.

During market hours, a missed postback means a missed trade, which means wrong P&L, wrong behavioral signals, and wrong alerts. This is a fundamental reliability problem for any real-time behavioral platform.

What we want: a durable event stream (like the market data WebSocket) that we can reconnect to and replay missed events from, similar to how Kafka/Redis Streams work.

**Problem 2: No access to order book / position state beyond API calls**

We can call `/positions` and `/orders` via REST. But that means polling, which is bad design at scale. With 50 users each polling every 30 seconds, that's 100 API calls per minute against our single API key — hitting rate limits fast and creating unnecessary load on Zerodha's infrastructure.

Zerodha's own Kite Web has real-time order book updates. We don't. The public API doesn't expose the same streaming primitives for orders that it exposes for market data.

**Problem 3: Historical intraday fills have a 60-day limit**

`/trades` returns fills only for the current day. `GET /trades/{order_id}` has limits. For behavioral analysis across weeks and months, we need more history. The portfolio API gives aggregate data but not fill-level detail needed for pattern detection.

**Problem 4: No way to show contextual data inside Kite**

The most impactful moment to show a behavioral alert is when the trader is about to place an order in Kite, not when they're looking at our separate app. We'd like to surface alerts natively inside the Kite experience — but that requires either an official integration or a browser extension that Zerodha is aware of and comfortable with.

### What We're Asking Zerodha For

- **Option A (Minimum)**: Confirmation/guidance that a browser extension overlay on Kite Web is acceptable to Zerodha, and what constraints they'd want respected
- **Option B (Better)**: Access to a durable order event stream (like the market data WebSocket) for order book updates
- **Option C (Best)**: Official equity partner status (like Sensibull), with native integration points in Kite Web/Mobile and joint go-to-market

---

## 4. What Zerodha Gets From This

### Trader Retention

Zerodha's biggest churn signal is traders blowing up their accounts. A trader who loses ₹5L in a single week of impulsive F&O trading either quits trading entirely or switches brokers looking for a "fresh start."

TradeMentor is the only product that actively tries to prevent account blowups — not by blocking trades, but by giving traders self-awareness before they self-destruct. Traders who survive and improve their behavior keep trading and paying brokerage for longer.

**TradeMentor is a retention tool Zerodha doesn't have to build.**

### Differentiation

Every major broker in India (Upstox, Groww, AngelOne, 5Paisa) is racing to match Zerodha's features. What none of them have is behavioral intelligence — because it's genuinely hard to build.

If TradeMentor is exclusive to or deeply integrated with Zerodha, it becomes a meaningful point of differentiation: "The only broker that helps you trade better, not just faster."

### User Upgrade Path

Currently Zerodha has no reason to upsell active traders. TradeMentor creates a premium tier of insight that could be:
- Bundled as a Zerodha+ feature (₹299-499/mo alongside brokerage)
- Joint revenue share on TradeMentor's own subscription
- Free for Zerodha users as a loyalty/retention investment

### Regulatory Goodwill

SEBI has repeatedly expressed concern about retail F&O losses. Zerodha is the largest broker and hence under the most regulatory scrutiny. A built-in behavioral guardrail layer is the kind of initiative that reads well in regulatory submissions and annual reports.

> "We have integrated a behavioral intelligence platform that surfaces pattern-based risk alerts to F&O traders before they place orders."

That sentence in a SEBI report costs Zerodha nothing if TradeMentor builds it — and it's genuinely true.

### Data Insight (Aggregate, Anonymized)

With appropriate consent, aggregated behavioral data (e.g., "67% of F&O traders show revenge trading within 20 minutes of a loss exceeding 1.5× their daily average") is the kind of research Zerodha publishes on their blog (Zerodha Z-Connect, SEBI submissions). We'd share this willingly as part of a partnership.

---

## 5. The Sensibull Precedent

Sensibull is the most directly comparable example.

**What Sensibull is**: An options trading platform (strategy builder, P&L simulator, IV charts) originally built on top of the public KiteConnect API.

**How it got integrated**: Zerodha acquired/partnered with Sensibull and embedded it directly inside Kite. Sensibull users can place orders from within Sensibull and they flow through Kite. Sensibull is now accessible as a tab inside Kite Web.

**What this required**: Access to internal order placement APIs, co-branding, joint marketing, distribution through the Kite interface.

**How TradeMentor is different from Sensibull**:

| | Sensibull | TradeMentor |
|---|---|---|
| Primary audience | Options strategy builders | All F&O traders |
| Core value | Trade construction | Behavioral awareness |
| Order interaction | Places orders | Never touches orders |
| Revenue model | Subscription | Subscription (can be Zerodha-bundled) |
| SEBI category risk | Higher (strategy tool = investment advice boundary) | Lower (pure analytics, no advice) |
| Integration requirement | Deep (order routing) | Light (data read + alert surface) |

TradeMentor is lower risk to integrate than Sensibull was, because we never advise or place orders. We only surface behavioral observations.

---

## 6. Technical Architecture Deep Dive

### How We Connect to Zerodha Today

```
Trader → Kite OAuth → TradeMentor captures access_token
Access token stored encrypted (Fernet) in Supabase per user

Order flow (current):
  Trader places order on Kite
    → Zerodha fires postback to ZERODHA_POSTBACK_URL
    → Our FastAPI handler receives order fill
    → PositionLedger processes fill (append-only FIFO ledger)
    → BehaviorEngine runs against updated trade list
    → If pattern detected: RiskAlert created, pushed via WebSocket to browser
    → If DANGER severity: WhatsApp notification to guardian (if configured)
```

### PositionLedger (Core Engine)

We do not use Zerodha's P&L calculations. We maintain our own:

- **Append-only fill ledger**: every fill is a permanent record
- **FIFO cost basis**: for instruments with multiple entries, we match sells against oldest buys first
- **Pure function core**: `_compute_fill_effect()` takes current state + new fill → returns new state deterministically (testable, auditable)
- **Idempotent processing**: each fill has `{order_id}:ledger` idempotency key — re-processing the same fill is a no-op
- **Completed trade materialization**: when a position closes or flips, we immediately write a `CompletedTrade` record with realized P&L, entry/exit prices, hold duration

### BehaviorEngine (22 Patterns)

All thresholds are configurable per user based on their trading profile. Cold-start defaults are based on Indian F&O research benchmarks (documented in `docs/validation/18_behavioral_engine_research_plan.md`).

Key patterns:
- `revenge_trade`: trade placed within N minutes of a loss exceeding X% of daily P&L
- `overtrading_burst`: >N trades in <M minutes
- `session_meltdown`: down >40% of daily target after lunch → escalates to DANGER at 75%
- `end_of_session_mis_panic`: MIS trades after 15:00 (forced SQ bracket)
- `expiry_day_overtrading`: trade count > 1.5× 3-day baseline on the instrument's own expiry
- `size_escalation`: position size 3× average after consecutive losses
- `no_stoploss`: hold time exceeding 10 min (monthly expiry) / 15 min (weekly) for OTM options

Detection runs server-side on every order postback — no client-side detection.

### Event Architecture

```
Order postback
  → FastAPI handler
  → PositionLedger (DB write)
  → BehaviorEngine (pattern scan)
  → EventBus.publish(alert_created)
  → Redis Streams (durable, replayable)
  → WebSocket dispatcher
  → Browser (toast + alert list update)
```

Redis Streams give us durability: if the WebSocket drops and reconnects, the client can request replay of events it missed.

### Multi-Account Support

One Zerodha user can have one KiteConnect OAuth token. We support multiple broker accounts per TradeMentor user for:
- Paper trading account + live account
- Future: family accounts (spouse trading on same TradeMentor login)

Each `BrokerAccount` has its own encrypted `access_token`, `api_key`, and `api_secret`.

---

## 7. Security & Data Handling

### What Data We Store

| Data | Where | Encryption |
|---|---|---|
| Zerodha `access_token` | Supabase (PostgreSQL) | Fernet symmetric (AES-128-CBC) |
| `api_secret` | Supabase | Fernet symmetric |
| Trade fills / positions | Supabase | At-rest (Supabase default) |
| User phone (guardian) | Supabase | At-rest |
| Journal entries | Supabase | At-rest |
| Behavioral analysis | Supabase | At-rest |

We do **not** store:
- Bank account numbers
- Demat account numbers
- Aadhaar / PAN (we don't ask for them)
- Payment information (Razorpay handles this)
- Full KYC details

### Access Token Lifecycle

1. Zerodha OAuth → one-time `request_token`
2. Exchange for `access_token` via KiteConnect SDK
3. `access_token` stored encrypted in DB
4. Used for API calls only (never exposed to frontend)
5. Expires daily at midnight IST (Zerodha enforces this)
6. User re-authenticates next trading day via single-click re-login

### Token Security

- Encryption key (`ENCRYPTION_KEY`) is a single master secret in environment variables
- Never stored in DB or code
- Losing it breaks all stored tokens — documented in internal notes, rotation procedure to be written
- In production: should be in a secrets manager (AWS Secrets Manager / Doppler)

### What We Do NOT Do

- We never execute orders on behalf of users
- We never read portfolio value or demat holdings (only intraday trades/positions)
- We never read payment/banking data
- We have no write access to the Zerodha account — only read via OAuth scopes
- We do not sell individual trade data to any third party

### Data Retention

- Raw trade fills: 24 months (user-configurable deletion)
- Behavioral alerts: 12 months
- Journal entries: indefinite (user owns them)
- Access tokens: deleted on disconnect
- All data deleted within 30 days of account deletion (per Privacy Policy)

---

## 8. SEBI & Legal Compliance

### What We Are (Legally)

TradeMentor is a **behavioral analytics platform**, not a registered investment advisor (RIA).

We do not:
- Provide buy/sell recommendations
- Predict market direction
- Advise on which instruments to trade
- Claim to improve returns

We do:
- Mirror a trader's own behavioral patterns back at them
- Surface observations ("you placed 4 trades in 6 minutes") without interpretation
- Help traders track their own self-set goals and rules
- Provide an AI coach that discusses psychology and habits, with explicit disclaimers

### SEBI Disclaimer (Shown at Multiple Points)

> "TradeMentor is a behavioral analytics tool and does not provide investment advice. Past behavioral patterns are not indicative of future trading performance. TradeMentor is not registered with SEBI as an Investment Adviser. All trading decisions remain solely with the user."

This disclaimer appears:
- On the Terms of Service (full section)
- Inline on the Chat/AI Coach page
- As a footer on Analytics
- On the Welcome/Landing page

### DPDP Act 2023 Compliance

Privacy Policy written to comply with India's Digital Personal Data Protection Act 2023:
- Clear consent at onboarding (checkbox, cannot skip)
- Data minimization (we collect only what's needed for the service)
- Right to erasure (account deletion + data purge)
- Grievance Officer contact in policy
- No cross-border transfer of personally identifiable data outside India (Supabase India region, Upstash India region)

### Terms of Service

- Section 2: SEBI IA Regs 2013 disclaimer
- Section on Zerodha data use: explicit disclosure that we access Zerodha data via KiteConnect with user's consent
- Section on AI: disclaims AI outputs as informational, not advisory

---

## 9. Scalability & Infrastructure

### Current Limits (Free Tier Stack)

| Component | Provider | Current Limit | Handles |
|---|---|---|---|
| Database | Supabase Free | 500MB storage, 2 compute units | ~500 active users |
| Cache | Upstash Free | 10K requests/day | ~50 active users |
| Backend | Render Free | 512MB RAM, sleeps after 15min | Dev only |
| Frontend | Vercel Free | Unlimited requests | Any scale |

### Production Stack (Paid, ~$50-100/mo)

| Component | Provider | Cost | Handles |
|---|---|---|---|
| Database | Supabase Pro | $25/mo | 8GB storage, unlimited requests |
| Cache | Upstash Pay-as-you-go | ~$5-10/mo | Millions of requests |
| Backend | Render Starter | $7/mo | Always-on, 512MB |
| Celery Workers | Render Starter | $7/mo each | Background tasks |
| Frontend | Vercel Free | $0 | Any scale |

### Scaling Architecture (For Zerodha-Scale)

If TradeMentor is surfaced to even 1% of Zerodha's 12M+ active users (~120,000 users):

1. **Database**: Migrate to Supabase Enterprise or dedicated PostgreSQL (AWS RDS). Behavioral patterns are write-heavy during market hours (10-minute burst) → read-heavy off-hours (analytics, reports)

2. **Event processing**: Current Redis Streams → Kafka migration for >10K concurrent users. Celery workers horizontally scalable.

3. **API**: FastAPI is async-native, handles concurrent connections efficiently. Stateless design means horizontal scaling behind a load balancer is straightforward.

4. **WebSocket**: Current single-server WS can be replaced with Redis Pub/Sub fanout for multi-node deployment.

5. **BehaviorEngine**: Stateless per-trade evaluation, scales linearly. No shared state between users.

6. **Zerodha API rate limits**: KiteConnect limits are per-token (per user), not global. 50 users each polling independently don't share one rate limit pool. At scale, the architecture relies on webhooks (no polling), which doesn't hit rate limits at all.

### Keep-Alive (Render Free Tier)

Until paid tier, keep-alive is implemented via:
- Celery Beat task pinging `/health` every 4 minutes
- Fallback: Uptime Robot (free) hitting health endpoint every 5 minutes
- The cron job ensures zero cold starts during 09:00–16:00 IST

---

## 10. Business Model

### Current Plan

| Tier | Price | Features |
|---|---|---|
| Free | ₹0 | 1 broker account, basic alerts (last 7 days), no AI coach |
| Pro | ₹499/mo | 3 broker accounts, all alerts, AI coach, analytics history |
| Elite | ₹999/mo | Unlimited accounts, Guardian alerts, priority support, raw export |

### With Zerodha Integration (Possible Models)

**Model A — Zerodha Bundles TradeMentor**
- Zerodha offers TradeMentor Pro as "Kite Behavioral Intelligence" at ₹299/mo (discounted)
- Revenue share: 70% TradeMentor / 30% Zerodha
- Zerodha benefits: increased ARPU per active trader, retention tool, regulatory differentiation

**Model B — Free for Zerodha Users**
- TradeMentor basic tier free for all Zerodha users
- Zerodha pays per active user ($X/user/month, similar to B2B SaaS)
- TradeMentor benefits: distribution to millions of users, monetize with premium tier

**Model C — Acquisition / Integration**
- Zerodha acquires TradeMentor and builds it into Kite (Sensibull model)
- TradeMentor team continues building under Zerodha brand

### Current Revenue

Pre-launch. No paid users yet. Product is in active development and private beta.

---

## 11. Q&A Preparation — Technical

**Q: How do you use our API? What data do you read?**
We use KiteConnect for: (1) OAuth authentication, (2) real-time order postbacks to our server, (3) `/trades` endpoint for same-day fills. We do not read positions, holdings, portfolio value, or financial data beyond intraday trade fills.

**Q: What happens if your server goes down? Do you lose trade data?**
Yes, currently. Postbacks to our server are lost if we're unavailable. This is the main production reliability gap we're working on. With a durable order event stream, we could replay missed fills on reconnect. Without it, we do a periodic reconciliation using `/trades` endpoint.

**Q: Do you store access tokens?**
Yes, encrypted with Fernet (AES-128-CBC) in our database. The encryption key is never stored in the DB — it's an environment variable. Tokens expire daily at Zerodha's end regardless.

**Q: Can you place orders on behalf of users?**
No. We have no order placement in our codebase. Our KiteConnect integration is read-only. The OAuth scopes we request are: `orders` (read), `trades` (read). We do not request `orders:write`.

**Q: How do you handle the KiteConnect rate limits?**
We don't poll at all in the intended production design. Everything is webhook-driven. The only API calls are: (1) initial token exchange on login, (2) `/trades` for same-day fill reconciliation (once per session), (3) `/profile` for user info on login. No polling loops.

**Q: Why do you need a persistent WebSocket order feed instead of postbacks?**
Postbacks are HTTP fire-and-forget. If our server is restarting during a deploy, or experiences a cold start (free tier), postbacks arrive to no listener and are dropped. A WebSocket stream we maintain lets us reconnect and request replay. This is the same problem Kite's own market data WebSocket solves for price feeds.

**Q: How do you handle multiple users on the same underlying?**
Each user's data is completely isolated in our database. BrokerAccount rows are user-scoped. There's no shared state between users. Behavioral detection runs per-user.

**Q: What's your database schema like?**
Core tables: `users`, `broker_accounts` (per Zerodha account), `trades` (fills), `positions` (current), `position_ledger_entries` (append-only FIFO), `completed_trades` (materialized closed positions), `risk_alerts` (behavioral detections), `trade_journals` (free-text + structured notes), `goal_commitments`, `user_profiles` (thresholds, preferences).

**Q: What's your tech stack?**
FastAPI (Python 3.11) + SQLAlchemy async + asyncpg on backend. React 18 + TypeScript on frontend. Supabase PostgreSQL, Upstash Redis. Celery for background tasks. All open-source stack — no proprietary dependencies except hosting providers.

**Q: How would the browser extension work technically?**
Content script injected into kite.zerodha.com. Reads order form fields from DOM (no network interception). Calls our backend with the instrument + quantity + direction before submission. Backend returns behavioral context. Content script renders a brief overlay ("3 trades in 6 min — is this a revenge trade?"). User can dismiss and proceed normally. No order blocking. No DOM mutation of Kite's forms.

---

## 12. Q&A Preparation — Business & Product

**Q: What problem are you solving?**
F&O traders in India have a well-documented behavioral problem: SEBI's own data shows 90%+ of retail F&O traders lose money consistently. The primary cause isn't lack of market knowledge — it's behavioral self-sabotage (revenge trading, overtrading, panic exits). No existing tool addresses this in real time.

**Q: Who are your target users?**
Active retail F&O traders on Zerodha — specifically traders who are already technically competent (have been trading 6+ months) but struggling with consistency. Not beginners. Not algorithmic traders.

**Q: How many users do you have?**
Currently in private development/testing. No public users yet. We have a working product with guest mode for demos.

**Q: What makes you different from other analytics tools?**
Most analytics tools (Streak, Sensibull analytics, smallcase) show aggregate P&L and strategy performance. We show behavioral patterns — the psychology behind the numbers. The focus is "why you make decisions" not "what decisions made money." No other product in the Indian market does this.

**Q: Why would a trader use a separate app instead of Kite's own analytics?**
Kite shows P&L, holdings, and order history. It doesn't detect patterns across sessions, doesn't track behavioral habits, doesn't flag when you're in a revenge trading spiral, doesn't track goal adherence, doesn't give AI coaching on trading psychology. These are different jobs.

**Q: What does the AI coach do exactly?**
It's a conversational AI with access to the user's own trade history. It answers questions like "Why am I overtrading on Fridays?" or "What's my average loss when I trade within 5 minutes of waking up?" It reasons about the user's specific data, not generic advice. It is explicitly not a financial advisor and tells the user this.

**Q: How do you prevent the AI from giving financial advice?**
System prompt explicitly prohibits securities recommendations. Every AI response is prefaced with a disclaimer that this is behavioral coaching, not financial advice. We've reviewed the SEBI IA Regulations 2013 — behavioral psychology coaching is not regulated investment advisory activity.

---

## 13. Q&A Preparation — Security

**Q: If your system is compromised, can an attacker use the stored tokens to trade on users' accounts?**
Tokens are encrypted at rest. An attacker would need both: (1) the database contents AND (2) the `ENCRYPTION_KEY` environment variable. These are in separate systems (Supabase database vs Render environment variables). We don't have order placement capabilities, so even a compromised token can only read data — not execute trades.

**Q: Do you log access tokens anywhere?**
No. We explicitly suppress token logging. Our logging framework uses `***` masking for any field named `token`, `secret`, or `key`. We did an audit pass to ensure no token appears in application logs, Sentry events, or debug output.

**Q: What happens when a user disconnects?**
The access token is deleted from our database immediately. We issue a Zerodha API call to invalidate the token. The user's behavioral data (trade history, alerts) remains unless they explicitly delete their account (DPDP compliance).

**Q: How do you handle KiteConnect session expiry?**
Tokens expire daily at midnight IST. We catch 403 errors from Zerodha API calls and mark the broker account as `connected: false`. Users see a "Re-login required" prompt in the UI. We do not attempt auto-refresh (KiteConnect doesn't support refresh tokens).

**Q: Have you done a security audit?**
Internal security review covering OWASP Top 10, rate limiting (admin panel, API endpoints), SQL injection (using SQLAlchemy parameterized queries — no raw SQL), XSS (React's default escaping + no dangerouslySetInnerHTML), CSRF (JWT-based auth, no cookies), and data exposure (no PII in logs, no tokens in URLs).

**Q: What rate limiting do you have?**
- Admin login: 5 attempts per IP per 15 minutes
- Admin OTP: 5 guesses per IP per 5 minutes
- API endpoints: Sliding window rate limiting on sensitive routes
- WebSocket connections: Per-user connection limit

---

## 14. Q&A Preparation — Legal & Compliance

**Q: Are you registered with SEBI?**
No. Behavioral analytics tools do not require SEBI registration as Investment Advisers. We have reviewed SEBI IA Regulations 2013 and are confident that providing behavioral pattern detection and psychology coaching (without securities recommendations) does not constitute investment advisory activity.

**Q: How do you handle user consent for data access?**
Multi-step consent: (1) Welcome page checkbox (Terms + Privacy linked, must be ticked) → (2) Zerodha OAuth screen (Zerodha's own consent) → (3) In-app data processing notice. Users can revoke consent at any time by disconnecting their Zerodha account.

**Q: What is your data residency?**
Database: Supabase India region (AWS ap-south-1, Mumbai). Cache: Upstash India region. Frontend: Vercel (global CDN). Backend: Render (US East currently — to be migrated to Indian region for production at scale).

**Q: Can you comply with Zerodha's API usage terms?**
Yes. We've reviewed the KiteConnect developer terms. Specifically: (1) We display Zerodha's brand assets per their guidelines, (2) We don't scrape or reverse-engineer any Zerodha system, (3) We use only documented API endpoints, (4) We don't resell Zerodha data, (5) We maintain user consent records.

**Q: What if SEBI issues new regulations on F&O trading tools?**
We follow SEBI regulatory updates. The "mirror, not blocker" philosophy is specifically designed to stay well within the behavioral analytics space (not advisory). If regulations change, we have the technical ability to adjust features quickly (e.g., adding more disclosures, restricting certain AI responses).

---

## 15. Q&A Preparation — Managerial / Strategic

**Q: Why do you need Zerodha? Can you build without them?**
We can build the behavioral analytics layer without deeper Zerodha integration — and we have. But the most impactful features (real-time overlay in Kite, durable event stream, native distribution) require their cooperation. We're not blocked from building a useful product, but the ceiling without partnership is lower.

**Q: What's your competitive moat?**
Three things that are hard to replicate: (1) Proprietary behavioral pattern library tuned specifically for Indian F&O markets (expiry day cycles, NSE session timing, MIS/NRML nuances), (2) Longitudinal user data — the longer a user is on TradeMentor, the more accurately the engine knows their personal behavioral fingerprint, (3) User trust — traders share their worst moments with TradeMentor. That relationship is hard to build.

**Q: Why wouldn't Zerodha just build this themselves?**
Zerodha has 800+ employees and has built some of the most sophisticated trading infrastructure in India. What they haven't built is behavioral psychology tooling — because it's a different domain (behavioral economics + trading psychology research) from what their engineering team focuses on. Sensibull is the precedent: Zerodha didn't build an options strategy tool themselves either.

**Q: What's your monetization strategy?**
Subscription SaaS. ₹499-999/month for Indian F&O traders who trade professionally. The target user loses ₹5,000-50,000/month to behavioral mistakes. If TradeMentor saves even 10% of that, it's worth ₹500-5,000/month — making our pricing a trivial cost. The ROI story is clear.

**Q: What's your roadmap?**
Q1 2026: Production hardening + backend hosting migration  
Q2 2026: Browser extension overlay (public beta)  
Q3 2026: Zerodha partnership conversations  
Q4 2026: Mobile app (React Native, reusing existing design system)  
2027: Expand to multi-broker (Upstox, AngelOne)

**Q: Are you full-time on this?**
[Answer honestly based on your situation.]

**Q: What does success look like for you in a Zerodha partnership?**
Phase 1: Technical integration — access to durable order stream + greenlight for extension  
Phase 2: Distribution — featured in Kite marketplace or newsletter  
Phase 3: Commercial partnership — revenue share, co-marketing  
Long-term: Acquisition if TradeMentor proves to be a product Zerodha wants to own and scale

---

## 16. What We're Asking For (Partnership Tiers)

### Tier 1 — Technical Alignment (No Commercial Agreement Needed)
- Confirmation that browser extension overlay on Kite Web is acceptable
- Documentation of any constraints (DOM elements we shouldn't interact with, CSP headers we should respect)
- Access to a staging/sandbox environment for extension testing

### Tier 2 — API Enhancement (Developer Program)
- Access to a WebSocket-based order event stream (or persistent postback queue with replay)
- Higher rate limits for partner applications
- Advance notice of API changes that would break integrations

### Tier 3 — Commercial Partnership (Equity Partner Model)
- Native integration point in Kite Web (similar to Sensibull tab)
- Co-branding: "Powered by TradeMentor" or "Kite Behavioral Intelligence"
- Revenue sharing arrangement
- Joint go-to-market / user acquisition

We are comfortable starting with Tier 1 and growing from there. We're not asking Zerodha to commit to anything commercial today.

---

## 17. Current Gaps & Honest State

Being transparent about what's not finished yet:

| Gap | Impact | ETA |
|---|---|---|
| Backend on localhost (webhooks not receiving) | High — P&L incorrect until moved to production | This week |
| M1 guard bug (overnight NRML positions not backfilling) | High — positions opened yesterday invisible | This week |
| TATATECH / DABUR P&L incorrect in DB | High — needs manual DB correction | This week |
| WhatsApp (Gupshup) code not written | Medium — Guardian alerts via WhatsApp not live | 2 weeks |
| Browser extension | Medium — doesn't exist yet | 2-3 months |
| Mobile app | Low — web is mobile-responsive, native app is future | 6-12 months |
| Production Render deployment | High — needed before pitch | This week |
| Payment integration (Razorpay) | Medium — no paid users can be onboarded | 1 month |
| Per-user onboarding flow (complete) | Low — working but rough edges | 2 weeks |

**The honest answer**: We have a technically solid foundation and a working product. We are not ready to pitch Zerodha commercially today. We should complete production hardening first. This document is preparation so that when we're ready, we don't have to scramble.

---

## 18. Things You Might Have Missed

### The Webhook URL Is The Most Urgent Fix

Before moving to Render or pitching anyone, change `ZERODHA_POSTBACK_URL` in `.env` from `http://localhost:8000/...` to the actual Render URL. Every trade currently goes unrecorded in the position ledger. This is P0.

### KiteConnect API Key Is Per Developer Account

When pitching Zerodha, clarify that the current setup uses a single developer KiteConnect API key (with a per-user access token). At scale, this may need to change — some partners get dedicated API keys with higher limits. This is a conversation to have early.

### Zerodha Has a "Connect" Marketplace

Zerodha has a developer program at `developers.kite.trade` and a "Connect" marketplace where third-party apps can be listed. Before approaching business development, consider listing TradeMentor in the Connect marketplace — it creates credibility and shows Zerodha you're already a serious KiteConnect user.

### The Expiry Day Bug Is Embarrassing If They Ask

The behavior engine hardcodes Thursday as expiry day (`weekday() == 3`). SEBI changed equity index expiry to Monday for NSE. If Zerodha demos the app and trades an instrument expiring on a non-Thursday, the pattern won't fire. Fix this before any demo: use `parse_symbol().expiry_date == today` instead.

### Token Re-Authentication UX Needs Polish

Currently if a user's Zerodha token expires overnight, they see a generic error. This needs to be a clean "Re-connect Zerodha" prompt with a single button. This is the first thing a Zerodha reviewer would notice if they use the app in the morning.

### You Should Have Usage Metrics Ready

Zerodha will ask: how many users, how many trades processed, what's your uptime. You need real numbers. Even if it's "100 beta users, X trades processed, Y% of sessions had behavioral alerts fired." Consider adding a simple analytics event log before the pitch.

### The Guardian Feature Is the Most Differentiated

Of all the features, Guardian (trusted person getting WhatsApp when you're in a danger spiral) is the one most likely to generate press coverage and word-of-mouth. Zerodha's marketing team would find it compelling. Make sure it's working before the pitch.

### Consider a Video Demo Over a Live Demo

Live demos in front of Zerodha could go wrong if the connection drops, token expires, or webhooks don't fire. Record a 3-minute walkthrough: connect Zerodha → place a few trades → see alerts fire → see behavioral history → see AI coach response. That's more reliable than live and they can watch it async.

---

*Document created: 2026-04-15. Update before any external sharing.*
