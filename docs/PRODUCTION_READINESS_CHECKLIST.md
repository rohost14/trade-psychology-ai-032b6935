# Production Readiness Checklist

> **The objective answer to "are we ready to launch?"** Every item that stands between the
> current build and a safe production deployment. Grounded in the codebase as of 2026-07-25.
> Companion to `PLATFORM_ROADMAP_AUTH_PAYMENTS.md` (the feature spec) — this is the *ship* gate.
>
> **Legend** — priority: **P0** blocks any launch · **P1** before real scale · **P2** polish.
> owner: **You** (business/legal/decisions) · **Dev** (engineering) · **Ext** (Zerodha/Meta/DLT/gateway/lawyer).
> status: `[ ]` todo · `[~]` in progress · `[x]` done.
>
> **Golden rule:** validate live and beta BEFORE building payments. The biggest risk is the
> huge amount already built that has never run against a real Zerodha account.

---

## A. Business & Legal (mostly You/Ext — several are hard blockers)
- [ ] **P0 · Ext/You — Zerodha KiteConnect commercial terms.** Confirm a **paid** third-party behavioural app is allowed on KiteConnect; check per-app cost, per-user limits, and whether partner status is required. *Can invalidate the business model — verify FIRST.*
- [ ] **P0 · You — Registered business entity + GSTIN.** Hard blocker for payments AND SMS DLT. Get this in motion early.
- [ ] **P0 · Ext — Legal review (SEBI posture).** Confirm "behavioural mirror, not investment advice" holds; no buy/sell tips, no assured returns. Disclaimers exist in-app — get a lawyer's sign-off for a money-adjacent product.
- [ ] **P0 · You/Dev — Refund policy** (window, pro-ration, non-refundable period) + published policy page.
- [ ] **P1 · Dev — Terms & Privacy versioning + re-consent** on material change (acceptance record).
- [x] **P0 · Dev — DPDP export + hard-delete** (Settings → Danger Zone). *Done.* Extend to cover billing + guardian data when those ship.
- [ ] **P2 · You — Pricing decided** (Free vs Pro, price points, monthly/annual).

## B. Live Validation & Private Beta (🚩 the #1 technical risk — do this FIRST)
- [ ] **P0 · You/Dev — Full live smoke against a real Zerodha account with real trades.** Verify: sync, live alerts, WS/prices, positions/trades tables, analytics numbers, **behaviour-cost + session-tagging + habits numbers**, cold-start **tradebook import + dedup** (import a range overlapping live days → confirm zero duplicates), My Record, morning-intent/EOD.
- [ ] **P0 · You — Admin panel live check** (needs admin login: JWT secret + 2FA): 10 rebuilt pages, Admins CRUD + forced onboarding, impersonation "view as user", cookie login (esp. prod CORS/SameSite), audit filters/export, System error-feed, **Global Settings** toggles actually take effect.
- [ ] **P0 · Dev — Read `alert_e2e_lag_ms`** (Admin → System → engine-metrics) after live traffic. If avg > 3s SLO → investigate the bottleneck (was deferred pending a real number).
- [ ] **P1 · You — Private beta (5–10 real traders)** for 2–4 weeks. Surfaces real-world bugs + validates the core loop (do the alerts change behaviour?) cheaply, before payments.
- [ ] **P1 · Dev — Fix everything beta surfaces.** Expect a backlog.

## C. Scale & Performance (P1 — unproven above a handful of users)
- [ ] **P1 · Dev — KiteTicker / WebSocket fan-out under load.** Per-connection limits, how many concurrent price streams, reconnect storms. *Never load-tested.*
- [ ] **P1 · Dev — Celery throughput** under a burst of postbacks/trades (watchdog now alerts on backlog > 2000; validate real numbers).
- [ ] **P1 · Dev — Load test** the user hot paths + WS at target concurrency (e.g. 1k, then 10k).
- [x] **P1 · Dev — DB indexes** on hot tables + admin-aggregate polish (021/031/043/067 + migration 073). *Done — verify query plans under real data volume.*
- [x] **P1 · Dev — Admin aggregate caching** (overview/insights Redis-cached). *Done.*
- [ ] **P1 · Dev — Upstash Redis limits** (connection count, command budget) validated at scale.

