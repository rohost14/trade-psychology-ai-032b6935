# Pattern Detection System — Production Findings Report

> **Status:** Critical — system is prototype-grade, not production-ready
> **Date:** 2026-03-01
> **Scope:** Frontend `patternDetector.ts` + Backend `behavioral_analysis_service.py` + `risk_detector.py` + `behavioral_evaluator.py` + `MANUAL_TEST_PLAYBOOK.md`
> **Author:** Claude Code audit (session 11)

---

## Executive Summary

The current behavioral pattern detection system was built to validate the concept and prove the feature works end-to-end. It does that. But it uses **universal static thresholds** that apply the same rules to every trader regardless of their capital, trading style, instrument type, or individual baseline. For 1000 users — all different — this produces high false-positive rates for some users and misses real problems for others. The test playbook validates these hardcoded thresholds but doesn't test whether they are appropriate for real traders.

This document catalogs every issue found, organized by severity and category.

---

## Section 0: Hardcoded Static Values — Complete Inventory

**This is the root of almost every production-readiness problem in the system.** Every threshold, every severity band, every time window, and every insight string is a magic number fixed at write-time. None of them adapt to who the user is, how much capital they have, what style they trade, or what their personal baseline looks like. Below is the full inventory.

### Frontend — `src/lib/patternDetector.ts`

**Default config object (applies to ALL users, no exceptions):**
```ts
const DEFAULT_CONFIG = {
  overtrading_trades_per_30min: 5,          // Same for scalper and swing trader
  overtrading_trades_per_hour: 8,           // Defined but NEVER USED in any detector
  revenge_max_time_after_loss_minutes: 5,   // Same for all styles
  revenge_min_loss_to_trigger: 500,         // Rs 500 — noise for big accounts, devastating for small
  fomo_rapid_entry_after_big_move_minutes: 2,  // Belongs to fomo — which is never implemented
  fomo_big_move_threshold_percent: 1,          // Same — dead config
  position_max_percent_of_capital: 5,       // Notional-based, wrong metric for F&O
  early_exit_min_profit_missed_percent: 50, // Belongs to early_exit — never implemented
}
```

**Hardcoded severity thresholds in each detector:**

| Detector | Hardcoded Values |
|---|---|
| `detectOvertrading` | `[5, 7, 10]` trades — same thresholds regardless of trading style |
| `detectRevengeTading` | Severity bands: `[500, 2000, 5000]` Rs — absolute, ignores capital |
| `detectLossAversion` | Ratio threshold: `1.5` — same for all risk:reward strategies |
| `detectLossAversion` | Severity bands: `[1.5, 2, 3]` ratio — arbitrary |
| `detectPositionSizing` | `[5, 10, 20]` % of capital — notional-based, wrong for F&O |
| `detectConsecutiveLosses` | `[3, 4, 5]` count — same for scalper and positional trader |
| `detectCapitalDrawdown` | `[10, 25, 40]` % — same regardless of risk tolerance |
| `detectSameInstrumentChasing` | `[2, 3, 4]` loss count — no time window, no capital context |
| `detectAllLossSession` | `[3, 5, 7]` count — ignores session duration and style |

**Hardcoded insight strings — generic statistics, not user data:**
```ts
'Revenge trades historically have a 40% lower win rate.'
'Data shows win rate typically drops after 5+ trades in quick succession.'
'Large positions correlate with 2x more emotional decisions.'
'Professional traders rarely risk more than 2% per trade or 6% per day.'
'After 3+ consecutive losses, win rate typically drops further.'
```
None of these are the user's actual statistics. They are marketing copy presented as data.

**Hardcoded capital default:**
```ts
export function detectAllPatterns(trades, capital = 100000, ...)
//                                                  ^^^^^^^^ Rs 1L for everyone if not passed
```

### Backend — `behavioral_analysis_service.py`

