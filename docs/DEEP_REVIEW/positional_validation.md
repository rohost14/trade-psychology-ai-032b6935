> **STATUS — audit STARTED 28 Aug 2026, IN PROGRESS.**
> Working document and live status: [`TRADING_SEMANTICS_AUDIT.md`](TRADING_SEMANTICS_AUDIT.md).
> Five parallel read-only investigations are running, scoped A–E against the
> numbered items below. This brief is the source of requirements and is not
> edited except for this status block.
>
> | # | scope | brief items covered | status |
> |---|---|---|---|
> | A | position lifecycle, average price & P&L, order intent vs execution | 1, 2, 14 | running |
> | B | long/short options, futures vs options, capital & margin | 7, 8, 12 | running |
> | C | hedge recognition & adjustment, strategy geometry, cross-underlying | 3, 4, 6, 10 | running |
> | D | expiry & rollover, time horizon, trader archetypes | 5, 13, archetypes | running |
> | E | MTF, portfolio exposure, data failure, multi-account | 9, 11, 15, 16 | running |
>
> No code changes are being made. Findings only.

---

Before Pattern 12, pause pattern reviews and perform a cross-pattern Position/Strategy/Hedging Coverage Audit.

Do not change code.
Think from the perspective of many different traders, not just the current dataset. Verify whether the current engine can correctly interpret:
Audit whether the engine correctly understands and separates:

* long/short equity
* long/short futures
* long/short calls and puts
* CE↔PE reversals
* partial exits, flips, averaging and pyramiding
* protective hedges: FUT + PUT, FUT short + CALL, stock + option
* straddles/strangles
* spreads, calendars, ratio spreads and multi-leg strategies
* simultaneous/overlapping legs
* hedge entry/removal/adjustment
* intraday vs overnight positions
* MTF positions and MTF + hedges

For each scenario, determine:

1. How the current position model represents it.
2. Whether detectors can distinguish a legitimate strategy/hedge from potentially harmful behaviour.
3. Which existing patterns could false-positive.
4. Whether strategy suppression/grouping handles it correctly.
5. What is missing or ambiguous.
6. Whether MTF risk/exposure is represented correctly.

Pay special attention to CE→PE: it must NOT automatically mean directional instability, and hedge construction must not be mistaken for behavioural deterioration.

Also identify any cases I missed.

Output a coverage matrix with PASS / GAP / RISK for every scenario, the highest-priority architectural gaps, and which pattern reviews should be revisited because of those gaps.

No code changes. Stop after the audit.


Things I think we should add to the audit
1. Position lifecycle — very important

Not just "buy → sell."

Test:

open
partial fill
partial exit
multiple fills
add to existing position
reduce position
completely close
reopen same instrument
close and reopen later
reverse from long → short
reverse from short → long
simultaneous orders that result in net zero
cancelled/rejected orders
pending orders
stop-loss execution
target execution

The engine must distinguish a new position from another fill belonging to the same position.

2. Average price changes

This is a big one given what happened with Pattern 8.

Example:

Buy 100 CE at ₹100
Add 100 at ₹60

The position isn't simply "₹100 entry + another trade."

The engine needs to understand:

weighted average entry
total quantity
realized P&L
unrealized P&L
remaining quantity
adverse excursion
position-level P&L

Otherwise adding to a loser can accidentally make a premium-loss percentage look smaller, exactly the kind of semantic problem we just discovered.

3. Hedge recognition

We should explicitly test three states, not just "hedged/not hedged":

A. Protective hedge

Reliance FUT long + Reliance PE long

B. Neutral/offsetting structure

CE long + PE long
CE short + PE short

C. Spread

Buy 25000 CE + sell 25200 CE

Those are not equivalent.

And the engine should not assume:

opposite direction = hedge

A hedge is a relationship between positions, not merely two opposite trades.

4. Hedge adjustment

This is easy to miss.

Example:

