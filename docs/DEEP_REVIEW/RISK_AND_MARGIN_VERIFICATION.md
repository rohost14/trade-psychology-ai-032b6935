# Risk and Margin — Verification

**29 Aug 2026. Deliverable 1 of the Risk Infrastructure phase.**

Answers the ten verification questions. Every external fact is checked against a
primary source or by download. Nothing is carried over on the authority of the
earlier report — the previous conclusion was wrong once already.

**Standard used:** VERIFIED = fetched, executed or read directly.
CLAIMED = a source says so and I did not independently confirm it.
UNPROVEN = stated openly as not established.

---

## 1. Can we calculate historical NSE F&O margin ourselves?

**Yes, for NFO index and stock derivatives. VERIFIED by building it and measuring
it against real broker margins.**

Median absolute error **4.0%** across 24 comparable cases; **23 of 24 within
15%**; futures within **0.5%**; a call spread within **0.3%**; and all 11
long-only positions returned **exactly 0**, matching the broker. Full table in
[`MARGIN_VALIDATION_MATRIX.md`](MARGIN_VALIDATION_MATRIX.md).

The earlier claim — "SPAN cannot be reproduced without exchange risk parameter
files" — is **superseded**. NSE Clearing publishes the method, the parameters and
the pricing model. The `.spn` file exists so members "need not execute complex
option pricing calculations", which is a convenience, not a secret.

Not established for **BFO, CDS or MCX** — see §10.

---

## 2. Exactly which inputs are required?

| input | used for |
|---|---|
| underlying reference price (**futures** price of the matching expiry) | all 16 scenarios |
| contract settlement/close price | the unshocked baseline, and net option value |
| strike, option type, expiry date | pricing |
| **signed** quantity | direction; loss sign |
| lot size **in force on the trade date** | contract value, exposure |
| annualised volatility of the underlying | the scan ranges |
| implied volatility of the leg | repricing under shock (see §5) |
| risk-free rate | discounting; low sensitivity |
| segment: index vs stock | selects PSR floor, VSR minimum, exposure rate |

---

## 3. Which inputs are publicly available historically?

**All of them, free, no login. VERIFIED by download.**

```
bhavcopy  https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_<YYYYMMDD>_F_0000.csv.zip
FOVOLT    https://nsearchives.nseindia.com/archives/nsccl/volt/FOVOLT_<DDMMYYYY>.csv
```

Fetched HTTP 200 for 2026-08-28, 08-27, 08-26 and **2024-03-15**. A holiday
returns 404, which is the correct behaviour, not an outage.

The bhavcopy supplies, per contract per date:

| column | gives us |
|---|---|
| `UndrlygPric` | spot |
| `SttlmPric` / `ClsPric` | contract price |
| `StrkPric`, `OptnTp`, `XpryDt` | contract identity |
| **`NewBrdLotQty`** | **the lot size in force on that date** |
| **`FinInstrmTp`** | **IDF / IDO / STF / STO — instrument class without parsing the symbol** |

`FinInstrmTp` matters more than it looks. It removes the entire class of defect
that F15 in the semantics audit describes: for any historical NSE contract we
never need to infer type, underlying or strike from the tradingsymbol, because
the exchange states them.

FOVOLT supplies `Applicable Annualised Volatility (N) = Max(F or L)` — NSE's own
figure — and prints its EWMA recursion in the header,
`E = sqrt(0.995*D^2 + 0.005*C^2)`, so it is reproducible if a day is missing.

---

## 4. Which components can be calculated exactly?

VERIFIED against the broker:

| component | evidence |
|---|---|
| **Price Scan Range** | futures margin is essentially PSR alone; computed 147,147 vs broker 147,445 = **−0.2%** |
| **the 16 scenarios** | published verbatim by NSE and implemented as written |
| **net option value** | published as long minus short at closing price |
| **exposure margin** | strike- and expiry-invariant in the broker's own output across 8 probes, consistent with a flat % of contract value |
| **spread benefit** | falls out of scanning legs jointly; bull call spread **−0.3%** |
| **long options carry no margin** | 11/11 cases exactly 0 |

