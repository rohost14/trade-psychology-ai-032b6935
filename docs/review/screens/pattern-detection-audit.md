# Pattern Detection Pipeline — Full Audit

**Date:** 2026-02-24 (Session 8)
**Status:** CRITICAL — 22 of 31 patterns broken, notifications dead, DangerZone disconnected

---

## Executive Summary

The behavioral pattern detection system — the CORE feature of TradeMentor AI — is fundamentally broken. A trader lost 50% of capital (Rs.11k to Rs.5k) across 5 consecutive losing trades, and the system only flagged "Position Size Warning" and 1 "Revenge Trading" alert. It missed: consecutive losses, capital drawdown, same-instrument chasing, all-loss session, overtrading, tilt spiral.

**Root cause:** `Trade.pnl` is always 0.0 (set in trade_sync_service.py). Real P&L lives only in `CompletedTrade.realized_pnl` (FIFO matching). Every detection system that checks `Trade.pnl < 0` is dead code.

---

## Architecture Overview

There are 5 separate detection systems, mostly disconnected:

| System | Location | Trigger | Patterns | Working |
|--------|----------|---------|----------|---------|
| Frontend patternDetector | `src/lib/patternDetector.ts` | Dashboard trade fetch | 4 | 2 of 4 |
| Backend RiskDetector | `backend/app/services/risk_detector.py` | Post-sync in zerodha.py | 5 | 2 of 5 |
| BehavioralAnalysisService | `backend/app/services/behavioral_analysis_service.py` | Manual `/api/behavioral/` call only | 27 | 9 of 27 |
| BehavioralEvaluator | `backend/app/services/behavioral_evaluator.py` | Post-sync for new fills | 5 | 2 of 5 |
| DangerZoneService | `backend/app/services/danger_zone_service.py` | NEVER auto-triggered | 5 triggers | 0 (dead) |

**What the user actually sees:** Dashboard sidebar shows MERGED alerts from backend RiskAlert records + client-side patternDetector. Both sources are broken for P&L-dependent patterns.

---

## The P&L Problem (Root Cause)

```
trade_sync_service.py → transform_zerodha_order():
  pnl = 0.0  ← EVERY synced trade starts at zero

pnl_calculator.py → calculate_and_update_pnl():
  - Runs FIFO matching on 30-day window
  - Updates Trade.pnl ONLY for closing fills (SELL side)
  - Creates CompletedTrade records with realized_pnl
  - Opening fills (BUY side) stay at pnl = 0.0

Result:
  - Trade.pnl = 0.0 for BUY fills (always)
  - Trade.pnl = calculated for SELL fills (after FIFO)
  - CompletedTrade.realized_pnl = correct (always)
```

**Impact:** Any detector that checks `Trade.pnl < 0` on individual trades will fail on opening fills. The RiskDetector queries Trade table ordered by `order_timestamp` — which includes both BUY and SELL fills. BUY fills have pnl=0, breaking consecutive loss streaks.

**The frontend patternDetector gets its data differently:** Dashboard.tsx maps CompletedTrades into entry+exit Trade events. Exit events have `pnl: ct.realized_pnl` (real P&L). Entry events have `pnl: 0`. The frontend revenge detection works because it specifically checks exit→entry pairs where the exit had a loss. But consecutive loss detection doesn't exist in the frontend at all.

---

## Complete Pattern Catalog

### A. Frontend patternDetector.ts (4 patterns)

| # | Pattern | Function | Threshold | P&L Needed? | Working? |
|---|---------|----------|-----------|-------------|----------|
| 1 | Overtrading | `detectOvertrading()` | 5 trades in 30min | No | YES |
| 2 | Revenge Trading | `detectRevengeTading()` | Entry within 5min of Rs.500+ loss | Yes (exit events) | YES |
| 3 | Loss Aversion | `detectLossAversion()` | Avg loss > 1.5x avg win | Yes | PARTIAL (needs 5+ trades with wins AND losses) |
| 4 | Position Sizing | `detectPositionSizing()` | > 5% of capital | No | YES |

