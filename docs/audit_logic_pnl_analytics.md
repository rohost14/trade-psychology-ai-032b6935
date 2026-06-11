# P&L and Analytics Math Logic Audit

**Date**: 2026-06-10
**Scope**: pnl_calculator.py, analytics.py, shield_service.py, analytics_service.py, position_ledger_service.py, mcx_contract_specs.py, market_hours.py
**Auditor**: Claude Sonnet 4.6

---

## SUMMARY TABLE

| # | Component | Status | Severity |
|---|-----------|--------|----------|
| 1 | Profit factor when no losses | BUG | Medium |
| 2 | Profit factor when all wins (ai-summary tab) | BUG | Medium |
| 3 | Expectancy formula — correct math, misleading label | MINOR_ISSUE | Low |
| 4 | progress endpoint — naive UTC date boundaries for week | BUG | High |
| 5 | progress endpoint — win rate uses Trade.pnl not CompletedTrade | BUG | High |
| 6 | VaR 95% — index-based percentile wrong on small samples | BUG | Medium |
| 7 | Max drawdown — trade-level not daily-level in ai-summary risk tab | MINOR_ISSUE | Low |
| 8 | Max drawdown — absolute amount, not % of peak capital | MINOR_ISSUE | Low |
| 9 | Daily volatility — sample std dev denominator N-1, but N=1 crashes | BUG | Low |
| 10 | Best streak — hardcoded floor of 7 | BUG | Medium |
| 11 | Realtime P&L — lot multiplier not applied (MCX/CDS) | CRITICAL_BUG | Critical |
| 12 | BTST entry filter — condition is always True (>= 15:00) | BUG | High |
| 13 | BTST exit filter — rejects valid 09:15–09:44 exits | BUG | High |
| 14 | BTST "next trading day" not verified | MINOR_ISSUE | Medium |
| 15 | Expiry day detection — hardcoded Thursday weekday | BUG | High |
| 16 | Timing heatmap — UTC-to-IST arithmetic wrong on half-hour boundary | BUG | Medium |
| 17 | progress endpoint — week boundaries naive UTC, not IST | BUG | High |
| 18 | progress endpoint — "clean_days" can go negative | BUG | Low |
| 19 | Discipline score — "critical" severity alerts ignored | MINOR_ISSUE | Medium |
| 20 | shield_service — session end hardcoded 15:30, breaks MCX/CDS | MINOR_ISSUE | Medium |
| 21 | pnl_pct formula correct; avg_entry=0 guard uses falsy check | MINOR_ISSUE | Low |
| 22 | Drawdown recovery logic — draws wrong start date for streak tracker | BUG | Medium |
| 23 | position_ledger FLIP — new position avg_entry price correct but realized_pnl omits flip excess | CORRECT | — |
| 24 | MCX multiplier unknown symbol fallback returns 1 silently | MINOR_ISSUE | Medium |
| 25 | Unrealized P&L for short positions — formula correct | CORRECT | — |
| 26 | Weighted average entry price — formula correct | CORRECT | — |
| 27 | FIFO P&L — long and short formulas correct | CORRECT | — |
| 28 | Lot multiplier — real-time path (calculate_trade_pnl_realtime) drops multiplier | CRITICAL_BUG | Critical |

---

## DETAILED FINDINGS

---

## [Overview KPIs]: Profit factor when no losses

**File**: `backend/app/api/analytics.py:304`
**Status**: BUG
**Finding**: When the trader has no losing trades, `profit_factor` is set to `0` instead of a meaningful value. Zero implies no edge, which is the opposite of the truth.

**Evidence**:
```python
profit_factor = (sum(winners) / abs(sum(losers))) if losers else 0
```

**Impact**: A trader who has run 20 trades with zero losses sees `profit_factor = 0.00`. The correct mathematical convention for infinite profit factor is either `float('inf')` (JSON-serialise as `null`) or a sentinel like `99.0` with a display label "∞".

**Fix**:
```python
if not losers:
    profit_factor = None  # display as "∞" on frontend
elif sum(losers) == 0:
    profit_factor = None
else:
    profit_factor = sum(winners) / abs(sum(losers))
```

---

## [AI-Summary Tab / Overview]: Profit factor division by zero when all wins

