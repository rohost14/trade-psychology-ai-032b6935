# 99 — `revenge_trade` · **FROZEN**

v3.0.0 · exit-triggered · trade-scoped · `emotional`/`alerting` · notification level 2

## Status
Frozen by explicit decision. Not to be tuned, retired or re-scoped without
being unfrozen first.

## Why
The research pass closed with the verdict DATA-CAPTURE-FIRST. AUC 0.482 — no
combination of available features separates a revenge trade from any other
re-entry. The apparent loss-run signal was chance, and the "mirror" reading of
it was retracted. The real finding was an order-history gap: every non-COMPLETE
order event is discarded at ingestion, so the data that would settle the
question is not being kept.

New data unblocks it. Nothing else does.

## Changes made while frozen
Exactly two, both forced rather than chosen.

**Temporal relation (2026-08-30).** It reads `concluded_before_entry`, the
CONCLUDED relation. This was a correctness fix: a causal claim must rest on a
loss that finished before the entry it explains. Nine of 32 firings had rested
on a loss that concluded after the entry they explained.

**Cooldown bump removed (2026-09-02).** A declared-cooldown breach used to
raise severity to at least caution. `cooldown_after_loss` was removed as a user
input, so `user_cooldown_min` no longer resolves and the branch could only have
been dead. `_RT_MATRIX` is untouched and nothing moves on the reference book.

## Parked, and touching either would silence it
Capital-relative rupee floors (`91975d4`, LIVE) would silence this detector at
capital >= Rs 2L. The percentile-of-own-losses alternative is the same
decision. Both parked — do not touch without asking.

## Tests
`tests/test_temporal_contract.py`, `tests/test_behavior_engine.py`