**Missing from frontend:** Consecutive losses, capital drawdown, same-instrument chasing, all-loss session, tilt spiral, FOMO, martingale, and 20+ more.

### B. Backend RiskDetector (5 patterns)

| # | Pattern | Method | Threshold | Data Source | Working? | Why Broken |
|---|---------|--------|-----------|-------------|----------|------------|
| 1 | Consecutive Loss | `_detect_consecutive_losses()` | 3+ caution, 5+ danger | Trade.pnl | NO | Trade.pnl = 0, BUY fills break streak |
| 2 | Revenge Sizing | `_detect_revenge_sizing()` | 1.5x size within 15min of loss | Trade.pnl | NO | Previous Trade.pnl = 0 |
| 3 | Overtrading | `_detect_overtrading()` | 5+ in 15min caution, 7+ danger | Trade count | YES | Count-based, no P&L needed |
| 4 | FOMO Entry | `_detect_fomo_entry()` | 3+ rapid entries at open | Trade timestamps | YES | Time-based, no P&L needed |
| 5 | Tilt Spiral | `_detect_tilt_spiral()` | Escalating sizes + losses | Trade.pnl, quantity | NO | Trade.pnl = 0 |

### C. BehavioralAnalysisService (27 patterns)

**GROUP 1: Primary Biases (4 patterns)**

| # | Pattern Class | Logic | P&L? | Working? |
|---|--------------|-------|------|----------|
| 5 | RevengeTradingPattern | Trade within 5min of loss, size >=1.5x | Yes | NO |
| 6 | NoCooldownPattern | Trade within 5min of any loss | Yes | NO |
| 7 | AfterProfitOverconfidencePattern | Size >1.5x median after wins | No (qty) | YES |
| 8 | StopLossDisciplinePattern (positive) | Max loss / avg loss < 2.5 | Yes | NO |

**GROUP 2: Behavioral Patterns (5 patterns)**

| # | Pattern Class | Logic | P&L? | Working? |
|---|--------------|-------|------|----------|
| 9 | OvertradingPattern | >10 trades/day or 5+ in 1 hour | No | YES |
| 10 | MartingaleBehaviorPattern | 2x+ position increase after loss | Yes | NO |
| 11 | InconsistentSizingPattern | Coefficient of variation > 0.5 | No (qty) | YES |
| 12 | TimeOfDayPattern | Win rate <40% during high-risk windows | Yes | PARTIAL |
| 13 | HopeDenialPattern | Avg loss >1.5x avg win | Yes | NO |

**GROUP 3: Enhanced/Cognitive Biases (5 patterns)**

| # | Pattern Class | Logic | P&L? | Working? |
|---|--------------|-------|------|----------|
| 14 | RecencyBiasPattern | 3+ same direction/symbol repeats after wins | Yes | PARTIAL |
| 15 | LossNormalizationPattern | >55% losing trades, low variance | Yes | NO |
| 16 | StrategyDriftPattern | Size or frequency shift >50% mid-session | No | YES |
| 17 | EmotionalExitPatternEnhanced | Cut winners <2%, avg loss >1.5x avg win | Yes | NO |
| 18 | ChopZoneAddictionPattern | 15+ trades, tiny P&L, many direction changes | Yes | NO |

**GROUP 4: Compound States (3 patterns)**

| # | Pattern Class | Logic | P&L? | Working? |
|---|--------------|-------|------|----------|
| 19 | TiltLossSpiralPattern | 4+ escalating losses | Yes | NO |
| 20 | FalseRecoveryChasePattern | 3+ larger/faster trades during drawdown | Yes | NO |
| 21 | EmotionalLoopingPattern | 3+ days of "gave back gains" | Yes | NO |

