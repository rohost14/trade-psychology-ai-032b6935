# Detector → Risk Quantity Dependency Map

**29 Aug 2026. Deliverable 5. INFORMATIONAL ONLY — no detector is changed,
reviewed, retired or retuned by this document.**

Which of the three quantities each detector actually consumes. Built by reading
`behavior_engine.py`, not from the registry's descriptions.

Quantities per [`RISK_LAYER_ARCHITECTURE.md`](RISK_LAYER_ARCHITECTURE.md):
**A** entry value · **B** P&L · **C** capital requirement (margin) · **flag**
bounded/unbounded.

23 detectors, 6 aliases, 29 pattern types.

---

## Needs NO margin — 15 detectors

These are complete with A and B. **Adding margin to them would be a regression**,
not an improvement: a percentage of the trade's own entry value is invariant to
account size and is exactly the behavioural signal wanted.

| detector | quantity | note |
|---|---|---|
| `premium_loss_event` | B / A | loss as % of premium. Guards `direction != LONG` explicitly |
| `options_premium_avg_down` | A | premium deployed across adds; also direction-guarded |
| `panic_exit` | B + time | |
| `early_exit` | B + time | |
| `holding_loser` *(alias)* | B + time | hold clock resets on an add — a D-item, not a margin issue |
| `rapid_reentry` | time only | |
| `overtrading_burst` | count | the only detector using `count_structures` on all paths |
| `daily_overtrading` *(alias)* | count | |
| `session_meltdown` | B | session aggregate |
| `win_rate_collapse` | B | |
| ~~`time_of_day_bias`~~ | — | RETIRED 2026-09-01 (Reviews 25-27) — the learned danger hours do not survive into a second period |
| `strategy_breakdown` | B | |
| `end_of_session_mis_panic` | B + time | product-scoped |
| `fomo_entry` | time + count | |
| `cooldown_violation` | none | reads no trade quantity at all — F18 |

---

## Needs comparable sizing (A, gated) — 4 detectors

These compare one trade's size to another's. They do **not** need margin; they
need **comparability**. Premium against premium is fine. Premium against a
future's notional is not.

| detector | current basis | correct basis |
|---|---|---|
| `martingale_behaviour` | `risk_basis` for both legs — but takes ratios **across denominator kinds without reading `.kind`** | A, refusing when `is_comparable` is false on either side |
| `revenge_trade` | `risk_basis` | A + comparability gate. **FROZEN** — not touched |
| `adding_to_adverse_position` | `risk_basis` | A within one position, so comparability is automatic |
| `winning_streak_overconfidence` | raw quantity vs an average | A. Note F23: a zero baseline makes its test unconditional |

**The gate matters more than the number here.** A margin figure would not fix a
martingale comparison between a long option and a short option; refusing to make
it would.

---

## Genuinely needs margin (C) — 4 detectors

The only places where premium is the wrong quantity rather than a differently-
scaled one.

| detector | question | today | needed |
|---|---|---|---|
| `excess_exposure` | position vs trading capital | `estimate_capital_at_risk` **direct — bypasses `risk_basis` entirely (F17)** | **C**, portfolio scope, provenance-tagged |
| `constitution_violation` / `max_trade_risk` | per-trade risk vs declared limit | same direct call, same bypass | **C** |
| `overexposure` *(alias)* | concentration vs capital | position query | **C** |
| `portfolio_concentration` *(alias)* | share of book in one underlying | `abs()` of signed quantity, so **a hedge increases concentration** | **C**, hedge-adjusted — needs the D3 netting decision first |

`capital_mismatch` *(alias)* also reasons about capital; it is dropped from
`death_spiral` today via F21's missing `_ALIAS_NATURE` entry.

---

## Needs the flag, not a number — 0 today

Nothing currently reads `DenominatorKind` to say *"this loss is not capped by
what you committed"*. On a book of 911 long options and 1 short that has cost
nothing. It becomes the single most important message the moment a user writes
options.

---

## Summary

| need | count |
|---|---|
| no margin | **15** |
| comparability gate on A | **4** |
| margin (C) | **4** |
| flag | 0 |

**Roughly two-thirds of the engine never needs a margin number at all.** This is
the quantitative form of the earlier conclusion: margin is required for
capital-relative questions, and those are a minority of the engine.

It also bounds the blast radius. An exact margin layer changes **4 detectors**,
and 2 of those cannot even see it until **F17** lands.

---

## Ordering implied — not a proposal to act

1. **F17** — route `excess_exposure` and `constitution_violation` through
   `risk_basis`. Without it the layer is invisible to the only detectors that
   want it.
2. **comparability gate** on the 4 sizing detectors — a refusal, not a new number.
3. **C from `margin_model`**, tagged `COMPUTED`.
4. **`BROKER` capture** at order time.
5. **the flag** — new messaging, and the only item here that is a product change.

**None of this is approved. No detector is modified by this document.**
