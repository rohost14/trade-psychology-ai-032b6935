# Hedging & Multi-Leg Strategy — IMPLEMENTED
*Session 20 (2026-03-15): Production implementation complete. This doc updated from "gap" to reference.*

---

## Current State: Every Symbol is Independent

The FIFO system in `position_ledger_service.py` tracks each `tradingsymbol` independently.

```
NIFTY25500CE  → its own position (entry → exit)
NIFTY25500PE  → completely separate position
BANKNIFTY FUT → separate position
```

**Result**: A straddle (NIFTY CE + NIFTY PE) looks like two unrelated trades.
The system has zero awareness that these two positions hedge each other.

---

## Why This Matters for Behavioral Detection

### Problem 1: False "loss" alerts on hedge legs
If you buy NIFTY 25500 CE + NIFTY 25500 PE as a straddle, and the CE leg shows a loss at T+30 minutes, the BehaviorEngine fires `consecutive_loss_streak` or `session_meltdown`. But you're not actually losing — the PE leg may be up ₹8,000 while CE is down ₹3,000. Net P&L = +₹5,000.

### Problem 2: False `size_escalation` / `excess_exposure`
Adding a hedge leg (buy PE to protect a CE position) looks like "increasing exposure" to the system. It's the opposite — it's reducing risk.

### Problem 3: `revenge_trade` false trigger
Closing the CE leg of a strangle and immediately opening a wider CE = adjusting the position. The system calls it revenge trading.

### Problem 4: Analytics are wrong
The Analytics tab shows "avg P&L per trade" counting each leg independently. A straddle that made ₹5,000 shows as "CE: -₹3,000" and "PE: +₹8,000" = two trades averaging +₹2,500. The correct view is: 1 strategy decision = +₹5,000.

---

## Strategies That Need Grouping

| Strategy | Legs | Detection signal |
|----------|------|-----------------|
| **Straddle** | Buy ATM CE + Buy ATM PE | Same underlying + same expiry + same strike + both buy + within 5 min |
| **Strangle** | Buy OTM CE + Buy OTM PE | Same underlying + same expiry + different strikes + both buy + within 5 min |
| **Short Straddle** | Sell ATM CE + Sell ATM PE | Same as straddle but both sell |
| **Short Strangle** | Sell OTM CE + Sell OTM PE | Same as strangle but both sell |
| **Bull Call Spread** | Buy CE (lower strike) + Sell CE (higher strike) | Same underlying + same expiry + same instrument type + opposite sides |
| **Bear Put Spread** | Buy PE (higher strike) + Sell PE (lower strike) | Same pattern |
| **Iron Condor** | Short strangle + long strangle (4 legs) | 4 legs, same underlying, same expiry, 2 CE + 2 PE |
| **Iron Butterfly** | Sell ATM CE/PE + Buy OTM CE/PE | 4 legs at 3 strikes |
| **Futures Hedge** | Long futures + Buy put | Same underlying, different instrument types (FUT + PE) |
| **Calendar Spread** | Buy near-month CE + Sell far-month CE | Same underlying + same strike + different expiries |
| **Synthetic Long** | Buy CE + Sell PE (same strike) | Creates synthetic futures position |
| **Covered Call** | Holdings + Sell CE (delivery) | CNC equity + NFO CE sell |

---

## What Needs to Be Built

### Phase 1: StrategyGroup Model (New DB table)

```sql
CREATE TABLE strategy_groups (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id),
    strategy_type    VARCHAR(50),  -- 'straddle' | 'strangle' | 'iron_condor' | ...
    underlying       VARCHAR(50),  -- 'NIFTY' | 'BANKNIFTY'
    expiry_date      DATE,
    status           VARCHAR(20) DEFAULT 'open',  -- 'open' | 'partially_closed' | 'closed'
    net_pnl          NUMERIC(15, 4),              -- sum of all leg P&Ls
    opened_at        TIMESTAMPTZ,
    closed_at        TIMESTAMPTZ,
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE strategy_group_legs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_group_id   UUID NOT NULL REFERENCES strategy_groups(id),
    completed_trade_id  UUID NOT NULL REFERENCES completed_trades(id),
    leg_role            VARCHAR(20),  -- 'long_call' | 'short_call' | 'long_put' | 'short_put' | 'futures'
    leg_pnl             NUMERIC(15, 4),
    created_at          TIMESTAMPTZ DEFAULT now()
);
```

### Phase 2: Strategy Detection Service

`strategy_detector.py` — runs after FIFO creates a CompletedTrade:

```python
def detect_strategy(completed_trade, recent_trades, window_minutes=15) -> Optional[StrategyGroup]:
    """
    Look at trades in the last 15 minutes on the same underlying.
    Match against known patterns.
    Return a StrategyGroup if a multi-leg strategy is detected.
    """
    underlying = extract_underlying(completed_trade.tradingsymbol)  # 'NIFTY25500CE' → 'NIFTY'
    expiry = extract_expiry(completed_trade.tradingsymbol)           # 'NIFTY25500CE' → '25MAR2025'

    # Find candidates: same underlying, same expiry, recent, different symbol
    candidates = [t for t in recent_trades
                  if extract_underlying(t.tradingsymbol) == underlying
                  and extract_expiry(t.tradingsymbol) == expiry
                  and t.id != completed_trade.id
                  and (completed_trade.entry_time - t.entry_time).seconds < window_minutes * 60]

    if not candidates:
        return None

    return _classify_strategy(completed_trade, candidates)
```