Long Reliance FUT
→ buy PE
→ add more FUT
→ add more PE
→ close half PE
→ close FUT

That trader is actively managing a strategy.

A sequence detector looking only at individual trades could call this:

overtrading
direction flipping
adding to position
rapid re-entry
excessive trading

when it's actually strategy adjustment.

This deserves explicit testing.

5. Expiry/rollover

A trader may:

NIFTY FUT near expiry → close → next-month FUT

or

current-month CE → next-month CE

That's not necessarily re-entry or loss-chasing.

Also:

same strike, different expiry
same underlying, different expiry
rolling a spread
closing one expiry while opening another
expiry-day adjustments

NSE's current contract structure explicitly distinguishes expiry and trading cycles, so expiry cannot just be treated as another timestamp attribute.

6. Options strategy geometry

I'd specifically test:

straddle
strangle
bull call spread
bear call spread
bull put spread
bear put spread
iron condor
iron butterfly
calendar spread
diagonal spread
ratio spread
covered call
protective put
collar

But don't assume the engine needs to identify every named strategy.

The audit question should be:

"If this structure occurs, which existing detectors misunderstand it?"

That's much more valuable.

7. Short-option sellers

This is particularly important because Pattern 8 exposed a general issue.

For a long option, premium falling is generally adverse.

For a short option, premium falling can be favourable.

So a generic:

"premium dropped 60%"

means completely different things depending on whether the trader bought or sold the option.

NSE explicitly distinguishes an option buyer from an option writer/short option position.

We should audit every detector that uses:

premium movement
P&L %
loss %
position size
adverse movement

against long vs short.

8. Futures are not options

Don't let the engine use option-style logic on futures.

For futures:

no premium-decay concept
P&L is driven differently
long/short direction matters
contract multiplier matters
mark-to-market matters
rollover matters

So Pattern 8-style "percentage of premium lost" cannot simply generalize to futures.

9. MTF

Definitely include:

cash equity without MTF
MTF long
MTF position increased
MTF position reduced
MTF overnight
MTF + protective option
MTF position converted/closed
available margin vs deployed capital
forced liquidation / broker square-off if the data can represent it

And importantly:

MTF should not be treated as an F&O position.

It's a financing/leverage context around an equity position.

10. Cross-underlying hedges

Don't restrict relationship detection to identical symbols.

Examples:

Reliance + NIFTY hedge
Bank stock + BANKNIFTY hedge
portfolio equity + index put
sector exposure + index hedge

The engine probably cannot reliably infer all of these from trades alone.

That's okay.

The audit should explicitly classify:

Recognizable / partially recognizable / impossible from current data.

Do not pretend correlation-based hedging can be inferred confidently from trade records.

11. Portfolio-level exposure

This is probably the biggest thing we haven't discussed enough.

A trader might have:

Reliance long ₹5L
TCS long ₹3L
NIFTY PE ₹2L

Individual trades look risky.

Portfolio net exposure may actually be very different.

We should ask whether the engine understands:

gross exposure
net directional exposure
underlying exposure
sector exposure
correlated exposure
hedge-adjusted exposure

But don't build this just because it sounds good. First determine whether the available data supports it reliably.

12. Capital / margin semantics

We should audit whether "risk" currently means:

trade notional

or

capital actually at risk

or

margin blocked

or

potential loss.

Those are different.

This matters enormously for:

futures
short options
spreads
MTF
hedged positions.

NSE's derivatives framework itself uses different margin/contract mechanics depending on the product, so one universal "position size" denominator is dangerous.

13. Time horizon

A trader can be:

scalper
intraday trader
positional trader
swing trader
expiry trader
overnight trader
hedger

A 30-minute gap can mean something completely different for each.

So before interpreting:

"rapid re-entry"

or

"long holding"

or

"overtrading"

we need to know whether the detector is implicitly assuming an intraday style.

14. Order intent vs execution

This is another important one.

We should distinguish where possible:

Order placed → partially filled → fully filled → cancelled/rejected