**GROUP 5: Phase A Advanced (10 patterns)**

| # | Pattern Class | Logic | P&L? | Working? |
|---|--------------|-------|------|----------|
| 22 | DispositionEffectPattern | Winners held <50% of loser duration | Yes | NO |
| 23 | BreakevenObsessionPattern | 3+ trades closed within +/-0.5% of entry | Yes | NO |
| 24 | AddingToLosersPattern | 2+ same-direction entries while underwater | Yes | NO |
| 25 | ProfitGiveBackPattern | 2+ days closing at <30% of peak | Yes | NO |
| 26 | EndOfDayRushPattern | 30%+ of trades after 3PM IST | No | YES |
| 27 | ExpiryDayGamblingPattern | 1.5x+ activity on expiry days | No | YES |
| 28 | BoredomTradingPattern | 5+ small quick trades with near-zero P&L | Yes | NO |
| 29 | ConcentrationRiskPattern | >60% trades in single instrument | No | YES |
| 30 | MaxDailyLossBreachPattern | Any day loss >2x avg daily loss | Yes | NO |
| 31 | GamblersFallacyPattern | Same direction 3+ times after 3 same-direction losses | Yes | NO |

### D. BehavioralEvaluator (5 event-driven patterns)

| # | Pattern | Confidence Range | P&L? | Working? |
|---|---------|-----------------|------|----------|
| Same as 5 | Revenge Trading | 0.70-0.99 | Yes | NO |
| Same as 9 | Overtrading | 0.72-0.95 | No | YES |
| Same as 19 | Tilt Spiral | Varies | Yes | NO |
| Same as 4B | FOMO Entry | Varies | No | YES |
| New | Loss Chasing | Varies | Yes | NO |

### E. DangerZoneService (5 trigger levels)

| Trigger | Threshold | Data Source | Working? |
|---------|-----------|-------------|----------|
| Loss Limit Breach | 100% of daily_loss_limit | `_get_today_pnl()` → Trade.pnl | NO (Trade.pnl=0) |
| Approaching Loss Limit | 85% of daily_loss_limit | Same | NO |
| Consecutive Loss Critical | 5+ consecutive losses | `_count_consecutive_losses()` → Trade.pnl | NO |
| Overtrading | 5+ / 8+ trades in 15min | Trade count | YES (but never auto-triggered) |
| Pattern-based | revenge/tilt/fomo/loss_chasing active | RiskAlert table | PARTIAL (depends on RiskDetector) |

---

## Summary: What Works vs What's Broken

### WORKING (9 patterns):
1. Overtrading (frontend + backend)
2. Position Sizing (frontend)
3. FOMO Entry (backend)
4. After-Profit Overconfidence (behavioral_analysis)
5. Inconsistent Sizing (behavioral_analysis)
6. Strategy Drift (behavioral_analysis)
7. End-of-Day Rush (behavioral_analysis)
8. Expiry Day Gambling (behavioral_analysis)
9. Concentration Risk (behavioral_analysis)

### PARTIALLY WORKING (3 patterns):
10. Revenge Trading (frontend exit→entry works; backend broken)
11. Loss Aversion (frontend works if enough trades; backend broken)
12. Time of Day Risk (time logic works; P&L analysis broken)

### COMPLETELY BROKEN (22 patterns):
Everything that requires Trade.pnl < 0: consecutive losses, tilt spiral, revenge sizing, martingale, no cooldown, stop loss discipline, hope & denial, loss normalization, emotional exit, chop zone, false recovery, emotional looping, disposition effect, breakeven obsession, adding to losers, profit give-back, boredom trading, max daily loss, gambler's fallacy, recency bias (partial).

### NEVER AUTO-TRIGGERED:
- BehavioralAnalysisService (only runs on manual `/api/behavioral/` call)
- DangerZoneService (only runs on manual `/api/danger-zone/status` call)