| Pattern Class | Hardcoded Constants |
|---|---|
| `RevengeTradingPattern` | `time_gap < 15` min, severity at `>= 3` instances |
| `NoCooldownPattern` | `time_gap < 5` min, critical at `>= 5` violations |
| `AfterProfitOverconfidencePattern` | `quantity > baseline_qty * 1.5`, uses session median as "baseline" |
| `StopLossDisciplinePattern` | `discipline_ratio < 2.5` (max_loss / avg_loss) |
| `OvertradingPattern` | `> 10 trades/day` (with hardcoded description "baseline: 3-5"), `5 trades in 1 hour` |
| `MartingaleBehaviorPattern` | `size_increase >= 1.8` (adjacent trades only, not rolling pattern) |
| `InconsistentSizingPattern` | `CV > 0.5` for detection, `CV > 0.7` for medium severity (inverted — medium fires at *lower* CV than detection, logic error) |
| `HopeDenialPattern` | `ratio > 1.5` (avg_loss / avg_win) |
| `TiltLossSpiralPattern` | `4+ consecutive losses` |
| `EndOfDayRushPattern` | `30%+ trades after 3 PM IST`, `2+ such days` |
| `ExpiryDayGamblingPattern` | `1.5x+ trades on expiry vs non-expiry` |
| `BoredomTradingPattern` | `5+ trades` with small P&L |
| `ConcentrationRiskPattern` | `60%+ trades on single instrument` |
| `MaxDailyLossBreachPattern` | `any day loss > 2x avg daily loss` |
| `DispositionEffectPattern` | `winners held < 0.5x duration of losers` |
| `ProfitGiveBackPattern` | `session ending at <= 30% of peak`, `2+ such days` |

### Backend — `risk_detector.py`

| Detection Method | Hardcoded Constants |
|---|---|
| `_detect_consecutive_losses` | Caution at `>= 3`, Danger at `>= 5` (same for all traders) |
| `_detect_revenge_sizing` | `curr_qty > loss_qty * 1.5`, window `<= 15 min` |
| `_detect_overtrading` | Caution at `>= 5`, Danger at `>= 7` trades in `15 min` |
| `_detect_fomo_entry` | `hour == 9 and minute < 20` (IST assumption, UTC bug), `>= 3 trades` |
| `_detect_tilt_spiral` | `>= 3 losses`, escalating sizes |

### Backend — `behavioral_evaluator.py`

| Constant | Value | Problem |
|---|---|---|
| `DEDUP_WINDOW_MINUTES` | `60` | Same for all patterns — overtrading dedup should be shorter, multi-day patterns longer |
| Overtrading window | `15 min`, `>= 5 trades` | Same for all styles |
| Revenge window | `15 min` | Same as above, different from frontend's `5 min` — inconsistent |

### The Core Problem in One Sentence

Every number in this system was chosen once by a developer and never revisited. They are not derived from research, not calibrated to user profiles, not relative to capital, and not adaptive to trading style. They will be wrong for the majority of users.

---

## Critical Bugs (Break Silently, Wrong Results)

### C-1: Frontend P&L Is Always Zero — Detectors Never Fire Correctly

**File:** `src/lib/patternDetector.ts`
**Severity:** Critical

The frontend pattern detector reads `trade.pnl` on every P&L-dependent check:

```ts
// detectOvertrading line 94
const pnlInWindow = tradesInWindow.reduce((sum, t) => sum + t.pnl, 0);  // always 0

// detectRevengeTading line 147
if (currentTrade.pnl < -config.revenge_min_loss_to_trigger)  // 0 < -500 = always false

// detectLossAversion line 195
const winners = trades.filter((t) => t.pnl > 0);   // always empty
const losers = trades.filter((t) => t.pnl < 0);    // always empty
```

The `Trade` model has `pnl` as a raw order fill field — it is always 0.0 because Zerodha doesn't include P&L on individual fills. Real P&L lives in `CompletedTrade.realized_pnl`. The backend fix (CompletedTradeAdapter) wraps CompletedTrade for backend services, but the frontend was never updated.

**Impact:** These frontend patterns **never actually fire** with real data:
- `revenge_trading` — always false (pnl < -500 never true)
- `loss_aversion` — always empty (no winners or losers found)
- `capital_drawdown` — always empty (no exits with pnl ≠ 0)
- `all_loss_session` — always empty (same reason)
- `same_instrument_chasing` — always empty

Only count-based patterns fire: `overtrading`, `consecutive_losses` (partially).

**Fix needed:** Frontend must consume `CompletedTrade` data for P&L patterns, not raw `Trade` fills.

---

### C-2: Dead Pattern — EmotionalExitPattern Always Returns No Detection

**File:** `backend/app/services/behavioral_analysis_service.py` line ~144
**Severity:** Critical

```python
class EmotionalExitPattern(BehavioralPattern):
    def detect(self, trades: List[Trade]) -> Dict:
        # Note: This pattern ideally needs 'duration' ...
        return self._no_detection()   # ← ALWAYS returns no detection
```

This pattern is listed in all documentation and the test playbook as detectable, but the implementation is a stub that returns nothing. Users and the product dashboard will never see this pattern even though the data exists.

---

### C-3: IST Timezone Bug in FOMO Entry Detection

