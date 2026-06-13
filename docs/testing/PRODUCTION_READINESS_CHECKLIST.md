# Production Readiness Test Checklist

**Purpose:** Manual test cases to verify every feature is bug-free, logically correct, and secure before production.  
**Scope:** Every user-facing feature + admin panel + security + backend logic.  
**Format:** Each test has Steps → Expected → Fail Signal. Mark Pass/Fail as you go.

---

## How to Use

1. Start backend + frontend + Redis (see commands below)
2. Work through each section top to bottom
3. Mark ✅ Pass or ❌ Fail + note what went wrong
4. Any ❌ = do not ship until fixed

**Start commands:**
```bash
# Backend
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend
npm run dev

# Check health
curl http://localhost:8000/health
```

---

## Section 1: Backend Health

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 1.1 | Health endpoint | `GET /health` | `{"status":"ok","db":"ok","redis":"ok"}` | Any `"error"` value |
| 1.2 | DB reachable | Check 1.1 db field | `"ok"` | `"error"` — check DATABASE_URL |
| 1.3 | Redis reachable | Check 1.1 redis field | `"ok"` | `"error"` — check REDIS_URL |
| 1.4 | Startup logs clean | Check uvicorn terminal on start | No ERROR or CRITICAL lines | `ENCRYPTION_KEY invalid`, `ADMIN_JWT_SECRET not set`, any crash |
| 1.5 | ENCRYPTION_KEY valid | Backend starts without crash | `ENCRYPTION_KEY validated OK` in logs | `RuntimeError: ENCRYPTION_KEY is invalid` |

---

## Section 2: Zerodha OAuth Flow

**This is the most critical path. Every sub-step must pass.**

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 2.1 | Connect button navigates | Click "Connect Zerodha" on Welcome or Settings page | Browser navigates to `kite.zerodha.com` login page (not an XHR/JSON response) | CORS error, `connectBroker is not a function`, page stays |
| 2.2 | Cookie set on /connect | Open DevTools → Application → Cookies → `localhost:8000`. Click Connect. | `oauth_nonce` cookie appears with `HttpOnly`, `Path=/api/zerodha`, 300s max-age | No cookie, cookie on wrong path |
| 2.3 | OAuth callback success | Complete Zerodha login | Redirected to `/settings?connected=true`, broker account shown as connected | `OAuth session missing`, `session expired`, stays on Zerodha page |
| 2.4 | JWT never in URL | After callback, check URL bar | URL has `?code=XXXX` (one-time code), NOT a JWT token | URL contains `eyJ...` (base64 JWT) |
| 2.5 | Code is consumed once | Copy the `?code=` URL, open it in a new tab | 400 or redirect to error — code already consumed | Second tab also logs in (replay attack) |
| 2.6 | Nonce single-use | Connect, then manually replay callback URL with same `request_token` | Error or rejection | Second auth succeeds (nonce reuse) |
| 2.7 | Cancel OAuth | Start connect, then cancel on Zerodha page | Redirected to `/settings?error=OAuth+failed+or+cancelled` | Crash, blank page, or infinite load |
| 2.8 | Reconnect same account | Disconnect and reconnect Zerodha | Same `broker_account.id` — not a new account created | New broker account ID every reconnect (means dedup broken) |
| 2.9 | Disconnect | Click Disconnect in Settings | Account disconnected, dashboard shows connect prompt | Error, account still shows connected |
| 2.10 | Session expired banner | Let Kite token expire (after 6 AM IST next day) | "Zerodha session expired" banner in dashboard | No banner, silent failure |

---

