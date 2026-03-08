# Chat (AI Coach) Screen Review

**Status:** 4/4 FIXED
**Session:** 7 (2026-02-24)

---

## Issues Found

| ID | Severity | Description | Status |
|----|----------|-------------|--------|
| C1 | HIGH | `/insight` endpoint hardcodes `patterns_active=[]` — never passes real patterns | FIXED |
| C2 | HIGH | No UserProfile context sent to AI — no persona, experience, weaknesses | FIXED |
| C3 | MEDIUM | Chat context too thin — missing patterns, consecutive losses, symbol performance | FIXED |
| C4 | LOW | Fallback responses don't log that AI is offline | FIXED |

---

## Fixes Applied

### C1: Pass real patterns to /insight
**File:** `backend/app/api/coach.py`
- Added RiskAlert query (same pattern already used in `/chat`) to fetch today's alerts
- Changed `patterns_active=[]` to `patterns_active=patterns_active` (actual detected patterns)

### C2: User profile context in AI
**Files:** `backend/app/api/coach.py`, `backend/app/services/ai_service.py`
- `/insight`: Fetches UserProfile, builds context string with experience/style/risk tolerance/weaknesses
- `/chat`: Fetches UserProfile, appends Trader Profile section to trading_context, passes `ai_persona` to AI service
- `ai_service.generate_chat_response()`: New `ai_persona` parameter. System prompt personality adapts per persona (coach/mentor/friend/strict)
- `ai_service.generate_coach_insight()`: New `user_profile_context` parameter, included in user prompt

### C3: Enriched chat context
**File:** `backend/app/api/coach.py` — `/chat` endpoint
- Added active behavioral patterns to context
- Added consecutive loss count (when >= 2)
- Added weekly symbol performance (best/worst symbols with P&L)

### C4: Fallback transparency logging
**File:** `backend/app/services/ai_service.py`
- Added `logger.warning("AI_FALLBACK: ...")` to `_fallback_insight`, `_fallback_chat_response`, `_fallback_persona`
- Added startup log with `api_key_configured` status
- No user-facing changes — only backend logging

---

## What's Still True
- AI is real (Claude Haiku via OpenRouter) when `OPENROUTER_API_KEY` is set
- Fallback is rule-based templates — works but generic
- RAG context (journal entries, knowledge base) is passed when available
- Chat history limited to last 10 messages
