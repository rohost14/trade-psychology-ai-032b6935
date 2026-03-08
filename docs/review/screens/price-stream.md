# Real-Time Price Stream & WebSocket — Screen Review

**Status**: REVIEWED (session 15, 2026-03-07)
**Reviewer**: Claude Code

---

## Scope

- `backend/app/api/websocket.py` — ConnectionManager + WebSocket endpoint
- `backend/app/services/price_stream_service.py` — ZerodhaTicker wrapper
- `src/hooks/useWebSocket.ts` — Frontend WebSocket hook
- Architecture: Zerodha Kite Ticker → ZerodhaTicker → ConnectionManager → browser WS clients

---

## Architecture

```
Browser                     FastAPI                    Zerodha
  |                            |                          |
  |── WS connect ─────────────>|                          |
  |   (JWT in query param)     |                          |
  |                     Auth validates JWT                |
  |                     connect() added to manager        |
  |── subscribe_positions ─────>|                         |
  |               Get open positions from DB              |
  |               Subscribe to instruments               |
  |                            |<── KiteTicker WebSocket ─|
  |                            |    (live ticks)          |
  |<── price broadcast ────────|                          |
  |<── behavioral_event ───────|  (after sync + BehavioralEvaluator)
  |<── alert ─────────────────|  (after risk detection)
```

---

## Observations (No Fix Required)

### WS-01 — console.log statements in frontend production code
`useWebSocket.ts:52,56,79,91` — multiple `console.log/error` calls. Should be removed or replaced with a debug flag before production. Low priority.

### WS-02 — Token in WebSocket URL query parameter
`urlObj.searchParams.set('token', token)` — standard pattern since WS handshake can't send custom headers. Token appears in server access logs. Acceptable for this use case.

### WS-03 — No exponential backoff on WS reconnect
`useWebSocket.ts:84-88` — reconnects every 3 seconds unconditionally. If Kite token is expired or server is down, this creates rapid reconnect loops. Production recommendation: exponential backoff (3s → 6s → 12s → max 60s) with max retry count.

### WS-04 — Single connection per account overwrites previous
`ConnectionManager.active_connections: Dict[str, WebSocket]` — one slot per account_id. Opening the app in two tabs: second tab's connection replaces first's in the dict. First tab's socket stays connected at browser level but never receives server pushes. Low impact (most users use one tab).

### WS-05 — No server-side heartbeat
Server handles client-sent pings but doesn't proactively check connection health. Half-open TCP connections (network interruption without FIN) won't be detected. Standard issue for WebSocket servers. Fix: periodic `send_json({"type": "ping"})` from server, close on no response.

### WS-06 — `get_position_instruments` opens new DB session per `subscribe_positions` message
`websocket.py:238-250` — uses `async with SessionLocal()` inside the WebSocket message handler. This works but bypasses FastAPI's dependency injection. Low impact.

### WS-07 — Price stream (ZerodhaTicker) uses kiteconnect sync library
`price_stream_service.py` — `kiteconnect.KiteTicker` uses a synchronous WebSocket client in a background thread. The `asyncio.to_thread()` or `run_in_executor()` pattern is used to bridge sync/async. Works but has thread-safety considerations.

---

## Status

| ID | Issue | Severity | Fixed |
|----|-------|----------|-------|
| WS-01 | console.log in frontend | LOW | Pre-launch cleanup |
| WS-02 | Token in WS URL | LOW | By design |
| WS-03 | No reconnect backoff | MEDIUM | Deferred |
| WS-04 | Single connection per account | LOW | Acceptable |
| WS-05 | No server heartbeat | MEDIUM | Deferred |
| WS-06 | New DB session per message | LOW | Acceptable |
| WS-07 | Sync KiteTicker in async | MEDIUM | Acceptable (executor) |
