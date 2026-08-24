# Pattern #1 — evidence-based validation of the contract

24 Aug 2026. **No production code changed. No threshold introduced. No score, no
merge, no delete.** Companion to `adding_to_adverse_position_contract.md`.

**Bar set before looking at anything** — because this is the step where S2a and
the revenge exposure ratio were both invented and then refuted: *a separation
counts only if the distribution shows it — a gap with no mass in it, or two
distinguishable modes. A percentile is not a separation; it is a number I chose.*

---

## 1. Canonical behavioural definition

> **The position moved against the trader, and the trader added exposure to it.**

That is the whole observable. Everything else — how far it had moved, how much
was added, how many times — describes *how much* of the behaviour occurred, not
*whether* it occurred.

The behaviour is **not** "the new order was bigger". Bigger is one way to do it,
and in this book the rare way.

## 2. What 1.5× / 2.0× measure today — exactly

`martingale_caution_multiplier` and `martingale_danger_multiplier` are compared
against `max_ratio`, computed in `_detect_martingale_behaviour` as:

```python
sizes    = last 3 PRIOR completed positions   (quantity, or notional if the
                                               trader changed underlying)
max_ratio = max(sizes[i] / sizes[i-1] for i in 1..len-1)
```

Three properties, all verified in code:

1. **The unit is a completed position, not a fill.** It compares one closed
   round-trip against another closed round-trip.
2. **It never touches the current trade.** The current position is appended to
   the displayed sequence and excluded from the arithmetic.
3. **It measures re-entry sizing** — how big the next *separate* position was —
   which is a different event from adding to a position that is already open.

So the multipliers are not mis-calibrated. **They are pointed at another event.**

## 3. Evidence for and against keeping 1.5× / 2.0×

Applied to the behaviour itself — the add — across the 96 adverse adds in the
book:

| reading of "1.5× / 2.0×" | fires at caution | fires at danger | max observed |
|---|---|---|---|
| quantity of the add vs quantity held | **1 of 96** | **0 of 96** | 1.50× |
| exposure of the add vs exposure held | **0 of 96** | **0 of 96** | 138% |
| **cumulative exposure across the episode** | **17 of 64** | **10 of 64** | 699% |

**Against keeping them per-add:** on a year of real trades they would fire once
at caution and never at danger. A rule that cannot reach the behaviour it names
is not conservative, it is inert.

**Why:** when you average down, each added lot costs *less* than the ones you
hold, so a same-size add is always **below** 100% of held exposure. The median
adverse add is **0.67× the quantity held** and **60% of the exposure held**. The
multiplier and the behaviour move in opposite directions.

**For keeping them somewhere:** the one dimension where they have real mass is
**cumulative exposure across the episode** — 27% of adverse-add positions cross
150%, 16% cross 200%. That is the only reading with a distribution to speak of.

**Verdict on the multipliers**

| dimension | verdict | reason |
|---|---|---|
| per-add quantity or exposure ratio | **REMOVE** | fires 0–1 times in 96. Inert, and pointed at the wrong unit |
| cumulative episode exposure | **DEFER** | the only reading with mass (17/64, 10/64). Whether those are the right cut points is a replay question, not a distribution question |
| current use (re-entry sizing, position-to-position) | **DEFER to `martingale_behaviour`'s own scope** | that detector may legitimately keep measuring re-entry sizing; that is decided when its scope is settled, not here |

## 4. Evidence for and against percentage-based measures

### 4a. % adverse movement at the moment of adding — **no defensible threshold**

```
adverse adds   n=96
   0.0-2.5    9  ################################
   2.5-5.0    9  ################################
   5.0-7.5   12  ###########################################
   7.5-10.0  15  ######################################################
  10.0-12.5   9  ################################
  12.5-15.0   5  ##################
  15.0-17.5   7  #########################
  17.5-20.0   5  ##################
  20.0-22.5   5  ##################
  22.5-25.0   5  ##################
  25.0-27.5   3  ###########
  27.5-30.0   4  ##############
  30.0-32.5   3  ###########
  32.5-35.0   4  ##############
  35.0-37.5   1  ####
```

p10 2.9 · p25 5.9 · p50 10.6 · p75 21.6 · p90 28.5 · max 36.4.
**Empty gaps wider than 2pp inside the range: none.** One mode, smooth decay.

**And the control kills it outright.** The magnitude of the move when the trader
adds is the same whether the move is for or against them:

| | adverse adds | favourable adds |
|---|---|---|
| median \|move\| at the moment of adding | **10.6%** | **10.4%** |

This trader adds after roughly a 10% move in **either** direction. **The
magnitude carries no information. The sign carries all of it.**

