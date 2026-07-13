# Behavioral Engine v2 — Implementation Master
*Living document. Updated after each source-doc review. This is the single place that holds everything we have agreed to implement.*

**Source docs reviewed: 4 of 4 + user review (`My_Opnion.md`) — decisions from user review integrated as §1E + Appendix A**
**Status legend**: `AGREED` = locked in from doc + discussion · `PROPOSED` = Claude review finding, pending user confirmation · `TBD` = expected in later docs

---

## 1. Core Architecture Decisions

### 1.1 Two-Axis Pattern Classification — PROPOSED (fixes doc-1 taxonomy conflict)

Doc 1 declares 3 categories (Universal Risk / Personal Baseline / Constitution Violation) but then labels patterns with 5 different types (adds "Emotional Trading" and "Analytics"). These are two different dimensions being mixed. Split them:

**Axis A — Nature** (what the pattern detects, drives UI grouping + four-state dashboard) — FINAL per user review:
- `emotional` — revenge, martingale, FOMO, overconfidence, direction instability, MIS panic, size escalation, premium avg down, recovery bet, profit giveaway, consecutive losses
- `risk` — excess exposure, concentration, meltdown, no stoploss, premium loss event
- `discipline` — cooldown violation, daily trade limit breach (constitution violations)
- `performance` — strategy breakdown, win rate collapse, time-of-day bias (ADDED per user review: these are performance degradation, not emotion/risk/discipline)

**Axis B — Threshold Source** (where the trigger numbers come from):
1. User Constitution (declared rules, locked)
2. Personal Baseline (learned from history)
3. Universal Default (research values, cold-start only)

**Axis C — Disposition** (ADDED per user review, replaces the old "analytics" nature which was a category error):
- `alerting` — can produce user-facing alerts
- `analytics-only` — panic exit, early exit, opening trap, rapid reentry, win rate collapse, strategy breakdown: recorded, feeds state/scores/reports, never alerts

Every pattern = one Nature + one Disposition + resolves thresholds through the B hierarchy top-down. Three orthogonal properties, declared in the Detector Registry (Appendix A).

### 1.2 Threshold Hierarchy — AGREED
```
User Constitution  >  Personal Baseline  >  Universal Default
```
No pattern may rely entirely on a fixed hardcoded number. Universal defaults exist only as cold-start fallback.

### 1.3 Severity Model — FINAL (revised per user review)
**Severity and confidence are independent dimensions. Never combined.**
- **Severity** = risk impact ("how dangerous if true"). Values: `info` / `caution` / `danger`. Determined by the pattern's nature + magnitude (e.g. meltdown at 75% of limit = danger regardless of anything else).
- **Confidence** = detection certainty ("how sure are we this is what it looks like"). 0–100, stored on every alert.
- User's examples: rapid re-entry can be 95% confidence + low severity; session meltdown can be 60% confidence + critical severity.
- **Routing consults both** (matrix TBD — Q22). Working shape: push requires danger severity AND confidence above gate; danger + low confidence → in-app; below minimum confidence → recorded as info, no alert.
- **PROPOSED unification (Claude):** for deterministic detectors (meltdown, exposure — pure arithmetic), confidence ≈ data quality (§A.6). Low confidence on a deterministic pattern means the input data is suspect, nothing else.
- Previous banding proposal (70–84→caution, ≥85→danger) WITHDRAWN — it conflated the two dimensions.

### 1.4 Confidence Scoring — REVISED per user review
Signal-stacking model for ambiguous emotional patterns (`revenge_trade`, `fomo_entry`, `winning_streak_overconfidence`).
**No fixed numeric weights at spec time.** Signals declared with relative importance — `critical` / `high` / `medium` / `low` — mapped to configurable values at runtime. Numeric calibration happens only after production data exists (detector evaluation metrics, §A.5). Config ships with sane initial mappings (e.g. critical=30, high=20, medium=10, low=5) explicitly marked as tuning starting points, not spec constants.

### 1.5 Analytics-Only Mechanism — PROPOSED
Analytics-only patterns still run in the engine and persist as `severity="info"` RiskAlert rows (mechanism already exists — cooldown_violation uses it today). They feed Journal, EOD reports, Analytics tab. They never create user-facing alerts and never notify.

### 1.6 Open Position Data — TBD (major architecture gap)
Doc 1 says exposure/concentration/meltdown "become significantly more accurate with live positions" but the engine runs per-CompletedTrade only. HOW open position data reaches the engine is undefined. Options to discuss:
- (a) inject positions snapshot into EngineContext at run time (positions already synced via Zerodha API)
- (b) separate real-time evaluator for open-position patterns (runs on webhook order events, not just closes)
- Decision expected from later docs; flagged as the biggest unresolved design item.

---

## 1B. Runtime Architecture (from Doc 2)

### 1B.1 State-Driven Engine — AGREED (concept)
Primary unit shifts from "alerts" to **behavioral state**. Per-event O(1) state updates replace per-trade full-history scans (current engine loads all session trades and runs 24 detectors every time).

Three state objects:
- `user_state` — session_pnl, peak_pnl, consecutive_losses/wins, today_trade_count, today_loss_count, tilt/risk/fomo scores, last_loss_time, last_trade_time
- `session_state` — pnl, peak_pnl, drawdown, trades_today, winners/losers, avg winner/loser hold. Reset daily.
- `position_state` — total_open_risk, concentration by symbol/underlying, option/futures exposure. **This answers master Q1 (open position data): a live position-state object fed by order events, consumed by exposure/concentration/meltdown/recovery-bet patterns.**

**PROPOSED hard requirement (doc 2 misses it):** state lives in Redis as a *derived cache*, always rebuildable from Postgres trades. Crash/eviction/manual-bulk-sync → rebuild path required. State is never source of truth.

**PROPOSED (doc 2 misses):** per-user event serialization — two workers processing the same user concurrently = state races. Queue partitioning by broker_account_id.

**PROPOSED (doc 2 misses):** out-of-order webhook events (Zerodha postbacks) — need sequencing/ordering guard before state update.

