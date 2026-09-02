# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TradeMentor AI is a trading psychology and behavioral analysis platform that helps traders identify harmful patterns in their trading behavior. It integrates with Zerodha broker to fetch real-time trades and provides behavioral alerts, analytics, and AI coaching.

**Philosophy**: "Mirror, not blocker" - show traders facts about their behavior, not restrictions.

## Development Commands

### Frontend (React + Vite)
```bash
npm install          # Install dependencies
npm run dev          # Start dev server on port 8080
npm run build        # Production build
npm run lint         # ESLint check
npm run test         # Run tests once
npm run test:watch   # Run tests in watch mode
```

### Backend (FastAPI + Python)
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Environment Setup
- Frontend: Set `VITE_API_URL` for backend URL (defaults to `http://localhost:8000`)
- Backend: Copy `backend/.env.example` to `backend/.env` and configure:
  - `DATABASE_URL` - PostgreSQL connection (uses Supabase)
  - `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY`
  - `ZERODHA_API_KEY` / `ZERODHA_API_SECRET` for broker integration
  - `OPENROUTER_API_KEY` for AI features

## Architecture

### Frontend (`src/`)
- **React 18 + TypeScript + Vite** with SWC for fast compilation
- **shadcn/ui** components in `src/components/ui/` (Radix primitives + Tailwind)
- **React Query** for server state management
- **react-router-dom** for routing with Layout wrapper
- **recharts** for analytics visualizations
- **framer-motion** for animations

Key directories:
- `src/pages/` - Route pages (Dashboard, Analytics, Goals, Chat, Settings)
- `src/components/dashboard/` - Dashboard-specific components (positions tables, alerts, risk guardian)
- `src/components/analytics/` - Analytics charts and cards
- `src/components/goals/` - Goal commitment and streak tracking
- `src/contexts/AlertContext.tsx` - Global behavioral alert state (backend-driven, WebSocket-triggered)
- `src/contexts/BrokerContext.tsx` - Broker connection state (Zerodha OAuth, sync, account management)
- `src/types/` - TypeScript interfaces (`api.ts` for API types, `patterns.ts` for behavioral types)

### Backend (`backend/app/`)
- **FastAPI** with async SQLAlchemy + asyncpg
- **Supabase** as PostgreSQL database

API structure:
- `api/` - Route handlers (zerodha, trades, positions, alerts, analytics, coach, behavioral, webhooks)
- `services/` - Business logic (zerodha_service, ai_service, behavioral_analysis_service, risk_detector)
- `models/` - SQLAlchemy models (trade, position, broker_account, risk_alert)
- `schemas/` - Pydantic schemas for request/response validation
- `core/config.py` - Settings via pydantic-settings

Key endpoints:
- `/api/zerodha/connect` - Generate Zerodha OAuth login URL
- `/api/zerodha/callback` - Handle OAuth callback, redirect to frontend with broker_account_id
- `/api/zerodha/accounts` - List all connected broker accounts
- `/api/zerodha/disconnect` - Revoke token and disconnect
- `/api/trades/` - CRUD for trades
- `/api/trades/sync` - Sync trades from Zerodha
- `/api/positions/` - Position tracking
- `/api/risk/state` - Current risk state (safe/caution/danger)
- `/api/risk/alerts` - Risk alerts with acknowledge endpoint
- `/api/analytics/behaviour-cost` - Realized P&L of behaviourally-flagged trades (RAW; factual, not "estimated" — replaced the old money-saved endpoint)
- `/api/webhooks/zerodha/postback` - Real-time order notifications from Zerodha
- `/api/behavioral/` - Behavioural summary served from the live engine's RiskAlerts (the legacy dual engine was retired 2026-07)
- `/api/my-record/` - Pre-trade personal-record lookup (replaced Blowup Shield)
- `/api/coach/` - AI trading coach

### Behavioral Pattern Detection

**Single engine: the backend `BehaviorEngine` is the ONLY detection engine** (`backend/app/services/behavior_engine.py` + the 17-detector `detector_registry.py`). It runs **per CompletedTrade** on the live postback pipeline and writes `RiskAlert` + `BehaviorEvent`. The old client-side `patternDetector.ts` and the legacy `behavioral_analysis_service` are both gone — `AlertContext` only fetches/refetches backend alerts (it does NOT detect). `src/types/patterns.ts` holds display types, not detection logic.