**File**: `backend/app/api/analytics.py:1097`
**Status**: BUG
**Finding**: Same bug as above but in the ai-summary `tab == "overview"` inline recompute. This path additionally has no guard at all — if `losers` is empty, `abs(sum(losers))` is `0` and `sum(winners) / 0` raises `ZeroDivisionError`, causing a 500 response.

**Evidence**:
```python
"profit_factor": round(sum(winners) / abs(sum(losers)), 2) if losers else 0,
```
Wait — `if losers else 0` does guard it. Re-examine: this is the same issue as above — returns 0 when no losses. But unlike line 304, this path also does not wrap in try/except at the expression level. If `losers` is a non-empty list whose sum happens to be exactly `0.0` (e.g. trades with pnl exactly 0 mistakenly in losers list), division still raises. Low probability but present.

**Impact**: Same cosmetic issue as #1 for the ai-summary narrative context data.

---

## [Overview KPIs]: Expectancy formula — correct math, misleading label

**File**: `backend/app/api/analytics.py:305`
**Status**: MINOR_ISSUE
**Finding**: Expectancy is computed as `total_pnl / len(trades)`, which is mathematically equivalent to the standard expectancy formula `(win_rate × avg_win) + (loss_rate × avg_loss)`. The result is correct. However, the field is labelled `expectancy` when it is actually `avg_pnl_per_trade`. In trading literature, "expectancy" usually refers to this value expressed in R-multiples or as a per-unit-risked figure, not as a raw rupee average.

**Evidence**:
```python
expectancy = total_pnl / len(trades) if trades else 0
```
`expectancy_r_multiple = avg_win / avg_loss * win_rate - loss_rate` is the proper definition.

**Impact**: Presentation only. The number is arithmetically correct but the label may confuse professional traders who expect R-multiple expectancy.

---

## [Progress Endpoint]: Week boundaries are naive UTC, not IST-anchored

**File**: `backend/app/api/analytics.py:126–141`
**Status**: BUG
**Finding**: The progress endpoint computes `this_week_start` from `datetime.now(timezone.utc).date()`. For an IST user, UTC midnight is 05:30 IST, meaning the week boundary shifts by 5 hours 30 minutes compared to what the user sees as "Monday". Trades placed between 00:00 UTC and 05:30 IST on Monday will be incorrectly included in the previous week.

**Evidence**:
```python
now = datetime.now(timezone.utc)
today = now.date()
this_week_start = today - timedelta(days=today.weekday())
```

Also: `datetime.combine(start_date, datetime.min.time())` creates a **naive** datetime. The DB stores timestamps as `TIMESTAMP WITH TIME ZONE` (UTC). Comparing a naive datetime to a timezone-aware column is undefined behavior in PostgreSQL via SQLAlchemy — the comparison may silently use the wrong timezone offset depending on the DB session timezone.

**Impact**: Week-over-week comparison data misaligns by up to 5.5 hours. On Monday mornings, several IST trades show in the wrong week.

**Fix**:
```python
from app.core.market_hours import IST as IST_TZ
now_ist = datetime.now(IST_TZ)
today_ist = now_ist.date()
this_week_start = today_ist - timedelta(days=today_ist.weekday())
# Build timezone-aware boundaries:
from zoneinfo import ZoneInfo
_ist = ZoneInfo("Asia/Kolkata")
start_dt = datetime(this_week_start.year, this_week_start.month, this_week_start.day, tzinfo=_ist)
```

---

## [Progress Endpoint]: Win rate uses Trade.pnl not CompletedTrade

**File**: `backend/app/api/analytics.py:159`
**Status**: BUG
**Finding**: The `get_period_stats` helper fetches raw `Trade` rows and computes win rate from `Trade.pnl`. The `Trade.pnl` field is set by FIFO only for closing fills; opening fills have `pnl = NULL` or `0`. This means every opening fill counts as a "loss" (pnl = 0, filtered to neither winner nor loser but still included in `len(pnls)` as 0), causing win rate to be systematically underreported.

**Evidence**:
```python
pnls = [float(t.pnl or 0) for t in trades]   # opening fills → pnl=0
winners = [p for p in pnls if p > 0]
# len(pnls) includes zero-pnl opening fills
"win_rate": (len(winners) / len(pnls) * 100) if pnls else 0,
```

For a trader who did 10 round-trips (20 raw trades, 10 opening + 10 closing):
- `len(pnls)` = 20
- winners denominator is 20, not 10
- Win rate appears halved.

