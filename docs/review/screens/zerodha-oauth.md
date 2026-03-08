# Zerodha OAuth Flow — Screen Review

**Status**: REVIEWED (session 15, 2026-03-07)
**Reviewer**: Claude Code

---

## Scope

- `backend/app/api/zerodha.py` — `/connect`, `/callback`, `/disconnect`, `/accounts`
- `backend/app/api/deps.py` — JWT creation + verification deps
- `backend/app/services/token_manager.py` — token validity check
- `src/contexts/BrokerContext.tsx` — OAuth callback handling + token storage
- `src/lib/api.ts` — Axios interceptor for 401 handling
- `src/components/alerts/TokenExpiredBanner.tsx` — user-facing expired session UI

---

## Flow Summary

```
User clicks "Connect Zerodha"
  → GET /api/zerodha/connect → returns Kite OAuth URL
  → Frontend: window.location.href = login_url
  → User logs in on Kite portal
  → Kite redirects to: GET /api/zerodha/callback?request_token=...&status=success
  → Backend:
      1. Exchanges request_token for access_token via Kite API
      2. Fetches Zerodha profile (user_id, email, name)
      3. Find-or-create User by email
      4. Find-or-update BrokerAccount by broker_user_id
      5. Issues JWT: { sub: user_id, bid: broker_account_id }
      6. Redirects: /settings?connected=true&token=JWT&broker_account_id=UUID
  → BrokerContext reads URL params:
      - Stores JWT in localStorage
      - Clears URL params
      - Triggers auto-sync (if data is stale)
```

**Token Lifecycle**:
- JWT expires in 24 hours (matches Kite's daily token)
- Kite access token expires at ~7:30 AM next trading day
- Refresh is not possible — user must re-authenticate
- All protected endpoints use `get_verified_broker_account_id` which checks `token_revoked_at`

---

## Bugs Fixed

### OA-01 — OAuth error not surfaced to user (FIXED)
**File**: `src/contexts/BrokerContext.tsx:73-76`
**Severity**: MEDIUM (UX bug — users have no feedback on OAuth failure)
**Description**: When Zerodha OAuth fails (user cancels, network error, token exchange fails), the backend redirects to `?error=<message>`. The frontend detected this param and logged it to console, then cleared the URL — but showed no user-facing message. Users would just see the Settings page with no indication of what happened.
**Fix**: Added `toast.error()` call to display the error message for 8 seconds before clearing the URL param.

---

## Observations (No Fix Required)

### OA-02 — JWT in localStorage (XSS risk)
JWT stored in `localStorage` is accessible to any JavaScript on the page (XSS vector). HttpOnly cookies would be more secure, but require backend changes and CORS configuration. localStorage is the standard React SPA approach. The trade-off is acceptable given the app doesn't handle financial transactions.

### OA-03 — Token visible in browser URL during redirect
The JWT is briefly visible in the URL (`/settings?connected=true&token=JWT...`). Browser history, proxy logs, and referrer headers can capture it. The BrokerContext immediately clears the URL via `window.history.replaceState()` which mitigates most exposure. The 302 redirect chain makes this an unavoidable pattern for SPA OAuth.

### OA-04 — No rate limiting on `/connect` endpoint
`GET /api/zerodha/connect` is public and generates a Kite OAuth URL. No rate limiting. Minimal risk since it just returns a URL with the app's API key (no user credentials).

### OA-05 — Race condition on simultaneous OAuth callbacks (theoretical)
If a user double-clicks the Kite login button or a network retry causes two callbacks, the `find-or-create User` pattern has a theoretical race where two `INSERT INTO users` fire simultaneously. The `email: unique=True` constraint catches the second insert as a `UniqueViolation`. This error propagates up and redirects to `?error=...`. Rare in practice. No fix needed.

### OA-06 — `get_verified_broker_account_id` doesn't check `account.status`
Only checks `token_revoked_at`. If `token_revoked_at` is NULL but `status = "disconnected"` (edge case from manual DB manipulation), endpoints would still pass auth. In all normal disconnect flows, `token_revoked_at` IS set, so this is theoretical.

---

## Status

| ID | Issue | Severity | Fixed |
|----|-------|----------|-------|
| OA-01 | OAuth error not shown to user | MEDIUM | ✅ Yes |
| OA-02 | JWT in localStorage | LOW | By design |
| OA-03 | Token briefly in URL | LOW | Mitigated (replaceState) |
| OA-04 | No rate limit on /connect | LOW | Acceptable |
| OA-05 | Race on dual callback | LOW | Theoretical |
| OA-06 | status field not checked in auth dep | LOW | Theoretical |
