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

## 3. "Should we build the margin calculator ourselves?" — YES, and it is exact

### Correction to my earlier answer

**I said SPAN was "not reproducible without exchange files" and that any internal
version would be "an approximation wearing a precise name." That was wrong.**

NSE Clearing publishes the complete methodology, every parameter, and the pricing
model. The `.spn` risk parameter file is a **convenience for members**, in NSE's
own words: *"members need not execute complex option pricing calculations which
are performed by NSE Clearing."* It is not a secret input. Everything it contains
can be recomputed from public data.

I did not research it properly the first time. Below is the research, and a
working numeric proof.

### First — does the postback give us margin? No. Verified.

The Kite postback payload, in full, is:

```
user_id, unfilled_quantity, app_id, checksum, placed_by, order_id,
exchange_order_id, parent_order_id, status, status_message,
status_message_raw, order_timestamp, exchange_update_timestamp,
exchange_timestamp, variety, exchange, tradingsymbol, instrument_token,
order_type, transaction_type, validity, product, quantity,
disclosed_quantity, price, trigger_price, average_price, filled_quantity,
pending_quantity, cancelled_quantity, market_protection, meta, tag, guid
```

**No `span`, no `exposure`, no `margin`, no `option_premium`.** Nothing
margin-related at all. `grep` on our own `app/api/webhooks.py` returns zero hits
for those names, correctly — there is nothing to read.

So the real choice is: call `/margins/orders` per order, or compute it. And
`/margins/orders` cannot answer for a past trade, so for history we must compute.

### The published SPAN formula, in full

