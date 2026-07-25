# Deep Code Review — Master Plan

> **Objective:** review **every single file inside `D:\trade-psychology-ai\`** — not just `src/` and
> `backend/app/`, but the *entire* repo: root configs, build/tooling, Docker/deploy, env, migrations,
> scripts, test suites, PWA assets, CI/agents, docs, archived + separate sub-apps. Effectively
> **line-by-line**, for: correctness, code quality, feature-intent match, **all references / imports /
> wiring**, **all external connections** (Postgres/Supabase, Redis/Upstash, Celery, Zerodha OAuth+ticker+
> postback, OpenRouter, OpenAI embeddings, Gupshup/Twilio, Web-Push/VAPID, SMTP, Sentry, WebSocket), **all
> data flows end-to-end**, security risks, bugs, scalability to **10k concurrent users in production**, and
> dead/outdated code + docs. Ends with a **QA regression + performance/load test plan** and a
> **"what's left for 100% production readiness + next steps"** section.
>
> **Rules of this review:**
> - **Findings-only.** No fixes without explicit go-ahead (per the project's non-negotiable rule). Each
>   phase produces findings; fixes happen in later, separately-approved passes.
> - **Do NOT trust docs.** Every claim verified against code. Docs get their own audit pass; when a doc
>   misleads, it's flagged. A running **dead-code / dead-doc ledger** is kept throughout.
> - **Full coverage, honest depth.** Per your call: **every file** is inventoried and reviewed, including
>   archives, the separate Next.js app, generated UI primitives, and one-off scripts. "Line-by-line" means
>   each file is actually read + reasoned about. Where a file is generated/vendored (lockfiles, `ui/*`), it
>   still gets a "used / modified / safe?" check — that check is stated, not skipped and not faked.
> - **More than code.** References, API contracts, DB schema, Redis keyspaces, external-service config,
>   env surface, and every runtime flow are traced — not only the source lines.

---

## 0. Scope — the complete repo inventory (ground truth, counted 2026-07-25)

Everything below is **in scope**. Counts exclude `node_modules/`, `.venv/`, `venv/`, `dist/`, `.git/`,
`__pycache__/`, `.pytest_cache/` (build/vendor/artifacts — verified present, not reviewed except their
*config*).

| Area | Path | Files | In-scope treatment |
|---|---|---|---|
| Backend app | `backend/app/{api,core,services,tasks,models,schemas,utils}` | 188 `.py` (+9 `_archive`) | full line audit |
| Backend migrations | `backend/migrations/*.sql` | 72 | full audit (order, idempotency, indexes, constraints) |
| Backend scripts | `backend/scripts/**` (db, debug, validate, smoke_*) | 73 | full audit — classify keep / dev-only / dead |
| Backend tests | `backend/tests/*.py` | 29 | full audit — coverage + correctness of the tests themselves |
| Backend config/deploy | `backend/{Dockerfile,Procfile,pytest.ini,requirements.txt,.env.example,.env,.dockerignore,.gitignore}` | 8 | full audit |
| Frontend app | `src/{pages,components,contexts,hooks,lib,data,types,test}` + `App.tsx`/`main.tsx`/`index.css`/`vite-env.d.ts` | 230 `.ts/.tsx` (incl. 37 `_archive`) | full line audit |
| Root build/tooling | `package.json`, `package-lock.json`, `vite.config.ts`, `vitest.config.ts`, `tsconfig{,.app,.node}.json`, `tailwind.config.ts`, `postcss.config.js`, `eslint.config.js`, `components.json`, `index.html`, `skills-lock.json` | 12 | full audit |
| PWA / public | `public/{sw.js,manifest.json,robots.txt,icons,fonts,placeholder.svg,favicon}` | 9 | full audit (sw.js = code; rest = asset check) |
| CI / agents | `.github/agents/full-stack-auditor.agent.md`, `.agents/`, `.claude/` | — | audit (what runs, what it can touch) |
| Root env / dotfiles | `.env`, `.env.example`, `.gitignore` | 3 | audit (secrets hygiene, ignore coverage) |
| Docs (all) | `docs/**` + `docsreview/` + `docsreviewscreens/` + `docsreviewsessions/` + root `*.md` | 133 md + `README.md`/`CLAUDE.md`/`AUDIT_FINDINGS.md`/`DESIGN.md` | full audit vs code → stale/wrong/dead |
| Archived code | `_archive/` (root), `backend/app/**/_archive`, `src/**/_archive` | 9 + 37 + root | confirm-dead + line-scan for anything still referenced |
| Separate / dead trees | `scroll-loss-experience/` (12, separate Next.js app), `design_v2/` (14), `prototype_design/` (19) | 45 | full review per your "everything" call; flag for removal |
| Vendor/artifacts (config only) | `node_modules/`, `.venv/`, `venv/`, `dist/`, `.pytest_cache/` | — | **not** line-reviewed; their *generators/config* are |

**Headline:** ~188 backend + ~230 frontend source files, 72 migrations, 73 scripts, 29+ tests, 133 docs,
12 build configs, plus 3 dead/separate trees and archives. This is a large mature codebase — full coverage
is a multi-day, multi-phase effort (see cadence).

---

## Method — vertical slices + cross-cutting passes
Reviewing by **vertical slice** (a feature end-to-end: frontend → API → services → models → DB/migrations
→ tests → connectivity) catches logic *and* wiring/mapping issues together — matching the "start at an
index, follow every reference" approach. Interleaved with **cross-cutting passes** (infra, external
connections, security, scale, build/ops) that don't belong to one feature. Ordered **risk-first** (money +
security + core engine before cosmetics). Every phase records **references** (who imports/calls this, what
it depends on) so the final map is a real call/connection graph, not a file list.

## Output structure (`docs/DEEP_REVIEW/`)
- `00_REVIEW_PLAN.md` — this plan.
- `NN_<phase>.md` — one findings doc per phase (committed as it completes).
- `DEAD_CODE_LEDGER.md` — running list of dead/orphaned/outdated code + docs (append-only).
- `CONNECTIONS_AND_FLOWS.md` — the traced external-connection + data-flow map (built during P0/P9, referenced by all).
- `99_SYNTHESIS.md` — final: 10k-prod-readiness verdict + ranked risk register + QA/perf plan + prioritized fix backlog + **100%-readiness pending list** + **next steps**.

**Finding format (every finding):** `file:line · SEVERITY · category · one-line problem · why it matters · suggested fix`.
- **Severity:** P0 (data loss / security / money-wrong / crash) · P1 (breaks at scale or common path) · P2 (quality/maintainability) · P3 (nit).
- **Category:** correctness · security · scale · dead-code · quality · feature-gap · doc-stale · config · flow.

---

## External connections & data flows — traced end-to-end (coverage checklist)

Every integration below is traced **config → client init → call sites → failure/retry behaviour →
prod-readiness** (built into `CONNECTIONS_AND_FLOWS.md`, deep-dived in **P9**, but touched in every phase
that uses it). None may be left "assumed working".

**External connections:**
- **Postgres / Supabase** — `DATABASE_URL`, async engine + PgBouncer transaction-pooler settings (`statement_cache_size=0`, pool 5+10), `get_db` lifecycle, per-worker connection budget at scale.
- **Redis / Upstash** — `REDIS_URL` (`rediss://`), sync + async pools (`redis_pool.py`), Streams event bus, admin_state, rate limiter, caches, nonces; free-tier command budget vs 10k.
- **Celery** — broker/back-end wiring (`celery_app.py`), beat schedule, queues/routing, worker concurrency, task retries + DLQ.
- **Zerodha KiteConnect** — OAuth login/callback, per-user api_key/secret (Fernet), daily token expiry, postback webhook, shared KiteTicker (market-data account), order stream, GTT/margin calls.
- **OpenRouter** — LLM calls (coach, personalization re-learn, reports); model overrides via `admin_settings`; rate-limit + cost under batch + live.
- **OpenAI** — embeddings for RAG (`OPENAI_API_KEY`).
- **Gupshup WhatsApp** (+ legacy **Twilio** vestiges) — templates, kill-switch gate, Meta-approval-blocked state.
- **Web Push / VAPID** — `sw.js`, subscription storage, `push_notification_service`, kill-switch.
- **SMTP** — admin OTP + watchdog emails only.
- **Sentry** — init, `before_send` filter, sample rates, PII off, what actually reaches it.
- **WebSocket** — `manager`, event subscriber bridge, replay-on-reconnect, sticky-session assumption.

