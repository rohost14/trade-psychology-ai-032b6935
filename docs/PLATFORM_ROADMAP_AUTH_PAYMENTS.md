# Platform Roadmap — Auth, Verification, Subscriptions & Billing

> **Status: PLANNING DOC. Nothing implemented.** Grounded in the codebase as of 2026-07-25.
> This is the spec for everything a Sensibull-grade platform has that TradeMentor does not yet —
> to be built slowly, phase by phase. Each section = current state → gap → spec → edge cases.

---

## 0. Current state (verified in code)

| Area | What exists today |
|---|---|
| **User auth** | **Zerodha OAuth only.** `/api/zerodha/connect` → Kite login → `/api/zerodha/callback` creates/loads `User` (keyed by Zerodha email) + `BrokerAccount`, issues a JWT (`sub`=user_id, `bid`=broker_account, 24h). **No password, no email/password login, no recovery.** |
| **Token lifecycle** | App JWT 24h; Zerodha access token expires daily (~6am IST) → user must re-connect. `token_revoked_at` on BrokerAccount. |
| **Admin auth** | Separate, mature: email + password (bcrypt) → email OTP / TOTP → JWT, IP allowlist, session-epoch revoke, httpOnly cookie. (Not reused for users yet — good reference implementation.) |
| **Identity (`User`)** | `email` (unique, from Zerodha), `display_name`, `avatar_url`, guardian fields. **No `password_hash`, no user phone, no `email_verified`, no plan/subscription.** |
| **Guardian (accountability partner)** | `guardian_phone`, `guardian_name`, `guardian_confirmed(_at)`, `guardian_loss_limit`. A WhatsApp **consent request** exists (`profile.py`) but WhatsApp is **blocked on Meta template approval**, and there is **no robust OTP verify loop**. Number change re-invalidates consent. |
| **Comms** | Push (VAPID, works). WhatsApp (Gupshup/Twilio — blocked on Meta approval). Email (admin OTP only — **no user transactional email**). |
| **Payments / subscription / billing** | **NONE.** No plans, gateway, invoices, or refunds. Product is effectively free/unbilled. |
| **Data rights** | DPDP export + hard-delete exist (Settings → Danger Zone). |
| **Feature gating** | Admin Global Settings kill-switches + detector flags (2026-07-25). **No per-user PLAN gating.** |

---

## 1. Gap analysis vs Sensibull / general SaaS

| Capability | Sensibull-grade | Us | Priority |
|---|---|---|---|
| Broker OAuth (Zerodha) | ✅ | ✅ (have) | — |
| Email/password account (independent of broker) | ✅ | ❌ | High |
| Email verification | ✅ | ❌ | High |
| Forgot / reset password | ✅ | ❌ (n/a — no pw) | High |
| Session / device management, logout-all | ✅ | Minimal | Med |
| User phone OTP verification | ✅ | ❌ | High |
| Accountability-partner verify (OTP + consent) | partial | Weak | High |
| Subscription plans (Free/Pro) | ✅ | ❌ | High |
| Payment gateway (Razorpay) | ✅ | ❌ | High |
| Payment-failure handling + dunning | ✅ | ❌ | High |
| Refunds (full/partial/pro-rated) | ✅ | ❌ | High |
| Invoices + GST | ✅ | ❌ | High |
| Trials / coupons | ✅ | ❌ | Med |
| Upgrades / downgrades / proration | ✅ | ❌ | Med |
| Transactional email (receipts, resets) | ✅ | ❌ | High |
| Plan-based feature gating (entitlements) | ✅ | ❌ | High |
| Terms/Privacy versioning + re-consent | ✅ | Partial | Med |
| Multi-broker | ✅ | ❌ (Zerodha only) | Low/Future |
| Google / social login | ✅ | ❌ | Low |

---

## 2. Subsystem specs

### A. Authentication & Identity
**Goal:** an account that survives without a live Zerodha session, with proper recovery — while keeping "Sign in with Zerodha" as the fast path.

