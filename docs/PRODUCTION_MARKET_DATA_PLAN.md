# Production Market-Data & Broker-Auth Plan

Status as of 2026-07-28. Covers the live-price architecture, the two known gaps,
the production key model, edge cases, and everything that needs **you / Zerodha**
(not code). Verified against the actual code, not docs.

---

## 0. TL;DR

- **The live-data architecture is correct** — shared master KiteTicker → per-symbol
  token→holders fan-out → multicast to browser → client-side P&L math → webhook-driven
  baseline reset → Redis event bus. This is the same model Sensibull-class apps use.
- **The 3 req/sec Kite limit does NOT apply to prices.** Prices stream over the
  KiteTicker WebSocket (push, no rate limit). The limit only touches REST pulls
  (orders, positions, margins) which we call *once* per state-change.
- **Gap #1 (feed rode on a customer's token) — FIXED IN CODE.** A dedicated
  market-data account with automated daily TOTP token refresh is fully built and
  dormant; it activates the moment you set `ZERODHA_MD_*` env vars. Until then it
  falls back to a user token (dev) and now logs a loud error + metric if a
  *configured* feed degrades.
- **Gap #2 (single ticker → cluster) — deferred to scale.** Genuinely a scale item
  for us (we subscribe only to held instruments, not the whole option chain), not a
  per-user problem. Plan below; no action until ~a few thousand distinct instruments.
- **The real blocker is business, not code:** the platform-app (Model A) + Zerodha
  partner/commercial terms. Questions to ask Zerodha are in §6.

---

## 1. Current architecture (verified)

| Layer | Where | What it does |
|---|---|---|
| Master WebSocket | `services/price_stream_service.py` (`SharedPriceStream`) | ONE KiteTicker for ALL users; subscribes to the **union of open-position instruments**; unsubscribes on close (stays lean). |
| Fan-out / pub-sub | `broadcast_ltp` → `_token_holders[token]` → `manager.send_to_account` | Each tick goes only to the users holding that instrument (per-symbol channel). Throttled 1/sec/instrument. |
| Event bus | `core/event_bus.py` (Redis Streams) | Alerts / position / margin events → WS → browser, zero polling; `?since=` replay on reconnect. |
| Client-side P&L | `src/components/dashboard/OpenPositionsTable.tsx` `getLivePnl` | Browser computes `(LTP − avg) × qty × mult` per tick. Server does zero per-tick math. |
| Reactive reset | postback → `process_webhook_trade` → `sync_positions` → `position_update` | Baseline (qty, avg) refetched only when an order changes state. |

**Why the 3/sec limit is a non-issue:** a user holding 1000 lots of one option is
**one** instrument on the ticker; Kite streams its LTP with no rate limit; quantity
is just a client-side multiplier. The single REST call is the one-time baseline fetch.

---

## 2. Gap #1 — market-data feed independence  ✅ CODE DONE (needs your account + env)