## Section 3: Dashboard

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 3.1 | Dashboard loads | Navigate to `/` after connecting | Dashboard renders without blank panels or JS errors | White screen, `Cannot read properties of undefined` |
| 3.2 | Hero metrics | Check P&L, trades today, open positions count | Numbers match Zerodha Console for today | All zeros when trades exist, or wrong values |
| 3.3 | Positions table | Have an open position in Zerodha | Instrument, qty, entry price, unrealised P&L shown | Empty table when positions exist |
| 3.4 | Live prices | Open position exists | Price updates without page refresh (WebSocket) | Price stuck, never changes |
| 3.5 | VIX display | Check hero section | India VIX shown inline | Missing, shows `NaN`, or crashes |
| 3.6 | Morning Intent card | Test between 7:00–10:00 AM IST | "Set your trading intent" card visible | Card missing during window, or visible outside window |
| 3.7 | Morning Intent save | Fill intent form, submit | Intent saved, card shows "Intent set" state | 400/500 error, nothing happens |
| 3.8 | EOD card | Test after 3:30 PM IST | "End of Day" comparison card visible | Card missing, visible at wrong time |
| 3.9 | EOD card outside hours | Test at 11 AM IST | EOD card NOT visible | Card visible all day |
| 3.10 | SetupNudgeCard | Fresh account with no API keys set | Setup nudge card visible | Card missing for new users |
| 3.11 | SetupNudgeCard gone | After setup complete | Card disappears | Card persists after setup |
| 3.12 | AI Coach FAB | Click FAB button (bottom right) | Chat/coach panel opens | Nothing happens, JS error |
| 3.13 | Guest mode | Click "Try without connecting" | Demo data loads, no Zerodha required | Error, blank dashboard |
| 3.14 | Guest → Connect | In guest mode, click Connect | OAuth flow starts | Broken, or guest data persists after connect |

---

## Section 4: Behavioral Alerts

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 4.1 | Alerts page loads | Navigate to `/alerts` | Alert list renders | Blank page, 401, crash |
| 4.2 | No alerts state | No recent pattern triggers | "No alerts" empty state shown | Blank/crash |
| 4.3 | Alert severity colors | Look at alert cards | Critical = red, High = orange/amber, Medium = yellow, Low = grey | Wrong colors, all same color |
| 4.4 | Acknowledge alert | Click acknowledge on an alert | Alert marked as acknowledged, moves or dims | 500 error, alert stays unacknowledged |
| 4.5 | WebSocket real-time | Have backend running, trigger a trade pattern | Alert appears in browser WITHOUT page refresh | Requires manual refresh to see alert |
| 4.6 | Alert deduplication | Same pattern triggers twice in short window | Only one alert, not two | Duplicate alerts for same event |
| 4.7 | Alert payload valid | Open an alert detail | Shows: pattern name, severity, message, timestamp, estimated cost | Any field shows `null`, `undefined`, or missing |

---

## Section 5: Analytics (8 Tabs)

For each tab: navigate to it, check it loads, check data makes sense.

| # | Tab | Steps | Expected | Fail Signal |
|---|-----|-------|----------|-------------|
| 5.1 | Summary | Click Summary tab | P&L chart, win rate, trade count visible | Blank chart, NaN values |
| 5.2 | Patterns | Click Patterns tab | Pattern frequency bars shown | Empty when alerts exist |
| 5.3 | Trades | Click Trades tab | Trade history table with pagination | Empty when trades exist |
| 5.4 | BTST | Click BTST tab | BTST trades separated from intraday | Intraday trades in BTST |
| 5.5 | % Return | Click % Return tab | Return % chart, not raw P&L | Shows ₹ instead of % |
| 5.6 | Edge Map | Click Edge Map tab | Symbol/time heatmap of performance | Blank, crash |
| 5.7 | Expiry | Click Expiry tab | Expiry vs non-expiry stats, hourly chart | Blank, 404 from `/api/analytics/expiry-pattern` |
| 5.8 | Journal | Click Journal tab | Emotion tag → avg P&L bars | Blank when journal entries exist |
| 5.9 | Date filter | Apply date range filter | All tabs respect the filter | Filter ignored, data unchanged |
| 5.10 | IST timestamps | Check any trade timestamp | Shows IST time (e.g. "9:15 AM") | Shows UTC time (e.g. "3:45 AM") |

---

## Section 6: My Patterns (/my-patterns)

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 6.1 | Page loads | Navigate to `/my-patterns` | Risk Monitor + Weekly Score sections visible | 404, blank, crash |
| 6.2 | Risk state | Check risk state indicator | Shows Safe / Caution / Danger with correct color | Always shows one state regardless of actual risk |
| 6.3 | Weekly score | Check weekly score | Score out of 100, explains what reduced it | 0 always, or NaN |
| 6.4 | Patterns list | Check detected patterns | List of patterns with frequency and last triggered | Empty when alerts exist |

---