**Design decision (open):** decouple **identity** (email/password login) from **broker linkage** (Zerodha OAuth). Today the two are fused (User is born from a Zerodha login). Target:
- Sign up / log in with **email + password** OR **Zerodha OAuth**; both resolve to one `User`.
- Zerodha becomes a **linked broker account**, not the identity source.

**Features**
- A1. Email+password signup/login (bcrypt rounds=12, reuse admin pattern; min length; optional breach check).
- A2. Email verification on signup (token or 6-digit OTP; unverified users get limited access).
- A3. Forgot / reset password (single-use token, short TTL, rate-limited, email-delivered, no enumeration).
- A4. "Sign in with Zerodha" (have) → links/creates account; if the Zerodha email matches an existing email/pw account → **link**, don't duplicate.
- A5. Sessions: short access JWT + refresh token; device/session list; **logout-all** (reuse the admin `session_epoch` pattern on `User`); rotate on password change.
- A6. Change password / change email (re-verify new email).
- A7. (Future) Google OAuth, other brokers.

**Data model additions**
- `User`: `password_hash`, `email_verified_at`, `phone`, `phone_verified_at`, `session_epoch`, `auth_provider` (`password`|`zerodha`|`google`), `last_login_at`.
- `password_reset_tokens(token_hash, user_id, expires_at, used_at)`.
- `email_verification_tokens(...)`.
- `user_sessions(id, user_id, device, ip, created_at, last_seen, revoked)` OR rely on `session_epoch` + refresh rotation.

**Endpoints** (`/api/auth/*`): signup · login · verify-email · resend-verification · forgot-password · reset-password · refresh · logout · logout-all · change-password · change-email.

**Edge cases**
- Email already exists via Zerodha vs manual signup → link/merge, not duplicate.
- Login before email verified → allow-limited vs block (decide).
- Reset token: reuse, expiry, used-once, request for non-existent email (respond identically — no enumeration).
- Brute force → per-account lockout (reuse admin `LOGIN_FAIL_*`).
- Password change → invalidate all other sessions (bump epoch), keep current.
- Zerodha email changes upstream → don't orphan the account.
- Account deleted then re-signup with same email.
- Concurrent signup race (unique email constraint + retry).
- Disposable-email abuse (optional blocklist).
- Clock skew / JWT `exp` tolerance.

---

### B. Verification & OTP (user phone + accountability partner)
**Channels:** **SMS OTP** (does NOT need Meta approval, unlike WhatsApp) via an India DLT-registered provider (MSG91 / Gupshup SMS / Twilio). **WhatsApp OTP** (parked on Meta approval). **Email OTP** (infra exists).
> ⚠️ **India TRAI DLT registration required** for SMS OTP — sender ID + template registration, needs a registered business entity.

**B1. User phone verification** — verify the user's own mobile for 2FA + critical alert delivery. Send/verify OTP, 6-digit, 5-min TTL, resend cooldown (30–60s), max 5 attempts/number, per-account + per-IP limits (reuse admin OTP hardening: per-account counter, constant-time compare, replay guard).

**B2. Accountability partner (guardian) verify + consent** — the partner is a **third party** → DPDP consent required.
- Send OTP/consent message to the guardian's number → guardian confirms → `guardian_confirmed`.
- Record **consent** (who consented, when, to what, channel). Handle **STOP/opt-out**. Re-consent on number change (already invalidates).
- Guardian can **revoke**; user gets notified.

**B3. User 2FA (optional)** — TOTP or SMS/email OTP at login (reuse admin TOTP).

**Data model:** OTP in Redis (like admin) or `otp_challenges` table; `guardian_consent_log(user_id, phone, consented_at, revoked_at, channel, ip)`.

**Edge cases:** OTP brute-force (per-account limit), resend flood, wrong/typo'd number, number reused across accounts, international numbers, DND/regulatory (transactional route), provider outage → fallback channel, OTP replay (consume on use), guardian never confirms (pending state + reminder), guardian revokes mid-danger, delivery failure surfaced to user.

---