**Problem (now fixed in code):** the shared ticker used to borrow *any connected
user's* access_token. That's improper (uses a customer's session for everyone),
unreliable (dies when that user logs out / token expires — the `403` reconnect loop
you saw), and likely against Zerodha's terms.

**What's built (dormant until configured):**
- `services/zerodha_auth_service.py` — full automated Kite login: password →
  **TOTP** → `request_token` → `generate_session` → `access_token`; cached in Redis
  (`zerodha_md:access_token`, 27h TTL).
- Celery beat: `refresh-market-data-token` at **08:45 IST Mon–Fri** (`tasks/market_data_tasks.py`).
- `price_stream_service._pick_access_token` priority: **(1)** dedicated MD token →
  **(2)** borrow a user token (dev fallback only).
- **New (this pass):** if `ZERODHA_MD_*` is configured but the token is missing, it
  logs a loud `ERROR` + increments the `md_token_unavailable` metric (surfaced in the
  admin watchdog `market_data_degraded` health flag) instead of silently degrading.

**▶ YOUR ACTION (later — needs Zerodha + your side):**
1. Open / designate a **real Zerodha account** to be the market-data source (it only
   streams data — never places trades). Your own founder account works.
2. Create a **Kite Connect app** for it → `api_key` + `api_secret`.
3. On that account's Zerodha profile, set up **TOTP 2FA** and save the **base32 TOTP
   secret** (the string behind the QR, not the 6-digit code).
4. Set these in `backend/.env` (all 5 required, else it stays on the dev fallback):
   ```
   ZERODHA_MD_API_KEY=...
   ZERODHA_MD_API_SECRET=...
   ZERODHA_MD_USER_ID=...        # client id e.g. AB1234
   ZERODHA_MD_PASSWORD=...
   ZERODHA_MD_TOTP_SECRET=...    # 32-char base32
   ```
5. Restart backend + beat. Confirm the ticker logs `dedicated-md-account` (not
   `user-fallback`) and no `403` loop.

**Caveat — needs live validation:** the auto-login uses Zerodha's standard web-login
endpoints (the approach algo traders use for daily token refresh). It cannot be
tested without the real MD credentials, so validate it at Gate 3 when you add them.

---

## 3. Gap #2 — ticker cluster (scale tier)  ⏸️ DEFERRED — plan only

**Reality check (important):** the 3000-instrument cap is **total distinct
instruments on one connection**, NOT per user. We subscribe only to the **union of
instruments users actually hold**, with heavy F&O overlap (everyone holds the same
NIFTY/BANKNIFTY strikes) and unsubscribe on close. So distinct-instrument count stays
well under 3000 for a long runway. Kite also allows **3 connections/api_key ≈ 9000**
before any sharding. **This is not a per-user problem** — it's a genuine scale tier.

**Why Sensibull needs a cluster and we don't (yet):** Sensibull streams the **entire
NSE F&O option chain** for everyone (thousands of strikes), so they hit the cap on
day one and run a sharded cluster. We only need held instruments.

**Staged plan (build only when the trigger hits):**
1. **Now → ~3000 distinct instruments:** single shared ticker. No action.
2. **3000–9000:** shard instruments across up to 3 KiteTicker connections on the same
   api_key by `instrument_token % N`; a subscription-manager assigns shards.
3. **>9000 or HA:** multiple api_keys / MD accounts, each running tickers, plus a
   supervisor that redistributes shards if one dies (removes the single-point-of-failure).

**Trigger to revisit:** add an ops alert when distinct subscribed instruments exceed
~2500, or when a second MD connection is needed.

---

## 4. Production key model (Model A)  🚫 BLOCKED on Zerodha terms — plan only

**Today (Model B — wrong for a product):** `BrokerAccount.api_secret_enc` stores a
**per-user** api_key/secret → each user would need their own Kite Connect app + fee.
Nobody will do that.

**Target (Model A — what real apps do):**
- **One** Kite Connect app = **one** `api_key`. Users click "Connect Zerodha" →
  Zerodha OAuth (login with *their* creds) → they authorize *your* app → you store
  *their* daily `access_token`. They never create an app or see a key.
- You pay the one Kite Connect app fee; fold it into pricing.

**Migration (code, once terms are confirmed — do NOT build speculatively):**
remove per-user `api_key`/`api_secret_enc`; use one `ZERODHA_API_KEY`/`SECRET` from
env for all OAuth; keep the existing OAuth flow, just point it at the single app.
Medium refactor, low risk, but gated on the Zerodha answer (building the wrong model
now = wasted/risky auth churn).

---

## 5. Edge cases — handling status

| Scenario | Status |
|---|---|
| New position opens mid-day | ✅ postback → `subscription_refresh` → ticker subscribes new token |
| Position closed | ✅ unsubscribed when no holders remain |
| MD token expires / a user logs out | ✅ **after Gap #1 activated** — dedicated token, auto-refreshed 08:45; loud alert if it fails |
| Webhook (postback) missed | ✅ order-WS + 04:00 reconcile + on-login sync = defense-in-depth |
| Same symbol MIS + NRML | ✅ fixed (M1, migration 075) |
| Same instrument, many users | ✅ token→holders fan-out (the design's strength) |
| Browser reconnect / offline | ✅ WS `?since=LAST_EVENT_ID` replay |
| Illiquid option, no ticks (LTP frozen) | ⏸️ minor UX — add a "price stale" indicator later (§7) |
| 09:15 open thundering herd | ⏸️ scale tuning — sequential all-account loops; parallelize under load test (§7) |
| MD auth breaks in prod | ✅ now logged loud + `md_token_unavailable` metric / `market_data_degraded` flag |

---

## 6. ▶ What to confirm with Zerodha (the real blocker)

Ask directly — do not assume; their terms/pricing change and govern the whole product:
1. **Platform app:** can one Kite Connect app serve many customers' accounts (Model A),
   and what approval / partner status is required?
2. **API billing:** who pays the Kite Connect fee — the platform (one flat) or each end
   user? Is there a partner arrangement that bundles it?
3. **Market data:** is it permitted to stream live market data from **one** account's
   token to display prices to all users? Any per-account data subscription needed?
4. **OAuth at scale:** any cap on concurrent authorized users per app?

These answers unblock: Model-A migration (§4), the MD account setup (§2), and pricing.

---

## 7. Deferred minor items (noted, not built)

- **Stale-price indicator (frontend):** during market hours an illiquid option's LTP
  can freeze; show a subtle "stale" badge when a symbol's last tick is older than N s.
  Low value, per-symbol tracking is fiddly — do when polishing the dashboard.
- **09:15 thundering herd:** the per-account sync/subscribe loops run sequentially;
  parallelize with bounded concurrency once a real load test shows the ceiling
  (tie to the scale review / Gate 4).

---

## 8. ▶ Consolidated action checklist (you / Zerodha — later)

- [ ] Confirm Zerodha terms — §6 (the gate for everything below).
- [ ] Provision the dedicated market-data account + Kite Connect app + TOTP — §2.
- [ ] Set `ZERODHA_MD_*` in `.env`, restart, verify `dedicated-md-account` + no 403 — §2.
- [ ] After terms: Model-A key migration (remove per-user keys) — §4.
- [ ] At scale: ticker cluster — §3. Thundering-herd tuning — §7.