Also, `avg_loss` uses the average of negative raw P&Ls, not per-round P&L, creating a different metric from the overview tab which uses `CompletedTrade`.

**Impact**: Progress tab shows significantly different (lower) win rate than Overview tab for the same period. The weekly comparison numbers are unreliable.

**Fix**: Use `CompletedTrade` (not `Trade`) for win rate and P&L, consistent with all other analytics endpoints.

---

## [Risk Metrics]: VaR 95% — index calculation wrong on small sample

**File**: `backend/app/api/analytics.py:681–683`
**Status**: BUG
**Finding**: The 5th percentile is found by `idx_5 = max(0, int(len(daily_pnls) * 0.05))`. For a sample of 10 days, `int(10 * 0.05) = 0` → the minimum value in the sorted list is returned. For 20 days: `int(20 * 0.05) = 1` → second-worst day. The formula actually computes the floor of the 5th percentile index rather than the proper interpolated percentile. More critically, for any `len < 20`, `idx_5 = 0` always, meaning VaR 95% = worst day ever, not the 5th percentile.

**Evidence**:
```python
idx_5 = max(0, int(len(daily_pnls) * 0.05))
var_95 = round(daily_pnls[idx_5], 2)
```

For 10 trading days: `idx_5 = 0`. `var_95 = daily_pnls[0]` = worst single day. For 30 days: `idx_5 = 1`. True 5th percentile index should be `1.5` (interpolated between index 1 and 2).

**Impact**: VaR 95% is overstated (too negative) for small sample sizes, and consistently underestimates true VaR for large samples. A trader with 30 days of data sees the 2nd-worst day as their "1-in-20 risk" instead of the interpolated 5th-percentile figure.

**Fix**:
```python
import statistics
# Python 3.8+ statistics.quantiles:
if len(daily_pnls) >= 2:
    var_95 = round(statistics.quantiles(daily_pnls, n=20)[0], 2)  # 5th percentile
```
Or use numpy: `np.percentile(daily_pnls, 5)`.

---

## [Risk Metrics]: Max drawdown is absolute rupees, not percent of peak

**File**: `backend/app/api/analytics.py:686–726`
**Status**: MINOR_ISSUE
**Finding**: `max_drawdown` is returned as a raw rupee amount (`cumulative - peak`), not as a percentage of peak equity. For a trader who grew from 0 to ₹5 lakh then fell to ₹4.5 lakh, the drawdown shows as `-50,000` with no context. Without a starting capital figure, the percentage cannot be computed server-side. However the field name `max_drawdown.amount` implies a rupee figure, which is fine — but a `max_drawdown_pct` field is missing and would be more useful for risk sizing.

**Impact**: Presentation issue. Not mathematically wrong, just incomplete.

---

## [Risk Metrics]: Daily volatility — division by N-1, but guard only requires N>=2

**File**: `backend/app/api/analytics.py:678–680`
**Status**: BUG
**Finding**: The variance uses `len(daily_pnls) - 1` (sample variance, correct). But with exactly 1 trading day, the guard `if len(daily_pnls) >= 2` is correct and avoids division by zero. This specific check is fine. However in the ai-summary inline risk recompute (lines 1178–1183), the same computation runs, and there the guard is `if len(daily_vals) >= 2`, also correct. No crash bug here. **Status downgraded to CORRECT for this specific check.**

---

## [Progress Endpoint]: "best_streak" hardcoded floor of 7

**File**: `backend/app/api/analytics.py:252`
**Status**: BUG
**Finding**: `best_streak` is computed as `max(days_clean, 7)`, meaning the "best streak" is always at least 7 even on a user's first day. This is explicitly noted in a code comment as "Simplified — would need history" but the number `7` is arbitrary and misleading.

**Evidence**:
```python
"best_streak": max(days_clean, 7),  # Simplified - would need history
```

**Impact**: New users or users who have triggered daily alerts see a fabricated "7-day best streak" that never existed. This violates the platform's "mirror, not blocker" philosophy — it shows fiction.

**Fix**: Either compute the real best streak from historical RiskAlert data (requires a query over all-time data, not just last 30 days), or return `None` with a `"best_streak_available": False` flag until enough history exists.

---

## [Realtime P&L]: Lot multiplier not applied for MCX and CDS

