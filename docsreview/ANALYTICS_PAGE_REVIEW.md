# Analytics Page — Deep Review & Analysis

*Date: 2026-07-15. Scope: the `/analytics` page (6 tabs) + its `analytics.py` backend. Every feature, data flow, real-vs-dummy, UX, product value, recommendations. Findings only — nothing implemented.*

*Severity: **P1** = wrong data shown as fact, **P2** = misleading label / minor correctness, **P3** = polish / tech-debt. **PROD** = product/strategy observation.*

---

## 1. Headline

**This is by far the strongest, most mature page reviewed.** Well-architected shell (ErrorBoundary + Suspense + 6 lazy tabs + period selector + export + compliance disclaimer + instrument drill-down), **every tab runs on real data**, and the statistics are genuinely professional — 95% confidence-interval edge validation, profit factor, expectancy, disposition effect, R:R, trade-sequence degradation, conditional performance vs personal baseline, on-the-fly trade quality scoring. **No mock/dummy data. None of the bug classes that broke Alerts and My Patterns** (no severity-vocab mismatch, no unimported `cn`, no dead `estimated_cost`). The work needed here is minor labeling + dead-code cleanup, not repair.

---

## 2. Tabs & features

| Tab | Endpoints (all real) | Shows |
|---|---|---|
| **Overview** | `overview`, `overview` (2× window), `edge-confidence`, `performance` | 6 KPIs (P&L, win rate, profit factor, expectancy, win-days %, max drawdown) with period-over-period deltas; statistical edge banner (95% CI); equity curve; daily P&L; P&L attribution donut; product mix; streaks |
| **Edge** | `performance`, `timing-heatmap` | Per-underlying edge, hour/day/size breakdowns, session windows, timing heatmap; instrument drill-down |
| **Trade DNA** | `quality-breakdown`, `critical-trades`, `pnl-percent`, `trade-sequence` | Clean-vs-flagged quality split, best/worst 5, R:R, **disposition effect**, intraday trade-sequence win-rate decay, hold-time buckets, searchable trade log with quality score |
| **Behavior** | `risk-metrics`, `conditional-performance`, `journal-correlation` | Per-pattern alert cost (heeded/ignored + post-alert P&L), conditional performance (after-loss / first-30min / quick-reentry vs baseline), emotion-vs-P&L from journal |
| **Sessions** | `overview` (90d), `expiry-pattern`, `conditional-performance` | Session/day/expiry breakdowns |
| **BTST** | `btst` | Overnight/weekend holds, overnight reversals, monthly P&L, trade table |

Plus `InstrumentPanel` (per-underlying drill-down via `instrument`), `ExportReportButton`, `ComplianceDisclaimer`.

---

## 3. Real data or dummy?

**All real.** Every tab fetches live `analytics.py` endpoints that query `CompletedTrade` / `RiskAlert` / `JournalEntry` / features. Verified spot-checks:
- **Trade DNA quality score is legitimately computed** — `quality-breakdown` scores each trade 0–8 on the fly from real signals (no alert pre-entry, size ≤1.5× 30-day avg, personal strong hour, instrument WR, consecutive-loss state, expiry timing). It does **not** use the dead `CompletedTrade.quality_score` field (that field was only ever read by the now-removed My Patterns weekly score).
- **Behavior tab's "ignored cost" is real** — it's the actual realized P&L on trades where an alert was ignored, not an estimate. Unlike the dead `estimated_cost` elsewhere, this is defensible and aligns with the raw-P&L policy.
- BTST reversal detection uses the real `overnight_close_price` captured at backfill.

---

## 4. Product value

**PROD-1 — Genuinely differentiated and "pay-worthy" content.** This is the page that could justify a subscription to a serious retail F&O trader: statistical edge validation, disposition effect, trade-sequence overtrading detection, conditional performance vs your own baseline. Most retail journals don't come close. If anything, the *quality of thinking* here is higher than the rest of the app.

