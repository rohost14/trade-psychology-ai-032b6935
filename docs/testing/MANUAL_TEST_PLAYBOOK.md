# Manual Test Playbook: Behavioral Patterns & Alerts

> **Purpose:** Validate every behavioral pattern fires correctly with real market data.
> **When:** During live market hours (9:15 AM - 3:30 PM IST).
> **Instruments:** Use liquid F&O — NIFTY, BANKNIFTY, or stock futures.
> **Caution:** Use minimum lot sizes. This is a testing session, not a trading session.

---

## Table of Contents

1. [Pre-Flight Checklist](#1-pre-flight-checklist)
2. [Quick-Fire Tests (5 min each)](#2-quick-fire-tests-5-min-each)
3. [Session Tests (30-60 min)](#3-session-tests-30-60-min)
4. [Multi-Day Tests (3+ days)](#4-multi-day-tests-3-days)
5. [Verification Reference](#5-verification-reference)
6. [Known Gaps & Limitations](#6-known-gaps--limitations)
7. [Pattern Quick-Reference Table](#7-pattern-quick-reference-table)

---

## 1. Pre-Flight Checklist

### Services Running

| Service | Command | Verify |
|---------|---------|--------|
| Backend | `cd backend && uvicorn app.main:app --reload --port 8000` | `curl http://localhost:8000/docs` returns Swagger UI |
| Frontend | `npm run dev` | `http://localhost:8080` loads dashboard |
| Celery (optional) | `cd backend && celery -A app.core.celery_app worker` | Only needed for scheduled tasks |

### Broker Connection

- [ ] Open Settings page, Zerodha shows "Connected"
- [ ] Token is fresh (connected today — tokens expire at midnight)
- [ ] Run initial sync: click "Sync" button on dashboard
- [ ] Verify sync completes without errors (check browser console)

### Database Has Data

Run these checks in browser DevTools console or via API:

```bash
# Check CompletedTrade records exist
curl http://localhost:8000/api/trades/completed?limit=5

# Check risk state endpoint works
curl http://localhost:8000/api/risk/state

# Check behavioral analysis endpoint works
curl http://localhost:8000/api/behavioral/analysis?time_window_days=1
```

- [ ] CompletedTrade records returned (not empty array)
- [ ] Risk state returns valid JSON with `risk_state` field
- [ ] Behavioral analysis returns valid JSON with `patterns_detected` field

### Browser Setup

- [ ] Open browser DevTools (F12) → Console tab (to see frontend pattern logs)
- [ ] Open Network tab → filter by `XHR` (to monitor API calls)
- [ ] Keep a second tab open at `http://localhost:8000/docs` for direct API testing

### Capital Configuration

- [ ] Note your configured capital amount (used for position sizing and drawdown calculations)
- [ ] Note your daily loss limit (used for DangerZone loss limit triggers)
- [ ] If not configured, set them in Settings → Trading Rules

---

## 2. Quick-Fire Tests (5 min each)

These patterns need only 2-5 trades and trigger within minutes.

---

### QF-1: Revenge Trading (Frontend + Backend)

**What fires:** Frontend `revenge_trading`, Backend BehavioralEvaluator `REVENGE_TRADING`, RiskDetector `revenge_sizing`

**Steps:**
1. Enter any F&O position (e.g., BUY NIFTY FUT 1 lot)
2. Exit at a loss of at least **Rs 500** (let it move against you, or use a market order)
3. **Within 3 minutes**, enter a new position with **double the quantity** (e.g., 2 lots)
4. Click **Sync** on dashboard

**Expected Results:**

| System | Pattern | Severity | How to Verify |
|--------|---------|----------|---------------|
| Frontend | `revenge_trading` | Medium-High | Toast notification on dashboard; check RecentAlertsCard |
| BehavioralEvaluator | `REVENGE_TRADING` | HIGH | `GET /api/risk/alerts?hours=1` — look for `event_type: REVENGE_TRADING` |
| RiskDetector | `revenge_sizing` | DANGER | `GET /api/risk/state` — `active_patterns` includes `revenge_sizing` |

**Key thresholds:**
- Frontend triggers at: loss >= Rs 500, re-entry within 5 min
- BehavioralEvaluator triggers at: any loss, re-entry within 15 min, increased size
- RiskDetector triggers at: any loss, re-entry within 15 min, size >= 1.5x previous

**Pass criteria:**
- [ ] Frontend toast appears with "Revenge Trading" label
- [ ] RecentAlertsCard shows the alert
- [ ] `/api/risk/alerts?hours=1` contains at least 1 revenge-type alert
- [ ] `/api/risk/state` shows elevated risk (caution or danger)

---

### QF-2: Overtrading (Frontend + Backend)

**What fires:** Frontend `overtrading`, Backend BehavioralEvaluator `OVERTRADING`, RiskDetector `overtrading`

**Steps:**
1. Execute **5 rapid trades** within 15 minutes (buy/sell minimum lots, different symbols OK)
   - Trade 1: BUY NIFTY FUT → immediate exit
   - Trade 2: BUY BANKNIFTY FUT → immediate exit
   - Trade 3: BUY NIFTY FUT → immediate exit
   - Trade 4: BUY BANKNIFTY FUT → immediate exit
   - Trade 5: BUY NIFTY FUT → hold or exit
2. Click **Sync** on dashboard

**Expected Results:**

| System | Pattern | Severity | Threshold |
|--------|---------|----------|-----------|
| Frontend | `overtrading` | Medium | 5 trades in 30 min |
| BehavioralEvaluator | `OVERTRADING` | LOW | 5 trades in 15 min |
| RiskDetector | `overtrading` | CAUTION | 5-6 trades in 15 min |

**To escalate severity:**
- 7+ trades in 15 min → Frontend HIGH, BehavioralEvaluator MEDIUM
- 8+ trades in 15 min → BehavioralEvaluator HIGH, RiskDetector DANGER

**Pass criteria:**
- [ ] Frontend toast shows "Overtrading" alert
- [ ] `/api/risk/alerts?hours=1` contains `pattern_type: overtrading`
- [ ] `/api/risk/state` reflects elevated risk

---

### QF-3: Position Sizing (Frontend Only)

**What fires:** Frontend `position_sizing`

**Steps:**
1. Calculate 5% of your configured capital (e.g., Rs 5,000 on Rs 1,00,000 capital)
2. Enter a position where `price x quantity` exceeds that threshold
   - Example: If NIFTY FUT at Rs 24,000 and lot size 25, one lot = Rs 6,00,000 notional
   - Even 1 lot will likely trigger this on small capital
3. Click **Sync**

**Expected Results:**

| Threshold | Severity |
|-----------|----------|
| 5-10% of capital | Medium |
| 10-20% of capital | High |
| 20%+ of capital | Critical |

**Pass criteria:**
- [ ] Frontend toast shows "Position Sizing" with percentage
- [ ] Alert description shows exact percentage of capital used

---

### QF-4: FOMO Entry — Market Opening (Backend)

**What fires:** BehavioralEvaluator `FOMO_ENTRY`, RiskDetector `fomo`

**Steps:**
1. **At exactly 9:15 AM IST** (market open), place **3+ trades within 5 minutes** (by 9:20 AM)
2. Any instruments, any direction
3. Click **Sync** after 9:20 AM

**Expected Results:**

| System | Pattern | Severity |
|--------|---------|----------|
| BehavioralEvaluator | `FOMO_ENTRY` | LOW (3 trades) / MEDIUM (4+ trades) |
| RiskDetector | `fomo` | CAUTION |

**Key detail:** Detection checks IST hour=9 and minute<20. The trades must have timestamps in the 9:15-9:20 window.

**Pass criteria:**
- [ ] `/api/risk/alerts?hours=1` contains `pattern_type: fomo`
- [ ] Alert details show `opening_trade_count` matching your trade count

---

### QF-5: Same Instrument Chasing (Frontend)

**What fires:** Frontend `same_instrument_chasing`

**Steps:**
1. Take a position on NIFTY FUT → exit at a loss
2. Take another position on NIFTY FUT → exit at a loss
3. Click **Sync**

**Expected Results:**

| Losses on Same Symbol | Severity |
|----------------------|----------|
| 2 losses | Medium |
| 3 losses | High |
| 4+ losses | Critical |

**Pass criteria:**
- [ ] Frontend toast shows "Same Instrument Chasing" with the symbol name
- [ ] Alert description mentions the specific symbol

---

## 3. Session Tests (30-60 min)

These tests need 10-20+ trades across a trading session. Plan for a full morning or afternoon.

---

### ST-1: Loss Aversion Detection

**What fires:** Frontend `loss_aversion`, BehavioralAnalysisService `HopeDenialPattern`

**Target:** Generate a session with average loss significantly larger than average win.

**Steps:**
1. Execute at least **10 trades** with the following profile:
   - ~5 winners: cut quickly at Rs 200-500 profit each
   - ~5 losers: hold longer, let them hit Rs 800-1500 loss each
2. The key is that your average loss size should be **>1.5x your average win size**
3. Click **Sync**

**Expected Results:**

| Ratio (Avg Loss / Avg Win) | Frontend Severity |
|----------------------------|-------------------|
| 1.5-2.0x | Medium |
| 2.0-3.0x | High |
| 3.0x+ | Critical |

**Verification:**
```
GET /api/behavioral/analysis?time_window_days=1
```
Look for `HopeDenialPattern` in `patterns_detected` (avg loss > 1.5x avg win).

**Pass criteria:**
- [ ] Frontend `loss_aversion` alert shows with correct ratio
- [ ] `/api/behavioral/analysis` detects `HopeDenialPattern`
- [ ] `estimated_cost` (frontend) shows the excess loss amount

---

### ST-2: Consecutive Losses Escalation

**What fires:** Frontend `consecutive_losses`, RiskDetector `consecutive_loss`, DangerZone escalation

**Target:** Build a streak of consecutive losing trades and watch severity escalate.

**Steps:**
1. Take 5 trades sequentially, all resulting in losses (exit each at a small loss)
2. Click **Sync** after each trade to watch escalation in real-time
3. Note the behavior at each stage:

| After Trade # | Frontend Severity | RiskDetector | DangerZone |
|--------------|-------------------|--------------|------------|
| Trade 3 (3 losses) | Medium | CAUTION | WARNING |
| Trade 4 (4 losses) | High | CAUTION | DANGER + soft cooldown |
| Trade 5 (5 losses) | Critical | DANGER | CRITICAL + hard cooldown |

**Verification after each sync:**
```bash
# Frontend: check RecentAlertsCard severity progression
# Backend:
curl http://localhost:8000/api/risk/state
curl http://localhost:8000/api/risk/alerts?hours=1
curl http://localhost:8000/api/danger-zone/status
```

**Pass criteria:**
- [ ] Frontend severity escalates: Medium → High → Critical
- [ ] RiskDetector creates alerts at 3 and 5 consecutive losses
- [ ] DangerZone level progresses: WARNING → DANGER → CRITICAL
- [ ] Cooldown activates at DANGER (soft, skippable) and CRITICAL (hard, mandatory)
- [ ] `/api/danger-zone/status` shows `cooldown_active: true` and `cooldown_remaining_minutes`

---

### ST-3: Tilt Spiral Detection

**What fires:** BehavioralEvaluator `TILT_SPIRAL`, RiskDetector `tilt_loss_spiral`

**Target:** Simulate classic tilt behavior — increasing position sizes while losing.

**Steps:**
1. Trade 1: BUY 1 lot NIFTY FUT → exit at loss
2. Trade 2: BUY 1 lot NIFTY FUT → exit at loss
3. Trade 3: BUY 2 lots NIFTY FUT → exit at loss (size increase)
4. Trade 4: BUY 3 lots NIFTY FUT → exit at loss (size increase again)
5. Click **Sync**

**The key triggers:**
- 3+ consecutive losses (BehavioralEvaluator needs 4+ CompletedTrades)
- Escalating position sizes
- Cumulative P&L negative

**Expected Results:**

| System | Pattern | Severity |
|--------|---------|----------|
| BehavioralEvaluator | `TILT_SPIRAL` | HIGH (4+ losses, 3+ size increases) |
| RiskDetector | `tilt_loss_spiral` | DANGER (triggers cooldown) |
| DangerZone | Level DANGER+ | Soft/hard cooldown |

**Pass criteria:**
- [ ] `/api/risk/alerts?hours=1` shows `tilt_loss_spiral` DANGER alert
- [ ] Alert details contain `size_trend: "escalating"` and `consecutive_losses` count
- [ ] DangerZone shows elevated level with cooldown

---

### ST-4: Capital Drawdown (Frontend)

**What fires:** Frontend `capital_drawdown`

**Target:** Accumulate session losses exceeding 10% of capital.

**Steps:**
1. Trade throughout the session, accumulating net losses
2. Monitor after each sync when total session loss crosses these thresholds:

| Session Loss % of Capital | Severity |
|--------------------------|----------|
| 10-25% | Medium |
| 25-40% | High |
| 40%+ | Critical |

**Example:** On Rs 1,00,000 capital, lose Rs 12,000 total → Medium (12% drawdown).

**Pass criteria:**
- [ ] Frontend toast shows "Capital Drawdown" with percentage
- [ ] Description shows rupee amount and percentage

---

### ST-5: DangerZone Loss Limit Progression

**What fires:** DangerZone loss limit triggers at 70%, 85%, and 100%

**Target:** Watch DangerZone escalate as you approach your daily loss limit.

**Steps:**
1. Note your daily loss limit (check Settings or `/api/danger-zone/thresholds`)
2. Accumulate losses and sync after each milestone:

| Daily Loss Used % | DangerZone Level | Intervention |
|-------------------|-----------------|--------------|
| 70-84% | WARNING | In-app message only |
| 85-99% | DANGER | Push notification |
| 100%+ | CRITICAL | Hard cooldown + WhatsApp (if configured) |

**Verification:**
```bash
curl http://localhost:8000/api/danger-zone/status
```

Check `daily_loss_used_percent`, `level`, `intervention`, `cooldown_active`.

**Pass criteria:**
- [ ] Status progresses through WARNING → DANGER → CRITICAL
- [ ] `daily_loss_used_percent` matches your calculated percentage
- [ ] Intervention type escalates appropriately
- [ ] At CRITICAL: `cooldown_active: true`

---

### ST-6: All-Loss Session (Frontend)

**What fires:** Frontend `all_loss_session`

**Target:** Complete a session where every single trade is a loser.

**Steps:**
1. Execute at least **3 trades**, all resulting in losses (no winners at all)
2. Click **Sync**

| Total Losing Trades (0 wins) | Severity |
|------------------------------|----------|
| 3 trades | Medium |
| 5 trades | High |
| 7+ trades | Critical |

**Pass criteria:**
- [ ] Frontend toast shows "All-Loss Session"
- [ ] Description shows trade count and total loss
- [ ] Recommendation suggests stopping for the day

---

### ST-7: Loss Chasing (Backend)

**What fires:** BehavioralEvaluator `LOSS_CHASING`

**Target:** Lose on a symbol, then immediately re-enter the same symbol.

**Steps:**
1. BUY NIFTY FUT 1 lot → exit at loss (e.g., Rs 800 loss)
2. **Within 3 minutes**, BUY NIFTY FUT again (same symbol, same direction)
3. Click **Sync**

**Expected:** BehavioralEvaluator emits `LOSS_CHASING` with MEDIUM severity (gap <= 3 min).

**Verification:**
```
GET /api/risk/alerts?hours=1
```
Look for `event_type: LOSS_CHASING` with `context.symbol`, `context.previous_loss`, `context.gap_minutes`.

**Pass criteria:**
- [ ] Alert exists with correct symbol
- [ ] `previous_loss` is negative
- [ ] `gap_minutes` matches actual time between trades

---

### ST-8: Cooldown Escalation

**What fires:** DangerZone escalation system

**Target:** Trigger the same violation multiple times to test cooldown escalation.

**Steps:**
1. Trigger `consecutive_loss_danger` (3 consecutive losses) → expect 15-min cooldown
2. Wait for cooldown to expire
3. Trigger again (3 more consecutive losses) → expect **30-min** cooldown (escalated)
4. Wait for cooldown to expire
5. Trigger again → expect **60-min** cooldown (escalated again)

**Verification after each trigger:**
```
GET /api/danger-zone/escalation-status?trigger_reason=consecutive_loss_danger
```

| Violation # | Expected Cooldown | Escalation Level |
|-------------|------------------|-----------------|
| 1st | 15 min | 0 |
| 2nd (same day) | 30 min | 1 |
| 3rd | 60 min | 2 |
| 4th+ | 60 min | 2 (maxed) |

**Pass criteria:**
- [ ] `violation_count_24h` increments with each trigger
- [ ] `current_duration_minutes` doubles: 15 → 30 → 60
- [ ] `at_max_escalation` is `true` at level 2

---

## 4. Multi-Day Tests (3+ days)

These patterns analyze behavior across multiple trading days. Execute them over 3+ separate trading sessions.

---

### MD-1: Profit Give-Back Pattern

**What fires:** BehavioralAnalysisService `ProfitGiveBackPattern`

**Target:** On 2+ days, build up profits then give them all back.

**Steps (repeat on 2 separate days):**
1. Morning: take 3-4 winning trades, build session profit to Rs 1,500+
2. Afternoon: take losing trades until session P&L drops to Rs 300 or less (below 30% of peak)
3. Sync at end of day

**Detection logic:** Session peak > Rs 100 AND final P&L <= 30% of peak → "give-back day". Needs 2+ such days.

**Verification after day 2:**
```
GET /api/behavioral/analysis?time_window_days=7
```
Look for `ProfitGiveBackPattern` in `patterns_detected`.

**Pass criteria:**
- [ ] Pattern detected with severity `high`
- [ ] Description mentions the total amount given back
- [ ] Both give-back days counted

---

### MD-2: End-of-Day Rush

**What fires:** BehavioralAnalysisService `EndOfDayRushPattern`

**Target:** On 2+ days, place 30%+ of your trades after 3:00 PM IST.

**Steps (repeat on 2 separate days):**
1. Trade lightly in the morning (e.g., 3-4 trades before 3 PM)
2. After 3:00 PM: execute 2-3 more trades (so 30%+ of daily trades are late)
3. Sync at end of day

**Verification after day 2:**
```
GET /api/behavioral/analysis?time_window_days=7
```
Look for `EndOfDayRushPattern`.

**Pass criteria:**
- [ ] Pattern detected with severity `medium`
- [ ] At least 2 "rush days" counted

---

### MD-3: Expiry Day Gambling

**What fires:** BehavioralAnalysisService `ExpiryDayGamblingPattern`

**Target:** Trade significantly more on weekly expiry (Thursday) vs other days.

**Steps:**
1. On 2-3 non-expiry days: trade moderately (e.g., 4-5 trades per day)
2. On expiry Thursday: trade heavily (e.g., 10+ trades)
3. Ratio of avg expiry trades to avg non-expiry trades should be >= 1.5x

**Verification after expiry day:**
```
GET /api/behavioral/analysis?time_window_days=7
```
Look for `ExpiryDayGamblingPattern`.

| Ratio | Severity |
|-------|----------|
| 1.5-2.0x | Medium |
| 2.0x+ | High |

**Pass criteria:**
- [ ] Pattern detected on sufficient data
- [ ] Severity matches ratio threshold

---

### MD-4: Emotional Looping

**What fires:** BehavioralAnalysisService `EmotionalLoopingPattern`

**Target:** Across 3+ days, repeatedly build up gains then spiral them away.

**Criteria (any of):**
- 3+ days of giving back gains (see MD-1)
- 2+ give-back days AND 2+ tilt spiral days

This is a **compound pattern** that builds on simpler ones. It will fire only if the underlying patterns (ProfitGiveBack, TiltLossSpiral) are also detected.

**Verification:**
```
GET /api/behavioral/analysis?time_window_days=14
```
Look for `EmotionalLoopingPattern` with severity `critical`.

---

### MD-5: Disposition Effect

**What fires:** BehavioralAnalysisService `DispositionEffectPattern`

**Target:** Over 10+ trades, hold winners for much shorter duration than losers.

**Steps (across multiple days):**
1. When a trade goes profitable: exit quickly (within 15-30 min)
2. When a trade goes negative: hold it for 60+ min before exiting
3. Build up 10+ trades with this pattern

**Detection:** Avg winner duration < 0.5x avg loser duration

**Example:** Winners held 20 min average, losers held 60 min average → ratio 0.33 → Detected.

**Verification:**
```
GET /api/behavioral/analysis?time_window_days=14
```
Look for `DispositionEffectPattern` with severity `high`.

**Pass criteria:**
- [ ] Duration ratio calculated correctly
- [ ] Pattern description shows both averages

---

### MD-6: Concentration Risk

**What fires:** BehavioralAnalysisService `ConcentrationRiskPattern`

**Target:** Over 10+ trades, place 60%+ on a single instrument.

**Steps:**
1. Over multiple days, trade primarily one instrument (e.g., NIFTY FUT)
2. Out of 15+ total trades, ensure 10+ are on the same symbol

| Concentration | Severity |
|--------------|----------|
| 60-75% | Low |
| 75%+ | Medium |

**Verification:**
```
GET /api/behavioral/analysis?time_window_days=14
```
Look for `ConcentrationRiskPattern`.

---

### MD-7: Max Daily Loss Breach

**What fires:** BehavioralAnalysisService `MaxDailyLossBreachPattern`

**Target:** Have at least one day where loss exceeds 2x your average daily loss.

**Steps:**
1. Trade for 3+ days, with modest losses on most days (e.g., Rs 500-1000/day)
2. On one day, let losses run to 2x+ your average (e.g., Rs 2,500 loss)
3. Need 10+ trades across 3+ losing days

**Verification:**
```
GET /api/behavioral/analysis?time_window_days=14
```
Look for `MaxDailyLossBreachPattern` with severity `critical`.

---

## 5. Verification Reference

### API Endpoints Quick Reference

| Endpoint | What It Returns | Use For |
|----------|----------------|---------|
| `GET /api/risk/state` | Current risk level, active patterns | RiskDetector state |
| `GET /api/risk/alerts?hours=24` | All risk alerts in window | RiskDetector + BehavioralEvaluator alerts |
| `POST /api/risk/alerts/{id}/acknowledge` | Acknowledge an alert | Clearing alerts |
| `GET /api/behavioral/analysis?time_window_days=N` | Full 35-pattern analysis | BehavioralAnalysisService |
| `GET /api/behavioral/patterns` | Detected patterns only | Quick pattern check |
| `GET /api/behavioral/trade-tags` | Per-trade behavioral tags | Checking individual trade labels |
| `GET /api/danger-zone/status` | Danger level, cooldown, triggers | DangerZone state |
| `GET /api/danger-zone/thresholds` | Current trigger thresholds | Verifying configuration |
| `GET /api/danger-zone/escalation-status?trigger_reason=X` | Escalation level for a trigger | Cooldown escalation testing |
| `GET /api/danger-zone/summary` | Full summary with history | Comprehensive DangerZone review |
| `POST /api/danger-zone/trigger-intervention` | Manually trigger intervention | Force-testing interventions |
| `POST /api/alerts/test` | Send test WhatsApp/notification | Verifying notification pipeline |
| `GET /api/trades/completed?limit=N` | Recent completed trades | Checking CompletedTrade data |

### Frontend Verification

| Check | How |
|-------|-----|
| Toast notifications | Watch bottom-right of dashboard after sync |
| RecentAlertsCard | Dashboard → "Recent Alerts" card |
| Pattern details | Click on any alert to expand details |
| AlertContext state | DevTools Console → `window.__ALERT_CONTEXT__` (if exposed) or React DevTools → AlertContext |
| Network calls | DevTools Network tab → filter `behavioral\|risk\|danger` |

### Database Direct Checks (via Supabase Dashboard or psql)

```sql
-- Check CompletedTrade records
SELECT id, tradingsymbol, realized_pnl, entry_time, exit_time
FROM completed_trades
ORDER BY exit_time DESC
LIMIT 10;

-- Check BehavioralEvent records (from BehavioralEvaluator)
SELECT id, event_type, severity, confidence, context, detected_at
FROM behavioral_events
ORDER BY detected_at DESC
LIMIT 10;

-- Check RiskAlert records (from RiskDetector)
SELECT id, pattern_type, severity, message, details, detected_at, acknowledged_at
FROM risk_alerts
ORDER BY detected_at DESC
LIMIT 10;

-- Check Cooldown records
SELECT id, trigger_reason, started_at, expires_at, is_hard, was_skipped
FROM cooldowns
ORDER BY started_at DESC
LIMIT 5;
```

---

## 6. Known Gaps & Limitations

### Cannot Test Yet

| Feature | Why | Status |
|---------|-----|--------|
| Push notifications | Service worker + browser permission needed; not wired from sync pipeline | Phases 5-6 pending |
| WhatsApp alerts (full) | Requires Twilio credentials + guardian phone configured | Can test with `POST /api/alerts/test` if Twilio is set up |
| Celery scheduled tasks | Needs Redis (Upstash) + Celery worker running | Optional; sync works without it |
| Multi-user scenarios | Single-user testing only | N/A for manual testing |

### Testing Constraints

| Constraint | Impact | Workaround |
|-----------|--------|------------|
| Market hours only | Can only test during 9:15 AM - 3:30 PM IST Mon-Fri | Plan test sessions in advance |
| Real money | All trades use real capital | Use minimum lot sizes; budget Rs 2,000-5,000 for testing losses |
| Zerodha rate limits | API calls are rate-limited | Wait 1-2 seconds between syncs |
| Token expiry | Kite tokens expire at midnight IST | Re-connect each morning |
| CompletedTrade lag | Positions must close before CompletedTrade record appears | Use quick entries/exits; don't hold positions overnight for same-day testing |

### Data Dependency Notes

**Critical:** P&L-dependent patterns use `CompletedTrade.realized_pnl`, NOT `Trade.pnl` (which is always 0.0 for raw fills).

| Data Source | Used By | What It Contains |
|------------|---------|------------------|
| `CompletedTrade` | BehavioralEvaluator (revenge, tilt, loss chasing), RiskDetector (consecutive loss, revenge sizing, tilt), all 35 BehavioralAnalysisService patterns | Full position lifecycle with real P&L |
| `Trade` | BehavioralEvaluator (overtrading, FOMO), RiskDetector (overtrading, FOMO) | Raw order fills, no P&L |

**Implication:** For P&L-dependent patterns to fire, you must have **closed positions** (not just open fills). Enter and exit within the test window.

### Minimum Data Requirements

| Pattern Group | Minimum Trades | Minimum Days |
|--------------|---------------|--------------|
| Frontend basic (overtrading, revenge) | 2-5 | 1 |
| Frontend statistical (loss aversion) | 5+ (winners + losers) | 1 |
| BehavioralEvaluator (real-time) | 2-5 | 1 |
| BehavioralAnalysisService (basic) | 5-10 | 1 |
| BehavioralAnalysisService (complex) | 15+ | 1 |
| BehavioralAnalysisService (compound) | 20+ | 3+ |
| Disposition Effect | 10+ with duration data | 3+ |
| Expiry Day Gambling | 10+ across expiry and non-expiry | 5+ (at least 1 expiry) |
| Emotional Looping | 20+ | 3+ |

---

## 7. Pattern Quick-Reference Table

### All 41 Patterns by Detection Layer

#### Frontend Patterns (8) — `src/lib/patternDetector.ts`

| # | Pattern | Trigger | Min Trades | Severity Range |
|---|---------|---------|-----------|----------------|
| 1 | `overtrading` | 5+ trades in 30 min | 5 | Med / High / Crit |
| 2 | `revenge_trading` | Entry within 5 min of loss >= Rs 500 | 2 | Med / High / Crit |
| 3 | `loss_aversion` | Avg loss > 1.5x avg win | 5 | Med / High / Crit |
| 4 | `position_sizing` | Position > 5% of capital | 1 | Med / High / Crit |
| 5 | `consecutive_losses` | 3+ consecutive losing exits | 3 | Med / High / Crit |
| 6 | `capital_drawdown` | Session loss >= 10% of capital | 1 | Med / High / Crit |
| 7 | `same_instrument_chasing` | 2+ losses on same symbol | 2 | Med / High / Crit |
| 8 | `all_loss_session` | 3+ exits, 0 winners | 3 | Med / High / Crit |

#### Backend BehavioralEvaluator (5) — Real-time on sync

| # | Event Type | Trigger | Dedup Window |
|---|-----------|---------|-------------|
| 9 | `REVENGE_TRADING` | Entry within 15 min of completed loss, increased size | 60 min |
| 10 | `OVERTRADING` | 5+ trades in 15 min | 60 min |
| 11 | `TILT_SPIRAL` | Escalating sizes + cumulative loss + consecutive losses | 60 min |
| 12 | `FOMO_ENTRY` | 3+ trades in first 5 min OR 3+ same-direction on same symbol in 5 min | 60 min |
| 13 | `LOSS_CHASING` | Re-entry on same symbol within 10 min of loss | 60 min |

#### Backend RiskDetector (5) — Real-time on sync

| # | Pattern Type | Trigger | Severity |
|---|-------------|---------|----------|
| 14 | `consecutive_loss` | 3+ consecutive completed losses | CAUTION (3-4) / DANGER (5+) |
| 15 | `revenge_sizing` | Size >= 1.5x previous within 15 min of loss | DANGER |
| 16 | `overtrading` | 5+ trades in 15 min | CAUTION (5-6) / DANGER (7+) |
| 17 | `fomo` | 3+ trades in opening 5 min OR 3+ same-direction chasing | CAUTION |
| 18 | `tilt_loss_spiral` | 3+ losses + escalating sizes + net negative | DANGER |

#### Backend BehavioralAnalysisService (27 base + 8 enhanced = 35)

**Primary Biases (4):**

| # | Pattern | Category | Trigger | Severity |
|---|---------|----------|---------|----------|
| 19 | RevengeTradingPattern | impulse | Entry within 15 min of loss | High |
| 20 | NoCooldownPattern | impulse | Entry within 5 min of loss | High |
| 21 | AfterProfitOverconfidencePattern | overconfidence | 1.5x+ size after win | Medium |
| 22 | StopLossDisciplinePattern | discipline | max_loss < 2.5x avg_loss | Positive |

**Behavioral Patterns (5):**

| # | Pattern | Trigger | Severity |
|---|---------|---------|----------|
| 23 | OvertradingPattern | >10 trades/day OR 5+ in 1 hour | High / Medium |
| 24 | MartingaleBehaviorPattern | 1.8x+ size after loss | Critical |
| 25 | InconsistentSizingPattern | Size coefficient of variation > 0.5 | Medium |
| 26 | TimeOfDayPattern | Win rate <40% in specific windows | Medium |
| 27 | HopeDenialPattern | Avg loss > 1.5x avg win | High |

**Cognitive Biases (5):**

| # | Pattern | Trigger | Severity |
|---|---------|---------|----------|
| 28 | RecencyBiasPattern | 3+ same-direction repeats after consecutive wins | Medium |
| 29 | LossNormalizationPattern | 55%+ loss rate, small consistent losses | High |
| 30 | StrategyDriftPattern | 50%+ mid-session size/frequency change | Medium |
| 31 | EmotionalExitPatternEnhanced | Avg loss% > 1.5x avg win%, win <2% | Medium |
| 32 | ChopZoneAddictionPattern | 15+ trades, 40%+ direction changes, flat P&L | Medium |

**Compound States (3):**

| # | Pattern | Trigger | Severity |
|---|---------|---------|----------|
| 33 | TiltLossSpiralPattern | 4+ consecutive losses | Critical |
| 34 | FalseRecoveryChasePattern | 3+ recovery attempts during drawdown | Critical |
| 35 | EmotionalLoopingPattern | 3+ give-back days OR 2+ give-back + 2+ spirals | Critical |

**Phase A Enhanced (10):**

| # | Pattern | Category | Trigger | Severity |
|---|---------|----------|---------|----------|
| 36 | DispositionEffectPattern | fear | Winners held < 0.5x duration of losers | High |
| 37 | BreakevenObsessionPattern | fear | 3+ exits within +/-0.5% of entry | Med / Low |
| 38 | AddingToLosersPattern | impulse | 2+ adds to losing same-symbol position | Critical |
| 39 | ProfitGiveBackPattern | discipline | 2+ days ending at <=30% of peak | High |
| 40 | EndOfDayRushPattern | impulse | 30%+ trades after 3 PM on 2+ days | Medium |
| 41 | ExpiryDayGamblingPattern | impulse | 1.5x+ trades on expiry vs normal | High / Med |
| 42 | BoredomTradingPattern | compulsion | 5+ small/short/negligible-P&L trades | Medium |
| 43 | ConcentrationRiskPattern | discipline | 60%+ trades on single instrument | Med / Low |
| 44 | MaxDailyLossBreachPattern | discipline | Any day loss > 2x avg daily loss | Critical |
| 45 | GamblersFallacyPattern | impulse | 2+ same-direction entries after 3 same-direction losses | High |

#### DangerZone Triggers (6)

| # | Trigger | Levels |
|---|---------|--------|
| 46 | Loss limit breach | WARNING (70%) / DANGER (85%) / CRITICAL (100%) |
| 47 | Consecutive losses | WARNING (2) / DANGER (3) / CRITICAL (5) |
| 48 | Overtrading (15-min) | WARNING (5) / DANGER (8) |
| 49 | Overtrading (1-hour) | WARNING (15) / DANGER (25) |
| 50 | Danger-tier patterns | DANGER (revenge, tilt, fomo, loss chasing) |
| 51 | Caution-tier patterns | CAUTION (overconfidence, anchoring, round number bias) |

---

## Test Result Tracking

Use this checklist to track results across test sessions:

### Quick-Fire Results

| Test | Date | Result | Notes |
|------|------|--------|-------|
| QF-1: Revenge Trading | | Pass / Fail | |
| QF-2: Overtrading | | Pass / Fail | |
| QF-3: Position Sizing | | Pass / Fail | |
| QF-4: FOMO Opening | | Pass / Fail | |
| QF-5: Same Instrument Chasing | | Pass / Fail | |

### Session Test Results

| Test | Date | Result | Notes |
|------|------|--------|-------|
| ST-1: Loss Aversion | | Pass / Fail | |
| ST-2: Consecutive Losses Escalation | | Pass / Fail | |
| ST-3: Tilt Spiral | | Pass / Fail | |
| ST-4: Capital Drawdown | | Pass / Fail | |
| ST-5: DangerZone Loss Limit | | Pass / Fail | |
| ST-6: All-Loss Session | | Pass / Fail | |
| ST-7: Loss Chasing | | Pass / Fail | |
| ST-8: Cooldown Escalation | | Pass / Fail | |

### Multi-Day Results

| Test | Dates | Result | Notes |
|------|-------|--------|-------|
| MD-1: Profit Give-Back | | Pass / Fail | |
| MD-2: End-of-Day Rush | | Pass / Fail | |
| MD-3: Expiry Day Gambling | | Pass / Fail | |
| MD-4: Emotional Looping | | Pass / Fail | |
| MD-5: Disposition Effect | | Pass / Fail | |
| MD-6: Concentration Risk | | Pass / Fail | |
| MD-7: Max Daily Loss Breach | | Pass / Fail | |

---

## Recommended Test Order

**Day 1 (first market session):**
1. Pre-flight checklist
2. QF-1 through QF-5 (quick-fire tests, ~30 min total)
3. ST-2: Consecutive Losses Escalation (validates core risk system)
4. ST-5: DangerZone Loss Limit (validates intervention system)

**Day 2:**
1. ST-1: Loss Aversion
2. ST-3: Tilt Spiral
3. ST-7: Loss Chasing
4. ST-6: All-Loss Session (combine with ST-2 — same session can test both)

**Day 3:**
1. ST-4: Capital Drawdown
2. ST-8: Cooldown Escalation
3. Begin MD-1: Profit Give-Back (morning: win, afternoon: give back)

**Days 4-7:**
1. Continue multi-day tests (MD-1 through MD-7)
2. MD-3 specifically needs a Thursday for expiry testing

**After all tests pass:**
1. Run one "clean session" — trade normally, verify no false positives on disciplined trading
2. Verify the positive pattern (`StopLossDisciplinePattern`) fires when you trade well
