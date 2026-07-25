# Deep Code Review — Synthesis & 10k-Production-Readiness Verdict

> Consolidates P0–P14 (docs `01`–`15`). Every item is code-verified, findings-only. Read the per-phase
> docs for detail + repro. Severity: **P0** ship-blocker · **P1** breaks a real path or scale · **P2**
> quality/latent · **P3** nit.

---

## TL;DR verdict
**The architecture is sound and the hard problems are solved well** — event-driven per-trade engine, shared KiteTicker, Redis-Streams fan-out, idempotent pipeline, mature admin auth, clean tenant isolation, correct raw-P&L discipline, real test coverage on the money paths. **It is NOT a rewrite.**

**But it is NOT production-ready as-configured.** The blockers are concentrated in **deploy/ops config** (orphaned Celery queues, wrong worker pool, unwired logging, no CI, unpinned/vulnerable deps, no migration tracking) and a handful of **correctness gaps** (P&L product-mixing, flip rounds, MCX unrealized). **Nothing has ever been runtime-tested against a real Zerodha account** — the single biggest unknown. Estimate: the P0/P1 list is **days-to-weeks of focused fixes + a real load/integration test**, not months.

---

## Ranked risk register (all phases)

### 🔴 P0 — ship-blockers
| # | Finding | Phase |
|---|---|---|
| F1 | ✅ **FIXED 2026-07-26** — **9/16 scheduled Celery tasks never ran** (beat→default `celery` queue; worker consumed only `trades,alerts,reports`). Fix: Procfile worker `--queues=celery,trades,alerts,reports` + boot regression guard in `celery_app.py`. Verified orphaned 9→0. *Still confirm actual prod worker `--queues` at deploy.* | P0 |

### 🔴 P1 — breaks a real path / scale (or unverified-critical)
| # | Finding | Phase |
|---|---|---|
| R1 | 🟡 **PARTIALLY FIXED 2026-07-26** — worker → `prefork` (removes gevent+asyncpg incompat), concurrency single-sourced from config (=4, resolves D18), engine-dispose-on-fork added. ⚠️ **STILL OPEN:** `asyncio.run()`-per-task vs pooled asyncpg needs NullPool-in-worker (or persistent loop) + **load validation (Gate 4)** — left for the load test. | P3 |
| F2 | ✅ **FIXED 2026-07-26 (web process)** — `main.py` calls `setup_logging()` at load (before Sentry); error-feed + JSON logs + request-id filter (on handlers, also fixes F11) now active. ⚠️ **PENDING:** Celery workers don't run it (import `celery_app` not `main.py`) → task errors still miss the admin error-feed; scoped follow-up. | P0 |
| F3/A1 | ✅ **FIXED 2026-07-26** — rate-limiter now keys off the JWT `bid` (per-account) for authed endpoints; unauthed → peer IP, XFF only behind trusted proxy. Closes shared-NAT 429s + XFF-rotation bypass. | P0/P4 |
| F4 | Blocking **sync Redis on the async event loop** (limiters + error-feed) → throughput collapse. *(Still open — separate from F3; same file.)* | P0 |
| M1 | P&L **doesn't segregate by product** (MIS+NRML same symbol netted) → wrong P&L / missing CompletedTrades | P1 |
| M2 | **Flip-opened rounds build no CompletedTrade** live → real-time engine misses flip trades | P1 |
| M3 | **MCX/CDS unrealized P&L ignores lot multiplier** → commodity open P&L ~100× understated | P1 |
| N1 | **Redis is a tier-1 SPOF** for the live pipeline (locks + broker), not just cache | P9 |
| MIG1 | **No migration framework/tracking** (no schema_migrations/Alembic) → drift invisible, unsafe deploys | P8 |
| CFG1 | **HIGH FE dep vulns** — axios (auth-bypass prototype pollution + SSRF), React Router (XSS), **DOMPurify (XSS — the Chat mitigation itself)** | P10 |
| CFG2 | Backend deps **0/28 pinned** → non-reproducible builds; crypto/jose float | P10 |
| CFG3 | **No CI** — nothing gates typecheck/lint/test/audit | P10 |
| — | **Live validation never run** vs a real Zerodha account (biggest single unknown) | cross |

