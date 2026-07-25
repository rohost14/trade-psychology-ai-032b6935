# P9 — External Connections & Integrations (findings)

> Scope: each external dependency traced config→client→failure→prod-readiness, plus a "what breaks if it's
> down" matrix. Most connection-level defects already surfaced in P0/P3/P4 — this phase **consolidates** +
> adds the dependency-failure analysis. **Findings-only.**

## Verdict
Client-level failure handling is **mature**: httpx timeouts everywhere, a real **circuit breaker** on Kite, failure-isolated comms, fail-open/fail-closed choices that are mostly deliberate. The gaps are the already-filed ones (F4/F6/R1/R7/A6/A8/B3/B4/MIG1) plus two new observations below.

---

## 🟠 P1 (new framing)

### N1 · Redis is load-bearing for the live trade pipeline, not just cache · availability
Redis-down is handled *gracefully* for most consumers (event_bus fail-silent, rate-limit fail-open, admin_state→env fallback, metrics best-effort, admin blocklist fail-**closed** by design). **But** the trade pipeline's **`fifo_lock` + `behavior_lock`** (`trade_tasks`) and the **Celery broker itself** are hard Redis dependencies: if Redis is down, `_acquire_lock` fails → detection is requeued/retried and Celery can't dispatch at all → **the live postback→alert pipeline stops**. Combined with **B3** (Upstash free-tier budget) this makes Redis a **single point of failure for the core product loop**, not a soft cache. **Fix/plan:** treat Redis as tier-1 infra (HA/managed, monitored, budgeted); document the degraded behaviour; consider a DB-based lock fallback for the pipeline if Redis is the SPOF you can't remove.

---

## 🟡 P2

### N2 · Cached `httpx.AsyncClient` reused across per-task event loops (ties to R1) · correctness
`zerodha_service._get_client` caches a single `httpx.AsyncClient(timeout=10)` on `self._client`. httpx clients are **event-loop-bound**. In the FastAPI process (one loop) this is fine; but the same service is called from **Celery tasks via `asyncio.run()` (a new loop per task, P3-R1)** — a client created on a previous, now-closed loop raises "Event loop is closed"/transport errors on reuse. Same root cause as R1 (async objects vs loop-per-task). **Fix:** don't cache loop-bound clients across `asyncio.run` boundaries — create per-call, or fix the worker pool (R1) so there's a stable loop.

### N3 · No retry/backoff on OpenRouter / OpenAI calls · resilience
`ai_service` makes a **single** httpx attempt (timeout 30s/60s) then logs + returns a fallback. A transient 429/5xx/blip → failed coach/personalization response with no retry. Acceptable for interactive chat (user retries) but add a bounded retry for the batch/report paths. Also: no cost/rate-limit budget guard around OpenRouter (B-tier concern for batch load).

---

## Dependency-down matrix (what actually breaks)
| Dependency | Down behaviour | Severity |
|---|---|---|
| **Postgres/Supabase** | everything fails (`get_db` raises, `/health`→503) | hard SPOF (expected) |
| **Redis/Upstash** | **live pipeline stops** (locks + Celery broker); reads/WS degrade gracefully; admin locked out (fail-closed) | **N1 — tier-1 SPOF** |
| **Celery workers** | postbacks queue but never process → no alerts; watchdog would warn (but watchdog itself orphaned per P0-F1) | high |
| **Zerodha Kite** | circuit breaker opens (degraded mode), token-expired distinguished; ticker dies (R7) | handled + R7 |
| **OpenRouter** | coach 403/5xx handled, personalization degrades | graceful (N3) |
| **OpenAI (embeddings)** | RAG degrades | graceful |
| **Gupshup/Twilio** | `is_configured`→skip; Meta-blocked already | graceful |
| **Web Push/VAPID** | best-effort skip | graceful |
| **SMTP** | admin OTP + watchdog email fail (login 2FA blocked if email-OTP path) | medium — admins on TOTP unaffected |
| **Sentry** | no-op without DSN | none |

## ✅ Solid (credit)
Kite **circuit breaker** (CLOSED/OPEN/HALF_OPEN, >50%/60s trip, 60s cooldown, probe) is textbook and per-account. httpx timeouts on every external call. Auth errors excluded from tripping the breaker (correct — token expiry ≠ infra failure). Comms (whatsapp/email/push) are failure-isolated + config-gated + kill-switch-gated. Postback verification + idempotency (P3) make retries safe.

## Consolidated connection findings from earlier phases (carried into P15)
P0-F4 blocking sync Redis on the loop · P0-F6 Celery broker TLS `CERT_NONE` · P3-R1 gevent+asyncpg worker pool · P3-R5 blocking Redis in task loop · P3-R7 borrowed MD token + orphaned refresh + no ticker instrument cap · P4-A6 transient plaintext api_secret in Redis · P4-A8 single `ENCRYPTION_KEY`, no rotation · B3 Upstash free-tier budget · B4 DB pool/pooler sizing · MIG1 no migration tracking.

## For P14 (QA / chaos)
Kill each dependency in staging and assert the matrix above (esp. **Redis-down = pipeline behaviour**, N1) · OpenRouter 429/5xx injection (N3) · Kite circuit-breaker trip+recover · SMTP-down admin login via TOTP path · httpx-client reuse under the chosen worker pool (N2/R1).
