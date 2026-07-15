# Alerts Page — Deep Review & Analysis

*Date: 2026-07-15. Scope: the `/alerts` page (Behavioral Alerts) — every feature, its data flow, real-vs-dummy data, backend, UX/UI, product value, and recommendations. Findings only — nothing implemented.*

*Severity of findings: **P1** = user-visible breakage, **P2** = wrong/misleading or dead feature, **P3** = polish. **PROD** = product/strategy observation.*

> **UPDATE 2026-07-15 — P1 & P2 bugs FIXED** (build/tsc verified):
> - **5.1 severity vocabulary** — `Alerts.tsx` migrated fully to `danger/caution/positive` (History mapping via `normalizeSeverityStr`, Patterns severities/order/worst fixed, header stat now "N danger", filter options All/Danger/Caution). Cleared the 5 related TypeScript errors.
> - **5.2 dead `estimated_cost`** — removed from `AlertRow`, `AlertDetailSheet`, `PatternsTab` (total), and `AlertHistorySheet`.
> - **5.3 history inconsistency** — resolved via 5.1 (both surfaces now share the 3-level scale); `AlertHistorySheet` also now shows the proper `SEV_LABEL` instead of raw lowercase. The two-surfaces *redundancy* is left as a product decision (nav bell not removed).
> - **5.4 "48 hours" copy** — corrected to "last 7 days".
> Remaining items below (PROD asks, P3 polish, confidence, response-stats surfacing) are unchanged and still open.

---

## 1. What this page is, and why it exists

The Alerts page is the **primary surface of the entire product**. TradeMentor's thesis is "mirror, not blocker" — it does not stop trades; it shows the trader facts about their own behaviour. A behavioral alert (revenge trade, overtrading, martingale, panic exit, …) *is* that mirror. Everything else — dashboard, analytics, coach — is supporting cast. If the alerts are good, the product has a reason to exist; if they're noisy or wrong, nothing else saves it.

Route: `src/pages/Alerts.tsx` (514 lines). Title "Behavioral Alerts". Three tabs: **Live**, **History**, **Patterns**. Plus a right-side **detail sheet** (`AlertDetailSheet.tsx`).

---

## 2. Current features & functionality

### 2.1 Page header
- Title + unread count badge (`unacknowledgedCount`).
- Inline stat strip: `total`, `critical`, `unread` (`Alerts.tsx:448-474`).

### 2.2 Live tab (`LiveTab`)
- Shows **unacknowledged** alerts, newest first, from `AlertContext` (7-day window).
- Each row (`AlertRow`): severity dot + name + severity label, a "**N× this week**" frequency badge (≥2), a "Reviewed" chip, the engine-generated evidence line (`pattern.description`), time-ago, and an estimated-cost figure.
- "**Mark all reviewed**" bulk action.
- Empty state: "Clean session — you're trading with discipline."

### 2.3 History tab (`HistoryTab`)
- **Independent data fetch** (`/api/risk/alerts?hours=`) so users can look past the 7-day live window.
- Period selector: 7d / 30d / 90d. Severity filter: All / Critical / High / Caution / Info.
- Same `AlertRow` rendering. Count readout.

### 2.4 Patterns tab (`PatternsTab`)
- Aggregates `AlertContext` alerts by pattern type: count, frequency bar (relative to max), per-severity breakdown, total estimated cost, last-seen time.
- Sorted by frequency. Intended as "which behaviours recur most."

### 2.5 Alert detail sheet (`AlertDetailSheet.tsx`, 361 lines)
Genuinely rich, and the best part of the page:
- Header: severity, name, "N× this week", exact IST time.
- Evidence line + (conditional) estimated cost.
- **Data facts table** — per-pattern key numbers via `buildFacts()` (e.g. revenge_trade → prior symbol, prior loss, gap-to-reentry).
- **Trades involved** — real symbol/qty/P&L rows when the engine attaches `losing_trades` / `trade_list`.
- **"Why this fired"** — the engine's stacked confidence signals (Engine v2 A.8).
- **Pattern explanation** (`PATTERN_EXPLANATIONS`) + **Trader context benchmark** (`TRADER_BENCHMARKS`).
- Footer: **Mark as reviewed** + **Ask AI** (deep-links to `/chat?q=…` pre-filled with the alert).

