# P7 — Frontend (findings)

> **Scope + honest depth:** `src/` = 16 pages + 12 admin pages + 4 contexts + 12 hooks + 20 lib + 91
> components + 52 ui. I audited the **infrastructure** in full (`lib/api.ts`, the 4 contexts' core patterns,
> impersonation/guest-mode wiring) and ran **codebase-wide sweeps** for the known footguns (chart-axis rule,
> XSS sinks, client-side detection, cross-account param use). I did **not** line-audit all 91 components /
> 16 pages individually — component-level UI logic is sampled, not exhaustively read. **Findings-only.**

## Verdict
Frontend is in **good shape**. The real-time client, error handling, chart-axis discipline, and XSS hygiene are all solid. Findings are hardening (P2/P3) + doc-staleness, no correctness bombs.

---

## 🟡 P2

### FE1 · User JWT in `localStorage` (XSS-exposed) — asymmetric with admin's httpOnly cookie · security
`lib/api.ts` stores the user session token in `localStorage['tradementor_auth_token']` and attaches it as a Bearer header. Any XSS → the 24h user JWT is stealable (whereas admin uses an httpOnly cookie, not JS-readable). **Mitigations present:** CSP `script-src 'self'` (P0/main.py) blocks inline-script injection, and the only `dangerouslySetInnerHTML` sinks are DOMPurify-sanitized (see credit). Residual risk = an XSS via a dependency or a future unsanitized sink. Accept-with-eyes-open or move to an httpOnly cookie + CSRF for the user token too.

### FE2 · Guest-mode unmocked-GET catch-all returns `{}` → component crashes · robustness
`lib/guestMode.ts:338` returns `{}` for any GET not explicitly mocked. A component expecting an **array** (`.map`) or a specific shape gets `{}` → runtime crash in guest mode (memory-noted "has crashed components"; still present). Since guest mode is also the smoke-fixture layer, this is a real robustness gap. **Fix:** return shape-appropriate empties (or make components null-safe); at minimum log the unmocked path.

---

## ⚪ P3
- **FE3** `api.ts` redirects to `/maintenance` on **any** 503 from **any** endpoint — 503 is overloaded as "maintenance". A dependency returning 503 (not actual maintenance) falsely bounces the user to the maintenance page (this is exactly why the coach kill-switch had to return 403, not 503 — P2 era). Consider gating the redirect on a maintenance-specific marker.
- **FE4 (doc-stale)** `CLAUDE.md` states "Detection runs client-side in `AlertContext` using trades from API." **False** — `AlertContext` explicitly documents "backend BehaviorEngine is the ONLY engine; frontend patternDetector.ts removed"; it fetches `risk_alerts` + refetches on WS events. → P13 CLAUDE.md fix.
- **FE5 (confirms E1)** `components/analytics/ExportReportButton.tsx:93` calls `/api/behavioral/analysis` → the **legacy** `behavioral_analysis_service` engine. FE side of the dual-engine (P2-E1). Repoint at BehaviorEngine data or retire the legacy engine.

## ✅ Solid (credit — verified codebase-wide)
- **Chart-axis rule clean:** **0** occurrences of `formatCurrency` on a `tickFormatter` (the overflow/dropped-minus footgun); **9** correct `formatAxisCurrency`. The documented discipline holds everywhere.
- **Real-time client mirrors the backend:** `WebSocketContext` persists `last_event_id` per account in localStorage, reconnects with `?since=`, exponential backoff reset on success — an exact match to `event_bus` replay semantics (P0). Well-built.
- **XSS-safe:** the only `dangerouslySetInnerHTML` sinks are `Chat.tsx` (all three wrapped in `DOMPurify.sanitize`) and shadcn `ui/chart.tsx` (internal CSS-vars). No `eval`, no raw `innerHTML`.
- **API layer:** response interceptor handles 401→token-expired event, 429/5xx/timeout/offline→user toasts (kills the old silent-stuck-loader), `dedupGet` collapses duplicate in-flight GETs, per-tab impersonation token overrides the user token cleanly.
- **No cross-account param use** on the FE either (consistent with the clean BE posture from P6).

## Not exhaustively line-audited (deferrable)
The 16 pages + 91 components' internal UI logic (state machines, form validation, edge-case rendering) were sampled, not each read. The error/loading-primitive rollout is **partial** (per memory: Analytics 6 tabs + 3 misleading-empty fixes done; other pages still hand-roll) — a component-by-component consistency pass is a candidate deeper dive if you want it.

## For P14 (QA)
Guest-mode render smoke on every route (FE2) · WS drop→reconnect→replay no-dupes (verified design) · token-expiry → clean re-auth · 503 handling not over-triggering maintenance (FE3) · export report vs in-app alerts consistency (FE5/E1) · XSS regression on any new innerHTML.
