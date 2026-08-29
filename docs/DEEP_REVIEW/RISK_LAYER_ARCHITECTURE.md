# Risk Layer — Architecture

**29 Aug 2026. Deliverable 4. Design only. Nothing is wired.**

---

## 1. Three quantities. Not one, and not five.

The engine today collapses everything into one "capital at risk" number. That is
the root of F3, F17 and the martingale comparability problem. The replacement is
three separate quantities with three separate jobs.

| # | quantity | definition | who needs it |
|---|---|---|---|
| **A** | **entry value** | `avg_entry_price × qty × multiplier`. Premium paid for a buyer, premium received for a writer, contract value for a future or share | every behavioural ratio |
| **B** | **P&L** | `(exit − entry) × qty × multiplier`, **RAW** — no brokerage, STT or tax, ever | every outcome measure |
| **C** | **capital requirement** | what the account actually gave up. Long option = premium paid. Short option, future = **margin**. Equity = notional | "how big is this relative to my account" |

Plus one flag, not a fourth quantity:

**`DenominatorKind`** — `LOSS_CEILING` (bounded by what was committed) /
`MARGIN_POSTED` (not bounded) / `NOTIONAL` / `UNRELIABLE`.

### Maximum theoretical loss is deliberately NOT a quantity

For a long option it equals A. For a short option or a future it is unbounded, so
it cannot be a denominator and cannot be displayed. Its entire information
content is *bounded or not*, which the flag already carries. Introducing it would
add a number nothing can consume.

### A and B never require margin

```
Buy  NIFTY CE @ 50 x 65  ->  exit 45   ->  P&L −325,  −10% of premium paid
Sell NIFTY CE @ 50 x 65  ->  buy 100   ->  P&L −3,250, −100% of premium received
```

Both are complete without any margin figure. **−100% of premium received is how a
writer actually thinks about that trade**, and it is a correct, meaningful
number. The only thing that must change is the *label*: this is premium, never
"capital at risk".

Margin enters only at C, and only for the questions in §3.

---

## 2. Provenance is a first-class field

Every margin value carries its source. There is no default and no silent
fallback.

| source | meaning | may be shown as a rupee figure? |
|---|---|---|
| `BROKER` | from Kite `/margins/orders`, captured at order time | **yes** |
| `COMPUTED` | reconstructed by `margin_model` from exchange methodology | **no** — a band, or "approx", never an exact claim |
| `UNAVAILABLE` | no basis exists; the caller must abstain | never |

**A `COMPUTED` value must never be described as the margin the broker blocked.**
Measured error is +5-7% on short options and sub-1% on futures and spreads
([`MARGIN_VALIDATION_MATRIX.md`](MARGIN_VALIDATION_MATRIX.md)); good enough to
gate a percent-of-capital rule, not good enough to print.

### Four different numbers, kept apart

Collapsing these is how the current code got into trouble.

| scope | question | note |
|---|---|---|
| **single position** | what does this one leg require standalone? | wrong for any hedged book |
| **order-level** | what does adding this order require, given what I already hold? | what Kite `/margins/orders` returns |
| **portfolio** | what does the whole book require right now? | the only number comparable to account capital |
| **strategy** | what does this group of legs require together? | needs a definition of the group |

`margin_model.compute_margin` computes **portfolio margin for one underlying**. It
is not a single-position number and must not be stored in a field named as if it
were.

---

## 3. Which question needs which quantity

| question | quantity |
|---|---|
| how did this trade do? | B |
| how big was the loss relative to the trade? | B / A |
| did the trader size up after a loss? | A, and only across comparable instruments |
| how much account capital is committed? | **C, portfolio scope** |
| how large is this position against available capital? | **C** |
| how much is blocked by this strategy? | **C, strategy scope** |
| is the loss capped by what was committed? | the flag |

---

## 4. Instrument and direction — all eight, explicitly

`LONG` = bought exposure. `SHORT` = sold exposure. **Never inferred from CE/PE.**

| combination | class | quantity C | flag |
|---|---|---|---|
| Buy Call | `long_option` | premium paid | `LOSS_CEILING` |
| **Sell Call** | `short_option` | **margin** | `MARGIN_POSTED` |
| Buy Put | `long_option` | premium paid | `LOSS_CEILING` |
| **Sell Put** | `short_option` | **margin** | `MARGIN_POSTED` |
| Buy Future | `futures` | **margin** | `MARGIN_POSTED` |
| Sell Future | `futures` | **margin** | `MARGIN_POSTED` |
| Buy Equity | `equity` | notional | `NOTIONAL` |
| Sell Equity | `equity` | **UNRESOLVED** — notional today; a short posts ~20% margin with unbounded loss | should be `MARGIN_POSTED` |

A long PE is not bearish behaviour. A short CE is not a hedge. **Whether anything
is a hedge is a property of the portfolio, not of the leg** — and §6 shows we no
longer need to answer it to get the capital right.

Product dimension, orthogonal: **MIS** (intraday), **NRML** (overnight),
**MTF** (§10), **CNC** (excluded from the platform).

---

## 5. Single leg — what the layer must expose

Sell NIFTY 24500 CE × 65, five distinct facts:

| fact | value | source |
|---|---|---|
| premium received | `price × 65` | trade |
| entry value (A) | same | trade |
| capital requirement (C) | **margin** | `BROKER` if captured, else `COMPUTED` |
| P&L (B) | `(entry − exit) × 65` | trade |
| loss bounded? | **no** | flag |