**File:** `backend/app/services/behavioral_evaluator.py`
**Severity:** Critical

FOMO Entry is detected by checking if trades occurred in the 9:15–9:20 AM market opening window using:

```python
if trade_time.hour == 9 and trade_time.minute < 20:
```

If `trade_time` is stored/retrieved as UTC (which it is from Zerodha), then:
- 9:15 AM IST = 3:45 AM UTC
- This check would look for trades at 9 AM UTC = 2:30 PM IST (market is already 5 hours old)

**FOMO Entry at market open never fires correctly unless explicit IST conversion is done.**

The same issue may affect `EndOfDayRushPattern` (trades after 3 PM IST), `ExpiryDayGamblingPattern` (Thursday detection), and any other time-of-day logic.

---

### C-4: Position Sizing Uses Notional Value — Always Wrong for F&O

**File:** `src/lib/patternDetector.ts` — `detectPositionSizing()`
**Severity:** Critical

```ts
const tradeValue = trade.price * trade.quantity;  // notional value
const percentOfCapital = (tradeValue / capital) * 100;
```

For **NIFTY Futures** at Rs 24,000 with lot size 75:
- Notional = Rs 24,000 × 75 = **Rs 18,00,000**
- Actual margin required ≈ Rs 1,20,000–1,50,000

A trader with Rs 5L capital trading 1 lot of NIFTY Futures:
- Notional / Capital = 1800000 / 500000 = **360% → CRITICAL alert**
- Margin / Capital = 130000 / 500000 = **26% → possibly acceptable**

This creates **false CRITICAL alerts on every single F&O trade** for traders with reasonable capital. The metric must use margin deployed, not notional exposure.

---

## Architecture Problems (Wrong by Design)

### A-1: Four Separate Definitions of "Overtrading" — All Fire Simultaneously

**Severity:** High

| Layer | Threshold | Fires As |
|---|---|---|
| Frontend `patternDetector.ts` | 5 trades in 30 min | In-app toast + alert card |
| `BehavioralEvaluator` | 5 trades in 15 min | `BehavioralEvent` DB record |
| `RiskDetector` | 5-6 = caution, 7+ = danger in 15 min | `RiskAlert` DB record |
| `BehavioralAnalysisService` | >10/day OR 5+ in 1 hour | Analytics pattern |

One real overtrading event produces **4 separate alerts** to the same user. The same problem exists for:
- **Revenge trading**: 3 layers (frontend 5 min, BehavioralEvaluator 15 min, BehavioralAnalysisService 15 min)
- **Consecutive losses**: 3 layers (frontend 3+, RiskDetector 3+/5+, DangerZone 2+/3+/5+)
- **FOMO**: 2 layers

**Result:** Alert fatigue. Users experience the same event as multiple simultaneous notifications. They will start ignoring everything — the worst possible outcome for a behavioral psychology product.

**Fix needed:** Single alert orchestration layer. One event → one alert. Layers detect, orchestrator decides which alert to surface and deduplicate.

---

### A-2: Universal Static Thresholds — Identical Rules for All 1000 Users

**Severity:** High

Every threshold is a hardcoded constant with no user context:

| Threshold | Hardcoded Value | Why It's Wrong |
|---|---|---|
| `revenge_min_loss_to_trigger` | Rs 500 | Noise for Rs 50L trader; catastrophic for Rs 50K trader |
| `overtrading_trades_per_30min` | 5 | Scalpers do 20+ trades/day legitimately |
| `position_max_percent_of_capital` | 5% | Too high for conservative traders, too low for F&O scalpers |
| `capital_drawdown` trigger | 10% session loss | 10% of Rs 50K = Rs 5K (severe). 10% of Rs 50L = Rs 5L (also severe but different context) |
| Revenge re-entry window | 5 min (frontend) / 15 min (backend) | Inconsistent; neither is calibrated to user's trading style |
| Loss aversion ratio | 1.5x | A 1:3 risk-reward trader will always trigger this, even when trading correctly |
| Consecutive loss threshold | 3 (caution) / 5 (danger) | For a scalper: 3 losses in a row is normal noise. For a swing trader: 2 losses is alarming |
| Overconfidence size increase | 1.5x median | No baseline — first time user trades 2 lots vs 1 lot triggers this |

All of these need to be either: (a) user-declared, (b) style-calibrated, or (c) computed from user's own historical baseline.

---

### A-3: Frontend `detectAllPatterns()` Defaults Capital to Rs 1,00,000

**File:** `src/lib/patternDetector.ts` line 511
**Severity:** High

