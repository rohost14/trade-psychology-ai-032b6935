# My Patterns Page — Deep Review & Analysis

*Date: 2026-07-15. Scope: the `/my-patterns` page (titled "Risk Monitor") — every feature, its data flow, real-vs-dummy data, backend, UX/UI, product value, and recommendations. Findings only — nothing implemented.*

*Severity: **P0** = page crashes / broken for real users, **P1** = materially wrong data shown as fact, **P2** = dead/misleading feature, **P3** = polish. **PROD** = product/strategy observation.*

> **UPDATE 2026-07-15 — FIXED (build/tsc verified; tsc for the file 21→7 errors, all remaining pre-existing/elsewhere):**
> - **5.1 crash / 5.5 fake quality:** Removed the **Weekly Discipline Score** section entirely (arbitrary composite, low actionability, duplicated the real Behavior Risk score, 40% fake). This also removed the only `cn` usages (no import needed) and the placeholder trade-quality component. Backend `discipline-summary` endpoint left in place, now unused.
> - **5.2 emotional tax garbage → feature REMOVED.** Emotional Tax was the same arbitrary estimated-cost family as the discipline score (hardcoded per-pattern ₹ table, conflicts with raw-P&L/no-estimation policy). Unwired from the page (EmotionalTaxCard + emotionalTaxCalculator kept on disk, orphaned — reversible).
> - **5.3 streak:** now marks a day non-clean on `danger`/`critical` (was `high`, which never occurs — danger days had counted as clean).
> - **5.4 dead cost:** removed all `estimated_cost` UI; "#1 cost driver" → "most frequent pattern"; breakdown shows count only.
> - **5.6 recs:** worst-pattern/breakdown now keyed by `backend_type`, so tailored `patternRecs` lookups match.
> - **5.7:** "Alert History" card relabeled **"Cooldown History"** (it renders cooldowns).
> - **5.8/5.9:** Refresh handler wrapped `() => fetchStatus()`; title unified to **"My Patterns"**.
> Kept (clean, real): BehaviorScoresCard, PatternCalendar, danger banner, streak, cooldown history. PROD restructuring (de-dup vs Alerts/Dashboard, feedback-loop tie-in, weekly digest → Reports) still open.

---

## 1. What this page is

The behavioural **scorecard / risk cockpit**. Where Alerts is the event feed, My Patterns is meant to be "how am I doing overall" — live danger state, behaviour-risk scores, streaks, emotional cost, a 90-day pattern calendar, and a weekly discipline score. It merges the old Goals + Risk-Monitor + Discipline pages (`MyPatterns.tsx` header comment). It's the retention/gamification surface: streaks, "revenge-free days", weekly score trend.

Route file: `src/pages/MyPatterns.tsx` (785 lines). Header reads **"Risk Monitor"** (not "My Patterns" — see 5.7).

---

## 2. Current features (sections, top to bottom)

1. **Behavior Risk card** (`BehaviorScoresCard`) — headline score + 4 drivers (tilt/risk/discipline/strategy) + top contributor per driver. From `/api/risk/scores` (Phase-5 scores). **Clean, real.**
2. **Worst pattern callout** — "Your #1 cost driver this month" with count + est. cost.
3. **Live danger status banner** (`DangerStatusBanner`) — level, daily-loss-used %, trades today, consecutive losses, active triggers, recommendations, **Alert Guardian** button. From `/api/danger-zone/status`.
4. **Specific data-driven recommendations** — up to 3, derived from worst pattern + live danger state + weekly alert frequency.
5. **Pattern Calendar** (`PatternCalendar`) — 90-day GitHub-style heatmap of clean/caution/danger days. **Clean, real.**
6. **30-day pattern frequency breakdown** — bar list by count + est. cost.
7. **Emotional Tax card** — estimated rupee cost of emotional trading (`calculateEmotionalTax`).
8. **Streak tracker** — current/longest clean streak + milestones (3/7/14/21/30 days).
9. **Alert History (7 days)** card.
10. **Weekly Discipline Score** — gauge (score/100), alert-control + trade-quality breakdown bars, quick stats (trades / danger / caution / revenge-free days), 4-week trend sparkline. From `/api/analytics/discipline-summary`.

Backend: `danger_zone.py` (status/summary/trigger-intervention/escalation), `analytics.py::get_discipline_summary`, `risk.py::get_behavior_scores`.

---

## 3. Real data or dummy?

**Data sources are real** (danger-zone, discipline-summary, risk/scores, risk/alerts, calendar all query live tables). **But several displayed numbers are wrong or dead despite real sources** — this page shows more incorrect data than any reviewed so far:

- `estimated_cost` is **always 0** (engine never populates it) → "cost driver" money never shows; cost-based ranking is meaningless (§5.4).
- **Emotional Tax is fed a broken object** — the `patterns` mapping reads fields that don't exist on the alert (§5.2), so the tax is computed from garbage.
- **Streak counts danger days as clean** due to a severity-string bug (§5.3).
- **Trade-quality** half of the weekly score is a hardcoded neutral placeholder (§5.5).

