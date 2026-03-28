# Security Audit
*All security controls, their implementation, and remaining gaps*

---

## Score: 8.5/10 — Production-Ready

---

## Authentication & Authorization

### JWT Architecture
- **Standard**: `sub` = user_id (stable), `bid` = broker_account_id (ephemeral)
- **Expiry**: 24 hours (Zerodha session length matches)
- **Revocation**: `BrokerAccount.token_revoked_at` — checked on every request
- **Trigger**: KiteTokenExpiredError → token_revoked_at set → all subsequent requests return 401
- **Storage**: `localStorage` (acceptable for SPAs; `httpOnly` cookie would require server-side session)
- ✅ **JWT never appears in URL query strings** (redirect uses URL fragment `#token=X`, cleared immediately)

### OAuth Flow Security
- Auth code stored in Redis with **30-second TTL**
- **Atomic `getdel`** — code consumed in one operation (no race condition, no replay)
- State token verified before processing callback
- ✅ No PKCE needed (server-side token exchange — secret not exposed to browser)

### API Authorization
- **Every sensitive endpoint**: `Depends(get_verified_broker_account_id)`
- Covers: 24 routers × all write operations + all read operations with account data
- `get_verified_broker_account_id()` flow:
  1. Extract JWT from `Authorization: Bearer X`
  2. Decode + verify signature
  3. Confirm `bid` (broker_account_id) exists in DB
  4. Confirm `token_revoked_at IS NULL`
  5. Return UUID for use in query scoping
- ✅ No endpoint relies on user-supplied broker_account_id in body/query (always from JWT)

---

## Data Protection

### Token Encryption
- Broker `access_token` encrypted at rest using **Fernet symmetric encryption**
- `FERNET_KEY` in environment (never in code)
- Encrypt: `zerodha.py:201` — on OAuth callback
- Decrypt: `zerodha.py:405` — when making Kite API calls
- ✅ Tokens never appear in logs or API responses

### SQL Injection Prevention
- All raw SQL uses `text()` with parameterized bindings: `text("SELECT ... WHERE id = :id").bindparams(id=account_id)`
- SQLAlchemy ORM for all standard queries (inherently parameterized)
- ✅ Zero f-string interpolation in SQL

### Error Message Leakage
- All `except` blocks: generic message to client, full error logged server-side + Sentry
- `KiteAPIError` → "Service unavailable" to client, `logger.error(str(e))` server-side
- Global exception handler: `{"message": "Internal Server Error"}` only
- ✅ No stack traces or internal details exposed to API responses

---

## Network Security

### CORS Configuration
```python
if "*" in cors_origins and environment != "development":
    raise RuntimeError("SECURITY: wildcards + credentials = XSS escalation")
```
- Explicit origins required in production
- `allow_credentials=True` requires specific origins (not wildcard)
- ✅ Misconfigured prod deploy crashes immediately — not silently vulnerable

### Security Headers (every response)
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy:
  default-src 'self';
  script-src 'self' 'unsafe-inline';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data:;
  connect-src 'self' https://*.sentry.io wss:;
  frame-ancestors 'none';
  base-uri 'self'
```
- ⚠️ `unsafe-inline` required by Vite — tighten with nonces in Phase C

### WebSocket Authentication
- Token passed in **first message** (not in URL query string)
- URL-based token would appear in: server access logs, browser history, Nginx logs
- ✅ First-message auth handshake (session 19 fix)

### HTTPS
- Not enforced in application code
- ⚪ Delegate to reverse proxy (Nginx/Caddy) or hosting platform (Railway, Render, etc.)
- All WSS automatically enforced if HTTPS is on

---

## Rate Limiting

### API Rate Limiter
- **Implementation**: Redis sliding window (ZADD + ZCARD)
- **Scope**: per (account_id, endpoint path)
- **Default**: 10 req/60s on unspecified endpoints
- **Danger Zone intervention**: 4 req/900s (prevents guardian phone spam)
- **Fail-open**: Redis unavailable → request allowed (no user blocking for infra issues)
- ✅ Returns HTTP 429 with `Retry-After` header

### Kite API Rate Limiter
- 3 req/sec per account (Zerodha spec)
- Circuit breaker: CLOSED → OPEN (50% failure) → HALF_OPEN (60s) → CLOSED
- ✅ Prevents API key suspension from burst requests

---

## Input Validation

### Backend
- All request bodies validated via **Pydantic schemas**
- All path/query params typed (UUID, int, str with constraints)
- Profile update: Pydantic schema with field-level validators
- ✅ Invalid input → HTTP 422 Unprocessable Entity (Pydantic auto)

### Frontend
- Settings page: **Zod schema** validates all 10 profile fields before API call
- Validates: types, ranges, required fields, enum values
- ✅ Client-side validation prevents obvious bad requests; server still validates independently

---

## Webhook Security

### Zerodha Postback Verification
```python
checksum = hmac.new(api_secret, f"{order_id}{timestamp}", sha256).hexdigest()
```
- Matches Zerodha's documented checksum spec exactly
- Invalid checksum → HTTP 400, no Celery task enqueued
- ✅ Prevents spoofed webhooks

---

## Remaining Gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| CSP `unsafe-inline` | Low | Vite requires it. Nonce-based CSP is Phase C (4 hours). |
| HTTPS enforcement | Low | Delegate to reverse proxy — not in app code |
| No JWT refresh endpoint | Low | User reconnects via Zerodha OAuth daily (matches Zerodha session model) |
| Circuit breaker fails open on Redis error | Acceptable | Logs warning; never blocks users |
| Push VAPID keys not in `.env.example` | Low | Document before launch |
| `test_pooler.py` credentials | ✅ Fixed | Redacted + gitignored this session |
| No audit log for admin actions | Low | All mutations logged via Sentry/structured logs |

---

## Security Checklist

- [x] JWT never in URL query strings
- [x] OAuth auth code is single-use (atomic getdel, 30s TTL)
- [x] All tokens encrypted at rest (Fernet)
- [x] Zero f-string SQL interpolation
- [x] Error messages generic to client, detailed server-side
- [x] CORS guard prevents wildcard + credentials in prod
- [x] All 4 security headers on every response
- [x] WebSocket auth via first-message (not URL)
- [x] Webhook checksum verified (SHA-256)
- [x] Rate limiting on all endpoints (including spam-prone intervention)
- [x] Pydantic validation on all request bodies
- [x] Zod validation on frontend before API calls
- [x] token_revoked_at checked on every request (revocation takes effect immediately)
- [x] Hardcoded credentials removed from codebase
