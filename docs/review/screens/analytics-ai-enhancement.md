# Analytics AI Enhancement Plan

**Status:** COMPLETE — All phases implemented (Session 4)
**Prerequisite:** Analytics Phase 1+2 complete (4 tabs, 5 endpoints, 21 enhancements)

---

## Problem Statement

Deep audit revealed the analytics page has **ZERO generative AI**. All endpoints are pure SQL aggregation. The existing AI infrastructure (OpenRouter, RAG, knowledge base) is completely unused on the analytics page.

### Current State
- **Patterns: 25 unique** across 3 layers (need ~35 for professional-grade)
- **AI calls on analytics: 0** (only `generate_trading_persona()` via behavioral analysis)
- **No AI narratives** — users see charts but no interpreted insights
- **No predictive warnings** — PatternPredictionService exists but isn't surfaced
- **No caching** — AI persona regenerated every page load (~$0.08/call)

### Existing AI Infrastructure (available but unused)
- OpenRouter API: Claude Haiku ($0.001/call), GPT-4o Mini ($0.08/call)
- RAG service: pgvector embeddings + knowledge base
- `generate_trading_persona()` — LLM-powered psychological profiles
- `generate_coach_insight()` — contextual 1-liner coaching
- `generate_chat_response()` — conversational AI + RAG
- `PatternPredictionService` — real-time probability engine (5 patterns)

---

## Phase A: Add 10 New Behavioral Patterns (25 → 35)

**File:** `backend/app/services/behavioral_analysis_service.py`

| # | Pattern | Category | Severity | Detection Logic |
|---|---------|----------|----------|----------------|
| A1 | Disposition Effect | fear | HIGH | avg_hold_time(winners) < 0.5× avg_hold_time(losers) |
| A2 | Breakeven Obsession | fear | MEDIUM | ≥3 trades closed within ±0.5% of entry |
| A3 | Adding to Losers | impulse | CRITICAL | Same symbol, additional entry while position is losing |
| A4 | Profit Give-Back | discipline | HIGH | Session peak P&L → end ≤30% of peak, in ≥2 sessions |
| A5 | End-of-Day Rush | impulse | MEDIUM | ≥30% of trades in last 30 min (after 3PM IST) |
| A6 | Expiry Day Gambling | impulse | HIGH | Trade count or size ≥1.5× normal on expiry days |
| A7 | Boredom Trading | compulsion | MEDIUM | Small-size, short-duration, near-zero P&L clusters |
| A8 | Concentration Risk | discipline | MEDIUM | >60% of trades in single instrument |
| A9 | Max Daily Loss Breach | discipline | CRITICAL | Any day loss exceeds 2× average daily loss |
| A10 | Gambler's Fallacy | impulse | HIGH | Same direction 3+ times after consecutive same-direction losses |

Each: ~60-80 lines, class + detect() method + recommendation text.

**Data sources:**
- A1: CompletedTrade.duration_minutes
- A3: Sequential entries on same tradingsymbol
- A5: CompletedTradeFeature.entry_hour_ist (≥15 = after 3PM)
- A6: CompletedTradeFeature.is_expiry_day
- A7: CompletedTrade.duration_minutes + realized_pnl + total_quantity

---

## Phase B: AI-Generated Analytics Narratives (Hybrid: LLM + Rule-based)

### B1. New endpoint: `GET /api/analytics/ai-summary`

**File:** `backend/app/api/analytics.py`

```
Params: tab (overview|behavior|performance|risk), days (int)
Returns: {
  "narrative": "Your trading this month...",
  "key_insight": "Most impactful: ...",
  "action_item": "Consider...",
  "source": "ai" | "rule_based",
  "cached": true/false,
  "generated_at": "2026-02-07T..."
}
```

