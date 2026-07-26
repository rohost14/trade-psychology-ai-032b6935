# Load / Performance Harness

Synthetic load — **no real users needed**. Points at any running backend (localhost dev,
or a deployed URL). Three tools:

| Tool | Tests | Bottleneck it exercises |
|---|---|---|
| `seed_load_data.py` | seeds N synthetic accounts + completed trades; writes `tokens.json` | DB volume for analytics |
| `k6_http_ws.js` | ramps virtual users hitting the API + WebSocket | web/API + WS fan-out (B6/B7) |
| `flood_postbacks.py` | enqueues M synthetic fills into the Celery engine path | engine/queue throughput (B1/B2) |

## 0. Prereqs
- Backend running (`uvicorn app.main:app` + a Celery worker + beat + Redis + Postgres).
- k6 installed — https://k6.io/docs/get-started/installation/ (single binary).
- Run from `backend/` with the app's venv (so `import app.*` works).

## 1. Seed data
```bash
# from backend/
python -m scripts.load.seed_load_data --accounts 1000 --trades-per 60
# -> inserts 1000 accounts x 60 completed trades, writes scripts/load/tokens.json
```
Start at **1000**, not 10k. `tokens.json` = `[{account_id, token}, ...]` for k6.

## 2. HTTP + WebSocket load (k6)
```bash
# BASE_URL defaults to http://localhost:8000
BASE_URL=http://localhost:8000 \
k6 run --vus 200 --duration 3m scripts/load/k6_http_ws.js
# ramp: --stage 1m:200,3m:1000,1m:0   (VUs = concurrent users)
```
Each virtual user: dashboard-stats + a rotating analytics endpoint + opens a WebSocket.
k6 prints p95 latency, error rate, req/s. **Pass bar:** p95 < your SLO, error rate < 0.1%.

## 3. Engine throughput (postback flood)
```bash
# from backend/ — enqueues synthetic COMPLETE fills straight into the engine path
python -m scripts.load.flood_postbacks --account-index 0 --count 500 --rate 20
# --rate = fills/sec; watch the SLO + queue while it runs
```

## What to watch (the real signals)
- **Admin → System → engine-metrics → `alert_e2e_lag_ms`** — the SLO. Must stay < 3000ms under load.
- **Celery queue depth** — `redis-cli LLEN trades` (+ alerts/celery/reports). Should drain, not grow unbounded.
- **DB connections** — `SELECT count(*) FROM pg_stat_activity;` vs your pool/pooler cap (B4).
- **Redis command rate** — Upstash console (free-tier budget, B3).
- k6 summary: p95 latency, error rate, throughput.

## Incremental plan
1k → find the first ceiling → fix → 5k → 10k. Don't jump to 10k.

## Running WITHOUT staging (localhost caveats)
Localhost load-testing still finds: engine/queue throughput, DB pool starvation, N+1s,
blocking-I/O stalls (F4), the R1 worker-pool behaviour, analytics latency (Q3). It does
**not** validate: real network/WS at cloud scale, Upstash tier limits, cross-instance
fan-out, KiteTicker instrument caps. Treat localhost numbers as **relative** (before/after
a fix), not absolute capacity. A cheap 1-box cloud staging later gives absolute numbers.
```
```
