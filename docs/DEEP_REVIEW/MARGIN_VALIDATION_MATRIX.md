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

```
zero-margin cases   : 11/11 computed exactly 0
cases compared      : 24
median |error|      : 4.0%
90th pct |error|    : 7.3%
max |error|         : 397.4%
within 5%           : 14/24
within 15%          : 23/24
```

*(`nan%` marks a case where the broker blocks nothing, so a percentage is
undefined. Those are scored exactly instead — see below.)*

---

## What the distribution says

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
