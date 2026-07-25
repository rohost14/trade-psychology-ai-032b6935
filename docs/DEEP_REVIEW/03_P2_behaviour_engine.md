# P2 — Behaviour Engine (findings)

> Scope (read): `services/behavior_engine.py` (orchestration + detectors), `services/detector_registry.py`,
> `services/behavioral_analysis_service.py` (surface), `services/constitution_service.py`,
> `services/behavioral_baseline_service.py` vs `services/baseline_service.py`, `services/behavior_scores_service.py`
> (surface), `core/trading_defaults.py` (surface). Cross-checked FE consumers + FK cascades.
> **Findings-only.**

## Architecture as-verified
`BehaviorEngine.analyze()` runs **once per CompletedTrade** (live per-fill path only — batch/EOD does **not** re-run it). It: loads context in ~4 shared queries → iterates the **declarative DetectorRegistry** (28 specs) → applies feature-flags (off/shadow/canary/on, migration 068) → strategy-leg + constitution-breach **suppression** (recorded as evidence, notification withheld) → writes `RiskAlert` (notifiable) + `BehaviorEvent` (every detection, deterministic idempotency key) → updates cumulative session risk score/state. This is **genuinely well-built**: pure detectors, externalised thresholds, per-detector versioning, signal-stacking confidence, shadow `SessionState` parity metric. Credit noted.

---

## 🟠 P1

### E1 · Dual detection engine still live — "single source of truth" is false · correctness/dead-code
- **Where:** `services/behavioral_analysis_service.py` (1,887 LOC) defines a **second, independent** pattern set (`RevengeTradingPattern`, `EmotionalExitPattern`, `NoCooldownPattern`, `AfterProfitOverconfidencePattern`, `StopLossDisciplinePattern`, `OvertradingPattern`, `MartingaleBehaviorPattern`, `InconsistentSizingPattern`, `TimeOfDayPattern`, …) that recomputes patterns from **raw `Trade`s**. It is served **live** by `api/behavioral.py` (`/api/behavioral/analysis`, `/patterns`) and **consumed by the frontend** — `src/components/analytics/ExportReportButton.tsx:93` calls `/api/behavioral/analysis` for the exported report.
- **Why it matters:** two engines with **different logic + thresholds + input granularity** (raw Trades vs CompletedTrades) produce potentially **contradictory** behavioural findings. In-app live alerts come from `BehaviorEngine` v2; the **exported report's behavioural analysis comes from the legacy engine**. `behavior_engine.py`'s docstring ("Single source of truth … backend is the only engine") and CLAUDE.md's "dual-engine elimination DONE (S21)" are **both inaccurate** — the elimination stopped at the real-time path and left the on-demand API on the old engine.
- **Fix:** retire `behavioral_analysis_service` and back `/api/behavioral/*` with `BehaviorEngine`/stored `RiskAlert`+`BehaviorEvent` data, or explicitly document why two exist. → ledger (D10 upgraded: confirmed live, not "suspected").

### E2 · Alert→trade linkage is severed every EOD (elevation of P1-M6) · correctness/data-integrity
- **Chain:** live `PositionLedgerService.build_completed_trade_on_close` creates `CompletedTrade` with a **random UUID**; `BehaviorEngine` tags each `RiskAlert.trigger_completed_trade_id` + `BehaviorEvent.trigger_completed_trade_id` to that id; at EOD the **batch FIFO deletes+recreates** the window's CompletedTrades with a **deterministic `_stable_ct_id`** (different id); the FK is **`ON DELETE SET NULL`** (verified in `models/risk_alert.py:30`, `models/behavior_event.py:51`).
- **Result:** at EOD sync every **same-day** alert/event has its `trigger_completed_trade_id` **set to NULL**. The system's stated invariant — *"every RiskAlert + BehaviorEvent is tagged `trigger_completed_trade_id`"* (CLAUDE.md) — **breaks nightly**. Any My Record / analytics view that joins alert→trade loses that day's linkage after 15:35 IST.
- **Fix:** make the live builder use `_stable_ct_id` (same root cause + fix as P1-M6) so the id is stable across the live→batch handoff. Add a test asserting the tag survives an EOD recompute.

---

## 🟡 P2

### E3 · `analyze()` swallows ALL exceptions → silent detection loss · correctness/observability
`behavior_engine.py:348` wraps the whole method in `try/except` returning an **empty** `DetectionResult` (no alerts, no events, no score move) on any failure, logging ERROR only. Per-detector failures are caught individually (line 560, good), but a **context-load** failure (profile, session, strategy lookup) drops the entire trade's detection **silently**. Combined with **P0-F2** (prod logging unwired + admin error-feed dead), such losses are invisible in production. **Fix:** increment a failure counter (`metrics.incr("engine_analyze_failed")`) + surface on the engine-metrics admin page; consider a DLQ/retry for context-load failures.

### E4 · `behavioral_analysis_service` is dead-weight-or-dual — decide · dead-code
See E1. 1,887 LOC of a parallel engine. Retire or document. → ledger D10.

### E5 · (resolves D9) baseline services are **not** duplicates · quality
`services/baseline_service.py` = profit-factor / metric-window **helpers** (used by `ai_personalization_service`). `services/behavioral_baseline_service.py` = per-user **percentile behavioural baselines** (used by profile/zerodha/behavioral). Different concerns — **not a dup**. D9 closed as "distinct"; optional rename for clarity.

---

## ⚪ P3
- **E6** `ConstitutionService.apply_pending_if_due` calls `await db.commit()` and is invoked from `BehaviorEngine._load_context` (line 394) — committing the shared task/request session as a side effect of a **read** during detection is a smell (premature partial commit if anything is mid-flight). Low risk here (runs before detectors add anything). Consider a dedicated session or defer.
- **E7** `ConstitutionService.apply_changes` does no server-side **value** validation (negative/absurd limits accepted). Verify the Pydantic schema in `api/profile.py` enforces bounds (P6).
- **E8** `overtrading_burst` returns on the first burst match and never also emits the `daily_overtrading` signal in the same call — a heavy day that also had a 30-min burst reports only the burst. Intentional per comments, but the daily signal is skipped that trade.
- **E9** Detector correctness inherits P1 data issues: streak/size/session-P&L detectors read `CompletedTrade.realized_pnl` + `total_quantity`, so **product-mixing (P1-M1)**, **missing flip rounds (P1-M2)**, and **wrong MCX multiplier (P1-M5)** propagate into wrong pattern firing. No new bug in the detectors themselves — they're clean — but their inputs carry the P1 defects.

## ✅ Solid (credit)
Declarative registry (add-a-detector = one spec) · deterministic idempotency keys (retry/bulk-safe) · feature-flag shadow/canary rollout · strategy-leg + constitution-breach suppression that records evidence but withholds notification · per-detector semver on every alert · confidence = min(detector, data-quality) · signal-stacking with an alert gate · fully externalised thresholds (research defaults + user constitution) · shadow `SessionState` fold-vs-recompute parity counter. Constitution gate (tighten-instant / loosen-friction / market-hours→next-session / full history) is correct and well-reasoned.

## For P14 (QA)
Assert: alert `trigger_completed_trade_id` survives an EOD recompute (E2) · `/api/behavioral/*` vs live alerts agree or the legacy engine is gone (E1) · engine context-load failure increments a visible counter (E3) · constitution loosen→next-session timing · per-detector shadow→on parity.