So: real plumbing, but the headline behavioural numbers a user reads here are substantially untrustworthy today.

---

## 4. Product value (is it valuable? will people pay?)

**PROD-1 — Strong concept, currently the most broken page.** A behavioural scorecard with streaks and a weekly discipline score is exactly the retention mechanic a habit-change product needs — arguably the page people would open daily. But right now: it **crashes for connected users** (§5.1), the **streak is wrong** (§5.3), the **emotional tax is garbage** (§5.2), and the **cost numbers are dead** (§5.4). The value is almost entirely potential, not realized.

**PROD-2 — Heavy overlap with Alerts + Dashboard.** Pattern frequency here duplicates the Alerts "Patterns" tab; danger-state/consecutive-losses duplicate the Dashboard hero + risk state. Ten sections on one page is overload — it reads as "every behavioural widget we have, stacked." Needs an editorial pass on what belongs here vs Alerts vs Dashboard.

**PROD-3 — The gamification is the paid hook, so it MUST be correct.** Streaks, "revenge-free days", weekly-score-trending-up are what make someone renew. A wrong streak (counting a revenge day as clean) doesn't just look bad — it destroys trust in the one number they'd brag about. Fixing correctness here is worth more than any new feature.

---

## 5. Findings

### 5.1 [P0] The page crashes for connected users — `cn` is not imported
`MyPatterns.tsx` uses `cn(...)` at lines 77 (inside `ScoreGauge`), 714, 723, 734 (Weekly Score stats) — but **never imports `cn`** (no `import { cn } from '@/lib/utils'`). All usages sit inside the `{disciplineData?.has_data && (…)}` Weekly Score block. The backend `discipline-summary` returns **`has_data: true` unconditionally** (`analytics.py:3079`), so that block renders for every connected user as soon as the endpoint responds → `ReferenceError: cn is not defined` → the section (and likely the page) throws. These are exactly the TypeScript errors `MyPatterns.tsx(77|714|723|734): Cannot find name 'cn'`. **Fix: import `cn`.** This is the single most important finding — the page's flagship section is non-functional.

### 5.2 [P1] Emotional Tax is computed from fields that don't exist
The `patterns` memo (`MyPatterns.tsx:380-393`) builds objects from **top-level** alert fields — `a.pattern_type`, `a.pattern_name`, `a.severity`, `a.timestamp`, `a.detected_at`, `a.related_trade_ids`, `a.message`. `AlertNotification` has **none** of these at the top level; they live under `a.pattern.*` (`a.pattern.type`, `a.pattern.name`, `a.pattern.severity`, `a.shown_at`, …). So every field is `undefined`: `type` falls back to `'overtrading'` for **every** alert, `name`/`severity` are undefined. `calculateEmotionalTax(patterns, …)` therefore runs on garbage → the Emotional Tax figure is meaningless. (These are the tsc errors on lines 382-387.)

### 5.3 [P1] Streak counts danger days as clean (severity vocabulary bug)
The streak builder (`MyPatterns.tsx:296`) marks a day "not clean" only when `a.severity === 'high' || a.severity === 'critical'`. Raw `/api/risk/alerts` severities are `danger / caution / critical / info` — **`'high'` never occurs, and `'danger'` is not checked**. So a day on which the user got a **danger** revenge alert is counted as a **clean, disciplined day**, inflating the streak, "revenge-free days" proxy, and milestones. The core gamification metric is wrong. (Should be `'danger' || 'critical'`.)

### 5.4 [P2] Dead `estimated_cost` — same as the Alerts page
`worstPattern`, `patternBreakdown`, and `specificRecs` all read `a.pattern.estimated_cost`, which the engine never populates (always 0). Effects: the "Your #1 cost driver" money figure never renders; worst-pattern ranking sorts by a constant 0 then falls through to count; the 30-day breakdown's "₹X" never shows; recommendation cost suffixes never appear. Either wire a real cost (the raw realized loss on the flagged trades — the product decided against modelling charges, but realized loss is available and defensible) or remove the cost UI, consistent with the Alerts-page decision.

### 5.5 [P2] Trade-quality half of the weekly score is a placeholder
`discipline-summary` computes the quality component from `CompletedTrade.quality_score`, but that field **is never populated by any service** (the code comment says so, `analytics.py:3063`), so it always defaults to neutral `4.0/8 → 20/40`. The "Trade quality" breakdown bar is therefore permanently ~50%, and 40% of the discipline score is a flat constant. Either populate `quality_score` or drop the component and rescore alerts to 100.

