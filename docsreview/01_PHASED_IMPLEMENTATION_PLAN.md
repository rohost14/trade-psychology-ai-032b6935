# Behavioral Engine v2 — Phased Implementation Plan
*Companion to `00_IMPLEMENTATION_MASTER.md` (the WHAT). This is the HOW and WHEN.*
*Created Session 40 · 2026-07-13*

---

## Guiding Principles (locked, from master)

1. **Strangler migration** — old engine keeps running; new engine takes over one piece at a time. No big-bang cutover of a live alerting system.
2. **Replay-mandatory** — nothing goes live without replaying historical trades and validating fires (A.4).
3. **The razor** — every phase item must improve detection accuracy, reduce false positives, or increase user trust. Otherwise it waits.
4. **Archive, never delete** — dead source files move to `_archive/`, per standing project rule.
5. **Notification-layer suppression only** — BehaviorEvents always recorded, always update state (§1C.8).
6. **Config discipline** — no new constants in detector code; everything through configuration (A.9).

---

## Phase Overview

| Phase | Name | Value shipped | Depends on |
|-------|------|---------------|------------|
| 0 | Cleanup + P0 fixes on current engine | Correct alerts TODAY, less noise, codebase ready | — |
| 1 | Foundations (events, registry, state, replay) | Invisible, enables everything | 0 |
| 2 | Constitution + My Rules | Biggest user-visible feature | 1 (partially parallel with 0) |
| 3 | Baseline confidence | Personalized thresholds go live | 1 |
| 4 | Detector migration (strangler) | Merges/splits/confidence scoring, alert quality | 1, 3 |
| 5 | Scores + Death Spiral | Tilt, Behavior Risk headline, guardian-critical | 4 |
| 6 | Position state + entry-time detection | Alerts BEFORE damage, concentration/all-in | 1 (webhook work), 4 |
| 7 | Evaluation + tuning | Detector metrics, weight calibration | 5, 6 live for weeks |

Phases 0 and 2 can overlap. 3 can start while 4 runs. 5–7 are strictly sequential after 4.

---

## Phase 0 — Cleanup + P0 Fixes (current engine, no architecture change)

Goal: today's engine emits correct, contextual, non-noisy alerts, and the codebase is clean before v2 work begins. Everything here is also needed by v2 — zero throwaway work.

### 0.1 Dead code audit + archive
Verified so far (Session 40 recon):
- `backend/app/services/risk_detector.py` — marked DEPRECATED in trade_tasks.py ("Phase 3 cutover"), no longer called from the pipeline. Audit remaining references (`api/risk.py`, `api/zerodha.py`, `cooldown_service.py`, `danger_zone_service.py`, `api/analytics.py`) — reroute or archive with them.
- `backend/app/services/behavioral_evaluator.py` — same deprecation note. Same treatment.
- `backend/app/services/behavioral_analysis_service.py` — legacy batch layer, still serving `/api/behavioral/patterns`. Decide: does anything in the UI still call this endpoint? If yes, keep until Phase 4 replaces it; if no, archive now.
- `src/` — patternDetector.ts already removed (S21). Verify `AlertContext.tsx` holds no residual client-side detection logic, only backend-driven display.
- Unused predictive-strip component (S36 leftover), any orphaned imports.
Process: full reference graph per file → reroute live callers → move dead files to `backend/app/services/_archive/` → run tests.

### 0.2 P0 bug fixes (master §4)
1. **`trigger_trade_id`** — populate on every alert (the triggering CompletedTrade id). Schema column exists; engine hardcodes None.
2. **`detected_at` = trade time**, never sync time. Kills the 5:05pm problem at the data layer.
3. **Bulk-sync routing rule** (master Q12): past-session alert → analytics only, never push/guardian; same-session stale (> configurable minutes) → in-app only. Implement in the notification dispatch in `trade_tasks.py`.
4. **Cross-instrument sizing** — convert `size_escalation`, `post_loss_recovery_bet` to risk-% of capital (or same-underlying qty where capital unknown); VERIFY `martingale_behaviour` same-underlying check uses `instrument_parser`.
5. **Trade context lists** — add to `consecutive_loss_streak`, `rapid_reentry`, `martingale_behaviour`, `size_escalation`, `post_loss_recovery_bet` (overtrading + overconfidence already done, commits `cd33514`, `0b558b7`).
6. **Config sweep** — any remaining inline constants in detectors → `trading_defaults.py`.

### 0.3 Schema migrations (numbered from 061)
- `severity` enum + `critical` value (Q25). Existing rows untouched.
- `detector_version` column on risk_alerts (A.2), default "1.0.0" for existing rows.
- Routing matrix honored in dispatch: severity × confidence → channel (§1B.7b). Confidence column on risk_alerts (nullable; deterministic detectors write data-quality-derived confidence later — Phase 1).

### 0.4 Acceptance
- Replay last 60 days of own trading data through patched engine; diff alerts before/after; every change explainable.
- Zero references to archived files; tests green; alert content shows trade lists + trigger trade in UI.

