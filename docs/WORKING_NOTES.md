# TradeMentor AI — Working Notes
*Running log of decisions, state, and context. Updated every session.*
*If context is lost (restart/rate limit), read this + MEMORY.md + production_readiness_review.md*

---

## Session 31 (2026-04-02) — Design System + Dashboard Spec

### What happened
User said existing UI/UX is not coming out right. Decided to restart the design process properly: brainstorm page by page, write pixel-level specs, then build from Stitch/Figma mockups.

### New Design Workflow (locked)
1. Discuss + brainstorm a screen together
2. Write pixel-level spec in `docs/design/screens/XX_screenname.md` (web + mobile in same file)
3. User builds mockup in Stitch/Figma
4. User shares mockup → I implement
5. Update DESIGN_CHECKLIST.md as each stage completes

### Files Created This Session
- `docs/design/01_DESIGN_SYSTEM.md` — design tokens (colors confirmed, some TBDs remain)
- `docs/design/DESIGN_CHECKLIST.md` — master checklist of all 21 screens, 4 stages each
- `docs/design/screens/` — new subfolder for per-screen pixel specs
- `docs/design/screens/01_dashboard.md` — complete dashboard spec (web + mobile)
- `docs/design/02_WEB_SCREENS.md` — added navigation table at top pointing to screens/ files

### Design Decisions Locked (don't revisit without reason)

**Typography:** Inter. Tabular-nums for all financial data.

**Theme:** Dark nav chrome + white/off-white content area. One theme. No toggle for now.
- Dark: `#0F172A` nav/sidebar/header/footer
- Light content: `#F1F5F9` page bg, `#FFFFFF` cards

**Brand color:** Teal
- `#0D9488` — on light backgrounds (buttons, active states)
- `#2DD4BF` — on dark nav background (active nav text)
- `#0D9488/12` — active nav item background

**Full color palette confirmed:**
- Profit: `#16A34A` (green-700)
- Loss: `#DC2626` (red-600)
- Observation/alert: `#D97706` (amber-600)
- Observation bg tint: `#FEF3C7` (amber-50)
- Text primary: `#0F172A`, secondary: `#64748B`, muted: `#94A3B8`
- Border: `#E2E8F0`, card: `#FFFFFF`, page bg: `#F1F5F9`

**Anti-vibe-code rules locked:**
- No card-per-alert pattern — alerts are list rows
- No left colored border on alert rows — small severity dot only (7px circle)
- No metric card grid — stats in page header stat line
- No gradient backgrounds, no glassmorphism, no heavy shadows
- No rounded corners > 8px on data screens
- Max shadow: 1px border only on cards (no drop shadow)
- Monospace/tabular-nums for ALL financial numbers

### Dashboard Spec Summary (full spec in screens/01_dashboard.md)

**Web layout:**
- Page header: "Dashboard" title + compact stat line (trades · P&L · ⚠alerts · ✎unjournaled · goal)
- Full-width Behavioral Alerts section: list rows (dot + name + evidence + timestamp), max 3, view all link
- Two-column below: Left 62% (Open Positions + Closed Today) | Right 38% sticky (Blowup Shield + Session Pace)
- Right column: NO sparkline/graph. Blowup Shield (score + last event) + Session Pace (count vs avg).

**Mobile layout:**
- Header: Dashboard title + stat line (2 rows)
- Behavioral Alerts: max 2 rows, then view all
- Open Positions: simplified columns (Symbol + P&L + Journal icon)
- Closed Today: same simplified columns
- Blowup Shield + Session Pace: stacked cards below closed trades

**Key decisions:**
- Closed trades sort: unjournaled first. Show 5. Drop to 3 when all journaled.
- Stat line: ⚠ and ✎ hidden when 0. Goal shown only if set.
- No margin components. No behavioral score hero. No My Patterns/AI widget.
- Alert rows: tap → alert detail bottom sheet (evidence paragraph + triggering trades + journal/coach links)
- Trade rows: tap → journal bottom sheet (existing chip-select form)
- No acknowledge button anywhere on dashboard.

### Dashboard Checklist Status
- Discussed: ✅ | Specced: ✅ | Designed: ⬜ | Built: ⬜

### Next Screen to Design
Behavioral Alerts page (`/alerts`) — 3 tabs (Recent / History / By Pattern), filter chips, full observation cards.

---

## Session 30 (2026-03-22) — 29-Issue QA Audit, Full Production Polish

### QA Audit — All Issues Resolved

**C1 — `.env.example` missing vars** (`backend/.env.example`)
- Added: `OPENAI_API_KEY`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `EMAIL_FROM`

**D2 — `GET /api/trades/` missing `has_more`** (`backend/app/api/trades.py`)
- Added `has_more: bool` to paginated response schema so frontend can correctly detect end-of-list

**B4 — `behavior_score` crash on null** (`src/components/analytics/BehaviorTab.tsx`)
- Updated `UserBehaviorProfile` interface: `behavior_score: number | null`
- Score display: shows "—" instead of crashing; shows "Need 5+ trades" tooltip when null

**F3 — Duplicate `trading_since` field** (`src/pages/Settings.tsx`)
- Removed duplicate key in `UserProfile` interface (was defined twice → last one silently won)

**F5 — Demo data field name mismatch** (`src/lib/demoData.ts`)
- `DEMO_COMPLETED_TRADES` typed as `CompletedTrade[]`
- Fixed field names: `quantity` → `total_quantity`, `entry_price` → `avg_entry_price`, `exit_price` → `avg_exit_price`
- `DEMO_POSITIONS` typed as `Position[]`
- Guest mode quantity/price columns now render correctly (were blank before)

**M3 — Admin test-email endpoint** (`backend/app/api/admin/system.py`)
- Added `POST /api/admin/test-email` — sends test email to admin's own address to verify SMTP config is working

**E1 — Market hours missing holiday calendar** (`backend/app/utils/market_hours.py`)
- Added `NSE_HOLIDAYS_2025` and `NSE_HOLIDAYS_2026` dicts with full NSE holiday lists
- Added `is_trading_holiday(date)` function
- `is_market_open()` now checks holidays before returning True
- Added `NSE_EXTRA_HOLIDAYS` env var override for ad-hoc closures (budget day, etc.)