```ts
export function detectAllPatterns(
  trades: Trade[],
  capital: number = 100000,   // ← default Rs 1L
  config: PatternDetectionConfig = DEFAULT_CONFIG
): BehaviorPattern[]
```

If the calling component doesn't pass capital (which can happen on initial load, stale state, or error in BrokerContext), **every user gets thresholds calibrated for Rs 1L capital**. A Rs 10L trader's 1% loss looks like 10% drawdown. This is a silent wrong-computation failure — no error, just wrong alerts.

---

### A-4: No User Baseline — No Adaptive Personalization

**Severity:** High

The system applies the same thresholds from day 1 as it does on day 300. There is no:
- Baseline calibration period (silent observation first 2 weeks)
- Adaptive threshold computation from user history
- Per-user "normal" trading pattern to compare against

A trader who normally does 8 trades/day will trigger overtrading alerts daily at the 5-trade threshold. A trader who normally does 2 trades/day will not get an overtrading alert when they suddenly do 12 trades (2x their baseline, which is the real signal).

**The right signal is deviation from the user's own baseline, not crossing a universal threshold.**

---

### A-5: No Feedback Loop — Zero Accuracy Signal

**Severity:** High

Patterns fire → user can only acknowledge (dismiss) them. There is no mechanism to:
- Capture whether the user agreed the alert was relevant
- Measure false positive rate per pattern per user segment
- Improve thresholds based on user responses
- Detect "alert fatigue" users who dismiss everything

Without this, we don't know if 60% of alerts are false positives or 5%. We can't improve the system.

---

## Correctness Issues (Logic Wrong in Specific Cases)

### L-1: `detectSameInstrumentChasing` Has No Time Window

**File:** `src/lib/patternDetector.ts`
**Severity:** Medium

The detector counts all losses on the same symbol across the entire session with no time constraint. A trader who lost on NIFTY at 9:30 AM and again at 2:30 PM (5 hours apart, different setups, different market conditions) gets flagged for "chasing." These are two independent trades, not a chasing pattern.

True chasing requires re-entry on the same instrument within a meaningful time window (e.g., 2 hours) after a loss.

---

### L-2: Consecutive Losses Breaks on Exact Breakeven Trades

**File:** `src/lib/patternDetector.ts` — `detectConsecutiveLosses()`
**Severity:** Medium

```ts
const exits = trades.filter((t) => t.pnl !== 0);  // strict non-zero
```

A breakeven trade (pnl = 0) is excluded from the exit list entirely. So if a trader has:
- Loss → Loss → Breakeven → Loss → Loss

The breakeven silently resets the streak, even though behaviorally this is still a loss spiral. The streak counter sees only the two losses after the breakeven.

---

### L-3: Loss Aversion Ratio Applied Without Instrument Context

**File:** `src/lib/patternDetector.ts` — `detectLossAversion()`
**Severity:** Medium

A trader using 1:3 risk-reward (risking Rs 500 to make Rs 1,500 per trade) by design has:
- Avg win: Rs 1,500
- Avg loss: Rs 500
- Loss/Win ratio: 0.33 — below threshold, no alert (correct)

But if they have a bad month and their avg win drops to Rs 400:
- Loss/Win ratio: 1.25 — below 1.5, no alert (still correct)

However, an options premium seller who intentionally holds losers for theta decay will always show inflated average losses vs average wins. The pattern doesn't account for deliberate asymmetric strategies. Needs minimum trade count AND declaration of expected risk:reward from user.

---

### L-4: `MartingaleBehaviorPattern` Has No Historical Context

**File:** `backend/app/services/behavioral_analysis_service.py`
**Severity:** Medium

Martingale is detected as "size 1.8x+ after a loss." But this compares adjacent trades only — it doesn't require repeated escalation. A trader who happened to trade 1 lot, then 2 lots (1.8x) after an unrelated loss gets flagged as Martingale. True Martingale is a repeated pattern of doubling after losses, not a single instance.

---

### L-5: `InconsistentSizingPattern` — Coefficient of Variation Threshold Arbitrary

**File:** `backend/app/services/behavioral_analysis_service.py`
**Severity:** Low

CV > 0.5 is flagged as inconsistent sizing. But options traders routinely vary size by instrument (1 lot NIFTY vs 3 lots NIFTY weekly vs 5 lots stock options) based on IV, liquidity, conviction. CV of 0.5+ is normal and intentional for many strategies. This pattern will produce high false-positive rates for sophisticated traders.

---

## Test Playbook Issues (Infrastructure & Coverage)

### T-1: Requires Real Money — Cannot Run in Regression

