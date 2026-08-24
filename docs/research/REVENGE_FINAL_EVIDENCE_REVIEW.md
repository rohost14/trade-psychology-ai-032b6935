# Revenge trading — final evidence review

24 Aug 2026. **Analysis only. No code, thresholds, detectors, or architecture
changed. `revenge_trade` is not deleted.** No replacement detector is proposed,
no ≥N rule, no score, no composite, no episode state machine. Pattern #2 has not
been started.

**Verdict: DATA-CAPTURE-FIRST, with `revenge_trade` FROZEN in place.**

The short version: revenge trading cannot be detected from fill data, and this is
now proven rather than suspected. The information that could answer the question
already flows through our own process every trading day and is discarded at a
single `return` statement.

---

## 1. The fifteen signatures, re-evaluated

Every signature measured after a loss **and after a win**, post-win rate as the
control. 175 sessions with a completed round-trip, 742 round-trips, 435 losses,
326 losses followed by another trade.

| # | signature | after loss | after win | diff | SE | verdict |
|---|---|---|---|---|---|---|
| 1 | faster re-entry | 40.7% | 40.0% | +0.7pp | 4.7 | no separation |
| 2 | larger position | 41.1% | 39.4% | +1.7pp | 4.2 | no separation |
| 3 | higher risk | 49.1% | 43.2% | +5.9pp | 4.2 | **1.4 SE — see below** |
| 4 | same underlying | 31.9% | 33.6% | −1.7pp | 4.2 | **wrong direction** |
| 5 | same underlying + direction | 31.0% | 33.2% | −2.2pp | 4.2 | malformed (98% LONG) |
| 6 | different instrument, larger risk | 34.0% | 30.7% | +3.3pp | 4.0 | no separation |
| 7 | frequency burst | 4.9% | 5.8% | −0.9pp | 1.9 | **wrong direction** |
| 8 | repeated attempts (loss runs) | — | — | — | — | **chance — see §4** |
| 9 | session deterioration | 58.3% | 53.9% | +4.3pp | 4.2 | no separation |
| 10 | above-normal size | 29.4% | 30.7% | −1.3pp | 4.0 | **wrong direction** |
| 11 | combinations | 3.4% (4-of-4) | 1.7% | n=11 vs 4 | — | no compounding |
| 12 | next-day chasing | 3 trades | 4 trades | — | — | **wrong direction** |
| 13 | rule/stop abandonment | — | — | — | — | unobservable here |
| 14 | recovery-target sizing | 97.5% | 95.6% | +1.9pp | 1.3 | tautology (12.3× median) |
| 15 | rotation revenge | 14 | 12 | — | — | rotation, not reaction |

**S3 is not a survivor.** Fifteen signatures were tested; roughly one reaching
1.4 SE is what chance produces. It is the shape of noise, not a weak signal.

**Four point the wrong way.** This trader returns to the same underlying more
often after **wins**, bursts *less* after losses, sizes above normal *less* after
losses, and trades *less* the day after a losing day.

### H2 (≥3 attempts + exposure grew)

Refuted on three counts:

1. **Its exposure test was computed on the wrong quantity** — `any(b > a for a, b
   in zip(qtys, qtys[1:]))`. For options quantity is not exposure. 2025-07-28
   SENSEX ran 5 attempts at a flat 20 lots while capital at risk went 593 → 5600
   (9.45×) for −₹3,605, and was recorded `exposure_grew: False`.
2. **No binary replacement works.** On risk, "any step-up" fires on 9845 → 9940.
   Max single-step multiple across 92 episodes: p50 **1.03×**, p75 1.43×, p90
   2.97×, p95 4.09×, max 9.45× — one continuous tail, no gap to cut.
3. **`≥3 attempts` was doing all the work** — 71 of 92 candidates have exactly
   two attempts, so it discards 77% before exposure is consulted. That is a loss
   run with extra restrictions.

And the outcome evidence never supported it: 8 of 14 H2 firings ended in a win;
6 of the 10 largest escalations ended in a win.

## 2. Does *any* combination separate? No — and this is the decisive test

Rather than hand-pick combinations, I fitted the most permissive instrument
available: an unconstrained logistic regression over all ten observables at once
(re-entry speed, overlap, size change, risk change, same underlying, same
direction, burst, prior session P&L, position in session, absolute risk), scored
by 5-fold cross-validated AUC.

**This is a falsification instrument, not a proposed model.** The fitted weights
are discarded. The logic: if a model with free weights over every observable
cannot separate post-loss from post-win behaviour, no hand-built rule over the
same inputs can either.

