# Deep Review — Status Index (per doc)

> At-a-glance completion tracker across every `docs/DEEP_REVIEW/` doc. Master detail lives in each phase
> doc + `99_SYNTHESIS.md`. Legend: ✅ done · 🟡 partial · ⏸️ deferred (bigger change/decision) · ⛔ load/DB-gated
> (implementation can't finalise/validate without the load test or a live DB) · ⬜ open (safe, low-value, left).
> Updated 2026-07-26.

## 00_REVIEW_PLAN — the plan itself. ✅ complete (executed P0–P15).

## 01_P0 entry & map
- ✅ F1 orphaned Celery queues · ✅ F2 logging wired (web **+ worker**) · ✅ F3 rate-limiter per-account
- ✅ **F4** limiters → async Redis (error-feed handler stays sync — logging) · ✅ F11 (filter on handlers) · ✅ F12 (VIX comment) · ⬜ F13 (documented) · ✅ F14 boot repairs gated (RUN_STARTUP_REPAIRS) · ⬜ F10 revocation-on-read · ⬜ F5 dup limiters · ✅ F6 Celery TLS CERT_REQUIRED · ⬜ F7 NSE holidays · ✅ F8 CORS regex dev-only · ⬜ F9 guardrails compute

## 02_P1 money math
- ✅ M2 flip rounds · ✅ M3 MCX unrealized · ✅ M6 stable id (+E2/Q1) · ✅ M4 stale docstring
- ⏸️ **M1** product-mixing (schema migration + stateful re-key + backfill + live validation — spec'd)
- ✅ M5 batch MCX multiplier fallback · ⬜ M8 days_back window · ⬜ M9 float-before-Decimal · ⬜ M10 dup is_market_open · ⬜ M11 stable-id collision

## 03_P2 behaviour engine
- ✅ E1 dual engine retired · ✅ E2 (via M6) · ✅ E3 failure counter · E5 (D9 closed) · E9 (inherited P1, now fixed)

## 04_P3 real-time & scale
- ✅ R1 worker pool (prefork + NullPool) · ✅ R2 (via M6) · R3 postback throttle ⬜ · R4 batch loops ⛔ (fan-out CR1, load-gated)
- ✅ R5 (=F4, limiters async) · ⬜ R6 done (constant-time checksum) · R7 ticker cap ⛔ (infra/CR2)

## 05_P4 auth & security
- ✅ A1 (=F3) · ✅ A2 admin CSRF (Origin check) · ⬜ A3 lockout-DoS · ✅ A4 admin Redis pooled · ✅ A5 OAuth null-email guard · ✅ A6 secret TTL 10min + delete-on-consume · ⬜ A7 dual encrypt paths · ⬜ A8 key rotation (plan)

## 06_P5 analytics
- ✅ Q1 (via M6) · ✅ Q4 (via M3) · ⬜ Q2 fake-precision probabilities · ⛔ Q3 uncached aggregation (load-gated) · ⬜ Q5 regex · ⬜ Q6 split analytics.py (large refactor) · C1/C2 corrections applied

## 07_P6 remaining api/services
- ✅ DP2 stream purge · DP1 cascade **→ [your action]** run the `pg_constraint` query · ⬜ P6-1 coach input cap · ⬜ P6-2 danger_zone wording

## 08_P7 frontend
- ✅ FE3 maintenance-503 gating · ✅ FE4 (via DOC1) · ✅ FE5 (via E1) · ⬜ FE1 JWT in localStorage · ⬜ FE2 guest-mode `{}` crash

## 09_P8 db & migrations
- 🟡 MIG1 tracked runner shipped (Alembic = eventual; **baseline `--stamp` = your action**) · DP1 cascade **→ [your action]** query provided
- ✅ D11 quality_score dead (drop candidate) · ⬜ MIG2 outcome col · ⬜ MIG3 drop quality_score (migration) · ⬜ MIG5 dup event tables · MIG6 drift (needs DB)

## 10_P9 connections & integrations
- N1 Redis-SPOF **→ infra (HA plan)** · ✅ N2 httpx fresh-client-per-call (confirmed live by load test, fixed) · ✅ N3 OpenRouter bounded retry · matrix documented

## 11_P10 config/build/ops
- ✅ CFG2 pin deps · ✅ CFG3 CI · ✅ CFG4 env fail-secure · 🟡 CFG1 runtime-critical vulns fixed; 17 **build-tooling** vulns (build-time only) — `--force` too fragile, needs incremental upgrade · ⬜ CFG5 py 3.14→3.11 dev drift (CI on 3.11)

## 12_P11 scripts & tests
- ✅ T3 dead scripts archived · ⬜ T1 thin FE tests · ⬜ T2 tests-on-deploy-py (CI on 3.11) · **+ load harness added** (`scripts/load/`)

## 13_P12 archives/separate trees
- ✅ dead trees + docs + scripts archived (DS2) · `_archive` isolation confirmed

## 14_P13 docs audit
- ✅ DOC1 CLAUDE.md refreshed · ⬜ DOC2 empty cruft dirs + superseded CODEBASE_AUDIT · ⬜ DOC3 (architecture docs verify)

## 15_P14 QA/load plan
- ✅ plan written · **load harness now built** (`backend/scripts/load/`) · Gate 3 (live Zerodha) + Gate 4 (run the load test) **→ your action**

---

## Rollup
- **Done (code):** ~36 findings incl. every P0 + most P1 (F1/F2/F3/F4/F6/F8/R1/R5 · M2/M3/M5/M6/E1/E2 · CFG1-runtime/CFG2/CFG3/CFG4 · A2/A5 · DP2 · E3 · DOC1 · dead-code · 8 P3 nits · + load harness).
- **Deferred (needs approved bigger change):** M1 (schema + live validation).
- **Load/DB-gated (code can't finalise without the load test / live DB):** Q3 (cache), R4/B2 fan-out, R7/B5 ticker shard, B1/B3/B4/B6/B7 infra sizing. *(F4/R5 async-Redis limiters now DONE; A4 admin-Redis is the small remainder.)*
- **Your action (out of code scope):** run the load harness (Gate 4), live-Zerodha validation (Gate 3), DP1 cascade query, MIG1 `--stamp`, N1 Redis HA, business/legal/Ext items.
- **Left (safe, low-value):** the remaining ⬜ nits.
