> **ARCHIVED 22 Aug 2026 — do not use as a current reference.**
>
> Proposal fully shipped - getLastSessionStartUTC and ClosedPositionsCard both live.
>
> Live findings, if any, were rescued into `docs/ENGINE_BACKLOG.md`.

---

# P&L + Positions redesign — analysis & proposal (2026-07-30)

User pain: (1) can't journal yesterday's trades after the date rolls over / dashboard goes blank; (2) three confusing P&L numbers (hero vs open vs closed); (3) closed positions list every round-trip instead of consolidating like Zerodha, and breaks for high-frequency traders. "Make it clean and simple like Zerodha."

## What the code actually does today (grounded)

- **Hero "Intraday P&L"** = `realizedPnlDisplay + unrealizedTotal` (Dashboard.tsx:444).
- **Open Positions card total** = `unrealizedTotal` = Σ open positions' unrealized P&L.
- **Closed Positions card total** = `realizedPnlDisplay` = Σ today's closed round-trips' realized P&L.
- So mathematically **hero = open-total + closed-total** — they *do* reconcile. They just aren't labelled to show it, so it reads as three unrelated numbers.
- **"Today" boundary** = `getISTMidnightUTC()` (Dashboard.tsx:421). At IST midnight the closed list + stats reset to empty. The fetch (`/api/trades/completed`, limit 50) still holds yesterday's rows client-side — they're just filtered out of the view, and only *today's* rows are clickable/journal-able on the dashboard.
- **CompletedTrade = one round-trip** (`build_completed_trade_on_close`, created on every CLOSE/FLIP). Scalp SENSEX 5× → 5 CompletedTrades → 5 rows. The engine + journaling operate per round-trip (behaviourally meaningful — each is a decision).

## Proposal

### Fix 1 — Session window instead of calendar midnight (solves blank dashboard + journal-yesterday)
Define the day as **last market open (09:15 IST) → now**, not calendar midnight. Before today's 09:15 the window still points at the previous trading session, so:
- Closed positions + P&L stay visible (and journal-able) until the next 09:15.
- Dashboard doesn't go blank pre-market.
- **Change:** replace `getISTMidnightUTC()` with `getLastSessionStartUTC()` (09:15 IST today if now ≥ 09:15, else the most recent prior calendar day's 09:15). Frontend-only, ~1 helper + 2 call sites. Low risk.
- **Also (small gap):** make *any* past trade journal-able, not only from the dashboard — surface a "Tradebook" list (or make Journal's trade picker reach historical CompletedTrades) so nothing is ever un-journalable. P2.

### Fix 2 — One P&L story, Zerodha-style (kills the "three numbers" confusion)
Keep the same math, make the relationship explicit:
- **Hero = "Day P&L"** = realized + unrealized (the one headline number). Directly under it, always show the breakdown: **`Realized ₹X · Unrealized ₹Y`**. User sees the two parts summing to the headline.
- **Open Positions** card total → labelled **"Unrealized"**.
- **Closed Positions** card total → labelled **"Realized / Booked"**.
- Now it reads exactly like Zerodha: **Day P&L = Booked (closed) + Unrealized (open)**, and each card owns its half. No new numbers — just labels + one always-visible breakdown line.
- "Erratic" P&L: the formula is sound; the likely culprits are (a) the calendar-midnight reset (Fix 1 removes it) and (b) MCX contract-multiplier handling — flag for live validation, not a redesign.

### Fix 3 — Consolidate closed positions like Zerodha + cap volume
Display-layer aggregation only — **do NOT change the CompletedTrade model** (the engine/journal need per-round-trip):
- Dashboard "Closed positions" = **net row per instrument (+ product + expiry)**: symbol, # round-trips, **net realized P&L**, total qty traded, first-entry → last-exit, avg hold. SENSEX scalped 5× → ONE "SENSEX 77000 · 5 trades · −₹X" row.
- **Drill-down:** click a consolidated row → the individual round-trips (where per-trade journaling + behavioural tags live).
- **HFT volume:** consolidation already collapses 1000 trades into a handful of instrument rows, so the wall-of-rows problem mostly disappears. Additionally cap the card to **top ~12 positions** (by |P&L| or recency) + "View all N" → a full tradebook page with pagination.
- **Where to aggregate:** recommend a backend endpoint `/api/trades/closed-summary` (accurate weighted net, server-side paging — scales for HFT) over client-side grouping. Client-side grouping is a faster interim if you want to see it sooner.

## Scope / risk
- Fix 1: FE only, tiny, low risk. **Do first.**
- Fix 2: FE only (labels + breakdown line in SessionHeroCard + card headers). Low risk.
- Fix 3: new BE endpoint + FE consolidated table + drill-down. Medium — the real work. CompletedTrade model untouched (aggregation is a view).
- None of this changes the behavioural engine, detectors, or the raw-P&L rule (still `(exit−entry)×qty×mult`, net realized).

## Decisions needed from you
1. Fix 3 aggregation: **backend endpoint** (recommended, scales) or **client-side grouping** (faster to ship)?
2. Consolidated row = per **instrument+product+expiry** (so NIFTY 25000CE MIS ≠ NIFTY 25000CE NRML)? (recommended — matches Zerodha)
3. Closed-positions display cap: **top 12 + View all**, ok?
