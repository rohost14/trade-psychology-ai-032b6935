# KiteTicker Architecture: From Per-User to Shared Pool

**Date:** 2026-06-15
**File changed:** `backend/app/services/price_stream_service.py`
**Migration:** `PerUserPriceStream` → `SharedPriceStream` (singleton swap, last line of file)
**Rollback:** Change last line back to `price_stream = PerUserPriceStream()`

---

## 1. What Was the Problem

The original `PerUserPriceStream` created **one KiteTicker WebSocket connection per active broker account**. KiteTicker is Zerodha's market data WebSocket — it streams live prices (LTP) for subscribed instruments.

```
Before (PerUserPriceStream):

  User A connects → ZerodhaTicker(access_token=A_token) → subscribes NIFTY50, BANKNIFTY
  User B connects → ZerodhaTicker(access_token=B_token) → subscribes NIFTY50, RELIANCE
  User C connects → ZerodhaTicker(access_token=C_token) → subscribes NIFTY50

  3 users → 3 WebSocket connections to Zerodha
  NIFTY50 tick arrives → 3 separate copies processed → 3 separate Redis writes
  At 1000 users: 1000 connections, 1000 copies of the same tick every second
```

### Root Cause: A Wrong Assumption Baked Into the Code

The original code included this comment:

```
Migration path (post-Zerodha partnership):
  Swap PerUserPriceStream for SharedPriceStream.
  SharedPriceStream maintains ONE KiteTicker for all users...
  TODO: Implement when partnership API key is available.
```

This was wrong. The assumption was: "shared KiteTicker requires Zerodha to give us a special multi-user API key — something only partners get."

That assumption is incorrect. Here is why:

**KiteTicker is a market data feed, not a user data feed.**

NIFTY50's last traded price is the same number for every person on the planet watching it. There is no per-user component to market data. Any valid Zerodha `access_token` — belonging to any user — authenticates the WebSocket and gives you the same market data.

TradeMentor already had ONE shared `ZERODHA_API_KEY` (in settings) used for all users. The `access_token` was per-user only because each user goes through OAuth. But for KiteTicker, any one of those tokens is sufficient. We did not need a partnership key. We never did.

---

## 2. What Changed

### Code

Only `price_stream_service.py` changed. No callers changed — they all use the same interface (`start_account`, `stop_account`, `refresh_subscriptions`, `restart_all`, `get_cached_ltp`).

**Before:**
```python
price_stream: PriceStreamProvider = PerUserPriceStream()
```

**After:**
```python
price_stream: PriceStreamProvider = SharedPriceStream()
```

That single line change switches the behavior. Everything else flows from it.

### Architecture

```
After (SharedPriceStream):

  ONE ZerodhaTicker (uses any connected user's access_token)
    ↓ subscribes to UNION of all users' open position instruments
    ↓ NIFTY50 tick arrives → 1 Redis write → broadcast_price("NIFTY50")
  ConnectionManager.broadcast_price("NIFTY50")
    ↓ fans out to ALL frontend WebSockets subscribed to "NIFTY50"
  User A sees live P&L update
  User B sees live P&L update
  User C sees live P&L update

  1000 users → still 1 WebSocket connection to Zerodha
  1000 users on NIFTY50 → still 1 tick processed, 1 Redis write, 1 fan-out
```

`ConnectionManager.broadcast_price()` was **already** designed to fan out to all subscribers — it was never per-user. The WebSocket layer needed no changes at all.

### How Token Selection Works

```
SharedPriceStream._ensure_ticker(db):
  1. If ticker exists and is connected: return it.
  2. Else: query DB for any account where status=connected, token_revoked_at=null
  3. Pick first result, decrypt their access_token
  4. Create ONE ZerodhaTicker with that token
  5. Resubscribe all known instruments immediately
```

### How Token Expiry Is Handled

Zerodha access_tokens expire daily at ~6 AM. When the token expires:

1. KiteTicker starts failing reconnects
2. After max retries, `on_noreconnect` fires
3. `SharedPriceStream._on_ticker_noreconnect()` is called
4. Picks a fresh token from DB (any user who logged in today)
5. Rebuilds ticker, resubscribes all instruments
6. Live prices resume — no manual intervention

**Edge case:** If no user has logged in yet today (e.g., 6 AM before market open), ticker can't restart. It will restart automatically when the first user of the day authenticates. Active traders log in before 9 AM, so market hours are always covered.

---

## 3. Why Wasn't This Done Earlier

Three reasons:

**1. Wrong assumption encoded in a comment**
The "TODO: implement after partnership" comment in the original code created a false dependency. It communicated to anyone reading it: "this requires Zerodha approval." Nobody questioned the assumption until now because the code was working and the architecture question never came up explicitly.

