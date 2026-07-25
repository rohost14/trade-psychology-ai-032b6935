# P6 — Remaining API + Services (findings)

> **Scope + honest depth:** this bucket is large (16 top-level `api/*` + ~9 services not yet covered). I ran
> a **targeted risk-pass** — full read of the high-consequence paths (DPDP delete/export `account_data.py`,
> coach/LLM `coach.py`+`ai_service.py` surface, notifications/kill-switches, `danger_zone`) — and a
> **cross-cutting sweep** of the CRUD remainder (journal/reports/goals/alerts/cooldown/risk/positions/trades/
> settings/my_record/session_intent) for **auth-scoping, cross-account bypass, and body-param IDOR**. The
> CRUD files were **not** each line-audited; findings below say which got which. **Findings-only.**

## Verdict
Strong security posture on the API surface. The one thing to actively verify is the DPDP hard-delete's dependence on the FK cascade graph (P8). No new correctness bombs found in this pass.

---

## 🟠 P1

### DP1 · DPDP hard-delete depends entirely on a complete `ON DELETE CASCADE` graph — must verify · correctness/compliance (verify P8)
`account_data.py:/delete` does `DELETE FROM users WHERE id = …` (or `broker_accounts` fallback) and **relies on every referencing table cascading** from there (`# every FK cascades from here`). If **any** table that references `users`/`broker_accounts` lacks `ON DELETE CASCADE`:
- the delete **fails with an FK violation → 500 "nothing was deleted"** → the user **cannot delete their account** (DPDP §12 breach), **or**
- (if the FK is `SET NULL`/`NO ACTION` on a nullable col) **orphan rows retain PII** → erasure incomplete (DPDP breach).
Special attention: **`behavior_events` is partitioned** (migration 067) — confirm cascade works across all partitions; and the many per-account tables added over 74 migrations. **Action:** P8 must enumerate every FK into `users`/`broker_accounts` and confirm `ON DELETE CASCADE`. This is the single highest-risk item in P6.

---

## 🟡 P2

### DP2 · Redis purge on account deletion misses the per-account event stream · compliance
> ✅ **FIXED 2026-07-26 (test-first)** — extracted pure `_redis_purge_patterns`; added `stream:{account_id}` (event-replay stream with trade/alert payloads) **and** `rl:acct:{account_id}:*` (the current rate-limit key shape after F3/A1 — the old `rl:{id}:*` no longer matched). `tests/test_dpdp_purge_patterns.py` verifies both. Erasure now covers the event stream.
`_purge_redis_for_account` deletes `rl:`, `margin:`, `dna:`, locks, `ew:`, `circuit:` keys, but **not** `stream:{account_id}` (the event-bus **per-account replay stream**, `event_bus.ACCOUNT_STREAM_PREFIX`), which holds recent trade/alert payloads (symbols, P&L, order ids). After erasure this stream survives until MAXLEN (~500 entries) rotates it out. Also not purged: any `metrics:*`/`admin:error_feed` entries referencing the account. **DPDP erasure is therefore incomplete** for the event stream. **Fix:** add `stream:{account_id}` (and audit the full per-account keyspace) to the purge list.

---

## ⚪ P3
- **P6-1** `coach.py` does not length-cap the user's inbound message before sending to the LLM (only `max_tokens` on output is bounded, 300–1000). Cost is bounded by `coach_limiter` (10/min) but a single huge message inflates input tokens. Add an input length cap.
- **P6-2** `danger_zone_service` has `HARD_COOLDOWN = "cannot skip"`. Since the app **cannot block Zerodha order placement**, this is a UI/notification-level construct, not an execution block — consistent with "mirror not blocker" at the order level, but the wording ("cannot skip") is worth a product check against the philosophy. `danger_zone` routes are mostly status/stats + `trigger-intervention`.

## ✅ Solid (credit — verified this pass)
- **No cross-account IDOR:** swept all 16 api files — **every** endpoint authenticates via `get_current_broker_account_id`/`_verified`/`get_current_user_id` (auth_deps ≥ routes in every file), and **no endpoint reads `broker_account_id` from query/body** (grep clean). Clean tenant-isolation posture.
- **Coach is fully account-scoped:** every context query (`Position`/`RiskAlert`/`JournalEntry`/`UserProfile`) filters `broker_account_id == <caller>` — no cross-user context leak into the LLM.
- **Kill-switches honored:** `push_notification_service` checks `ss.feature_enabled("push")`, `whatsapp_service` `feature_enabled("whatsapp")`, `coach` `feature_enabled("ai_coach")` (403). Global Settings actually gate delivery.
- **DPDP delete friction:** requires typing the exact Zerodha user id, revokes the broker token **first**, audits **before** delete (no PII in the audit), fail-safe ("nothing was deleted" on error), Redis purge after the durable commit.

## Ledger closure (this pass)
- **D7** (archived routers `portfolio_radar`/`guardrails`/`portfolio_chat`) — confirmed: remaining refs are only to the **Celery tasks/services** (`portfolio_radar_tasks`, `position_metrics_service`) in `api/admin/tasks.py`, which are intentionally kept/shared. Routers are dead. **Closed** (the guardrail-tasks compute-waste question stays as D19/F9).
- **D8** (`vix_service`) — 0 live refs (grep clean). Confirmed dead. **Closed.**

## Not fully line-audited (deferred — say the word to deepen)
`journal.py` (598), `reports.py` (532), `daily_reports_service.py` (1027), `goals.py`, `cooldown.py`, `risk.py`, `my_record.py`, `session_intent.py`, `alert_service`/`notification_rate_limiter`/`early_warning`/`alert_checkpoint` internals, `email_service`, `rag_service`. Swept for auth-scoping + bypass (clean); their internal logic (report math, cooldown state machine, RAG retrieval) is a candidate for a deeper targeted pass if you want it.

## For P14 (QA)
FK-cascade delete drill on a fully-populated account (DP1) · post-delete Redis + stream residue check (DP2) · cross-account access attempts on every endpoint (verified clean statically) · kill-switch on/off delivery · coach context isolation.