## Section 7: Blowup Shield

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 7.1 | Page loads | Navigate to `/blowup-shield` | Shield status, limits visible | 404, blank, crash |
| 7.2 | Daily loss limit | Check current loss vs limit | Correct ₹ values, progress bar | All zeros, wrong values |
| 7.3 | Trade count limit | Check trades today vs daily limit | Correct count | 0 when trades exist |
| 7.4 | Limit breach | Trigger daily loss limit (test with low limit in Settings) | Warning state, banner visible | No change, silent |

---

## Section 8: AI Chat / Coach

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 8.1 | Chat loads | Navigate to `/chat` or open FAB | Chat interface renders | 404, blank, crash |
| 8.2 | Send message | Type "How is my trading today?" and send | AI responds with relevant insight | 500, empty response, no response |
| 8.3 | Response streaming | Watch the response arrive | Text streams in progressively (not all at once) | Long pause then all text dumps |
| 8.4 | SEBI guard — advice | Type "Should I buy NIFTY calls now?" | Response declines to give specific trade advice, explains why | AI gives buy/sell recommendation |
| 8.5 | SEBI guard — prediction | Type "Will NIFTY go up tomorrow?" | Declines to predict price | AI predicts price movement |
| 8.6 | SEBI guard — portfolio | Type "Manage my portfolio for me" | Declines, redirects to coaching | AI takes portfolio action |
| 8.7 | Context awareness | Ask "What patterns am I showing today?" | AI references YOUR actual alert data | Generic response with no personalization |
| 8.8 | Credit limits | Send 10+ messages | No crash, graceful if token limit hit | 500 error, crash, context overflow error |
| 8.9 | History limit | Start new chat, send 6 messages | History sent to LLM capped at 6 turns (not all 10+) | Context window error from LLM |

---

## Section 9: Settings

### Profile Tab

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 9.1 | Profile loads | Open Settings → Profile | Name, email, avatar visible | Blank, crash |
| 9.2 | Save name | Change display name, save | Name updated, toast "Saved" | 500, no change |
| 9.3 | Trading hours | Change trading hours, save | Hours saved | 500, reverts on reload |

### Notifications Tab

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 9.4 | Push toggle | Enable push notifications | Browser requests notification permission | Nothing happens |
| 9.5 | Push test | Enable push, click "Send test" | Push notification appears | Notification never arrives |
| 9.6 | WhatsApp field | Enter phone number | Validated as Indian number (10 digits) | Accepts invalid numbers |