**Runtime flows (each traced source→sink, with the failure branch):**
1. **User onboarding / OAuth** — connect → Zerodha login → callback → account create → signup-gate → JWT/cookie.
2. **Live trade → alert** — postback → Celery `process_webhook_trade` → TradeSync → PositionLedger(FIFO) → CompletedTrade+features → BehaviorEngine → RiskAlert/BehaviorEvent → event_bus → WS + push/WhatsApp.
3. **Market data** — shared KiteTicker → union subscribe → tick fan-out → WS `position_update`/`margin_update`.
4. **Analytics on-demand** — page open → API → service query (indexed) → response; admin aggregates via Redis cache.
5. **Nightly/batch** — intent re-learn (18:15) · reconciliation · EOD reports · retention · watchdog (the sequential all-account loops).
6. **Tradebook import** (cold-start) — CSV → parse → idempotent upsert → reconcile with postback twins (no engine run).
7. **AI coach / RAG** — chat → context build → embeddings/retrieval → OpenRouter → stream back.
8. **Admin** — login (pw→OTP/TOTP→cookie) → IP allowlist → impersonation (read-only middleware) → audit log.
9. **Data rights (DPDP)** — export / hard-delete / import (Settings → Danger Zone).
10. **WS reconnect/replay** — client `last_event_id` → `?since=` → Redis Streams replay → resume.
11. **Constitution / rules** — profile change → `RULE_FIELDS` gate (tighten instant / loosen 409).
12. **Startup** — lifespan: encryption-key validate, settings warm, ticker restart, event subscriber, one-time P&L repair + pnl_pct backfill.

