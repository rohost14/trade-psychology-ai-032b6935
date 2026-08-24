# Pattern #1 reworked — adding to an adverse position

24 Aug 2026. **Proposed contract. No code changed. No threshold introduced.**
Supersedes the trade-to-trade framing in `martingale_behaviour_review.md`, which
was measuring the wrong thing.

---

## The correction, and why the first review missed it

The first review measured **position-to-position**: was the *next* completed
position larger than the *previous* one. That framing cannot see the behaviour it
is named after.

> 1 lot @50 → add 1 @40 → add 1 @30

Every add is the same size. Nothing gets "larger". A multiplier rule of any value
is blind to it. And because a `CompletedTrade` aggregates every entry into one
`avg_entry_price`, all three fills collapse into **one row at 40** — the adds
disappear before any detector sees them.

Measured on the real book, from raw fills rather than completed trades:

| | |
|---|---|
| positions with at least one add | 71 of 742 (9.6%) |
| positions with at least one **adverse** add | **64 (8.6%)** |
| individual adverse adds | **96** |
| **adverse adds smaller than 1.5× the position held** | **95 of 96 — 99%** |
| median add size vs position held | **0.67×** — most adds are *smaller* than what is already on |

**A 1.5× rule is blind to 99% of this behaviour.** That is not a calibration
problem; the axis is wrong.

### The day that shows both failures at once

2025-08-21. The current detector fired **danger** — a push — on
`NIFTY2582125150PE`, a single-fill position that **won ₹1,102**, because three
earlier positions had escalated and then this one de-escalated.

On the same day, in the same session:

```
NIFTY2582125100PE   held 75 @ 24.45   added 75 @ 15.55   = 36% adverse
                    same size, no escalation             = −₹1,065
```

That is the behaviour. **The detector cannot see it, and never could.** It flagged
the recovery and missed the averaging-down, in one session.

## What the correct measurement is

Three dimensions, kept separate. Direction-symmetric by construction.

### 1. Adverse movement, relative to the position's own direction

```
adverse% = (avg_entry_price − fill_price) / avg_entry_price × direction
           direction = +1 for a long position, −1 for a short
```

A long filling **lower** and a short filling **higher** produce the same positive
number. Equity, futures, long options and short options all measure identically,
because this is a price ratio and carries no instrument assumption.

The price is not a market feed — it is **the trader's own fill price**, which is a
market print at the moment of the decision. No LTP dependency, no staleness
class.

Measured across the book: adverse move at the moment of adding —
**p25 5.9% · p50 10.6% · p75 21.6% · max 36.4%**.

### 2. Exposure added while adverse — and exposure is not quantity

Quantity is not exposure and premium is not exposure. The correct denominator is
already built and already used by `revenge_trade`:
`app/core/instrument_risk.py` — `classify()`, `risk_basis()`, `DenominatorKind`.

| instrument | exposure measure | note |
|---|---|---|
| long option | premium paid, `qty × price` | `LOSS_CEILING`. Adding at a **lower** price adds **less** exposure per lot — 1 lot @40 on top of 1 @50 raises exposure by 80%, not 100% |
| short option | margin posted (SPAN) | `MARGIN_POSTED`. Premium *received* is the maximum gain, never the exposure |
| futures | margin posted / notional | `MARGIN_POSTED` |
| equity intraday | notional, leverage-adjusted | `NOTIONAL` |
| spread / hedged multi-leg | **abstain** | `UNRELIABLE`. Leg-sum over-states net risk in a known direction. `revenge_trade` already abstains rather than report a ratio known to be wrong; the same rule applies here |

This is the answer to "do not assume premium or quantity represents exposure" —
the mapping exists, is tested, and needs no new machinery.

### 3. Repetition across the episode

Adverse adds within one position, measured on the book:

| adverse adds | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| positions | 46 | 9 | 5 | 3 | 1 |

18 positions add adversely more than once; 9 do it three times or more.

## The four cases, and which is which

| case | example from the book | verdict |
|---|---|---|
| **Averaging down** — adding while adverse, size flat or smaller | `SENSEX2560380000PE` held 100@20.65, added 80@15.65 (24% adverse, 0.8×) | **catch** |
| **Martingale escalation** — adding while adverse *and* increasing size | `SENSEX25JUL81000CE` … +60@36.00 after holding 120@51.53 (30% adverse, 0.5× then a 3× jump in lots) | **catch, more severe** |
| **Normal re-entry** — a *new* position after the previous one closed | every 671 single-fill position | **not this detector.** This is what `martingale_behaviour` measures today |
| **Adding after a favourable move** | `TITAN25AUG3600CE` held 175@19.20, added 175@21.20 — 10% **in profit** | **must not catch** — 20 such adds exist |

