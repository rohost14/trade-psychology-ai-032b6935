# 13 — `rapid_reentry` · **KEEP**

v2.0.0 · exit-triggered · trade-scoped · `emotional`/**`analytics`** · notification level 0

## What it reports
Re-entering the same instrument within minutes of closing it. Evidence only.

## Status
Unchanged in behaviour. It emits `severity="info"`, writes `BehaviorEvent` rows
and never raises a `RiskAlert`.

That is deliberate, and as of 2026-09-03 it is enforced rather than incidental.
The alert gate used to test severity alone, so the rule held only because this
detector happened to hardcode `info`; the gate now refuses to alert on any
`disposition="analytics"` detector whatever severity it carries, and the
registry rejects an analytics spec that declares a notification channel.

## Known consequence
No trader-facing surface reads it today. `danger_zone`'s CAUTION path for this
pattern is therefore unreachable. Recorded as a design consequence of the
analytics disposition, not a defect — evidence does not entitle a detector to
interrupt anyone.

It is one of two members of `_STRATEGY_SUPPRESSED`: inside a recognised
multi-leg structure the re-entry is a leg, not a decision, so the subject does
not exist.

## Tests
`tests/test_analytics_disposition_contract.py`,
`tests/test_strategy_suppression.py`