### NOTIFICATION PIPELINE: DEAD
- Push notifications: `send_risk_alert_notification()` exists but never called from sync
- WhatsApp: `send_danger_alert.delay()` exists but never triggered from sync
- WebSocket: `notify_risk_alert()` defined but never invoked

---

## Data Flow: Current vs Required

### CURRENT (Broken):
```
Trade synced → Trade.pnl = 0 → RiskDetector sees pnl=0 → No P&L patterns detected
                              → Frontend gets CompletedTrade → Only 4 patterns checked
                              → DangerZone never called → No interventions
                              → Notifications never sent → User unaware
```

### REQUIRED (Fixed):
```
Trade synced → P&L calculated → CompletedTrade created with realized_pnl
  → RiskDetector queries CompletedTrade → P&L patterns work
  → Frontend checks 8+ patterns → Consecutive losses, drawdown, etc detected
  → DangerZone auto-assessed → Interventions trigger
  → Notifications sent → Push + WhatsApp for danger events
  → User sees alerts immediately → Can take action
```

---

## The Sync Pipeline (Step by Step)

```
1. Frontend: POST /api/zerodha/sync/all
2. Backend zerodha.py:
   a. TradeSyncService.sync_trades_for_broker_account()
      - Fetch trades from Zerodha API
      - Upsert to Trade table (pnl = 0.0)
      - Sync positions from Zerodha
      - Run PnL Calculator (FIFO matching)
        → Updates Trade.pnl for SELL fills
        → Creates CompletedTrade records
      - Returns: { new_trade_ids: [...] }
   b. TradeSyncService.sync_orders_to_db()
   c. SIGNAL PIPELINE:
      - RiskDetector.detect_patterns() → RiskAlert records
      - BehavioralEvaluator.evaluate(new_fills) → BehavioralEvent records + WebSocket
      - [MISSING] DangerZoneService.assess_danger_level()
      - [MISSING] Notification dispatch for danger events
3. Frontend receives response:
   a. Fetches /api/trades/completed → CompletedTrade data
   b. Fetches /api/risk/alerts → RiskAlert records
   c. AlertContext.runAnalysis(mapped trades) → Client-side detection (4 patterns)
   d. Dashboard displays merged alerts (backend + frontend)
```

---

## Files Reference

| File | Purpose | Lines |
|------|---------|-------|
| `src/lib/patternDetector.ts` | Frontend pattern detection (4 patterns) | 370 |
| `src/types/patterns.ts` | PatternType enum + interfaces | 231 |
| `src/lib/emotionalTaxCalculator.ts` | Pattern cost calculation | ~300 |
| `src/contexts/AlertContext.tsx` | Alert state management + detection trigger | 241 |
| `src/pages/Dashboard.tsx` | Data fetching + alert merging | ~650 |
| `src/components/dashboard/RecentAlertsCard.tsx` | Alert sidebar display | 177 |
| `backend/app/services/risk_detector.py` | Backend pattern detection (5 patterns) | 548 |
| `backend/app/services/behavioral_analysis_service.py` | Full behavioral analysis (27 patterns) | 1813 |
| `backend/app/services/behavioral_evaluator.py` | Event-driven evaluation (5 patterns) | 519 |
| `backend/app/services/danger_zone_service.py` | Danger level assessment + interventions | 573 |
| `backend/app/services/trade_sync_service.py` | Trade sync + P&L calculation | 620 |
| `backend/app/services/pnl_calculator.py` | FIFO P&L matching | ~650 |
| `backend/app/api/zerodha.py` | Sync endpoint + signal pipeline | 688 |
| `backend/app/api/webhooks.py` | Zerodha postback handler | 227 |
| `backend/app/tasks/trade_tasks.py` | Celery trade processing tasks | ~300 |
| `backend/app/models/completed_trade.py` | CompletedTrade model (has real P&L) | 64 |
| `backend/app/models/trade.py` | Trade model (pnl often 0) | ~100 |