---

## Phases (risk-first; each = a committed findings doc)

- **P0 · Repo map & entry** — full tree inventory (done above), then entry/infra ground truth: `main.py` (middlewares, lifespan, router mounts, CORS/CSP/security headers, health), `core/config`, `database`, `celery_app`, `event_bus`, `redis_pool`, `deps`/auth deps, `request_context`, `logging`, `admin_state`, `error_feed`, `metrics`, `rate_limit*`, `trading_defaults`, `exchange_constants`, `market_hours`. Build the authoritative route map + start `CONNECTIONS_AND_FLOWS.md`.
- **P1 · Money math (CRITICAL)** — `pnl_calculator`, `position_ledger_service`, `trade_sync_service`, CompletedTrade/FIFO build, `completed_trade_feature`, multipliers, MCX/exchange specs. Every ₹ correct; idempotency; raw-P&L rule; the startup P&L-repair + backfill correctness.
- **P2 · Behaviour engine** — `behavior_engine` (2.6k LOC), `detector_registry`, every detector, `behavioral_baseline_service` vs `baseline_service` (dup?), `behavior_scores_service`, `constitution_service`, thresholds, `behavioral_analysis_service` legacy question.
- **P3 · Real-time & scale** — `webhooks`, `tasks/*` (trade/alert/report/reconciliation/intent/retention/watchdog/portfolio_radar — incl. the sequential all-account loops), `event_bus` runtime, `websocket`, `price_stream_service`, `order_stream_service`, `circuit_breaker_service`, `token_manager`. Correctness + the 10k bottlenecks B1–B7.
- **P4 · Auth & security** — user auth (`zerodha.py`, `zerodha_auth_service`, auth deps), all `api/admin/*` + `session_registry` + `admin_state`, impersonation middleware, encryption/Fernet, `rate_limiter`, nonce/CSRF, cookies, CORS/CSP, secrets handling, signup gate. Threat-model each surface.
- **P5 · Analytics** — `api/analytics.py` (3.2k LOC), `analytics_service`, `order_analytics_service`, `habits_service`, `pattern_prediction_service`, `ai_personalization_service`, + FE analytics components (5 tabs, ReportCard, cards, charts, axis/tooltip rules).
- **P6 · Remaining API + services** — profile, settings, alerts, journal, reports, coach/`ai_service`/`rag_service`, notifications/push/whatsapp/email, constitution, cooldown, my_record, goals, danger_zone, account_data, session_intent, behavioral, risk, positions, trades, admin_settings, instrument/margin/gtt/GTT, notification_rate_limiter, early_warning, alert_checkpoint, etc. (every remaining `api/` + `services/`).
- **P7 · Frontend** — every `src/` file: pages (16) + admin pages (12), `contexts` (Broker/WebSocket/Alert/AdminAuth), `hooks` (12), `lib` (api/adminApi/guestMode/impersonation/support/formatters/…), all `components/` incl. `ui/*`, `data/`, `types/`, `App.tsx`/`main.tsx`/`index.css`. State mgmt, error/loading consistency, api mapping, perf, guest-mode fidelity, bundle, a11y where it affects function.
- **P8 · DB & migrations** — 36 models, all 72 migrations (order, idempotency, indexes, constraints, cascades, partitioning), 15 schemas, ghost columns (`quality_score`, `outcome`), data integrity, drift between models and migrations.
- **P9 · External connections & integrations (deep)** — the full `CONNECTIONS_AND_FLOWS.md`: each service (list above) config→code→failure→prod-readiness; every flow's failure branch; retry/idempotency/backpressure; secret rotation; what breaks if each dependency is down.
- **P10 · Config, build, tooling & ops** — `package.json` (deps, scripts, audit for vulns/unused), `vite.config`, `vitest.config`, 3× `tsconfig`, `tailwind.config`, `postcss`, `eslint.config`, `components.json`, `index.html`, `skills-lock.json`, `backend/{Dockerfile,Procfile,pytest.ini,requirements.txt}`, `.dockerignore`/`.gitignore`, both `.env.example` (vs `.env` — secret leakage check), `public/{sw.js,manifest.json,robots.txt}`, PWA assets, `.github/agents`, `.agents`, `.claude`. Prod-readiness of the *runtime + build*.
- **P11 · Scripts & test suites** — `backend/scripts/**` (73: db/debug/validate/smoke_*/one-offs — classify keep vs dev-only vs dead → ledger), `backend/tests` (29) + `src/test` correctness & coverage, guest-mode fixtures as smoke coverage.
- **P12 · Archived & separate trees** — `_archive/*`, `backend/app/**/_archive`, `src/**/_archive`, `design_v2/`, `prototype_design/`, `scroll-loss-experience/` (separate Next.js app), `docsreview*`. Confirm truly dead, scan for anything still referenced, flag removal candidates → ledger.
- **P13 · Docs audit** — every doc in `docs/`, `docsreview*/`, and root (`README`, `CLAUDE.md`, `AUDIT_FINDINGS.md`, `DESIGN.md`, the 3 planning docs, architecture doc, memory-referenced docs) — mark correct / stale / wrong / dead vs the code. Feed the dead-doc ledger.
- **P14 · QA regression + performance/load testing plan** — see dedicated section below. Deliverable: an executable test/verification plan (not just findings) covering functional regression, integration, real-time, security, and load/perf to 10k.
- **P15 · Synthesis** — consolidated 10k-prod-readiness verdict, ranked risk register, the QA/perf plan roll-up, prioritized fix backlog, **100%-production-readiness pending list**, and **next steps** (see final section).