**Severity:** Critical

Every test requires live trades during market hours with real capital (Rs 2,000–5,000 budget stated for testing losses). This means:
- Cannot run tests when market is closed
- Cannot run tests automatically on code change
- Cannot run tests for free
- Cannot test multiple scenarios in parallel
- Cannot be part of CI/CD pipeline

**Fix needed:** Synthetic data seeder that injects `CompletedTrade` and `Trade` records directly into the database with controlled timestamps, P&L, and quantities. Tests then validate pattern output without any real trading.

---

### T-2: No Negative Tests — False Positive Coverage Is Zero

**Severity:** High

Every test in the playbook verifies that a pattern FIRES. There is zero coverage for verifying that patterns do NOT fire when they shouldn't (false positives).

Missing negative tests include:
- Disciplined session (3 trades, all winners, proper sizing) → no alerts should fire
- Scalper doing 8 trades in 30 min legitimately → no overtrading if within their declared limit
- Trader with 1:3 risk-reward profile → no loss aversion alert
- Breakeven trade in middle of session → no consecutive loss streak reset
- 2 trades on NIFTY 5 hours apart (both losses) → no same-instrument-chasing

---

### T-3: No Multi-User Isolation Tests

**Severity:** High

The playbook explicitly says: "Multi-user scenarios: N/A for manual testing." For a production system with 1000 users, critical tests include:
- User A and User B trading simultaneously — their patterns don't cross-contaminate
- User A's `broker_account_id` never appears in User B's alerts
- Concurrent sync operations for 100 users don't cause race conditions

---

### T-4: Test Thresholds Hardcoded to Rs 500 — Not Capital-Relative

**Severity:** High

The revenge trading test says:
> "Exit at a loss of at least **Rs 500**"

This hardcodes the same threshold into the test that's in the code. It validates the code behavior, not whether Rs 500 is the right threshold. There is no test for: "Does this threshold scale with user capital?"

---

### T-5: No Edge Case Coverage

**Severity:** Medium**

Missing edge cases never tested:
- Zero trades: all detectors should return empty arrays, not errors
- One trade: no pattern should fire with insufficient data
- `realized_pnl = NULL`: should handle gracefully, not crash
- `entry_time > exit_time`: data integrity violation — should be caught
- Trades across midnight (carry position): session boundary handling
- Weekend/holiday timestamps
- Token expired mid-sync: partial sync state
- Duplicate trade records: idempotency of pattern detection
- Very large P&L (Rs 10L+ single trade): no overflow
- Negative quantity (short trades): sizing logic still correct

---

### T-6: Pass Criteria Are Vague

**Severity:** Medium

Many test pass criteria use subjective language:
- "elevated risk (caution or danger)" — not a specific assertion
- "severity matches ratio threshold" — no exact value stated
- "alert description shows correct ratio" — no specific format tested

Production tests need exact JSON assertions:
```json
{
  "pattern_type": "consecutive_loss",
  "severity": "danger",
  "details.consecutive_losses": 5,
  "details.total_loss": ">= 3000"
}
```

---

### T-7: No Performance / Load Testing

**Severity:** Medium

No tests for:
- 1000 users syncing simultaneously — pattern detection throughput
- Large trade history (3 years, 5000 trades) — detection time
- Database query performance under load
- Rate limiting behavior under stress

---

## Completeness Gaps (Missing Logic)

### G-1: No Instrument Type Differentiation

Options buyers, options sellers, and futures traders have fundamentally different risk profiles. The current system treats them identically:

| Trader Type | Risk Profile | Current System |
|---|---|---|
| Options buyer | Max loss = premium paid (known upfront) | Applies futures-style thresholds |
| Options seller | Unlimited loss potential, margin-based | Same thresholds as buyer |
| Futures trader | Mark-to-market, margin-based loss | Same as everyone |

An options buyer losing 100% of their premium is a normal, intended outcome. An options seller losing 100% of their premium collected is catastrophic. The same P&L number means completely different things.

---

### G-2: No Baseline Learning Period (Cold Start)

New users with fewer than 20 trades get pattern alerts calibrated against universal thresholds with no historical context. The first few weeks, when traders are most likely to be cautious, they get bombarded with alerts calibrated for "average" traders — which they are not yet. This is the fastest way to cause alert fatigue before the user has any trust in the system.

---

### G-3: Insight Text Is Generic — Not User-Specific Data

All insight strings are hardcoded generic statistics:

```ts
insight: 'Revenge trades historically have a 40% lower win rate.'
insight: 'Large positions correlate with 2x more emotional decisions.'
insight: 'Professional traders rarely risk more than 2% per trade or 6% per day.'
```

