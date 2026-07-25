# P4 — Auth & Security (findings)

> Scope (read): `api/admin/deps.py`, `api/admin/auth.py` (login/OTP/TOTP/lockout/cookie), `api/zerodha.py`
> OAuth `/connect`+`/callback`+nonce store, `api/deps.py` (P0), `models/broker_account.py` encryption,
> impersonation issuance (`api/admin/users.py`), CORS/CSP (P0). Threat-modelled each surface. **Findings-only.**

## Verdict
**Admin auth is genuinely mature** and **user OAuth is well-built.** The heavy hardening from prior sessions holds up under threat-modelling. New findings are mostly P2/P3 hardening gaps + a refinement of P0-F3.

---

## 🟠 P1

### A1 · (refines P0-F3) User-facing per-account rate limiters are non-functional; admin brute-force is NOT · security
> ✅ **FIXED 2026-07-26** (with F3) — limiter keys off the JWT `bid` for authed endpoints (real per-account limits, no more shared-NAT 429s or XFF bypass); unauthed falls to peer IP, XFF only behind a trusted proxy. Admin path was already safe via per-email lockout. Blocking-Redis (F4) still separate/pending.
Re-scoping P0-F3 after reading the admin flow:
- **Admin brute-force is mitigated** — `admin_login` uses a **per-email** `LOGIN_FAIL` counter (5/15min) and 2nd-factor uses a **per-email** `VERIFY_FAIL` counter (5/15min), both **XFF-independent**. So the bypassable per-IP `admin_login_limiter`/`admin_otp_limiter` are only the outer layer; the real caps are per-email and hold. **Downgrade the admin half of F3.**
- **User endpoints remain broken (P1 stands):** `analytics`/`coach`/`profile`/`reports`/`account_data`/`sync` limiters still key on `X-Forwarded-For`/IP (P0-F3 root cause: `request.state.broker_account_id` never set) → **no effective per-user limit**, false 429s for shared-NAT users, and trivial bypass by rotating XFF. These protect expensive endpoints (analytics recompute, LLM coach) → a single user can hammer them. **Fix per P0-F3** (key off the authenticated dep).

---

## 🟡 P2

### A2 · Admin cookie is `SameSite=None` with **no CSRF token** — CSRF defense rests on CORS alone · security
`_set_admin_cookie` sets the admin JWT cookie `SameSite=None; Secure` in prod, and `get_current_admin` accepts the **cookie alone** for state-changing routes (broadcast, suspend, erase, config, task-trigger). **Grep confirms no CSRF token/middleware** anywhere. `SameSite=None` explicitly opts out of the browser's CSRF protection, so the only thing stopping a cross-site POST is: (a) FastAPI JSON bodies forcing a **CORS preflight** + (b) a restrictive CORS origin list. That's **defense-by-side-effect**: it breaks if any admin route accepts a non-preflighted content-type (form/multipart/text) **or** if CORS is loosened — and **P0-F8** already widens CORS to private-IP origins (`http://10.x/192.168.x`) in prod. **Fix:** use `SameSite=Strict`/`Lax` if the admin UI is same-site; otherwise add a real CSRF token (double-submit) or require the `Authorization: Bearer` header (not cookie) for mutations.

### A3 · Admin lockout is per-email → account-lockout DoS · security (low-moderate)
`LOGIN_FAIL`/`VERIFY_FAIL` keyed on `body.email` means anyone who knows an admin's email can **lock that admin out for 15 min** by submitting 5 bad passwords/codes. The correct trade-off vs the brute-force protection, but note it: consider a per-email+per-IP composite or a captcha step so an attacker can't lock a legit admin at will.

### A4 · Admin auth opens un-pooled, blocking Redis connections in async handlers · scale/quality
`auth.py:_redis()` does `redis.from_url(...)` **per call** (new connection, not `redis_pool`), and `deps.py._is_blocklisted` uses a separate module-level sync client — both **blocking** on the event loop (P0-F4 class). Admin traffic is low-volume so impact is small, but it's inconsistent with `redis_pool` and blocks the loop. Route through the shared pool; use async where on the request path.

---

## ⚪ P3
- **A5** OAuth identity is keyed on the Zerodha profile **email** (`User.email == zerodha_email`). If `zerodha_email` is ever null/absent, `User.email == None` can mis-match, and two Zerodha logins sharing an email would merge into one User. Add a not-null guard + prefer `broker_user_id` as the stable key. (BrokerAccount already keys on `broker_user_id` — good; the User row is the soft spot.)
- **A6** During the per-user setup flow the Zerodha **api_secret sits in Redis in plaintext** (`zerodha_creds:{setup_token}`) until the callback consumes it (then Fernet-encrypted at rest in DB). Transient, but a Redis compromise in that window leaks a broker secret. Minimise TTL + consider encrypting the transient blob.
- **A7** Two token-encryption code paths in the callback (direct `Fernet(...)` for new accounts vs `existing_account.encrypt_token()` for updates) — same key, but inconsistent; use the model method throughout.
- **A8** `ENCRYPTION_KEY` is a **single Fernet key** for all broker tokens + api_secrets + admin TOTP secrets. Already known (single point of failure). No key-rotation mechanism — losing/rotating it invalidates every stored token. Document a rotation plan (versioned keys) before scale.

## ✅ Solid (credit — this is strong work)
- **Admin deps:** 404-hiding on every failure, **fail-CLOSED** JTI blocklist (Redis down → reject), IP allowlist with correct CIDR + `ADMIN_TRUST_PROXY_HEADERS` gate (the XFF handling the rate-limiter *should* have used), **session-epoch** instant revocation, fresh role/is_active from DB (instant deactivation/role-change).
- **Login/2FA:** bcrypt rounds=12, `secrets.compare_digest` for OTP, dummy-hash timing padding, dev-bypass gated on `ENVIRONMENT==development`, TOTP replay guard (used-code TTL), per-email 2nd-factor lockout, audit logging.
- **User OAuth:** single-use CSRF **nonce** via httpOnly cookie + Postgres store (Zerodha doesn't echo `state`, so this is the correct mechanism), **auth-code exchange** (no JWT in the redirect URL), signup gate that only blocks new users, Fernet token + api_secret encryption at rest, per-user broker credentials.
- **Impersonation:** admin-gated issuance, `imp=True` token, central **read-only middleware** choke point (main.py), audited.

## For P14 (QA / security regression)
Cross-account access attempt (mismatched `bid`) · XFF-spoof rate-limit bypass on user endpoints (A1) · **admin CSRF probe** (cross-site POST with cookie; confirm CORS+JSON blocks it — A2) · admin account-lockout DoS (A3) · impersonation write-block on every non-GET · OTP/TOTP brute-force cap · null-email OAuth (A5) · `ENCRYPTION_KEY` rotation drill (A8).