**Effort: ~4–6 working days.**

---

## Phase 1 — Foundations

Goal: the rails everything else runs on. No user-visible change.

### 1.1 BehaviorEvent
- Reuse/extend existing `models/behavioral_event.py` (already in codebase — audit its shape first) as the append-only event record: detector, version, severity, confidence, data_quality, evidence array (A.8), input snapshot ref (A.4 replayability), trade refs, timestamps.
- RiskAlert becomes the *notification* record; BehaviorEvent is the *evidence* record. Alerts reference events.

### 1.2 Detector Registry (A.1, A.10)
- One declarative registry: name, version, nature, disposition, trigger (entry/exit/session), consumes (primary state only — derived-state ban enforced here), produces, uses_baseline/constitution/position_state, notification_level, guardian_eligible.
- Engine iterates the registry; adding a detector = registry entry + one class.

### 1.3 State objects
- `session_state` (owner of session facts incl. peak_pnl per A.7 ownership table — write the table first), `user_state` (cross-session facts + derived scores, clearly split primary vs derived).
- Redis as derived cache with **rebuild-from-Postgres path** (mandatory: bulk sync, crash, eviction all trigger rebuild).
- Per-user serialization: partition event processing by broker_account_id (Celery routing key), ordering guard on event timestamps.

### 1.4 Data quality (A.6)
- Quality flag computed per event batch: GOOD / PARTIAL / UNKNOWN / INVALID (webhook gaps, duplicate postbacks, sync-vs-webhook divergence).
- Deterministic detectors: confidence = data quality mapping.

### 1.5 Replay harness (A.4)
- CLI: `replay --account X --from DATE --detector Y[@version]` → runs detectors over historical CompletedTrades, emits would-fire report, diffs against recorded alerts.
- This is the strangler's validation gate for every phase after.

### Acceptance
- State rebuild produces identical state from scratch vs incremental.
- Replay of 90 days matches current-engine alerts for unmigrated detectors (control test).

**Effort: ~2 weeks.**

---

## Phase 2 — Constitution + My Rules (user-visible flagship)

Can start UI work parallel with Phase 1.

### 2.1 Data
- Constitution object per user (§1C.2), migrated from existing UserProfile fields (single source of truth — Settings rule fields removed/redirected).
- `constitution_history` table (Q18): every version, who/when/what changed, override flags.
- Migration for existing users: prefill from current profile values, one-time review prompt.

### 2.2 Rules engine
- Single `constitution_violation` pattern_type, rule key in context (Q15).
- Severity ladder per rule: approaching (config ~80%) = caution → breached = danger → severe (config ~120%) = critical + guardian-eligible (§1C.4).
- Absorb existing early-warning service (70% P&L push) into the "approaching" tier — one code path.
- Suppression pairs live (notification-layer only, §1C.8): constitution beats consecutive_loss_streak / revenge / daily_overtrading / position_risk notifications.

### 2.3 Lock + override (§1C.3)
- Tighten = instant, always. Loosen = friction flow (warning + typed confirm) + `constitution_override` BehaviorEvent; loosening during market hours → effective next session.

### 2.4 Onboarding + My Rules tab
- 3 questions → generated constitution → ONE review screen (V3 wording) → done.
- My Rules top-level tab (Q13): Active Constitution, Today's Progress, Violations, Constitution Score (0–100 adherence, absorbs Weekly Discipline Score), Rule History, Guardian, Edit.
- Nav slot decision implementation only — no broader IA restructure.

### Acceptance
- Constitution violations fire correctly in replay of constructed scenarios; overrides logged; existing users migrated without data loss; Weekly Discipline Score removed from My Patterns without regression.

**Effort: ~2–2.5 weeks.**

---

## Phase 3 — Baseline Confidence

### 3.1 Compute (extends `learn_patterns`, same 18:15 IST Celery slot)
Per-metric records (Q23): value, confidence (f(sessions, trades, variance)), sample size, variance, last_updated. Metrics: avg/p95 daily trades, avg position risk %, avg hold times (win/loss), avg reentry delay, win rate, typical peak pnl, typical drawdown, per-hour performance (danger_hours already exists).

### 3.2 Apply
- Write to the `baseline` key `get_thresholds()` reads — **fixes the dead wiring**.
- Blend: LOW conf → defaults · MEDIUM → conf-weighted blend · HIGH → baseline. Band cutoffs in config.

### Acceptance
- Backtest: for 5+ real accounts, show effective thresholds vs defaults; scalper's overtrading threshold rises, positional trader's stays; no threshold ever crosses universal floors.

**Effort: ~1 week.**

---

## Phase 4 — Detector Migration (strangler)

One family at a time; each migrated detector: registry entry → replay validation → shadow mode (fires events, no notifications, compared against old engine for N sessions) → cutover → old detector retired.