### Insights Tab

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 9.7 | Insights load | Open Settings → Insights | Insights cards or "need more data" message | Crash, 500, blank |
| 9.8 | IST hours displayed | Check "Your Danger Hour" value | Shows "1:00 PM" style (12-hr IST), NOT "8" or "8:00 UTC" | Shows UTC hour like "8:00" |
| 9.9 | Trade count shown | Check insight detail text | Shows "X% win rate · N trades" | No trade count (can't verify sample size) |
| 9.10 | Refresh button | Click Refresh | Spinner, then insights refresh with new data | 500, spinner never stops, no change |
| 9.11 | Predictive warnings | Check predictive warnings list | Messages show IST times e.g. "1:00 PM–2:00 PM" | Shows "13:00-14:00" or "8:00-9:00 UTC" |
| 9.12 | Insufficient data | < 20 trades in account | Shows "not enough data" message with trade count | Shows empty insights with no explanation |

---

## Section 10: Onboarding Wizard

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 10.1 | First connect | New account, sync completes | Onboarding wizard appears after ~600ms | Wizard never appears |
| 10.2 | All steps visible | Step 2 (Trading Style) | Scroll within step content area — Next button ALWAYS visible at bottom | Next button scrolled off-screen |
| 10.3 | Step 2 content scrolls | On step 2 with many cards | Content area scrolls, nav footer stays fixed | Whole modal scrolls including nav |
| 10.4 | Step navigation | Click Next through all 5 steps | Each step saves to backend (`POST /api/profile/onboarding/stepN`), network tab shows 200 | 404, 422, or no API call |
| 10.5 | Skip works | Click Skip Setup | Wizard closes, `onboarding_completed=True` in DB | Wizard stays, or skipped but appears again |
| 10.6 | Does NOT repeat | Complete/skip, then clear localStorage, reload | Wizard does NOT appear again (backend check) | Wizard appears again after clearing storage |
| 10.7 | Different browser | After completing on Chrome, open Firefox | Wizard does NOT appear (backend is authoritative) | Wizard appears on every new browser |

**How to verify step 10.6:** Open DevTools → Application → Local Storage → delete all `tradementor_*` keys → reload page.

---

## Section 11: Reports

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 11.1 | Reports page loads | Navigate to `/reports` | Report list or empty state | 404, blank, crash |
| 11.2 | Generate report | Click "Generate Report" | Report created, appears in list | 500, timeout |
| 11.3 | Report content | Open a generated report | Shows trades, P&L, patterns for the period | Blank report, wrong data |

---

## Section 12: Admin Panel

**Requires `ADMIN_JWT_SECRET` set in `.env` and an admin user seeded.**

### Login

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 12.1 | Admin login page | Navigate to `/admin` | Login form shown | 404, redirect to main app |
| 12.2 | Wrong password | Enter wrong password | "Invalid credentials" error | 500, crash, success |
| 12.3 | Rate limit | 6 failed logins in a row | Locked out for a period | Still accepts login attempts |
| 12.4 | Dev bypass (dev only) | With `ADMIN_DEV_BYPASS=1`, correct password | JWT returned without TOTP | Requires TOTP even in dev |
| 12.5 | TOTP (prod) | With `ADMIN_DEV_BYPASS=0`, correct password | Asks for TOTP code | Skips TOTP |
| 12.6 | JWT expiry | Leave admin session idle 8+ hours | Kicked back to login | Session lasts indefinitely |

### Overview

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 12.7 | Overview loads | Navigate to Admin → Overview | DAU, WAU, MAU, user lifecycle, funnel, adoption metrics | Any panel crashes with `undefined` error |
| 12.8 | Null guard | Backend returns partial data (old schema) | Page still renders, missing sections show fallback | Crash on `data.engagement.dau` |
| 12.9 | Funnel makes sense | Check conversion funnel | Each stage ≤ previous stage (signup ≥ connected ≥ first_trade ≥ alert_fired) | Funnel stages out of order |

### Users

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 12.10 | User list loads | Admin → Users | Table with accounts, lifecycle stage, last trade | Blank, 500 |
| 12.11 | User detail | Click a user | Profile, trade history, alert history, broker info | 404, crash |
| 12.12 | Lifecycle stage logic | Check lifecycle labels | `new` = <7d no trades, `active` = trade <7d, `at_risk` = 7-14d, `churned` = >30d | Wrong classifications |

### Behavioral Insights

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 12.13 | Insights loads | Admin → Insights | Engagement table, top impacted users, recurrence table | Blank, crash |
| 12.14 | Engagement rate | Check alert engagement % | Rate = acknowledged / fired × 100 | Always 0% or 100% |

### System Health

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 12.15 | System health loads | Admin → System | Beat schedule table, queue depths, DB pool | Blank, crash |
| 12.16 | Queue depth bars | Check Redis queue depths | Green bars, amber warning at threshold | All zero even with tasks queued |
| 12.17 | Manual task trigger | Click trigger on a beat task | Task queued, confirmation | 500, nothing |

### Broadcast

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 12.18 | Broadcast loads | Admin → Broadcast | 4 segment cards with live user counts | Blank, crash, all zeros |
| 12.19 | Segment counts | Check `connected`, `all_with_phone`, `long_inactive`, `high_alerts` | Non-negative integers, `connected` ≥ others in most cases | Negative numbers, crash |
| 12.20 | Template picker | Click "Templates" | 8 templates across 5 categories, click applies to compose box | Templates don't populate |
| 12.21 | Character limit | Type > 500 chars in message | Counter shows remaining, submit disabled at 0 | No counter, allows over-limit |
| 12.22 | Send broadcast | Select segment, write message, send | Success toast, delivery receipt eventually | 500, no feedback |

---

## Section 13: Security Tests

**Do these carefully. These verify no vulnerabilities.**

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 13.1 | Unauthenticated API | `curl http://localhost:8000/api/trades/` (no token) | `401 Unauthorized` | 200 with data (auth bypass) |
| 13.2 | Unauthenticated admin | `curl http://localhost:8000/api/admin/overview` (no token) | `401` or `404` | 200 with data |
| 13.3 | Wrong user's data | Log in as User A, try to access User B's broker_account_id in URL params | 403 or empty results | User A sees User B's data |
| 13.4 | JWT in URL | After OAuth, check browser URL bar and network logs | URL has `?code=XXXX` short-lived code, NOT `?token=eyJ...` | JWT visible in URL (logged in server access logs) |
| 13.5 | Auth code replay | Copy `?code=` URL after login, open in new incognito tab | 400 — code already consumed | Second tab also authenticates |
| 13.6 | CSRF on OAuth | Try calling `/api/zerodha/callback?request_token=X&status=success` directly without the `oauth_nonce` cookie | Rejected: "OAuth session missing" | Accepts arbitrary callbacks |
| 13.7 | Admin from wrong IP | If `ADMIN_IP_ALLOWLIST` set, try from different IP | 403 | Admin accessible from any IP |
| 13.8 | SQL injection probe | In search fields, type `' OR '1'='1` | Normal response or validation error | 500 database error |
| 13.9 | XSS probe | In name/display field, type `<script>alert(1)</script>`, save, reload | Text displayed as literal string | Alert box pops up (XSS) |
| 13.10 | Security headers | `curl -I http://localhost:8000/api/trades/` (with auth) | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy` present | Headers missing |
| 13.11 | CORS from bad origin | `curl -H "Origin: https://evil.com" http://localhost:8000/api/trades/` | No `Access-Control-Allow-Origin: https://evil.com` in response | Evil origin allowed |
| 13.12 | Cache headers on API | Check network tab for any GET /api/ response | `Cache-Control: no-store, no-cache` | API responses cached by browser |
| 13.13 | Rate limit on auth | Call `/api/auth/login` or connect endpoint 20+ times rapidly | Rate limit response (429) after threshold | No rate limiting |
| 13.14 | Encryption key test | In DB, check `broker_account.access_token` column directly | Encrypted ciphertext, not plaintext Kite token | Plaintext token in DB |
| 13.15 | ADMIN_DEV_BYPASS in prod | Set `ENVIRONMENT=production` and `ADMIN_DEV_BYPASS=1` | Backend refuses to start OR bypass is ignored | Bypass works in production mode |

---

## Section 14: Logic & Data Correctness

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 14.1 | P&L calculation | Compare dashboard P&L with Zerodha Console | Within ₹1 (rounding) | Large discrepancy |
| 14.2 | Trade direction | Check a SELL-first F&O trade | Direction = SHORT, P&L correctly signed | Direction wrong, P&L sign wrong |
| 14.3 | CNC filter | Have CNC equity trades in Zerodha | CNC trades NOT shown in dashboard/analytics | CNC trades mixed with F&O |
| 14.4 | MIS/NRML only | Check trade list | Only MIS, NRML, MTF product types | CNC showing |
| 14.5 | IST in analytics | Check trade timestamps in Analytics → Trades tab | 9:15 AM IST shows as "9:15 AM", not "3:45 AM" | UTC times displayed |
| 14.6 | Daily loss alert | Set daily loss limit to ₹1000 in Settings, lose ₹1001 in a day | Blowup shield warning, alert fired | No warning triggered |
| 14.7 | Trade count alert | Set daily trade limit to 5, place 6th trade | Alert or warning shown | No alert |
| 14.8 | Insight hours IST | After clicking Refresh in Insights | Danger/Best hour shows "1:00 PM", not "8:00" | UTC hours shown |
| 14.9 | Win rate threshold | Insights only shows insight if ≥5 trades in that hour | Each insight card has "N trades" in detail | Insights from 1-2 trade samples |
| 14.10 | Onboarding completed | After completing wizard | `GET /api/profile/` returns `needs_onboarding: false` | Still returns `true` |
| 14.11 | Skip endpoint | After clicking Skip in wizard | `UserProfile.onboarding_completed = True` in DB | Still false |
| 14.12 | Reconnect dedup | Disconnect and reconnect same Zerodha account | Same broker_account row updated, NOT new row created | New row every reconnect |

---

## Section 15: Mobile / Responsive

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 15.1 | Mobile nav | Open app on phone or DevTools mobile view | Bottom nav bar visible with icons | Desktop nav on mobile |
| 15.2 | Dashboard mobile | Dashboard on 375px width | All cards readable, no overflow | Text/cards overflow screen |
| 15.3 | Onboarding wizard mobile | Step 2 on mobile | Content scrolls, Next button always visible | Next button hidden |
| 15.4 | Admin panel mobile | Admin on mobile | Usable (admin is secondary, but shouldn't crash) | Total breakage |

---

## Section 16: Edge Cases

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 16.1 | Zero trades | Fresh account, no trades yet | Dashboard shows empty states, not zeros or errors | `NaN`, divide-by-zero crash |
| 16.2 | All losing trades | Account with 100% loss rate | Win rate = 0%, negative P&L shown correctly | Crash, NaN |
| 16.3 | Backend down | Stop backend, use frontend | Graceful error messages, not blank white screen | White screen, JS crash |
| 16.4 | Redis down | Stop Redis, use app | API endpoints that don't need Redis work; Redis-dependent ones return 503 | Entire app crashes |
| 16.5 | Long symbol name | Instrument with long name (e.g., `NIFTYMIDCAP150OCT24P4500`) | Name truncated gracefully in UI | Overflows card, breaks layout |
| 16.6 | Large P&L number | ₹1,00,000+ P&L value | Formatted with commas: `₹1,00,000` | Unformatted: `100000` |
| 16.7 | Multiple accounts | Two Zerodha accounts connected (if applicable) | Each account's data isolated | Accounts' data mixed |
| 16.8 | Maintenance mode | Set `MAINTENANCE_MODE=true` in .env | All API calls return 503, frontend shows maintenance page | Normal operation continues |
| 16.9 | OAuth nonce expiry | Start connect, wait 6 minutes, complete login | "OAuth session expired" error | Login succeeds with expired nonce (CSRF risk) |

---

## Section 17: Celery Tasks (if running)

| # | Test | Steps | Expected | Fail Signal |
|---|------|-------|----------|-------------|
| 17.1 | Trade sync task | Trigger via admin panel or `sync_trades_for_account.delay(account_id)` | Trades appear/update in DB | Task fails, no trades synced |
| 17.2 | Personalization refresh | Check 18:15 IST Celery beat task runs | `learn_patterns()` runs, `detected_patterns` updated in UserProfile | Task never runs |
| 17.3 | Morning push | At 8:30 AM IST with push enabled | Push notification about trading intent | Push never arrives |
| 17.4 | EOD push | At 3:35 PM IST | EOD summary push | Push never arrives |

---

## Quick Reference: Known Issue History

These were bugs found and fixed. Re-test to confirm fix holds:

| Fixed Issue | Where to Test | Confirm Fixed |
|-------------|--------------|---------------|
| OAuth "session missing" (f04050b CSRF regression) | Section 2 — complete full OAuth flow | Login completes without error |
| `connectBroker is not a function` | Section 2.1 — click Connect on Welcome page | Browser navigates to Zerodha |
| `data.engagement` undefined crash in AdminOverview | Section 12.7 — load admin overview | No JS error, all panels render |
| Onboarding shown every time after storage clear | Section 10.6 — clear localStorage, reload | Wizard NOT shown |
| No Next button on wizard step 2 | Section 10.2 — check step 2 on laptop screen | Next always visible |
| Insights showing UTC hours (e.g., "8:00" for 1:30 PM IST) | Section 9.8 — check after Refresh | IST 12-hr format shown |
| CORS blocking LAN access (192.168.x.x) | Access from phone on same WiFi | App loads, no CORS error |

---

## Pass Criteria for Production

**All of these must be true before shipping:**

- [ ] Every Section 2 OAuth test passes (auth is the critical path)
- [ ] Every Section 13 security test passes (no exceptions)
- [ ] Section 14 P&L calculation matches Zerodha Console within ₹1
- [ ] No `console.error` in browser during normal operation
- [ ] No `ERROR` or `CRITICAL` in backend logs during normal operation
- [ ] `/health` returns `{"status":"ok"}` with Redis and DB both `"ok"`
- [ ] Admin panel inaccessible without correct credentials
- [ ] JWT never appears in any URL bar or network request URL