### 1B.2 Three-Layer Engine — AGREED
Universal Risk Engine / Personal Baseline Engine / Constitution Engine. Maps 1:1 onto master §1.1 Axis B (threshold source). Note: layers are *threshold sources consulted by pattern detection*, not sequential pipeline stages (doc 2's final diagram draws them as a pipeline — misleading, ignore the diagram).

### 1B.3 Event Model — AGREED (concept) / PROPOSED (split)
Event types: trade opened, trade closed, position modified, SL modified, square-off, session start/end, market open/close.

**PROPOSED — the most important implication doc 2 leaves implicit:** patterns split by WHEN they can fire:
- **Entry-time patterns** (fire on Trade Opened — intervention still possible): excess exposure/position_risk, portfolio_concentration, recovery_bet, martingale, revenge_trade, cooldown_violation, overtrading (burst + daily), fomo_entry, overconfidence, expiry_day_overtrading, MIS panic
- **Exit-time patterns** (fire on Trade Closed — retrospective): no_stoploss, premium_loss_event, profit_giveaway, consecutive_loss_streak, direction_instability
- **Session-level / EOD**: early_exit, session analytics
This is the single biggest value unlock: today EVERYTHING fires at position close, when it's too late to act on entry-related risk.

### 1B.4 Baseline Learning — REVISED per user review
- Nightly job 18:15 IST (slot already exists: `personalization-refresh` Celery task)
- Input: last 30–60 sessions
- Output `behavior_baseline`: avg/p95 daily trades, avg position risk, avg hold time, avg reentry delay, win rate, preferred symbols/hours, danger hours, typical peak pnl, typical drawdown
- **Activation: fixed gate (20 sessions AND 100 trades) REPLACED by Baseline Confidence.** A scalper hits 100 trades in 4 days (not enough sessions); a swing trader needs 2 months (too slow). Fixed counts treat them identically.
  - Baseline carries confidence LOW / MEDIUM / HIGH derived from available history.
  - Engine transitions gradually: effective_threshold = conf × personal + (1 − conf) × universal_default. No cliff.
  - **PROPOSED refinement (Claude): confidence is per-metric, not global.** Session-level metrics (daily trade count) mature with SESSION count; trade-level metrics (hold time, sizing) mature with TRADE count. One trader can have HIGH confidence on hold-time baseline and LOW on daily-count baseline simultaneously.
  - Concrete confidence formula = f(sessions, trades, metric variance stability) — needs definition before build (Q23).
- Must write to the `baseline` key `get_thresholds()` already reads (fixes the dead-wiring P0).

### 1B.5 Alert Scoring — AGREED (concept) / CONFLICT to resolve
Signal-weight scoring per pattern (doc 2 revenge example: recent loss +25, same symbol +20, bigger size +20, session red +15, fast re-entry +20 → 100 max).
**CONFLICT: doc 1 says alert gate >70; doc 2 says below 50 = no alert.** Pick one banding, e.g.: <50 discard · 50–69 record as `info` · 70–84 `caution` · ≥85 `danger`. Pending user decision.

### 1B.6 Composite Scores (Tilt / FOMO / Overconfidence / Risk, 0–100) — CONFLICT to resolve
Doc 2 promotes scores to primary user-facing UX ("user sees Tilt Score 88 instead of 5 alerts"). **Directly conflicts with user's earlier decision: compound/tilt state goes to Analytics tab only, nothing new added to alerts.** Resolution PROPOSED: compute scores in state (cheap, feeds AI coach later), display in Analytics/My Patterns only; alerts stay per-pattern. Pending user confirmation.

### 1B.7 Notification Levels — AGREED
```
L0 analytics (no notification) · L1 in-app · L2 push · L3 critical push · L4 guardian
```
Replaces the binary caution/danger→push logic. Each pattern's level set in inventory table (§2).

### 1B.7b Universal Routing Matrix — FINAL (user V3)
| Severity | Confidence | Route |
|----------|-----------|-------|
| Low | any | Analytics |
| Medium | Low | Analytics |
| Medium | High | In-App |
| High | Low | In-App |
| High | High | Push |
| Critical | Low | In-App + Flag |
| Critical | High | Critical Push |
| Critical + Guardian-eligible | High | Guardian |

Severity never replaces confidence; confidence never replaces severity. Both required, always.
Build-time reconciliations: severity scale mapping (Q25); "Flag" definition — PROPOSED: data-quality review queue (critical severity with low confidence usually means suspect input data, §1.3). Confidence Low/High cutoff = config.

### 1B.8 Guardian — AGREED (tightened)
Emergency accountability only. **Hard budget: 1–3 alerts/month.** Patterns: session meltdown (severe), extreme loss spiral, constitution breach (e.g. "exceeded self-defined loss limit by 60%"). Resolves master Q7 — supersedes both doc 1 (meltdown only) and earlier discussion (3 patterns): guardian list = severe meltdown + severe spiral + constitution breach, budget-capped.

### 1B.9 Dedup Engine — AGREED (concept) / TBD (spec)
- Dedup key: user + pattern + severity
- **Stateful re-arm**: after firing, pattern re-fires only when its driving condition worsens (martingale: size increases again) — not on blind 24h expiry
- Severity escalation (caution→danger) always bypasses dedup
- Cross-pattern suppression matrix (revenge vs cooldown_violation, no_stoploss vs premium_loss_event) still TBD — not in doc 2

### 1B.10 Tech Stack — REJECTED as written / PROPOSED mapping
Doc 2 names Node/NestJS + BullMQ/Kafka. **Wrong for this codebase — existing stack is FastAPI + Celery + Redis (Streams) + Supabase Postgres and already implements most of the target architecture.** Mapping:
| Doc 2 says | We use |
|---|---|
| Node/NestJS backend | FastAPI (exists) |
| BullMQ/Kafka queue | Celery + Redis (exists); Redis Streams event bus already live |
| Workers A–E | Celery queues/tasks (trade processing + beat jobs exist; add behavior/notification/baseline separation) |
| Hot data Redis | exists (sessions, dedup, event bus) |
| Warm data Postgres | exists (Supabase) |
| Cold analytics warehouse | defer |
Kafka/5-lakh-user scaling = premature; Redis Streams fine for current scale, revisit at real load.

### 1B.11 Missing From Doc 2 — open items
1. **Migration path** from current engine (big-bang rewrite vs strangler pattern running old+new in parallel) — nothing said
2. **Manual bulk-sync path** — the 5:05pm-alert problem (detected_at = sync time, alerts hours late) unaddressed
3. **Testing/replay** — validate new engine by replaying historical trades against known alerts
4. Multi-account users — state keyed by broker_account_id (assumed, unstated)
5. SL Modified / Position Modified events — Zerodha postback captures order updates; pipeline currently ignores non-fill updates. Extension needed for those event types.

---

## 1C. User Constitution & Onboarding (from Doc 3)

### 1C.1 Scope Split — AGREED (core insight of doc 3)
**User controls (hard rules):** daily loss limit, cooldown duration, max trades/day, max exposure per trade (%), max consecutive losses, trading-hours restrictions, guardian settings.
**User cannot control:** martingale, revenge, recovery bet, profit giveaway, premium destruction detection. These stay behavioral observations — otherwise users config-away their own protection (`max_losses=20, cooldown=0` problem).

Rule criteria: measurable, objective, trackable. "Constitution enforces commitments; Behavioral Engine predicts behavior. Two systems, kept separate." — AGREED.

### 1C.2 Constitution Object — AGREED (shape)
```json
{
  "daily_loss_limit": 5000,
  "max_consecutive_losses": 3,
  "loss_cooldown_minutes": 15,
  "max_daily_trades": 10,
  "max_trade_risk_pct": 3,
  "restricted_windows": ["13:00-14:00"],
  "guardian_enabled": true
}
```
Advanced rules (later, not onboarding): stop-after-profit-target, max symbol exposure %, no-expiry-day-trading, max premium decay exit rule.

**PROPOSED — single source of truth migration:** UserProfile ALREADY has daily_loss_limit, daily_trade_limit, max_position_size, cooldown_after_loss, trading_capital (Settings → Profile tab). Constitution must not become a second store. Migrate: those fields become the constitution object; Settings keeps only non-rule prefs (notifications, display, broker). Existing users: prefill constitution from current profile values, prompt one-time review.

### 1C.3 Lock + Override Semantics — RESOLVES master Q2
Doc 3: 30-day lock after creation/modification, but with emergency override (warning + confirmation + tracked as `constitution_override` — the override itself becomes a behavioral signal). AGREED, with one PROPOSED asymmetry doc 3 misses:
- **Tightening (stricter rule) = allowed instantly, anytime, no friction.** Lowering loss limit is never dangerous.
- **Loosening = friction path.** Warning + typed confirmation + logged event.
- **PROPOSED stronger guard: loosening during market hours takes effect NEXT session ("change applies tomorrow").** Kills mid-tilt rule edits dead while respecting user autonomy. Loosening outside market hours: effective immediately after friction flow.
- Not locked ever: capital, experience level, trading style (facts, not commitments).

### 1C.4 Violation Severity — AGREED
- Level 1 "Approaching" at 80% of rule (e.g. ₹4,000 of ₹5,000 loss)
- Level 2 "Breached" at 100%
- Level 3 "Severe" at 120%+ → guardian-eligible
**PROPOSED consolidation:** existing early-warning service (session 36: push at 70% P&L limit, 80% trade count) becomes Level 1 of this system — one threshold set, one code path, not two parallel warning systems. Reconcile 70% vs 80% number.

### 1C.5 Onboarding — FINAL (user V3 confirmed review screen)
Flow: **3 questions (trading style, experience, capital) → generate recommended constitution → ONE review screen → accept or adjust → finish.**
Review screen wording (user V3): *"Based on your profile, here are your recommended trading rules. You can accept them or customize them now. You can always tighten them immediately, while relaxing them later requires additional safeguards."* Explicit acceptance = ownership; without it they're the app's rules, not the trader's.
Guardian: stays in onboarding, optional, skippable (user review overruled removal — users who join FOR accountability shouldn't have to discover it later).
Everything else (restricted windows, advanced rules, remaining customization) → My Rules, later. Removed questions preserved in Advanced setup, not deleted.

**Defaults (behavioral presets from experience + style ONLY — capital-based behavioral presets REMOVED per user review; capital influences risk arithmetic only):**
| | Beginner | Intermediate | Advanced |
|---|---|---|---|
| Daily loss | 2% capital | 2% | 2–3% |
| Max trades | 5 | 10 | baseline-derived |
| Cooldown | 15 min | 10 min | 5 min |
| Consec losses | 3 | 4 | 5 |
| Risk/trade | 1% | 2% | 2–3% |
(₹ amounts computed from capital; the behavioral numbers never vary by capital. A ₹20k trader can be disciplined; a ₹20L trader can be reckless.)

### 1C.6 My Rules UI — FINAL (user V3): top-level navigation item
Constitution accountability is the product's differentiator, not a setting. Buried in Settings = configured once, never seen again; inside My Patterns = mistaken for analytics. It must feel *living* — a destination.
Contents: Active Constitution · Today's Progress (₹3,200/₹5,000, 7/10 trades, cooldown active) · Rule Violations · Constitution Score · Rule History · Guardian · Edit Rules.
**NOTE (Claude):** user V3 sketched a full nav (Dashboard/Trades/Journal/Patterns/My Rules/Insights/Profile) that differs substantially from the current app nav (Dashboard/Analytics/Alerts/My Patterns/Blowup Shield/Chat/Reports/Settings). Only the "My Rules = top-level" decision is adopted here; the broader IA restructure is a separate future discussion, not silently in scope.

### 1C.7 Constitution Score (0–100 rule adherence) — AGREED (concept) / PROPOSED (consolidation)
95+ excellent · 80–95 good · 60–80 needs improvement · <60 high risk.
**Score sprawl warning:** we now have four score concepts floating — Constitution Score (doc 3), composite Tilt/FOMO/Risk scores (doc 2), pattern family score (earlier discussion), existing Weekly Discipline Score in My Patterns (session 34). PROPOSED: Constitution Score absorbs/replaces Weekly Discipline Score; family score + composite scores live in Analytics. One scoring surface per tab, designed together, later.

### 1C.8 Constitution vs Behavioral Pattern Suppression — FINAL (corrected per user review)
When a constitution rule exists and fires, the overlapping behavioral pattern must not double-NOTIFY:
- `max_consecutive_losses` breach suppresses `consecutive_loss_streak` notification
- `loss_cooldown` violation suppresses `revenge_trade` notification
- `max_daily_trades` breach suppresses `daily_overtrading` notification
- `max_trade_risk_pct` breach suppresses `position_risk` notification

**Critical correction (user review): suppression applies to the USER NOTIFICATION only. The BehaviorEvent is ALWAYS generated and ALWAYS updates state.** A cooldown violation that hides the revenge alert must still raise the Tilt Score, still count toward Death Spiral, still appear in analytics. Suppressing evidence would corrupt the behavioral model. Rule: constitution alert wins the notification (psychologically stronger — "YOUR rule"); the behavioral event records silently and feeds everything downstream. This principle governs the entire cross-pattern suppression matrix (Q4): dedup/suppression operates at the notification layer, never at the event layer.

### 1C.9 Live-Price Rule Subsystem — FLAGGED (scope, doc 3 doesn't notice)
Advanced rules "exit if option loses 40% premium" and "stop after ₹10,000 profit" require monitoring OPEN position MTM in real time — price-tick-driven, not trade-event-driven. Different subsystem from the engine (needs KiteTicker/LTP watcher on open positions). Defer both rules until that subsystem is scoped; do not block v2 on it.

---

## 1D. New Patterns & Behavioral States (from Doc 4)

Core idea — AGREED: the 24 patterns detect *events*; the new layer detects *states*. Humans operate in states. Many existing patterns become more useful as inputs to states than as standalone alerts.

### 1D.1 Tilt Score (P25) — AGREED / decay simplified per user review
Composite 0–100: consecutive losses (0–25) + revenge (0–20) + recovery bets (0–20) + martingale (0–20) + giveaway (0–15). Bands: 0–30 normal · 30–60 elevated · 60–80 high · 80+ critical.
Lives in `user_state.current_tilt_score` (doc 2 already reserves the field — consistent).
Requirements:
- **Decay: simple exponential decay only** (user review: no complicated recovery models, no win-reduces-tilt weighting in v1 — validate in production first). Scores decay naturally absent new negative events.
- **Per-event contributions**: relative importance labels → config-mapped values (§1.4), not spec constants. Doc 4's own example didn't reconcile — moot now.
- **Hysteresis for any alerting**: crossed 80 → fired; dips to 75 → back to 82 must NOT re-fire. Re-arm only below 60.
- Daily reset with session state.
**Display**: Analytics / My Patterns per user's standing decision (Q10). Whether critical tilt (80+) may alert = user decision.

### 1D.2 Death Spiral (P26) — FINAL (user V3, supersedes doc 4's raw signal counts)
State-based definitions, NOT signal counts:

| Level | Definition | In-App | Push | Guardian |
|-------|-----------|--------|------|----------|
| **Warning** | Behavior deteriorating (weighted signals present, capital still within limits, sizing normal) | ✅ | ❌ | ❌ |
| **Danger** | Behavior deteriorating + capital at meaningful risk (high tilt, recovery bet/martingale, session deteriorating) | ✅ | ✅ | ❌ |
| **Critical** | Behavior deteriorating + capital at severe risk + discipline violated + **continued escalation** | ✅ | ✅ | ✅ |

**Critical requires multi-domain agreement — at least 3 of the 4 behavioral domains (Emotional / Risk / Discipline / Performance) independently indicating deterioration.** Never raw detector count ("6 detectors fired" ≠ critical). Multiple independent systems must agree the trader is actively self-destructing. This is what dramatically reduces false positives, and it reuses the §1.1 nature axis as the domain definition.

**Continued escalation** = trader still opening positions AFTER the discipline breach / meltdown threshold. Rationale (user): trader who hits danger and STOPS = the system worked — no guardian. Trader who breaches constitution, overrides it, and keeps opening trades = exactly why guardian exists.

Implementation: event-of-events consuming the BehaviorEvent log (today_patterns set already exists). Time-compression weighting (4 signals in 90 min ≠ 4 signals in 6 hours) retained from earlier review.

### 1D.3 Same Symbol Obsession (P27) — AGREED, resolves Q8
3+ losses on same underlying in session + 2+ re-entries; increasing size = severity bump to danger. In-app.
This IS the `same_symbol_loss_chase` we proposed pre-docs. "Probably more valuable than FOMO" — agreed.
**PROPOSED suppression pair (add to matrix):** `options_premium_avg_down` fires on first same-direction re-entry after big loss; obsession fires at 3+ losses and suppresses further avg_down alerts that session (obsession is the escalation).

### 1D.4 Time Of Day Bias (P28) — AGREED
Real-time: trade opened at 13:15 → check learned `danger_hours` (already computed by learn_patterns, already stored in detected_patterns!) → in-app nudge with historical numbers. Minimum 30 sessions.
Requires entry-time detection (§1B.3). Complements morning-intent push (day-level) without duplicating it (hour-level).

### 1D.5 Win Rate Collapse (P29) — FINAL: ANALYTICS-ONLY (per user review)
No standalone real-time alerts, ever. Two independent reasons:
1. Statistics: at baseline 58%, a 15-trade sample has ~12.7pp standard deviation; doc 4's "mild" tier fires on ~1.1σ = pure variance. False "strategy broken" alarms are harmful (trader abandons working strategy).
2. Win rate is strategy-dependent (user review): 30% WR + profit factor 2.3 = excellent trader; 80% WR + PF 0.8 = losing trader. Win rate alone routes wrong.
Disposition: analytics-only, one input into Strategy Health (§1D.6). Statistical treatment (binomial vs baseline) still applies within analytics display.

### 1D.6 Strategy Breakdown (P30) — AGREED / analytics-only PROPOSED
Multi-signal: win-rate collapse + profit-factor collapse + shrinking winners + growing losers + rising early-exit + rising giveaway. Statistically much sounder than P29 alone.
Slow-moving structural signal → belongs in Analytics + weekly digest/EOD report, never an intraday alert. Doc leaves notification unspecified; setting it to analytics-only.

### 1D.7 Concentration Risk (P31) — DUPLICATE of §2 10b
Same pattern as portfolio_concentration from doc 1's excess_exposure split. Doc 4 adds the missing levels: largest-underlying exposure ÷ total exposure — warning 40% · danger 60% · critical 80%. Adopted into 10b.
**PROPOSED edge fix:** with one open underlying, concentration = 100% by definition → fires on every single-position trader. Concentration requires 2+ open underlyings; single oversized position is position_risk/all-in territory.
**Doc self-contradiction noted:** Tier A "must build" but requires position_state, which doc's own Tier C says doesn't exist yet. Blocked on position_state either way.

### 1D.8 All In Bet (P32) — FINAL: one detector, branded top tier (per user review)
Internally: single detector (position_risk), one severity ladder — caution at constitution `max_trade_risk_pct` (or 5% default), danger 10%+, critical 30%+, extreme 50%+ with emotional multiplier (recent losses / recovery / martingale bump severity). No duplicate alerts.
Externally: the extreme tier is PRESENTED to the user as **"All-In Bet"** — users instantly understand "ALL-IN"; nobody feels "Position Exposure Exceeded." Presentation-layer naming on the same event, not a second pattern. (User review kept the label; merge of logic stands.)

### 1D.9 Scoring Surface — FINAL SHAPE (user V2): one headline, four drivers
```
Behavior Risk (headline, 0–100)
  ├─ Tilt (emotional)
  ├─ Risk
  ├─ Discipline (constitution adherence, inverted)
  └─ Strategy Health (performance)
```
Users get ONE number; the four drivers sit underneath it. Unifies all prior score concepts (doc 2 composites, doc 3 Constitution Score, doc 4 states, family-score idea, existing Weekly Discipline Score).

**Detector → driver-score aggregation — FINAL (user V3 + V4 corrections):**
```
Contribution = Signal Importance × Confidence × Detector Multiplier   (NO recency term)
Driver Score = Σ Contributions → exponential decay over time → clamp 0–100
```
Never average. Never flat point-adds. **One aging mechanism only** (V4): the event contributes at full weight, the running score decays exponentially. No recency multiplier at contribution time.
**No positive-behavior credits in v1** (V4): no "good cooldown → Tilt −8". Absence of new negative behavior + decay IS the recovery. Positive credits considered in v1.1 with production data.

**Headline aggregation — FINAL (user V4): dominant-driver weighted.**
Behavior Risk ≈ the highest driver, nudged by the rest — e.g. Tilt 95 / Risk 20 / Discipline 90(inv) / Strategy 85 → headline 90–95, NOT the 72.5 a mean would give. Exact formula at build: `headline = max(drivers) + small weighted contribution of remaining drivers, clamped 0–100`, Discipline direction-inverted before combining.
**Naming collision:** engine already has a session risk score + states (Stable→Pressure→Tilt→Breakdown). Behavior Risk replaces/absorbs it — one score system, not two.

**Display (user V2, resolves Q10): progressive disclosure, not analytics-only.**
- Dashboard: coarse band only — "Behavior Risk: High" (Normal / Elevated / High / Critical)
- Analytics / My Patterns: full detail — Tilt 82, contributors (revenge, martingale, recovery bet), history
- Users shouldn't have to visit Analytics to know they're tilted. Ambient dashboard state ≠ an alert; consistent with mirror-not-blocker and with "nothing new in alerts."

### 1D.10 Build Order — ADJUSTED from doc 4
Doc 4's Phase 1 includes Concentration Risk, which is blocked on position_state (its own Tier C dependency). Corrected order:
- **Phase 1**: Tilt Score + Same Symbol Obsession (both need only the event log — cheap) 
- **Phase 2**: Death Spiral + Time Of Day Bias (event log + existing learn_patterns output + entry-time events)
- **Phase 3**: Concentration Risk + All-In tiers (after position_state ships) 
- **Phase 4**: Win Rate Collapse + Strategy Breakdown (needs robust baseline stats)

---

## 1E. User Review Decisions (from `My_Opnion.md`) — summary of what changed

| # | Decision | Where applied |
|---|----------|---------------|
| 1 | Confidence weights → relative importance labels (critical/high/medium/low), config-mapped, tuned post-production | §1.4 |
| 2 | Baseline activation → Baseline Confidence (gradual blend), not fixed counts | §1B.4 + Q23 |
| 3 | Severity ⊥ Confidence — independent dimensions, routing consults both | §1.3 + Q22 |
| 4 | consecutive_loss_streak: reduce standalone notification weight, KEEP as major input to Tilt/Death Spiral/emotional models | §3, already aligned |
| 5 | Win Rate Collapse → analytics-only, input to Strategy Health, never real-time | §1D.5 |
| 6 | All-In Bet: internal merge stands, external label "All-In Bet" for the extreme tier | §1D.8 |
| 7 | Guardian stays in onboarding, optional/skippable | §1C.5 |
| 8 | Performance = 5th nature category; "analytics" reclassified as Disposition axis | §1.1 |
| 9 | Data Quality (GOOD/PARTIAL/UNKNOWN/INVALID) input to every detector; confidence degrades with input quality | §A.6 |
| 10 | State field ownership table — every field exactly one owner (peak_pnl ambiguity caught) | §A.7 |
| 11 | Suppression = notification-layer ONLY; BehaviorEvent always generated, always updates state | §1C.8 |
| 12 | All numeric thresholds → configuration; spec describes behavior not values | global |
| 13 | Score recovery: simple exponential decay only in v1 | §1D.1 |
| 14 | Onboarding: 3 questions (style/experience/capital) + auto-generated constitution (+ Claude: one review screen for ownership) | §1C.5 |
| 15 | Capital-based behavioral presets removed; capital → risk arithmetic only | §1C.5 |
| 16 | Engineering standards → Appendix A | Appendix A |

Plus (prose sections): Pattern Validation Framework, mandatory offline replay, detector versioning, explainability requirement, detector evaluation metrics, Detector Registry — all in Appendix A.

**The governing razor (user):** for every new concept ask — *does this improve detection accuracy, reduce false positives, or increase user trust in alerts? If not, it waits until the core engine proves itself.*

---

## 2. Final Pattern Inventory (end state after doc 1)

Count: 24 current → 2 merges (−2) → 2 splits (+2) → **24 detectors**, of which 4 analytics-only, ~20 alert-capable.

| # | Pattern (final name) | Disposition | Nature | Threshold source | Notification |
|---|---------------------|-------------|--------|------------------|--------------|
| 1 | consecutive_loss_streak | KEEP, rebuild triggers | emotional | Constitution → Baseline → Default | danger only (push) |
| 2 | revenge_trade | KEEP, confidence model | emotional | Constitution (cooldown) + confidence | high-confidence only (push) |
| 3a | overtrading_burst | KEEP (split) | personal-baseline | Baseline → Default | push on danger |
| 3b | daily_overtrading (NEW, split from 3) | NEW pattern_type | discipline | Constitution → Baseline → Default | in-app; push if constitution breach |
| 4 | size_escalation | KEEP, risk-% based | emotional | Baseline | in-app only |
| 5 | rapid_reentry | ANALYTICS-ONLY | analytics | — | none |
| 6 | panic_exit | ANALYTICS-ONLY | analytics | — | none |
| 7 | martingale_behaviour | KEEP, risk-% based | risk (universal) | Universal + Baseline | push |
| 8 | cooldown_violation | REDESIGN: only if user enabled cooldown, else disabled | discipline | Constitution only | push |
| 9 | direction_instability (MERGE of rapid_flip + options_direction_confusion) | NEW merged | emotional | Default | in-app |
| 10a | position_risk (from excess_exposure) | KEEP (split) | risk (universal) | Constitution → Baseline → Default | push on danger |
| 10b | portfolio_concentration (NEW, split from 10; levels from doc 4 P31: 40/60/80%, requires 2+ open underlyings) | NEW — needs position_state | risk (universal) | Constitution → Default | push on danger |
| 11 | session_meltdown | KEEP — highest priority | risk (universal) | Constitution → Baseline → Default | push + guardian |
| 12 | fomo_entry | KEEP, confidence model | emotional | confidence | in-app |
| 13 | no_stoploss | KEEP, expiry/instrument adjusted | risk (universal) | Default (adjusted) | push on danger |
| 14 | early_exit | ANALYTICS-ONLY (EOD) | analytics | — | none |
| 15 | winning_streak_overconfidence | KEEP (already fixed same-underlying) | emotional | Baseline | high-confidence only |
| 17 | options_premium_avg_down | KEEP, add same-direction check | emotional | Default | in-app |
| 18 | premium_loss_event (MERGE of iv_crush + premium_destruction) | NEW merged, levels 40/60/80% | risk (universal) | Default (moneyness/expiry adjusted — PROPOSED) | push at 80% only |
| 20 | expiry_day_overtrading | KEEP | personal-baseline | Baseline → Default | push severe only |
| 21 | opening_5min_trap | ANALYTICS-ONLY | analytics | — | none |
| 22 | end_of_session_mis_panic | KEEP + profitable-suppression | emotional | Default | in-app |
| 23 | post_loss_recovery_bet | KEEP, risk-% based | risk (universal) | Baseline | push |
| 24 | profit_giveaway | KEEP, % of peak + capital-scaled floor | emotional | Baseline (capital-scaled) | push on danger |

**New detectors from doc 4** (see §1D): tilt_score (state), death_spiral, same_symbol_obsession, time_of_day_bias, win_rate_collapse, strategy_breakdown (analytics). P31 merged into 10b; P32 merged into 10a.

**Frontend patternDetector.ts (8 detectors): REMOVE entirely — AGREED.** Backend is single source of truth.

---

## 3. Pattern-Level Decisions From Doc 1 + Review

### consecutive_loss_streak
- Two parallel counters: strict consecutive AND total session losses (wins between don't reset the session counter) — AGREED from earlier discussion.
- Trigger signals: consecutive count, total loss amount, loss % of capital, same-symbol repetition, rising frequency.
- PROPOSED fix: doc-1 alert levels are weak ("constitution exceeded + session P&L negative" is nearly tautological — consecutive losses imply negative P&L). Replace Medium trigger with: loss amount ≥ X% of daily loss limit. High trigger (sizing increasing) overlaps size_escalation/martingale — use it as a severity booster, not a separate level.
- Context must include loss trades list (symbol, pnl, exit_time).

### revenge_trade
- Confidence 0–100, alert >70. Signals: recent loss, re-entry speed, same underlying, larger size, session red, same symbol.
- ₹500 floor → % of capital (with min/max clamps). 20-min window → user cooldown → baseline-derived → default.
- Context: losing trade + new trade + size comparison.
- PROPOSED: define signal weights before build; define confidence→severity band mapping (1.3 above).
- PROPOSED: define dedup/priority vs cooldown_violation — if user has cooldown enabled and revenge fires in that window, both may trigger. Rule: cooldown_violation (constitution breach) wins; revenge_trade suppressed for that trade.

### overtrading_burst / daily_overtrading
- Split into two pattern_types — AGREED.
- Burst threshold derived from personal baseline (e.g. 75th percentile of user's 30-min counts), fallback default.
- Daily threshold from constitution (user-declared max trades/day) → baseline → default.
- Keep profitable-burst suppression.

### size_escalation
- Compare **position risk % of capital**, not raw quantity — AGREED (kills cross-instrument bug class).
- Same underlying required. Escalation trade list in context.

### rapid_reentry → analytics-only
- PROPOSED caveat: rapid re-entry remains a *signal input* to revenge_trade confidence. Keep computation, kill the standalone alert.

### panic_exit → analytics-only
- Exclude SL-triggered exits. Track hold duration, loss size, exit reason. Never notify.

### martingale_behaviour
- Same underlying, risk-% based sizing comparison. Verify same-underlying uses `instrument_parser.parse_symbol().underlying`.
- Universal Risk → push.

### cooldown_violation
- Exists ONLY if user enabled cooldown (constitution). Otherwise detector disabled. Push on violation.
- Takes priority over revenge_trade (see above).

### direction_instability (merged)
- Level 1: exact instrument reversal. Level 2: underlying reversal (CE↔PE). Level 3: multiple flips in session.
- PROPOSED severity mapping: L1/L2 = caution, L3 = danger. In-app only per doc 1.
- Context: prior position P&L (flip after loss = emotional; after profit = possibly strategy).

### excess_exposure → position_risk + portfolio_concentration
- Position risk: single position % of capital. Concentration: one underlying dominates account.
- Concentration REQUIRES open position data — blocked on 1.6 decision.
- Never fixed rupees.

### session_meltdown
- Highest priority pattern. Drawdown vs daily loss limit: Constitution → Baseline → Default.
- Push + Guardian WhatsApp.
- PROPOSED: with open-position data, include unrealized MTM in drawdown (currently realized-only).

### fomo_entry
- Confidence model: multiple underlyings + session negative + high frequency. In-app.

### no_stoploss
- Large loss AND no SL order (exit_order_type gate — already implemented). Adjust thresholds for expiry proximity + instrument type.
- PROPOSED: push on danger only (doc says "Push" without granularity).

### early_exit → analytics-only (EOD)
- Winner vs loser hold time. EOD report + Analytics tab only.

### winning_streak_overconfidence
- Already rebuilt (commit `0b558b7`): streak = any instrument, size = same-underlying baseline. Doc 1 consistent with this.
- Notification: high confidence only.

### options_premium_avg_down
- Add same-direction requirement (CE→CE / PE→PE) — re-entering opposite direction is not averaging down.

### premium_loss_event (merged)
- Levels: 40% / 60% / 80% premium loss. Context: hold time, entry premium, exit premium.
- Push at 80% only.
- PROPOSED: moneyness/expiry adjustment — 40% on deep-OTM near expiry = noise. Same adjustment doc already demands for no_stoploss; apply here too.

### expiry_day_overtrading
- Frequency vs expiry-day personal baseline. Special rules 0DTE/weekly. Push severe only.

### opening_5min_trap → analytics-only
- Trade already completed; retrospective. Journal/EOD only.

### end_of_session_mis_panic
- MIS entries after 15:00 AND negative session AND repeated entries (tightened from count-only).

### post_loss_recovery_bet
- Distinct from martingale: single outsized jump vs progressive. Risk-% based. Push.

### profit_giveaway
- Peak erosion as % of peak, not fixed ₹1000.
- PROPOSED: keep a capital-scaled absolute floor (e.g. max(0.2% capital, ₹500)) — pure % breaks at tiny peaks (peak ₹300, lose ₹200 = 66% → noise alert).

---

## 4. P0 Bugs (fix before/during architecture work) — AGREED

1. `trigger_trade_id = None` everywhere — alerts never reference triggering trade
2. Cross-instrument raw-quantity comparisons (size_escalation, recovery_bet, martingale — verify each)
3. Missing trade context lists in most patterns
4. Dedup logic redesign (currently 24h blanket per pattern_type; severity escalation partially handled) — full spec TBD in later docs
5. Same-underlying validation everywhere sizes are compared
6. Quantity-based sizing → risk-% of capital based

P1: overlapping alerts (dedup between related patterns), duplicate notifications, open-position awareness.
P2: confidence scoring rollout, baseline integration.

**Known dead wiring (from earlier audit, still true):** `learn_patterns()` never writes the `baseline` dict that `get_thresholds()` reads — adaptive layer is disconnected. Any baseline work must fix this first.

---

## 5. Open Questions (pending discussion / later docs)

1. ~~Open position data architecture~~ — RESOLVED by doc 2: `position_state` object fed by order events (§1B.1). Implementation detail (webhook pipeline extension) still to spec.
2. ~~Constitution lock semantics~~ — RESOLVED by doc 3 + review (§1C.3): 30-day soft lock, tightening always instant, loosening = friction + logged `constitution_override` signal; PROPOSED addition: in-session loosening takes effect next session.
3. ~~Confidence signal weights~~ — RESOLVED by user review: relative importance labels, config-mapped, tuned post-production (§1.4). Signal LISTS per pattern still to enumerate at build time.
4. Dedup cross-pattern suppression matrix — stateful re-arm agreed (§1B.9), suppression pairs TBD.
5. ~~Baseline validity~~ — RE-RESOLVED by user review: Baseline Confidence with gradual blend replaces the fixed 20-session/100-trade gate (§1B.4). Formula definition = Q23.
6. Analytics-only rows: keep in risk_alerts as `info`, or separate table?
7. ~~Guardian scope~~ — RESOLVED by doc 2: severe meltdown + extreme spiral + constitution breach, hard budget 1–3/month (§1B.8).
8. ~~New patterns~~ — RESOLVED by doc 4: same_symbol_obsession (§1D.3), time_of_day_bias (§1D.4), win_rate_collapse (§1D.5) all specified.
9. ~~Alert score gate conflict~~ — SUPERSEDED by user review: severity and confidence are independent (§1.3). Gate question becomes part of the routing matrix (Q22).
10. ~~Composite scores UX~~ — RESOLVED (user V2): progressive disclosure. Dashboard = coarse band ("Behavior Risk: High"), Analytics = full scores + contributors (§1D.9).
11. ~~Migration path~~ — RESOLVED (user V2): strangler, 100% agreed. Replay-test each migrated pattern before cutover.
12. ~~Bulk-sync semantics~~ — RESOLVED (user V2, strengthened): alert from a PAST session detected during sync → analytics only, NEVER push, NEVER guardian ("otherwise users think the app is broken"). PROPOSED staleness ladder (Claude): different session → analytics-only · same session but detection lag > X min → in-app only, no push · real-time → full routing. detected_at always = trade time.
13. ~~My Rules placement~~ — RESOLVED (user V3): top-level navigation item, a living destination not a settings page (§1C.6). Broader nav restructure sketched in V3 = separate future discussion, NOT in scope.
14. **Score consolidation** (§1C.7): Constitution Score vs Weekly Discipline Score vs composite scores vs family score — one design pass needed, later.
15. ~~Constitution violation shape~~ — RESOLVED (user V2): single `constitution_violation` pattern_type with rule key in context ("rule": "cooldown").
16. ~~Early-warning merge number~~ — RESOLVED (user V2): configuration value, nothing hardcoded.
17. ~~Constitution store~~ — RESOLVED (user V2): per user.
18. ~~Rule audit~~ — RESOLVED (user V2): constitution_history required.
19. ~~Death spiral~~ — RESOLVED (user V3): Warning = in-app · Danger = push, no guardian · Critical = push + guardian. Critical requires 3+ independent domains + continued escalation, never raw counts (§1D.2).
20. ~~Tilt decay parameters~~ — RESOLVED (user V2): fix the STRATEGY now (simple exponential, configurable), not the numbers. Config ships with an initial half-life as tuning start; no debates over 40 vs 50 min pre-launch.
21. ~~Scoring surface~~ — RESOLVED (user V2): one headline (Behavior Risk) + four drivers (§1D.9).
21b. ~~Headline aggregation~~ — RESOLVED (user V4): dominant-driver weighted headline; single aging mechanism (decay only, no recency term); no positive credits in v1 (§1D.9).
22. ~~Routing matrix~~ — RESOLVED (user V3): universal table adopted (§1B.7b). Two reconciliations at build: severity scale (Q25) and "Critical+Low-conf → In-App + Flag" — define Flag (PROPOSED: data-quality review queue, per §1.3 deterministic-confidence unification).
23. ~~Baseline Confidence formula~~ — RESOLVED (user V3): per-metric records {confidence, last_updated, sample_size, variance}; LOW→defaults, MEDIUM→blend, HIGH→trust baseline. Band cutoffs = config (§1B.4).
24. ~~Constitution review screen~~ — RESOLVED (user V3, adopted Claude's recommendation): 3 questions → generate → ONE review screen ("accept or adjust… tightening always instant, relaxing requires safeguards") → finish. Ownership preserved (§1C.5).
25. ~~Severity scale~~ — RESOLVED (user V4): four severities — `info / caution / danger / critical`. Small enum migration. Danger = e.g. martingale; Critical = e.g. death spiral + meltdown + constitution breach → critical push + guardian.

---

## 6. Flagged For Later (not in current scope)

- ~~Tilt/compound state detection~~ — formalized by doc 4 as Tilt Score + Death Spiral (§1D.1–1D.2); display decision = Q10/Q19.
- ~~Pattern family score~~ — superseded by four-state dashboard (§1D.9, Q21).
- Frontend detector removal execution plan (when engine v2 lands).
- Live-price rule subsystem (§1C.9) — premium-decay exit rule, profit-target stop.
- Docs cleanup: `16_behavioral_patterns_complete.md` is stale (says 15 backend patterns; reality 24) — rewrite after v2 ships.

---

## Appendix A — Engineering Standards (from user review)

### A.1 Detector Registry
One declarative registry, not 30 scattered classes. Every detector declares:
`name · version · nature · disposition · entry/exit/session trigger · dependencies · uses_baseline · uses_constitution · uses_position_state · notification_level · owner`
The §2 inventory table becomes this registry in code. At 40 detectors this is survival, not luxury.

### A.2 Detector Versioning
Every alert stores the detector version that produced it. Alerts from martingale v1 vs v3 must remain distinguishable (column on risk_alerts).

### A.3 Pattern Validation Framework
Every detector ships with acceptance criteria BEFORE enabling: target precision, recall, false-positive %, false-negative %. Without targets, threshold arguments never end.

### A.4 Offline Replay Testing — MANDATORY
No detector goes live without replaying historical trades and verifying it fires correctly. Also the migration mechanism (strangler, Q11).
**Replayability (stronger than replay testing):** store detector version + input snapshot with each BehaviorEvent so improved detectors can re-evaluate historical data ("what would revenge v3 have caught last year?").

### A.5 Detector Evaluation (ongoing, production)
Per-detector dashboard: precision, recall, FP%, FN%, average confidence, average user dismiss rate. Six months in, "FOMO precision 27%" tells us exactly what needs work. Dismiss rate feeds the alert-fatigue question (earlier Q6 discussion) — measure first, auto-mute decisions later.

### A.6 Data Quality
Every detector input carries quality: `GOOD / PARTIAL / UNKNOWN / INVALID`. Sources of degradation: duplicate webhooks, missing executions, delayed postbacks, partial fills, cancelled orders, broker outages, sync failures. Confidence calculations must factor input quality. For deterministic detectors, confidence ≈ data quality (§1.3).

### A.7 State Ownership Table
Every state field has exactly ONE owning object. Known ambiguity already caught: `peak_pnl` appears in both user_state and session_state in doc 2's spec — resolve (belongs to session_state; user_state references). Full ownership table required before state model build.

### A.8 Explainability
Every alert must answer WHY. Not "Martingale detected" but: confidence 86% because → 3 consecutive losses · position risk 2.1× · same underlying · session P&L −4.8%. Evidence array (signal, value, contribution) stored in alert context. The trade-list context work already shipped (overtrading, overconfidence) is this requirement's first installment.

### A.9 Numeric Config Discipline
No threshold/weight/band constants in detector code. Everything in configuration (extends existing `trading_defaults.py` discipline to all new systems).

### A.10 Detector Dependency Rules (user V2)
Every detector declares **Consumes** (state objects, baseline, constitution) and **Produces** (BehaviorEvent, score contributions — e.g. Tilt +12, Risk +6) in the registry.
**Layering rule: no detector may consume another detector. Only BehaviorEvents or State.** Prevents spaghetti logic and circular dependencies.

Canonical dependency graph (one direction only, upward):
```
L0  Primary State  (session/user/position facts, baseline, constitution)
L1  Detectors      consume L0 + trade events → produce BehaviorEvents
L2  Meta-detectors (Death Spiral) consume BehaviorEvents → produce BehaviorEvents
L3  Scores         (Tilt/Risk/Discipline/Strategy) consume BehaviorEvents + L0
L4  Headline       (Behavior Risk) consumes L3
L5  Routing        consumes BehaviorEvents + severity + confidence
```
**PROPOSED patch (Claude) — the state backdoor:** scores live in `user_state` (current_tilt_score), and detectors are allowed to consume state — so a detector could consume a score derived from other detectors' events, and the cycle sneaks back in. Fix: state splits into **primary state** (facts: pnl, counts, times, positions) and **derived state** (scores). Detectors consume primary state only. If a detector ever genuinely needs a score, it takes the previous tick's value (explicit one-tick delay), never the live one.

---

*All 4 source docs + user reviews V1–V4 integrated. **SPEC COMPLETE.** Remaining build-time items (resolvable during implementation, no user decision needed): Q4 suppression-matrix enumeration, Q6 analytics-row storage choice. Implementation plan: `01_PHASED_IMPLEMENTATION_PLAN.md`.*
