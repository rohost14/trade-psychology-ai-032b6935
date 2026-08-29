# Risk Quantities and Margin — design note

**29 Aug 2026. DESIGN REQUIRED. No code changed. Answers three questions raised
against the consolidated audit report.**

External facts below are sourced, not recalled. Where two published sources
disagree, both are shown.

---

## 1. "Why do we need three concepts?" — we don't. We need two and a flag.

The three proposed quantities were **A. premium exposure**, **B. maximum
theoretical loss**, **C. actual margin requirement**.

**B has no use in this app. Recommend dropping it as a quantity.**

| case | max theoretical loss | is it useful? |
|---|---|---|
| long CE / long PE | = premium paid | **duplicate of A** |
| short CE | unbounded | **cannot be a denominator** — nothing divides by infinity |
| short PE | strike × qty (bounded, but ~20× the real margin) | a number no trader or detector uses |
| futures | unbounded | same as short CE |
| short equity | unbounded | same |

For every instrument it is either a duplicate of A or unusable. It cannot be a
denominator, cannot be displayed (*"you risked ₹∞"*), and cannot be compared.

**Its only real information content is binary — is the loss bounded or not — and
we already encode exactly that**, in `DenominatorKind`:

```
LOSS_CEILING   → loss is bounded by the amount committed   (long option)
MARGIN_POSTED  → loss is NOT bounded by the amount committed (short opt, futures)
NOTIONAL       → equity
UNRELIABLE     → abstain
```

**So: two quantities and one flag.**

| # | quantity | definition | use |
|---|---|---|---|
| **1** | **entry value** | `avg_entry_price × qty × multiplier` — premium paid or received | intra-trade ratios (§2 Class 1) |
| **2** | **capital committed** | what the account actually gave up. Long option = premium paid. Short/futures = margin | position-vs-capital rules (§2 Class 3) |
| **flag** | **`DenominatorKind`** | bounded / unbounded / unreliable | the *"your loss is not capped"* message, and `is_comparable` |

The behavioural message a writer needs isn't a number — it's the flag. *"You sold
a naked call; ₹2L was blocked and the loss is not capped by it."*

---

## 2. "Do we need margin everywhere? Isn't a % of premium the same thing?"

**Largely yes — and for the current book, entirely yes.** Detectors split into
three classes by what the denominator is *for*, and margin is required in only
one of them.

### Class 1 — intra-trade ratio. Margin NOT needed. Never.

`pnl_pct`, `premium_loss_event`, `options_premium_avg_down`, `no_stoploss`'s
`loss_pct`, `holding_loser`, `early_exit`.

Denominator is the position's **own entry value**. Your reasoning is exactly
right here: ₹50 premium → lost ₹5 is −10%, and −10% is −10% whether the account
is ₹10k or ₹10L. Margin adds nothing.

**This holds for writers too**, which is the non-obvious part: a short whose
premium tripled is −200% of premium received. That is how a writer actually
thinks about the trade. The number is fine; only the *label* is wrong — call it
premium, never "capital at risk".

### Class 2 — cross-trade comparison. Margin needed only across classes.

`martingale_behaviour`, `revenge_trade` sizing, `adding_to_adverse_position`.

"Trade B is 2× trade A" requires A and B in the **same unit**. Two long options —
premium works. A long option vs a short option vs a future — premium is three
different things and the ratio is meaningless. That is precisely what
`RiskBasis.is_comparable` exists to block, and **F17 in the audit is that it is
being bypassed.**

### Class 3 — position vs account capital. Margin IS needed; premium is wrong.

`excess_exposure`, `constitution_violation`/`max_trade_risk`,
`portfolio_concentration`, capital-relative floors.

Numerator must be **money actually committed**. ₹9,000 premium *received* on a
short is not ₹9,000 committed — the account gave up ~₹2L. Using premium here is
not a rounding error; it is the wrong sign of transaction. **This is F3.**

### What this means for the current book — the honest bottom line

Reference book: **911 LONG options, 1 SHORT, 4 futures, 19 equity, no MTF**
(`docs/patterns/11-direction_instability/STATUS.md:49`).

**5 positions out of 935 (0.5%)** are ones where capital committed ≠ entry value.
For 99.5% of this trader's history, your statement is exactly true: **premium is
the capital, and margin is display-and-analytics only.**

It stops being true the moment a user writes options or trades futures — and F3
exists because when that happened, the detector went *silent* rather than wrong,
which is the worse failure.

---

## 3. "Should we build the margin calculator ourselves?"

### What the exchanges and Zerodha actually publish

