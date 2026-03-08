# Trade Data Architecture Overhaul

## Executive Summary

Production-ready implementation plan for overhauling TradeMentor's trade data and behavioral signal pipelines. Based on `trade_position_logic.md`, cross-checked against the current codebase, and incorporating all issues from `ISSUE_WITH TRADE_ARCHITECTURE.md`.

**Two pipelines, clearly separated:**

```
DATA PIPELINE (Phases 1-5):  Sync → Trades → FIFO → CompletedTrades → API → Frontend
SIGNAL PIPELINE (Phases 6-7): Fill arrives → Evaluator → BehavioralEvent → Push to client
```

FIFO is deterministic, idempotent, replayable. Behavioral detection is event-driven, runs AFTER data pipeline, never mutates trades/positions/P&L.

---

## Table Map (What Stores What, Who Reads What)

| Table | Layer | Purpose | Who Reads It |
|-------|-------|---------|--------------|
| `trades` | Execution Ledger | Immutable fills. One row = one execution. Never edited. | FIFO matcher (input), behavioral evaluator (recent fills) |
| `positions` | Position State | Live open positions. Mirrors Zerodha exactly. | Real-time nudges, dashboard "Open Positions", unrealized P&L |
| `completed_trades` | Decision Lifecycle | Flat-to-flat rounds. Created ONLY when position goes zero. One row = one decision. Immutable once created. | Dashboard "Completed Trades", AI learning, reports, win rate, performance stats |
| `completed_trade_features` | ML Features | Derived feature vectors per completed trade. Computed post-FIFO. Rebuildable. | Pattern prediction, AI personalization, clustering |
| `incomplete_positions` | Data Integrity | Flags sync gaps where fills don't add up. Detected automatically. | Reports (exclusion + warning), dashboard (prompt user to resolve) |
| `behavioral_events` | Signal Layer | Durable, queryable behavioral detections. Append-only. One row = one detected signal with confidence. | Behavior timeline UI, alert delivery, escalation, AI training, daily summaries |

---

## Current Bugs (Why This Overhaul Is Needed)

### Bug 1: Duplicate Trades
**File:** `trade_sync_service.py` lines 356-376
**Issue:** Step 3 "Sync Orders" fetches `/orders` and pushes them into the `trades` table. But Step 1 already synced `/trades` (fills). Different dedup keys = double every completed trade.
**Impact:** All 6 behavioral services get wrong data.

### Bug 2: lot_size Double-Counting in FIFO P&L
**File:** `pnl_calculator.py` lines 225, 228, 346, 349
**Issue:** FIFO multiplies `qty * lot_size`. Kite already returns qty in units. F&O P&L is 65x too high.

### Bug 3: Flawed Position Quantity Sign Override
**File:** `trade_sync_service.py` lines 285-290
**Issue:** Today-only `buy_qty`/`sell_qty` overrides position sign. Breaks overnight positions.

### Bug 4: No Position Lifecycle Tracking
**Issue:** No flat-to-flat completed trade records. Dashboard shows raw fills instead of decision outcomes.

### Bug 5: CNC/Delivery Trades Polluting Data
**Issue:** User only trades MIS/NRML/MTF. CNC pollutes behavioral analysis.

### Bug 6: Behavioral Detection Coupled With Sync Pipeline
**File:** `trade_sync_service.py` lines 392-501
**Issue:** `risk_detector.detect_patterns()` runs inside `sync_trades_for_broker_account()`. This means behavioral detection is embedded in the data sync pipeline. If FIFO re-runs, behavioral detection re-runs and may produce inconsistent alerts.
**Impact:** Non-idempotent behavioral signals. Backfills corrupt alert history.

### Bug 7: No Durable Behavioral Event Store
**Issue:** `risk_alerts` table lacks confidence scoring, delivery tracking, position context, and event-type taxonomy. Behavioral detections are computed inline by scattered services with no single source of truth.
**Impact:** No behavior timeline UI, no explainability, no alert deduplication, no historical learning.

---

## Architecture: Two Pipelines

### Data Pipeline (deterministic, idempotent, replayable)
```
Zerodha /trades → trades table (immutable fills)
Zerodha /positions → positions table (live state)
trades table → FIFO matcher → completed_trades (flat-to-flat rounds)
                            → Trade.pnl updated (backward compat)
                            → incomplete_positions (gap detection)
completed_trades → completed_trade_features (post-FIFO, separate step)
```

### Signal Pipeline (event-driven, runs AFTER data pipeline, never mutates data)
```
New fill inserted → BehavioralEvaluator.evaluate(fill)
  reads: positions, recent trades, recent behavioral_events
  emits: zero or more behavioral_events (persisted first)
  → WebSocket push to connected clients (only after DB insert)
  → Cooldown/escalation check (rate limiter)
  → Optional: WhatsApp via existing infrastructure
```

**Hard constraint:** Signal pipeline MUST NOT mutate trades, positions, or P&L. FIFO MUST NOT emit behavioral signals.