Order (risk-ascending):
1. **Analytics-only moves** (zero notification risk): panic_exit, early_exit, opening_trap, rapid_reentry → disposition analytics, severity info.
2. **Merges**: rapid_flip + options_direction_confusion → `direction_instability` (L1/L2/L3); iv_crush + premium_destruction → `premium_loss_event` (40/60/80, moneyness/expiry-adjusted).
3. **Splits**: overtrading → burst + `daily_overtrading`; excess_exposure → `position_risk` (with All-In Bet presentation tier + emotional multiplier).
4. **Confidence-scored rebuilds**: revenge_trade (signal stacking, relative importance), fomo_entry, winning_streak_overconfidence.
5. **Remaining keeps**: consecutive_loss_streak (dual counters), size_escalation, martingale, recovery_bet, no_stoploss, profit_giveaway (capital-scaled floor), expiry_day_overtrading, MIS panic (+profitable suppression), premium_avg_down (+same-direction gate), session_meltdown.
6. **New cheap detectors**: same_symbol_obsession, time_of_day_bias (danger_hours already computed).
7. **Dedup engine v2**: stateful re-arm, escalation bypass, cross-pattern suppression matrix (enumerate Q4 pairs here).
8. Retire `behavioral_analysis_service.py` (archive) once analytics endpoints read BehaviorEvents.

### Acceptance per detector
- Replay precision/recall vs hand-labeled expectations (A.3 acceptance criteria written BEFORE migration); shadow-mode divergence explained; then cutover.

**Effort: ~3–4 weeks (family by family, shippable increments).**

---

## Phase 5 — Scores + Death Spiral

1. Driver scores (Tilt first, then Risk/Discipline/Strategy): Σ(importance × confidence × multiplier) → exponential decay → clamp; no recency term; no positive credits (V4).
2. Behavior Risk headline: dominant-driver weighted, discipline inverted (V4).
3. Display: Dashboard coarse band ("Behavior Risk: High") + Analytics detail with contributors (Q10). Hysteresis on any threshold display/alerting.
4. **Death Spiral** (§1D.2 final): Warning in-app · Danger push · Critical push+guardian; Critical = 3+ independent domains + continued escalation (new position after breach). Time-compression weighting.
5. Guardian critical flow through Gupshup template (respect 1–3/month budget with hard counter).

### Acceptance
- Replay full history: tilt trajectories plotted for known bad days (e.g., the 558% day); death spiral critical fires ≤ a handful of times per year of data per active trader; zero guardian fires on "trader stopped" scenarios.

**Effort: ~2 weeks.**

---

## Phase 6 — Position State + Entry-Time Detection

1. Webhook pipeline extension: consume order-fill events on ENTRY (currently only position-close triggers engine); optional SL-modify events later.
2. `position_state`: open risk, concentration by underlying, exposure by type; rebuilt from Zerodha positions API on sync.
3. Entry-time detectors go live: position_risk/all-in AT ENTRY, revenge/cooldown at entry, portfolio_concentration (2+ underlyings rule), meltdown with unrealized MTM.
4. Restricted-windows constitution rule becomes real-time.

### Acceptance
- Entry alerts arrive while position open (latency < seconds in webhook path); concentration never fires single-position; MTM meltdown matches broker P&L within tolerance.

**Effort: ~2–3 weeks. Highest technical risk phase (ordering, partial fills, MTM accuracy).**

---

## Phase 7 — Evaluation + Tuning

1. Detector evaluation dashboard (A.5): per-detector precision proxy, dismiss rate, confidence distribution, fire counts (admin panel section).
2. Weight/threshold calibration from production data (the V1 rule: tune AFTER real users).
3. Win Rate Collapse + Strategy Breakdown as analytics (binomial-tested, profit-factor aware) feeding Strategy Health driver.
4. Alert-fatigue decisions (auto-mute candidates) — only now, with dismiss data in hand.
5. Docs: rewrite `16_behavioral_patterns_complete.md` from the registry (auto-generate).

**Effort: ~1–2 weeks + ongoing.**

---

## Deferred (explicitly out of plan)
- Live-price rule subsystem (premium-decay exit, profit-target stop) — §1C.9
- Positive behavior credits in scores — v1.1
- Broader nav/IA restructure — separate discussion
- Kafka / 5-lakh-user scaling — revisit at real load
- AI coach consumption of states — after Phase 5 data exists

## Standing risks
1. **Webhook completeness** (Phase 6) — Zerodha postback gaps corrupt position_state → rebuild path + data-quality flags are the mitigation, built in Phase 1 deliberately.
2. **Shadow-mode duration temptation** — cutting it short to ship faster reintroduces the exact false-positive problem v2 exists to kill. Minimum N=10 sessions per detector.
3. **Constitution migration** — existing users' Settings values move; a bad migration silently changes their thresholds. Migration test against production snapshot mandatory.

---

*Total: ~13–16 working weeks end-to-end, but Phase 0 ships value in week 1 and every phase is independently shippable.*
