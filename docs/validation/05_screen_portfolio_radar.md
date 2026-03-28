# Screen 05: Portfolio Radar
*Route: `/portfolio-radar` | File: `src/pages/PortfolioRadar.tsx`*

---

## Purpose
Real-time position intelligence beyond just open/closed P&L. Shows position-specific risk metrics (time-to-expiry, premium decay for options, breakeven gap), portfolio-level concentration analysis (underlying exposure, expiry clustering, directional skew), and GTT discipline tracking.

---

## Layout

```
┌────────────────────────────────────────────────────────┐
│  Header: "Portfolio Radar" + last updated time         │
├───────────────────────────┬────────────────────────────┤
│  Position Clock Cards     │  Concentration Panel       │
│  (per open position)      │  - Expiry distribution     │
│                           │  - Underlying exposure     │
│  [NIFTY 25200 CE]         │  - Directional skew        │
│  Entry: ₹180             │  - Margin utilization      │
│  LTP: ₹142  (-21%)       │  - Active concentration    │
│  DTE: 3 days              │    alerts                  │
│  Theta decay: -₹8/day    │                            │
│  Breakeven gap: ₹220     │                            │
│                           │                            │
│  [BANKNIFTY FUT]          │                            │
│  Entry: ₹48,200          │                            │
│  LTP: ₹48,450 (+0.5%)   │                            │
│  Unrealized: +₹2,500     │                            │
│                           │                            │
├───────────────────────────┴────────────────────────────┤
│  GTT Discipline Tracker                                │
│  Orders with GTT set vs no GTT (compliance %)         │
└────────────────────────────────────────────────────────┘
```

---

## Components

### Position Clock Cards
- **API**: `GET /api/portfolio-radar/metrics`
- **Service**: `position_metrics_service.py` — computes per-position:
  - `DTE` (days to expiry, from instrument expiry date)
  - `theta_decay_per_day` (options only, from Black-Scholes theta)
  - `breakeven_gap` (for options: distance from current price to breakeven)
  - `capital_at_risk` (qty × current loss per unit)
  - `premium_decay_pct` (options: how much premium has decayed since entry)
- **LTP source**: Redis LTP cache (KiteTicker → Redis 2s TTL)
- **Validation**: ✅ Options metrics calculated, equity/futures show simplified view

### Portfolio Concentration Panel
- **API**: `GET /api/portfolio-radar/concentration`
- **Service**: `portfolio_concentration_service.py` — computes:
  - Expiry distribution (% of portfolio expiring this week / next week / month)
  - Underlying exposure (NIFTY: 45%, BANKNIFTY: 30%, etc.)
  - Directional skew (% long vs short by delta)
  - Margin utilization (from latest `MarginSnapshot`)
  - Active concentration alerts (if single underlying > 60% of portfolio)
- **Validation**: ✅ Alerts fire via event-driven position monitor (not beat task)

### GTT Discipline Tracker
- **API**: `GET /api/portfolio-radar/gtt-discipline`
- **Service**: `gtt_service.py`
- **Content**:
  - Positions with GTT set: ✅
  - Positions without GTT: ⚠️
  - GTT compliance % (last 30 days)
  - "Sync GTTs" button → `POST /api/portfolio-radar/sync-gtts`
- **GTT data**: Seeded once on login, updated via webhooks (no polling)
- **Validation**: ✅ GTT state is event-driven, not polled

---

## APIs Called

| Endpoint | When | Purpose |
|----------|------|---------|
| `GET /api/portfolio-radar/metrics` | Mount + `lastTradeEvent` | Position clock data |
| `GET /api/portfolio-radar/concentration` | Mount + `lastTradeEvent` | Concentration panel |
| `GET /api/portfolio-radar/gtt-discipline` | Mount | GTT tracking |
| `POST /api/portfolio-radar/sync-gtts` | Sync button | Pull latest GTTs from Kite |

---

## Backend: Position Monitor Tasks

The position monitor (`backend/app/tasks/position_monitor_tasks.py`) runs per-fill, not on a beat:

```
Trade fill arrives via webhook
  → process_webhook_trade (Celery)
    → After FIFO + behavioral detection:
      → check_position_overexposure (immediate)  — fires if position > limit
      → check_holding_loser_scheduled (T+30min chain, max 8 checks = 4hr window)
        → each check: holding_loser pattern? → _fire_position_alert()
```

Redis chain key `holding_loser_chain:{account_id}` (TTL=1900s) prevents multiple parallel chains from the same account's BUY fills.

`_fire_position_alert()` creates `RiskAlert` in DB → publishes `alert_update` event → WhatsApp for danger severity.

**Validation**: ✅ No beat task, no polling, dedup via Redis SETNX

---

## Validation Checklist

- [x] DTE shows correct days (fetched from instrument expiry, not hardcoded)
- [x] Options metrics only shown for CE/PE positions, not futures/equity
- [x] Concentration alert fires if single underlying exceeds 60% of portfolio
- [x] GTT sync pulls from Kite API, not from local DB only
- [x] Position clock cards update when new fills arrive (WebSocket trade_update)
- [x] No beat task polling (confirmed removed from celery_app.py beat schedule)
- [x] Position holding_loser check chain deduped — one chain per account, not per fill