### C. Subscriptions & Billing
**Gateway:** **Razorpay** (India standard — UPI/cards/netbanking/wallets, Subscriptions API, webhooks). Alt: Cashfree. (Stripe India is limited.)
> ⚠️ Requires a **registered business + GST**; recurring card payments in India follow **RBI e-mandate** rules (₹ limits, pre-debit notification); UPI Autopay / e-NACH are alternatives.

**C1. Plans** — Free (limited) + Pro (monthly / annual). Feature matrix per plan (→ §E). Price shown **inclusive of 18% GST**.

**C2. Payment flow (webhook is source of truth)**
1. Client requests checkout → backend creates a Razorpay **order/subscription** → returns to Razorpay Checkout.
2. User pays.
3. **Razorpay webhook** (`payment.captured` / `subscription.charged`) → backend verifies **signature** → activates. *Never* trust client-side success.
4. Client polls/gets entitlement update.

**C3. Subscription lifecycle:** `trialing → active → past_due (failed) → cancelled | expired`. Grace period on failure before downgrade.

**C4. Payment failure & dunning:** Razorpay smart retries; grace period (e.g. 3–7 days); reminder emails; auto-downgrade to Free after grace (keep data).

**C5. Refunds:** full / partial / **pro-rated on cancellation** (policy decision); via Razorpay Refund API; refund-status webhook; refund → downgrade; defined refund **window & policy page**.

**C6. Invoices + GST:** generate GST invoice (18% on SaaS), sequential invoice numbers, store + email + downloadable; capture **GSTIN** for B2B; credit note on refund.

**C7. Upgrades/downgrades:** proration; immediate vs next-cycle; plan-price-change **grandfathering**.

**C8. Trials:** X-day free trial; card-required vs not; **one trial per user/phone** (abuse guard); trial-ending email; trial→paid conversion.

**C9. Coupons:** % or flat; expiry; usage limits; first-time-only; stacking rules.

**Data model:** `plans`, `subscriptions`, `payments`, `invoices`, `refunds`, `coupons`, `coupon_redemptions`, `webhook_events` (idempotency), `entitlements` (or derive from subscription).

**Endpoints:** `/api/billing/plans` · `/checkout` · `/webhook/razorpay` (public, signature-verified) · `/subscription` · `/cancel` · `/invoices` · admin: `/admin/billing/*`, issue-refund.

**Edge cases (extensive — billing is where bugs cost money):**
- **Webhook idempotency** (dedup by event id) + **signature verify** + **out-of-order** webhooks.
- Payment succeeds but **webhook lost** → nightly **reconciliation job** against Razorpay.
- **Double-charge** prevention; retry idempotency keys.
- **Chargebacks / disputes** handling.
- **Refund** fails at gateway; **partial-refund** accounting; **tax on refund** (credit note).
- **Card expiry / mandate revoke** mid-cycle; RBI pre-debit notification.
- **Plan price change** while subscribed (grandfather).
- **Proration rounding**; currency; **timezone/billing-date** drift.
- User **deletes account with active subscription** → cancel + refund policy; refund **after** data deletion (keep minimal billing record for law/GST retention).
- Subscription **paused**; **grace-period** boundary; **downgrade keeps data** (never delete on downgrade).
- Coupon abuse; trial abuse (same phone/device/user).

**Compliance:** PCI — gateway-hosted, **we never store card data**; RBI recurring rules; refund SLA; GST retention (invoices kept even after DPDP delete — legal exemption); price display with GST.

---

### D. Transactional email & comms
- Provider: existing SMTP `email_service` (admin OTP) → scale via **SES / Resend / Postmark** for deliverability + templates.
- Emails: welcome · verify-email · reset-password · **payment receipt/invoice** · **payment-failed** · subscription-cancelled · trial-ending · guardian-consent.
- Edge: bounce/complaint handling, SPF/DKIM/DMARC, unsubscribe/preferences (transactional exempt), rate limits, templating/i18n.

---