None of these reference the user's actual data. A user who sees "your revenge trades have a 62% loss rate (vs your 48% loss rate normally)" will act. A user who sees a generic industry statistic will ignore it.

---

### G-4: `frequency_this_week` and `frequency_this_month` Always Return 0

**File:** `src/lib/patternDetector.ts`

```ts
frequency_this_week: 0,   // hardcoded
frequency_this_month: 0,  // hardcoded
```

These fields exist on the pattern object and are displayed in the UI, but they are never computed. The `calculatePatternFrequency` utility function exists but is not called during `detectAllPatterns`. Users always see "0 times this week" regardless of how often a pattern has actually occurred.

---

### G-5: `StopLossDisciplinePattern` Is a POSITIVE Pattern — Not Used in UI

**File:** `backend/app/services/behavioral_analysis_service.py`

The only positive pattern in the system (`StopLossDisciplinePattern`) detects good behavior but is likely never surfaced to the user. Behavioral psychology research shows positive reinforcement is as important as negative warnings. The frontend has no concept of "positive patterns" in its alert system.

---

## Additional Missed Issues Found on Deep Re-Read

### F-1: Four PatternTypes Declared in Frontend But Have Zero Implementation

**File:** `src/lib/patternDetector.ts` + `src/types/patterns.ts`
**Severity:** High

The `PatternType` union and `PATTERN_NAMES` map declare these 4 patterns — they exist in the type system, appear in UI components, and are listed in documentation — but there is **no detector function** and they are **never called** in `detectAllPatterns()`:

| Pattern Type | In PatternType | In PATTERN_NAMES | Detector Function | Called in detectAllPatterns |
|---|---|---|---|---|
| `fomo` | ✓ | ✓ | ✗ | ✗ |
| `no_stoploss` | ✓ | ✓ | ✗ | ✗ |
| `early_exit` | ✓ | ✓ | ✗ | ✗ |
| `winning_streak_overconfidence` | ✓ | ✓ | ✗ | ✗ |

If UI components try to render these pattern types, they will silently show no data. The `PATTERN_NAMES` object has entries for all of them, so no type error is thrown — the patterns just never fire. This is invisible to tests since there's no negative coverage.

---

### F-2: Historical Insight Text Uses `nextTrade.pnl` — Always Shows ₹0

**File:** `src/lib/patternDetector.ts` — `detectRevengeTading()`
**Severity:** High

```ts
historical_insight: nextTrade.pnl < 0
  ? `This revenge trade also lost ₹${Math.abs(nextTrade.pnl).toLocaleString('en-IN')}`
  : `This trade recovered ₹${nextTrade.pnl.toLocaleString('en-IN')}`,
```

Since `nextTrade.pnl` is always 0 (raw fill, no realized P&L), the insight shown to users is always one of:
- "This trade recovered ₹0" (wrong — 0 is neither positive nor negative)

The condition `nextTrade.pnl < 0` is never true, so the "also lost" branch never fires. Every revenge trading alert shows "This trade recovered ₹0." Users see this and immediately distrust the system.

The same problem exists in `detectPositionSizing`:
```ts
historical_insight: trade.pnl < 0
  ? `This oversized position lost ₹${Math.abs(trade.pnl)...}` // pnl=0, never fires
  : `Position was profitable: ₹${trade.pnl...}`               // always shows ₹0
```

---

### F-3: `overtrading_trades_per_hour` Config Field Is Defined But Never Used

**File:** `src/lib/patternDetector.ts`
**Severity:** Medium

```ts
const DEFAULT_CONFIG = {
  overtrading_trades_per_hour: 8,   // defined in config
  ...
}
```

`detectOvertrading()` only checks 30-minute windows, never hourly. The hourly config field is dead. This is misleading — anyone reading the config believes hourly detection exists. It doesn't.

---

### F-4: OvertradingPattern Burst Frequency Always Reports Zero

**File:** `backend/app/services/behavioral_analysis_service.py` — `OvertradingPattern`
**Severity:** Medium

```python
def _find_clusters(self, trades):
    """Find clusters of rapid trades."""
    clusters = []
    # Simplified clustering logic placeholder
    return clusters   # always returns empty list

# In detect():
"frequency": len([t for group in self._find_clusters(sorted_trades) for t in group]),
#             ^^^ iterates empty list → always 0
```

When the clustering branch of `OvertradingPattern` fires, the `frequency` field is always reported as 0 — even though multiple trades were detected. The analytics dashboard shows "Overtrading detected, frequency: 0 times." This is a placeholder that was never replaced.

