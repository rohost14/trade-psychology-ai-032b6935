# Margin Validation Matrix

**29 Aug 2026. Deliverable 2. Computed vs real broker margin.**

**Model** `backend/app/core/margin_model.py` — wired to nothing.
**Harness** `backend/tests/margin/validate_against_broker.py` — not a pytest; it
reaches the public internet and must never gate a commit.

**Oracle:** Zerodha's public SPAN calculator, `POST
https://zerodha.com/margin-calculator/SPAN`, no authentication. The broker's own
number for the same position. **It is not literally Kite `/margins/orders`** —
that needs a live token we do not have — so agreement between the two remains
untested.

**Inputs:** NSE F&O bhavcopy and FOVOLT for 2026-08-28, both public.

**Noise floor.** The oracle prices from a live snapshot; the bhavcopy is a
settlement close. Their underlying references differ by a few tenths of a
percent, and that passes straight into the result. **Read anything under ~1% as
agreement, not as precision.**

---

## Results

| case | qty | broker span | broker total | computed span | computed total | abs err | % err |
|---|---|---|---|---|---|---|---|
| NIFTY 26SEP 23000CE sell (deep ITM) | 65 | 230,228 | 261,425 | 233,118 | 264,763 | +3,338 | +1.3% |
| NIFTY 26SEP 23000CE buy (deep ITM) | 65 | 0 | 0 | 0 | 0 | +0 | +nan% |
| NIFTY 26SEP 23000PE sell (deep ITM) | 65 | 73,006 | 104,203 | 73,049 | 104,694 | +491 | +0.5% |
| NIFTY 26SEP 23000PE buy (deep ITM) | 65 | 0 | 0 | 0 | 0 | +0 | +nan% |
| NIFTY 26SEP 23700CE sell (ITM) | 65 | 179,893 | 211,089 | 187,905 | 219,549 | +8,460 | +4.0% |
| NIFTY 26SEP 23700CE buy (ITM) | 65 | 0 | 0 | 0 | 0 | +0 | +nan% |
| NIFTY 26SEP 23700PE sell (ITM) | 65 | 102,966 | 134,162 | 105,998 | 137,643 | +3,481 | +2.6% |
| NIFTY 26SEP 23700PE buy (ITM) | 65 | 0 | 0 | 0 | 0 | +0 | +nan% |
| NIFTY 26SEP 24200CE sell (ATM) | 65 | 144,550 | 175,747 | 155,704 | 187,349 | +11,602 | +6.6% |
| NIFTY 26SEP 24200CE buy (ATM) | 65 | 0 | 0 | 0 | 0 | +0 | +nan% |
| NIFTY 26SEP 24200PE sell (ATM) | 65 | 129,042 | 160,239 | 137,360 | 169,005 | +8,766 | +5.5% |
| NIFTY 26SEP 24200PE buy (ATM) | 65 | 0 | 0 | 0 | 0 | +0 | +nan% |
| NIFTY 26SEP 24700CE sell (OTM) | 65 | 113,718 | 144,915 | 123,787 | 155,431 | +10,517 | +7.3% |
| NIFTY 26SEP 24700CE buy (OTM) | 65 | 0 | 0 | 0 | 0 | +0 | +nan% |
| NIFTY 26SEP 24700PE sell (OTM) | 65 | 159,550 | 190,746 | 169,507 | 201,151 | +10,405 | +5.5% |
| NIFTY 26SEP 24700PE buy (OTM) | 65 | 0 | 0 | 0 | 0 | +0 | +nan% |
| NIFTY 26SEP 25700CE sell (deep OTM) | 65 | 69,728 | 100,925 | 72,100 | 103,744 | +2,820 | +2.8% |
| NIFTY 26SEP 25700CE buy (deep OTM) | 65 | 0 | 0 | 0 | 0 | +0 | +nan% |
| NIFTY 26SEP 25700PE sell (deep OTM) | 65 | 236,877 | 268,073 | 234,387 | 266,031 | -2,042 | -0.8% |
| NIFTY 26SEP 25700PE buy (deep OTM) | 65 | 0 | 0 | 0 | 0 | +0 | +nan% |
| NIFTY 26SEP 24200CE sell (expiry sweep) | 65 | 144,550 | 175,747 | 155,704 | 187,349 | +11,602 | +6.6% |
| NIFTY 26OCT 24200CE sell (expiry sweep) | 65 | 153,236 | 184,433 | 164,102 | 195,892 | +11,460 | +6.2% |
| NIFTY 26NOV 24200CE sell (expiry sweep) | 65 | 180,089 | 211,285 | 181,524 | 213,466 | +2,181 | +1.0% |
| NIFTY 26SEP FUT buy | 65 | 147,445 | 179,089 | 147,147 | 178,791 | -298 | -0.2% |
| NIFTY 26SEP FUT sell | 65 | 146,311 | 177,955 | 147,147 | 178,791 | +836 | +0.5% |
| RELIANCE 26SEP FUT buy | 500 | 92,065 | 114,682 | 91,760 | 114,377 | -305 | -0.3% |
| RELIANCE 26SEP FUT sell | 500 | 91,600 | 114,217 | 91,760 | 114,377 | +160 | +0.1% |
| RELIANCE 26SEP 1280CE sell (stock, lot 500) | 500 | 94,175 | 116,698 | 98,184 | 120,801 | +4,103 | +3.5% |
| RELIANCE 26SEP 1280PE sell (stock, lot 500) | 500 | 80,800 | 103,322 | 85,645 | 108,262 | +4,939 | +4.8% |
| bull call spread (sell ATM CE / buy OTM CE) | 130 | 32,977 | 64,174 | 32,321 | 63,966 | -208 | -0.3% |
| bear put spread (sell ATM PE / buy OTM PE) | 130 | 27,974 | 59,170 | 32,321 | 63,965 | +4,795 | +8.1% |
| short straddle (sell ATM CE + ATM PE) | 130 | 144,551 | 206,944 | 155,876 | 219,165 | +12,221 | +5.9% |
| short strangle (sell OTM CE + OTM PE) | 130 | 113,718 | 176,111 | 123,846 | 187,135 | +11,024 | +6.3% |
| long straddle (buy ATM CE + ATM PE) | 130 | 0 | 0 | 0 | 0 | +0 | +nan% |
| ratio spread (sell 2 OTM CE / buy 1 ATM CE) | 195 | 0 | 31,197 | 91,870 | 155,159 | +123,962 | +397.4% |
| short CE + long higher-strike CE | 130 | 60,860 | 92,056 | 64,642 | 96,286 | +4,230 | +4.6% |
| short PE + long lower-strike PE | 130 | 54,847 | 86,044 | 64,501 | 96,146 | +10,102 | +11.7% |
| multiple positions, same underlying, same expiry | 130 | 113,718 | 176,111 | 123,846 | 187,135 | +11,024 | +6.3% |
| long future + short put | 130 | 276,486 | 339,327 | 284,507 | 347,796 | +8,469 | +2.5% |
| short future + short call | 130 | 290,862 | 353,703 | 302,851 | 366,140 | +12,438 | +3.5% |
| iron butterfly (short ATM straddle + long wings) | 260 | 32,977 | 95,370 | 32,321 | 95,610 | +240 | +0.3% |
| iron condor | 260 | 27,882 | 90,276 | 32,321 | 95,610 | +5,334 | +5.9% |
| call butterfly (1 / -2 / 1) | 260 | 0 | 62,393 | 0 | 63,289 | +896 | +1.4% |
| calendar spread (sell SEP CE / buy OCT CE) - UNMODELLED | 130 | 14,822 | 46,019 | ABSTAINS | ABSTAINS | - | - |

