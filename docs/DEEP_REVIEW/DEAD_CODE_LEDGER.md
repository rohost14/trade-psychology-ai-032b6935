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

## Prior-audit items (carried forward from CODEBASE_AUDIT.md — re-verify during phases)
| # | Item | Where verified |
|---|---|---|
| D7 | Archived routers `portfolio_radar` / `guardrails` / `portfolio_chat` (git-mv'd to `api/_archive/`) | main.py mounts removed — confirm no live caller in P6/P7 |
| D8 | `vix_service.py` archived (0 imports) | confirm in P6 |
| D9 | `baseline_service.py` (1 importer) vs `behavioral_baseline_service.py` (4) — suspected legacy dup | P2 |
| D10 | `behavioral_analysis_service.py` (1,887 LOC, 2 importers) vs `behavior_engine.py` — legacy engine? | P2 |
| D11 | Ghost columns: `CompletedTrade.quality_score` (populated by nothing), `risk_alert.outcome` (never written) | P8 |
| D12 | Root cruft: `AUDIT_FINDINGS.md`, `DESIGN.md`, `design_v2/`, `prototype_design/`, `scroll-loss-experience/`, `docsreview*` | P12/P13 |
| D13 | `guestMode.ts` stale mocks for archived features | P7 |
| D14 | ~62 TODO/FIXME/HACK markers | triage across phases |

## Docs (seed — full pass in P13)
| # | Item | Note |
|---|---|---|
| DD1 | `CODEBASE_AUDIT.md` says "224 routes / 0 broken mappings" | superseded by this deeper review; keep as history |
| DD2 | Repo docs "can be stale" (per CLAUDE.md) | P13 marks each correct/stale/wrong/dead vs code |

## Scripts / tests (seed — full pass in P11)
| # | Item | Note |
|---|---|---|
| DS1 | `backend/scripts/**` (73 files: smoke_*, debug/, db/, validate/, one-offs + `.txt`/`.pyc` artifacts) | classify keep(dev-tool) / dead / secrets-check |