---

## Why Flat-to-Flat Rounds (Not Per-Exit)

Trader buys 195 NIFTY CE @ 25, sells 130 @ 15, sells 65 @ 35:

| | Per-Exit (WRONG) | Flat-to-Flat (CORRECT) |
|---|---|---|
| Records | 2 ("trades") | 1 (decision) |
| Win rate | 50% (1W 1L) | 0% (1L) |
| Trade count | 2 | 1 |
| Duration | Fragments | 2 days (real hold) |
| AI learns | "Lost on trade 1, won on trade 2" | "Decision to go long lost 650" |
| Revenge detect | Partial exit looks like new trade | Partial exit stays in same round |

One decision = one row. This is what a trading psychology app needs.

---

## Implementation Plan

### Phase 1: Fix Data Pipeline Bugs ✅ COMPLETED

#### Step 1.1: Remove Order-to-Trades Push
**File:** `backend/app/services/trade_sync_service.py`
**Action:** Delete lines 356-376 (the "Step 3: Sync Orders" block). Orders already sync to the `orders` table via `sync_orders_to_db()`.

#### Step 1.2: Add Product Filter
**File:** `backend/app/services/trade_sync_service.py`
**Action:** Add `TRACKED_PRODUCTS = {"MIS", "NRML", "MTF"}` at module level. Filter both the `/trades` sync loop (line 232) and positions sync loop (line 278) — `continue` if product not in set.

#### Step 1.3: Remove Position Quantity Sign Override
**File:** `backend/app/services/trade_sync_service.py`
**Action:** Delete lines 285-290 (buy_qty/sell_qty sign override). Kite's `quantity` is already correctly signed.

#### Step 1.4: Remove lot_size Multiplication from P&L
**File:** `backend/app/services/pnl_calculator.py`

| Location | Change |
|----------|--------|
| Batch FIFO (lines 225, 228) | Remove `* lot_size` |
| Realtime FIFO (lines 346, 349) | Remove `* lot_size` |
| Unrealized P&L (lines 394, 396) | Remove `* multiplier` |
| `calculate_and_update_pnl()` loop | Remove `get_lot_size()` call |
| `_process_symbol_trades()` signature | Remove `lot_size` parameter |
| `get_unrealized_pnl()` | Remove `multiplier` variable |

**Keep:** `get_lot_size()` method and `_lot_size_cache` for future position sizing alerts.

#### Step 1.5: Skip Holdings Sync
**File:** `backend/app/api/zerodha.py`
**Action:** Comment out holdings sync call in `sync_all_data()` (line 568). Keep method available.

#### Step 1.6: Decouple Risk Detection from Sync
**File:** `backend/app/services/trade_sync_service.py`
**Action:** Remove the entire risk detection block (lines 392-501) from `sync_trades_for_broker_account()`. This block runs `risk_detector.detect_patterns()`, does deduplication, sends WhatsApp alerts — all inside the sync pipeline.

Move this to a separate post-sync step called from `sync_all_data()` in zerodha.py AFTER the data pipeline completes. This is a temporary measure until Phase 6 replaces it with the proper BehavioralEvaluator.

```python
# In zerodha.py sync_all_data(), after trade sync:
trade_result = await TradeSyncService.sync_trades_for_broker_account(broker_account_id, db)
results["trades"] = trade_result

# Risk detection runs AFTER data pipeline, NOT inside it
try:
    risk_result = await run_post_sync_risk_detection(broker_account_id, db)
    results["risk"] = risk_result
except Exception as e:
    logger.error(f"Post-sync risk detection failed (non-fatal): {e}")
```

#### Step 1.7: Add Session P&L Helper
**File:** `backend/app/core/market_hours.py`
**Action:** Add a `get_session_boundaries()` function that returns (start, end) for the current trading session in UTC. All services use this instead of computing "today" independently.

```python
def get_session_boundaries(segment: MarketSegment = MarketSegment.FNO,
                           for_date: Optional[date] = None) -> Tuple[datetime, datetime]:
    """
    Get trading session start/end in UTC for a given date.
    Session = market open to market close in IST, converted to UTC.
    All services MUST use this for session P&L calculations.
    """
    ...
```

**Locked definition:**
- Session = trading day in IST
- Starts at market open (09:15 IST for equity/F&O)
- Session P&L = realized P&L only
- Unrealized P&L used ONLY for live risk checks

---

### Phase 2: New Models + Migration ✅ COMPLETED

#### Step 2.1: CompletedTrade Model (Flat-to-Flat Round)
**New file:** `backend/app/models/completed_trade.py`