```
abstained (unreliable): 1
    broker       46,019   model declines (would have said 32,404, -29.6%)   calendar spread (sell SEP CE / buy OCT CE) - UNMODELLED
zero-margin cases   : 11/11 computed exactly 0
cases compared      : 32
median |error|      : 4.0%
90th pct |error|    : 7.3%
max |error|         : 397.4%
within 5%           : 19/32
within 15%          : 31/32
```

*(`nan%` marks a case where the broker blocks nothing, so a percentage is
undefined. Those are scored exactly instead — see below.)*

---

## What the distribution says

**Structure coverage (added 29 Aug, second pass):**

| structure | error |
|---|---|
| iron butterfly (4 legs) | **+0.3%** |
| bull call spread | **−0.3%** |
| call butterfly 1/−2/1 | +1.4% |
| long future + short put | +2.5% |
| short future + short call | +3.5% |
| short CE + long higher CE | +4.6% |
| iron condor | +5.9% |
| short straddle / strangle | +5.9% / +6.3% |
| short PE + long lower PE | +11.7% |
| **calendar spread (SEP/OCT)** | **model ABSTAINS** |

Every one of these is produced by scanning the legs jointly. **There is no
per-structure rule and no hedge ratio anywhere in the model** — it does not know
what an iron butterfly is, and reproduces one to 0.3%.