### 2.6 Backend
- `GET /api/risk/alerts?hours=` (`risk.py:56`) — list from `risk_alerts` table, with `unacknowledged_count`.
- `POST /api/risk/alerts/{id}/acknowledge` (`risk.py:85`) — sets `acknowledged_at`.
- `GET /api/risk/state` — safe/caution/danger rollup (last 4h) for the dashboard.
- `GET /api/risk/scores` — Phase-5 behaviour scores.
- `GET /api/risk/alert-response-stats` (`risk.py:139`) — **ignored-vs-acted-on per pattern** ("revenge alerts ignored: 18"). Built, documented… **and never called by the frontend** (see §5.6).
- Alert generation: `BehaviorEngine.analyze()` → `RiskAlert` rows (+ `BehaviorEvent` evidence) → Redis event bus → `AlertContext` refetch → toast + rows. Delivery to WhatsApp via `alert_service.py` (Gupshup), push via `push_notification_service`.

---

## 3. Real data or dummy data?

**Verdict: real data.** All three tabs read the live `risk_alerts` table:
- Live/Patterns via `AlertContext` → `/api/risk/alerts?hours=168`.
- History via its own `/api/risk/alerts?hours=` fetch.
- Alert descriptions, facts, "trades involved", and "why this fired" are all produced by `BehaviorEngine` from the user's actual CompletedTrades — not mocked.
- No `mock`/`dummy`/`sample`/hardcoded-alert references exist in the page or its components.

**The one exception — `estimated_cost` is effectively dummy (always absent).** See §5.2. The UI renders "₹X est." and Patterns "total cost", but the engine never populates `details.estimated_cost` (grep in `behavior_engine.py` / `trade_tasks.py` = zero hits). So those figures never appear — a value proposition that looks wired but isn't.

---

## 4. Is it valuable? Will people pay? (product view)

**PROD-1 — This is the product, so the bar is "is the alert worth the subscription."** Honest read:
- **Strength:** the alerts are evidence-based, specific, and personalized (real symbols, real losses, real gaps), with a genuinely good detail sheet (facts + explanation + benchmark + Ask-AI). That's differentiated — most "trading journals" don't detect behaviour in real time.
- **Weakness for willingness-to-pay:** every alert here is **post-trade** — it fires after a CompletedTrade closes. Post-mortem awareness has real but *limited* stopping power. The trader already did the revenge trade. The paid "aha" is either (a) **pattern awareness over time** ("I revenge-trade every Friday and it costs me") or (b) **pre-trade / in-the-moment nudges** ("you're about to re-enter 4 min after a stop"). The page today leans (a); (b) is where retention/willingness-to-pay actually lives, and it's thin.
- **The single most valuable unused asset:** `alert-response-stats` — "you ignored 80% of your revenge alerts." That meta-insight ("you don't even listen to your own mirror") is the emotional hook that makes people either commit or churn honestly. It exists in the backend and is shown **nowhere**.

**Will people pay for the page as-is?** For pattern *awareness* — some will. For behaviour *change* — not yet, because it's retrospective and doesn't close the loop (no "did this alert help / did you stop?" feedback, no cost quantification, no pre-trade warning surfaced here). The raw material is strong; the packaging under-delivers on the "so what do I do now" question.

---

## 5. Findings (bugs, dead features, inconsistencies)

### 5.1 [P1] Severity vocabulary mismatch — real rendering breakage
The app migrated to a **3-level** severity system — `PatternSeverity = 'danger' | 'caution' | 'positive'` (`types/patterns.ts:33`), and `AlertContext.normalizeSeverity()` maps every backend severity (`info/caution/danger/critical`) into it. But **`Alerts.tsx` was never updated off the old 4-level scale** (`critical / high / medium / low`). Consequences, all live today:

