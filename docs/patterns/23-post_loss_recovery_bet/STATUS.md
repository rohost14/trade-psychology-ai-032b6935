# 23 — `post_loss_recovery_bet` · **KEEP**

v1.1.0 · exit-triggered · trade-scoped · `risk`/`alerting` · notification level 2

## What it reports
One materially oversized bet placed after losses — the single swing, as
distinct from `martingale_behaviour`'s doubling progression. The two sit in the
same consolidation family ("sizing after losses"), where martingale wins
because it makes the stronger claim.

## Changed since the review
**Temporal relation (2026-08-30).** It reads
`EngineContext.concluded_before_entry` — losses that CONCLUDED before this
position was entered — rather than any trade that merely occurred earlier in
the session. A causal claim requires the loss to have finished before the
decision it is supposed to explain.

**Suppression (2026-09-02).** One of two members of `_STRATEGY_SUPPRESSED`.
Inside a recognised multi-leg structure the sizing is a property of the
structure, not a recovery bet, so the subject does not exist. Suppression is
notification-layer only: the `BehaviorEvent` is still written with
`evidence["_suppressed"]`.

## Tests
`tests/test_temporal_contract.py`, `tests/test_strategy_suppression.py`
