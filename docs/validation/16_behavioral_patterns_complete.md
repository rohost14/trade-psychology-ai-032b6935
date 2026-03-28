# Behavioral Patterns — Complete Reference
*All patterns, where they run, what they detect, and what's missing*

---

## Summary: 23 Unique Patterns Today

| Layer | File | Count | When runs |
|-------|------|-------|-----------|
| Backend BehaviorEngine | `behavior_engine.py` | **15** | Real-time, per CompletedTrade (via webhook pipeline) |
| Frontend patternDetector | `patternDetector.ts` | **8** | Instant, in-browser on every WebSocket trade event |
| Legacy BehavioralAnalysisService | `behavioral_analysis_service.py` | ~15 | Batch only — `/api/behavioral/patterns` endpoint |

**Total actively detected unique patterns: 23**
(15 backend + 8 frontend, some semantic overlap = 23 distinct behaviours)

All 4 previously unimplemented patterns are now live in BehaviorEngine:
`fomo_entry`, `no_stoploss`, `early_exit`, `winning_streak_overconfidence`

---

## Layer 1: Backend BehaviorEngine (Real-Time, Per Trade)

Runs inside `trade_tasks.py` after every FIFO-closed position.
Creates `RiskAlert` in DB → publishes `alert_update` event → browser notified instantly.
**Strategy-aware**: alerts suppressed for hedge/multi-leg strategy legs.

| # | Pattern | Severity | What it checks | Threshold source |
|---|---------|----------|---------------|-----------------|
| 1 | `consecutive_loss_streak` | caution/danger | N consecutive losing trades today | UserProfile: caution=3, danger=5 |
| 2 | `revenge_trade` | caution/danger | Entry within N min after a loss | Profile: revenge_window_min=10; <3min = danger |
| 3 | `overtrading_burst` | caution/danger | N+ trades in 30-min window | Profile: burst_trades_per_15min × 2 |
| 4 | `size_escalation` | caution | Position size increasing 50%+ after losses (3-trade sequence) | Hardcoded: 50% escalation |
| 5 | `rapid_reentry` | caution | Re-enter same symbol within 3 min | Hardcoded: 3 min |
| 6 | `panic_exit` | caution | Position closed <2 min at a loss | Hardcoded: 2 min hold |
| 7 | `martingale_behaviour` | danger | Doubling size (1.8x) on consecutive losses | Hardcoded: 1.8x |
| 8 | `cooldown_violation` | danger | New trade while active cooldown exists | DB: Cooldown.expires_at |
| 9 | `rapid_flip` | caution | Reversed direction (LONG→SHORT) in <5 min on same symbol | Hardcoded: 5 min |
| 10 | `excess_exposure` | caution/danger | Position capital-at-risk > profile limit | Profile: max_position_size % |
| 11 | `session_meltdown` | caution/danger | Session P&L > 80% of daily loss limit | Profile: daily_loss_limit |
| 12 | `fomo_entry` | caution | 2+ different instruments entered in first 15 min of market open (9:15–9:30 IST) | Hardcoded |
| 13 | `no_stoploss` | caution/danger | Option held >30 min at ≥30% premium loss (danger at ≥60%) | Hardcoded |
| 14 | `early_exit` | caution | Session pattern: winners held <50% the time of losers (requires ≥2 of each) | Hardcoded |
| 15 | `winning_streak_overconfidence` | caution | 3 consecutive wins + next trade size ≥1.5× avg win-streak size | Hardcoded |

**Risk scoring**: Each pattern adds delta to session risk score (0–100).
States: Stable → Pressure (20) → Tilt Risk (40) → Tilt (60) → Breakdown (80) → Recovery

**Strategy suppression**: `revenge_trade`, `martingale_behaviour`, `size_escalation`, and
`consecutive_loss_streak` are automatically suppressed when a trade belongs to a detected
multi-leg strategy (straddle/strangle/spread/iron condor/futures hedge).

---

## Layer 2: Frontend patternDetector.ts (Instant, In-Browser)

Runs in `AlertContext` on every `lastTradeEvent`. Session-scoped to today IST.
**Ephemeral** — not persisted. Immediate feedback before backend processes.

| # | Pattern | What it checks |
|---|---------|---------------|
| 1 | `overtrading` | 8+ trades in 30 min (CompletedTrade data) |
| 2 | `revenge_trading` | Entry within 10 min after loss > ₹500 |
| 3 | `loss_aversion` | Avg loss 1.5x+ larger than avg win (holding losers too long) |
| 4 | `position_sizing` | Position capital-at-risk > 10% of configured capital |
| 5 | `consecutive_losses` | 3+ consecutive losing CompletedTrades today |
| 6 | `capital_drawdown` | Session loss > 10% of configured capital |
| 7 | `same_instrument_chasing` | 2+ losses on same symbol in last 3 hours |
| 8 | `all_loss_session` | 3+ exits today, zero winners |

**P&L accuracy**: Frontend uses `CompletedTrade.realized_pnl` via `CompletedTradeAdapter`.
`Trade.pnl` is always 0 — frontend patterns were broken before Session 9 fix.

---

## Layer 3: Legacy BehavioralAnalysisService (Batch)

`behavioral_analysis_service.py` — ~15 patterns, runs on-demand or in reports.
These are NOT real-time. Called from `/api/behavioral/patterns` endpoint.

Patterns include: revenge_trading, emotional_exit, no_cooldown, loss_chasing, tilt_spiral, overtrading, etc.
Uses `CompletedTradeAdapter` (correct P&L). Returns structured results for Analytics tab.

**Status**: Kept for batch analytics. Will eventually be unified with BehaviorEngine.

---

## Live Alerts Tab — Design Recommendation

Currently alerts are scattered across 3 places:
- Dashboard: RecentAlertsCard (last 8, 48h window)
- Header bell: AlertHistorySheet (last 30)
- My Patterns: full alert history

**Recommendation**: Add `/alerts` route with a dedicated Alerts screen:

```
┌────────────────────────────────────────────────────────┐
│  Live Feed tab | History tab | Analytics tab           │
├────────────────────────────────────────────────────────┤
│  [Live Feed]                                           │
│  Real-time alert stream (WebSocket)                   │
│  Each alert: severity badge | pattern | message | time │
│  Acknowledge button per alert                          │
│  "All caught up" when empty                           │
├────────────────────────────────────────────────────────┤
│  [History]                                             │
│  Full paginated alert history                          │
│  Filter: severity | pattern | date range              │
│  Bulk acknowledge                                      │
├────────────────────────────────────────────────────────┤
│  [Analytics]                                           │
│  Most frequent patterns (bar chart)                   │
│  Pattern trend over 30/90 days                        │
│  "Best day" / "Worst pattern" stats                   │
│  Journal correlation: "Alerts when FOMO selected"     │
└────────────────────────────────────────────────────────┘
```

This consolidates everything and gives the alert feature the prominence it deserves.
The journal `followed_plan` + `deviation_reason` fields now enable the correlation analytics.