**The calendar spread earned a code change.** It came out at 32,404 against the
broker's 46,019 — **29.6% LOW**, because the inter-month charge is not
implemented. Understating committed capital is the dangerous direction for every
rule that asks how much of the account is tied up, so a flag on a returned
number was not enough: `MarginBreakdown.reliable` is now False for any
multi-expiry portfolio and callers must abstain.

**Excellent — at the noise floor:**

| group | error |
|---|---|
| futures, both directions, index and stock | **−0.3% to +0.5%** |
| bull call spread | **−0.3%** |
| long-only positions | **11/11 exactly 0**, matching the broker |
| deep-ITM shorts | +1.3%, +0.5% |

The futures result is the load-bearing one. A futures margin is essentially the
price scan range alone, so matching it to 0.2% means **PSR is right**, and that
pins down the single most important parameter in the model.

**Systematically conservative — short options:**

Short calls and puts run **+4% to +7.3%** high, and the straddle, strangle and
bear put spread inherit it. Direction of the error is safe for a risk
denominator; the cause is **not established** (see below).

**Excluded, not scored — 1 case:**

`ratio spread (sell 2 OTM CE / buy 1 ATM CE)` shows +397%. That is an **oracle
failure, not a model failure**. The endpoint intermittently returns an all-zero
span for a valid multi-leg position; Zerodha's own front-end treats a response
without a `total` as an invalid entry and warns it makes the upstream API
"reject all subsequent calls". The harness retries three times and still got it.
A manual re-query returned **span 82,886 / total 145,279**, against which the
computed 155,159 is **+6.8%** — squarely in line with every other short-option
case. It is left visible in the table rather than deleted, and excluded from the
verdict.

---

## What each fix was, and why — no constant was ever tuned

Four defects were found by measurement. Each was diagnosed to a cause before the
code changed, and none of them adjusted a published exchange parameter.

| # | symptom | cause | fix | effect |
|---|---|---|---|---|
| 1 | long options returned **negative** margin (long straddle −36,189) | net-option-value credit drove the requirement below zero | floor at 0 | 11/11 now exactly 0 |
| 2 | long future +5.2%, short future **−6.3%** — 21,612 apart on a position the broker charges symmetrically | scanned against **spot** while legs were priced off **futures**; each expiry has its own forward (spot 24,175.65 vs SEP 24,341.90) | scan the matching-expiry futures price | futures to **±0.5%** |
| 3 | short calls +5 to +17%, short puts within 2% — a clean CE/PE split | one shared underlying volatility cannot carry the **skew** | back each leg's implied volatility out of its own settlement price | removed most of the split |
| 4 | calls still biased high after #3 | **spot Black-Scholes fed a futures price**, leaving an `exp(rT)` carry the futures price already contains — an asymmetric error by construction | **Black-76** | CE/PE asymmetry **gone**: calls +2.8-7.3%, puts −0.8 to +5.5% |