**WITHDRAWN 24 Aug.** This paragraph claimed averaging down and martingale are
"the same behaviour at different intensities" and should be one detector. That is
wrong and the conflation was mine. Adding to an adverse position needs the
position to still be OPEN and does not care about size; martingale needs a CLOSED
loss and an escalation on the next attempt. They read different objects and
neither can observe the other's subject. They may fire together, which is two
true statements rather than duplication.

See `two_behaviours_not_one.md` and
`tests/test_adverse_add_lifecycle.py::TestTheTwoBehavioursAreDistinct`.

### Cases it must catch — verbatim from the book

```
2025-06-12  ASIANPAINT25JUN2400CE   7 legs   −₹2,810
  200@5.05  +200@5.35(−6%)  +200@4.90(+11%)  +200@4.55(+19%)
            +200@4.00(+27%)  +200@3.50(+34%)  +200@3.00
  Constant 200 every time. Price −41%. No add is ever larger.

2025-11-25  NIFTY25NOV26000CE       5 legs   −₹8,835   ← the largest single loss in the book
  75@59.00  +75@50.00(+15%)  +75@42.70(+22%)  +75@34.35(+32%)  +75@30.50(+34%)
  Constant 75 every time.

2025-07-03  NIFTY2570325500PE       2 legs   −₹2,212
  150@24.60 +150@16.15(+34%)   one add, same size, 34% adverse
```

None of these is visible to any detector in the engine today.

### Cases it must not catch

```
2025-08-12  TITAN25AUG3600CE     175@19.20 → +175@21.20   10% IN PROFIT
2025-08-29  NIFTY2590224700CE     75@36.90 → +75@39.70     8% IN PROFIT
2025-04-16  NIFTY2541723000PE    add at 1.2% adverse, 0.5× — noise, not a decision
```

And a case that must be caught but **must not be claimed as a prediction**:

```
2026-01-29  SENSEX26JAN82000CE   4 adverse adds, 9% → 18%   ended +₹5,719 PROFIT
```

Averaging down sometimes works. The alert reports what happened; it does not
forecast.

## Proposed behavioural contract

> **`adding_to_adverse_position` reports one fact: the trader increased exposure
> in a position that had moved against them.**
>
> - **Unit: the fill, inside one open position.** Not the completed trade, and
>   not the gap between two completed trades.
> - **Adverse is relative to the position's own direction.** A long filling lower
>   and a short filling higher are the same event.
> - **Exposure is instrument-specific** (`instrument_risk.risk_basis`), and where
>   the denominator is known to be unreliable — spreads, hedged multi-leg — the
>   detector **abstains** rather than report a ratio that is wrong in a known
>   direction.
> - **Adding while the position is in profit is not this pattern** and must never
>   be reported as it.
> - **Severity is ordinal in three inputs, none of which is fixed here:**
>   depth of the adverse move · whether the add grew exposure · how many times it
>   has happened in this position. Adding while adverse is the finding; adding
>   *more* while adverse is worse; doing it repeatedly is worse still.
> - **It states what happened and makes no predictive claim.** One of the deepest
>   ladders in the book finished profitable.

### Deliberately not decided here

No cut points. Not "how adverse is adverse", not how much growth counts, not how
many repetitions escalate. **The 1.5× and 2.0× multipliers stay exactly as they
are and are not applied to anything new** — under this contract size becomes a
severity input rather than the trigger, and whether those two numbers are the
right cut points *for that role* is a question for after the semantic correction
and a replay, as instructed.

## Relationship to the two neighbouring detectors

All three currently work **position-to-position**. **None of them can see inside a
position.** That is the finding, not an overlap problem.

| detector | what it actually measures | overlaps this contract? |
|---|---|---|
| `martingale_behaviour` (today) | size of completed position N vs completed position N−1, N−2 | **No.** Different unit entirely. It measures re-entry sizing |
| `options_premium_avg_down` | a **new** long-option position opened after a *previously closed* losing option position on the same underlying | **No — and its name is wrong.** It never sees an average-down; it sees re-entry after a realised loss. Recorded for its own review |
| `size_escalation` | quantity or notional across three completed positions | **No.** Same unit as martingale |
| `holding_loser` (position monitor) | an open position held while down, no add required | **Adjacent, correctly.** Holding is that detector's job; **adding** is this one's. The boundary is clean |

So the proposal does not merge or replace anything. It measures an event that has
**no detector at all today**, and the three position-to-position detectors keep
whatever scope their own reviews give them.

## Observability limits — stated plainly

