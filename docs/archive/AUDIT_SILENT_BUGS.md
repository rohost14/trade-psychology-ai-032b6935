# Silent Bug Audit — TradeMentor AI
**Date**: 2026-03-18
**Trigger**: `first_entry_time` NULL discovered via Portfolio Chat session
**Scope**: Entire backend trading pipeline
**Standard**: Zerodha partnership-level technical review

---

## Executive Summary

| Severity | Count | Status |
|---|---|---|
| CRITICAL | 2 | ❌ Must fix before any partnership demo |
| HIGH | 4 | ❌ Must fix before production traffic |
| MEDIUM | 4 | ⚠️ Fix within 1 week of launch |
| LOW | 2 | Fix when convenient |

---

## CRITICAL

### C1 — Expiry Day Detection Hardcoded to Thursday
**File**: `behavior_engine.py` lines ~847, ~952
**Impact**: Every F&O expiry-based behavioral alert fires on the WRONG day.

```python
# WRONG — hardcoded Thursday
is_expiry_day = (entry_ist.weekday() == 3)
```

- Weekly expiry can be Wednesday or Friday when Thursday is a holiday
- Monthly expiry varies by month
- SEBI can change the schedule; any change breaks all F&O alerts
- Affects: `fomo_entry`, `no_stoploss` tighter thresholds on expiry day
- **All expiry-day behavioral data in DB is unreliable**

**Fix**: Replace `weekday() == 3` with `parse_symbol(symbol).expiry_date == today`

---

### C2 — `last_entry_time` Field Does Not Exist on Position Model
**File**: `position.py` (model), `position_monitor_tasks.py` lines ~181, ~297
**Impact**: The holding-loser alert feature is **completely non-functional**. Silent AttributeError.

```python
# position_monitor_tasks.py — uses field that doesn't exist:
if position.last_entry_time:  # AttributeError — only first_entry_time exists
    hold_min = (now - position.last_entry_time).total_seconds() / 60

# position.py — model only has:
first_entry_time = Column(DateTime(timezone=True))
# last_entry_time is NEVER defined
```

- "Holding loser for 30+ minutes" alert never fires — ever
- Duration calculations in position monitor are completely broken
- This is a core safety feature for F&O traders — silent failure is dangerous

**Fix**: Add `last_entry_time` column, migration, backfill from `first_entry_time`

---

## HIGH

### H1 — Race Condition in processed_at Idempotency Check (Not Atomic)
**File**: `trade_tasks.py` lines ~165–183
**Impact**: Two Celery workers processing the same order can BOTH pass the idempotency gate → duplicate P&L calculation, duplicate alerts, duplicate strategy detection.

```python
# Non-atomic check-then-set:
fresh = await db.get(Trade, trade.id)
if fresh.processed_at is not None:
    return  # Worker A exits

# Worker B passes the same check 50ms later (before Worker A commits)
await db.execute(
    update(Trade).where(Trade.id == id, Trade.processed_at == None)
    .values(processed_at=now)
)
# Both workers now run the full pipeline
```

Redis lock partially mitigates but does NOT fix the race in the idempotency check itself.

**Fix**: Use `UPDATE ... WHERE processed_at IS NULL RETURNING id` — if 0 rows returned, another worker won. Check `result.rowcount == 1` before proceeding.

---

### H2 — Out-of-Order Webhook Processing (No State Machine)
**File**: `webhooks.py` + `trade_sync_service.py`
**Impact**: Zerodha can send COMPLETE before OPEN (network reordering). Current code has no state transition validation — a COMPLETE trade can be downgraded to OPEN status by a late-arriving webhook.

```python
# upsert_trade() blindly overwrites all fields including status:
for key, value in trade_data.items():
    setattr(existing_trade, key, value)  # COMPLETE → OPEN is allowed
```

**Fix**: Add `VALID_TRANSITIONS` dict. Reject status downgrades: `COMPLETE → OPEN` is invalid.

---

### H3 — NULL Timestamps Cause Silent Partial Behavioral Analysis
**File**: `pnl_calculator.py`, `behavior_engine.py`
**Impact**: If Zerodha postback arrives without `order_timestamp` (happens on retries/edge cases), the trade is processed but all timing-based patterns (FOMO timing, session meltdown hours, expiry-day thresholds) are silently skipped. The alert may still fire but with wrong/missing context.