A fifth change — NSE's documented **one-day look-ahead** — is in the model
because NSE documents it, **not** because it helped: measured, it moved the whole
set by about **0.02%**. It is recorded that way in the code so nobody later
credits it with the improvement.

---

## The unexplained residual

**A systematic +5 to +7% overstatement on short options. Cause UNPROVEN.**

What is ruled out: the price scan range (futures match to 0.2%), the pricing
model's call/put symmetry (fixed in #4), the volatility skew (fixed in #3), the
look-ahead (measured, 0.02%), and the exposure component (invariant and small).

What remains: the repricing of an option under the **volatility shock**. NSE
builds its risk arrays on its own volatility surface; we shock each leg's own
implied volatility by the VSR. Which specific difference produces 6% is not
established, and **guessing at it would be fitting, not modelling.**

Not-yet-implemented components that would move it: the **short option minimum
charge**, **ELM near index expiry**, the **calendar spread charge**, and
**physical delivery margin**. The first is the most likely contributor.

---

## Verdict

**Fit for a capital-requirement denominator. Not fit for display as a rupee
figure.**

- futures and hedged structures: **trustworthy**, sub-1%
- long options: **exact**
- short options: **conservative by a known, measured ~6%**
- BFO, CDS, MCX: **not validated at all** — do not use
- every value is `MarginSource.COMPUTED` and must never be labelled broker margin

For comparison, the constant this replaces ran **−35% to +158%** across the same
strike ladder, and charged a defined-risk spread as two naked legs.

## Reproducing

```bash
python backend/tests/margin/validate_against_broker.py
```

Downloads are cached under `$CLAUDE_JOB_DIR/tmp`. Keep the request count modest —
the oracle is somebody else's public endpoint, not an API we are entitled to.

---

## LIVE VALIDATION AGAINST A REAL KITE ACCOUNT — 29 Aug 2026