### 🟠 P2 — quality / latent / correctness-adjacent
E2/M6/Q1 alert→trade link nulled on CT-rebuild → **behaviour-cost undercounts** (corrected from P1: not nightly, event-triggered) · E1 **dual detection engine** (`behavioral_analysis_service` live behind `/api/behavioral/*`, feeds the export report) · E3 engine `analyze()` swallows all errors (silent detection loss) · A2 **admin cookie SameSite=None + no CSRF token** (defense rests on CORS) · A3 admin per-email lockout DoS · DP1 DPDP delete cascade (**resolves favorably on paper — run the `pg_constraint` query to confirm**) · DP2 Redis purge misses `stream:{id}` (DPDP-incomplete) · MIG2 `outcome` col ~0 adoption → empty stats · Q2 prediction service fakes "probabilities" · Q3 uncached heavy analytics aggregation · N2 httpx client reused across per-task loops · N3 no OpenRouter retry · ✅ **CFG4 FIXED 2026-07-26** (`ENVIRONMENT` default→`production` fail-secure + value validator; dev explicit-set unaffected) · F6 Celery broker TLS `CERT_NONE` · F7 NSE holidays hardcoded ≤2026 · F8 CORS private-IP origins in prod · F9 guardrails compute waste (killed feature still runs) · F14 every-boot P&L repair scan · F5 dup rate-limiters · FE1 user JWT in localStorage · FE2 guest-mode `{}` crash · T1 thin FE tests · DOC1 **CLAUDE.md architecture sections stale** (misleads every session) · dead trees to remove (scroll-loss-experience/design_v2/prototype_design).

### ⚪ P3 — nits
F10-F13, M5/M8-M11, A4-A8, R5-R7, Q4-Q6, MIG3/5/6, FE3-5, CFG5, T2-3, DOC2-3 (see per-phase docs).

### 📈 Scale sizing (infra, from SCALABILITY_REVIEW_10K — not code bugs)
B1 Celery capacity · B2 batch fan-out (CR1) · B3 Redis paid tier · B4 DB pooler · B5 ticker instrument shard (CR2) · B6/B7 WS.

---

## Prioritized fix backlog (recommended order)
1. **Deploy-config P0/P1 (fast, high-impact):** F1 queue routing + a startup assertion · R1 worker pool (prefork) + reconcile Procfile/celery_app · F2 call `setup_logging()` · CFG4 env default. *(All small, unblock everything.)*
2. **Security/build gate:** CFG1 `npm audit fix`+DOMPurify bump · CFG2 pin+lock · CFG3 CI (incl. audits) · F3 rate-limit key off the auth principal · A2 admin CSRF.
3. **Money correctness:** M1 product key · M2 flip round · M3 MCX unrealized · M6/E2 stable CT id (fixes Q1 behaviour-cost too).
4. **Ops/DB:** MIG1 Alembic + baseline · DP1 run the cascade query · DP2 purge stream · N1 Redis HA plan.
5. **Product/cleanup:** E1 retire/repoint legacy engine · E3 detection-failure counter · DOC1 refresh CLAUDE.md · dead-code sweep (ledger) · Q3 analytics cache.
6. **Then:** P14 Gate 3 (staging + real Zerodha) → Gate 4 (load to 10k).

---

## What's left for 100% production readiness (owner-tagged)
**Hard blockers (yours / external):**
- **[You]** Run **live validation** against a real Zerodha account (P14 Gate 3) — nothing here is runtime-tested.
- **[You]** Zerodha **commercial/partner terms** (API-at-scale, postback, market-data account — the borrowed-token ticker R7).
- **[You]** **Business entity + GST + billing** (no payment system exists — roadmap only).
- **[Ext]** **Meta/WhatsApp (Gupshup)** approval.
- **[Dev]** Apply **migration 074** (+ adopt migration tracking, MIG1).

**Engineering (this review — the P0/P1 list above):** deploy-config, worker pool, logging, CI, dep pinning + vuln fixes, rate-limit fix, money-correctness trio, migration framework, Redis HA.

**Infra/scale:** off free/dev tiers (Celery autoscale, paid Redis, DB pooler, multi web instance behind LB); CR1 batch fan-out; CR2 ticker shard.

**Ops/observability:** wire logging (F2), real metrics/alerting/on-call for the SLOs, backups/DR + DPDP retention verified (DP1/DP2), `ENCRYPTION_KEY` rotation plan (A8), `SUPPORT_EMAIL` real inbox.

**Legal/product:** Terms/Privacy content correctness, formal security review / pen test (none yet), pricing.

---

## Next steps
1. **You review this synthesis + the per-phase docs**, decide scope of an approved **fix pass** (per the non-negotiable rule I've made **zero** code changes — findings only).
2. I execute fixes in the backlog order above, batched + committed per group, on your go-ahead — starting with the deploy-config P0/P1 (cheapest, highest-leverage).
3. Stand up **CI + staging** (Gate 0) so fixes are verifiable.
4. **You** run the live-Zerodha validation (Gate 3) — the one thing I can't do — then load test to 10k (Gate 4).
5. Close the hard blockers (Zerodha terms, entity/GST, Meta, live-validation) in parallel.

**Bottom line:** solid foundation, real but bounded gaps, concentrated in config/ops + a few correctness fixes. No rewrite. The path to 10k is a focused fix pass + the load/integration test that has never been run.