1. **The engine cannot see fills.** `EngineContext` carries
   `completed_trade` and `session_trades` only. No detector reads
   `PositionLedger`, and `num_entries` is read by nothing. **This contract cannot
   be implemented without adding fill-level data to the context** — see below.
2. **Short and non-option coverage is specified but unvalidated.** The book is
   727 LONG vs 15 SHORT; 494 CE, 230 PE, 16 EQ, 2 FUT. **All 64 adverse-add
   positions are long options.** The symmetric rule is correct by construction,
   but this dataset contains no short, futures or equity example to test it
   against. That is a gap in the *evidence*, not in the *definition*, and it
   should be said out loud rather than implied away.
3. **Spreads and hedges abstain**, so the contract deliberately says nothing
   about multi-leg net exposure.
4. **Intent is not observable.** Adding at a worse price may be a planned scale-in
   with a pre-decided ladder. The detector reports the fact; it cannot know the
   plan. Same wall as the revenge research.

## What implementation would require — for approval, not proposed

The data exists. `PositionLedger` already stores `fill_qty`, `fill_price`,
`position_qty_after`, `avg_entry_price_after` and `occurred_at` per fill.
`CompletedTrade.entry_trade_ids` already links a position to its entry fills.

And the plumbing precedent already exists **in the same function**: `_load_context`
already runs a `Trade` query keyed on `completed_trade.exit_trade_ids` to get
`exit_order_types`. The entry side is symmetric — the same query shape on
`entry_trade_ids`, selecting price, quantity and timestamp.

**Hot-path cost is small and boundable.** Only 9.6% of positions have more than
one entry fill, so gating the query on `num_entries > 1` skips it on **90.4% of
trades**. The detector itself stays pure over `ctx`, as every detector is today.

This is still a change to `EngineContext` and one extra query, so it needs
explicit approval before any code is written.

## Status — IMPLEMENTED 24 Aug 2026

Shipped as detector `adding_to_adverse_position` v1.0.0. What was built:

| piece | where |
|---|---|
| fill sequence + adverse-add walker | `app/core/position_fills.py` (new) |
| `EngineContext.position_fills` | `behavior_engine.py`, gated on `num_entries > 1` |
| the detector | `_detect_adding_to_adverse_position`, returns a `DetectorResult` |
| registry + copy | `detector_registry.py`, frames `TRADE` + `STRUCTURAL` |
| frontend name | `AlertContext.tsx` — required by the vocabulary contract test |
| tests | `tests/test_adding_to_adverse_position.py`, 30 cases |

### Severity — two ordinal axes, no score

```
        B1 add < held      B2 add >= held
A1  1×      info               caution
A2  2×      caution            danger
A3  3×+     danger             critical
```

Both axes are **definitional, not calibrated**. "More than once" needs no
number — a repetition requires two. "At least as much again" is the identity,
1.0, not a value anyone picked. No percentage appears in the detector, because
the evidence pass measured every candidate and found no defensible cut point:
adverse depth is one smooth mode with no gap, and the median move when adding is
10.6% against versus 10.4% in favour — **the magnitude carries no information,
only the sign does.**

### Verified on real data

Replayed through the full engine path, six representative sessions:

```
2025-11-25 [critical] NIFTY25NOV26000CE: added 4 times, 15% down to 34% down
2025-06-12 [danger]   ASIANPAINT25JUN2400CE: added 5 times, 6% down to 34% down
2025-07-03 [caution]  NIFTY2570325500PE: added 150 to a position 34% against
2026-01-29 [critical] SENSEX26JAN82000CE: added 4 times, 9% down to 18% down
2025-08-12 [silent]   TITAN — adds were made after FAVOURABLE moves
2025-04-02 [silent]   single-fill position
```

Projected over the full 175-session book: **49 alerting (34 caution, 7 danger,
8 critical) across 40 sessions, plus 15 recorded as info.** For scale, the whole
engine currently produces 388 alerts across 203 sessions.

### A bug the tests caught before it shipped

`test_flip_resets_the_counter` failed on the first run. The walker reset the
add *counter* on a flip but kept the collected adds, so a position that reversed
double-counted. Fixed in `position_fills.py`: `OPEN` and `FLIP` clear the list as
well as the counter, `CLOSE` deliberately does not — a sequence ending
`OPEN..INCREASE..CLOSE` is exactly one position and those adds are the answer.
`martingale_behaviour` is unchanged and still carries the defects documented in
`martingale_behaviour_review.md` — 46 of 58 firings containing a false statement,
22 real escalations missed. Those findings stand; what changes is that fixing
them by moving the ratio operand would still leave the behaviour in this document
undetected.
