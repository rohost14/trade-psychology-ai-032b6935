# PENDING — single source of truth

Updated 2026-07-29. Branch `dashboard-production-readiness`, CI green, working tree clean.
**Nothing is code-blocking.** Everything below is your action or Zerodha/business.

---

## ✅ Done (code complete, pushed, CI-green)

- 8 runtime crashes fixed (httpx-loop, portfolio_sync ×2, sync no-rollback, BrokerAccount
  scope shadow, reconcile asyncio, tag-length harness).
- Full CI net taxonomy live: compileall · pyflakes · import-smoke · mypy (advisory) ·
  **Postgres+Redis integration** (full DB suite runs every push) · pip-audit · FE typecheck/lint/test.
- mypy triage (192→63); 3 real attr-defined bugs fixed (`whatsapp_service.send_alert`→`send_message`).
- `portfolio_radar_tasks` archived (was broken).
- **M1** — product is part of the position key; MIS/NRML same symbol no longer net.
  Migration 075 **applied**. (Live confirmation = Gate 3.)
- **Market-data feed hardening** — dedicated `ZERODHA_MD_*` account + auto TOTP token
  refresh already coded (dormant); added loud alert + `md_token_unavailable` metric on
  silent degradation.
- **Model A auth** — BYO-key flow retired; one platform Kite Connect app (`ZERODHA_API_KEY`)
  via OAuth for all users.
- Docs: `PRODUCTION_MARKET_DATA_PLAN.md`, this file.

---

## ⛔ Pending — YOUR action (ordered by priority)

### 1. Zerodha multi-user approval — THE #1 go-live gate
- A standard Kite Connect app is **bound to the owner's client id** → only YOU can log in.
- Multi-user (real users) needs **Zerodha compliance approval**: email `kiteconnect@zerodha.com`
  with product details. Granted only to mass-market platforms.
- **Confirm in that email:** (a) one app serving many users — approval + process; (b) who pays
  the API fee (platform vs each user); (c) one-account market-data streaming to all users allowed;
  (d) any concurrent-user cap. (Full list: `PRODUCTION_MARKET_DATA_PLAN.md` §6.)
- Until approved: **solo-login only** (fine for testing).