**PROD-2 — But it's arguably too advanced for the stated audience, and tonally off-brand.** The product's positioning is a behavioural *mirror* for retail traders ("show facts, not restrictions"). This page assumes the user knows what **profit factor**, **expectancy**, **R:R ratio**, **disposition effect**, and **95% confidence interval** mean. Many retail F&O traders won't. There's little inline "what this means / what to do" scaffolding (some tabs have a one-line takeaway, many metrics don't). Risk: the page impresses but doesn't *change behaviour* for the median user — it's a quant dashboard bolted onto a psychology app.

**PROD-3 — Real overlap with Alerts + My Patterns.** The Behavior tab's per-pattern heeded/ignored + post-alert P&L is a richer version of the **alert-response-stats** card I just added to Alerts, and overlaps My Patterns' pattern frequency. The clean-vs-flagged quality story appears in both Trade DNA and (formerly) the discipline score. Three surfaces tell overlapping "how your behaviour costs you" stories with different numbers. Worth an editorial decision on which page owns which story.

---

## 5. Findings

### 5.1 [P2] "Net P&L" is actually gross
Overview's hero KPI is labeled **"Net P&L"** (`OverviewTab.tsx:186`), but per the product's decision all P&L is **raw / gross** (no brokerage/STT/charges). Calling it "Net" is the one place on this page that contradicts that policy and could mislead ("net" implies after costs). Relabel "P&L" (or "Gross P&L"); the footer `ComplianceDisclaimer` should carry the "before charges" caveat. Check other tabs for stray "net" wording too.

### 5.2 [P3] Overview period-over-period deltas are approximated
The "vs prev" deltas derive the previous period by fetching a 2× window and subtracting the current (`OverviewTab.tsx:264-273`). Profit-factor and expectancy "prev" are explicitly rough (`prevPF = kP.profit_factor` — the 2× window's PF, not the true prior period; comment says "rough"). So the PF/expectancy delta chips can be misleading. Either compute a true prior-period call or drop the delta on the metrics that can't be derived cleanly.

### 5.3 [P3 / tech-debt] Significant orphaned code from the 8-tab → 6-tab rewrite
The page was rewritten (old `SummaryTab/PatternsTab/TradesTab/EdgeMapTab/ExpiryTab/JournalCorrelationTab/PnlPercentTab` were deleted). Left behind, **imported by nothing**:
- Frontend components: `DnaCard`, `RecoveryCard`, `RiskTab`, `TimingTab`, `PerformanceTab`, `ProgressTab` (all 0 imports).
- Their backend endpoints are consequently dead or nearly so: `edge-map`, `recovery-pattern`, `trading-dna`, `options-behavior` (referenced only by the orphaned components), and `discipline-summary` (now orphaned after the My Patterns cleanup).
This is ~6 dead components + ~5 dead endpoints of maintenance surface. Per the archive-not-delete rule, move the components to `_archive/` and mark the endpoints dead (or remove). Not user-facing, but it's real rot and it inflates the analytics bundle.

### 5.4 [P3] Minor
- `EquityTooltip`/`DailyTooltip`/`PieTooltip`/`SeqTooltip`/`HoldTooltip` typed `any` (pre-existing style; harmless).
- Behavior tab "total ignored cost" header sums post-alert P&L across patterns — if the net is positive it still reads "ignored cost", which is odd wording (per-row red/green is correct).
- Several `extractUnderlying`/`classifyExpiry` regex helpers are duplicated across OverviewTab/EdgeTab (drift risk — same class as the symbol-parser we extracted for the dashboard).

**No P0/P1 found.** No wrong-data-as-fact, no crashes.

---

## 6. What's good (keep / celebrate)

- **Architecture:** lazy tabs + ErrorBoundary + Suspense + per-tab loading/error/retry + abort-on-unmount. Textbook.
- **Statistical honesty:** the edge-confidence CI ("edge not yet confirmed, n=…") is the rare analytics feature that tells users when their sample is too small to trust — genuinely responsible.
- **Behavioural depth:** disposition effect, conditional performance vs personal baseline, trade-sequence decay, on-the-fly quality scoring — this is the good stuff.
- **Real, correct P&L** (gross, consistent with policy) everywhere; instrument drill-down; export; compliance disclaimer present.

---

## 7. Recommendations

1. **Fix the "Net P&L" label (5.1)** — the one policy inconsistency.
2. **Decide the audience & add scaffolding** (PROD-2): either (a) keep it pro and add short "what this means / what to do" lines under each advanced metric, or (b) split a simple "Overview + Edge" default view from an "Advanced" section. The content is excellent; the accessibility to a retail trader is the gap.
3. **De-duplicate the behavioural story** (PROD-3): let Analytics own the *quantified* behaviour cost, Alerts own the *live* response loop, My Patterns own the *at-a-glance* scorecard — and cross-link rather than recompute.
4. **Archive the orphaned rewrite code (5.3)** — move 6 dead components to `_archive/`, retire the dead endpoints.
5. **Tidy** (5.2, 5.4): honest prev-period deltas or none; extract the shared symbol/expiry regex helpers.

*Files reviewed: `src/pages/Analytics.tsx`; `src/components/analytics/{OverviewTab,EdgeTab,TradeDnaTab,BehaviorTab,SessionsTab,BtstTab}.tsx`; `backend/app/api/analytics.py` (overview / performance / edge-confidence / quality-breakdown / risk-metrics / conditional-performance / btst / trade-sequence / pnl-percent / expiry-pattern endpoints). Orphan/endpoint-usage confirmed by import + reference grep.*