Detectors (15, declarative in `detector_registry.py`) include: `revenge_trade`, `adding_to_adverse_position`, `overtrading_burst`/`daily_overtrading`, `martingale_behaviour`, `session_meltdown`, `fomo_entry`, `no_stoploss`, `constitution_violation`, `post_loss_recovery_bet`, and more. A detector may emit more than one `pattern_type`, so the registry also carries 4 alias names (`daily_overtrading`, `holding_loser`, `overexposure`, `capital_mismatch`) — **15 detectors, 19 pattern types**, and `all_pattern_types()` is the authority for the second number. (Pattern 2 ADDED `adding_to_adverse_position`. Fifteen retirements since, each with a retirement suite under `backend/tests/test_*_retired.py` and evidence under `docs/patterns/`: `consecutive_loss_streak` 2026-08-26 — trigger was chance, 63 sessions with a 3+ loss run against 63.0 expected, and the trader's own `max_consecutive_losses` rule under `constitution_violation` carries the behaviour; `profit_giveaway` 2026-08-27 — a drawdown from the session peak is arithmetic, shuffling trade order produced MORE firings than the real order; `expiry_day_overtrading` 2026-08-27 — it never withheld, firing on 55 of the 55 positions it could judge, and both its trader-facing statistics were unsourced and measured false; `size_escalation` 2026-08-27 — its claim was ordering, and the real trade order fired LESS than shuffled order (42 vs 49.7, p = 0.880); `direction_instability` 2026-08-28 — it could not separate an emotional reversal from a change of view, and trades inside its 10-minute window did BETTER (56.2% win) than the same transition outside it (41.7%); `panic_exit` 2026-08-29 — its subject did not exist, short holds performed the same as long ones; `cooldown_violation` 2026-08-29 — its precondition never occurred on the live path (`Cooldown` rows are written only by `danger_zone_service.trigger_intervention`, which no Celery task calls), 0 firings against `constitution_violation`'s 181 for the same behaviour; `early_exit` 2026-08-30 — the disposition effect is the right measure but a single session gives 3–5 trades per side, shuffle null p = 0.610, and `baseline_service`'s history-scope `avg_winner_hold_min`/`avg_loser_hold_min` survive in its place; `winning_streak_overconfidence` 2026-08-30 — the concept is real literature but the conditioning variable had the wrong sign: sizing up was LESS likely after a 3+ win run (21.4% vs 30.4%), monotone across run lengths, rho = -0.076, and this trader sizes up after LOSSES instead, which `martingale_behaviour` covers; shuffle null p = 0.582 and the danger tier never fired in 175 sessions; `options_premium_avg_down` 2026-08-30 — it was never an average-down, 0 of 44 firings involved an open position because its "prior losers" were CLOSED rounds on the same UNDERLYING, and its copy described `adding_to_adverse_position`, which already covers option premium averaging on 100% of its 64 firings; `opening_5min_trap` 2026-08-30 — the opening window was not a worse place to trade (39.4% win inside 09:15-09:25 against 39.5% for the rest of the day, and BETTER on money, p = 0.274), and it reached its finding by discarding 42% of window entries for having made money — selection on outcome, the shape that retired `panic_exit`; `time_of_day_bias` 2026-09-01 — the learned "danger hours" it alerted on do not survive into a second time period: full book [12, 15], first half [11, 12, 15], SECOND HALF none at all, not one hour flagged in both, five different hours across four quarters. Chance reproduces 2+ flagged hours 31% of the time and the real book flags 2. The descriptive fallback fails too — the two halves' hourly win-rate ranks correlate at Spearman rho = +0.071. Separating a 30% hour from a 40% baseline needs n ≈ 100 in that hour; the producer's gate is n ≥ 5, where the interval is ±43pp. All four lists were measured separately: `danger_hours` contradicted, `best_hours` unstable (one hour, second half only), `danger_days` flat (36.0–42.6% across weekdays against a 39.5% book rate), `best_days` UNVALIDATED not invalidated (zero firings at every slice). INSUFFICIENT EVIDENCE, NOT PROOF THAT TIME-OF-DAY EFFECTS DO NOT EXIST — the nightly learning and storage are deliberately KEPT; only the trader-facing interpretation is gone. A correction is part of the record: the first review called it mis-wired with no writer for `detected_patterns["time_patterns"]`, which was WRONG — it is written on a nightly 18:15 IST beat, so the detector was LIVE for any trader with 30+ sessions. `excess_exposure` 2026-09-01 — no universal exposure threshold survives and none replaced its 5/10: a trader who DECLARED 40% was told DANGER at 35%, inside their own rule, because `safety_bounds` clamps a declared value so it may only tighten, and the alert could not tell 35% from 45%. Outcome evidence never supported it either (per round 0-5% won 40.2%, 5-10% 37.4%, 10-15% 43.1%, 15-25% 43.9% — no trend; only 25%+ separated, at n=10 with 81% of that bucket from ONE position). Single-position exposure is now solely a breach of the trader's own declared limit via `constitution_violation`'s `max_trade_risk`, which already used `capital_requirement/trading_capital`; the entry-time arm emits that same pattern type and rule so `_pattern_dedup_key` collapses entry and exit. At ₹1L the removal drops 520 alerts on 724 rounds that a trader declaring NOTHING used to receive; `portfolio_concentration` 2026-09-01 — it measured how FEW positions were open: with n positions the top underlying's share is at least 1/n, so a two-position book had a 50% floor against a 40% cut and fired 206 of 206, 69% of all firings, the rate falling monotonically as the book diversified; `death_spiral` 2026-09-02 — the L2 meta-detector was a summary of alerts the trader had already been sent, not a state: without rules it fired 10/203 and was SET-IDENTICAL to "a danger emotional + a danger risk alert today", a strict subset of the simpler "2 danger detectors" rule whose four excluded sessions include the 4th-worst day in the book; with one declared rule it fired on 38.9% of sessions with `constitution_violation` present in 100% and 61% deriving both "independent" domains from two detectors reading the SAME `daily_loss_limit`; 69% followed an already-delivered danger alert and only 15% were incremental. Its absorption branch was DEAD CODE — 0 `absorbed:` rows ever, matched against engine-produced events while the composite was written later by `trade_tasks`. Replay 87 → 0, every other detector identical, P&L byte-identical; historical rows KEPT and marked Retired in the UI. **Also 2026-09-01: `sl_percent_options`/`sl_percent_futures` no longer invent 50.0/1.0 as `Source.FACT` — an undeclared rule resolves to None, so a trader who set nothing is no longer told "You set your options exit at 50% of premium" in a notification_level-4 constitution_violation, and the fabricated band no longer pre-empts the universal 40/60/80 severe-loss ladder, which is UNCHANGED and independent of any exposure rule.** Level 1 stays untested — the book is 911 LONG vs 1 SHORT.) **Retired names leave `PATTERN_COPY` and `BACKEND_TO_FRONTEND_TYPE` but STAY in `formatPatternName` so stored rows still render, and must not appear as a `pattern_type` in `src/lib/demoData.ts` — guest fixtures double as smoke fixtures and a contract test enforces it.** Severity vocabulary = `info`/`caution`/`danger`/`critical`. Behaviour→money is **realized P&L of flagged trades** (factual, via `trigger_completed_trade_id`), never a counterfactual "estimated cost".