**Initial margin = SPAN + Exposure** ([Zerodha support](https://support.zerodha.com/category/trading-and-markets/general-kite/funds/articles/what-is-span-and-exposure-margin)).

**SPAN** — *"Standard Portfolio Analysis of Risk… used by exchanges to calculate
risk and margins for F&O portfolios"*, using price and volatility of the
underlying *"to determine the maximum possible loss for a portfolio"*. It is
scenario-based and portfolio-level. The exchange publishes **SPAN parameter files
several times a day**; per Zerodha's own Varsity discussion these are member
files and **NSE does not make them public**. Zerodha's calculator consumes them.

**⇒ SPAN cannot be reproduced from a formula. Anyone claiming a "SPAN
calculator" without the files is running an approximation.**

**Exposure** — this part *is* a published formula:

| segment | exposure margin | basis |
|---|---|---|
| index futures + **index option selling** | **2%** | contract value = **spot × lot size** |
| stock futures + **stock option selling** | **3.5%**, or 1.5 σ of 6-month log returns, whichever higher | contract value = **spot × lot size** |

*(Source: Zerodha support, above. Note: generic NSE-guidance secondary sources
give **3%** for index and **5% or 1.5σ** for stock. Two published numbers
disagree. Zerodha's is authoritative for us because Zerodha is the broker whose
margin our users actually pay.)*

Plus **additional ELM near index expiry** — Zerodha has a dedicated article on it.
A third layer, on top of both.

### What Kite's API gives us — and the decisive limitation

| endpoint | scope |
|---|---|
| `POST /margins/orders` | **prospective only.** Returns exact `span`, `exposure`, `option_premium`, `total` per order, accounting for existing positions |
| `POST /margins/basket` | **prospective only.** Adds spread benefit — `initial` vs `final` |
| `POST /charges/orders` | historical, but returns **charges, not margin** |
| `GET /user/margins` | account-level aggregate |

**There is no API for the margin of a past position.** ([Kite Connect margins docs](https://kite.trade/docs/connect/v3/margins/))

### What we do today — verified

- `margin_service.py:127-136` reads only the **account-level** `utilised`
  aggregate (`span + exposure + option_premium`). One number for the whole
  account, not per position.
- **`order_margins` / `basket_margins` are called nowhere in the codebase.** grep
  returns zero hits.
- Per-position figures come entirely from `_futures_span_margin` — flat
  percentages of notional: **12%** broad index, **15%** BANKNIFTY/BANKEX, **20%**
  stock. These were unsourced.

### How good is our estimator, actually — measured against the published reality

NIFTY 25000 strike, qty 75 → contract value ₹18,75,000.

| quantity | value |
|---|---|
| exposure @ 2% (published) | ₹37,500 |
| real total naked-short margin, NIFTY, 2026 | **≈ ₹1.5–2.0 L** per lot |
| implied real total as % of contract value | **≈ 8 – 10.7%** |
| **our estimator @ 12%** | **₹2,25,000** |

**Our figure overstates by roughly 12–50%. It is in the right band and errs in
the safe direction for a risk denominator.** The 20% stock figure is also
plausible (3.5% exposure + a larger SPAN). Before F3 the same position produced
**₹1,080** — wrong by ~200×. The remaining error is a different order of problem
from the one F3 fixed.

**One sourced deviation to record:** F3 uses **strike × qty** as the option
contract notional; the published basis is **spot × lot size**. At the money they
agree within a few percent; for a deep-OTM short, strike overstates, which is
safe. `parse_symbol` gives us strike; we do not store historical spot. The code
comment already flags this as judgement — it is now a *sourced* deviation rather
than a guess.

---

## 4. Recommendation

### Do NOT build a SPAN replica. Three reasons.

1. **It is not reproducible.** The risk arrays are exchange member files. Any
   "internal SPAN" is an approximation wearing a precise name.
2. **It would need daily volatility and spot inputs we do not store**, and would
   drift every day against the number the trader actually paid — so it would be
   *wrong differently* each session, which is harder to reason about than a
   stable conservative constant.
3. **The upside is bounded and small.** Every Class-3 threshold is a coarse
   percent-of-capital band. Moving the denominator from 12% to 10% of contract
   value changes almost no verdict, and it affects **5 of 935 positions** in the
   book we have.

### Recommended: capture forward, estimate backward. Two pieces, sequenced.

**Piece A — capture the exact number at fill time. Small, exact, permanent.**

Call `POST /margins/orders` on the live order path and store `span`, `exposure`,
`option_premium`, `total` on the trade row. Broker-authoritative, includes ELM
and spread benefit for free, never needs re-deriving. One API call per order sits
comfortably inside the 3 req/s REST budget. **This is the only way we will ever
hold a true margin figure, because no API can give it to us after the fact.**

**Piece B — keep the estimator for history, but label it.**

Historical sessions and every CSV tradebook import can never have Piece A. Keep
`_futures_span_margin` as is, but:

- source the constants in the docstring to the published exposure percentages
  and the observed total band (this note),
- mark the value **`ESTIMATED`** so display and analytics can refuse to print a
  precise rupee figure from it,
- let detector logic read `exact` when present and fall back to `estimated`.

**Sequencing:** A does not depend on B. B is a docstring-and-flag change, not new
maths. **Neither should start before F17** — routing `excess_exposure` and
`constitution_violation` through `risk_basis` — because until then the safety
layer that would carry the `ESTIMATED` flag is bypassed entirely.

### Register entries

| # | item | status |
|---|---|---|
| **D8** *(revised)* | margin vs declared capital | **narrowed**: it is not "which is authoritative" — it is that **no per-position margin exists at all**, exact or estimated, and none can be obtained for the past |
| **D14** *(new)* | drop max-theoretical-loss; two quantities + one flag | §1 |
| **D15** *(new)* | capture margin at fill (Piece A) | §4 |
| **D16** *(new)* | label estimated margin; source the constants (Piece B) | §4 |

**Nothing in this note is implemented. It is design input for the FIX NOW
approval decision, not part of it.**