### 5.6 [P2] Tailored recommendations rarely fire (type-key mismatch)
`specificRecs` looks up `patternRecs[worstPattern.type]`, but `worstPattern.type` is the **frontend** type (`a.pattern.type`, e.g. `revenge_trading`), while `patternRecs` is keyed by **backend** type (`revenge_trade`, `rapid_reentry`, …). `'revenge_trading' !== 'revenge_trade'`, so most patterns miss the tailored copy and fall back to the generic "fired N×" line — gutting the page's "Based on your data" value. (Use `backend_type` for the lookup.)

### 5.7 [P2] "Alert History" card actually shows cooldowns
`AlertHistoryCard` is fed `summary.cooldown_history_7d` and titled **"Alert History (7 days)"**, but it renders **cooldown** records (reason + duration), not alerts. Mislabeled — and it overlaps conceptually with the Alerts page History. Either relabel "Cooldown History" or replace with real alert history (and then it fully duplicates Alerts).

### 5.8 [P3] Refresh button passes the click event as an AbortSignal
`onClick={fetchStatus}` (`MyPatterns.tsx:542`) passes the `MouseEvent` as `fetchStatus`'s `signal` argument, so `api.get(..., { signal: mouseEvent })` gets a non-AbortSignal and `signal?.aborted` is read off an event. Harmless in practice but type-wrong (the tsc error at 542). Use `onClick={() => fetchStatus()}`.

### 5.9 [P3] Title inconsistency
Connected view header: **"Risk Monitor"** (`:540`). Not-connected view + nav: **"My Patterns"** (`:515`). Pick one name.

### 5.10 [P3] `emotionalTaxCalculator` cost table is incomplete
`PATTERN_COSTS` is typed `Record<PatternType, string>` but omits several patterns (`opening_5min_trap`, `options_direction_confusion`, `options_premium_avg_down`, `iv_crush_behavior`, …) — the tsc error at `emotionalTaxCalculator.ts:16`. Those patterns get no cost weight, further skewing the (already broken, §5.2) emotional tax.

---

## 6. What's good (keep)

- **BehaviorScoresCard** — clean, real, well-designed (headline + 4 drivers + top contributor). The best thing on the page.
- **PatternCalendar** — real 90-day heatmap; danger detection correct; strong at-a-glance retention artifact.
- **Danger status banner** — live, real, actionable (Alert Guardian). Good.
- **The overall concept** — a behavioural scorecard with streaks + weekly score is the right retention surface.
- Abort-controller on the status fetch; event-driven refetch on trade/alert; good empty/not-connected states.

---

## 7. What to add / change (product)

1. **Fix correctness first (§5.1-5.6)** before anything else — a scorecard that crashes and miscounts streaks has negative value.
2. **De-duplicate against Alerts + Dashboard.** Decide the page's job: if it's the "scorecard", drop the pattern-frequency list (lives in Alerts › Patterns) and the raw danger banner (lives on Dashboard), and lean into scores + streak + calendar + weekly trend.
3. **Make the streak the hero.** It's the daily-open hook. Once correct, put it near the top with the calendar, not buried mid-page.
4. **Tie in the new alert feedback loop.** The Alerts page now captures "did you stop / took anyway". A "you stopped 8 of 12 danger moments this week" line here would be a far stronger discipline signal than the placeholder trade-quality bar.
5. **Real cost or no cost** — same call as Alerts: realized loss on flagged trades, or remove.
6. **Weekly digest home** (deferred from Alerts review) — the weekly discipline score + trend is the natural anchor for the weekly behavioural summary we said we'd fold into Reports.

---

## 8. Priority summary

| Priority | Item | Type |
|---|---|---|
| P0 | `cn` not imported → Weekly Score section crashes for connected users (5.1) | Crash |
| P1 | Emotional Tax computed from non-existent fields (5.2) | Wrong data |
| P1 | Streak counts danger days as clean — severity bug (5.3) | Wrong data |
| P2 | Dead `estimated_cost` across cost driver / breakdown / recs (5.4) | Dead feature |
| P2 | `quality_score` never populated → 40% of weekly score is a constant (5.5) | Dead component |
| P2 | Tailored recommendations miss (frontend-vs-backend type key) (5.6) | Reduced value |
| P2 | "Alert History" card actually shows cooldowns (5.7) | Mislabel |
| P3 | Refresh passes event as AbortSignal (5.8); title inconsistency (5.9); cost table gaps (5.10) | Polish |
| PROD | De-duplicate vs Alerts/Dashboard; make streak the hero; tie in feedback loop | Product |

*Files reviewed: `src/pages/MyPatterns.tsx`, `src/components/patterns/{BehaviorScoresCard,PatternCalendar}.tsx`, `src/components/goals/EmotionalTaxCard.tsx`, `src/lib/emotionalTaxCalculator.ts`; `backend/app/api/danger_zone.py`, `backend/app/api/analytics.py::get_discipline_summary`, `backend/app/api/risk.py::get_behavior_scores`.*
