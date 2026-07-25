# P11 — Scripts & Test Suites (findings)

> Scope: `backend/tests/` (17 files), `src/test/`, `backend/scripts/**` (73), guest-mode fixtures.
> **Findings-only.** Ran the pure-logic backend tests live.

## Verdict
Backend test coverage on the **critical paths is genuinely good and green**. Frontend testing is thin. Scripts are mostly dead dev one-offs (no secrets) with a few keepers that double as P14 assets.

## Evidence (ran live)
- **402 backend tests collect** cleanly (17 files: engine, tradebook import, reconcile, admin deps, detector flags, habits, session windows, data integrity, db schema, integration, notifications, phase2, trade classifier, dashboard api).
- **109 pure-logic tests PASS** in 3.4s — `test_behavior_engine` (32), `test_tradebook_import` (29), `test_session_windows_by_exchange` (14), `test_trade_classifier` (19), `test_import_reconcile` (7), `test_habits_service` (8). The money/engine/import paths are actually covered + passing.
- **Frontend: 3 test files** total (`analyticsTabs.smoke`, `sseParser`, `example`) vs ~230 ts/tsx.

## 🟡 P2
### T1 · Frontend test coverage is minimal · test-coverage
3 FE test files (mostly smoke) for the entire app. No component/interaction/state coverage, no coverage floor. Combined with **CFG3 (no CI)**, FE regressions are unguarded. **Fix:** add vitest coverage for the high-value FE logic (WebSocket reconnect/replay, api interceptor, guest-mode, chart formatters, AlertContext dedup) + a floor in CI.

## ⚪ P3
- **T2** The suite runs on **Python 3.14** (dev) but the container deploys **3.11** (CFG5) — tests never execute on the deploy runtime, and there's no CI to run them anywhere (CFG3). Pin CI to the deployed Python.
- **T3 (ledger)** Script hygiene: `scripts/debug/*` (19 check_*/debug_* one-offs) + `scripts/smoke_phase*.py` (11 phase smokes, superseded by pytest) are **dead dev leftovers** → archive; `scripts/*.txt` + committed `*.pyc` (5) → delete; `scripts/swap_tables.py` is **destructive** (table swap) → gate/archive. **KEEP** (P14 assets): `scripts/validate/*` (behaviour scenario harness 01–07), `replay_engine.py`/`replay_parity.py`, `simulate_trader_environment.py`, `reproduce_position_lag.py`, `scripts/db/seed_data.py`. **No hardcoded secrets in any script** (grep clean — extends the P0 root-scripts result).

## ✅ Solid
Critical-path backend tests exist **and pass** (engine, FIFO/import, reconcile, session windows, classifier). `pytest.ini` configures asyncio auto-mode. Test files are well-named + scoped. Guest-mode fixtures double as FE smoke data.