---

## P14 (detail) · QA Regression + Performance/Load Testing Plan

A separate, concrete plan — what to test, how, and the pass bar — so readiness is *proven*, not asserted.

### A. Functional regression (per feature slice)
- **Money math:** golden-dataset regression — known fills → expected CompletedTrade rows + realized P&L (LONG/SHORT, partial fills, multi-round, MCX multipliers, intraday reversal). Assert raw-P&L rule (no charges). Re-run after any ledger/sync change.
- **Behaviour engine:** replay fixtures (`scripts/replay_engine.py`/`replay_parity.py` exist — audit + extend) → each of 22 detectors fires on its trigger, stays silent otherwise; severity + `trigger_completed_trade_id` tagging; `cooldown_violation` suppression.
- **Idempotency:** double-postback, re-import same tradebook, webhook retry → no duplicate trades/alerts (unique constraints + twin reconcile).
- **Constitution/rules:** tighten = instant; loosen = 409 override path.
- **Data rights:** export completeness; hard-delete cascade leaves no orphan rows; import round-trip.
- **Admin:** authz matrix (each role × each endpoint), 2FA lockout, TOTP replay, impersonation read-only (every non-GET blocked), signup gate, kill-switches.
- **Guest mode:** every mocked path renders (doubles as FE smoke).

### B. Integration / real-time (staging vs a real/sandbox Zerodha account — the never-run gap)
- OAuth connect → callback → account row → JWT/cookie.
- Live postback → alert appears in browser within SLO (`alert_e2e_lag_ms` < 3s).
- WS drop → reconnect with `?since=` → missed events replayed, no dupes.
- Token daily-expiry → reconnect flow at market open.
- Push + WhatsApp fallback fires when WS offline (WhatsApp blocked on Meta — assert graceful skip).
- Every external dependency **down** path: Redis down (engine still processes, WS degrades), OpenRouter down (coach 5xx handled), SMTP down, Sentry down — no user-facing crash.

### C. Security regression
- Auth bypass attempts (missing/expired/tampered JWT, cross-account access via mismatched `broker_account_id`), admin IP-allowlist + `X-Forwarded-For` spoof (only when `ADMIN_TRUST_PROXY_HEADERS`), CSP/headers present on every response, CORS origin enforcement, rate-limit trips, no secrets in logs/Sentry/responses, `.env` not shipped, dependency vulnerability scan (`npm audit`, `pip-audit`).