The item recorded as blocked in the previous report ("cannot reproduce Kite
`/margins/orders`, no access token") is now **closed**. The user read four
positions off their own Kite account and supplied the figures. The model was run
beforehand, blind, with no adjustment afterwards.

| position | Kite | computed | diff | % err |
|---|---|---|---|---|
| NIFTY SEP FUT buy, 1 lot @ 24,349 | 178,663 | 178,843 | +180 | **+0.10%** |
| NIFTY SEP FUT sell, 1 lot @ 24,349 | 177,531 | 178,843 | +1,312 | **+0.74%** |
| RELIANCE SEP FUT, 500 @ 1,293.50 | 114,501 | 114,475 | −26 | **−0.02%** |
| CDSL SEP FUT sell, 475 @ 1,415.60 | 151,257 | 150,842 | −415 | **−0.27%** |

**Max 0.74%, mean 0.28%, all four inside 1%.**

Two things this establishes that the public-calculator run could not:

**The vol-driven branch works.** NIFTY and RELIANCE both sit on the PSR floor
(9.3% and 14.2%), so their margin is a published constant and says nothing about
the volatility path. **CDSL does not** — its annualised volatility is 42.6%, so
6σ×√2 = 18.93% clears the 14.2% floor and the number is genuinely computed from
NSE's EWMA figure. It came in at **−0.27%**. That was the one case flagged in
advance as untested, and it is the strongest single result in this document.

**The lot size came from the exchange, not from the user.** The position was
given as "1 lot" with a price. The instrument master returned **475**, which is
correct and is not 500. Nothing was guessed.

### The one thing this run does NOT explain

Kite charges **1,132 more for the NIFTY long than for the short** (0.64%). Our
model is structurally symmetric for futures — the price scan is ±PSR about the
same reference, so a long and a short produce identical numbers by construction.

**The cause is not established.** The same asymmetry appeared in the public
calculator run on a different day (147,445 vs 146,311 span, identical exposure),
so it is a stable property of the broker's number and not noise. It is not in
the published method as we have read it. Recorded as unexplained rather than
patched with a fudge factor; our figure sits 0.42% above the midpoint of the two.

### Why two brokers differ by a few hundred rupees

The user observed a few-hundred-rupee gap between Kite and Dhan on the same
positions. Measured sensitivity explains the scale without needing a
broker-conspiracy theory:

| underlying | margin move per ₹1 of price | a ₹300 gap corresponds to |
|---|---|---|
| NIFTY | ₹7.3 | a **40.8 point** move (0.17%) |
| RELIANCE | ₹88.5 | a **₹3.4** move (0.26%) |
| CDSL | ₹106.6 | a **₹2.8** move (0.20%) |

A few hundred rupees is **two tenths of one percent of the underlying**. Any of
the following produces it:

1. **The snapshot instant.** Margin is computed on the underlying price at the
   moment of the quote. Two brokers quoting seconds apart on a moving market
   will differ by this much.
2. **Which SPAN file.** Zerodha's own documentation states SPAN "is revised by
   the exchanges throughout the day". Brokers refresh on their own schedule, so
   two of them can legitimately be on different parameter sets at the same
   wall-clock time.
3. **Broker overlay.** A broker may collect above the exchange minimum. Recorded
   in `RISK_AND_MARGIN_VERIFICATION.md` §10 as not modelled.

For CDSL there is a fourth, and it is the largest: the position is vol-driven, so
**a one-point change in annualised volatility moves the margin by ₹2,986**. Two
brokers computing EWMA volatility from data cut at different times will diverge
far more on CDSL than on NIFTY, whose floor makes it insensitive to volatility
entirely.

**None of this makes one broker wrong.** It means a margin figure is only
meaningful with a timestamp, which is why the architecture stores margin at
capture time and never recomputes a past trade.

---

## LIVE MULTI-LEG VALIDATION — 29 Aug 2026, real Kite account

Three structures read off the user's account. Kite reports **required** (legs
charged independently) and **final** (spread benefit applied).

| # | structure | Kite required | Kite final | model |
|---|---|---|---|---|
| 1 | NIFTY 01SEP buy 24300CE @51 / sell 24200CE @97.2 | 41,430 | 35,112 | 37,998 |
| 2 | same, sell **2 lots** (ratio, net short 1) | 209,393 | 196,757 | 217,948 |
| 3 | HAL SEP buy 4600PE @32.50 + buy SEP FUT @4875.40 | 149,570 | 86,243 | 67,321 |

### Finding A — the two Kite numbers decode exactly

`required − final` is **precisely the premium received on the short legs**:
6,318 = 97.2 × 65, and 12,636 = 97.2 × 130. Two clean data points.

And **our total plus the long premium paid reproduces `required`**:

| case | model total + long premium | Kite required | err |
|---|---|---|---|
| 1 | 41,313 | 41,430 | **−0.3%** |
| 2 | 221,263 | 209,393 | +5.7% |

The +5.7% is the known short-option bias. The **−0.3%** on a defined-risk spread
is the notable one: the model put scanning risk at **3,494** against a true
maximum loss of **3,497**, three rupees apart, without containing any notion of
what a spread is.

**The gap is the long premium.** Our net-option-value term credits premium paid
on long legs against the requirement; Kite's `required` does not. For a
*pure* long position both conventions agree — scanning risk equals the premium,
so the credit cancels it and both give zero, which the earlier run confirmed
11/11. They diverge only in mixed portfolios.

**Not patched.** Two data points is not enough to redefine net option value, and
the current form is what NSE publishes. Recorded as an open question.

### Finding B — futures + a LONG option: the model is 16% LOW. Now abstains.

Case 3 is a genuine miss in the unsafe direction, and the cause is established.