Strategy classification rules:
```python
def _classify_strategy(trade, candidates):
    types = set([trade.instrument_type] + [c.instrument_type for c in candidates])
    sides = set([trade.direction] + [c.direction for c in candidates])
    strikes = set([extract_strike(trade.tradingsymbol)] + [extract_strike(c.tradingsymbol) for c in candidates])
    n_legs = 1 + len(candidates)

    # Straddle: CE + PE, same strike, both LONG or both SHORT
    if types == {'CE', 'PE'} and len(strikes) == 1 and n_legs == 2:
        if sides == {'LONG'}:  return 'straddle_buy'
        if sides == {'SHORT'}: return 'straddle_sell'

    # Strangle: CE + PE, different strikes
    if types == {'CE', 'PE'} and len(strikes) == 2 and n_legs == 2:
        if sides == {'LONG'}:  return 'strangle_buy'
        if sides == {'SHORT'}: return 'strangle_sell'

    # Iron condor: 4 legs, CE + PE, both directions
    if types == {'CE', 'PE'} and sides == {'LONG', 'SHORT'} and n_legs == 4:
        return 'iron_condor'

    # Futures hedge: FUT + PE (or FUT + CE)
    if 'FUT' in types and ('CE' in types or 'PE' in types) and n_legs == 2:
        return 'futures_hedge'

    # Vertical spread: 2 legs, same type (CE+CE or PE+PE), different strikes, opposite sides
    if len(types) == 1 and sides == {'LONG', 'SHORT'} and n_legs == 2:
        t = list(types)[0]
        if t == 'CE': return 'bull_call_spread'
        if t == 'PE': return 'bear_put_spread'

    return 'multi_leg_unknown'
```

### Phase 3: Update BehaviorEngine

When a trade belongs to a strategy group, pass `strategy_context` to detectors:

```python
# In BehaviorEngine._load_context():
strategy = await strategy_detector.get_group(completed_trade.id, db)
ctx.strategy_group = strategy

# In _detect_revenge_trade():
if ctx.strategy_group:
    return None  # Never flag strategy adjustments as revenge

# In _detect_session_meltdown():
if ctx.strategy_group:
    pnl = ctx.strategy_group.net_pnl  # Use strategy P&L, not individual leg P&L
```

### Phase 4: Analytics Grouping

Update `analytics_service.py` to show:
- Strategy-level P&L (not per-leg)
- "You ran 4 straddles this month. Net: +₹18,400"
- Pattern analytics exclude hedge-leg trades from individual pattern detection
- New "Strategies" tab in Analytics with strategy breakdown

---

## Instrument Symbol Parsing (CRITICAL)

Kite symbols follow NSE/BSE naming:
```
NIFTY2532025000CE   → NIFTY, expiry=25320 (25 Mar 2025), strike=25000, CE
BANKNIFTY25APRFUT   → BANKNIFTY, expiry=25APR, FUT
RELIANCE            → RELIANCE, EQ
```

Need robust parser:
```python
import re

def extract_underlying(symbol: str) -> str:
    """NIFTY2532025000CE → NIFTY"""
    # Futures: symbol ends with FUT
    if symbol.endswith('FUT'):
        return re.sub(r'\d{2}[A-Z]{3}FUT$', '', symbol)
    # Options: symbol ends with CE or PE + digits + CE/PE
    m = re.match(r'^([A-Z]+)\d+[A-Z0-9]+(?:CE|PE)$', symbol)
    return m.group(1) if m else symbol

def extract_strike(symbol: str) -> Optional[int]:
    """NIFTY2532025000CE → 25000"""
    m = re.search(r'(\d{4,6})(?:CE|PE)$', symbol)
    return int(m.group(1)) if m else None

def extract_expiry(symbol: str) -> Optional[str]:
    """NIFTY2532025000CE → '25320' (yyMMd for weekly, or yyMMM for monthly)"""
    m = re.match(r'^[A-Z]+(\d{5}|\d{2}[A-Z]{3})', symbol)
    return m.group(1) if m else None
```

---

## Implementation Status (Session 20 — 2026-03-15)

| Phase | Work | Status | Files |
|-------|------|--------|-------|
| Symbol parser | `instrument_parser.py` | ✅ Done | `backend/app/services/instrument_parser.py` |
| `StrategyGroup` + `StrategyGroupLeg` models | New models + migration 046 | ✅ Done | `backend/app/models/strategy_group.py`, `backend/migrations/046_strategy_groups.sql` |
| `strategy_detector.py` — 15 strategy types | New service | ✅ Done | `backend/app/services/strategy_detector.py` |
| BehaviorEngine strategy-aware suppression | `behavior_engine.py` | ✅ Done | Suppresses 4 patterns on strategy legs; uses strategy net_pnl for meltdown |
| Wire into trade pipeline | `trade_tasks.py` | ✅ Done | `detect_and_save()` called after FIFO creates CompletedTrade |
| Analytics strategy grouping | `analytics_service.py` | P2 — pending | Future work |
| Frontend strategy display (grouped legs) | Dashboard + Analytics | P2 — pending | Future work |

**Migration 046 must be applied in Supabase before deployment.**

### Known Limitation (Phase 2 — Future)

The first leg of a strategy may still fire alerts (we don't know it's a strategy leg until
the second leg closes). Full entry-time detection using open Positions (before any leg closes)
requires extending the pipeline to run strategy detection on each webhook fill, not just on
CompletedTrade creation. This is tracked as a P2 improvement.

No UI needed immediately — AI coach can reference: "This trade was marked as a strategy leg, so no alerts fired."