**Fix**: Reject webhook payloads where all three timestamps (`order_timestamp`, `exchange_timestamp`, `fill_timestamp`) are NULL. Log as ERROR.

---

### H4 — FIFO Lock TTL Can Expire During Slow P&L Query
**File**: `trade_tasks.py` lines ~188–206
**Impact**: The Redis FIFO lock has 60s TTL. If the DB is slow (long P&L calculation), the lock expires while FIFO is still running. A second worker reacquires the lock and runs FIFO on partially-updated data → corrupted P&L.

**Fix**: Extend TTL to 120s, or (better) move `pnl_calculator` outside the lock — it's idempotent and doesn't need the lock.

---

## MEDIUM

### M1 — Overnight Position Backfill Too Broad
**File**: `trade_sync_service.py` lines ~660–667
**Impact**: Overnight-closed detection doesn't verify an entry leg exists in our DB. Can create phantom `CompletedTrade` records for positions we never tracked → corrupts P&L history and behavioral baselines.

**Fix**: Before adding to `overnight_closed` list, check that at least one BUY trade exists in DB for that symbol today.

---

### M2 — Strategy Leg Suppression Silently Fails
**File**: `trade_tasks.py` line ~275, `behavior_engine.py` lines ~768–773
**Impact**: If strategy detection throws an exception (caught as WARNING), `strategy_group` stays None. The behavior engine then alerts on a losing leg of a profitable hedge spread as if it were a standalone loss → false danger alerts.

**Fix**: Log strategy detection failures as ERROR. In behavior engine: if strategy_group is None AND the trade looks like a derivative, defer alert to manual queue rather than firing immediately.

---

### M3 — Margin Insolvency Hidden as 100% Utilisation
**File**: `margin_service.py` lines ~124–127
**Impact**: If account `live_balance < 0` (debit balance / margin call territory), the code reports `utilization_pct = 100%`. Caller has no way to distinguish "fully used" from "in debt". Risk calculations downstream may not trigger critical alerts.

**Fix**: Return `is_insolvent: True` flag when `live_balance < 0`. Surface as a distinct alert level.

---

### M4 — MCX/Evening Trading Missed by Hardcoded Market Hours
**File**: `position_monitor_tasks.py` lines ~67, ~250
**Impact**: Position monitor only checks 09:15–15:25 IST. MCX closes at 23:30. Any MCX commodity position held into evening is never monitored after 15:25.

**Fix**: Make market hours segment-aware. Check `exchange` field on position to determine correct window.

---

## LOW

### L1 — `first_entry_time` Was Never Set on REST-Synced Positions (FIXED)
**Status**: ✅ Fixed 2026-03-18
`_sync_positions` now backfills `first_entry_time` from today's BUY trades in DB.

### L2 — Portfolio Chat LLM Gave Psychology Advice Instead of Data (FIXED)
**Status**: ✅ Fixed 2026-03-18
System prompt hardened with explicit prohibition on behavioural coaching.

---

## Fix Priority

| # | Issue | Effort | Status |
|---|---|---|---|
| C1 | Expiry day parse from symbol | 2h | ✅ Fixed 2026-03-18 — `is_expiry_day()` in instrument_parser.py |
| C2 | Add last_entry_time column + migration 054 | 1h | ✅ Fixed 2026-03-18 — model + sync backfill |
| H1 | Atomic processed_at claim (rowcount check) | 1h | ✅ Fixed 2026-03-18 — UPDATE rowcount==1 |
| H2 | State transition validation (no downgrades) | 1h | ✅ Fixed 2026-03-18 — TERMINAL status guard in upsert_trade |
| H3 | Reject NULL-timestamp webhooks | 30m | ✅ Fixed 2026-03-20 — early return before trade_data build |
| H4 | FIFO lock TTL 60→120s + exponential backoff | 30m | ✅ Fixed 2026-03-18 |
| M1 | Overnight backfill guard | 1h | ✅ Fixed 2026-03-20 — BUY entry count check before overnight_closed |
| M2 | Strategy detection ERROR logging | 30m | ✅ Fixed 2026-03-18 |
| M3 | Margin insolvency flag | 30m | ✅ Fixed 2026-03-20 — is_insolvent in segment + overall dict |
| M4 | Segment-aware market hours | 2h | ⚠️ Post-launch |