That is the most important result in this document, and it is a good one: the
sign of the move is **definitional and binary** — adverse or not — so the trigger
needs no calibrated number at all.

### 4b. % additional exposure vs exposure held — **no threshold, but structure**

```
   0-10     0
  10-20     6  ############
  20-30    12  ########################
  30-40    12  ########################
  40-50    17  ##################################
  50-60     1  ##
  60-70     5  ##########
  70-80     6  ############
  80-90     9  ##################
  90-100   27  ######################################################
 100-130     0                      <- a real gap
 130-140     1  ##
```

The mode at 90–100% is "added the same number of lots"; the gap above 100% is
real but explained arithmetically — adding more lots than you hold *while the
price is against you* is simply rare here (max quantity ratio 1.50×). It is a
fact about this trader's habit, not a natural boundary in the behaviour.

Adverse p50 60% vs favourable p50 100% — the difference is again arithmetic, not
psychology: a favourable add costs *more* per lot.

### 4c. Cumulative exposure across the episode — continuous, has mass

p25 85% · p50 96% · p75 181% · max 699%. Big mode at 75–100% (doubled once), then
a long tail. No gap. Usable as an ordinal measure; not a place to put a line
without a replay.

### 4d. Repetition — **the one measure with a defensible break**

| adverse adds in one position | positions | share |
|---|---|---|
| 1 | 46 | 71.9% |
| 2 | 9 | 14.1% |
| 3 | 5 | 7.8% |
| 4 | 3 | 4.7% |
| 5 | 1 | 1.6% |

The break at **"more than once"** is definitional, not calibrated — a repetition
requires two. It splits the population 72 / 28 and needs no number chosen by me.

### 4e. Progression — a fact worth reporting, not a threshold

Of the 18 positions that add adversely more than once, **13 deepen strictly every
time** — each add is further against them than the last. 2 more end deeper than
they started. Only 3 do not deepen.

**Summary answer to "should severity be expressed as percentages?"**
**No — not as thresholds.** Two of the five candidate measures are continuous with
no gap, one is explained by arithmetic, and the depth measure is refuted outright
by its own control. The measures are good for **describing** what happened in the
alert. They are not defensible as **cut points**. The only structure the data
actually supports is the **sign** of the move and the **fact of repetition**, both
of which are definitional.

**No replacement percentage is proposed, because the evidence does not support
one.**

## 5. Exposure and adverse-movement definitions

**Adverse movement** — direction-signed, instrument-agnostic, from the trader's
own fill price:

```
adverse% = (avg_entry_price − fill_price) / avg_entry_price × direction
           direction = +1 long, −1 short
```

**Exposure** — reuse `app/core/instrument_risk.risk_basis()` unchanged. It
already wraps `estimate_capital_at_risk` and labels the denominator:

| class | denominator | comparable? |
|---|---|---|
| long option | `LOSS_CEILING` — premium paid | yes |
| short option | `MARGIN_POSTED` — margin, never the premium received | yes |
| futures | `MARGIN_POSTED` | yes |
| equity | `NOTIONAL` | yes |
| **spread / hedged** | **`UNRELIABLE`** | **no — `is_comparable` is False → abstain** |

**No new exposure model is proposed.** The one that exists is correct and already
carries the abstention.

## 6. Minimum data required

Per **open position**, in fill order, until it returns to flat:

| field | source | why |
|---|---|---|
| direction (signed position) | `PositionLedger.position_qty_after` sign | the whole symmetry rests on it |
| original entry price, quantity | first fill | the reference the move is measured from |
| each subsequent fill: price, signed qty, timestamp | `PositionLedger.fill_price`, `fill_qty`, `occurred_at` | the adds |
| running average entry after each fill | `PositionLedger.avg_entry_price_after` | already computed — no need to recompute |
| running position quantity | `PositionLedger.position_qty_after` | distinguishes an add from a partial exit |
| instrument type + symbol | `CompletedTrade` | for `risk_basis` |
| spread membership | `ctx.strategy_group` | to abstain |

**Everything on that list already exists.** `PositionLedger` stores all six
per-fill fields. Nothing new needs to be computed or recorded — it needs to be
*reachable*, and today `EngineContext` carries none of it.

Cheapest correct route, using the precedent already in `_load_context` (which
queries `Trade` on `exit_trade_ids` for `exit_order_types`): the symmetric query
on `entry_trade_ids`, gated on `num_entries > 1`, which skips **90.4%** of trades.

## 7. Cases detected / ignored / abstained

**DETECTED** — adverse add, exposure increased