- **Header stats are wrong.** `stats.critical`/`stats.high` filter `severity === 'critical'` / `'high'` (`Alerts.tsx:450-451`), but `AlertContext` alerts are only ever `danger/caution/positive`. So **"N critical" in the header is always 0**, regardless of how many danger alerts exist.
- **History tab renders blank severity.** `HistoryTab` maps raw backend severity through its *own* map to `'high'/'medium'/'critical'/'low'` (`Alerts.tsx:231`), then `AlertRow` does `SEV_DOT[sev]` / `SEV_LABEL[sev]` — but `SEV_DOT`/`SEV_LABEL` are keyed by `danger/caution/positive`. `SEV_DOT['high']` is `undefined` → **colorless dot and blank severity label** for every History row. (Left border still works because `severityBorderClass` normalizes; the dot/label don't.)
- **Patterns tab math is broken.** `severities` is keyed `{critical,high,medium,low}` but `alert.pattern.severity` is `danger/caution` → `severities['danger']++` on `undefined` → `NaN`. `worstSeverity` uses `SEVERITY_ORDER=['critical','high','medium','low']`; `indexOf('danger') === -1` → wrong "worst" every time.
- **Detail sheet opened from History** inherits the bad `'high'` severity → header dot/label also break.
- These are exactly the pre-existing TypeScript errors on `Alerts.tsx:231,341,366,450-451` — the compiler is flagging this mismatch.

Net: **the Live tab mostly works** (it renders AlertContext severities directly), but **History and Patterns are visibly degraded and the header critical count is dead.**

### 5.2 [P2] `estimated_cost` is a dead value proposition
Rendered in three places (`AlertRow`, `AlertDetailSheet`, `PatternsTab` total) but **never populated by the engine**. Every "₹X est." and pattern "total cost" silently evaluates to 0 and hides. Either wire a real cost model (careful — the product just decided *not* to model brokerage/charges; "estimated cost of the behaviour" is a different, defensible number = the realized loss on the flagged trades) or remove the UI so the page doesn't imply a feature it doesn't have.

### 5.3 [P2] Two parallel History surfaces
There's the **History tab** on this page *and* a separate **`AlertHistorySheet`** slide-out wired into `Layout.tsx` and `Sidebar.tsx`. Two different history UIs over the same data, with **different severity mapping** → they can render the same alert inconsistently. Consolidate to one.

### 5.4 [P2] Patterns tab copy is wrong
Says "detected in the last **48 hours**" (`Alerts.tsx:388`) but it aggregates `AlertContext`, which fetches a **7-day** window (`AlertContext.tsx:290`). Misleading.

### 5.5 [P3] `confidence` is computed but never shown
The engine computes and stores per-alert `confidence` (0-100, `risk_alert.py`), surfaced nowhere in the UI (only a code comment references it). For a behavioural tool, "we're 90% sure this was revenge trading" is a trust-building number worth showing — currently wasted.

### 5.6 [PROD-2] The best insight endpoint is unsurfaced
`GET /api/risk/alert-response-stats` returns, per pattern, how many alerts the user **ignored vs acknowledged** — the honest "do you even respond to your mirror" metric. Fully built, zero frontend usage. This is the highest-leverage thing to surface on this page.

### 5.7 [P3] Acknowledge semantics are thin
"Acknowledge" = "Mark as reviewed" = sets `acknowledged_at`. There's no signal of *what the user did* (stopped trading? took the trade anyway? found it useful/not?). So the app can't learn which alerts help, and can't compute a real "alerts that changed behaviour" number. `acknowledgeAll` also fires N parallel POSTs (`AlertContext.tsx:412`) — fine now, wants a bulk endpoint at scale.

### 5.8 [P3] "Live" is a 7-day unacknowledged list, not "live"
The Live tab shows all *unacknowledged* alerts from the last 7 days, not today's session. A week-old un-reviewed alert sits in "Live." Arguably fine, but the label oversells immediacy; consider "Unreviewed" or a session/day scoping.

---

## 6. What's genuinely good (keep)

- **Evidence-first alerts** with real trade numbers — the core is strong and honest.
- **Detail sheet** — facts table + "trades involved" + "why this fired" signals + explanation + trader benchmark + Ask-AI deep link. This is the product's best-designed surface.
- **Event-driven, no polling** (after the recent cleanup) — alerts arrive via WebSocket + reconnect replay.
- **Frequency badge** ("N× this week") — the right instinct: recurrence matters more than any single instance.
- **Clean empty/loading states**; market-hours-gated toasts; persistent "seen" set so alerts don't re-toast across reloads.
- **Ask-AI hand-off** — turning an alert into a coaching conversation is a smart, sticky pattern.

---

## 7. What to add (highest product leverage first)

1. **Surface `alert-response-stats`** — a "You and your alerts" strip: "Revenge alerts: 18 fired, 3 acted on." This is the accountability mirror and it already exists server-side.
2. **Close the feedback loop** — on acknowledge, one tap: "Did you stop? / Took it anyway / Not useful." Enables a real "alerts that changed your behaviour" metric and trains alert quality. This is what converts awareness into paid behaviour-change.
3. **Real impact quantification** — replace dead `estimated_cost` with the realized loss on the flagged trades (data the ledger already has): "this revenge cluster cost ₹12,400 this month." Concrete money is the willingness-to-pay lever.
4. **Per-pattern mute/snooze** — let users silence a pattern they disagree with (with a "you muted this" honesty note). Reduces the #1 churn cause for alert products: noise.
5. **Pre-trade / in-the-moment presence on this page** — the early-warning system exists (push at 70% loss / 80% trade count). Surface those *here* as a distinct "heads-up" stream so the page isn't purely retrospective.
6. **Weekly behavioural digest** — "your week in patterns" (email/WhatsApp + an in-page card). Retention + a natural re-engagement hook.
7. **Filter/group by pattern type** in Live/History (only severity+period exist today).
8. **Alert → journal → trade linking** on the page (the journal linkage exists in the sheet; make it navigable both ways).

---

## 8. What to remove / modify

- **Fix the severity vocabulary (5.1)** — migrate `Alerts.tsx` fully onto `danger/caution/positive` (or a clearly-defined 4-level with a matching `SEV_*` map). This is the top correctness fix; it also clears 5 of the repo's TypeScript errors.
- **Consolidate the two History UIs (5.3)** into one.
- **Wire or remove `estimated_cost` (5.2)** — don't ship a figure that never appears.
- **Fix the "48 hours" copy (5.4).**
- **Reconsider the "Patterns" tab** — as-is it's a frequency list that overlaps My Patterns. Either make it the home of the response-stats + impact quantification (§7.1, §7.3), or fold it into My Patterns and drop the tab.

---

## 9. Cross-cutting / things possibly overlooked

- **Severity is doing two jobs** (how bad × how certain). The engine already separates `severity` and `confidence`; the UI collapses them. Showing both would raise trust and reduce "why did this fire?" confusion.
- **No de-dup visibility.** The engine dedups/suppresses alerts (constitution breach wins, strategy legs suppressed); the user never sees "we suppressed 3 related alerts." A subtle "grouped" affordance would explain quiet periods and prevent "why didn't it fire?" doubt.
- **Analytics gap.** No funnel on the alerts themselves: fired → seen → acknowledged → acted → behaviour-changed. Without it there's no way to prove (to the user or to yourselves) that the mirror works — which is the whole pitch.
- **Accessibility:** rows are buttons with aria-labels (good); the severity-color-only cues (dot) need the text label to always render — which 5.1 currently breaks in History/Patterns.
- **Scale:** `acknowledgeAll` fan-out and per-tab full refetch are fine now; both want batching before large DAU.
- **Trust/compliance:** `TRADER_BENCHMARKS` present hardcoded statistics ("win rate below 30%…") as fact. For a SEBI-sensitive product, keep these clearly qualitative or cite, or they become a liability.

---

## 10. Priority summary

| Priority | Item | Type |
|---|---|---|
| P1 | Severity vocabulary mismatch → History/Patterns/header broken (5.1) | Bug |
| P2 | Dead `estimated_cost` shown as a feature (5.2) | Dead feature |
| P2 | Two parallel history UIs, inconsistent (5.3) | Redundancy |
| P2 | "48 hours" copy wrong (5.4) | Bug |
| PROD | Surface `alert-response-stats` — the accountability mirror (5.6 / 7.1) | Product |
| PROD | Feedback loop on acknowledge → real "behaviour changed" metric (7.2) | Product |
| PROD | Real impact quantification (7.3) | Product |
| PROD | Per-pattern mute + pre-trade heads-up stream (7.4 / 7.5) | Product |
| P3 | Surface `confidence`; acknowledge semantics; "Live" scoping; benchmarks-as-fact | Polish/Trust |

*Files reviewed: `src/pages/Alerts.tsx`, `src/components/alerts/{AlertDetailSheet,AlertHistorySheet,TokenExpiredBanner}.tsx`, `src/contexts/AlertContext.tsx`, `src/lib/alertSeverity.ts`, `src/types/patterns.ts`; `backend/app/api/risk.py`, `backend/app/api/alerts.py`, `backend/app/services/alert_service.py`, `backend/app/models/risk_alert.py`.*