**E2 — Webhook for deleted/suspended accounts** (`backend/app/api/webhooks.py`)
- Previously: silently processed or returned confusing "Account not found"
- Now: explicitly checks account state, logs `"Webhook discarded — account {id} is {state}"`, returns 200 with clear message to prevent Zerodha retry loop

---

## Session 29 (2026-03-22) — Rate Limiting, BTST Frontend, Onboarding Card

### 1. Admin Login Rate Limiting

**Files changed:**
- `backend/app/core/rate_limiter.py` — added `admin_login_limiter` (5/900s) + `admin_otp_limiter` (5/300s)
- `backend/app/api/admin/auth.py` — wired both limiters, added per-email Redis lockout

**Two layers of protection:**
1. **IP sliding-window** (`admin_login_limiter`): 5 requests per 15 minutes per IP. Returns 429 + `Retry-After` header. Handled by existing `RateLimiter` class.
2. **Per-email Redis lockout**: After 5 consecutive wrong passwords for a specific email, that email is locked for 15 minutes (Redis key `admin_fail:{email}`, TTL=900). Catches attackers rotating IPs. Counter is cleared on successful login.
3. **OTP endpoint** (`admin_otp_limiter`): 5 OTP attempts per 5 minutes per IP — prevents 6-digit brute-force (1M possibilities).

Both `/login` and `/verify` endpoints now take `Request` as first parameter so the limiter can read the IP.

### 2. BTST Analytics Frontend

**Backend:** `/api/analytics/btst` already existed. Fixed missing fields in trade list:
- Added `hold_type` ("weekend_hold" if Friday entry, "overnight" otherwise)
- Added `instrument_type`

**Frontend:** `BTSTCard` component added to `BehaviorTab.tsx`
- 4 summary metrics: BTST trade count, win rate, total P&L, overnight reversal count (with P&L lost)
- Context blurb explaining the pattern and why Friday entries are highlighted
- Collapsible trade table: symbol, instrument type, entry date, hold duration, P&L, reversal status
- Weekend hold trades get a "WE" badge; reversal rows get orange highlight
- Null-safe: `<BTSTCard>` returns null if `!data?.has_data`
- Positioned between `ConditionalPerformanceCard` and `OptionsPatternCard`

### 3. Onboarding Flow — GettingStartedCard

**File:** `src/components/dashboard/GettingStartedCard.tsx` (new)

A 4-step checklist that shows on the Dashboard for new users:
1. **Connect Zerodha** — always done (✅) if the card is showing
2. **Set up your profile** — done when `onboardingStatus?.completed` is true. Shows "Set up now →" button that reopens the wizard.
3. **Sync your first trades** — done when `tradeCount > 0`. Shows inline "Sync now" button that calls `syncTrades()` with loading state.
4. **Explore Analytics** — done when `tradeCount >= 5`. Shows link to `/analytics` when 0 < trades < 5.

**Visibility logic:**
- Auto-hides when `tradeCount >= 3 && onboardingCompleted` (user has meaningful data + completed setup)
- Per-account dismiss button stores `tradementor_gs_dismissed_{accountId}` in localStorage
- Progress bar shows X of 4 steps with percentage

**Wired in Dashboard.tsx:**
- Added `GettingStartedCard` import
- Updated `useOnboarding` destructure to also pull `reopenOnboarding` + `status`
- Rendered above the Page Header (before the main grid)

---

## Session 28 (2026-03-21) — Bug Fixes, BehaviorEngine 22 Patterns, Email Removal, WhatsApp Templates

### Bug Fixes (All 12 AUDIT_SILENT_BUGS.md now ✅ closed)

**H3 — Reject webhooks with all NULL timestamps** (`backend/app/api/webhooks.py`)
- Added early rejection before building `trade_data`:
  ```python
  _ts_fields = (form_dict.get("order_timestamp"), form_dict.get("exchange_timestamp"), form_dict.get("fill_timestamp"))
  if not any(_ts_fields):
      logger.error(f"Postback rejected — order {form_dict.get('order_id')} has no timestamps")
      return {"status": "ok", "message": "No timestamps"}
  ```
- Returns 200 (not 4xx) to prevent Zerodha retry loop.

**M1 — Overnight backfill guard** (`backend/app/services/trade_sync_service.py`)
- In `_sync_positions()` overnight_closed loop: before appending to `stats["overnight_closed"]`, now queries DB for BUY trades for that symbol today.
- If no BUY entry found → logs "untracked position" and `continue`. Prevents phantom CompletedTrade records for positions opened before the user connected to TradeMentor.

**M3 — Margin insolvency distinct from 100% utilization** (`backend/app/services/margin_service.py`)
- `_analyze_segment()` now returns `"is_insolvent": live_balance < 0`
- `_analyze_margins()` checks both segments: if insolvent → `risk_level = "insolvent"` with "Account is in debit balance (margin call territory)" message
- `"insolvent"` is a fourth distinct risk level above "danger" (not just 100% utilization)

### BehaviorEngine: 18 → 22 Patterns

**G3 — Expiry day detection bug fix** (`instrument_parser.py`)
- `is_expiry_day(symbol, trade_date)` function replaces all hardcoded `weekday()==3` checks
- `expiry_key` length = 7 chars → monthly ("YYYY-MM"), 10 chars → weekly ("YYYY-MM-DD")
- SEBI can change expiry schedule; symbol-parsed expiry_date is the source of truth

**G9 — Monthly vs weekly expiry thresholds** (no_stoploss detector, `behavior_engine.py`)
- Monthly expiry: 10 min hold, 20% loss (tightest — theta at maximum all day)
- Weekly expiry: 15 min hold, 30% loss
- Normal day: 30 min hold, 25% loss
- New threshold keys in `trading_defaults.py`: `no_stoploss_monthly_hold_min`, `no_stoploss_monthly_loss_pct`