versus only looking at completed trades.

Otherwise:

"trader repeatedly entered"

might actually be:

placed order → didn't fill → modified → cancelled → eventually filled.

That isn't the same behavioural sequence.

This is particularly relevant because we've already encountered the TRIGGER PENDING issue.

15. Data failure states

For a real-time product, audit:

stale LTP
missing LTP
delayed tick
broker disconnect
websocket reconnect
position sync delay
duplicate fills
out-of-order events
app restart
Redis restart
broker API outage
market closed
partial day/session

Never interpret missing data as trader behaviour.

16. Multi-account / multi-broker

Eventually a trader may connect:

Zerodha
Upstox
Angel
multiple Zerodha accounts

We need to know whether behaviour is:

account-level, broker-level, or user-level.

Otherwise a trader could appear to have:

"rapid re-entry"

when they actually closed in Account A and opened the hedge in Account B.

One more thing: trader archetypes

I'd explicitly test the engine against these hypothetical users:

Pure intraday directional trader
Scalper
Futures trader
Long-options trader
Short-options seller
Options spread trader
Hedger
Expiry trader
Swing/positional trader
MTF equity trader
Algorithmic/systematic trader
High-frequency/manual rapid trader
Averaging/pyramiding trader
Market-neutral trader
Portfolio hedger

The goal isn't to make 15 different engines.

The goal is:

Would the same detector incorrectly label a legitimate action for one archetype as harmful behaviour?

That's the real test.

And there is one especially important principle

Given what we've discovered in Patterns 6–11, I'd add this to the audit:

Before any detector is allowed to make a behavioural claim, establish that the underlying trading event is correctly classified at the position/strategy level.

Because:

CE → PE could be FOMO, a genuine reversal, a hedge, a spread adjustment, or simply closing one leg and opening another.

Adding to a losing position could be martingale, averaging, pyramiding, or hedge construction.

Increasing size could be reckless risk escalation or simply the next leg of a multi-leg strategy.

Premium falling 60% could be catastrophic for a long option and favourable for a short option.

That's exactly where a behavioural product can become dangerously wrong.

Also, this isn't just theoretical: SEBI's latest published research continues to show substantial losses among individual F&O traders, so getting the behavioural interpretation right matters much more than maximizing the number of alerts.

So yes: add this entire coverage audit before Pattern 12. I would call it "Trading Semantics & Strategy Coverage Audit", and I would make Claude produce a matrix of PASS / GAP / UNSUPPORTED / FALSE-POSITIVE RISK rather than allowing it to make assumptions.


Be especially strict about these:

CE→PE is NOT automatically direction instability. It can be a genuine reversal, hedge, spread adjustment, or strategy construction.
Opposite positions are NOT automatically a hedge. Determine whether the available data is sufficient to establish a hedge relationship.
Adding to a losing position can be averaging, pyramiding, strategy adjustment or harmful escalation.
Premium loss means different things for long vs short options.
Position-level P&L, average entry, realized/unrealized P&L and remaining quantity must remain correct after multiple fills/adds/exits.
MTF must not be treated as ordinary cash equity or F&O.
Never infer trader behaviour from missing/ambiguous data.

For EVERY scenario, classify:

PASS — correctly represented and safely handled
GAP — something important is missing
FALSE-POSITIVE RISK — existing detector could misclassify legitimate behaviour
UNSUPPORTED — current data cannot reliably determine it

For every GAP/FALSE-POSITIVE RISK, identify exactly which detector/service/pattern is affected.

Also identify scenarios I have missed.

Do not propose thresholds or implement anything yet. Do not assume a strategy can be identified if the available data cannot prove it.

Finish with:

Overall coverage assessment
Highest-priority architectural gaps
Patterns that may need to be revisited because of these findings
What can safely be handled now vs what requires additional data
Whether we should fix anything before continuing Pattern 12

No code changes. Stop after the audit and wait for approval.