### E. Feature gating by plan (entitlements)
- Reuse the admin feature-flag mechanism → **per-plan/per-user entitlements**.
- **Free vs Pro matrix** (example — to finalise): Free = dashboard + live alerts + basic analytics; Pro = deep analytics/Habits, AI coach, WhatsApp alerts, larger import windows, guardian mode, reports.
- Enforcement: **backend** entitlement check per endpoint (403 + upsell payload); **frontend** locks/upsell UI.
- Edge: downgrade → **graceful lock, never data loss**; grandfathering; interaction with admin global kill-switches (kill-switch overrides plan).

---

### F. Legal / compliance
- **Terms & Privacy versioning** + acceptance record; **re-accept on material change**.
- DPDP: export/delete exist; extend to cover billing + guardian data; consent registry.
- **Guardian consent** = third-party personal data → explicit consent + revoke.
- SEBI posture: we are a **behavioural mirror, not an advisor** — keep the existing disclaimers; no buy/sell advice, no assured returns.
- Payments: GST registration, refund-policy page, RBI recurring-mandate compliance.

---

## 3. Cross-cutting edge-case master list
- **Auth:** enumeration, brute-force, token theft + rotation, concurrent sessions, email change, OAuth+password same email, deleted→re-signup, clock skew.
- **OTP:** replay, per-account brute-force, resend flood, provider outage → fallback, international/DND, DLT template mismatch.
- **Billing:** webhook replay/idempotency/order/signature, lost-webhook reconciliation, double-charge, double-refund, chargeback, mandate revoke, card expiry, price change, proration rounding, tax-on-refund, delete-account-with-subscription, downgrade-keeps-data.
- **Data/DPDP:** delete account with active sub (cancel+refund first), export includes billing?, guardian data on user deletion, GST invoice legal retention vs delete request.
- **Ops:** gateway downtime, partial success + webhook lost, refund fails, email bounce, SMS provider outage.

---

## 4. Data model additions (summary)
`User`: +password_hash, email_verified_at, phone, phone_verified_at, session_epoch, auth_provider, last_login_at.
New tables: password_reset_tokens · email_verification_tokens · (user_sessions) · guardian_consent_log · otp_challenges (or Redis) · plans · subscriptions · payments · invoices · refunds · coupons · coupon_redemptions · webhook_events · terms_acceptances.

---

## 5. Third-party choices (India-specific)
- **Payments:** Razorpay (primary) / Cashfree (alt).
- **SMS OTP:** MSG91 / Gupshup SMS / Twilio — **requires TRAI DLT** sender+template registration (business entity needed).
- **Email:** Resend / SES / Postmark (deliverability).
- **WhatsApp:** Gupshup (Meta approval pending) — OTP + guardian, once approved.
- **Auth libs:** reuse the in-house admin auth patterns (bcrypt, JWT, TOTP, session-epoch) rather than a new dependency.

---

## 6. Suggested phased rollout
1. **Auth foundation** — email/password + email verify + forgot-password + sessions/logout-all. Decouples identity from Zerodha. *(No payment dependency.)*
2. **Verification** — SMS OTP for user phone + guardian consent (do TRAI DLT registration here).
3. **Monetization core** — plans + entitlements + Razorpay checkout + signature-verified webhook + GST invoices.
4. **Billing depth** — refunds, dunning/grace, coupons, trials, upgrades/downgrades, reconciliation job.
5. **Polish** — transactional email suite, admin billing panel, terms versioning, compliance pages.

---

## 7. Open decisions (need the user)
1. **Identity model:** add email/password (broader, more work) or stay Zerodha-OAuth-only and add recovery differently (simpler)?
2. **Pricing:** Free vs Pro tiers + price points + monthly/annual.
3. **Gateway:** Razorpay (recommended) — confirm.
4. **SMS + DLT:** provider choice + who does the DLT registration (needs business entity + GST).
5. **Refund policy:** window, pro-ration, non-refundable period.
6. **Business status:** is there a registered entity + GSTIN yet? (Hard blocker for real payments in India.)
7. **Free-tier feature matrix:** exactly what's gated behind Pro.

---

*Companion memory: `project_platform_roadmap` (index). This doc is the source of truth for the auth/verification/billing build-out; keep it updated as phases ship.*