## D. Deployment & Config (P0 — missing env → silent degradation)
- [ ] **P0 · Dev — Apply migrations 072, 073, 074** in prod (074 = admin_settings; feature works on defaults until applied).
- [ ] **P0 · You/Dev — Required env set:** `DATABASE_URL`, `SECRET_KEY`, `ENCRYPTION_KEY` (fail-fast if missing), `ZERODHA_API_KEY/SECRET`, `REDIS_URL` (Upstash, not localhost).
- [ ] **P0 · Dev — `BACKEND_CORS_ORIGINS`** = actual prod frontend origin (else app is blocked / admin cookie fails).
- [ ] **P0 · Dev — `ADMIN_JWT_SECRET`** set (else all `/api/admin/*` 404 silently).
- [ ] **P1 · Dev — `SENTRY_DSN` (+ `VITE_SENTRY_DSN`)** set (else no error visibility in prod).
- [ ] **P1 · Dev — `VAPID_*` keys** set (else push silently fails).
- [ ] **P1 · Dev — Admin cookie in prod:** `ADMIN_TRUST_PROXY_HEADERS` if behind a proxy; SameSite=None+Secure requires HTTPS + frontend origin in CORS.
- [ ] **P0 · Dev — Rotate any dev/test credentials**; secrets in a manager, not on disk; `ENCRYPTION_KEY` backed up (losing it = all broker tokens undecryptable).
- [ ] **P1 · Dev — Celery worker + beat running** in prod (postback processing, scheduled tasks, watchdog).
- [ ] **P1 · Dev — Zerodha postback URL** configured in the Kite app to the prod webhook.

## E. Third-party Approvals (⏳ external timelines you don't control)
- [ ] **P1 · Ext — WhatsApp (Gupshup/Meta) template approval.** Guardian alerts + broadcasts + WhatsApp OTP blocked until then.
- [ ] **P1 · Ext — SMS DLT registration** (TRAI: sender ID + templates) for SMS OTP. Needs the business entity.
- [ ] **P0 · Ext — Razorpay account + KYC** (needs entity/GST) before any payment work goes live.
- [ ] **P1 · Ext — Transactional email domain** (SPF/DKIM/DMARC) on the chosen provider.

## F. Security (P0/P1)
- [x] **P0 · Dev — Admin auth hardening** (authz, 2FA lockout, TOTP replay, constant-time OTP, IP allowlist, httpOnly cookie, session-epoch). *Done.*
- [ ] **P1 · Dev — User-side rate limiting** review (some exists; cover auth/OTP/checkout when built).
- [ ] **P1 · Ext — Security review / light pen test** before public launch (auth, payments, admin, impersonation surfaces).
- [ ] **P1 · Dev — Dependency audit** (`npm audit`, `pip-audit`) + a plan to keep current.
- [ ] **P2 · Dev — Move admin JWT localStorage→cookie: done; revisit user-token storage** when user auth is built.

## G. Observability & Ops (P1)
- [x] **P1 · Dev — Sentry (ErrorBoundary), admin error-feed, health watchdog** (DB/Redis/error-spike/queue-backlog → emails superadmins). *Done — wire `SENTRY_DSN` (D).* 
- [ ] **P1 · Dev — Uptime / external monitoring** (health endpoint pinged; alert on down).
- [ ] **P0 · Dev — DB backups + tested restore** (Supabase/managed PG) + documented DR.
- [ ] **P1 · You — Real support inbox + process.** `SUPPORT_EMAIL` is currently a placeholder (`support@tradementor.ai`) — create the mailbox and swap the constant (`src/lib/support.ts`).
- [ ] **P2 · You — On-call / incident runbook** (who responds, how).

## H. QA & Testing (P1 — coverage is thin)
- [ ] **P1 · Dev — Integration tests in CI** (needs a test Postgres): admin IAM guards (last-superadmin/self-mutation), auth flows, billing webhooks.
- [ ] **P1 · Dev — E2E smoke** (Playwright) on the critical path: connect → dashboard → alert → analytics.
- [ ] **P1 · Dev — Frontend admin render-smoke** (mock harness like the analytics smoke suite).
- [ ] **P1 · Dev — Load test harness** (ties to C).
- [x] **P2 · Dev — Lint gate usable** (0 errors) + unit tests for new logic (habits/dedup/admin-deps). *Done.*