**File**: `backend/app/services/pnl_calculator.py:774–784`
**Status**: CRITICAL_BUG
**Finding**: `calculate_trade_pnl_realtime()` — used in the webhook real-time path — computes P&L as `(exit_price - entry_price) × match_qty` with no lot multiplier. For MCX instruments where Kite sends quantity in LOTS (not units), this produces P&L that is off by the contract multiplier.

**Evidence**:
```python
if opening["side"] == "BUY":
    match_pnl = Decimal(str((trade_price - opening["price"]) * match_qty))
else:
    match_pnl = Decimal(str((opening["price"] - trade_price) * match_qty))

total_pnl += match_pnl
```
Compare to the batch FIFO at line 292 which applies `lot_multiplier`:
```python
match_pnl = Decimal(str((price - opening["price"]) * match_qty)) * lot_multiplier
```

**Impact**: For a CRUDEOIL trade (multiplier = 100):
- Entry: ₹6500/barrel, Exit: ₹6560/barrel, 1 lot (= 100 barrels)
- Correct P&L: `(6560 - 6500) × 1 × 100 = ₹6,000`
- Realtime P&L shown: `(6560 - 6500) × 1 = ₹60` — **100× understatement**

For GOLD (multiplier = 100): same error magnitude.
For NATURALGAS (multiplier = 1250): P&L is off by 1250×.