```python
class CompletedTrade(Base):
    __tablename__ = "completed_trades"

    id                  # UUID PK
    broker_account_id   # FK → broker_accounts

    # Instrument
    tradingsymbol       # String(100)
    exchange            # String(20)
    instrument_type     # String(20) — EQ, FUT, CE, PE
    product             # String(20) — MIS, NRML, MTF

    # Round
    direction           # String(10) — LONG, SHORT
    total_quantity      # Integer — peak position size (in units)
    num_entries         # Integer — count of entry fills (not unique IDs)
    num_exits           # Integer — count of exit fills (not unique IDs)

    # Prices
    avg_entry_price     # Numeric(15,4) — weighted average
    avg_exit_price      # Numeric(15,4) — weighted average

    # P&L
    realized_pnl        # Numeric(15,4) — total round P&L

    # Timing
    entry_time          # TIMESTAMP — first entry fill
    exit_time           # TIMESTAMP — last exit fill (position went flat)
    duration_minutes    # Integer

    # Direction flip metadata (Issue #6)
    closed_by_flip      # Boolean DEFAULT false — true when closing fill
                        # both closed this round AND opened reverse direction

    # Fill references (audit trail ONLY — not for counting)
    entry_trade_ids     # ARRAY(String)
    exit_trade_ids      # ARRAY(String)

    # Status
    status              # String(20) — 'closed' (immutable once created)

    created_at, updated_at
```

#### Step 2.2: CompletedTradeFeature Model (ML Features)
**New file:** `backend/app/models/completed_trade_feature.py`

```python
class CompletedTradeFeature(Base):
    __tablename__ = "completed_trade_features"

    id                          # UUID PK
    completed_trade_id          # FK → completed_trades (one-to-one, CASCADE)
    broker_account_id           # FK → broker_accounts

    # Timing features
    holding_duration_minutes    # Integer
    entry_hour_ist              # Integer (0-23)
    exit_hour_ist               # Integer (0-23)
    entry_day_of_week           # Integer (0=Mon)
    is_expiry_day               # Boolean

    # Sizing features
    size_relative_to_avg        # Numeric — qty / avg of recent 20 rounds
    is_scaled_entry             # Boolean — num_entries > 1
    is_scaled_exit              # Boolean — num_exits > 1

    # Context features
    entry_after_loss            # Boolean — previous round was a loss?
    consecutive_loss_count      # Integer — losses in a row before this
    session_pnl_at_entry        # Numeric — session realized P&L when round started
    minutes_since_last_round    # Integer — gap from prev round exit

    # Outcome features
    is_winner                   # Boolean
    pnl_per_unit                # Numeric — realized_pnl / total_quantity

    created_at
```

#### Step 2.3: IncompletePosition Model (Gap Detection)
**New file:** `backend/app/models/incomplete_position.py`

```python
class IncompletePosition(Base):
    __tablename__ = "incomplete_positions"

    id                  # UUID PK
    broker_account_id   # FK → broker_accounts

    tradingsymbol       # String(100)
    exchange            # String(20)
    product             # String(20)
    direction           # String(10) — LONG/SHORT
    unmatched_quantity  # Integer
    avg_entry_price     # Numeric(15,4)
    entry_time          # TIMESTAMP

    reason              # String(50) — SYNC_GAP, POSITION_MISMATCH
    detected_at         # TIMESTAMP
    details             # Text — human-readable

    resolution_status   # String(20) — PENDING, RESOLVED, IGNORED
    resolved_at         # TIMESTAMP (nullable)
    resolution_method   # String(50) — MANUAL_ENTRY, CSV_IMPORT, IGNORED

    created_at, updated_at
```

#### Step 2.4: BehavioralEvent Model (Signal Layer)
**New file:** `backend/app/models/behavioral_event.py`

```python
class BehavioralEvent(Base):
    __tablename__ = "behavioral_events"

    id                      # UUID PK
    broker_account_id       # FK → broker_accounts

    # Event classification
    event_type              # String(50) — REVENGE_TRADING, OVERTRADING,
                            #   TILT_SPIRAL, FOMO_ENTRY, LOSS_CHASING,
                            #   NO_STOPLOSS, EARLY_EXIT, etc.
    severity                # String(10) — LOW, MEDIUM, HIGH
    confidence              # Numeric(3,2) — 0.00 to 1.00
                            # HARD RULE: No insert below 0.70

    # Context
    trigger_trade_id        # FK → trades (nullable) — the fill that triggered
    trigger_position_key    # String — "NIFTY25000CE:NFO:NRML:LONG"
    message                 # String — human-readable explanation
    context                 # JSONB — structured detection context
                            #   e.g. {"consecutive_losses": 4, "session_pnl": -5200,
                            #         "time_since_last_loss_minutes": 3}

    # Timing
    detected_at             # TIMESTAMP — when the evaluator detected this

    # Delivery (Issue #10)
    delivery_status         # String(20) — PENDING, SENT, ACKNOWLEDGED
    acknowledged_at         # TIMESTAMP (nullable)

    created_at

    # TABLE IS APPEND-ONLY
    # No updates except delivery_status and acknowledged_at
```