**Hybrid logic:**
1. Check cache: `UserProfile.ai_cache` JSONB → key = `{tab}_{days}`
2. If cached within 24 hours, return cached
3. If OPENROUTER_API_KEY configured → call LLM (Claude Haiku, ~$0.002)
4. If no API key or API fails → use rule-based template engine
5. Cache result, return

### B2. New AI function: `generate_analytics_narrative()`

**File:** `backend/app/services/ai_service.py`

- **LLM path:** Claude Haiku with structured prompt per tab
- **Rule-based path:** Template with conditional logic:
  ```
  "Your win rate of {X}% is {above/below} the 50% threshold.
  Your most costly pattern is {pattern} at ₹{Y}.
  {if expectancy > 0: 'Your positive expectancy suggests...'}
  {if behavior_score < 50: 'Focus on reducing...'}"
  ```
- Both return same response structure

### B3. Surface pattern predictions on analytics

**File:** `backend/app/api/analytics.py` (enhance `/ai-insights`)

Add `predictions` from PatternPredictionService to response:
```python
"predictions": {
  "revenge_trading": {"probability": 45, "severity": "high"},
  "tilt_loss_spiral": {"probability": 20, "severity": "critical"},
  ...
}
```

### B4. Frontend: `AINarrativeCard` component

**File:** `src/components/analytics/AINarrativeCard.tsx` (new)

- Async-loads from `/api/analytics/ai-summary?tab=X&days=Y`
- Skeleton while loading, graceful on failure
- Shows: narrative + key insight + action item
- Badge: "AI" or "Rule-based" indicator
- Optional "Regenerate" button

### B5. Frontend: Predictive Warnings in BehaviorTab

**File:** `src/components/analytics/BehaviorTab.tsx`

New section: probability bars for 5 predicted patterns
- Color: green (<30%), amber (30-60%), red (>60%)
- From `/api/analytics/ai-insights` response

---

## Phase C: Production Hardening

| # | Fix | File |
|---|-----|------|
| C1 | Cache AI persona in UserProfile (24hr) | `behavioral_analysis_service.py` |
| C2 | Add `ai_cache` JSONB to UserProfile | `user_profile.py` + migration |
| C3 | Token/cost logging per AI call | `ai_service.py` |
| C4 | Graceful degradation — analytics works without AI | all endpoints |

---

## Implementation Order

| Step | What | Depends On |
|------|------|-----------|
| 1 | Add 10 new patterns (A1-A10) | — |
| 2 | Add `ai_cache` to UserProfile + migration | — |
| 3 | Add `generate_analytics_narrative()` (hybrid) | — |
| 4 | Add `/api/analytics/ai-summary` endpoint | 2, 3 |
| 5 | Enhance `/ai-insights` with predictions | — |
| 6 | Cache persona in behavioral service | 2 |
| 7 | Frontend: `AINarrativeCard` component | 4 |
| 8 | Frontend: Narrative cards in all 4 tabs | 7 |
| 9 | Frontend: Predictive warnings in BehaviorTab | 5 |
| 10 | Token tracking + build verification | all |

---

## Cost per User per Day

| Action | Calls | Cost |
|--------|-------|------|
| AI Narrative (4 tabs, cached daily) | 4 | $0.008 |
| AI Persona (cached daily) | 1 | $0.08 |
| Rule-based fallback | ∞ | $0.00 |
| **Total** | | **≤$0.09** |

---

## Verification Checklist

- [x] Backend syntax passes (`ast.parse`) — all 4 files
- [x] Frontend builds (`npm run build`) — 33s, no errors
- [x] 10 new patterns registered in BehavioralAnalysisService
- [x] `/ai-summary?tab=overview` returns narrative (hybrid: LLM or rule-based)
- [x] `/ai-insights` includes predictions from PatternPredictionService
- [x] Persona cached in UserProfile.ai_cache (24hr TTL)
- [x] AI failure → analytics still works (graceful degradation)
- [x] All 4 tabs show AINarrativeCard
- [x] Predictive warnings in BehaviorTab with probability bars