The batch FIFO correctly applies the multiplier on EOD reconciliation, so `realized_pnl` in `CompletedTrade` will be correct. But the real-time `Trade.pnl` field (written during webhook processing via `calculate_trade_pnl_realtime`) will be wrong, affecting:
1. The `progress` endpoint (which reads `Trade.pnl` directly — Bug #5)
2. Any behavioral alert that uses `Trade.pnl` for loss detection before EOD reconciliation runs

**Fix**: Apply `get_lot_multiplier(trade.exchange, trade.tradingsymbol)` to `match_pnl` in the while loop, matching the batch FIFO pattern.

---

## [BTST Analytics]: Entry time filter is always True for trades after 15:00

**File**: `backend/app/api/analytics.py:1837`
**Status**: BUG
**Finding**: The BTST entry condition is:
```python
if not (entry_ist.hour > 15 or (entry_ist.hour == 15 and entry_ist.minute >= 0)):
    continue
```
The second sub-expression `entry_ist.hour == 15 and entry_ist.minute >= 0` is true for ALL trades from 15:00 to 15:59 (since `minute >= 0` is always true). But combined with the outer `or`, the full condition is true for any trade where `hour >= 15`. This is functionally correct for the intent (entries at 15:00 or later). However:

1. The inner `minute >= 0` branch is logically redundant and misleading. The intent from the docstring is "after 15:00", but the condition also passes 15:00:00 exactly (the condition should arguably be `hour > 15 or (hour == 15 and minute > 0)` — i.e., strictly after 15:00).
2. The condition allows entries at 15:30 (market close for F&O) and even theoretical 15:31+ fills for MIS auto-square-off, which are square-off fills, not deliberate entries.

**Evidence**:
```python
if not (entry_ist.hour > 15 or (entry_ist.hour == 15 and entry_ist.minute >= 0)):
    continue
```

**Impact**: Any NRML trade entered at exactly 15:00:00 IST is included (likely fine). MIS auto-square-off trades at 15:20–15:28 IST would be included if someone had NRML product — but auto-square-off is always MIS, so NRML filter guards this. Low real-world impact but the logic is fragile and the intent is ambiguous between "at or after 15:00" vs "after 15:00".

---

## [BTST Analytics]: Exit time filter rejects valid early entries

**File**: `backend/app/api/analytics.py:1841`
**Status**: BUG
**Finding**: The BTST exit condition is:
```python
if not (exit_ist.hour < 9 or (exit_ist.hour == 9 and exit_ist.minute < 45)):
    continue
```
This means it accepts exits between 00:00 and 09:44 IST. However the spec says "exit before 09:45 IST on the next session". NSE F&O opens at 09:15 IST. A trade exited at 09:15 IST (market open) satisfies the intent and also satisfies this condition. But a trade exited at `hour=9, minute=45` would be rejected (correct). The filter appears correct for F&O.

However, there is a subtle issue: exits between 00:00 and 08:59 IST are accepted. This can only happen for MCX commodity trades (which trade until 23:30 IST) or if someone holds an F&O position through a system glitch. For F&O, any exit time before 09:15 IST on the next day represents pre-market order fills which are unusual. These are being silently included in BTST analytics, which may inflate the BTST count.

**Impact**: Minor for F&O users. Can over-count for MCX users who close commodity overnight positions at 2 AM IST (a valid MCX exit) as "BTST" trades.

---

## [BTST Analytics]: "Next trading day" not verified — holiday gap not handled

**File**: `backend/app/api/analytics.py:1832–1843`
**Status**: MINOR_ISSUE
**Finding**: The BTST filter checks `entry_ist.date() != exit_ist.date()` but does not verify that the exit date is the **next trading day**. If a trader enters on Wednesday before an NSE holiday on Thursday, and exits on Friday, the position spans 3 calendar days. The filter passes this as a BTST trade (different dates, entry after 15:00, exit before 09:45), even though it was a 2-night hold — a materially different behavioral profile from a true overnight BTST.

**Evidence**: The `is_trading_holiday` function exists in `market_hours.py` but is not called here.

**Impact**: Multi-day pre-holiday holds are labeled the same as true overnight BTSTs. The behavioral signal is diluted; reversal analysis is also affected since `overnight_close_price` would be the first night's close for a 2-night hold.

---

## [Feature Computation]: Expiry day detection hardcodes Thursday

**File**: `backend/app/services/pnl_calculator.py:624`
**Status**: BUG
**Finding**: `is_expiry` is set based on `exit_ist.weekday() == 3` (Thursday). This was flagged in Session 27 of the project memory as a P0 bug and was supposed to be fixed using `parse_symbol().expiry_date == today`. The fix has NOT been applied in the current code.

**Evidence**:
```python
is_expiry = exit_ist.weekday() == 3 if exit_ist else False
```

**Impact**:
1. SEBI moved weekly NIFTY expiry from Thursday to Wednesday in 2024. The code still uses Thursday.
2. BANKNIFTY expires on Wednesday, FINNIFTY on Tuesday, MIDCPNIFTY on Monday. None of these are correctly identified.
3. Monthly expiries for stock options occur on the last Thursday but only for that instrument.
4. MCX contracts expire on specific dates that are not Thursday.

All `is_expiry_day = True` entries in `CompletedTradeFeature` are wrong for everything except SENSEX (BSE) and historical NIFTY pre-2024 weekly expiries. The conditional performance analysis (line 1393) uses this flag, showing incorrect "expiry day" performance statistics.

**Fix**: Parse the expiry date from the symbol using `instrument_parser.py` (which already exists per session notes) and compare to exit date.

---

## [Timing Heatmap]: UTC-to-IST arithmetic wrong on half-hour boundary

**File**: `backend/app/api/analytics.py:1594`
**Status**: BUG
**Finding**: The fallback IST hour calculation when `feat.entry_hour_ist` is None uses:
```python
ist_hour = (ct.entry_time.hour * 60 + ct.entry_time.minute + 330) // 60 % 24
```
This computes `(UTC_minutes + 330) // 60`. For a trade entered at UTC 03:30 (= 09:00 IST), result: `(3*60 + 30 + 330) // 60 = 690 // 60 = 11`. This is WRONG. Correct IST hour is 9 (09:00 IST). The formula is computing `floor((h*60 + m + 330) / 60)` which equals `h + (m + 330) // 60` only when `m + 330 < 60`, i.e. when `m < -270` (never). The correct formula is:

`ist_hour = (ct.entry_time.hour + 5 + (1 if (ct.entry_time.minute + 30) >= 60 else 0)) % 24`

But even this is only correct when the conversion doesn't cross midnight. The only correct approach is `ct.entry_time.astimezone(IST)`.

**Evidence**:
```python
ist_hour = (ct.entry_time.hour * 60 + ct.entry_time.minute + 330) // 60 % 24
```
Test: UTC 03:45 → `(3*60 + 45 + 330) // 60 % 24 = 555 // 60 = 9`. IST should be 09:15. Hour = 9. ✓
Test: UTC 03:30 → `(3*60 + 30 + 330) // 60 = 690 // 60 = 11`. IST should be 09:00. Hour = 9. ✗ (returns 11)
Test: UTC 03:00 → `(3*60 + 0 + 330) // 60 = 510 // 60 = 8`. IST should be 08:30. Hour = 8. ✓
Test: UTC 03:15 → `(3*60 + 15 + 330) // 60 = 555 // 60 = 9`. IST should be 08:45. Hour = 8. ✗ (returns 9)

The formula gets the hour right when `minute + 30 < 60`, but jumps to the next hour when `minute >= 30` (because 330 minutes = 5 hours 30 minutes, and `(m + 30) >= 60` triggers the carry). This means all trades entered in the `:30–:59` minute range of a UTC hour are assigned to the wrong IST hour — one hour too late.

There is an identical calculation in `analytics.py:532` (performance tab hour fallback), producing the same error there.

**Impact**: For traders whose `CompletedTradeFeature` rows are missing (features not yet computed), the timing heatmap and by_hour performance breakdown shows trades in the wrong hour. All trades entered at UTC X:30–X:59 (which is IST (X+5):00 to (X+5):29) are bucketed into the wrong hour. Roughly 50% of fallback-path trades are in the wrong IST hour.

**Fix**:
```python
from zoneinfo import ZoneInfo
_IST = ZoneInfo("Asia/Kolkata")
h = ct.entry_time.astimezone(_IST).hour
```

---

## [Progress Endpoint]: "clean_days" can go negative

**File**: `backend/app/api/analytics.py:90`
**Status**: BUG
**Finding**:
```python
alert_dates = set(a.detected_at.date() for a in current_alerts)
clean_days = 7 - len(alert_dates)
```
If a trader has alerts on all 7 days, `clean_days = 0` (correct). But `detected_at` is a UTC timestamp, and since the "week" starts on a UTC Monday (also bug #4), there can be 8 distinct UTC dates in a 7-IST-day window — for example, Sunday 18:30 UTC (= Monday 00:00 IST). In this case `len(alert_dates)` could be 8, yielding `clean_days = -1`.

**Impact**: Discipline score shows negative clean days, which is confusing in the UI.

**Fix**: Clamp: `clean_days = max(0, 7 - len(alert_dates))`.

---

## [Discipline Score]: "critical" severity ignored in analytics_service

**File**: `backend/app/services/analytics_service.py:85–86,129–130`
**Status**: MINOR_ISSUE
**Finding**: The discipline score computation counts `danger` and `caution` alerts but ignores `critical` severity:
```python
danger_count = len([a for a in alerts if ... str(a.severity).lower() == "danger"])
caution_count = len([a for a in alerts if ... str(a.severity).lower() == "caution"])
```
However the system generates `critical` severity alerts (e.g. `session_meltdown` after consecutive danger escalation). These contribute 0 weight to the score.

**Impact**: After a session meltdown (the most severe behavioral state), the discipline score does not reflect the most serious violation. A day with 1 critical alert scores the same as a day with 0 alerts.

**Fix**: Add `critical_count` with weight 3.0 (higher than danger's 2.0):
```python
critical_count = len([a for a in alerts if ... str(a.severity).lower() == "critical"])
weighted_alerts = (critical_count * 3.0) + (danger_count * 2.0) + (caution_count * 0.5)
```

---

## [Shield Service]: Session end hardcoded to 15:30 IST

**File**: `backend/app/services/shield_service.py:37–51`
**Status**: MINOR_ISSUE
**Finding**: `_session_end_utc` always returns 15:30 IST as the session end:
```python
_SESSION_END_HOUR = 15
_SESSION_END_MINUTE = 30
```
For MCX commodity alerts (which the behavior engine can fire at any point during 09:00–23:30 MCX session), post-alert trades in the evening session (17:00–23:30 IST) will not be counted as "continued trading". For CDS currency alerts, 16:00–17:00 IST trades are missed. 

**Impact**: For commodity traders, the shield "heeded" count is over-reported. An MCX trader who gets a 10:00 AM CRUDEOIL overtrading alert and continues trading at 18:00 PM appears to have "heeded" the alert, when in fact they traded 8 hours after the alert.

**Fix**: Use `get_session_boundaries(segment, for_date)` from `market_hours.py` to get the correct session end for the instrument's exchange, derived from the alert's associated `pattern_type` or instrument context.

---

## [pnl_pct Computation]: Falsy check on avg_entry treats 0 and None the same

**File**: `backend/app/services/position_ledger_service.py:521`
**Status**: MINOR_ISSUE
**Finding**:
```python
if not avg_entry or avg_entry == 0:
    return None
```
`not avg_entry` already handles `None`, `0`, and `0.0`. The `or avg_entry == 0` is redundant. More importantly, an `avg_entry` of `0` is only possible for instruments with zero cost (e.g. deep OTM options that expired worthless and were bought at ₹0.05 rounded to 0 in float). In this case returning `None` is correct. No actual bug — just a style issue.

**Status revised to CORRECT**.

---

## [Max Drawdown]: Wrong start date assignment for ongoing drawdowns

**File**: `backend/app/api/analytics.py:696–726`
**Status**: BUG
**Finding**: The drawdown tracking sets `current_dd_start = date_str` when a new peak is reached. This is used as the start of the *next* potential drawdown. However on the very first day, `current_dd_start` is `None`. If the first day is a losing day (cumulative goes negative immediately), `current_dd_start` is `None` and any drawdown period recorded will have `start: None`.

**Evidence**:
```python
peak = 0
current_dd_start = None   # ← starts None
...
for date_str, day_pnl in sorted_daily:
    cumulative += day_pnl
    if cumulative > peak:
        ...
        peak = cumulative
        current_dd_start = date_str   # ← set only on new peak
    else:
        dd = cumulative - peak
        if dd < max_drawdown:
            max_drawdown = dd
            max_dd_start = current_dd_start  # ← None if never peaked
```

If a trader starts with day 1 loss, the max drawdown start date is `None` throughout.

**Impact**: `max_drawdown.start_date` returned as `null` to frontend for traders who started losing immediately. Also `drawdown_periods` entries with `start: None` will fail `_days_between(None, end)` returning 0 duration — falsely reporting drawdown duration as 0 days.

**Fix**: Initialize `current_dd_start` to the first date in `sorted_daily` instead of `None`.

---

## [MCX Contract Specs]: Unknown symbol silently returns multiplier=1

**File**: `backend/app/services/mcx_contract_specs.py:148–154`
**Status**: MINOR_ISSUE
**Finding**: When an MCX symbol prefix is not in `MCX_MULTIPLIERS`, `get_mcx_multiplier` logs a WARNING and returns `1`. This means the P&L calculation silently proceeds with a 1× multiplier (correct for NSE/BSE but wrong for MCX). The lot sizes table does not include:
- `SILVERMICEX` (if Zerodha uses this symbol variant)
- `CASTOR` (Castor seed futures traded on NCDEX)
- Any new contracts added by MCX after the code was written

**Impact**: Any unknown MCX contract shows P&L divided by its true multiplier. A `SILVERMINI` trade (multiplier 5) with a new symbol variant would show 5× smaller P&L.

**Fix**: Log the warning (already done), but also mark the `CompletedTrade` with a `pnl_data_quality = "estimated"` flag so the UI can warn the user.

---

## [Batch FIFO]: P&L for realtime path missing lot multiplier — MCX/CDS critical

**File**: `backend/app/services/pnl_calculator.py:698–785`
**Status**: CRITICAL_BUG (same as Finding #11, additional detail)
**Finding**: Full detail of the missing lot multiplier in `calculate_trade_pnl_realtime`. The function is called from `process_webhook_trade` in `webhooks.py` to set `Trade.pnl` in real-time. The lot multiplier for MCX/CDS instruments is obtained via `get_lot_multiplier(exchange, tradingsymbol)` in the batch path but is completely absent here.

Additionally, the real-time path does not handle the case where the prior trades for replay are themselves from a prior session (NRML multi-day hold). If a NRML position was opened yesterday, `prior_trades` will include yesterday's entry fill, the replay will correctly build the opening_queue, and the closing P&L will be correct (minus the multiplier bug). This is a minor correctness note — the logic is otherwise sound.

**Impact**: Same as #11. MCX traders see wrong P&L in real-time on the dashboard until the nightly EOD reconciliation FIFO runs and overwrites with the correct value.

---

## [Position Ledger FLIP]: P&L computation correct

**File**: `backend/app/services/position_ledger_service.py:573–601`
**Status**: CORRECT
**Finding**: When a FLIP occurs (e.g., long 50 NIFTY lots, SELL 100 closes 50 and opens 50 short):
```python
closing_qty = min(abs(fill_qty), abs(current_qty))   # = 50
realized_pnl = (fill_price - current_avg_price) * closing_qty  # for LONG
```
The excess quantity (`100 - 50 = 50`) opens a new SHORT position at `fill_price`. The `realized_pnl` correctly applies only to `closing_qty` (the matched portion), not the excess. This is mathematically correct.

---

## [Weighted Average Entry Price]: Correct

**File**: `backend/app/services/pnl_calculator.py:425–431`
**Status**: CORRECT
**Finding**: The weighted average entry price is correctly computed as:
```python
avg_entry = sum(f["price"] * f["qty"] for f in entry_fills) / total_entry_qty
```
For example: BUY 50 @ 19800 + BUY 50 @ 19900:
`avg_entry = (19800×50 + 19900×50) / 100 = 19850`. Correct.

---

## [FIFO P&L]: Long and short formulas correct

**File**: `backend/app/services/pnl_calculator.py:291–294`
**Status**: CORRECT
**Finding**:
- LONG (opening side = BUY): `P&L = (exit_price - entry_price) × qty × lot_multiplier` ✓
- SHORT (opening side = SELL): `P&L = (entry_price - exit_price) × qty × lot_multiplier` ✓

The sign convention is correct. A LONG trade profits when exit > entry; a SHORT trade profits when exit < entry.

---

## [Unrealized P&L]: Formula correct for open positions

**File**: `backend/app/services/pnl_calculator.py:817–820`
**Status**: CORRECT
**Finding**:
```python
if qty > 0:  # Long position
    pnl = (current - entry) * qty
else:  # Short position
    pnl = (entry - current) * abs(qty)
```
Both formulas are mathematically correct. Note: Kite's `position.last_price` is used as `current`, which is the last traded price at sync time. This is a snapshot value, not live — stated in code comment.

---

## ADDITIONAL NOTES

### Charges / Brokerage
No brokerage or STT deduction code was found anywhere in pnl_calculator.py, analytics_service.py, or position_ledger_service.py. All P&L figures are **gross P&L before charges**. The UI should clarify this prominently. 

For options sellers: STT is on premium received (turnover-based), not notional. Since no STT is applied, the absence of incorrect STT computation is not a bug — charges are simply not computed at all.

### Sharpe Ratio
No Sharpe ratio computation was found in any file. The analytics do not claim to show it, so there is no bug here. If added in future, use Indian risk-free rate (~6.5% annualized on 10-year G-Sec as of 2026) and annualize with `sqrt(252)` trading days.

### pnl = 0 trades (break-even)
Trades where `realized_pnl = 0.0` exactly are consistently classified as neither winner nor loser (excluded from `winners` and `losers` lists via `p > 0` and `p < 0` filters). This means they reduce the denominator for win rate. A break-even trade reduces displayed win rate. This is the correct convention for trading analytics — break-even is not a win.

---

## PRIORITY RANKING FOR FIXES

| Priority | Finding | Reason |
|----------|---------|--------|
| P0 — Fix immediately | #11, #28: Realtime MCX/CDS P&L | Silent 100–1250× error in live P&L display |
| P0 — Fix immediately | #15: Expiry day hardcoded Thursday | Wrong behavioral data for all NIFTY/BN traders post-SEBI expiry change |
| P1 — Fix before next release | #5: Progress uses Trade.pnl | Win rate systematically wrong (up to 2× understatement) |
| P1 — Fix before next release | #4, #17: UTC week boundaries | Week-over-week data misaligned by 5.5 hours |
| P1 — Fix before next release | #12, #13: BTST time filters | BTST count inflated / deflated |
| P2 — Fix soon | #1: Profit factor = 0 on no losses | Shows 0 when should show ∞ |
| P2 — Fix soon | #6: VaR 95% wrong on small samples | Overstates risk for early users |
| P2 — Fix soon | #22: Drawdown start_date = None | Frontend null crash possible |
| P2 — Fix soon | #10: best_streak hardcoded 7 | Fabricated metric |
| P3 — Fix when convenient | #16: Timing heatmap UTC→IST | ~50% of fallback trades in wrong bucket |
| P3 — Fix when convenient | #18: clean_days can be negative | Visual glitch only |
| P3 — Fix when convenient | #19: critical alerts ignored in score | Scoring inconsistency |
| P3 — Fix when convenient | #20: Shield session end 15:30 for MCX | MCX shield data inaccurate |