The published parameters:

- **PSR** = 6σ × √2, floored at **9.3%** index / **14.2%** stock / **17.7%**
  index options over 9 months residual. "Subject to" means a minimum — NSE's own
  stock wording is "subject to at least 14.2%". On 2026-08-28 the floor **binds**
  for NIFTY (6σ√2 = 7.19%), BANKNIFTY (8.89%) and RELIANCE (11.29%), so the
  common case is a published constant, not a computed one.
- **VSR** = 25% of annualised EWMA vol, minimum 4% index / 10% stock.
- **Calendar spread charge** = 1.75% index / 2.2% stock of the far month.
- **Exposure** = 2% index / 3.5% stock of contract value (Zerodha).

---

## 5. Which components cannot be reconstructed exactly?

Stated plainly, because several cannot.

**a) A residual ~+5 to +7% overstatement on short options. UNPROVEN cause.**
Diagnosed as far as: the price scan is right (futures match to 0.2%), so the gap
is in repricing the option under the volatility shock. NSE computes its risk
arrays on its own volatility surface; we use each leg's implied volatility backed
out of its settlement price. Which specific difference produces the 6% is **not
established**. The bias is conservative and systematic, not random.

**b) Short option minimum charge.** A real SPAN component. Parameter not
retrieved. Not implemented, so deep-OTM shorts are the likeliest under-statements.

**c) Additional ELM near index expiry.** Zerodha documents it as a separate
layer. Not modelled.

**d) Physical delivery margin on stock F&O in expiry week.** Escalates sharply
for ITM stock contracts. Not modelled.

**e) Inter-commodity spread credit.** Needs the exchange tier and credit-rate
tables. Not attempted; the model is single-underlying by contract.

**f) Calendar spread charge.** Published, but needs composite delta per month.
Not implemented — the model raises `calendar_spread_unmodelled` instead of
silently understating.

**g) The exposure reference price.** The broker's exposure implies an underlying
of 23,997.35 for options and 24,391.2 for futures on the same date, while
bhavcopy gives spot 24,175.65 and the September future 24,341.90. Neither
matches. The oracle prices from a live snapshot, so a sub-1% difference is
expected; the *inconsistency between the two* is **UNPROVEN**. Exposure is ~18%
of the total, so a 0.7% error there is ~0.13% of the answer. Not pursued.

**h) A conflict in the published exposure rate.** Zerodha says **2%** index /
**3.5%** stock; generic NSE-guidance secondary sources say **3%** / **5% or
1.5σ**. We use Zerodha's, because Zerodha is the broker our users are charged by
— **not** because it validates better. This is recorded rather than resolved.

---

## 6. Can we reproduce Kite's `/margins/orders` result?

**Not directly tested — no live access token. Stated as a limitation.**

Validated instead against **Zerodha's public SPAN calculator**
(`POST https://zerodha.com/margin-calculator/SPAN`, no authentication), which
returns `span`, `exposure`, `netoptionvalue`, `spread` and `total` for an
arbitrary position. It is the broker's own number for the same question, so it is
a true oracle rather than a second estimate — but it is **not literally the
`/margins/orders` response**, and confirming the two agree remains open.

Two structural facts established from the oracle's own output:

- `total = span + exposure` exactly. `netoptionvalue` is reported separately but
  is already inside `span`.
- Exposure is invariant to strike and to expiry, and a call spread pays the same
  exposure as its short leg alone — so exposure attaches to short option legs and
  to futures, and long option legs carry none.

**A known defect of the oracle:** it intermittently returns an all-zero block for
a valid multi-leg position. Zerodha's own front-end JavaScript treats a response
without a `total` as an invalid entry and warns that leaving it in place makes
the upstream API "reject all subsequent calls". One case in the matrix (the ratio
spread) is affected and is **excluded**, not scored — a manual re-query returned
span 82,886 / total 145,279 where the harness recorded 0 / 31,197.

---

## 7. How does portfolio margin differ from single-leg margin?

**Enormously, and it is measured, not asserted.**