```
post-loss vs post-win, prior-state only:   AUC 0.482   folds [0.493, 0.437, 0.531, 0.455, 0.495]
same procedure on SHUFFLED labels:         AUC 0.429
n = 567 transitions (326 post-loss, 241 post-win)
```

**AUC 0.482 — chance.** No combination of observable behaviours separates
loss-chasing from ordinary trading in this book.

**One correction, because it nearly became a false finding.** The first run
returned AUC 0.783, which would have reversed this entire review. It was label
leakage: `running_pnl` accumulates the current trade's own P&L, so it partly
encodes whether that trade lost. Replaced with session P&L *before* the trade,
the result collapsed to chance. The 0.78 measured nothing but the arithmetic of a
running total.

## 3. The eighteen candidate sessions, classified from data only

**None of these is a revenge label.** They are classifications of observable
shape, ranked against the book's own distribution. Percentiles are within the 175
sessions.

| id | date | longest loss run | pct | max post-loss risk step-up | pct | trades | P&L | pct | observable shape |
|---|---|---|---|---|---|---|---|---|---|
| A1 | 2025-07-28 | 5 | 99 | 9.45× | 98 | 11 | −3,405 | 14 | run + escalation + volume |
| A2 | 2025-11-06 | 5 | 99 | 6.01× | 95 | 5 | −4,828 | 7 | run + escalation |
| A3 | 2025-05-20 | 2 | 73 | 5.15× | 94 | 7 | −6,376 | 3 | escalation only |
| A4 | 2025-09-09 | 2 | 73 | 7.64× | 97 | 5 | −2,967 | 15 | escalation only |
| A5 | 2026-02-04 | 4 | 96 | 4.36× | 91 | 7 | −2,222 | 26 | run + escalation |
| B1 | 2025-09-16 | 8 | 100 | 3.35× | 88 | 9 | −5,495 | 5 | run + escalation + volume |
| B2 | 2025-08-13 | 7 | 99 | 3.41× | 89 | 9 | −6,548 | 3 | run + escalation + volume |
| B3 | 2026-01-05 | 5 | 99 | 11.63× | 99 | 7 | −4,139 | 9 | run + escalation |
| B4 | 2025-11-17 | 5 | 99 | 1.33× | 65 | 6 | −2,252 | 25 | run only |
| B5 | 2025-11-20 | 5 | 99 | 1.19× | 58 | 10 | **+165** | 61 | run only, **positive session** |
| C1 | 2025-11-25 | 2 | 73 | 1.41× | 67 | 5 | −9,956 | 1 | **outcome only** |
| C2 | 2026-02-06 | 2 | 73 | 2.86× | 85 | 6 | −3,509 | 13 | escalation only |
| C3 | 2026-02-02 | 3 | 90 | 7.65× | 97 | 5 | −2,574 | 21 | run + escalation |
| D1 | 2026-01-23 | 2 | 73 | 1.15× | 56 | 9 | −8,234 | 1 | **outcome only** |
| D2 | 2026-02-24 | 4 | 96 | 0.84× | 35 | 5 | −5,275 | 6 | run + **de-escalation** |
| D3 | 2026-01-22 | 4 | 96 | 0.83× | 35 | 5 | −4,144 | 8 | run + **de-escalation** |
| D4 | 2025-05-09 | 3 | 90 | 1.19× | 59 | 3 | −3,916 | 10 | run only |
| D5 | 2025-09-22 | 3 | 90 | 0.88× | 38 | 3 | −2,859 | 16 | run + de-escalation |

Book medians: run 2, step-up 1.08×, 4 trades, −₹559.

**What this actually shows, and it is not flattering to the selection:**

- **The "control" group is not a control.** D2 and D3 sit at the 96th percentile
  for loss runs — as extreme as most of Group B. They were separated only by
  escalation, which is the criterion I selected them on. Circular.
- **Run length and escalation are independent.** B4/B5 have p99 runs with
  ordinary step-ups; A3/A4 have p94–97 step-ups with p73 runs. They do not
  co-occur, which is what §1 signature 11 already showed.
- **Neither tracks outcome.** B5 is a 5-loss run that finished **+₹165**. C1 and
  D1 are the two worst sessions in the book (p1) with entirely ordinary shape.
- **The two worst days look normal.** If revenge is what makes a day go badly,
  the days it went worst should look distinctive. They do not.

The honest classification of all eighteen: **six show escalation, ten show a long
run, three show only a bad outcome, and no combination of these tracks either the
other or the result.**

## 4. Observable versus fundamentally invisible

