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

**Single engine: the backend `BehaviorEngine` is the ONLY detection engine** (`backend/app/services/behavior_engine.py` + the 27-detector `detector_registry.py`). It runs **per CompletedTrade** on the live postback pipeline and writes `RiskAlert` + `BehaviorEvent`. The old client-side `patternDetector.ts` and the legacy `behavioral_analysis_service` are both gone — `AlertContext` only fetches/refetches backend alerts (it does NOT detect). `src/types/patterns.ts` holds display types, not detection logic.

Detectors (23, declarative in `detector_registry.py`) include: `revenge_trade`, `adding_to_adverse_position`, `overtrading_burst`/`daily_overtrading`, `martingale_behaviour`, `session_meltdown`, `fomo_entry`, `no_stoploss`, `early_exit`, `winning_streak_overconfidence`, `constitution_violation`, `post_loss_recovery_bet`, and more. A detector may emit more than one `pattern_type`, so the registry also carries 6 alias names (`daily_overtrading`, `death_spiral`, `holding_loser`, `overexposure`, `portfolio_concentration`, `capital_mismatch`) — **23 detectors, 29 pattern types**, and `all_pattern_types()` is the authority for the second number. (Pattern 2 ADDED `adding_to_adverse_position`. Five retirements since: `consecutive_loss_streak` 2026-08-26 — trigger was chance, 63 sessions with a 3+ loss run against 63.0 expected, and the trader's own `max_consecutive_losses` rule under `constitution_violation` carries the behaviour; `profit_giveaway` 2026-08-27 — a drawdown from the session peak is arithmetic, shuffling trade order produced MORE firings than the real order; `expiry_day_overtrading` 2026-08-27 — it never withheld, firing on 55 of the 55 positions it could judge, and both its trader-facing statistics were unsourced and measured false; `size_escalation` 2026-08-27 — its claim was ordering, and the real trade order fired LESS than shuffled order (42 vs 49.7, p = 0.880); `direction_instability` 2026-08-28 — it could not separate an emotional reversal from a change of view, and trades inside its 10-minute window did BETTER (56.2% win) than the same transition outside it (41.7%). Level 1 stays untested — the book is 911 LONG vs 1 SHORT. See `docs/patterns/`.) Severity vocabulary = `info`/`caution`/`danger`/`critical`. Behaviour→money is **realized P&L of flagged trades** (factual, via `trigger_completed_trade_id`), never a counterfactual "estimated cost".

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
