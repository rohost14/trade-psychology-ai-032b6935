# Codebase Audit

> Full-codebase review (2026-07-25). **Method (honest):** enumerated *every* file (183 backend `.py`
> / ~193 frontend `.ts/.tsx` / 72 migrations), deep-read the architecturally-significant modules,
> and grep-verified specific claims (mounted routers, import counts, dead code). I did **not** read
> every line of all 376 files in one pass — but every directory and file group is inventoried below,
> and every *finding* is code-grounded (verified), not doc-based.

---

## 1. Scale of the codebase
| Area | Files | LOC |
|---|---|---|
| `backend/app/services` | 49 | 22,309 |
| `backend/app/api` (+ `api/admin` 17) | 29 + 17 | 12,996 + 3,501 |
| `backend/app/tasks` | 15 | 5,282 |
| `backend/app/core` | 16 | 2,877 |
| `backend/app/models` | 36 | 2,337 |
| `backend/app/schemas` | 15 | 789 |
| **Backend total** (excl archive) | **183** | **~50,770** |
| `src/` (pages 16, admin 12, components ~56, ui 53, lib 20, hooks 12, contexts 4) | ~193 | ~28,400 |
| Migrations | 72 | — |

This is a **large, mature codebase** — not a prototype. That's the headline: it's substantial and mostly coherent, but it carries **accumulated dead weight** from archived features and rapid iteration.

---

## 1a. Cleanup performed + connectivity verified (2026-07-25)
**Cleanup (git mv → `_archive/`, nothing deleted; verified safe before each move):**
- Archived 3 dead routers (`portfolio_radar`, `guardrails`, `portfolio_chat`) + removed their `main.py` mounts. `personalization` **KEPT** (found live consumers — see §2). Services untouched (shared with Celery).
- Archived `vix_service.py` (0 imports).
- Moved 6 root one-off scripts (`build_dashboard.py`, `patch.py`, `redesign_script.py`, `restore_scale.py`, `upgrade.py`, `upgrade_html.py`) → `_archive/root_oneoff_scripts/`.

**Verification after cleanup (all green):**
- Backend **boots** — 235 → **224 routes** (−11 dead endpoints); imports resolve; no lingering refs to archived modules.
- Frontend **typecheck** passes (imports intact).
- **Frontend→Backend mapping diff:** 108 live FE `api.*` paths vs 204 BE routes → **0 broken mappings.** The 10 "unmatched" were all `guestMode.ts` mock strings (archived shield/portfolio-radar) or non-calls — no live call hits a missing endpoint.
- **Left intentionally:** `design_v2/`, `prototype_design/`, `scroll-loss-experience/`, `docsreview*/` dirs (docs/separate app — user decision), and `guestMode.ts` stale mocks for archived features (harmless; guest mode never hits the backend, and touching it is risky per the `{}` catch-all crash history).

---

## 2. Findings by severity

### ✅ RESOLVED 2026-07-25 — orphaned routers archived (with a correction)
Original claim: 4 archived-feature routers were dead. **On verification, only 3 were** — `personalization` is **LIVE** (called by `PredictiveContextStrip` on Dashboard + `InsightsTab` in Settings; the *page* was archived, the *endpoints* are used). **Kept.** *(This is exactly the "archived page but live API" mapping nuance — caught before touching it.)*
- **Archived + unmounted** (only `main.py` imported them; NO live frontend caller): `portfolio_radar`, `guardrails`, `portfolio_chat` → `backend/app/api/_archive/`.
- **NOT touched:** their **services** (`portfolio_concentration_service`, `position_metrics_service`, `gtt_service`, `ai_personalization_service`, `zerodha_service`) — all shared with **live Celery tasks** (`portfolio_radar_tasks`, `intent_tasks`, `trade_tasks`). Only the unused HTTP routers were removed.
- **Follow-up (not done):** `portfolio_radar_tasks` (Celery) still runs though its frontend is gone — decide whether to retire it (separate task; touching Celery beat is riskier).