---

### F-5: No Session/Day Boundary — Patterns Accumulate Across Days

**File:** `src/lib/patternDetector.ts`
**Severity:** High

`detectAllPatterns()` receives a `trades` array and runs detectors on it without any date filtering. The calling component (AlertContext) determines what trades to pass. If it passes all historical trades (which it may, to populate the alert history):

- `detectConsecutiveLosses`: counts the most recent consecutive loss streak across ALL time — yesterday's 2 losses + today's 1 loss = 3 consecutive losses → alert fires on today's first trade, incorrectly marking a fresh day as a loss spiral
- `detectSameInstrumentChasing`: groups ALL losses on same symbol ever — losses on NIFTY from 2 months ago count toward today's "chasing" alert
- `detectCapitalDrawdown`: sums ALL exits' P&L ever — if you had a bad week 3 months ago and it's included, your "session drawdown" is wrong

None of the frontend detectors filter to the current trading session (today only) before running. This is a silent, hard-to-notice error.

---

### F-6: `InconsistentSizingPattern` Severity Logic Is Inverted

**File:** `backend/app/services/behavioral_analysis_service.py`
**Severity:** Medium

```python
if cv > 0.5:  # detection threshold
    return {
        "severity": "medium" if cv > 0.7 else "low",
        ...
    }
```

This reads: severity is "medium" when `cv > 0.7`, and "low" when `cv` is between 0.5 and 0.7. But the intent is clearly that **higher** CV should be **more severe**. The labels suggest the developer intended "medium" for the moderate case and something higher for the extreme — but no "high" or "critical" branch exists. Traders with the worst inconsistency (CV = 2.0) get the same "medium" alert as someone at CV = 0.71.

---

### F-7: `_find_clusters` in OvertradingPattern Returns Empty — Dead Code Branch

**File:** `backend/app/services/behavioral_analysis_service.py`
**Severity:** Medium

The comment says "Simplified clustering logic placeholder." This means the entire burst-detection branch of `OvertradingPattern` (checking for 5+ trades in 1 hour) fires the detection logic but the supporting `_find_clusters` function is a stub. The detection uses `_find_clusters`'s output to populate `frequency` — which is always 0. Additionally, the pattern can detect clustering (via the outer loop) but can never actually enumerate which trades formed the cluster, breaking the `affected_trades` field.

---

### F-8: `detectRevengeTading` — Typo in Function Name (Minor but Indicative)

**File:** `src/lib/patternDetector.ts`
**Severity:** Low

Function is named `detectRevengeTading` (missing 'r' in Trading). Not functionally broken since the caller uses the same name, but it signals that this code has never been through a proper review. It also makes the function harder to find via text search for "revengeTr".

---

### F-9: Hardcoded Recommendation Text Gives Wrong Absolute Advice for All Users

**Severity:** High (Product)

Every pattern's recommendation is a universal prescription that ignores the user's actual situation:

```ts
insight: 'Professional traders rarely risk more than 2% per trade or 6% per day.'
```

For an aggressive scalper with Rs 50L capital, 2% per trade is Rs 1L — completely valid. For a beginner with Rs 50K, 2% is Rs 1,000 — very different context. The advice is the same. Worse, calling all users "professionals" implicitly is condescending to beginners and factually wrong.

```python
"recommendation": "Set max 5 trades per day. Focus on quality over quantity."
```

A scalper with a proven edge doing 25 trades/day is told to do 5. This is harmful, not helpful. It will cause them to disable all alerts immediately.

These strings need to be generated dynamically using the user's profile, style, and actual numbers.

---

### F-10: `calculate_risk_state` Uses 4-Hour Alert Window — Stale Alerts Drive Risk Level

**File:** `backend/app/services/risk_detector.py`
**Severity:** Medium

```python
cutoff = datetime.now(timezone.utc) - timedelta(hours=4)
```

The risk state (safe/caution/danger) is computed from unacknowledged alerts in the **last 4 hours**. This means:
- A trader who had a DANGER alert at 9:30 AM is still shown as "DANGER" at 1:30 PM, even if they stopped trading, took a break, and traded well since then
- Acknowledged alerts are excluded but only if the user actively clicks "acknowledge" — most won't
- There's no automatic decay of risk state over time

The risk state doesn't reflect what's actually happening now — it reflects what happened up to 4 hours ago.