## Testing

Frontend tests use Vitest + React Testing Library:
```bash
npm run test                    # Run all tests
npm run test -- --watch         # Watch mode
npm run test -- src/path/file   # Run specific file
```

Test setup in `src/test/setup.ts` mocks `window.matchMedia` for component tests.

## UI / Design

**Before changing anything visual, read `docs/DESIGN_SYSTEM.md`.** It is authoritative and self-contained — colour tokens, the 7-step type scale, spacing, container rules, interaction states, charts, copy voice, and a per-screen specification for all 26 routes. If a value isn't there, add it there first.

- `docs/DESIGN_SYSTEM.md` — the design system + screen specification. Permanent. The target, even where the code is behind it.
- `docs/DESIGN_MIGRATION.md` — where the code stands against it: current debt, deprecations, Track A (visual, in scope) vs Track B (deferred feature/logic changes), status. **Disposable — delete when its status table is green.**

Two rules that catch most mistakes: containers are the exception, not the default (sections + dividers + edge-to-edge tables); and a failed request is never rendered as an empty state.

## Key Design Patterns

- Path alias: `@/` maps to `src/` (configured in vite.config.ts and vitest.config.ts)
- CSS variables for theming in `src/index.css` (supports dark mode via `next-themes`)
- Tailwind with custom risk colors (`risk-safe`, `risk-caution`, `risk-danger`)
- Local storage for persisting alerts and goals (`tradementor_*` keys)