**2. The system was working**
Per-user KiteTicker works fine at small user counts. At 10 users, 10 connections to Zerodha is negligible. The problem only becomes visible at scale. There was no production pain to trigger a fix.

**3. No explicit scale analysis was done at the right moment**
The architecture was designed before the first user. At that point, optimizing for 1000 users feels premature. By the time you have 1000 users, the "why didn't we fix this earlier" conversation is already overdue. The fix was discovered now because of an explicit question about how Sensibull does it — which forced a precise analysis of what KiteTicker actually is.

---

## 4. Scale Impact Analysis

### At 100 Users

| Metric | Before (PerUserPriceStream) | After (SharedPriceStream) |
|---|---|---|
| KiteTicker connections | 0–100 (one per active session) | 1 |
| Tick processing | Up to 100×/second per instrument | 1×/second per instrument |
| Redis LTP writes | Up to 100 per tick cycle | 1 per tick cycle |
| Server memory | ~5–10 MB per ticker thread | ~5–10 MB total |
| Risk | Low — 100 connections is manageable | Very low |

**Verdict at 100:** Both work. SharedPriceStream is cleaner but PerUserPriceStream was not failing. Positive change, but not urgent.

### At 1000 Users

| Metric | Before | After |
|---|---|---|
| KiteTicker connections | 500–1000 concurrent (active users) | 1 |
| Tick processing overhead | Significant CPU, duplicate work | Negligible |
| Redis commands/second | Up to 1000× instruments × ticks/sec | 1× instruments × ticks/sec |
| Memory for ticker threads | 500 MB – 2 GB | ~10 MB |
| Server crash risk from thread count | Real risk (OS thread limit ~1000) | None |
| Duplicate data | 100 users on NIFTY50 = 100 copies/sec | 1 copy/sec |

**Verdict at 1000:** PerUserPriceStream would be causing measurable problems. OOM risk, high CPU, Redis quota blown. SharedPriceStream is the difference between "struggling" and "running clean."

**Negative impact of SharedPriceStream at 1000:** Single point of failure. If the ticker dies and token recovery takes 10–30 seconds, all 1000 users lose live price updates simultaneously. With PerUserPriceStream, one user's ticker dying only affects that user. Mitigated by the `_on_noreconnect` auto-recovery.

### At 10,000 Users

| Metric | Before | After |
|---|---|---|
| KiteTicker connections | 3,000–10,000 (Zerodha would block this) | 1–3 (instrument set may need 2-3 connections) |
| Zerodha's position | Would ban/throttle the API key | Fine — 1 connection is normal |
| Tick processing | Server would be unusable | Still lightweight |
| Instrument coverage | Each user's ticker covers their instruments | Union of all instruments across all users |

**At 10k, PerUserPriceStream is not an option.** Zerodha enforces limits on connection counts per API key. You would be banned. SharedPriceStream is the only viable path.

**New bottleneck at 10k (not KiteTicker):**

At 10k users, the bottleneck shifts to:

1. **Zerodha REST API rate limit:** All users share one `ZERODHA_API_KEY`. Zerodha's limit is 10 requests/second. If 10k users all trigger a positions sync simultaneously, you're 1000× over the limit. Mitigation: aggressive DB caching (serve positions from DB, sync from Zerodha only on webhook events or explicit user action). This works up to a point.

2. **PostgreSQL connections:** 10k users active = potentially thousands of DB queries. Needs PgBouncer connection pooling before this scale.

3. **WebSocket fan-out latency:** `broadcast_price` sends to all subscribers concurrently with `asyncio.gather`. At 10k subscribers to NIFTY50, this is 10k concurrent `send_json` calls per second. May need a Redis pub/sub fan-out layer instead of in-process gather.

---

## 5. Do We Still Need Zerodha Partnership

**For KiteTicker / live market data: NO.** Solved entirely by SharedPriceStream. Done.

**For REST API (positions, trades, orders): DEPENDS ON SCALE.**

| Scale | REST API situation |
|---|---|
| < 500 users | Fine. 10 req/sec limit not hit if you cache aggressively. |
| 500–2000 users | Need careful caching. Webhook-driven sync only (not periodic polling). |
| 2000–10k users | Will hit rate limits during market hours. Partnership rate limits help. |
| 10k+ | Partnership is nearly mandatory for REST API reliability. |

**What Zerodha partnership actually gives:**
- Higher REST API rate limits (exact numbers are negotiated)
- Dedicated support channel
- Co-marketing / listing on Kite platform
- Potentially a dedicated market data feed (not KiteTicker, but a real co-lo feed)
- Revenue share terms (Zerodha takes % of your revenue in most partnership arrangements)

