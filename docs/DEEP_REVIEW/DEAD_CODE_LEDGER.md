# Dead / Outdated / Unwanted — Running Ledger

> Append-only. Every dead/orphaned/duplicate/stale item found during the review, with evidence + a
> disposition (KEEP / ARCHIVE / DELETE / DECIDE). **Findings-only — nothing acted on without approval.**
> Status legend: 🔴 confirmed dead · 🟠 orphaned-but-running (compute waste / trap) · 🟡 duplicate/stale.

## Code

| # | Item | Evidence | Disposition |
|---|---|---|---|
| D1 | 🟡 `core/rate_limit.py` (factory) duplicates `core/rate_limiter.py` (class) | Two independent sliding-window impls; factory used only by `danger_zone.py` (+ archived `portfolio_radar`) | Consolidate on one **async** impl (P0-F5). DECIDE |
| D2 | 🟠 Guardrails feature — routers archived, Celery tasks still live | `guardrail_tasks.check_guardrail_rules` beat every 60s (routes to consumed `alerts` queue → actually runs); `portfolio_radar_tasks`/`portfolio_sync_tasks` still triggered; frontend gone | DECIDE retire vs restore (P0-F9) |
| D3 | 🟠 `market_data_tasks` / intent / maintenance beat tasks queued but never consumed | Route to default `celery` queue; worker consumes only `trades,alerts,reports` (P0-F1) | Not dead by intent — **broken wiring**; fix routing, don't delete |
| D4 | 🔴 `setup_logging()` dead (never called) → error-feed handler + JSON logging + request-id filter all unwired | grep: zero callers (P0-F2) | Wire it up (fix, not delete) |
| D5 | 🟡 `redis_pool.py` stale comment: "VIX fetches" | vix_service archived earlier | Trivial comment cleanup |
| D6 | 🟡 Two metrics subsystems (`logging_config.MetricsCollector` vs `core/metrics.py`) | Different purposes; document authority (P0-F13) | KEEP, document |
| D15 | 🔴 `PnLCalculator.calculate_trade_pnl_realtime` dead (~90 LOC) | Replaced by PositionLedgerService; zero live callers (P1-M7) | ARCHIVE/remove |
| D16 | 🟡 Two `is_market_open` (`exchange_constants` no-holidays/zoneinfo vs `market_hours` holidays/pytz) | Divergent on holidays; two tz libs (P1-M10, P0-F7) | Consolidate. DECIDE |
| D17 | 🟡 `pnl_calculator` docstring L51-55 stale (claims Zerodha-realised overwrite) | Reconcile is log-only+avg-repair now (P1-M4) | Fix comment |
| D18 | 🟡 Procfile worker `--pool=gevent --concurrency=100` contradicts `celery_app.py` `worker_concurrency=4` (prefork) | Config drift; gevent wrong for asyncio.run tasks (P3-R1) | Reconcile |
| D19 | 🟠 `guardrail_tasks` runs every 60s (consumed `alerts` queue) though feature archived | Compute waste for killed feature (P0-F9 confirm) | DECIDE retire |

## Prior-audit items (carried forward from CODEBASE_AUDIT.md — re-verify during phases)
| # | Item | Where verified |
|---|---|---|
| D7 | ✅ CLOSED (P6): archived routers dead; remaining refs = shared Celery tasks/services (`portfolio_radar_tasks`, `position_metrics_service`) in admin/tasks.py, intentionally kept | Guardrail-tasks compute-waste stays as D19/F9 |
| D8 | ✅ CLOSED (P6): `vix_service.py` 0 live refs (grep clean) — dead | ARCHIVE confirmed |
| D9 | ~~baseline dup~~ **RESOLVED: NOT a dup** — `baseline_service`=profit-factor helpers (personalization); `behavioral_baseline_service`=per-user percentile baselines. Distinct. (P2-E5) | CLOSED (optional rename) |
| D10 | 🟠 `behavioral_analysis_service.py` (1,887 LOC) = **CONFIRMED live dual engine** — served by `/api/behavioral/analysis`+`/patterns`, consumed by `ExportReportButton.tsx`. Different logic/thresholds than BehaviorEngine v2 → contradictory findings. "single source of truth" claim false. (P2-E1) | DECIDE retire vs document |
| D11 | ✅ P8: `quality_score` truly dead (only reader = `_archive/analytics_dead_endpoints.py`; no live reader/writer) — drop or leave. `risk_alert.outcome` HAS a writer (`api/risk.py`) but ~0 adoption (MIG2) — not dead, just unused-data | quality_score: DROP candidate |
| D20 | 🟡 No migration framework/tracking (no schema_migrations/alembic/runner) — manual .sql apply (P8-MIG1) | Adopt Alembic pre-scale |
| D21 | 🟡 `behavioral_events` (old shadow, 020/040) vs `behavior_events` (live partitioned, 064/067) — confirm old is dead (P8-MIG5) | Verify + drop old |
| D12 | Root cruft: `AUDIT_FINDINGS.md`, `DESIGN.md`, `design_v2/`, `prototype_design/`, `scroll-loss-experience/`, `docsreview*` | P12/P13 |
| D13 | `guestMode.ts` stale mocks for archived features | P7 |
| D14 | ~62 TODO/FIXME/HACK markers | triage across phases |

## Docs (seed — full pass in P13)
| # | Item | Note |
|---|---|---|
| DD1 | `CODEBASE_AUDIT.md` says "224 routes / 0 broken mappings" | superseded by this deeper review; keep as history |
| DD2 | 🟠 P13: **CLAUDE.md architecture sections STALE** — describes pre-v2 (8 client-side patterns not 28 backend detectors; "detection client-side in AlertContext"+"estimated costs" false; `money-saved`/blowup endpoints renamed). Loaded every session → misleads. (DOC1) | REFRESH (top doc fix) |
| DD3 | 🟡 P13: empty cruft dirs `docsreviewscreens/`+`docsreviewsessions/`; `CODEBASE_AUDIT.md` superseded by DEEP_REVIEW; root `AUDIT_FINDINGS.md`/`DESIGN.md` stray (DOC2/D12) | remove/archive |
| DD4 | 🟡 P13: `docs/architecture/*` (9) partially stale (verify vs code; not line-audited) | verify before trusting |

## Scripts / tests (seed — full pass in P11)
| # | Item | Note |
|---|---|---|
| DS1 | ✅ P11 classified (no secrets): DEAD→archive = `scripts/debug/*` (19), `smoke_phase*.py` (11); DELETE = `scripts/*.txt` + `*.pyc` (5); GATE = `swap_tables.py` (destructive). KEEP (P14 assets) = `validate/*`, `replay_*`, `simulate_trader_environment`, `reproduce_position_lag`, `db/seed_data` | archive/delete dead |
| DS2 | 🟡 P12: `scroll-loss-experience/` separate Next.js app w/ committed `.next/` build cache + node_modules; `design_v2/`, `prototype_design/` — 0 build refs, 0 live imports, no secrets | REMOVE from repo |
| DS3 | ✅ P12: `_archive/*` correctly excluded from typecheck+eslint + 0 live imports (clean isolation) | KEEP as-is |
