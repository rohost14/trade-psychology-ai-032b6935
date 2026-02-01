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
- `src/contexts/AlertContext.tsx` - Global behavioral alert state with pattern detection
- `src/contexts/BrokerContext.tsx` - Broker connection state (Zerodha OAuth, sync, account management)
- `src/lib/patternDetector.ts` - Client-side behavioral pattern detection engine
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
- `/api/analytics/money-saved` - Estimated losses prevented
- `/api/webhooks/zerodha/postback` - Real-time order notifications from Zerodha
- `/api/behavioral/` - Behavioral analysis
- `/api/coach/` - AI trading coach

### Behavioral Pattern Detection

Patterns detected (defined in `src/types/patterns.ts`):
- `overtrading` - Too many trades in short time window
- `revenge_trading` - Quick re-entry after loss
- `loss_aversion` - Holding losers too long / cutting winners early
- `position_sizing` - Oversized positions relative to capital
- `fomo`, `no_stoploss`, `early_exit`, `winning_streak_overconfidence`

Detection runs client-side in `AlertContext` using trades from API. Patterns have severity levels (low/medium/high/critical) and estimated costs.

## Testing

Frontend tests use Vitest + React Testing Library:
```bash
npm run test                    # Run all tests
npm run test -- --watch         # Watch mode
npm run test -- src/path/file   # Run specific file
```

Test setup in `src/test/setup.ts` mocks `window.matchMedia` for component tests.

## Key Design Patterns

- Path alias: `@/` maps to `src/` (configured in vite.config.ts and vitest.config.ts)
- CSS variables for theming in `src/index.css` (supports dark mode via `next-themes`)
- Tailwind with custom risk colors (`risk-safe`, `risk-caution`, `risk-danger`)
- Local storage for persisting alerts and goals (`tradementor_*` keys)