Source: [NSCCL SPAN](https://www.nseclearing.in/risk-management/equity-derivatives/nsccl-span)
and [SPAN Risk Parameters](https://www.nseclearing.in/risk-management/equity-derivatives/span-risk-parameters).

**Price Scan Range (PSR)** — 6 standard deviations scaled by root-2, *subject to
a floor*:

| segment | floor |
|---|---|
| index derivatives | **9.3%** of underlying price |
| index options, residual maturity > 9 months | **17.7%** |
| stock derivatives | **14.2%** |

**Volatility Scan Range (VSR)** — 25% of annualised EWMA volatility, minimum
**4%** (index) / **10%** (stock).

**The 16 scenarios**, verbatim from NSE: underlying unchanged, plus/minus 1/3,
2/3 and 3/3 of PSR — each with volatility up and volatility down (14 scenarios) —
plus two extreme moves at **double** the PSR, of which only **35% of the loss**
is charged. Losses positive, gains negative.

**Scanning Risk Charge** = the largest loss across those 16.

**Calendar / inter-month spread charge** — **1.75%** of the far month (index),
**2.2%** (stock), on portfolio delta per month.

**Net Option Value** = long option positions minus short option positions at
closing price. **Total SPAN = SPAN Risk Requirement minus Net Option Value.**

**Option pricing model = Black-Scholes**, rate = MIBOR. NSE states this outright.

**Exposure margin** (charged on top) — **2%** index / **3.5%** stock of
spot times lot size.

### Every input is public, free, and archived — verified by download

| input | source | verified |
|---|---|---|
| underlying spot, per contract per date | F&O bhavcopy, column `UndrlygPric` | HTTP 200 |
| option settlement / close price | same, `SttlmPric` / `ClsPric` | yes |
| strike, expiry, option type | same, `StrkPric` / `XpryDt` / `OptnTp` | yes |
| **lot size as of that date** | same, `NewBrdLotQty` | yes (NIFTY = 65) |
| **applicable annualised volatility** | `FOVOLT_DDMMYYYY.csv`, NSE's own EWMA | HTTP 200 |
| PSR / VSR / spread-charge parameters | NSE Clearing pages above | yes |

```
https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_<YYYYMMDD>_F_0000.csv.zip
https://nsearchives.nseindia.com/archives/nsccl/volt/FOVOLT_<DDMMYYYY>.csv
```

No login. Fetched successfully for 2026-08-28, 08-27, 08-26 **and 2024-03-15** —
the archive goes back years, which covers the entire 189-session reference book.

The volatility file even carries NSE's EWMA formula in its own header —
`E = sqrt(0.995*D^2 + 0.005*C^2)` — so the recursion is reproducible from scratch
if a day is ever missing.

### Numeric proof — a probe script reproduced a real margin

Feasibility script (job tmp directory, **not** production), single-leg, calls
only, built from nothing but the files above:

```
NIFTY 2026-09-01 24200CE  spot=24175.65  lot=65  settle=104.75  annvol=0.1620  T=4d
  6-sigma*root2 = 7.1945%  ->  PSR = 9.3000%  (floor BINDS)    VSR = 4.0497%
  contract value      =    1,571,417
  scanning risk       =      138,871
  net option value    =       -6,809
  SPAN                =      145,680
  exposure @ 2%       =       31,428
  TOTAL, 1 lot short  =      177,108     = 11.27% of contract value
```

**Rs 1,77,108.** Independently reported real NIFTY naked-short margin for 2026 is
**Rs 1.5–2.0 lakh per lot**. The exposure component, Rs 31,428, matches the
independently reported *"additional Rs 30,550 per lot"* almost exactly.

**The calculator works.** This is not an estimate with an error band — it is the
exchange's own arithmetic on the exchange's own published inputs.

### And the flat constant is worse than section 2 suggested

Same script, real SPAN versus our `12% x strike x qty`, across the live chain:

| strike | moneyness | real SPAN + exposure | our estimator | error |
|---|---|---|---|---|
| 22750 | 94.1% | Rs 2,71,290 | Rs 1,77,450 | **-35%** |
| 23500 | 97.2% | Rs 2,22,575 | Rs 1,83,300 | -18% |
| **24200** | **100.1%** | **Rs 1,77,108** | **Rs 1,88,760** | **+7%** |
| 25000 | 103.4% | Rs 1,25,189 | Rs 1,95,000 | +56% |
| 26000 | 107.6% | Rs 92,664 | Rs 2,02,800 | **+119%** |
| 26550 | 109.8% | Rs 80,160 | Rs 2,07,090 | **+158%** |

**The constant is only accurate at the money.** It scales *with* strike; real
margin scales *inversely* with strike for a call. My earlier claim that the
estimator was within "plus or minus 12–50%, overstating" was measured at a single
ATM point and does not generalise: the real range is **-35% to +158%**, and it
under-states exactly where risk is largest — deep in the money.

It is also structurally blind to the two things that matter most —
**time to expiry** (a 4-day short and a 40-day short get the same number) and
**spread benefit** (a defined-risk spread is charged as two naked legs).

### Still to be sourced before building

Not guesses — open items with known answers we have not yet pulled:

- **short option minimum charge** — a SPAN component; parameter not yet retrieved
- **additional ELM near index expiry** — Zerodha documents it as a separate layer
- whether Zerodha's "exposure" and SEBI's "ELM" are the same charge under two names
- MIBOR reference rate source (low sensitivity — a 1% rate error moves a 4-day
  option by pennies)
- put pricing and short-futures scenarios (trivial; the probe did calls only)
- composite delta, for calendar-spread and spread-benefit treatment

---

## 4. Recommendation — build it, and validate it against a free oracle

**Revised from the earlier "do not build."** Build it. It is exact, the inputs
are free and archived, and there is no other way to price a historical position.

**Piece A — a `margin_calculator` service.** Black-Scholes, the 16 scenarios,
net option value, exposure. A pure function of (spot, strike, expiry, type,
direction, qty, lot, vol, rate). Roughly one module.

**Piece B — two public-data ingesters.** Daily bhavcopy and FOVOLT, with a
backfill across the reference book. Gives spot, settlement, lot size and NSE's
own volatility for every past date.

**Piece C — validation, and this is what makes it honest.**
`POST /margins/orders` returns the broker's exact `span` / `exposure` / `total`
for a prospective order. That is a **free exact oracle**. Run our calculator
against it across the live chain and report the error distribution. We can
*measure* accuracy rather than assert it — the same standard this codebase
applies to every detector.

**Piece D — store, never re-derive.** Once computed or fetched, persist
`span` / `exposure` / `total` on the trade row with `margin_source` of `BROKER`
or `COMPUTED`. Volatility moves; a past trade must never be recomputed.

**Sequencing.** C validates A, so A and B first, then C, and only then does
anything consume the number. **None of it before F17** — until `excess_exposure`
and `constitution_violation` route through `risk_basis`, an accurate margin would
be computed and then bypassed.

**Scope honesty:** on the current reference book this affects **5 positions out
of 935**. It is correctness infrastructure for the users we do not have yet, not
a fix for the book we have. That is a good reason to build it *well*, and a good
reason not to build it *first*.

### Register entries — revised

| # | item | status |
|---|---|---|
| **D8** *(revised)* | margin vs declared capital | **narrowed**: no per-position margin exists at all, and none can be obtained for a past trade from any API |
| **D14** | drop max-theoretical-loss; two quantities and one flag | section 1 — unchanged |
| **D15** *(revised)* | capture broker margin at fill via `/margins/orders` | still worth doing; now the **validation oracle** as well as a data source |
| **D16** *(superseded)* | label the estimate | replaced by D17 — we do not need an estimate |
| **D17** *(new)* | build the exact SPAN calculator, bhavcopy/FOVOLT ingest, oracle validation | section 4 |

**Nothing here is implemented. The probe script lives in the job tmp directory
and is deliberately not in the repo.**
