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
| D15 | ✅ CLOSED 2026-08-04: `PnLCalculator.calculate_trade_pnl_realtime` (96 LOC) removed → `services/_archive/dead_pnl_and_checksum.py`. Zero callers re-verified; it also still used the retired oldest-lot FIFO cost basis and replayed every prior trade per fill. Removal cleared the stale `opposite_side` pyflakes warning and the now-unused `get_lot_multiplier` import. | CLOSED |
| D22 | ✅ CLOSED 2026-08-04: `ZerodhaClient.validate_postback_checksum` — a **third** copy of postback verification, zero callers. Live path uses `api/webhooks.py::verify_zerodha_checksum` / `verify_zerodha_checksum_header`, both `hmac.compare_digest`; the dead copy used a plain `==`. Archived to `services/_archive/dead_pnl_and_checksum.py`. | CLOSED |
| D16 | 🟡 Two `is_market_open` (`exchange_constants` no-holidays/zoneinfo vs `market_hours` holidays/pytz) | Divergent on holidays; two tz libs (P1-M10, P0-F7) | Consolidate. DECIDE |
| D17 | ✅ FIXED 2026-07-26 (M4): `pnl_calculator` class docstring corrected — reconcile is log-only+avg-repair, no Zerodha overwrite; RAW P&L via multiplier | CLOSED |
| D18 | ✅ RESOLVED 2026-07-26 (with R1): Procfile → `--pool=prefork`, dropped `--concurrency=100` → `celery_app.worker_concurrency=4` is now the single source | CLOSED |
| D19 | 🟠 `guardrail_tasks` runs every 60s (consumed `alerts` queue) though feature archived | Compute waste for killed feature (P0-F9 confirm) | DECIDE retire |

## Zero-caller scan — 2026-08-04 (mechanical, NOT yet triaged)

Ran an AST scan over `backend/app` (excluding `_archive`), counting every textual
reference to each function/method across `backend/` and `src/`. Framework entrypoints
(FastAPI routes, Celery tasks, fixtures, properties, validators) excluded. **36 hits.**
Two were verified and actioned (D15, D22). **The remaining 34 are UNTRIAGED — do not
bulk-remove them.** Three known trap categories:

- **Parked feature code, not dead.** `live_position_engine.merge_live_alert_on_close`
  is part of `LivePositionEngine`, which `docs/PENDING.md` records as done/applied/
  tested and deliberately wired to nothing pending Zerodha approval + Gate 3.
- **Comment mentions inflate the count.** `calculate_trade_pnl_realtime` scored 3 hits
  and was still dead — two were prose in other files' comments. The reverse also
  happens, so the count is a starting point, not a verdict.
- **Dynamic dispatch / re-export.** Anything reached via `getattr`, a registry, or an
  `__init__.py` re-export will read as zero-caller and is not.

| Area | Candidates |
|---|---|
| `core/market_hours.py` | `is_high_risk_window`, `get_trading_session`, `get_allowed_trading_hours`, `classify_segment_from_symbol` |
| `core/logging_config.py` | `ContextLogger.clear_context`, `MetricsCollector.record_api_call`, `MetricsCollector.record_error` — plausibly downstream of D4 (`setup_logging` never called) |
| `core/celery_app.py` | `_dispose_async_engine_on_fork`, `_setup_worker_logging` — **check for signal registration before touching** |
| `services/instrument_service.py` | `get_instrument_by_token`, `get_option_chain`, `get_futures`, `cleanup_expired` |
| `services/email_service.py` | `format_eod_email`, `format_morning_email` — vs `retention_service._format_eod_report` / `_format_morning_brief`, also zero-caller. Two pairs of formatters, all four unreferenced: likely one real duplication |
| `api/websocket.py` | `notify_trade_update`, `notify_risk_alert` |
| `services/zerodha_service.py` | `get_order_trades` |
| Others | `redis_pool.get_sync_redis_optional`, `ai_service.generate_trading_persona`, `behavioral_baseline_service.get_current_baseline`, `broker_interface.BrokerFactory.get_supported_brokers`, `cooldown_service.end_cooldown`, `detector_registry.spec_for`, `gtt_service.get_discipline_summary`, `notification_rate_limiter.set_user_config`, `order_analytics_service.get_daily_order_summary`, `portfolio_concentration_service.analyse_and_alert`, `price_stream_service.AsyncKiteTicker.stop_async`, `price_stream_service.SharedPriceStream._on_ticker_noreconnect`, `retention_service._format_eod_report`, `retention_service._format_morning_brief`, `token_manager.get_token_expiry_estimate`, `trade_sync_service.fetch_orders_from_zerodha` |

Reproduce: the scan script is throwaway; re-derive with an AST walk + identifier
Counter rather than trusting this list once the code has moved on.

## Prior-audit items (carried forward from CODEBASE_AUDIT.md — re-verify during phases)
| # | Item | Where verified |
|---|---|---|
| D7 | ✅ CLOSED (P6): archived routers dead; remaining refs = shared Celery tasks/services (`portfolio_radar_tasks`, `position_metrics_service`) in admin/tasks.py, intentionally kept | Guardrail-tasks compute-waste stays as D19/F9 |
| D8 | ✅ CLOSED (P6): `vix_service.py` 0 live refs (grep clean) — dead | ARCHIVE confirmed |
| D9 | ~~baseline dup~~ **RESOLVED: NOT a dup** — `baseline_service`=profit-factor helpers (personalization); `behavioral_baseline_service`=per-user percentile baselines. Distinct. (P2-E5) | CLOSED (optional rename) |
| D10 | ✅ RETIRED 2026-07-26 (E1): `behavioral_analysis_service.py` → `services/_archive/` (git mv). Both consumers repointed to `behavior_summary` (live engine RiskAlerts). Dead `/trade-tags` route removed. App boots, no live importers. | CLOSED |
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
| DS2 | ✅ DONE 2026-07-26: `design_v2/` + `prototype_design/` → `_archive/dead_trees/` (git mv); `AUDIT_FINDINGS.md`+`DESIGN.md` → `_archive/stray_docs/`; `scripts/debug/`+`smoke_phase*`+`swap_tables.py` → `scripts/_archive/`. `scroll-loss-experience/` = **untracked** (0 git files) — already not in repo. Verified typecheck+boot+424 tests collect. | CLOSED |
| DS3 | ✅ P12: `_archive/*` correctly excluded from typecheck+eslint + 0 live imports (clean isolation) | KEEP as-is |
