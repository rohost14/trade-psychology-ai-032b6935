# Connections & Flows — traced map

> Ground-truth map of external connections + runtime flows, built during P0 and deepened in P9. Each row:
> how it's configured, where the client is created, failure/retry behaviour, and 10k-readiness. `⚠` = a
> P0/P1 finding lives here (see phase docs).

## External connections

| Service | Config (env) | Client / where | Failure behaviour | 10k note |
|---|---|---|---|---|
| **Postgres/Supabase** | `DATABASE_URL` | `core/database.py` async engine, PgBouncer txn-pooler (`statement_cache_size=0`, pool 5+10, pre_ping) | `get_db` rollback+raise; `/health` reports | ⚠ pool budget across web+worker instances (B4) |
| **Redis/Upstash** | `REDIS_URL` (`rediss://`) | `core/redis_pool.py` sync pool(20)/async pool(50); Streams, admin_state, rate limit, metrics, error_feed, nonces, caches | mostly fail-open/silent | ⚠ free-tier cmd budget (B3); ⚠ blocking sync calls on loop (P0-F4) |
| **Celery** | `celery_broker` (=REDIS_URL), redbeat | `core/celery_app.py`; Procfile `worker`/`beat` | `acks_late`, `reject_on_worker_lost`, per-task retries+DLQ | ⚠ **queue routing gap orphans 9 beat tasks (P0-F1)**; concurrency cap (B1) |
| **Zerodha KiteConnect** | `ZERODHA_API_KEY/SECRET/REDIRECT_URI`; per-user `BrokerAccount.api_secret_enc` (Fernet); market-data `ZERODHA_MD_*` | `services/zerodha_service`, `price_stream_service` (shared ticker), `order_stream_service`, `api/zerodha.py` OAuth | token daily-expiry; circuit breaker | ⚠ MD token refresh orphaned (P0-F1 #9) → ticker dies daily; ⚠ instrument union cap (B5) |
| **OpenRouter (LLM)** | `OPENROUTER_API_KEY`; models via `admin_settings` | `services/ai_service`, coach, personalization, reports | per-call; batch re-learn = many calls | ⚠ rate-limit/cost under batch (B2/CR4) |
| **OpenAI (embeddings)** | `OPENAI_API_KEY` | `services/rag_service` | RAG degraded if down | P6/P9 |
| **Gupshup WhatsApp** (+ legacy **Twilio**) | `GUPSHUP_*` (+ `TWILIO_*` vestiges) | `services/whatsapp_service` + kill-switch | Meta-approval-blocked; kill-switch gates | confirm graceful-skip (P6) |
| **Web Push / VAPID** | `VAPID_PUBLIC/PRIVATE/EMAIL` | `public/sw.js`, `services/push_notification_service` + kill-switch | best-effort | P6/P10 |
| **SMTP** | `SMTP_*`, `EMAIL_FROM` | admin OTP + watchdog emails only | ⚠ watchdog orphaned via F1 #10 | P9 |
| **Sentry** | `SENTRY_DSN` | `main.py` init, `before_send` filter, 10% traces, PII off | no-op without DSN | OK |
| **WebSocket** | — | `api/websocket.py` `manager`; `event_bus` subscriber bridge | replay on reconnect (`?since=`) | ⚠ per-instance ceiling + fan-out cost (B6/B7); sticky sessions required |

## Runtime flows (source → sink; ⚠ marks a broken/at-risk branch found so far)

1. **OAuth onboarding** — `/api/zerodha/connect`→Zerodha→`/callback`→account+JWT/cookie→signup-gate. *(P4)*
2. **Live trade→alert** — postback→Celery `process_webhook_trade`→TradeSync→PositionLedger(FIFO)→CompletedTrade+features→BehaviorEngine→RiskAlert/BehaviorEvent→event_bus→WS + push/WhatsApp. *(P1/P2/P3)* ⚠ depends on `behavior_events` partitions that F1 #6 stops maintaining.
3. **Market data** — shared KiteTicker→union subscribe→tick fan-out→WS `position_update`/`margin_update`. ⚠ F1 #9: MD token never refreshed → ticker dies daily.
4. **Analytics on-demand** — page→API (indexed)→service; admin aggregates Redis-cached. ⚠ every endpoint blocks loop on rate-limit Redis (P0-F4).
5. **Nightly/batch** — intent re-learn 18:15 · reconcile 04:00 · EOD 15:35 · retention tick 60s · watchdog 5m. ⚠ **most orphaned (F1)**; the ones that run loop all-accounts sequentially (B2).
6. **Tradebook import** — CSV→parse→idempotent upsert→twin-reconcile (no engine run). *(P6)*
7. **AI coach / RAG** — chat→context→embeddings/retrieval→OpenRouter→stream. *(P6)*
8. **Admin** — pw→OTP/TOTP→cookie→IP allowlist→impersonation(read-only mw)→audit. ⚠ brute-force limiter bypassable (P0-F3).
9. **Data rights (DPDP)** — export / hard-delete(cascade) / import. *(P6)*
10. **WS reconnect/replay** — client `last_event_id`→`?since=`→Redis Streams replay→resume. *(P3)*
11. **Constitution/rules** — profile change→`RULE_FIELDS` gate (tighten instant / loosen 409). *(P6)*
12. **Startup** — lifespan: validate Fernet key · warm admin settings · restart ticker · start event subscriber · P&L repair + pnl_pct backfill. ⚠ repair/backfill run every boot, load rows in memory (P0-F14); ⚠ `setup_logging()` NOT called (P0-F2).

## Deploy topology (from Procfile / Dockerfile)
- `web`: `uvicorn app.main:app` (single process per instance; keep-alive 120).
- `worker`: `celery … --pool=gevent --concurrency=100 --queues=trades,alerts,reports` ⚠ default `celery` queue unconsumed (P0-F1); gevent pool + async DB interaction to verify (P3).
- `beat`: `celery … beat --scheduler=redbeat.RedBeatScheduler` (schedule persisted in Redis).
- Dockerfile: single image, default CMD = web; healthcheck curls `/health`; worker/beat via CMD override.
