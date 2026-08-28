# Trading Semantics & Strategy Coverage Audit

**Status: IN PROGRESS — started 28 Aug 2026.**
Working document. Updated as findings land.

Brief: [`positional_validation.md`](positional_validation.md). **No code changes
in this audit.** Findings only.

---

## Why this exists

Patterns 6–11 established a principle the brief states directly:

> Before any detector is allowed to make a behavioural claim, establish that the
> underlying trading event is correctly classified at the position/strategy level.

Every retirement in that run failed for the same underlying reason — the detector
was making a behavioural claim about an event it had not correctly classified.
`direction_instability` read a CE→PE swap as emotional reversal when the data
said loss-cutting. `size_escalation` read three rising numbers as escalation.
`premium_loss_event` measured a percentage that means opposite things for a
buyer and a writer.

This audit asks the prior question across the whole engine, for traders unlike
the one whose book it was built on.

## Classification scheme

| | meaning |
|---|---|
| **PASS** | correctly represented and safely handled |
| **GAP** | something important is missing |
| **FALSE-POSITIVE RISK** | an existing detector could misclassify legitimate behaviour |
| **UNSUPPORTED** | current data cannot reliably determine it |

Every GAP / FALSE-POSITIVE RISK must name the exact detector, service, file and
line affected. **A structure is not "identified" if the data cannot prove it.**

## The engine under audit

23 detectors, 29 pattern types (`all_pattern_types()` is the authority).
Patterns 1–11 reviewed; 4, 6, 9, 10, 11 retired on measurement; `revenge_trade`
frozen by decision; `overtrading_burst` **deferred** and still live.

**Known bias in all prior evidence:** the reference book is one intraday
long-options buyer — **911 LONG vs 1 SHORT**, 89% CE/PE, 4 futures, 19 equity, no
MTF. Every threshold and every measurement to date comes from that book. Short
options, futures, equity, MTF, overnight and multi-leg strategies are therefore
**untested rather than deliberately handled**, and this audit must not confuse
the two.

---

## Work division

Five parallel read-only investigations, scoped so they do not overlap.

| # | scope | brief items | status |
|---|---|---|---|
| A | Position lifecycle, average price & P&L semantics, order intent vs execution | 1, 2, 14 | running |
| B | Long/short options, futures vs options, capital & margin semantics | 7, 8, 12 | running |
| C | Hedge recognition & adjustment, strategy geometry, cross-underlying | 3, 4, 6, 10 | running |
| D | Expiry & rollover, time horizon, trader archetypes | 5, 13, archetypes | running |
| E | MTF, portfolio exposure, data failure states, multi-account | 9, 11, 15, 16 | running |

---

## Coverage matrix

*Populated as findings arrive. Empty status = not yet assessed.*

### 1. Position lifecycle (A)

| scenario | status | detector / service affected | note |
|---|---|---|---|
| open | | | |
| partial fill | | | |
| partial exit | | | |
| multiple fills | | | |
| add to existing position | | | |
| reduce position | | | |
| completely close | | | |
| reopen same instrument | | | |
| close and reopen later | | | |
| reverse LONG → SHORT | | | |
| reverse SHORT → LONG | | | |
| simultaneous orders netting to zero | | | |
| cancelled / rejected orders | | | |
| pending orders | | | |
| stop-loss execution | | | |
| target execution | | | |
| **new position vs another fill of the same position** | | | the crux |

### 2. Average price & P&L (A)

| scenario | status | detector / service affected | note |
|---|---|---|---|
| weighted average entry after adds | | | |
| total quantity after adds/exits | | | |
| realized P&L | | | |
| unrealized P&L | | | |
| remaining quantity | | | |
| adverse excursion | | | |
| position-level P&L | | | |
| **adding to a loser shrinking a loss %** | | | the Pattern 8 class |

### 3. Long / short & instrument type (B)

| scenario | status | detector / service affected | note |
|---|---|---|---|
| long call / long put | | | |
| **short call / short put (writer)** | | | |
| long / short futures | | | |
| long / short equity | | | |
| premium-movement logic on a writer | | | |
| option logic applied to futures | | | |
| contract multiplier | | | |
| mark-to-market | | | |

### 4. Capital & margin semantics (B)

| question | status | note |
|---|---|---|
| does "risk" mean notional, capital-at-risk, margin blocked, or potential loss? | | |
| is one denominator used across non-comparable products? | | |

### 5. Hedges & strategy geometry (C)

| scenario | status | detector / service affected | note |
|---|---|---|---|
| protective hedge (FUT long + PE long) | | | |
| neutral structure (CE long + PE long) | | | |
| spread (buy 25000 CE + sell 25200 CE) | | | |
| **does any code assume opposite direction = hedge?** | | | |
| hedge adjustment sequence | | | |
| straddle / strangle | | | |
| bull/bear call/put spreads | | | |
| iron condor / butterfly | | | |
| calendar / diagonal / ratio | | | |
| covered call / protective put / collar | | | |
| simultaneous / overlapping legs | | | |
| strategy suppression reliability | | | |
| cross-underlying hedge | | | |

### 6. Expiry, time horizon & archetypes (D)

| scenario | status | detector / service affected | note |
|---|---|---|---|
| same strike, different expiry | | | |
| same underlying, different expiry | | | |
| futures rollover | | | |
| rolling a spread | | | |
| expiry-day adjustment | | | |
| intraday vs overnight | | | |
| multi-day position | | | |
| time windows assuming intraday | | | |
| archetype false positives | | | |

### 7. MTF, exposure, data failure, multi-account (E)

| scenario | status | detector / service affected | note |
|---|---|---|---|
| MTF represented distinctly from equity / F&O | | | |
| MTF overnight, adjustments, square-off | | | |
| gross vs net exposure | | | |
| hedge-adjusted exposure | | | |
| **missing/stale data readable as behaviour** | | | hard principle |
| broker disconnect / reconnect / restart | | | |
| duplicate or out-of-order fills | | | |
| account vs user scoping | | | |

---

## Findings

*Populated as agents report.*

---

## Scenarios the brief did not list

*Added here as they are discovered.*

---

## Conclusions

*To be written once all five reports are in.*

- Overall coverage assessment — **pending**
- Highest-priority architectural gaps — **pending**
- Pattern reviews to revisit — **pending**
- Safe now vs needs more data — **pending**
- Fix anything before Pattern 12? — **pending**
