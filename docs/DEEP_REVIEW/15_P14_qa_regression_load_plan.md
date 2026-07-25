# P14 — QA Regression + Performance/Load Test Plan (runnable)

> Turns the review's findings into an **executable** verification plan. Each item = what to run + the pass
> bar + which finding it guards. Ordered so the **cheapest checks that catch the worst regressions** run
> first. Existing assets called out (`scripts/validate/*`, `replay_*`, `simulate_trader_environment.py`).

## Gate 0 — make findings visible before testing anything (infra)
These must exist for the rest of the plan to mean anything:
1. **CI pipeline (CFG3):** GH Actions — FE `typecheck`+`lint`+`vitest`+`npm audit`; BE `python -c "import app.main"`+`pytest`+`pip-audit`. Gate merges. Run on **Python 3.11** (match Docker, CFG5/T2).
2. **Pin + lock deps (CFG2/CFG1):** freeze backend `requirements`, `npm audit fix` (bump axios / React Router / **DOMPurify**), re-run audits to zero HIGH.
3. **Staging env** mirroring prod tiers (paid Redis, pooled Postgres, real worker) — hard dependency for Gates 3–4.

## Gate 1 — Functional regression (mostly exists; extend)
Run `pytest` (402 tests; 109 money/engine already green). **Add:**
| Test | Asserts | Guards |
|---|---|---|
| Golden P&L dataset (LONG/SHORT, partial, multi-round, MCX×mult, CDS) | realized ₹ exact, raw (no charges) | money-math baseline |
| **Product-mixed MIS+NRML same symbol** | two positions NOT netted; per-round P&L correct | **M1** |
| **Flip long→short→cover** | flip-opened round produces a CompletedTrade live | **M2** |
| **MCX unrealized** via `/unrealized-pnl` | ×multiplier applied | **M3** |
| Untabulated MCX contract | falls back to Position.multiplier, not 1 | M5 |
| **`behaviour-cost` after import/replay** | totals stable, links not nulled | **Q1/E2** |
| Double-postback + re-import + late-fill replay | no dup trades/alerts; idempotent | idempotency |
| Constitution tighten/loosen | tighten instant, loosen next-session | constitution |
| 28-detector replay (`scripts/validate/01-07` + extend) | each fires on trigger, silent otherwise; `trigger_completed_trade_id` set | engine |
| Engine context-load failure | increments a visible counter (not silent) | E3 |

## Gate 2 — Security regression
| Test | Asserts | Guards |
|---|---|---|
| Cross-account access (mismatched `bid`, tampered JWT) | 401/403, no data leak | tenant isolation (clean statically) |
| **XFF-rotate on user endpoints** | rate limit still holds (currently DOESN'T) | **F3/A1** |
| **Admin CSRF probe** (cross-site POST w/ cookie) | blocked | **A2** |
| Admin brute-force (password + OTP, many IPs) | per-email lockout holds | A1 (admin OK) |
| **`npm audit` / `pip-audit`** | 0 HIGH | **CFG1/CFG2** |
| Impersonation write attempt (any non-GET) | 403 | impersonation mw |
| Response headers/CSP present; CORS origin enforced (no private-IP in prod) | pass | F8 |
| Secrets not in logs/Sentry/image | pass | A6, dockerignore |
| **DPDP delete drill** on a fully-populated account | 0 orphan rows across every table; `stream:{id}` purged | **DP1/DP2** + run the `pg_constraint` query (P8) |

## Gate 3 — Real-time / integration (staging + real/sandbox Zerodha — the never-run gap)
| Test | Pass bar | Guards |
|---|---|---|
| OAuth connect→callback→JWT | account row + cookie | user auth |
| Live postback → alert in browser | `alert_e2e_lag_ms` < 3s | SLO |
| WS drop → `?since=` replay | missed events, no dupes | WS design |
| Daily token-expiry (~6am) → reconnect at open | ticker recovers | R7 |
| **MD token refresh** fires + ticker survives | live prices next day | **F1#9/R7** |
| **Every scheduled task actually runs** (reports, intent, partitions, watchdog) | executed, not queued-orphaned | **F1** |
| Push + WhatsApp fallback (WS offline) | push sent; WhatsApp graceful-skip (Meta-blocked) | comms |
| **Chaos: kill each dependency** (Redis / OpenRouter / SMTP / Sentry) | matches P9 down-matrix; **Redis-down = pipeline behaviour understood** | **N1**, P9 |

## Gate 4 — Performance / load (staged 1k → 5k → 10k, on prod tiers)
**Do R1 FIRST — it may invalidate everything else:**
| Test | Pass bar | Guards |
|---|---|---|
| **Worker pool decision** — prefork vs gevent under market-open burst | no asyncpg/loop errors; queue drains; pool not starved | **R1/N2/B1** |
| Live fill volume (100k–500k engine tasks/day, 09:15 burst) | `alert_e2e_lag_ms`<3s@p95; queue drains within hours | B1 |
| Batch fan-out timing @1k/10k accounts (intent/reconcile/EOD) | completes off-peak; per-account sessions | R4/B2/CR1 |
| WebSocket N concurrent/instance | mem/fd/loop-lag bounded; fan-out cost within Redis budget | B6/B7 |
| KiteTicker instrument-union growth | shard before per-conn cap; no dropped ticks | B5/CR2 |
| Redis command rate vs tier | within paid budget | B3/N1 |
| DB connections across web+worker | ≤ pooler cap; no pool_timeout | B4 |
| Analytics endpoints @10k w/ 180d histories | p95 latency ok; add cache if not | Q3 |
**Tools:** Locust/k6 (HTTP+WS), a Celery flooder (task path); extend `simulate_trader_environment.py` / `reproduce_position_lag.py`. **SLOs:** p95 API < target, alert e2e < 3s, 0 dropped ticks, error rate < 0.1%, queue drains in market hours — all **green at 10k on the target tier** (not free tier).

## Exit criterion
Prod-ready when: Gates 0–2 green in CI, Gate 3 green on staging vs a real Zerodha account (**closes the biggest gap — nothing here is runtime-tested today**), and Gate 4 green at 10k on sized infra. Map results back to `PRODUCTION_READINESS_CHECKLIST.md`.