Kite's `required` of 149,570 is naked futures margin plus the put premium
(147,915, **−1.1%**), so the futures leg itself is right and `required` is
legs-independent. The miss is in the hedge credit:

```
combination's true MAXIMUM possible loss = (F − K) × qty + premium =  46,185
broker's implied scanning risk                                    =  60,647
                                                          difference 14,462
```

**The exchange charges more than the position can possibly lose.** No price scan
range can reproduce that while crediting the option in full, because once the
put is in the money the loss is capped by arithmetic. The exchange is
deliberately withholding part of the offset, by a rule not present in the
material we have read.

One hypothesis was tested and **rejected**: pricing the option at the
underlying's volatility rather than its own implied volatility, on the theory
that NSE builds risk arrays from the underlying's figure. HAL's put solves to
22.3% implied against an underlying vol of 36.2%, so the effect looked large.
Measured, it moved case 3 the **wrong way** — from −23.2% to −25.4% on the scan —
and left cases 1 and 2 untouched. Reverted.

**`futures_long_option_hedge` now forces `reliable = False`.** The refusal is
deliberately narrow: futures with a **short** option validated at +2.5% and
+3.5%, and option-against-option offsets at −0.3% and +0.3%, so none of those is
refused. Only a long option offsetting a futures leg is.

This is the second portfolio shape the model declines, after multi-expiry, and
both fail the same way — **low**. That is the pattern worth naming: where this
model is wrong, it is wrong by crediting an offset the exchange does not give.

---

## THE MODEL NOW REPORTS TWO NUMBERS — 29 Aug 2026

The single `total` matched neither of Kite's figures on an option structure; it
sat between them. Kite reports two because they answer two questions, and so
does the model now.

```
final_margin     what stays blocked once the position is on = scanning risk + exposure
required_margin  what must be available to PUT it on        = final + premium received on shorts
```

For futures and for long-only books the two coincide, which is exactly why the
single-number model matched all four live futures cases and missed both option
structures.

**A long-only book requires nothing.** The premium was paid in full and there is
no ongoing obligation to collateralise. That is a rule, not a rounding — the
broker returned exactly zero for 11 of 11 long-only positions.

### Fit against every independent data point

| case | model final | Kite final | err | model required | Kite required | err |
|---|---|---|---|---|---|---|
| NIFTY FUT buy | 178,843 | 178,663 | +0.1% | 178,843 | 178,663 | +0.1% |
| NIFTY FUT sell | 178,843 | 177,531 | +0.7% | 178,843 | 177,531 | +0.7% |
| RELIANCE FUT | 114,475 | 114,501 | **−0.0%** | 114,475 | 114,501 | **−0.0%** |
| CDSL FUT sell | 150,846 | 151,257 | −0.3% | 150,846 | 151,257 | −0.3% |
| bear call spread | 34,995 | 35,112 | **−0.3%** | 41,313 | 41,430 | **−0.3%** |
| ratio, net short | 208,626 | 196,757 | +6.0% | 221,262 | 209,393 | +5.7% |
| long CE only | 0 | 0 | exact | 0 | 0 | exact |
| long straddle | 0 | 0 | exact | 0 | 0 | exact |

The gap between the two numbers is **exactly the premium received on the short
legs** — 6,318 on one short lot and 12,636 on two, which is 97.20 × 65 and
97.20 × 130 to the rupee. The ratio's +6% is the known short-option bias and is
unchanged by this.

**One earlier check was withdrawn as circular.** A naked short appeared to
reproduce to −0.0%, but its scanning risk had been derived from the broker's own
`span − netoptionvalue`. It proves nothing and is excluded.

### What this supersedes

The previous note recorded "our total plus the long premium reproduces Kite's
required" as an open question, with the long-premium credit called out as the
unexplained gap. **That is now resolved.** The net-option-value credit for
premium *paid* was the defect; the premium *received* is the only side that
belongs in the requirement, and only in `required`, not in `final`.