## I. The 5 feature phases (from the roadmap — build in order; each ends production-usable)

### Phase 1 — Auth foundation (P0 · Dev) — *no payment dependency; unblocks accounts*
- [ ] Email+password signup/login (bcrypt; reuse admin pattern).
- [ ] Email verification (token/OTP; limited access until verified).
- [ ] Forgot / reset password (single-use token, TTL, rate-limited, no enumeration).
- [ ] "Sign in with Zerodha" (exists) → link to account, don't duplicate on email match.
- [ ] Sessions: refresh token + `session_epoch` on User + logout-all; rotate on password change.
- [ ] Change password / change email (re-verify).
- [ ] Data model: User += password_hash/email_verified_at/phone/session_epoch; reset + verification token tables.
- [ ] Edge cases: enumeration, brute-force lockout, Zerodha-vs-manual email merge, unverified login policy, token reuse/expiry, delete→re-signup.

### Phase 2 — Verification (P0/P1 · Dev + Ext)
- [ ] SMS OTP provider integrated (MSG91/Gupshup/Twilio) — **after DLT (E)**.
- [ ] User phone verification (send/verify, resend cooldown, per-account+IP limits, replay guard).
- [ ] Guardian OTP + **consent record** (third-party DPDP) + revoke + STOP handling.
- [ ] Optional user 2FA (reuse admin TOTP).
- [ ] Edge cases: OTP brute-force, resend flood, provider outage → fallback channel, number reuse, international/DND.

### Phase 3 — Monetization core (P0 · Dev + Ext)
- [ ] Plans (Free/Pro) + **entitlements** enforced backend (403 + upsell) and frontend (lock/upsell).
- [ ] Razorpay checkout (order/subscription) + **signature-verified webhook = source of truth**.
- [ ] Subscription lifecycle: trialing/active/past_due/cancelled/expired.
- [ ] GST invoices (18%, sequential numbering, store+email+download; GSTIN capture).
- [ ] `webhook_events` idempotency + out-of-order handling.
- [ ] Edge cases: webhook replay/signature/order, lost-webhook reconciliation job, double-charge, RBI e-mandate.

### Phase 4 — Billing depth (P1 · Dev)
- [ ] Refunds (full/partial/pro-rated) + credit note + refund webhook.
- [ ] Dunning: smart retries, grace period, reminder emails, auto-downgrade (keep data).
- [ ] Coupons (%/flat, expiry, usage limits, first-time-only).
- [ ] Trials (X-day, one-per-user/phone abuse guard, trial-ending email).
- [ ] Upgrades/downgrades + proration + price-change grandfathering.
- [ ] **Reconciliation job** (nightly, against Razorpay) for lost/partial events.
- [ ] Edge cases: chargebacks, mandate revoke, card expiry, tax-on-refund, delete-account-with-active-sub.

### Phase 5 — Polish (P1/P2 · Dev)
- [ ] Transactional email suite (welcome/verify/reset/receipt/payment-failed/trial-ending/guardian-consent) on a deliverability provider.
- [ ] Admin billing panel (subscriptions, payments, issue refunds, dunning view).
- [ ] Terms/Privacy versioning + re-consent.
- [ ] Feature-matrix finalised + downgrade = graceful lock (never data loss).

---

## J. Pre-launch gate (final flip)
- [ ] All **P0** above closed.
- [ ] Live smoke + private beta passed; SLO (`alert_e2e_lag_ms`) green.
- [ ] Migrations applied; env verified; backups tested; monitoring live; support inbox real.
- [ ] Zerodha commercial terms + business entity + Razorpay live confirmed.
- [ ] Staged rollout plan (private → invite → open) written, not a big-bang launch.

---

## Honest note
No checklist guarantees zero incidents — a system this size, once live, *will* surface issues.
The goal here is to **de-risk with staging + validation**, not to pretend it's bug-free. Ship to a
small ring first, watch, then widen.