**Loss runs are arithmetic, not behaviour.** Win rate 41.4% (307/742). Shuffling
each session's outcomes 2,000 times at that rate, preserving session lengths:

| run length | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| observed | 125 | 65 | 32 | 11 | 5 | 0 | 1 | 1 |
| expected by chance | 129.6 | 61.6 | 28.8 | 12.1 | 5.1 | 1.9 | 0.9 | — |

Indistinguishable, including the 8-run. **This retracts my own recommendation
from the previous session**, where I proposed the loss-run as the surviving unit.
It survives as a *fact about the session*; it carries no behavioural information,
and under the design of record a 3-run would render around p80 — `danger` — while
being chance.

| behaviour | verdict | proof |
|---|---|---|
| overlapping positions | **OBSERVABLE** | 17.8% post-loss, 25.3% post-win |
| rotation across instruments | **OBSERVABLE** | 14 after a loss, 12 after a win |
| repeated attempts / runs | **OBSERVABLE, but chance-distributed** | table above |
| risk escalation | **OBSERVABLE, continuous** | p50 1.03× → max 9.45×, no gap |
| re-entry speed | **OBSERVABLE, no contrast** | median 12.6 min vs 16.5 min |
| frequency bursts | **OBSERVABLE, wrong direction** | 4.9% vs 5.8% |
| session deterioration | **OBSERVABLE, confounded** | negative in both branches |
| next-day behaviour | **OBSERVABLE, wrong direction** | 3 trades vs 4 |
| rule / stop abandonment | **NOT OBSERVABLE from tradebook; OBSERVABLE live** | CSV has no order-type column; `trades.order_type` exists and postbacks carry `SL`/`SL-M` |
| order churn (modify/cancel/replace) | **THROWN AWAY — see §6** | arrives live, filtered out |
| setup quality | **NOT OBSERVABLE** | no entry reason, no chart context, no watchlist |
| recovery intent | **NOT OBSERVABLE — permanently** | not in any feed; inferable only from outcome, which is circular |

## 5. Behaviour by behaviour

**Rotation revenge** — 14 sequences of three different underlyings with rising
risk starting from a loss, 12 starting from a win. 2025-11-26 CONCOR → UNITDSPR →
PGEL, ₹5,938 → ₹8,600 → ₹17,255, −₹2,520 is visually compelling and statistically
ordinary. This is portfolio rotation.

**Same-instrument revenge** — returning to the same underlying is *less* likely
after a loss (31.9% vs 33.6%). The same-instrument restriction in H2 was not
merely unnecessary, it selected against the evidence.

**Repeated attempts** — frequent (50 of 240 runs reach 3+, 48 of 175 sessions)
and fully explained by chance.

**Risk escalation** — the only dimension with any directional consistency, and it
is continuous with no natural break. Every attempt to binarise it either misses
the 9.45× case or admits the 1.01× case.

**Speed** — no contrast. Re-entry is essentially as fast after wins.

**Frequency bursts** — median 1 trade within 30 minutes of an exit in both
branches; the 3+ rate is lower after losses.

**Session deterioration** — the rest of the session is negative more often than
not after wins *and* losses, which describes the book's edge, not a reaction.

**Rule / stop abandonment** — the one signature that would most directly indicate
loss of discipline, and the tradebook cannot see it at all. Not weak evidence:
**no** evidence. See §6.

**Next-day behaviour** — contrary. After a losing day, median 3 trades; after a
winning day, median 4. Identical median first-trade size.

## 6. The order-history gap — what we receive and what we discard

This is the substantive finding of this review.

**What arrives.** `order_stream_service.py` opens a KiteTicker per online user and
documents its own callback as *"Fired for every order status change of the
authenticated user"* — regardless of where the order was placed. Postbacks carry
the same shape. The payload already includes `status`, `order_type` (MARKET /
LIMIT / **SL** / **SL-M**), `trigger_price`, `pending_quantity`,
`cancelled_quantity`, `parent_order_id`, `order_timestamp`,
`exchange_update_timestamp`, and the full `raw_payload`.

**What we keep.** Two losses, at two different layers:

```python
# order_stream_service.py — every non-fill event is dropped at ingestion
status = (data.get("status") or "").upper()
if status != _FILL_STATUS:        # "COMPLETE"
    return
```

```python
# trade_sync_service.py — and the EOD path collapses history to final state
stmt.on_conflict_do_update(index_elements=['broker_account_id', 'kite_order_id'], …)
```

So: **placed, modified, cancelled and rejected events are discarded at ingestion,
and the one path that does persist orders upserts on order id — a
modify → modify → cancel sequence collapses into a single final row.**