| position | broker total |
|---|---|
| sell 24200 CE alone | ₹175,747 |
| sell 24200 CE **+ buy 24700 CE** | **₹64,174** |

Adding a second position **reduced** the requirement by **63%**. Any model that
computes legs independently and adds them is not wrong by a few percent on
hedged books; it is wrong by a factor of three, in the unsafe direction for
"how much capital is committed" and the safe direction for "is this position too
big" — a contradiction that cannot be papered over.

---

## 8. What is the correct treatment of spreads and hedges?

**Scan the legs together. Do not classify them.**

The spread benefit is not a rule we write and not a hedge ratio we invent. Under
each of the 16 scenarios the long leg's gain and the short leg's loss land in the
same sum, so the worst case over the sixteen is smaller than the sum of the
individual worst cases. The exchange gets its answer the same way.

Measured consequence: the model reproduces the bull call spread to **−0.3%**
without containing the word "spread" anywhere in its logic.

**This is the strongest argument for the whole layer.** The semantics audit found
`strategy_detector` guessing structures from entry-time proximity, mislabelling a
FUT+short-PE as a hedge (F5) and granting suppression to `MULTI_LEG_UNKNOWN`
(F6). A margin model does not need any of that: **the capital consequence of a
hedge is computable without knowing what the structure is called.**

Naming structures is still needed for *messaging*. It is no longer needed for
*risk*.

---

## 9. Expiry, ELM, calendar spreads

- **Expiry day is not Thursday.** NIFTY's monthly expiries in the bhavcopy are
  2026-09-29, 2026-10-27, 2026-11-23 — **Tuesdays**. Code and docs that hardcode
  "last Thursday" are wrong for the current contract. VERIFIED. This is the same
  defect class as F11; the fix is to read `XpryDt`, never to compute it.
- **Weeklies exist for index only.** NIFTY had five expiries inside September;
  RELIANCE had one per month. An "expiry day" rule that ignores this treats every
  Tuesday as a stock-option expiry.
- **ELM near index expiry** — documented by Zerodha as an extra layer, **not
  modelled**.
- **Calendar spread charge** — published rates, **not implemented**; flagged per
  calculation instead.
- **Physical delivery margin** in stock F&O expiry week — **not modelled**.

---

## 10. What is still unknown or broker-specific?

| item | status |
|---|---|
| the +5-7% short-option residual | **UNPROVEN** |
| short option minimum charge | parameter not retrieved |
| ELM, delivery margin, calendar charge | published, not implemented |
| exposure rate 2%/3.5% vs 3%/5% | **conflicting published sources**, unresolved |
| exposure reference price | broker's implied reference matches neither spot nor futures |
| Kite `/margins/orders` agreement | untested, no token |
| **BFO** (SENSEX/BANKEX) | **not attempted.** BSE sets its own parameters; the F11 finding — that BSE monthly expiry has no sourced rule — still stands |
| **CDS** | not attempted |
| **MCX** | not attempted. SPAN applies, but see [`INSTRUMENT_MASTER_SPEC.md`](INSTRUMENT_MASTER_SPEC.md) — we cannot yet state MCX quantity semantics from a primary source |
| broker-specific margin | Zerodha may collect **above** exchange minimum. Our figure is an *exchange* margin; the broker's own policy overlay is not modelled |
| peak margin / intraday reporting | not modelled |
| MTF | see §10 of [`RISK_LAYER_ARCHITECTURE.md`](RISK_LAYER_ARCHITECTURE.md) |

---

## Superseded conclusions

| earlier claim | status |
|---|---|
| "SPAN cannot be reproduced without exchange files" | **WRONG.** Superseded by a working calculator validated against broker margins |
| "any internal calculator is an approximation wearing a precise name" | **WRONG** for futures (0.2%) and spreads (0.3%); **partly right** for short options, which carry a systematic +6% |
| "our 12% constant is accurate to ±12-50%" | **WRONG.** Measured across the strike ladder it runs **−35% to +158%** |
| "the probe reproduced a real margin to +0.77%" | **WITHDRAWN.** That comparison used a 4-day weekly against the oracle's 32-day monthly. Two different contracts; the agreement was coincidence |