**G2 — Expiry day overtrading alert** (pattern 19, `_detect_expiry_day_overtrading`)
- Fires after 13:00 IST on any instrument's own expiry date
- Cold-start fallback: 5+ trades = CAUTION, 8+ = DANGER (baseline comparison is future work)
- Also checks lot count: 10+ lots = CAUTION
- RISK_DELTA = 20

**G4 — Opening 5-min trap** (pattern 20, `_detect_opening_5min_trap`)
- Derivative entry 09:15–09:20 IST
- 1 entry = CAUTION, 2+ = DANGER
- RISK_DELTA = 10

**G5 — End-of-session MIS panic** (pattern 21, `_detect_end_of_session_mis_panic`)
- `ct.product in ("MIS", "INTRADAY")` and `entry_ist >= 15:10`
- 2 trades = CAUTION, 3+ = DANGER
- RISK_DELTA = 15

**G6 — Post-loss recovery bet** (pattern 22, `_detect_post_loss_recovery_bet`)
- Last 2 prior trades (before current) must both be losses
- `current_qty / avg_recent_qty >= 2.0` = CAUTION, `>= 3.0` = DANGER
- RISK_DELTA = 20

All 4 new detectors added to `_run_all_detectors` list. All thresholds in `trading_defaults.py`.

### Email Reports Removed (user decision)

Decision: We do NOT send reports/notifications over email. Email delivery was removed from user-facing features. SMTP config kept only for admin panel OTP fallback.

Changes:
- `retention_service.py`: removed `email_service` import, removed `email=` param from `send_eod_report()` + `send_morning_brief()`, removed email send blocks
- `report_tasks.py`: `_get_delivery_channels()` now returns `phone, None` — email always None. Removed `UserProfile` import.
- `profile.py`: removed `email_service` import + `"email": {"smtp_configured": ...}` from notification-status response
- `admin/system.py`: removed email health check block
- `config.py`: SMTP vars kept (`Optional[str] = None`) with comment "only for admin panel OTP"
- `email_service.py` file kept intact (admin OTP needs it)

### Per-User Zerodha API Keys

- `BrokerAccount` model has `api_secret_enc` (Fernet-encrypted)
- Setup-credentials flow: user provides their own api_key + api_secret during Zerodha connect
- `ENCRYPTION_KEY` env var (Fernet) protects all stored tokens. Losing it = all tokens unreadable.

### WhatsApp — Template Approach Confirmed

