# Deep Code Review — Master Plan

> **Objective:** review **every file** in the codebase (frontend + backend + DB + docs), effectively
> line-by-line, for: correctness, code quality, feature-intent match, security, bugs, scalability to
> **10k concurrent users in production**, and dead/outdated code+docs.
>
> **Rules of this review:**
> - **Findings-only.** No fixes without explicit go-ahead (per the project's non-negotiable rule). Each
>   phase produces findings; fixes happen in later, separately-approved passes.
> - **Do NOT trust docs.** Every claim verified against code. Docs get their own audit pass; when a doc
>   misleads, it's flagged. A running **dead-code / dead-doc ledger** is kept throughout.
> - **Honest depth.** "Line-by-line" means each significant file is actually read + reasoned about.
>   Generated/vendored files (shadcn `ui/*`, lockfiles) get a shallow "is it modified/used" check, not a
>   line audit — flagged as such, not pretended.

---

## Method — vertical slices + cross-cutting passes
Reviewing by **vertical slice** (a feature end-to-end: frontend → API → services → models → DB/migrations
→ tests → connectivity) catches logic *and* wiring/mapping issues together — matching the "start at an
index, follow every reference" approach. Interleaved with **cross-cutting passes** (infra, security, scale)
that don't belong to one feature. Ordered **risk-first** (money + security + core engine before cosmetics).

## Output structure (`docs/DEEP_REVIEW/`)
- `00_REVIEW_PLAN.md` — this plan.
- `NN_<phase>.md` — one findings doc per phase (committed as it completes).
- `DEAD_CODE_LEDGER.md` — running list of dead/orphaned/outdated code + docs (append-only).
- `99_SYNTHESIS.md` — final: 10k-prod-readiness verdict + top risks + prioritized fix backlog.

**Finding format (every finding):** `file:line · SEVERITY · category · one-line problem · why it matters · suggested fix`.
- **Severity:** P0 (data loss / security / money-wrong / crash) · P1 (breaks at scale or common path) · P2 (quality/maintainability) · P3 (nit).
- **Category:** correctness · security · scale · dead-code · quality · feature-gap · doc-stale.

---

## Phases (risk-first; each = a committed findings doc)

- **P0 · Entry & map** — `main.py`, `core/config`, `deps`, routing, middleware, DB engine/session, celery/beat wiring, redis pools, env surface. Build the authoritative architecture + route map (ground truth for everything after).
- **P1 · Money math (CRITICAL)** — `pnl_calculator`, `position_ledger_service`, `trade_sync_service`, CompletedTrade/FIFO build, `completed_trade_feature`, multipliers, MCX specs. Every ₹ must be correct; idempotency; raw-P&L rule.
- **P2 · Behaviour engine** — `behavior_engine` (2.6k LOC), `detector_registry`, every detector, `behavioral_baseline_service`/`baseline_service` (dup?), `behavior_scores_service`, `constitution_service`, thresholds. Correctness + the `behavioral_analysis_service` legacy question.
- **P3 · Real-time & scale** — `webhooks`, `tasks/*` (trade/alert/report/reconciliation/intent/retention/watchdog — incl. the sequential all-account loops), `event_bus`, `websocket`, `price_stream_service`, `order_stream_service`. Correctness + the 10k bottlenecks (B1–B7 from `SCALABILITY_REVIEW_10K.md`).
- **P4 · Auth & security** — user auth (`zerodha.py`, `zerodha_auth_service`, `deps`), admin auth (all `api/admin/*`, `session_registry`, `admin_state`), impersonation middleware, encryption/Fernet, `rate_limiter`, secrets handling, CORS, cookies. Threat-model each surface.
- **P5 · Analytics** — `api/analytics.py` (3.2k LOC — the biggest file), `analytics_service`, `order_analytics_service`, `habits_service`, `pattern_prediction_service`, `ai_personalization_service`, + FE analytics components (tabs, cards, charts).
- **P6 · Remaining API + services** — profile, settings, alerts, journal, reports, coach/`ai_service`/`rag_service`, notifications/push/whatsapp/email, constitution, cooldown, my_record, goals, danger_zone, account_data, admin_settings, instrument/margin/gtt/circuit_breaker/token_manager/etc.
- **P7 · Frontend** — pages, `contexts` (Broker/WebSocket/Alert/AdminAuth), `hooks`, `lib` (api/adminApi/guestMode/impersonation/formatters/…), components. State mgmt, error/loading consistency, api mapping, perf, guest-mode fidelity, bundle.
- **P8 · DB & migrations** — 36 models, all 74 migrations (order, idempotency, indexes, constraints, cascades), ghost columns (`quality_score`, `outcome`), data integrity, partitioning.
- **P9 · Config / ops / infra** — env vars, logging, metrics, deploy config (Procfile/Docker/hosting), monitoring, backups. Prod-readiness of the runtime.
- **P10 · Docs audit** — every doc in `docs/`, `docsreview*/`, root `*.md` — mark correct / stale / wrong / dead vs the code. Feed the dead-doc ledger.
- **P11 · Synthesis** — consolidated 10k-prod-readiness verdict, ranked risk register, prioritized fix backlog (maps into `PRODUCTION_READINESS_CHECKLIST.md`).

**Scope notes:** `_archive/*` = logged as dead, not line-audited. `components/ui/*` (shadcn, ~53) = shallow used/modified check. `scroll-loss-experience/`, `design_v2/`, `prototype_design/` = confirmed-dead check only (candidates for removal), not line-audited unless asked.

## Cadence & expectations
This is a **multi-turn, multi-day effort** (≈400 code files + 74 migrations + docs). Each phase is committed as it completes, so nothing is lost across sessions; progress is tracked in memory. You review findings between phases; I fix only on your go-ahead.

## "Will it work for 10k in production?" — threaded through every phase
Each phase explicitly asks: *does this hold at 10k concurrent?* (per-request cost, N+1, unbounded loops, connection budgets, sync-in-async, memory, idempotency, backpressure). Scale findings roll up into P11 + the scalability doc.