| ID | Issue | Severity | Category |
|---|---|---|---|
| C-1 | Frontend P&L always 0, detectors never fire | Critical | Bug |
| C-2 | EmotionalExitPattern always returns no-detection | Critical | Bug |
| C-3 | IST timezone bug in FOMO / time-of-day patterns | Critical | Bug |
| C-4 | Position sizing uses notional (wrong for F&O) | Critical | Bug |
| A-1 | 4 overlapping overtrading definitions, alert spam | High | Architecture |
| A-2 | Universal static thresholds, no user context | High | Architecture |
| A-3 | Capital defaults to Rs 1L if not passed | High | Architecture |
| A-4 | No user baseline, no adaptive personalization | High | Architecture |
| A-5 | No feedback loop, zero accuracy measurement | High | Architecture |
| L-1 | Same instrument chasing has no time window | Medium | Logic |
| L-2 | Breakeven trade silently breaks loss streak | Medium | Logic |
| L-3 | Loss aversion doesn't account for intentional risk:reward | Medium | Logic |
| L-4 | Martingale detects single event, not repeated pattern | Medium | Logic |
| L-5 | InconsistentSizing CV threshold too broad | Low | Logic |
| T-1 | Test requires real money, cannot be automated | Critical | Testing |
| T-2 | No negative tests (false positive coverage = 0) | High | Testing |
| T-3 | No multi-user isolation tests | High | Testing |
| T-4 | Test thresholds hardcoded, not capital-relative | High | Testing |
| T-5 | No edge case coverage | Medium | Testing |
| T-6 | Pass criteria vague, not machine-assertable | Medium | Testing |
| T-7 | No performance/load testing | Medium | Testing |
| G-1 | No instrument type differentiation (options vs futures) | High | Completeness |
| G-2 | No baseline learning period for cold start | High | Completeness |
| G-3 | Insight text generic, not user-specific | High | Completeness |
| G-4 | frequency_this_week/month always 0 | Medium | Completeness |
| G-5 | Positive patterns not surfaced to user | Low | Completeness |
| F-1 | 4 frontend PatternTypes declared, never implemented (fomo/no_stoploss/early_exit/overconfidence) | High | Dead Code |
| F-2 | Historical insight text reads pnl=0, always shows ₹0 to user | High | Dead Code |
| F-3 | overtrading_trades_per_hour config defined but never used | Medium | Dead Code |
| F-4 | OvertradingPattern burst frequency always reports 0 (dead _find_clusters) | Medium | Dead Code |
| F-5 | No session/day boundary — patterns accumulate across all historical trades | High | Logic |
| F-6 | InconsistentSizingPattern severity logic inverted (higher CV gets lower severity) | Medium | Logic |
| F-7 | _find_clusters is a stub — burst overtrading affected_trades always empty | Medium | Dead Code |
| F-8 | detectRevengeTading typo — minor but signals no code review occurred | Low | Quality |
| F-9 | Hardcoded recommendation text gives wrong absolute advice (e.g., "max 5 trades/day" to scalpers) | High | Product |
| F-10 | calculate_risk_state uses 4-hour stale window — past DANGER drives current "DANGER" state | Medium | Logic |

**Total: 35 issues** — 4 Critical, 16 High, 11 Medium, 4 Low

### Hardcoded Value Count
- Frontend `patternDetector.ts`: **28 hardcoded constants** across thresholds, severity bands, time windows, insight strings
- Backend `behavioral_analysis_service.py`: **30+ hardcoded constants** across 27 pattern classes
- Backend `risk_detector.py`: **8 hardcoded constants** across 5 detectors
- Backend `behavioral_evaluator.py`: **5 hardcoded constants**

**~71 magic numbers** that need to become adaptive, per-user, or configurable values.

---

## What Production-Grade Looks Like

1. **Per-user adaptive thresholds** computed from each user's own trading baseline
2. **Single alert orchestration layer** — one event, one alert, deduplication across all layers
3. **Margin-based position sizing** not notional — use Kite margin data
4. **Frontend consumes CompletedTrade** data for P&L patterns, not raw Trade.pnl=0
5. **Personalized insight text** — user's own numbers, not industry averages
6. **Baseline calibration period** — 2 weeks silent observation before alerts begin
7. **Feedback mechanism** — "Was this helpful?" → accuracy score per pattern
8. **IST timezone enforcement** — explicit conversion before all time-of-day checks
9. **Instrument-type awareness** — options buyer vs seller vs futures have different thresholds
10. **Automated synthetic test suite** — seed CompletedTrade records, assert pattern output, no real money

---
*Next action: Complete the Product Design Questionnaire (`PATTERN_DETECTION_QUESTIONNAIRE.md`) before rebuilding thresholds.*
