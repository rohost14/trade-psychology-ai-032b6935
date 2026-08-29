# Risk Infrastructure — Consolidated Plan and Status

**29 Aug 2026. Consolidates the existing audit documents. Not a fresh audit.**

Sources already established and NOT re-derived: `SEMANTIC_CONTRACT.md` ·
`CANONICAL_TRADING_SEMANTICS.md` · `PHASE0_CLASSIFICATION.md` ·
`RISK_QUANTITIES_AND_MARGIN.md` · `MARGIN_VALIDATION_MATRIX.md` ·
`INSTRUMENT_MASTER_SPEC.md` · `DETECTOR_RISK_DEPENDENCY_MAP.md` ·
`RISK_LAYER_ARCHITECTURE.md` · `RISK_AND_MARGIN_VERIFICATION.md`.

---

## ALREADY FIXED

| # | item | evidence |
|---|---|---|
| F8 | `is_comparable` false for unclassifiable instruments | scenario baseline |
| F9 | `parse_symbol` abstains instead of returning `EQ` | baseline |
| F7 | contract multiplier reaches the denominator | baseline |
| F11 | BSE monthlies no longer inherit NSE's weekday rule | baseline |
| F3 | short option capital = SPAN of contract notional, not of premium received | measured |
| **F15** | **parser reads 2-digit, half-rupee and hyphenated-underlying strikes** | 17 book symbols; **654 half-rupee strikes exist in one day's universe** |
| **F16** | **`or "EQ"` deleted at both sites; it was cancelling F9** | source-scanning guard test |
| **calendar-spread abstention** | multi-expiry margin is now `reliable = False` | measured **−29.6%** understatement |

## SAFE TO IMPLEMENT NOW — done this phase, wired to nothing

| item | where |
|---|---|
| contract specification type, effective-dated, immutable | `app/core/contract_spec.py` |
| exchange coverage matrix with explicit abstention | `app/core/exchange_support.py` |
| instrument master: exchange-stated → derived → unavailable | `app/services/instrument_master.py` |
| risk quantity API — A/B/C as separate **types** | `app/core/risk_quantities.py` |
| comparability rule; refusal returns `None` | same |
| broker margin capture, `orders` and `basket` modes | `zerodha_service.get_order_margins` |
| NSE F&O margin model | `app/core/margin_model.py` |
| infrastructure regression suite, 39 cases | `tests/semantics/test_risk_infrastructure.py` |

## REQUIRES PRIMARY-SOURCE RESEARCH — blocked, not guessed

| item | blocker |
|---|---|
| **MCX** | whether Kite's fill quantity is lots or units, confirmed against a real fill; multipliers read from MCX contract specs, not a third-party chart; how revisions are dated |
| **CDS** | quantity semantics, multiplier, tick value, its own scan ranges |
| **BFO** | BSE expiry rule (none sourced); ICCL's own SPAN parameters; whether the BSE bhavcopy carries the same stated fields |
| short option minimum charge | SPAN component, parameter not retrieved |
| ELM near index expiry | documented by Zerodha as a separate layer |
| physical delivery margin, stock F&O expiry week | not researched |
| exposure rate **2%/3.5% (Zerodha) vs 3%/5% (generic NSE)** | two published sources conflict |
| the **+5-7% short-option residual** | cause not established |
| Kite `/margins/orders` agreement with the public calculator | needs a live token |

## REQUIRES A PRODUCT / DESIGN DECISION

D1 hedge model with quantity and overlap · D2 one structure rule · D3 net
exposure (`portfolio_concentration`'s `abs()` makes a hedge *increase*
concentration) · D4 partial exits as a unit · D5 session scope · D6 rollover ·
**D7 MTF** · D8 margin vs declared capital · D9 multi-account · D10 trading
style · **D11 short equity denominator** · D12 `same_symbol_obsession` identity ·
D13 `holding_loser` hold clock.

## UNSUPPORTED — must abstain

Resting stop-loss orders (Pattern 12) · cross-underlying hedging · sector
exposure · order intent · target vs discretionary exit · holdings hedging ·
automated vs manual · simultaneous leg holding · BSE index monthly expiry ·
**MCX and CDS capital** · **MTF funded fraction**.

## INTENTIONALLY DEFERRED

**All detector wiring.** F1, F2, F4, F5, F6, F10, F12, F13, F14, F18-F24 are
detector-visible and out of scope for an infrastructure phase. F21
(`_ALIAS_NATURE` missing `capital_mismatch`) is deliberately **not** fixed here
despite being a one-line change, because it alters `death_spiral` composition.

---

## Sequence from here

1. ~~confirmed bugs → fix → tests~~ **done** (F15, F16, calendar abstention)
2. ~~infrastructure layer + harness~~ **done**
3. **margin validation against the user's Kite account** — *blocked, needs a token*
4. risk integration into detectors — *not approved*
5. impact check — `PATTERN_IMPACT_REGISTER.md`
6. Pattern 12 — *not started*