**What Zerodha partnership does NOT give (that we previously thought it would):**
- A "special" KiteTicker with multi-user capability — KiteTicker already works for multiple users with our current setup

**Verdict:** Do not pursue partnership for KiteTicker reasons. Pursue it only when REST API rate limits become a production problem (around 2000+ DAU).

---

## 6. Things You Should Know (That You Didn't Ask)

### 6.1 KiteTicker Instrument Limit

Each KiteTicker connection can subscribe to **max 3000 instruments**. You can have up to 3 connections per `access_token` = 9000 instruments total.

The F&O universe is ~10,000+ instruments (every weekly/monthly option strike for every underlying). But active F&O traders hold concentrated positions — mostly NIFTY50 and BANKNIFTY strikes. In practice, the union of all active users' positions is likely 100–500 instruments. One KiteTicker connection is sufficient up to tens of thousands of users.

If it ever hits 3000 unique instruments, add a second connection in `SharedPriceStream._build_ticker`. The architecture already supports this via `_token_symbol_map`.

### 6.2 REST API Calls Still Per-User

The KiteTicker change has zero impact on REST API calls (positions sync, trade sync, etc.). Those still go through each user's own `access_token`. Zerodha's rate limit on REST API applies across ALL calls from TradeMentor's `ZERODHA_API_KEY`. This is a separate scaling concern addressed by webhook-driven sync and DB caching.

### 6.3 The Daily Token Dependency

The shared ticker depends on at least one user having logged in today. If the server restarts at 2 AM with no users, the ticker won't start until someone authenticates at 9 AM. This is fine for a trading app — there is no live market data before 9 AM anyway (NSE opens 9:15 AM). But if users use TradeMentor for EOD analysis before opening Zerodha, they'll connect fine — their OAuth flow gives us a fresh token → ticker starts.

**Long-term solution (when needed):** A dedicated TradeMentor service Zerodha account, logging in automatically via TOTP automation. Automate the daily login via Celery beat at 8:45 AM IST. Zerodha technically discourages automated login but this is standard practice for algorithmic traders. Do this only when needed — the current approach works fine.

### 6.4 What Happens When the Token Owner Disconnects

The ticker authenticates using "User A's token." If User A revokes their Zerodha connection mid-day:

1. `stop_account(A)` is called → A's instrument subscriptions are cleaned up
2. The ticker's underlying `access_token` is now revoked
3. Zerodha will drop the WebSocket connection
4. `on_noreconnect` fires → picks any other connected user's token → rebuilds

Gap: ~30–60 seconds of no live prices while reconnecting. Acceptable. Users see stale prices during this window (they won't notice in most cases — prices visually freeze for a moment).

### 6.5 SharedPriceStream Lives in the FastAPI Process

Celery workers are separate processes. They cannot access `SharedPriceStream._ticker` directly. This is already handled correctly:

- Celery tasks that need current price use `get_cached_ltp(instrument_token)` → reads from Redis LTP cache written by the shared ticker
- This design was already correct before this change

### 6.6 Behavioral Analysis Does Not Strictly Need Live Prices

TradeMentor's core value — behavioral pattern detection — runs primarily on order fills (via Zerodha webhook postback). The pattern detection engine does not need tick-by-tick prices. It needs:
- Trade fills (webhook ✓)
- Session P&L at various checkpoints (positions API, polled or triggered)

Live prices are used for real-time P&L display on the dashboard. This is important for user experience but is not the behavioral engine itself. If the ticker is unavailable, pattern detection still works; only the live P&L dashboard goes stale.

---

## 7. Future State: After Zerodha Partnership

If and when TradeMentor gets a Zerodha partnership agreement, the main gains are:

1. **Higher REST API rate limits** — can serve 10k+ users syncing positions without hitting throttles
2. **Co-branded trust** — "Connect with Zerodha" badge on the onboarding screen
3. **Potential co-lo / direct market feed** — but only relevant at very large scale (100k+ users)
4. **Publisher-style access** — users can connect with a simpler flow (no need to manually generate their API key). This would change the onboarding UX, not the behavioral engine.

**Code migration for publisher access:** The `PerUserPriceStream` / `SharedPriceStream` switch would remain as-is. SharedPriceStream already works correctly. Publisher access would only change how `access_token`s are obtained (via publisher OAuth flow instead of developer OAuth flow) — the rest of the code is unchanged.

---

## 8. Rollback

To revert to PerUserPriceStream, change the last line of `price_stream_service.py`:

```python
# Current (SharedPriceStream — shared pool):
price_stream: PriceStreamProvider = SharedPriceStream()

# Rollback (PerUserPriceStream — per user):
price_stream: PriceStreamProvider = PerUserPriceStream()
```

No other changes needed. The interface contract is identical.