### ✅ RESOLVED 2026-07-25 — dead service archived
- **`services/vix_service.py`** — 0 imports (VIX rejected). **Archived** → `backend/app/services/_archive/`.

### 🟠 Medium — Duplicate / possibly-legacy services (49 services is a lot)
- **`baseline_service.py` (1 importer)** vs **`behavioral_baseline_service.py` (4 importers)** — two baseline services; the first is barely referenced → likely legacy dup. Verify + consolidate.
- **`behavioral_analysis_service.py` (1,887 LOC, 2 importers)** vs **`behavior_engine.py` (2,653 LOC)** — the engine was unified in "Behavioral Engine v2" (dual-engine elimination, S21). Confirm `behavioral_analysis_service` isn't the old engine lingering; if it's still a live dependency, document *why* two exist.
- Alert stack sprawl: `alert_service` · `alert_checkpoint_service` · `early_warning_service` · `notification_rate_limiter` · `push_notification_service` — cohesive but worth a dependency map to ensure no overlap.

### 🟠 Medium — Complexity hotspots (maintainability, not bugs)
- **`api/analytics.py` — 3,239 LOC, 25+ endpoints in one file.** Hard to navigate; a merge-conflict magnet. → split into sub-routers (overview/edge/behaviour/habits/sessions) mounted under `/api/analytics`.
- `services/behavior_engine.py` (2,653) — core + inherently complex; cohesive, leave but keep well-tested.
- `services/behavioral_analysis_service.py` (1,887) — see duplicate note.
- `tasks/trade_tasks.py` (1,451), `services/trade_sync_service.py` (1,242), `api/zerodha.py` (1,170), `services/daily_reports_service.py` (1,027).
- Frontend: `Welcome.tsx` (701), `Chat.tsx` (696), `Dashboard.tsx` (689), `AdminUserDetail.tsx` (680), `OnboardingWizard.tsx` (667) — large but page-level (acceptable).

