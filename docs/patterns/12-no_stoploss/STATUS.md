# 12 — `no_stoploss` · **MODIFIED**

v1.0.0 · exit-triggered · trade-scoped · `risk`/`alerting` · notification level 2

## What it reports
How far a losing position was allowed to run before it was closed, as a
percentage of the capital that position actually put at risk. Nothing more.

## Changed since the review
The review describes the old behaviour twice over.

**The claim (2026-08-29).** It used to end "No stop-loss order detected on this
trade", derived from the exit fill's order type. That asserted the absence of
something it had not looked at: the exit fill answers "was this exit executed
by a stop", not "did the trader have a resting stop". A trader holding a
resting SL who exits manually first shows MKT and would have been told they had
none — the inverse of the truth. The exit mechanism is now mentioned only when
it was actually observed.

**The denominator (F4, 2026-09-03).** It divided by premium paid for every
option regardless of direction. Correct for a long option, wrong way round for
a short one, where premium received is the maximum profit rather than the
capital at risk — the semantic baseline recorded "2900% loss of premium" at
danger severity. A short option now uses SPAN margin on strike x quantity via
`estimate_capital_at_risk`. The long path is byte-identical.

Two abstentions were added, both because a wrong confident answer is worse than
no answer: an unreadable strike (the fallback is known to be ~200x too small),
and an unknown direction (the two denominators differ by ~200x and neither
guess is defensible).

## Still open
Whether a resting stop EXISTED and was cancelled needs the order book, which
Kite provides and no detector reads. That is the only thing that would turn
this from a factual loss/exit signal into a genuine "a stop was available and
was not used" behavioural one. Not built.

## Tests
`tests/test_no_stoploss_pattern12.py`, `tests/test_no_stoploss_denominator.py`