Note what is *not* here: no "estimated margin ≈ 12% of strike". That constant runs
**−35% to +158%** against reality and is retired by this design.

---

## 6. Hedges — computed, not classified

```
Sell NIFTY 24200 CE x 65            broker total  Rs 175,747
Sell 24200 CE  +  Buy 24700 CE      broker total  Rs  64,174   (−63%)
```

Adding a position **reduced** the requirement by 63%. Summing naked legs would
have given ~₹176k+ instead of ₹64k.

**The model reproduces this to −0.3% and contains no hedge rule at all.** Under
each of the 16 scenarios the long leg's gain and the short leg's loss enter the
same sum, so the joint worst case is smaller than the sum of the separate worst
cases. That is how the exchange gets it too.

This settles a question the semantics audit left open. `strategy_detector`
guesses structures from entry-time proximity, labels a FUT + short-PE a "hedge"
(F5), and grants suppression to `MULTI_LEG_UNKNOWN` (F6). **For capital, none of
that is needed** — scan the legs together and the answer is right whether or not
we can name the structure.

Applies equally to long future + short put, short future + short call, call and
put spreads, condors, butterflies, straddles, strangles and ratio spreads: no
per-strategy rule, no invented hedge ratio.

**Two things still require a product decision** and are NOT resolved here:

- **Calendar spreads.** Different expiries carry a published charge (1.75% index
  / 2.2% stock) that needs composite delta. The model **flags** them
  (`calendar_spread_unmodelled`) instead of quietly understating.
- **What counts as one strategy group** for the *strategy-scope* number. Margin
  needs no grouping; attributing capital to a named strategy does.

---

## 7. Data flow

```
LIVE                                    HISTORICAL
order placed                            bhavcopy + FOVOLT  (public, archived)
  -> Kite /margins/orders                 -> instrument master (effective-dated)
  -> store span/exposure/total            -> margin_model.compute_margin
  -> source = BROKER                      -> source = COMPUTED
                    \                    /
                     v                  v
              margin record (immutable, provenance-tagged)
                             |
                             v
                   risk_basis  ->  is_comparable gate
                             |
                             v
                   detectors that need C  (see DETECTOR_RISK_DEPENDENCY_MAP.md)
```

**Store, never re-derive.** Once written, a margin record is immutable.
Volatility moves; recomputing a closed trade next month would silently change
last month's alerts.

---

## 8. Where F17 sits

The layer is worthless if callers bypass it. Today `_detect_excess_exposure` and
`constitution_violation` call `estimate_capital_at_risk` **directly** and never
touch `risk_basis` — so `is_comparable`, `is_spread` and every UNRELIABLE marking
are unreachable for them. VERIFIED: `_detect_excess_exposure` has zero references
to either.

**F17 is the prerequisite for everything above.** An exact margin that a detector
does not consult changes nothing.

---

## 9. Recommendation on F3

**Option C: broker margin when available, computed margin historically —
sequenced, not immediate.**

F3 is currently correct in *direction* and crude in *magnitude*: it replaced a
number that was ~200× too small with one that is roughly the right order but
scales with strike, giving −35% to +158%.

**State this precisely, because it has been misread once already:**

> ₹1,080 → ₹225,000 is **not** a ₹224,000 loss.
> It is a change in the **denominator** used to estimate what the position
> required. **The trade's P&L did not change by one rupee.**

Sequence:

1. **Keep F3 as-is for now.** It is conservative and its failure mode is
   documented. Reverting would restore a 200× understatement.
2. **Land F17**, so the safety layer is actually consulted.
3. **Replace the estimate** with `margin_model`, tagged `COMPUTED`.
4. **Capture `BROKER`** at order time going forward, and prefer it.

Steps 3 and 4 are detector-visible and are **not** approved by this document.

---

## 10. MTF — classification

VERIFIED by grep: MTF exists in this codebase **only as a product tag**. It
appears in `_TRACKED_PRODUCTS`, the position key, and the CNC exclusion filter.
No leverage, financing or margin figure is ingested or computed anywhere.

| aspect | finding | class |
|---|---|---|
| is MTF relevant to F&O? | **No.** MTF is a cash-equity facility. F&O has its own margin regime | **DESIGN** — decide whether MTF is in product scope at all |
| what does Kite provide? | product tag on the order/position. Whether a per-position MTF funding figure is exposed is **not established** | **UNSUPPORTED pending research** |
| what do we ingest? | the tag only | — |
| what does capital requirement mean for MTF? | the trader funds part and the broker funds the rest; "capital committed" is the funded part, not notional | **DESIGN** |
| what is safe with today's data? | treating an MTF position as **cash equity at full notional**, which is what happens now. Conservative, and wrong in a known direction | **acceptable interim** |
| what needs more broker data? | the actual funded fraction and financing cost | **UNSUPPORTED** |

**Do not "fix" MTF by guessing a leverage ratio.** On the reference book there are
**zero** MTF positions, so nothing is currently mismeasured by it.

---

## 11. What this document does not decide

- table shapes or migrations
- whether to backfill the full reference book
- BFO / CDS / MCX support — **unvalidated, must not be enabled**
- short equity's denominator (§4)
- calendar spread charge and strategy grouping (§6)
- any change to any detector
