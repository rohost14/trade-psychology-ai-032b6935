# 24 — `constitution_violation` · **KEEP**

v1.0.0 · exit-triggered · trade-scoped · `discipline`/`alerting` · notification level 4 · **guardian eligible**

## What it reports
A breach of a limit the trader declared themselves. Nothing is inferred: every
rule it checks is a number the trader typed. It is the largest single source of
alerts in the system.

## Changed since the review
**Counting unit (2026-09-02).** Its `daily_trades` rule counted CompletedTrade
rows, which counts legs, while `daily_overtrading` counted structures. Two
detectors, one declared number, two different units — identical on the
reference book, guaranteed to disagree for a multi-leg trader. Both now count
structures.

**`max_trade_risk` absorbed exposure (2026-09-01).** `excess_exposure`,
`portfolio_concentration` and the `overexposure` alias were all retired, and
single-position exposure is now solely a breach of the trader's own declared
`max_position_size` through this detector. The entry-time arm emits the same
pattern type and rule, so `_pattern_dedup_key` collapses entry and exit.

**Undeclared rules resolve to None (2026-09-01).** `sl_percent_options` and
`sl_percent_futures` no longer invent 50.0 / 1.0 as `Source.FACT`, so a trader
who set nothing is no longer told "You set your options exit at 50% of
premium".

## Still open
Its cooldown rule spells the CONCLUDED temporal relation as an inline `<=`
rather than using `concluded_before_entry`. The declared-cooldown branch itself
was removed 2026-09-02 with `cooldown_after_loss` as a user input, so this is
tidiness rather than a live defect.

## Tests
`tests/test_threshold_contract.py`, `tests/test_engine_hygiene.py`