```
2025-06-12  ASIANPAINT25JUN2400CE  −₹2,810  7 legs, constant 200, price −41%
2025-11-25  NIFTY25NOV26000CE      −₹8,835  5 legs, constant 75  (worst loss in the book)
2025-07-03  NIFTY2570325500PE      −₹2,212  1 add, same size, 34% adverse
2026-01-29  SENSEX26JAN82000CE     +₹5,719  4 adverse adds — detected, and profitable
```

**IGNORED** — the move was in the trader's favour

```
2025-08-12  TITAN25AUG3600CE      175@19.20 → +175@21.20   10% in profit
2025-08-29  NIFTY2590224700CE      75@36.90 → +75@39.70     8% in profit
```

20 such adds exist across 7 positions. Under the contract these are never
reported, in any severity.

**ABSTAINED** — exposure not reliably determinable

Any leg inside a detected spread or hedge (`is_comparable == False`). The
detector says nothing rather than dividing by a denominator known to be
over-estimated.

**NOT THIS PATTERN** — a new position after the previous one closed. That is
re-entry, and it belongs to whatever scope `martingale_behaviour` keeps.

## 8. Overlap with existing detectors

All three neighbours work **position-to-position**. None can see inside a
position. There is no overlap to resolve — there is a gap.

| detector | unit | measures | overlap |
|---|---|---|---|
| `martingale_behaviour` | completed position | re-entry sizing across 3 closed positions | **none** |
| `options_premium_avg_down` | completed position | a new long-option position after a *previously closed* losing one on the same underlying | **none** — despite the name it never observes an average-down |
| `size_escalation` | completed position | quantity/notional across 3 closed positions | **none** |
| `holding_loser` | open position | held while down, **no add** | **adjacent, clean** — holding is its job, adding is this one's |

Per instruction, all three keep their current scope and none is merged or deleted
here.

## 9. Synthetic test matrix

Directional symmetry was **proven, not asserted** — the measurement was run
against `instrument_risk` for every class. Each long/short pair returns identical
numbers:

| case | adverse% | class | denominator | comparable |
|---|---|---|---|---|
| long equity, price falls | +10.0% | equity | notional | yes |
| short equity, price rises | +10.0% | equity | notional | yes |
| long futures, price falls | +1.0% | futures | margin_posted | yes |
| short futures, price rises | +1.0% | futures | margin_posted | yes |
| long CE, premium falls | +20.0% | long_option | loss_ceiling | yes |
| long PE, premium falls | +20.0% | long_option | loss_ceiling | yes |
| short CE, premium rises | +20.0% | short_option | margin_posted | yes |
| short PE, premium rises | +20.0% | short_option | margin_posted | yes |
| **spread leg (hedged)** | +20.0% | spread | **unreliable** | **no → abstain** |

And what the current multipliers would say about the same cases:

| case | qty ratio | current rule | contract |
|---|---|---|---|
| averaging down, same size | 1.00× | **SILENT** | report |
| martingale, bigger add | 3.00× | danger | report, more severe |
| adding after a favourable move | 1.00× | SILENT | **ignore — correct** |
| short, adding while adverse | 1.00× | **SILENT** | report |
| short, adding while favourable | 1.00× | SILENT | **ignore — correct** |

### Test matrix to build when implementation is approved

| # | case | expect |
|---|---|---|
| 1–2 | long / short **equity**, adverse add | detect, identical numbers |
| 3–4 | long / short **futures**, adverse add | detect, identical numbers |
| 5–6 | long **CE / PE**, adverse add | detect |
| 7–8 | short **CE / PE**, adverse add | detect, `MARGIN_POSTED` not premium |
| 9 | spread leg | **abstain** |
| 10 | hedged multi-leg | **abstain** |
| 11 | constant-size adds ×3 | detect, repetition recorded |
| 12 | increasing-size adds ×3 | detect, more severe than 11 |
| 13 | **decreasing** exposure (partial exit) | **not an add — silent** |
| 14 | add after recovery into profit | **silent** |
| 15 | add at exactly break-even (0%) | **silent** — the sign is the trigger |
| 16 | closed position, then re-entry | **silent** — not this pattern |
| 17 | partial exit then re-add while adverse | detect the re-add only |
| 18 | position flips through zero | new position, counters reset |
| 19 | single-fill position | silent |
| 20 | `num_entries > 1` but all adds favourable | silent |

## Standing limitation, restated

**All 64 adverse-add positions in the book are long options.** 727 LONG vs 15
SHORT; 494 CE, 230 PE, 16 EQ, 2 FUT. The symmetric rule is correct by
construction and proven on synthetic cases, but **no real short, futures or
equity example exists here to validate it against.** That gap belongs in the
record, not in a footnote.

## Status

Contract direction validated. **Percentage thresholds examined and rejected on
evidence.** The multipliers are REMOVE for the per-add dimension and DEFER for
the cumulative one. Nothing implemented; no cut points chosen.