### 🟡 Low — Repository hygiene / root cruft
Root directory holds **one-off scripts and dead directories** that don't belong in a production repo (no secrets found in the scripts — verified — but they're clutter and confusing):
- Scripts: `build_dashboard.py`, `patch.py`, `redesign_script.py`, `restore_scale.py`, `upgrade.py`, `upgrade_html.py`.
- Dead dirs: `design_v2/` (DEAD per project rules), `prototype_design/`, `scroll-loss-experience/` (separate Next.js app), `docsreviewscreens/`, `docsreviewsessions/`.
- Stray root docs: `AUDIT_FINDINGS.md`, `DESIGN.md`.
→ **Action:** move to `_archive/` or delete (they're already git-tracked history). Reduces confusion + eslint/scan noise.

### 🟡 Low — TODO/FIXME debt
~62 TODO/FIXME/HACK markers across source (excl archive/tests). None critical spotted; the notable one is `whatsapp_service` (Gupshup not active — Meta approval pending, already known). → triage into the backlog.

---

## 3. Architecture map (verified)
**Request/data flow (live path):**
```
Zerodha postback → /api/webhooks/zerodha/postback → Celery (process_webhook_trade)
  → TradeSyncService.upsert_trade → PositionLedger (FIFO) → CompletedTrade + features
  → BehaviorEngine (22 detectors) → RiskAlert + BehaviorEvent (tagged trigger_completed_trade_id)
  → event_bus (Redis Streams) → WebSocket → browser  +  push/WhatsApp (retried task)
```
**Market data:** ONE shared `KiteTicker` (`price_stream_service`) → union of open-position instruments → fans out to all WS. (Not per-user — good.)

**Layers:**
- `api/` — FastAPI routers (auth via `deps.get_current_broker_account_id`/`_verified`). `api/admin/` — separate JWT (cookie), superadmin roles.
- `services/` — business logic (engine, sync, analytics, ai, pnl, ledger, comms, admin_settings…).
- `models/` — SQLAlchemy (36); `schemas/` — Pydantic.
- `tasks/` — Celery (postback processing, reports, reconciliation, intent, retention, watchdog).
- `core/` — config, database, celery_app, event_bus, redis_pool, metrics, rate_limiter, admin_state, error_feed, trading_defaults, logging.
- Frontend: `pages/` (+ `pages/admin/`), `components/` (analytics/dashboard/patterns/settings/onboarding/ui), `contexts/` (Broker/WebSocket/Alert/AdminAuth), `hooks/`, `lib/` (api, adminApi, guestMode, impersonation, support, formatters…).

---

## 4. Per-area notes
- **`api/`** — well-structured per-domain routers. Biggest risk = `analytics.py` size + the 4 orphaned routers (§2). Auth deps are clean (read vs verified). Impersonation read-only middleware in `main.py`.
- **`services/`** — the heart; 49 files, some dead/dup (§2). Engine, ledger, sync, pnl are the critical path — keep well-tested (engine has 32 tests; sync/ledger less).
- **`models/`** — 36 tables, indexed well. Known ghost columns: `CompletedTrade.quality_score` (populated by nothing — anything scoring on it is a constant), `risk_alert.outcome` (never written — needs manual input nobody gives; derive instead).
- **`tasks/`** — mostly sound; **the sequential all-account batch loops** (intent re-learn, reconcile, EOD) are the scale bottleneck (see `SCALABILITY_REVIEW_10K.md`). Some tasks already fan out (weekly summary) — copy that.
- **`core/`** — solid infra. Two rate-limit files (`rate_limit.py` + `rate_limiter.py`) — check for dup. Redis pooling + Upstash-free-tier optimizations throughout (need paid tier at scale).
- **Frontend** — pages consistent; error/loading now standardized (useFetch/ErrorState/skeletons) though rollout is partial (Analytics + the 3 misleading-empty fixes done; other pages still hand-roll). `components/ui/` (53) = shadcn primitives (some generated — fine).

---

## 5. Security notes (from this pass)
- Admin auth hardened (authz, 2FA lockout, TOTP replay, const-time OTP, IP allowlist, httpOnly cookie, session-epoch). ✅
- Impersonation is read-only-enforced by a central middleware. ✅
- Per-user Zerodha secrets Fernet-encrypted; `ENCRYPTION_KEY` is a single point of failure (back it up).
- Orphaned mounted routers (§2) = unnecessary surface — close them.
- Root one-off scripts contain **no secrets** (verified) — but remove them.
- No formal security review / pen test yet (see readiness checklist §F).

---

## 6. Recommended cleanup (prioritized, all low-risk)
1. **Archive + unmount** the 4 dead routers (portfolio_radar, personalization, guardrails, portfolio_chat) + their services. *(Confirm no shared deps first.)*
2. **Archive** `vix_service.py` (0 imports) + consolidate the duplicate baseline services.
3. **Split `analytics.py`** into sub-routers (maintainability).
4. **Move root cruft** (6 scripts + 4 dead dirs + stray docs) into `_archive/` or delete.
5. **Document** `behavioral_analysis_service` vs `behavior_engine` (why both) or retire the legacy one.
6. Triage the ~62 TODOs into the backlog.

*None of this is a rewrite — it's dead-weight removal + one file split. The core architecture is sound.*

---

## 7. Bottom line
- **The codebase is large and fundamentally sound** — good separation (api/services/models/tasks/core), a well-designed real-time path, hardened admin, indexed DB.
- **It carries dead weight:** 4 orphaned-but-mounted routers, ≥1 fully-dead service, duplicate services, root cruft — accumulated from fast iteration + feature archival that stopped at the frontend.
- **Biggest structural smell:** `analytics.py` at 3,239 LOC.
- **No new critical bugs surfaced** in this pass; the known risks (scale sizing, live-validation gap, dead surface) are already tracked in the companion docs.
- **Cleanup is low-risk and worth doing before launch** (smaller attack surface, easier maintenance), but **not a blocker** — none of it breaks the running product.

*Companions: `SCALABILITY_REVIEW_10K.md` (scale) · `PRODUCTION_READINESS_CHECKLIST.md` (ship gate) · `PLATFORM_ROADMAP_AUTH_PAYMENTS.md` (feature gaps).*
