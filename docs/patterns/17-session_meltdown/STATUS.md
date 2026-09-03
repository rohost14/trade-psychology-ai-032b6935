# 17 — `session_meltdown` · **MODIFIED**

v1.0.0 · exit-triggered · trade-scoped · `risk`/`alerting` · notification level 4 · **guardian eligible**

## What it reports
A session's loss measured against the trader's own declared `daily_loss_limit`,
at 40% / 75% of it.

## Changed since the review
It is one of only two detectors whose behaviour moves with the money rules —
`daily_loss_limit` became opt-in and is `None` until the trader sets it, so
this is silent for a trader who has declared nothing. Twelve of the fourteen
detectors are byte-identical across rule configurations; this and
`constitution_violation` are the exceptions.

## Still open, and worth knowing
This is the loudest detector in the system: notification level 4 and guardian
eligible, meaning it can reach an accountability partner. The two constants
that drive it (40 / 75) carry no classification and no source, which matters
more here than anywhere else because of where its output can go.

Whether a capital-derived limit should be allowed to reach a named third party
at all is an open product question, and today it can. Parked by decision — not
to be changed without asking.

The denominator question is also unresolved: `account_risk` versus Kite's
`opening_balance`. Swapping it moves every firing count.

## Tests
`tests/test_engine_hygiene.py`, `tests/test_money_rules_independence.py`