### D. Performance / load (the 10k question — staged 1k → 5k → 10k)
- **Live path:** simulate market-hours fill volume (100k–500k engine tasks/day, bursty at 09:15) → measure queue depth, worker throughput, `alert_e2e_lag_ms`, DB pool saturation, Redis command rate vs tier budget. Tools: `scripts/simulate_trader_environment.py`/`reproduce_position_lag.py` exist — audit + build a proper load harness (Locust/k6 for HTTP+WS; a Celery flooder for the task path).
- **WebSocket:** N concurrent sockets/instance → memory, fd, event-loop lag; fan-out cost across instances (B6).
- **KiteTicker:** instrument-union growth vs per-connection cap (B5) — sharding trigger.
- **Batch jobs:** time the all-account loops at 1k/10k accounts; prove the fan-out refactor (CR1) before relying on it.
- **DB:** slow-query capture under load; index effectiveness; connection-cap math across web+worker instances (B4).
- **Pass bar:** define SLOs (p95 API latency, alert e2e < 3s, 0 dropped ticks, queue drains within market hours, error rate < 0.1%) — green at 10k on the target infra tier, not free tier.

### E. Test infrastructure gaps to close
- CI wiring (`.github` currently only has an agent def — no test workflow): add typecheck+lint+FE+BE test gate.
- Coverage measurement (backend `pytest --cov`, FE `vitest --coverage`) + a floor.
- A staging environment mirroring prod tiers for B/D (does not exist yet — hard dependency for live validation).

---

## Cadence & expectations
This is a **multi-turn, multi-day effort** (~500+ files across code, migrations, scripts, tests, configs,
docs, and 3 dead/separate trees). Each phase is committed as it completes, so nothing is lost across
sessions; progress is tracked in memory. You review findings between phases; I fix only on your go-ahead.

## "Will it work for 10k in production?" — threaded through every phase
Each phase explicitly asks: *does this hold at 10k concurrent?* (per-request cost, N+1, unbounded loops,
connection budgets, sync-in-async, memory, idempotency, backpressure). Scale findings roll up into P14/P15
and `SCALABILITY_REVIEW_10K.md`.

---

## What's pending for 100% production readiness (living — finalised in P15)

Seeded from prior review passes + memory; **verified/expanded during the review**, not taken on faith. Owner tag: **You** (business/decision) · **Dev** (code) · **Ext** (third-party/infra).

**Hard blockers (must clear before public launch):**
- **[You] Live validation never run** — nothing is runtime-tested against a real Zerodha account. Biggest risk. → P14-B on staging.
- **[You] Zerodha commercial/partner terms** — API usage at scale, postback, market-data account legitimacy.
- **[You] Business entity + GST + billing** — no payments/subscription system exists yet (roadmap doc only).
- **[Ext] Meta/WhatsApp (Gupshup) approval** — accountability-partner + alert delivery blocked until approved.
- **[Dev] Migration 074 (`admin_settings`) not applied** — Global Settings runs on fail-safe defaults until then.

**Infra / scale (from `SCALABILITY_REVIEW_10K.md`, to be re-verified):**
- Off free/dev tiers: Celery workers (autoscale on queue depth), paid Redis, DB pooler + right-sized pool, multiple web instances behind LB.
- CR1 fan-out the sequential all-account batch tasks; CR2 ticker instrument sharding; CR3 per-account sessions; CR4 stagger/cap AI batch; CR5 WS consumer groups if Redis cost demands.

**Engineering / quality (to be enumerated by this review):**
- No CI test gate; no coverage floor; no staging env; no load harness (P10/P11/P14-E).
- Dead-weight removal (archives, dead trees, duplicate services) — low-risk, per ledger.
- Error/loading standardization rollout is partial (P7).
- `SUPPORT_EMAIL` is a placeholder (`support@tradementor.ai`) — real inbox needed.
- Secrets: `ENCRYPTION_KEY` single point of failure (backup + rotation plan); VAPID/admin secrets management.
- Observability: Sentry present; add metrics/alerting/dashboards + on-call for the SLOs.
- Backups / disaster recovery / data-retention policy (DPDP) — verify.
- Legal: Terms/Privacy live pages exist — confirm content correctness; no formal security review / pen test yet.

## Next steps (immediate)
1. **You review + approve this expanded plan** (this doc) — then I begin **P0** (repo map & entry, start `CONNECTIONS_AND_FLOWS.md`).
2. Execute phases **P0 → P15 risk-first**, one committed findings doc each; you review between phases.
3. Findings-only throughout; batched fix passes only on your go-ahead after each phase (or grouped at the end — your call).
4. P14 produces the **runnable** QA/regression + load plan; P15 delivers the final **100%-readiness verdict + prioritized backlog**.
5. Parallel (yours, non-code): the hard blockers above (live validation env, Zerodha terms, entity/GST, Meta approval, apply 074).