Decision: Templates only (no session/dynamic messages). Reasons:
- Templates don't require user to message first every day
- One-time opt-in: user checks consent checkbox in onboarding → can receive templates forever
- Guardian: receives a single `tradementor_guardian` template when saved as guardian; can reply STOP to opt out
- All BSPs (Gupshup, Twilio, AiSensy, WATI) require Meta Business Manager — it's Meta's mandate, not BSP-specific
- Telegram rejected (users don't open Telegram as often as WhatsApp)

**3 Templates defined** (in `docs/WHATSAPP_GUPSHUP_MIGRATION.md`):
1. `tradementor_report` — EOD + morning brief. Variables: `{{1}}` date/greeting, `{{2}}` trades, `{{3}}` P&L, `{{4}}` alerts fired, `{{5}}` CTA text, `{{6}}` URL
2. `tradementor_alert` — Real-time behavioral alert to trader. Variables: `{{1}}` user name, `{{2}}` pattern name, `{{3}}` description, `{{4}}` impact, `{{5}}` action, `{{6}}` URL
3. `tradementor_guardian` — DANGER notification to guardian. Variables: `{{1}}` guardian name, `{{2}}` trader name, `{{3}}` alert name, `{{4}}` description, `{{5}}` action

**Example messages** (as they appear on phone):
- Report: "Your TradeMentor Daily Brief — Today · Mar 19\n📊 Trades: 7 | Net P&L: ₹-3,240\n⚠️ 3 alerts fired today\nReview your session: https://app.tradementor.ai/dashboard"
- Alert (DANGER): "⚠️ TradeMentor Alert — Rajesh K\n🔴 Revenge Trading\nYou entered BANKNIFTY 3 times in 12 minutes after a ₹8,400 loss.\n💸 Estimated additional exposure: ₹24,000\n→ Step away for 20 minutes\nhttps://app.tradementor.ai/alerts"
- Guardian: "🔴 TradeMentor Guardian Alert — Priya,\nRajesh Kumar needs your attention.\n⚠️ Revenge Trading\nRajesh entered BANKNIFTY 3 times in 12 minutes after a ₹8,400 loss...\n→ Please check in on them\nReply STOP to unsubscribe"

### WHATSAPP_GUPSHUP_MIGRATION.md — Full Rewrite

Complete step-by-step guide now in `docs/WHATSAPP_GUPSHUP_MIGRATION.md`:
- Part 1: Meta Business Manager account setup
- Part 2: Gupshup account creation + Embedded Signup + WhatsApp number connection
- Part 3: Template definitions with exact body text + sample values
- Part 4: Opt-in flows (user + guardian)
- Part 5: Real message examples
- Part 6: Code — `whatsapp_service.py` rewrite + `trade_tasks.py` wiring + `retention_service.py`
- Part 7: Environment variables
- Part 8: Day 1/2/3 checklist
- Part 9: Cost breakdown (~₹0.50–0.80/user/day)

### Migrations Confirmed Applied

User confirmed applied: 047_generated_reports, 048_admin_users, 049_admin_audit_log, 051, 052, 053, 054. Previous confusion in TRACKER.md (marked as pending) corrected. All migrations 035–054 now applied (040 skipped).

### Hosting (Free for now)

- **Frontend**: Vercel — genuinely free forever for static sites
- **Backend**: Render free tier (sleeps after 15min idle) or $7/mo paid (always-on). Railway also ~$5/mo.
- **DB**: Supabase free tier (already using)
- **Cache**: Upstash free tier (already using)
- **`.env`**: Never committed to git. On Vercel: set `VITE_API_URL` in project settings. On Render: paste all backend env vars in dashboard.

### Pending Items (status as of session 30)

| Item | Priority | Status |
|------|----------|--------|
| Wire WhatsApp alerts into `trade_tasks.py` | P1 | Code spec in migration doc §6.2. Blocked: Meta template approval. |
| Rewrite `whatsapp_service.py` (Gupshup) | P1 | Full code in migration doc §6.1. Blocked: Meta template approval. |
| ~~BTST analytics (G1)~~ | P2 | **✅ DONE (S29)** — `BTSTCard` in `BehaviorTab.tsx`; backend `/api/analytics/btst` updated |
| Admin panel activation | P0 | `ADMIN_JWT_SECRET` env var + INSERT first admin user (non-code setup) |
| Gupshup account setup (non-code) | P1 | Create Meta BM → Gupshup → submit templates. Still pending. |
| Razorpay payments | P1 | Not started |
| Deep OTM lottery (G7) | Blocked | Needs spot price at trade time |
| ~~Rate limit admin login~~ | P1 | **✅ DONE (S29)** — IP sliding-window + per-email Redis lockout |
| ~~SMTP for admin OTP in prod~~ | P1 | **✅ DONE (S30)** — `POST /api/admin/test-email` endpoint added; env vars documented in `.env.example` |

---

## Session 27 Planning (2026-03-18) — Behavioral Engine Gap Analysis

### Research Summary: What's covered vs what's missing

Full audit of `behavior_engine.py` (18 patterns), `trading_defaults.py` (35+ thresholds), `instrument_parser.py`, `strategy_detector.py`, `market_hours.py`.

---

### NEW WORK ITEMS DEFINED THIS SESSION

#### 1. BTST Analytics (Analytics + Reports — NOT an alert)

**Definition:** BTST = Buy Today Sell Tomorrow. Identified by:
- `product == 'NRML'` (MIS auto-squares ~3:20 PM, so only NRML can be held overnight)
- `entry_time.date() != exit_time.date()` (multi-day hold)
- Entry specifically after **15:00 IST** (emotional/distress indicator — this is not swing trading, it's someone holding overnight hoping to recover)
- Exit before **09:45 IST** next trading session (quick exit at open before conviction drops)

**Sub-analytics to compute (both go in Analytics section + reports):**
- **BTST Trade List**: Show all trades matching the above criteria with P&L
- **BTST Win Rate**: Of all BTST trades, what % closed profitable?
- **Overnight Reversal**: Within BTST trades — if `session_end_pnl > 0` (was profitable at ~3:15 PM close) BUT `realized_pnl < 0` (closed next morning in red). These are the most painful: "went to bed up, woke up down." Show separately as "Overnight reversals: X of Y BTST trades".
- **Aggregate BTST P&L**: Total money made/lost specifically on BTST trades

**What "session_end_pnl" means here**: We don't store an intra-day mark — but we can approximate: if `exit_time > next_market_open` then the position was carried overnight. To determine if it was profitable EOD, we need the MTM price at ~15:15. *Decision pending on data availability — may need to store daily mark-to-market for open NRML positions.*

**Friday BTST (Weekend hold):** Not a separate alert (per Q3). But in the analytics display, flag Friday entries specifically as they carry 2 extra theta days (Saturday + Sunday). Label them in the UI: "Weekend hold" vs "Overnight hold."

**Swing trading distinction:** Any NRML position with entry before 14:45 IST is considered a planned swing — exclude from BTST analysis entirely.

---

#### 2. Expiry Day Overtrading Alert (Behavioral ALERT — yes, real-time alert)

**Trigger logic:**
- Today is the expiry date of any instrument the trader has an open/recent position in
- Expiry date is read from `instrument_parser.py` → `parsed.expiry_date` — **never hardcoded**
- Compare today's trade count and average qty (for that underlying) against their personal baseline from the last 3–4 trading days for that same underlying only

**Detection pseudocode:**
```
is_expiry_day_for_underlying = (trade.entry_time.date() == parsed_symbol.expiry_date)
recent_baseline = avg_trades_per_session + avg_qty_per_session
  for same underlying over last 3–4 trading days (exclude any other expiry days from baseline)
if today_trade_count > baseline_count * 1.5 AND today_avg_qty > baseline_avg_qty * 1.5:
    → CAUTION alert
if either metric > 2× baseline:
    → DANGER alert
```

**Alert message example:**
> "On NIFTY expiry day you've placed 11 trades (vs your 4-trade avg) with 3.2× your usual lot size. Expiry-hour F&O has an 85% retail loss rate — each trade on an expiring contract decays 3–5× faster than normal."

**Time context:** The alert should note if the spike is after 14:30 IST specifically (expiry rush window). Not a separate trigger, just include the time detail in the message.

**Baseline cold-start (no history yet):** Use fixed fallback: >5 trades on expiry day after 13:00 IST OR any trade with qty > 10 lots on any expiry day → trigger caution.

---

#### 3. Expiry Day Detection — BUG FIX (currently hardcoded Thursday)

**Current broken code in `behavior_engine.py`:**
```python
is_expiry_day = (entry_ist.weekday() == 3)  # WRONG — Thursday only
```

**Correct approach:** Parse the tradingsymbol with `instrument_parser.py` and check if `parsed.expiry_date == today_ist.date()`. If parsing fails (EQ, unknown), default to False.

```python
parsed = parse_symbol(ct.tradingsymbol)
is_expiry_day = (parsed.expiry_date == entry_ist.date()) if parsed.expiry_date else False
```

**Why this matters:**
- SEBI may (and does) change expiry days. Already happened: BANKNIFTY moved, then SEBI restricted weekly expiries.
- BSE contracts (Sensex, Bankex) have different expiry days than NSE
- Monthly vs weekly expiry differ in severity (monthly = full series expiry, much higher risk)

**Add expiry type to context:**
```python
is_monthly_expiry = is_expiry_day and parsed.expiry_key is a monthly key (no specific day)
is_weekly_expiry  = is_expiry_day and parsed.expiry_key has a specific date
```
Monthly expiry → use tighter thresholds (no_stoploss hold: 10 min vs 15 min; loss threshold: 25% vs 30%)

**Known index expiry schedule (as of 2026, but always derive from instrument, never hardcode):**
- NIFTY: Weekly Thursday expiry + Monthly last-Thursday expiry
- Sensex / Bankex (BSE): Weekly Tuesday/Friday (varies by SEBI circular — derive from symbol)
- BANKNIFTY / FINNIFTY / MIDCPNIFTY: Monthly only (SEBI restricted weekly in 2024)

---

#### 4. Other Identified Gaps (prioritized backlog)

| ID | Pattern | Type | Priority | Blocker |
|----|---------|------|----------|---------|
| G1 | **BTST analytics** | Analytics + Report | **P1** | MTM data for overnight reversal detection |
| G2 | **Expiry day volume spike** | Real-time alert | **P1** | Baseline calculation per-underlying |
| G3 | **Expiry day detection bug fix** | Bug fix | **P0** | None — use instrument_parser.py |
| G4 | **Opening 5-min trap** | Alert | P2 | None |
| G5 | **End-of-session MIS panic exit** | Alert | P2 | None |
| G6 | **Post-loss single large recovery bet** | Alert | P1 | None |
| G7 | **Deep OTM lottery ticket buying** | Alert | P2 | Needs spot price at trade time |
| G8 | **Strategy pivot confusion** | Analytics | P2 | Needs strategy_detector integration |
| G9 | **Monthly vs weekly expiry severity** | Alert threshold | P1 | Tied to G3 fix |

---

#### 5. Pattern Details — Items Ready to Implement

##### G4: Opening 5-Minute Trap
- **Trigger:** Entry between 09:15–09:20 IST AND `instrument_type in ['CE', 'PE', 'FUT']`
- **Severity:** Caution (size ≤ avg), Danger (size > avg * 1.5)
- **Suppress for:** Strategy legs (hedge entries at open are legitimate)
- **Message:** "Entered BANKNIFTY at 09:16 AM — first 5 minutes have the widest spreads and most volatile price discovery. You typically get a worse fill price than any other time of day."
- **Risk delta:** +8

##### G5: End-of-Session MIS Panic Exit
- **Trigger:** `product == 'MIS'` AND `entry_time > 15:15 IST` OR `exit_time > 15:10 IST` with multiple trades in this window
- **More specifically:** 2+ MIS trades placed after 15:10 IST → pattern suggests scrambling to close before auto-squareoff
- **Severity:** Caution
- **Message:** "3 MIS trades in the last 15 minutes — potentially rushing before auto-squareoff. Forced last-minute exits consistently get 0.2–0.5% worse fills and create panic entries."
- **Risk delta:** +10

##### G6: Post-Loss Single Large Recovery Bet
- **Trigger:** (a) `session_pnl < -(daily_loss_limit * 0.60)` AND (b) `current trade size > session_average_size * 2.5`
- **Different from martingale:** Martingale catches 3-trade escalation. This catches the sudden large single bet after being deep in the hole (skips gradual escalation).
- **Severity:** Danger
- **Message:** "You're at −₹8,400 (63% of daily limit) and just placed a 5× oversized trade. The urge to recover a large loss in one trade is one of the most documented causes of account blow-ups in F&O."
- **Risk delta:** +25

---

### Decisions Made This Session

| Decision | Rationale |
|----------|-----------|
| BTST = analytics only, not alert | Swing traders hold NRML legitimately; alert would be too noisy. Analytics shows the pattern cost without interrupting. |
| Overnight reversal sub-metric | Shows the specific pain of "was profitable, held overnight, closed in red" — emotionally distinct from general BTST loss |
| Expiry day spike = real-time alert | High impact, time-sensitive. A distressed trader needs to see this in the moment, not in a weekly report. |
| Expiry detection from instrument date | Hardcoded Thursday was a bug. SEBI changes expiry schedules. Always parse from symbol. |
| BTST entry after 15:00 only | Positions entered before ~14:45 are planned swing trades. 15:00+ entries are typically emotional holdovers. |
| No separate severity for Friday BTST | Keep it simple. Friday entries appear in analytics as "Weekend hold" label, not a separate alert stream. |

---

## Current State (2026-03-17 — Session 26)

### Session 26 Changes
- **Landing page** (`src/pages/Welcome.tsx`): Full marketing landing page replacing minimal stub. Sections: Navbar (Logo + BETA + About/Features/Pricing/Login smooth-scroll links), Hero (cycling live alert cards, consent checkbox, Connect Zerodha + Guest CTAs), Problem, How It Works, Features grid (6 cards), Patterns showcase (5 patterns with severity badges), Testimonials, Pricing (monthly/yearly toggle, Free/Pro ₹499/Elite ₹999), FAQ accordion, Footer + "Not SEBI registered" bar.
- **Admin panel — backend** (all 9 routers registered in `main.py`):
  - `048_admin_users.sql` migration + `AdminUser` model
  - `049_admin_audit_log.sql` migration + `AdminAuditLog` model
  - `api/admin/auth.py` — email+password → OTP email → JWT (separate from Zerodha OAuth, returns 404 on failure)
  - `api/admin/deps.py` — JWT guard, always 404 never 403
  - `api/admin/overview.py` — metrics + 14-day signup sparkline + online_now count
  - `api/admin/users.py` — paginated list + detail + suspend/unsuspend + send WhatsApp (audit logged)
  - `api/admin/system.py` — full Redis metrics (memory/hit-rate/key-count/evictions/ops), Celery queue depths, DB pool stats, online users, integrations status
  - `api/admin/insights.py` — pattern frequency, severity breakdown, 14-day daily chart
  - `api/admin/config_api.py` — maintenance mode toggle + announcement banner (audit logged)
  - `api/admin/audit.py` — paginated audit log read endpoint
  - `api/admin/broadcast.py` — WhatsApp broadcast to connected/all_with_phone segment (dry-run first)
  - `api/admin/tasks.py` — RedBeat beat task status (last/next run per task)
  - `api/admin/audit_writer.py` — shared audit write helper
- **Admin panel — frontend** (all routes under `/admin/*`, wrapped in `AdminAuthProvider`):
  - `AdminAuthContext.tsx` — separate JWT stored as `tm_admin_token`
  - `adminApi.ts` — all admin API calls
  - `AdminLogin.tsx` — two-step email+password → OTP form
  - `AdminLayout.tsx` — sidebar (7 nav items) + route guard → /admin/login
  - `AdminOverview.tsx` — 8 stat cards + signup sparkline + infra health dots
  - `AdminUsers.tsx` — paginated table, search/filter, CSV export
  - `AdminUserDetail.tsx` — stats, profile, suspend toggle, send WhatsApp, recent alerts
  - `AdminSystemHealth.tsx` — full Redis metrics, Celery queues, DB pool, integrations, beat task status cards
  - `AdminInsights.tsx` — pattern bar chart, severity progress bars, daily sparkline
  - `AdminBroadcast.tsx` — segment picker, compose, dry-run preview count, confirm → send
  - `AdminAuditLog.tsx` — paginated timeline with action filter
  - `AdminConfig.tsx` — maintenance mode toggle, announcement banner
- **WhatsApp / Gupshup**: Migration plan documented in `docs/WHATSAPP_GUPSHUP_MIGRATION.md`. Code not written yet (blocked on Meta template approval). Day 2 tasks defined: rewrite `whatsapp_service.py`, 4 new `ai_service.py` methods, wire into retention/alert/danger_zone services.
- **Stitch design prompts**: `docs/STITCH_DESIGN_PROMPTS.txt` — detailed prompts for all 18 screens for Google Stitch UI design tool.
- **Pending migrations to apply in Supabase**: 047, 048, 049
- **Config needed**: `ADMIN_JWT_SECRET` env var (any long random string), SMTP for admin OTP emails

---

## Current State (2026-03-17 — Session 22)

### Session 22 Changes
- **Production readiness score**: 8.5 → 8.7/10
- **Circuit breaker alerting**: `sentry_sdk.capture_message` on CLOSED→OPEN in `circuit_breaker_service.py`
- **WhatsApp DLQ**: `MaxRetriesExceededError` Sentry capture with full context in `alert_tasks.py`
- **Integration tests**: 9 → 26 tests (5 new classes: WS JWT auth, event replay, position monitor, CB Sentry, options expiry)
- **Options expiry cleanup**: `_expire_stale_positions()` in `reconciliation_tasks.py` — weekly exact-date + monthly proxy; zeroes OTM worthless positions at 4 AM IST beat run
- **Celery concurrency**: 50 → 100 workers in `celery_app.py`
- **report_tasks parallelised**: sequential per-account loops → `asyncio.gather` batches of 20
- **Procfile**: web / worker / beat process definitions (`backend/Procfile`)
- **P2 items (all 7 done)**:
  - `.env.example` (backend + frontend root) — all vars documented
  - `Dockerfile` (multi-stage python:3.11-slim, non-root) + `docker-compose.yml` (web/worker/beat/redis/db) + `.dockerignore`
  - Maintenance mode: `MAINTENANCE_MODE` env flag → 503 middleware in `main.py` + `/maintenance` route in `App.tsx` + 503 handling in `api.ts`
  - WS reconnect indicator: `isReconnecting` state in `WebSocketContext.tsx` + amber pulsing dot in `Layout.tsx`
  - Skeleton loading states: shadcn `<Skeleton>` in OpenPositionsTable, ClosedTradesTable, SummaryTab, BehaviorTab, TimingTab, TradesTab
  - Empty states: icon + heading + SEBI stat cards in all blank table/list components

---

## Current State (2026-03-16 — Session 21)

### Session 21 Changes
- **D10 complete**: TradeJournalSheet localStorage fallback removed (DB-only save). Coach context builder fixed (was referencing non-existent `entry.lessons` — now uses all structured JournalEntry fields).
- **D11 complete**: Dashboard full-page sync spinner removed. Data loads immediately on broker connect; silent re-fetch on sync completion.
- **Chat**: `handleClearChat` now calls `DELETE /api/coach/session/today` to clear server-side session.
- **coach.py**: Added `DELETE /session/today` endpoint.
- **BlowupShield**: `capital_at_alert` added to `ShieldTimelineItem` TypeScript type (removed `as any` cast).
- **MyPatterns**: `warning` Tailwind tokens replaced with `amber-500` (token not in project theme).
- **Reports**: Renderer type detection fixed — uses `detail.report_type` not `detail.report_data.report_type`.
- **PortfolioRadar**: Negative P&L display bug fixed — was showing `₹500` for `-₹500`.
- **Settings**: Removed unused `useRef` import; fixed hardcoded "at 4:00 PM" string.
- **TRACKER.md**: Dashboard updated to 19/19 FIXED.

---

## Current State (2026-03-13)

### Test Suite
- **296/296 tests passing** (6 files)
- test_db_schema (52), test_dashboard_api (55), test_behavioral_detection (56)
- test_notifications (30), test_trade_classifier (19), test_data_integrity (18)
- test_phase2_services (35), test_behavior_engine (32)

### Git
- Branch: main
- Last commits: Redis Streams event-driven updates, remove all polling
- All work committed cleanly, one commit per logical change

### Migrations Applied in Supabase
- 035: UNIQUE(broker_account_id, order_id) + processed_at on trades ✅
- 036: position_ledger table ✅
- 037: trading_sessions table ✅
- 038: alert state machine columns on risk_alerts ✅
- 039: behavioral event context on behavioral_events ✅
- **040: shadow_behavioral_events** — SKIP (shadow mode removed)
- **041: coach_sessions** ✅ Applied
- **042: portfolio_radar (gtt_tracking, position_alerts_sent)** ✅ Applied
- **043: 7 composite indexes** ✅ Applied
- **044: partial indexes (open positions, active accounts)** ✅ Applied
- **045: Journal structured fields** ✅ Applied
- **046: StrategyGroup + StrategyGroupLeg** ✅ Applied

---

## Phase Status (as of 2026-03-13)

| Phase | Status | Key fact |
|-------|--------|----------|
| 0 | ✅ Done | Sentry, Redis, webhook 500 fix, reconnect fix |
| 1 | ✅ Done | idempotency, Redis locks, EOD reconciliation, /health |
| 2 | ✅ Done | position_ledger + trading_sessions + services + late fill |
| 3 | ✅ Done | BehaviorEngine in production. danger/caution severity. RiskDetector deprecated. |
| 4 | ✅ DONE EARLY | Redis Streams fully implemented. publish_event() dual-write. WS replay. Zero polling. |
| 5 | ✅ Done (6/8) | Items 8 (Prometheus) deferred. Item 3 (WS replay) NOW COMPLETE via Phase 4. |
| 6 | ✅ Done (5/7) | Items 4 (PositionLedger cutover) + 6 (AI split) deferred |

---

## Phase 4 — Redis Streams (COMPLETE as of 2026-03-13)

Implemented ahead of schedule (originally planned for 50+ users).

### What was built:
- `event_bus.py`: dual-write to `stream:events` (global) + `stream:{account_id}` (per-account)
- `publish_event()`: sync, never-raises, called from Celery after each pipeline step
- `start_event_subscriber()`: async loop on server boot, XREAD BLOCK 100ms, dispatches to WebSocket
- `replay_events_for_account()`: XREAD from per-account stream, used on reconnect
- WebSocket endpoint: `?since=last_event_id` triggers replay of all missed events
- `WebSocketContext.tsx`: persists `last_event_id` per account in localStorage
- `useMargins.ts`: one fetch on mount (Redis cache) + WebSocket updates. Zero polling.

### Polling removed:
| Data | Before | After |
|------|--------|-------|
| Trades | 60s interval | WebSocket trade_update event |
| Alerts | 60s interval | WebSocket alert_update event |
| Margins | 30s interval | WebSocket margin_update event |
| Prices | KiteTicker (unchanged) | KiteTicker (unchanged) |
| **Total** | **3 intervals** | **0 intervals** |

### Dual-write design:
- Celery pipeline = primary (processes trades, saves to DB, runs BehaviorEngine)
- Redis Streams = notifications + replay only (never used for processing)
- Celery fails → stream not written (correct — don't record failed events)
- Redis fails → Celery still processes (publish_event is fail-silent)

### At 50+ users (next step for Phase 4):
- Replace per-call Redis connection in publish_event() with connection pool
- Add XREADGROUP consumer groups for reliable delivery (XACK, PEL management)
- See WORKING_NOTES for full explanation

### Remaining polling (intentional/acceptable):
- `PredictiveWarningsCard.tsx` — 5-min interval (AI predictions, not event-driven)
- `DangerZone.tsx` — 30s interval (⚠️ should be converted to event-driven)
- `MyPatterns.tsx` — 30s interval (⚠️ should be converted to event-driven)

---

## Critical "Don't Forget" Items

### Phase 3 cutover still pending
- `BehaviorEngine` is in production (shadow mode removed per git log)
- Script validation (10 test trade scripts) still needs to be run manually
- After validation: confirm RiskDetector fully deprecated

### Phase 4 connection pool (for 50+ users)
- publish_event() opens new TCP connection per call — fine now, breaks at 50+ users
- Fix: shared ConnectionPool in publish_event() + XREADGROUP consumer groups
- Trigger: first time Sentry shows "max clients reached" from Upstash

### Script Validation Plan (post Phase 5-6)
- User executes individual scripts manually, one at a time with delays
- Each script inserts ONE trade with specific characteristics
- User observes dashboard/logs/Sentry after each execution
- Scripts to prepare (NOT execute automatically):
  - Script 1: Single loss trade
  - Script 2: Second loss (approaches consecutive threshold)
  - Script 3: Third loss quickly (triggers consecutive_loss_streak)
  - Script 4: New trade 3min after loss (triggers revenge_trade)
  - Script 5-8: Rapid trades in succession (triggers overtrading_burst)
  - Script 9: Large position after losses (triggers size_escalation/excess_exposure)
  - Script 10: Session P&L tanks (triggers session_meltdown)
- Tag all test trades with `tag = 'TEST_SCENARIO'` for easy cleanup
- Cleanup script: `DELETE FROM trades WHERE tag = 'TEST_SCENARIO'` (cascades)

---

## Architecture Notes

### Live Price Streaming
- `PriceStreamProvider` interface (easy swap to SharedPriceStream post-partnership)
- `PerUserPriceStream`: one KiteTicker per active account
- KiteTicker MODE_LTP (lightest mode)
- `price_stream.start_account()` called from WebSocket `subscribe_positions`
- `price_stream.refresh_subscriptions()` called after every trade fill
- `price_stream.restart_all()` called on server startup

### BehaviorEngine (Shadow Mode)
- 11 patterns implemented (margin_risk intentionally skipped — needs live API)
- Writes to `shadow_behavioral_events` table only
- Never raises (bulletproof try/except)
- Uses `TradingSession.risk_score` for cumulative state
- Behavior states: Stable → Pressure → Tilt Risk → Tilt → Breakdown → Recovery

### EOD Reconciliation
- Runs at 4:00 AM IST daily (not 3-min polling)
- Staggered: 10 accounts/sec (scales to 1000+ users)
- Looks at yesterday's Kite orders vs our DB

### Coach Insight
- Non-blocking: returns fallback immediately, queues LLM generation to Celery
- 15-minute cache in `UserProfile.ai_cache["coach_insight"]`
- Frontend polls once after 5s if `status: "generating"`

### Sentry Config
- `before_send` filter drops: KeyboardInterrupt, SystemExit, CancelledError
- These are normal shutdown events, not bugs
- Traces sample rate: 10%

---

## Known Pending Items

1. **ZERODHA_API_KEY** not set in .env — KiteTicker won't connect without it
2. **Script validation** — 10 test trade scripts, run manually, observe BehaviorEngine alerts
3. **Frontend sync button** — still shows, remove after KiteTicker confirmed working
4. **margin_risk pattern** — intentionally skipped in BehaviorEngine (needs live Kite margin API)
5. **UserProfile.user_id FK** — missing FK from user_profiles to users. Needed for multi-account features. Deferred to multi-broker work.
6. **G6: Some routes use get_current_broker_account_id (not verified)** — needs full route audit. Deferred.
7. **Phase 4 XREADGROUP** — for guaranteed delivery at 50+ users. ConnectionPool already added.

---

## Hotfixes Applied (session 17)

- `instrument_service.py`: missing `timezone` import → NameError on all 5 exchanges (NSE/NFO/BSE/MCX/BFO)
- `shield_service.py`: N+1 query storm (150+ queries per page) → batch-loaded (5 queries total)
- `BlowupShield.tsx`: continuous re-fetch → 5-min module-level cache + visibilitychange guard
- `main.py`: Sentry capturing normal Ctrl+C shutdown as errors → before_send filter added
- `position_ledger_service.py`: missing late-fill (out-of-order) handling → full replay on late arrival

## Multi-broker Architecture (session 18)

- `broker_interface.py`: `BrokerInterface` ABC + `BrokerFactory` + `get_broker_service()` already existed but were dead code
- `ZerodhaClient` now inherits `BrokerInterface` — interface contract enforced at class level
- Added `validate_token()` to `ZerodhaClient` (was missing from interface impl)
- Added `get_ltp()` as optional method on interface (raises NotImplementedError by default)
- `get_instruments()` signature updated: `access_token` now optional param (Kite doesn't need auth for instruments)
- `BrokerFactory.register(BrokerType.ZERODHA, ZerodhaClient)` — factory now live
- `get_broker_service("zerodha")` works and returns `ZerodhaClient` instance
- `dhan_service.py` created — full stub with all abstract methods and key Dhan differences documented
- **To add Dhan**: implement all methods in `dhan_service.py`, uncomment `BrokerFactory.register`, add config keys
- Existing routes unchanged — they still use `zerodha_client` singleton directly (backward-compatible)
- New code should use: `get_broker_service(account.broker_name)` instead of importing `zerodha_client`

## Fixes Applied (session 18) — see docs/FIXES_SESSION_18.md

- `event_bus.py`: per-call Redis TCP connection → shared ConnectionPool (max 10). Zero connections wasted.
- `event_bus.py`: stale docstring ("5 trading days validation" → updated to reflect Phase 4 complete)
- `DangerZone.tsx`: 30s setInterval removed → refetch on lastTradeEvent/lastAlertEvent from WebSocket
- `MyPatterns.tsx`: 30s setInterval removed → refetch on lastTradeEvent/lastAlertEvent from WebSocket
- `zerodha.py`: new broker_account now auto-creates UserProfile immediately (not lazy on first profile access)
- `zerodha.py`: POST /metrics/reset was unprotected → added get_verified_broker_account_id dependency

---

## Audit & Scalability Docs (session 19 — 2026-03-15)

Three permanent analysis documents created:
- **`docs/PRODUCTION_READINESS_AUDIT.md`** — Security, reliability, testing, ops gaps with fix roadmap. Score: 6.4/10.
- **`docs/SCALABILITY_ANALYSIS.md`** — Full 10k-user stress test. Every layer analysed with file:line evidence. Quick wins + 4-stage scaling roadmap.
- **`docs/INFRASTRUCTURE_AND_COST_ANALYSIS.md`** — Deployment options (Railway vs ECS vs K8s), Supabase tiers, Redis costs, WhatsApp cost breakdown, full cost table at 100/500/1k/3k/10k users, practical plan.

### Key findings summary:
- **Breaks at ~200–500 users as-is** (Celery 4 workers, no DB indexes, beat tasks sequential)
- **Quick wins extend to ~2,000–3,000 users** (2 hours of config changes)
- **10k users requires 16 weeks of architectural work**
- **Celery IS used** — it's the task queue that uses Redis as its broker. Not replaceable with "just Redis."
- **Critical blockers (P0):** Celery workers (4→100), missing DB indexes, React Error Boundary, JWT refresh

---

## Portfolio Radar (session 19 — 2026-03-15)

### What was built:
- **Migration 042**: `gtt_tracking` + `position_alerts_sent` tables
- **`position_metrics_service.py`**: breakeven, breakeven_gap, premium_decay_pct, capital_at_risk, DTE — pure math from instruments table + Redis LTP cache
- **`portfolio_concentration_service.py`**: expiry-week grouping, underlying grouping, directional skew, margin utilization — with 4h cooldown dedup
- **`gtt_service.py`**: sync GTT triggers, record honored/overridden outcomes, get_discipline_summary (internal score, NOT shown on frontend)
- **`portfolio_radar_tasks.py`**: Celery Beat every 5 min — compute metrics → analyse concentration → sync GTTs → fire alerts
- **`api/portfolio_radar.py`**: 4 endpoints: /metrics, /concentration, /gtt-discipline, /sync-gtts
- **`pages/PortfolioRadar.tsx`**: Position Clock cards + Concentration panel + GTT Discipline panel
- **`zerodha_service.py`**: added `get_gtt_triggers()` method
- **`trade_tasks.py`**: GTT detection on CLOSE/FLIP — variety='gtt' → honored, variety='regular' with active GTT → overridden
- **`celery_app.py`**: portfolio-radar task registered, every 300s
- **Layout.tsx + App.tsx**: "Radar" nav item added, route /portfolio-radar

### Key design decisions:
- Zero friction: all auto-detected (instruments table + LTP cache + webhook variety field)
- No AI for calculations — pure math only. AI only for natural language alerts (template-based currently)
- `discipline_rate` computed internally but stripped from API response (never shown on frontend)
- WhatsApp + in-app alerts with 4-hour cooldown per condition key
- 3 alert thresholds: >60% same expiry week, >70% same underlying, >80% margin utilization

### Migration needed in Supabase:
- **042**: Run `backend/migrations/042_portfolio_radar.sql`

---

## User Preferences / Non-Negotiables

- Never change a test to make it pass — fix the code
- No commented-out dead code — delete + use git
- Commit per logical change, descriptive messages
- QA-first: validate from user/QA/developer perspective before marking complete
- Script validation: user executes scripts manually one at a time (not automated)
- Phase 4 deferred until 50+ users — don't reopen unless asked
