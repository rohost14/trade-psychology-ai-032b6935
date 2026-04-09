# Instrument Sync Architecture: Production-Grade Analysis

You asked for a "Chief Architect" perspective on how to handle **Instrument Master Sync** and **Real-Time Data** for a multi-user application (like Sensibull, Tijori) using Zerodha's Kite Connect API.

This document outlines the optimal, scalable architecture that respects Zerodha's constraints while ensuring performance for 10,000+ users.

---

## 1. The Core Problem: Static Metadata vs. Live Data

We are dealing with two distinct types of data. Conflating them leads to the "100k DB inserts every day" problem.

| Feature | **Instrument Master** | **Live Market Data** | **Trade Updates** |
| :--- | :--- | :--- | :--- |
| **Source** | CSV Dump (Daily) | WebSocket (Real-time) | Postback/Webhook (Real-time) |
| **Size** | ~50MB / 100k+ rows | Kilobytes/sec | Small JSON payloads |
| **Frequency** | Once per day (08:00 AM) | Milliseconds | Instant (Event-driven) |
| **Content** | `Token` -> `Symbol`, `Lot Size`, `Expiry` | `Price`, `Depth` | `Order ID`, `Status` (COMPLETE) |
| **Our Need** | **Reference Only** (Lookups) | **Analytics Only** (Charts) | **Critical** (Behavioral Analysis) |

---

## 2. Production Constraints (Zerodha)

1.  **Rate Limits:** 3 requests/second for API calls. Polling won't work for 10,000 users.
2.  **WebSocket Limit:** 3 connections per API Key. Each connection can handle max 3,000 symbols.
    *   *Constraint:* You CANNOT subscribe to all 100,000 instruments.
    *   *Constraint:* You CANNOT have a dedicated WebSocket per user on the backend (if using one central broker app).
3.  **Database Load:** Inserting 100k rows daily causes massive WAL (Write Ahead Log) churn, bloating the DB and slowing down backups.

---

## 3. The Recommended Architecture

### A. Instrument Master: "The CSV-Backed Cache"

**Do NOT insert 100,000 rows into your primary SQL database daily.** It is wasteful and slow.

**The Solution: Redis / In-Memory Lookup**
1.  **08:00 AM:** Download `instruments.csv` (50MB).
2.  **Load to Redis/Memory:** Parse it and load it into a Redis Hash or an optimized in-memory structure.
    *   Key: `instrument_token` (e.g., `567123`)
    *   Value: `{"symbol": "NIFTY24OCT25000CE", "lot_size": 50, ...}`
3.  **Lazy SQL Hydration:**
    *   When a user trades `567123`, we check: *Is `567123` in our SQL `instruments` table?*
    *   **No:** Fetch details from Redis/Memory -> Insert **ONE** row into SQL.
    *   **Yes:** Do nothing.
    *   **Result:** Your SQL DB only contains the ~500 unique instruments your users *actually* traded, not the 99,500 pending garbage ones.

### B. Trade Sync: "Postbacks" (No Polling)

**Do NOT poll `GET /orders` every second.** This is unscalable and will get your API key banned.

**The Solution: Webhooks (Postbacks)**
1.  **Setup:** In your Zerodha Developer Console, set `Postback URL` to `https://api.tradepsychology.ai/api/webhooks/zerodha`.
2.  **Flow:**
    *   User places buy order on Kite Mobile App.
    *   Order Executes.
    *   Zerodha **instantly** sends a POST request to your backend.
    *   Payload: `{"order_id": "123", "status": "COMPLETE", "token": "567123", "price": "100"}`.
3.  **Processing:**
    *   Your backend receives the webhook.
    *   Look up `567123` in Redis -> "NIFTY...".
    *   Record trade in DB.
    *   Run Behavioral Analysis immediately.
    *   Send WhatsApp alert.

**Why this wins:**
*   **Zero Polling:** No API calls consumed until a trade happens.
*   **Real-Time:** Updates happen within milliseconds of execution.
*   **Scalable:** Request load scales with *trading volume*, not *user count*.

### C. Live Prices (WebSocket): "The Aggregator"

**The Constraint:** users trade different things, but we have a limit of 3000 symbols per socket.

**The Solution: The Ticker Service**
1.  **Global Subscription Manager:**
    *   We maintain a `Set` of all unique tokens currently "active" (open positions or watched charts).
2.  **Backend Socket:**
    *   Connect **ONE** WebSocket to Zerodha on the backend.
    *   Subscribe to the aggregated `Set`.
    *   When a price tick arrives, broadcast it to the relevant Frontend user via your own WebSocket or SSE (Server-Sent Events).
3.  **Cleanup:**
    *   When a user closes a position or logs off, remove their tokens from the `Set`.

---

## 4. Why This Beats Your Current Approach

| Feature | Current (Bad) | Proposed (Production) |
| :--- | :--- | :--- |
| **Startup Time** | 5-10 Minutes (DB Churn) | **< 10 Seconds** (Redis Load) |
| **DB Size** | Huge (100k junk rows/day) | **Tiny** (Only traded/active instruments) |
| **Trade Latency** | High (Polling Delay) | **Instant** (Webhook/Postback) |
| **API Costs** | High (Requests/sec) | **Near Zero** (Push-based) |
| **Multi-User** | fails at ~50 users | **Scales to 10k+ users** |

---

## 5. Implementation Roadmap

1.  **Phase 1 (Immediate Fix):**
    *   Switch `InstrumentService` to **Lazy Loading**.
    *   Stop the daily SQL bulk insert.
    *   Load CSV into a global Python Dictionary (good enough for 1 server) or Redis (for scale).

2.  **Phase 2 (Real-Time):**
    *   Implements **Postback/Webhook** handler for trade updates.
    *   Remove all `sync_trades()` polling calls.

3.  **Phase 3 (Live Data):**
    *   Implement the specific WebSocket aggregator only if you need live P&L ticking on your dashboard.

**Chief Architect Verdict:**
Stop the SQL spam immediately. It is the biggest bottleneck. Refactor to **Lazy Loading** with an in-memory Master Cache.
