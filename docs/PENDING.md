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

## Hard product constraints (govern all future work)
1. **Kite gives NO trade history** — today-only; new users start empty; only fix = Console CSV import.
2. **Zero manual-input adoption** — never design features that need the user to type/tap.