**Constraints enforced in code (not DB):**
- `confidence < 0.70` → do NOT insert (Issue #9)
- Table is append-only: only `delivery_status` and `acknowledged_at` may be updated
- Severity must scale with confidence: HIGH requires confidence >= 0.85

#### Step 2.5: Register All Models
**File:** `backend/app/models/__init__.py`
Add imports for `CompletedTrade`, `CompletedTradeFeature`, `IncompletePosition`, `BehavioralEvent`.

#### Step 2.6: Migration SQL
**New file:** `backend/migrations/020_trade_architecture_overhaul.sql`

```sql
-- =============================================
-- LAYER 3: completed_trades (flat-to-flat rounds)
-- =============================================
CREATE TABLE IF NOT EXISTS completed_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id),
    tradingsymbol VARCHAR(100) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    instrument_type VARCHAR(20),
    product VARCHAR(20),
    direction VARCHAR(10),
    total_quantity INTEGER,
    num_entries INTEGER DEFAULT 1,
    num_exits INTEGER DEFAULT 1,
    avg_entry_price NUMERIC(15, 4),
    avg_exit_price NUMERIC(15, 4),
    realized_pnl NUMERIC(15, 4),
    entry_time TIMESTAMP WITH TIME ZONE,
    exit_time TIMESTAMP WITH TIME ZONE,
    duration_minutes INTEGER,
    closed_by_flip BOOLEAN DEFAULT false,
    entry_trade_ids TEXT[],
    exit_trade_ids TEXT[],
    status VARCHAR(20) DEFAULT 'closed',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ct_broker ON completed_trades(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_ct_exit_time ON completed_trades(exit_time DESC);
CREATE INDEX IF NOT EXISTS idx_ct_symbol ON completed_trades(tradingsymbol, exchange);
CREATE INDEX IF NOT EXISTS idx_ct_broker_exit ON completed_trades(broker_account_id, exit_time DESC);

-- =============================================
-- ML FEATURES: completed_trade_features
-- =============================================
CREATE TABLE IF NOT EXISTS completed_trade_features (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    completed_trade_id UUID NOT NULL REFERENCES completed_trades(id) ON DELETE CASCADE,
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id),
    holding_duration_minutes INTEGER,
    entry_hour_ist INTEGER,
    exit_hour_ist INTEGER,
    entry_day_of_week INTEGER,
    is_expiry_day BOOLEAN DEFAULT false,
    size_relative_to_avg NUMERIC(10, 4),
    is_scaled_entry BOOLEAN DEFAULT false,
    is_scaled_exit BOOLEAN DEFAULT false,
    entry_after_loss BOOLEAN DEFAULT false,
    consecutive_loss_count INTEGER DEFAULT 0,
    session_pnl_at_entry NUMERIC(15, 4) DEFAULT 0,
    minutes_since_last_round INTEGER,
    is_winner BOOLEAN DEFAULT false,
    pnl_per_unit NUMERIC(15, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ctf_one_per_trade
    ON completed_trade_features(completed_trade_id);
CREATE INDEX IF NOT EXISTS idx_ctf_broker
    ON completed_trade_features(broker_account_id);

-- =============================================
-- DATA INTEGRITY: incomplete_positions
-- =============================================
CREATE TABLE IF NOT EXISTS incomplete_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id),
    tradingsymbol VARCHAR(100) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    product VARCHAR(20),
    direction VARCHAR(10),
    unmatched_quantity INTEGER,
    avg_entry_price NUMERIC(15, 4),
    entry_time TIMESTAMP WITH TIME ZONE,
    reason VARCHAR(50) NOT NULL,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    details TEXT,
    resolution_status VARCHAR(20) DEFAULT 'PENDING',
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_method VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ip_broker ON incomplete_positions(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_ip_status ON incomplete_positions(resolution_status);

-- =============================================
-- SIGNAL LAYER: behavioral_events
-- =============================================
CREATE TABLE IF NOT EXISTS behavioral_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID NOT NULL REFERENCES broker_accounts(id),
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(10) NOT NULL,
    confidence NUMERIC(3, 2) NOT NULL CHECK (confidence >= 0.70),
    trigger_trade_id UUID REFERENCES trades(id),
    trigger_position_key VARCHAR(200),
    message TEXT NOT NULL,
    context JSONB,
    detected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    delivery_status VARCHAR(20) DEFAULT 'PENDING',
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_be_broker ON behavioral_events(broker_account_id);
CREATE INDEX IF NOT EXISTS idx_be_detected ON behavioral_events(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_be_type ON behavioral_events(event_type);
CREATE INDEX IF NOT EXISTS idx_be_delivery ON behavioral_events(delivery_status)
    WHERE delivery_status = 'PENDING';
CREATE INDEX IF NOT EXISTS idx_be_broker_type_recent
    ON behavioral_events(broker_account_id, event_type, detected_at DESC);

-- =============================================
-- CLEANUP: Remove duplicate trades from /orders push
-- =============================================
DELETE FROM trades WHERE fill_timestamp IS NULL AND status = 'COMPLETE';
```

---

### Phase 3: FIFO Matcher — Flat-to-Flat Rounds + Features ✅ COMPLETED

**File:** `backend/app/services/pnl_calculator.py`

**Hard constraint:** FIFO creates data (completed_trades, features, incomplete flags). It NEVER emits behavioral signals.

#### Step 3.1: Rewrite `_process_symbol_trades()` with Round Accumulator

```
ALGORITHM:

For each symbol's fills sorted by timestamp:
  Maintain: opening_queue[] (existing FIFO)
  Maintain: round_acc = {
    entry_fills: [],     # [{trade_id, qty, price, timestamp, trade_obj}, ...]
    exit_fills: [],      # [{trade_id, qty, price, timestamp, trade_obj}, ...]
    direction: None,     # LONG or SHORT
    total_pnl: Decimal(0)
  }

  For each fill:
    IF same side as queue head (or queue empty):
      → opening fill
      → add to opening_queue
      → add to round_acc.entry_fills
      → set direction if first fill (BUY=LONG, SELL=SHORT)

    ELSE (opposite side):
      → closing fill
      → match against opening_queue FIFO
      → accumulate P&L
      → add to round_acc.exit_fills
      → assign P&L to closing fill Trade.pnl (backward compat)

      IF opening_queue is now EMPTY:
        → position went flat
        → create CompletedTrade from round_acc
        → closed_by_flip = false
        → RESET round_acc

      IF closing fill has EXCESS qty after emptying queue:
        → direction flip happened
        → close current round with portion that zeroed (closed_by_flip = true)
        → start new round_acc with excess as first entry (flipped direction)

  After all fills processed:
    IF opening_queue NOT empty:
      → position still open — no CompletedTrade
      → check for incomplete positions (see Step 3.4)
```

#### Step 3.2: Fill Counting (Issue #7)

```python
# Count fills directly, not unique trade_ids
num_entries = len(round_acc["entry_fills"])  # count of fill entries
num_exits = len(round_acc["exit_fills"])     # count of fill entries
# entry_trade_ids and exit_trade_ids are for AUDIT TRAIL ONLY
```

#### Step 3.3: Idempotency — Timestamp-Bounded Deletion (Issue #5)

The existing `calculate_and_update_pnl()` has a `days_back` parameter (default 30). Use this to scope deletion:

```python
# Before processing, delete ONLY completed_trades within the recompute window
cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

await db.execute(
    delete(CompletedTrade).where(
        and_(
            CompletedTrade.broker_account_id == broker_account_id,
            CompletedTrade.exit_time >= cutoff  # Only within recompute window
        )
    )
)
# Features cascade-delete via ON DELETE CASCADE
```

**Hard rule:** Never delete historical data outside the recompute window.

Also clear IncompletePositions for symbols being reprocessed (they'll be re-detected if still applicable):

```python
symbols_being_processed = set(trades_by_symbol.keys())
for symbol_key in symbols_being_processed:
    sym, exch = symbol_key.split("_")
    await db.execute(
        delete(IncompletePosition).where(
            and_(
                IncompletePosition.broker_account_id == broker_account_id,
                IncompletePosition.tradingsymbol == sym,
                IncompletePosition.exchange == exch,
            )
        )
    )
```

#### Step 3.4: Incomplete Position Detection

Sync window always includes all trades since position opened
Or incomplete_positions catches every gap

After FIFO finishes for a symbol, if opening_queue is non-empty:

```python
if opening_queue and broker_account_id:
    # Check if Zerodha says this position is flat
    pos_result = await db.execute(
        select(Position).where(
            and_(
                Position.broker_account_id == broker_account_id,
                Position.tradingsymbol == symbol,
                Position.exchange == exchange,
                Position.total_quantity == 0,
            )
        )
    )
    closed_position = pos_result.scalar_one_or_none()

    if closed_position:
        # Gap: we have opening fills but broker says position is flat
        unmatched_qty = sum(o["remaining_qty"] for o in opening_queue)
        incomplete = IncompletePosition(
            broker_account_id=broker_account_id,
            tradingsymbol=symbol,
            exchange=exchange,
            product=opening_queue[0].get("product"),
            direction="LONG" if opening_queue[0]["side"] == "BUY" else "SHORT",
            unmatched_quantity=unmatched_qty,
            avg_entry_price=sum(o["price"]*o["remaining_qty"] for o in opening_queue)/unmatched_qty,
            entry_time=min(o["timestamp"] for o in opening_queue),
            reason="SYNC_GAP",
            details=f"Broker shows flat but {unmatched_qty} units of "
                    f"{'LONG' if opening_queue[0]['side']=='BUY' else 'SHORT'} "
                    f"fills are unmatched",
        )
        db.add(incomplete)
```

#### Step 3.5: Feature Computation (Post-FIFO, Separate Method)

After ALL symbols are processed by FIFO, a separate method computes features:

```python
async def _compute_features_for_new_rounds(
    self, broker_account_id, db, cutoff
):
    """
    Compute features for completed_trades that don't yet have features.
    Runs AFTER FIFO, reads completed_trades, writes completed_trade_features.
    Does NOT touch trades, positions, or P&L.
    """
    # Get completed trades without features
    rounds = await db.execute(
        select(CompletedTrade)
        .outerjoin(CompletedTradeFeature)
        .where(
            and_(
                CompletedTrade.broker_account_id == broker_account_id,
                CompletedTrade.exit_time >= cutoff,
                CompletedTradeFeature.id == None,  # no feature yet
            )
        )
        .order_by(CompletedTrade.exit_time.asc())
    )
    ...compute features using session helper, recent round history...
```

This keeps FIFO clean: it produces data. Feature computation is a separate, stateless pass.

---

### Phase 4: API Endpoints ✅ COMPLETED

#### Step 4.1: Pydantic Schemas
**File:** `backend/app/schemas/trade.py`

Add `CompletedTradeResponse` and `CompletedTradeListResponse`.

#### Step 4.2: GET /api/trades/completed
**File:** `backend/app/api/trades.py`

Add BEFORE `/{trade_id}` route. Paginated, ordered by exit_time DESC.

#### Step 4.3: GET /api/trades/incomplete
**File:** `backend/app/api/trades.py`

Returns pending incomplete positions for the user.

---

### Phase 5: Frontend Changes ✅ COMPLETED

#### Step 5.1: Add CompletedTrade Type
**File:** `src/types/api.ts`

```typescript
export interface CompletedTrade {
  id: string;
  tradingsymbol: string;
  exchange: string;
  instrument_type: string;
  product: string;
  direction: 'LONG' | 'SHORT';
  total_quantity: number;
  num_entries: number;
  num_exits: number;
  avg_entry_price: number;
  avg_exit_price: number;
  realized_pnl: number;
  entry_time: string;
  exit_time: string;
  duration_minutes: number;
  closed_by_flip: boolean;
  status: string;
}
```

#### Step 5.2: Update Dashboard
**File:** `src/pages/Dashboard.tsx`

- Fetch from `GET /api/trades/completed` instead of `GET /api/trades/`
- State type: `CompletedTrade[]`
- Trade stats: all completed trades have P&L — no `closingTrades` filter needed
- Map to Trade interface for `runAnalysis()`:
  `trade_type = direction === 'LONG' ? 'BUY' : 'SELL'`

#### Step 5.3: Redesign ClosedTradesTable
**File:** `src/components/dashboard/ClosedTradesTable.tsx`

Props: `CompletedTrade[]` (not `Trade[]`)

| Symbol | Direction | Qty | Entry | Exit | P&L | Duration |
|--------|-----------|-----|-------|------|-----|----------|
| NIFTY25000CE | LONG | 195 | 25.00 | 21.67 | -650 | 2d 6h |

- Direction badge: green LONG / red SHORT
- Entry + Exit columns instead of single Price
- Duration formatted as Xh Ym or Xd Yh
- No `isOpening` logic — all rows have P&L

---

### Phase 6: Behavioral Events Pipeline ✅ COMPLETED

Add one derived identifier to behavioral_events:
position_snapshot_id OR
position_key (instrument + product + direction + open_timestamp)

This lets you later answer:
“Which live position was this alert actually about?”

This phase replaces the current scattered behavioral detection with a clean, dedicated system.

#### Step 6.1: BehavioralEvaluator Service
**New file:** `backend/app/services/behavioral_evaluator.py`

```python
class BehavioralEvaluator:
    """
    Event-driven behavioral signal detector.

    Rules:
    - Runs AFTER a new trade fill is inserted (post-sync)
    - Input: single new fill (or batch of new fills)
    - Reads: positions, recent trades, recent behavioral_events
    - Emits: zero or more BehavioralEvents
    - MUST NOT mutate trades, positions, or P&L

    Confidence rules:
    - No event emitted below 0.70 confidence
    - HIGH severity requires confidence >= 0.85
    - MEDIUM severity requires confidence >= 0.75
    - LOW severity requires confidence >= 0.70
    """

    CONFIDENCE_THRESHOLDS = {
        "HIGH": 0.85,
        "MEDIUM": 0.75,
        "LOW": 0.70,
    }

    async def evaluate(
        self,
        broker_account_id: UUID,
        new_fills: List[Trade],
        db: AsyncSession
    ) -> List[BehavioralEvent]:
        """
        Evaluate new fills for behavioral signals.
        Returns events that passed confidence threshold.
        Events are NOT yet persisted — caller persists after validation.
        """
        events = []

        # Load context (read-only)
        open_positions = await self._get_open_positions(broker_account_id, db)
        recent_trades = await self._get_recent_trades(broker_account_id, db)
        recent_events = await self._get_recent_events(broker_account_id, db)

        # Run detectors
        events.extend(await self._detect_revenge_trading(new_fills, recent_trades, recent_events))
        events.extend(await self._detect_overtrading(new_fills, recent_trades, recent_events))
        events.extend(await self._detect_tilt_spiral(new_fills, recent_trades, recent_events))
        events.extend(await self._detect_fomo_entry(new_fills, recent_trades, open_positions))
        events.extend(await self._detect_loss_chasing(new_fills, recent_trades, recent_events))

        # Filter by confidence threshold
        validated = []
        for event in events:
            min_conf = self.CONFIDENCE_THRESHOLDS.get(event.severity, 0.70)
            if event.confidence >= min_conf:
                validated.append(event)

        return validated
```

Each detector method returns `BehavioralEvent` objects with appropriate confidence scores. Logic migrates from current `risk_detector.py` but with confidence scoring added.

#### Step 6.2: Wire Into Post-Sync Pipeline

BehavioralEvaluator must run:
On new fill insert
Not on full sync completion
Otherwise, bulk syncs could spam evaluations.

Wire BehavioralEvaluator to run per-fill after successful insert into trades

In `zerodha.py` `sync_all_data()`, after data pipeline completes:

```python
# DATA PIPELINE (deterministic)
trade_result = await TradeSyncService.sync_trades_for_broker_account(broker_account_id, db)
orders_result = await TradeSyncService.sync_orders_to_db(broker_account_id, db)

# SIGNAL PIPELINE (event-driven, after data is committed)
evaluator = BehavioralEvaluator()
new_fills = ...  # get fills from this sync cycle
events = await evaluator.evaluate(broker_account_id, new_fills, db)

# Persist events (only after confidence validation)
for event in events:
    db.add(event)

# Cooldown/rate-limit check before delivery
rate_limiter = NotificationRateLimiter()
for event in events:
    if rate_limiter.should_send(broker_account_id, event.event_type, event.severity):
        await push_to_websocket(broker_account_id, event)
        event.delivery_status = "SENT"

await db.commit()
```

#### Step 6.3: Alert Cooldown/Escalation State (Issue #4)

Extend existing `notification_rate_limiter.py` with per-(account, event_type) state:

- **Storage:** Redis preferred (already have Upstash), DB fallback via `behavioral_events` query
- **State per (account_id, event_type):**
  - `last_alert_time`
  - `alert_count_in_window`
  - `last_severity`
- **Rules:**
  - Minimum cooldown between same event_type (e.g., 15 min for WARNING)
  - Escalate severity only on repeated confirmations (3+ detections in 1 hour → escalate)
  - CRITICAL events bypass cooldown (loss limit breach)

#### Step 6.4: WebSocket Push (Issue #3)

Extend existing `ConnectionManager` in `websocket.py` to push behavioral events:

```python
# In ConnectionManager, add method:
async def push_behavioral_event(self, account_id: str, event: BehavioralEvent):
    """Push behavioral event to connected client. Only after DB persist."""
    ws = self.active_connections.get(account_id)
    if ws:
        await ws.send_json({
            "type": "behavioral_event",
            "data": {
                "event_type": event.event_type,
                "severity": event.severity,
                "message": event.message,
                "confidence": float(event.confidence),
                "detected_at": event.detected_at.isoformat(),
            }
        })
```

**Rule:** No push without DB insert. Event must be persisted before delivery.

---

## What Does NOT Change

| System | Why |
|--------|-----|
| **6 behavioral services** (risk_detector, behavioral_analysis, danger_zone, daily_reports, ai_personalization, pattern_prediction) | Continue working on Trade.pnl for fill-level analysis. Phase 6's BehavioralEvaluator will gradually replace `risk_detector` patterns, but the others remain as higher-level analysis services reading from the data pipeline. |
| **Orders table / sync_orders_to_db()** | Already correct. Orders sync to their own table. |
| **Instrument refresh / get_lot_size()** | Keep for future use. |
| **AlertContext / frontend pattern detector** | Works with mapped CompletedTrade fields. |
| **HoldingsCard / useHoldings** | Components stay, not called during sync. |

---

## Implementation Order & Dependencies

```
Phase 1 (all independent — fix bugs first):
  1.1 Remove order→trades push          [trade_sync_service.py]
  1.2 Add product filter                 [trade_sync_service.py]
  1.3 Remove qty sign override           [trade_sync_service.py]
  1.4 Remove lot_size from P&L           [pnl_calculator.py]
  1.5 Skip holdings sync                 [zerodha.py]
  1.6 Decouple risk detection from sync  [trade_sync_service.py, zerodha.py]
  1.7 Add session P&L helper             [market_hours.py]

Phase 2 (models + migration — independent of Phase 1):
  2.1 CompletedTrade model               [NEW: completed_trade.py]
  2.2 CompletedTradeFeature model        [NEW: completed_trade_feature.py]
  2.3 IncompletePosition model           [NEW: incomplete_position.py]
  2.4 BehavioralEvent model              [NEW: behavioral_event.py]
  2.5 Register all models                [__init__.py]
  2.6 Migration SQL                      [NEW: migrations/020_*.sql]

Phase 3 (depends on Phase 1.4 + Phase 2):
  3.1 FIFO with round accumulator        [pnl_calculator.py]
  3.2 Fill counting (not trade_id dedup) [pnl_calculator.py]
  3.3 Timestamp-bounded idempotency      [pnl_calculator.py]
  3.4 Incomplete position detection      [pnl_calculator.py]
  3.5 Feature computation (post-FIFO)    [pnl_calculator.py]

Phase 4 (depends on Phase 2):
  4.1 Pydantic schemas                   [schemas/trade.py]
  4.2 GET /completed endpoint            [api/trades.py]
  4.3 GET /incomplete endpoint           [api/trades.py]

Phase 5 (depends on Phase 4):
  5.1 CompletedTrade type                [types/api.ts]
  5.2 Dashboard update                   [Dashboard.tsx]
  5.3 ClosedTradesTable redesign         [ClosedTradesTable.tsx]

Phase 6 (depends on Phase 2.4 + Phase 1.6):
  6.1 BehavioralEvaluator service        [NEW: behavioral_evaluator.py]
  6.2 Wire into post-sync pipeline       [zerodha.py]
  6.3 Alert cooldown/escalation          [notification_rate_limiter.py]
  6.4 WebSocket push for events          [websocket.py]
```

---

## Verification Checklist ✅ ALL PASSED

**Data Pipeline (Phases 1-5):**
1. ✅ `npm run build` — frontend compiles (3334 modules, 0 errors)
2. ✅ Backend starts without import errors (103 files, 0 syntax errors)
3. ✅ No duplicate trades after sync (order→trades push removed, comment at line 366)
4. ✅ CNC/delivery filtered out (TRACKED_PRODUCTS at line 29, filters at lines 242 + 291)
5. ✅ Overnight positions retain correct sign (buy_qty/sell_qty override removed, comment at line 298)
6. ✅ FIFO P&L does NOT multiply by lot_size (no `* lot_size` or `* multiplier` in pnl_calculator.py)
7. ✅ CompletedTrades created with flat-to-flat semantics (round accumulator in _process_symbol_trades)
8. ✅ Direction flips captured (`closed_by_flip = true` when remaining_close_qty > 0)
9. ✅ num_entries/num_exits count fills directly (len(entry_fills), len(exit_fills))
10. ✅ Idempotent re-sync only deletes within recompute window (cutoff = now - days_back)
11. ✅ Features computed post-FIFO, not during (_compute_features_for_new_rounds after FIFO loop)
12. ✅ Incomplete positions detected for sync gaps (_detect_incomplete_position when opening_queue non-empty)
13. ✅ All 6 behavioral services still work (Trade.pnl field preserved, FIFO still updates it on closing fills)
14. ✅ Dashboard shows completed trades with direction, entry/exit, duration (ClosedTradesTable redesigned)
15. ✅ Session P&L consistent across all services (Trade.pnl + CompletedTrade.realized_pnl from same FIFO)

**Signal Pipeline (Phase 6):**
16. ✅ BehavioralEvaluator runs AFTER data pipeline, never mutates data (called after sync + P&L in zerodha.py)
17. ✅ Events below 0.70 confidence are NOT inserted (CONFIDENCE_THRESHOLDS filter in evaluate())
18. ✅ Severity scales with confidence (HIGH>=0.85, MEDIUM>=0.75, LOW>=0.70)
19. ✅ Events persisted BEFORE any delivery (db.commit at line 639, WebSocket push at line 645)
20. ✅ WebSocket push only after DB insert (push wrapped in separate try/except after commit)
21. ✅ Cooldown prevents repeated same-type alerts (60-min dedup window via _is_duplicate)
22. ✅ Behavioral detection is decoupled from FIFO/sync (no pnl_calculator/sync imports in evaluator)
23. ✅ Behavioral events are idempotent per (user, event_type, position_key, time_bucket)
24. ✅ Re-sync does NOT create new behavioral events (upsert_trade returns is_new flag, only new inserts tracked)

---

## Future Additions (V2)

| Feature | What | When |
|---------|------|------|
| `position_lots` | Persist FIFO lots for real-time lot queries | When we need "exited hedge first" detection |
| Incomplete position resolution UI | Frontend form + CSV upload | When users report missing data |
| `external_trade_imports` | CSV tradebook ingestion | When CSV upload is built |
| `daily_behavior_summary` | Daily aggregation cache | When on-the-fly becomes slow |
| True `trade_rounds` (multi-instrument) | Group hedges/straddles as single decision | V3 — after position_lots exists |
| Behavior timeline UI | Frontend view of behavioral_events | After Phase 6 is stable |
