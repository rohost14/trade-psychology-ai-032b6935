# P5 — Analytics (findings)

> Scope (read): `api/analytics.py` (3,239 LOC, ~30 endpoints — sampled the money/quantified-cost ones in
> full: `recalculate-pnl`, `unrealized-pnl`, `behaviour-cost`, `quality-breakdown`), `services/{analytics,
> order_analytics,habits,pattern_prediction,ai_personalization}_service.py` (surface + key methods).
> **Findings-only.** Analytics filter rule enforced: factual/provable + raw-P&L + no counterfactual/probabilistic-attribution.

## Verdict
The quantified-cost design **respects the analytics filter** — `behaviour-cost` in particular is a model of it. Two accuracy corrections to **earlier phases** came out of this pass (below), plus a fabricated-precision issue in the predictor and a scale concern on per-request aggregation.

---

## ✅ Corrections to earlier findings (verified this phase — honesty over consistency)

### C1 · E2 / M6 / R2 trigger is **CompletedTrade rebuild**, NOT nightly/EOD
Earlier docs (P1-M6, P2-E2, P3-R2) said the live-random-id → batch-stable-id churn that NULLs `trigger_completed_trade_id` happens "every EOD / nightly". **Verified wrong:**
- `calculate_and_update_pnl` (the delete+recreate) is called **only** from `POST /recalculate-pnl` (`analytics.py:137`) and tradebook **import** (`account_data.py:316`). **Grep: nothing in `eod_sync`/webhook/`sync_trades_for_account` calls it**, and **no frontend code calls `/recalculate-pnl`**.
- So the id-churn fires on **CompletedTrade-rebuild events**: (a) tradebook **import**, (b) **manual** `/recalculate-pnl` (currently no caller), (c) **late-fill replay** (`position_ledger._rebuild_completed_trades_after_replay`, which also rebuilds with fresh random ids).
- **Net:** for a pure-live user with no imports and no out-of-order fills, alert→trade links **stay intact** and `behaviour-cost` is correct. The bug is real but **latent/event-triggered**, not a nightly guarantee. **Severity of E2/M6 downgrades P1→P2**, but the fix is unchanged (live builder should use `_stable_ct_id`). Late-fill replay makes it more than theoretical.

### C2 · `ai_personalization_service` has **no LLM** — scale-doc B2/CR4 claim is false
`SCALABILITY_REVIEW_10K.md` (B2/CR4) states the 18:15 re-learn calls `learn_patterns` which "may call the LLM → 10k LLM calls back-to-back". **Grep-verified false:** `ai_personalization_service` contains **zero** LLM/OpenRouter/ai_service references — `learn_patterns` is pure SQL+Python stats (win-rate danger_hours/danger_days). The **sequential all-account loop is still a real scale issue** (one task, one session, all accounts — R4/B2), but there is **no LLM cost/rate-limit explosion**. Correct the scale doc.

---

## 🟡 P1→P2 (see C1)

### Q1 · `behaviour-cost` (flagship "patterns → money") under-counts after any CompletedTrade rebuild · correctness
> ✅ **FIXED 2026-07-26 (via M6)** — with the live builder now using the shared stable id, the `RiskAlert.trigger_completed_trade_id → CompletedTrade.id` join no longer breaks on rebuild, so behaviour-cost stops dropping flagged trades.
`GET /behaviour-cost` inner-joins `RiskAlert.trigger_completed_trade_id == CompletedTrade.id` (and the same for the constitution `rule_rows`). When that link is NULLed by a CT rebuild (C1: import / recalc / late-fill replay), those alerts **silently drop out** of the metric (`isnot(None)` filter + inner join). Result: the headline "your patterns cost ₹X" **understates** after an import or replay. The endpoint's design is otherwise **exactly right** (raw realized P&L of DISTINCT flagged trades, deduped by trade, "realized P&L on flagged trades" framing — no counterfactual). Fix = the same `_stable_ct_id` change (removes the churn) or re-point the link on rebuild.

---

## 🟡 P2

### Q2 · `pattern_prediction_service` presents hand-tuned heuristics as "probabilities" · product-integrity
`predict_patterns` returns `"probability": min(95, base + increments)` per pattern (e.g. revenge base 10 + fixed bumps → "73%"). These are **magic-number heuristics**, not calibrated probabilities, but are surfaced (Dashboard `PredictiveContextStrip`, cooldown pre-trade alert) as precise percentages — **spurious statistical precision**. Not an analytics-filter violation (it's forward behavioural prediction, not past-P&L attribution), but the fake precision is misleading and the thresholds are unvalidated. Consider qualitative bands (low/med/high) or label them "signal strength", and get product sign-off on the numbers.

### Q3 · Heavy per-request Python aggregation over 90–180d windows, uncached · scale
Several endpoints (`quality-breakdown`, `overview`, `performance`, `risk-metrics`, `timing-heatmap`) each load large CompletedTrade windows (up to 180d) into Python and aggregate per request, with **no caching** (unlike admin aggregates) and behind the **broken per-IP limiter** (P0-F3/A1). At 10k concurrent, overlapping heavy loads = DB + CPU + memory pressure. Push aggregation into SQL and/or add a short per-account cache. (B-class scale.)

---

## ⚪ P3
- **Q4** `unrealized-pnl` endpoint surfaces the **P1-M3** MCX/CDS multiplier bug (understated commodity open P&L) — noted as the delivery point, fix lives in M3.
- **Q5** `_underlying` regex in `quality-breakdown` (`^([A-Z&\-]+?)(\d|[A-Z]{3}\d{2})`) is fragile for equity symbols (e.g. `M&M`); analytics is F&O-focused so low impact, but note.
- **Q6** `analytics.py` at 3,239 LOC / ~30 endpoints in one file is a maintainability/merge-conflict hotspot (prior-audit item) — split into sub-routers. → ledger.

## ✅ Solid (credit)
`behaviour-cost` is a textbook application of the analytics filter (raw P&L, distinct-trade dedup, no counterfactual, careful framing). `quality-breakdown` computes a deterministic rubric **live** (does **not** read the ghost `quality_score` column — good). Endpoints consistently use `get_verified_broker_account_id` + per-account scoping + windowed queries. Error handling wraps each endpoint (though the broken limiter + no-cache are the scale gaps).

## For P14 (QA)
Assert `behaviour-cost` totals are stable across an import/replay (Q1) · MCX unrealized (Q4) · analytics-endpoint latency + memory at 10k with realistic 180d histories (Q3) · pattern-prediction numbers reviewed by product (Q2). Update `SCALABILITY_REVIEW_10K.md` per C2.