This is not a Zerodha limitation, a permissions gap, or a missing endpoint. The
data reaches our process and we throw it away. Both behaviours are correct for
their original purpose — the pipeline only needs fills, and the orders table only
needs current state — but they make an entire class of behaviour unobservable.

**What that class contains** — behaviours a fill record can never show:

- **stop-loss placed, then cancelled while the position ran** — the single most
  direct observable of discipline breaking down, and invisible today
- **modify count per order** — moving a stop away from price
- **cancel-then-replace within seconds**, and time from placement to cancellation
- **orders placed and pulled without ever filling** — hesitation, or hunting

Reading B from the previous session — *revenge changes which trade you take, not
its shape* — is precisely the hypothesis these observables would test, and the
only one still standing after §2.

## 7. The five-way separation

**OBSERVABLE FACT** — 435 losses across 175 sessions. Loss runs up to 8. Positions
overlap in 17.8% of post-loss cases. Risk step-ups from 0.8× to 9.45×. Re-entry
median 12.6 min after a loss. 98% of round-trips are LONG options. Next-day trade
count 3 after a loss, 4 after a win. Win rate 41.4%.

**CORRELATION / SIGNAL** — none that survives. Fourteen measurable signatures, max
1.4 SE, four pointing the wrong way; a free-weight model over all of them together
reaches AUC 0.482.

**INFERENCE** — that loss runs indicate a behavioural state (refuted: matches
chance). That escalation after a loss indicates chasing (unsupported: 6 of 10
largest ended in a win). That H2's 14 sessions were revenge episodes (unsupported:
its exposure test measured the wrong quantity and its real filter was attempt
count).

**INTENT THAT CANNOT BE OBSERVED** — why a trade was taken. Whether a setup would
normally have been skipped. Whether size was chosen to recover a specific loss.
Emotional state. These are not in any feed, at any price, and no amount of fill
data will ever recover them. Any detector claiming them is claiming something it
cannot know.

**DATA WE ARE CURRENTLY THROWING AWAY** — every non-COMPLETE order event, dropped
at `order_stream_service.py` ingestion; and the modification history of every
order, collapsed by the upsert in `sync_orders_to_db`. Concretely: stop placement
and cancellation, modify counts, cancel/replace churn, placement-to-cancel timing,
and unfilled orders.

## 8. Verdict

**DATA-CAPTURE-FIRST. `revenge_trade` stays FROZEN and undeleted in the meantime.**

Against the alternatives:

- **DROP** — wrong, but not because the evidence is encouraging. It is
  discouraging. It is wrong because we have never tested the data that could
  actually answer the question, and that data is already arriving. Dropping now
  would discard the hypothesis on evidence that could not have confirmed it.
- **REDESIGN** — wrong. There is nothing to design from. AUC 0.482 means a
  redesign would be fitting to noise, and every previous attempt (S2a, streak,
  H2, exposure ratios) failed the same way for the same reason.
- **MIRROR-ONLY** — tempting, and it was my own recommendation last session, but
  §4 retracts it. A "3rd consecutive loss" mirror shows a chance artefact in a
  frame that implies meaning, and the severity model would render it `danger`. It
  remains defensible *only* as a bare fact with no severity, no cost, and no
  behavioural language — a weaker product than it appeared.
- **KEEP / FREEZE alone** — insufficient. Freezing is right for the detector but
  is not a plan; without capture the question stays permanently unanswerable.

**What to build now:** nothing in the engine. The one thing worth doing is
capture — retain non-COMPLETE order events and stop collapsing modification
history — and that is a data decision, not a detector, with independent value for
`no_stoploss` regardless of what it eventually says about revenge.

**What stays research-only:** revenge detection entirely. No rule, no threshold,
no episode model, no severity.

**What evidence would justify a real revenge alert later:**

1. **Stop-cancellation events**, live. If stops are cancelled at a materially
   higher rate after a loss than after a win — the same control used throughout
   this review — that is the first genuine signal any of this work has produced.
2. **Order churn after losses**, measured against the post-win control.
3. **`heeded` response data.** Rest-of-session P&L ranks detectors but cannot
   judge the product. An alert exists to convert an automatic action into a
   deliberate one; only response data measures that.
4. A signal that clears the control by a margin that a fifteen-test family can't
   manufacture. Nothing in this review comes close.

**And the honest possibility that must stay on the table:** this trader may simply
not revenge trade often. The next-day evidence points that way — fewer trades
after a losing day, not more. If the captured order data also comes back null, the
correct product answer is that TradeMentor does not ship a revenge alert, and says
so plainly rather than shipping a detector that fires on chance.