### 2. Gate 3 — live validation (solo, when market open)
- Log in with your Zerodha account.
- Open positions show + update **real-time** (sub-second) as price moves.
- Alerts fire **real-time** and are **accurate / non-ambiguous**.
- Verify **M1**: same symbol in MIS + NRML shows two positions with correct P&L.
- (Optional now) validate the MD auto-login once `ZERODHA_MD_*` is set (#3).

### 3. Provision the dedicated market-data account
- A real Zerodha account (your own works) + a Kite Connect app + TOTP 2FA secret.
- Set 5 env vars in `backend/.env`: `ZERODHA_MD_API_KEY/API_SECRET/USER_ID/PASSWORD/TOTP_SECRET`.
- Restart → feed logs `dedicated-md-account`, no more 403 reconnect noise.
- Steps: `PRODUCTION_MARKET_DATA_PLAN.md` §2.

### 4. Business / legal
- Business entity + GST · pricing decision · Meta/WhatsApp (Gupshup) approval ·
  replace placeholder `SUPPORT_EMAIL` (`support@tradementor.ai`).

---

## ⏸️ Deferred — not now, planned

| Item | When / trigger | Notes |
|---|---|---|
| Model-A key refactor (remove per-user key remnants) | after Zerodha #1 says yes | small code change; I do it then |
| Ticker cluster (gap #2) | ~2500+ distinct subscribed instruments | scale tier; `PRODUCTION_MARKET_DATA_PLAN.md` §3 |
| Redis position read-cache in front of the ledger (write-through, Postgres stays truth) | Gate-4 / only after a load test *measures* `get_position` Postgres reads as a real bottleneck | **Latency-only, not correctness.** DO NOT ship blind — it adds a stale-cache failure mode to money-critical P&L. Correct invalidation must cover **every** write path: webhook fill, sync, reconcile, and especially the **out-of-order replay** (which rewrites *past* ledger entries → a naive current-position cache goes wrong). Localized seam (`PositionLedgerService.get_position`), so deferring costs nothing — easy to add when justified + validated. |
| Gate 4 — 10k load test | paid staging infra | free tier can't; local flood already validated the engine |
| Stale-price indicator (FE) | dashboard polish | minor UX; illiquid-option LTP freeze |
| 09:15 thundering-herd tuning | under a real load test | parallelize sequential all-account loops |
| mypy → blocking | after typing pass | currently advisory (catches real attr-defined among noise) |

---

## 🚀 Launch / Infrastructure / Ops — the "ship it" checklist (mostly NOT done)

> Hosting chosen by REQUIREMENTS (not by what the repo assumes): the app needs an
> **India region** (real-time, Zerodha + Indian users), **long-lived WebSockets**
> (shared KiteTicker + fan-out), **always-on background processes** (Celery worker +
> beat, not serverless), and **low solo-founder ops**.
>
> **Recommendation — launch on Fly.io (Mumbai `bom`)**: container-native, great WS,
> runs always-on worker+beat, India region, cheap, solo-friendly.
> **Simpler alt:** DigitalOcean App Platform (Bangalore). **Scale/enterprise target:**
> AWS ECS **Fargate** (Mumbai ap-south-1) — migrate later if needed (containers either way).
> **Avoid:** Render (Singapore only, spin-down), raw EC2 (ops burden), Cloud Run
> (awkward for always-on Celery + long-lived WS), Cloudflare Workers (can't run FastAPI/Celery).
> **Keep:** Supabase (Mumbai) + Upstash. **Frontend:** Cloudflare Pages / Vercel.

### Hosting / deploy
- [ ] **Backend on Fly.io (Mumbai)** — one app with 3 process groups (web / worker / beat)
      via `fly.toml`; scale worker independently. NOT set up yet.
- [ ] **Frontend on Cloudflare Pages / Vercel** — connect git, auto-build React.
- [ ] Confirm **Supabase** (already used) is on a paid tier for prod (backups, no pausing),
      **Mumbai region**.
- [ ] Confirm **Upstash** tier for prod (free-tier command cap throttles at scale).
- [ ] **Auto-deploy (CD)** — GitHub → Fly (`flyctl deploy` / GitHub Action) + Cloudflare
      Pages on push to `main`. (CI already exists + green; CD is the missing half.)

### Domain / DNS / SSL
- [ ] **Buy a domain** (you don't have one — `tradementor.ai` is only a placeholder in code).
- [ ] Put **Cloudflare** in front as DNS + CDN + DDoS.
- [ ] Point app + api subdomains at Fly/Pages; **SSL/TLS** auto (Fly certs + Cloudflare).
- [ ] Set the real domain in `FRONTEND_URL`, `ZERODHA_REDIRECT_URI`, CORS origins.

### Email
- [ ] **Domain mailbox** (support@, hello@) — Google Workspace or Zoho Mail.
- [ ] **Transactional email sender** — Resend / Postmark / SES (for receipts once payments,
      support, admin OTP if used).
- [ ] **SPF + DKIM + DMARC** DNS records (deliverability — or mail lands in spam).
- [ ] Replace placeholder `SUPPORT_EMAIL` everywhere.

### Staging environment (you have none)
- [ ] A **staging Fly.io app** + staging Supabase/Upstash (or Supabase branch DB).
- [ ] Used for: pre-prod smoke, Gate-3 rehearsal, Gate-4 load test (paid infra).

### Git / CI / CD (you're new to GitHub)
- [ ] Learn basic git flow (branch → commit → push → PR). CI runs automatically on push.
- [ ] **CI = DONE & green** (`.github/workflows/ci.yml`).
- [ ] **CD = NOT done** — wire Fly.io + Cloudflare Pages auto-deploy on merge to `main`.
- [ ] Branch protection on `main` (require CI green before merge).

### Secrets / config
- [ ] Move all secrets to the host's secret store (Fly secrets / env), never commit `.env`.
- [ ] **BACK UP `ENCRYPTION_KEY`** in a password manager — if lost, ALL Fernet-encrypted
      broker data is unrecoverable. Critical.
- [ ] VAPID keys, `ADMIN_JWT_SECRET`, `SECRET_KEY`, all `ZERODHA_*`, `TWILIO_*`,
      `OPENROUTER_API_KEY` — set per environment.

### Monitoring / alerting / backups
- [ ] **Sentry** — already wired (errors). Confirm prod DSN + alert routing.
- [ ] **Uptime monitor** — UptimeRobot / BetterStack pinging `/health`.
- [ ] **DB backups** — Supabase auto-backup (paid tier) + verify a restore once.
- [ ] Redis is ephemeral (fine to lose) — nothing to back up.
- [ ] Admin **health watchdog** already runs (beat task) — confirm it can notify you.
- [ ] Log retention / access (Fly logs; consider a log drain later).

### Product analytics / support
- [ ] Product analytics (PostHog / GA4) — see activation, retention, funnels.
- [ ] Support/feedback channel (email + maybe an in-app widget).
- [ ] Basic onboarding flow polish (empty-state → first value; Kite = no history).

### Cost planning (rough monthly, verify current)
- [ ] Fly.io (backend: web + always-on worker/beat) · Supabase (paid) ·
      Upstash (paid) · domain · Google Workspace · Sentry · **Kite Connect ₹2000/app** ·
      Twilio WhatsApp · payment-gateway fees. Tally before pricing the product.

---

## 📱 Mobile app (Capacitor → iOS + Android) — NOT started, MAJOR epic

The product is **mobile-first**; today only a React web app exists. Wrapping it native
with Capacitor is a large body of work with real technical hurdles (not just "wrap and ship").

### Capacitor shell
- [ ] Add Capacitor (`@capacitor/core`, `/ios`, `/android`), `capacitor.config.ts`, wrap the Vite build. NOT installed.
- [ ] App icons, splash screen, status bar, **safe-area insets**, Android hardware back-button.
- [ ] iOS + Android project scaffolding (`ios/`, `android/`).

### The hard technical items (these bite)
- [ ] **Native push** — current web **VAPID won't work in a native app.** Need **FCM (Android)
      + APNs (iOS)** via `@capacitor/push-notifications` + Firebase; backend must send to
      FCM/APNs device tokens (not just web-push subscriptions). Migrate `pushNotifications.ts`.
- [ ] **OAuth deep-linking** — Zerodha's redirect must return **into the app**, not a browser.
      Needs a **custom URL scheme + universal links** (iOS `apple-app-site-association`) and
      **App Links** (Android `assetlinks.json`) hosted on your domain, and `ZERODHA_REDIRECT_URI`
      pointing at it. This is the trickiest part of a broker OAuth mobile flow.
- [ ] **Secure token storage** — JWT is in `localStorage` (`BrokerContext.tsx:95`); a webview's
      localStorage is weak for a fintech. Move to `@capacitor/preferences` / a secure-storage plugin.
- [ ] **Biometric unlock** (Face ID / fingerprint) — expected for a finance app.
- [ ] **Forced-update / OTA** — a min-supported-version gate + optional live updates (Capgo/Appflow).
- [ ] **Mobile crash/analytics** — Sentry mobile SDK + Firebase/PostHog mobile.

### App store / release
- [ ] **Apple Developer account** ($99/yr) + **Google Play Console** ($25 once).
- [ ] Store listings — name, icon, **screenshots**, description, keywords (ASO).
- [ ] **Apple privacy nutrition labels** + **Google Play Data Safety form** (must match real data use).
- [ ] **App review prep** — Apple/Google scrutinise broker/finance apps; prepare the justification
      (it's a **read-only mirror/journal — never places trades**, which helps review a lot).
- [ ] Age rating, EULA (Apple standard or custom), encryption/export-compliance declaration.
- [ ] Host deep-link association files (`apple-app-site-association`, `assetlinks.json`) on the domain.

> **CDN note:** web frontend/landing → served via CDN (Cloudflare Pages/Vercel, free).
> API/WebSocket → NOT cacheable, no CDN. Mobile app assets → bundled in the binary, no CDN.
> OTA update bundles (if used) → via the OTA provider's CDN.

---

## 🧩 Product / Business / Legal — pending (not built, or needs review)

### Monetization — NOT built (biggest gap for going paid)
- **Payment gateway** — Razorpay (India) integration. Nothing exists today.
- **Subscription plans / tiers**, billing cycle, renewal, upgrade/downgrade.
- **GST invoicing** (needs business entity + GST reg first).
- **Paywall / feature-gating** by plan.
- **Refund / cancellation** flow.
- Spec exists (not built): `docs/PLATFORM_ROADMAP_AUTH_PAYMENTS.md`.

### Notifications / accountability
- **WhatsApp** — built on **Twilio** (`whatsapp_service.py`), currently **SAFE MODE (logging only)** — no creds set. To go live: **Twilio WhatsApp Business sender approval + message templates** (the real blocker), then set `TWILIO_*` env. (Memory's "Gupshup" note is stale — code is Twilio.)
- **Accountability loop** — *partially* built: cooldown / circuit-breaker, alert-response metric, goal-change logging. **Partner-dispatch (alert to an accountability partner) depends on WhatsApp** → blocked until WhatsApp is live.
- **Push notifications** — built (web push / VAPID), works.

### Legal / compliance — pages exist but NOT vetted
- **Terms of Service + Privacy Policy pages exist** (`TermsOfService.tsx`, `PrivacyPolicy.tsx`) and a `ComplianceDisclaimer` component is shown on Analytics/Chat — **but they are self-authored placeholders, NOT lawyer-reviewed.** Get them legally reviewed before launch.
- **SEBI positioning (the big one):** a P&L / behavioural-analytics product must be clearly positioned as a *mirror / journaling tool*, **NOT** investment advice or research-analyst services (which need SEBI registration). Needs a **legal opinion** on positioning + disclaimer wording. `ComplianceDisclaimer` must be vetted.
- **Privacy Policy must reflect DPDP** — data export/delete already exist (`/api/account/export|delete`); the policy text must match reality + Zerodha data handling.
- **Grievance / support mechanism** — a named contact + process (consumer/SEBI expectation). Replace placeholder `SUPPORT_EMAIL`.

### Auth (beyond Zerodha OAuth)
- Currently **Zerodha-OAuth-only by design** (no email/password). Roadmap has an optional email/OTP auth spec (not built) — only needed if you want non-Zerodha onboarding; otherwise skip.

### Onboarding / cold-start (product)
- **Kite gives no trade history** → new users land empty. Cold-start import surfacing exists (Console CSV import); keep refining the empty-state → first-value flow.

---

## Hard product constraints (govern all future work)
1. **Kite gives NO trade history** — today-only; new users start empty; only fix = Console CSV import.
2. **Zero manual-input adoption** — never design features that need the user to type/tap.
