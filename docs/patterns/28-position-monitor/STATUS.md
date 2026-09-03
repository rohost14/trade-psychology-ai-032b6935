# 28 — position monitor · **BOTH SUBJECTS RETIRED**

The 60-second open-position beat still runs; the two detectors this directory
reviewed do not.

## `holding_loser` · RETIRED 2026-09-02
A snapshot plus a stopwatch — `unrealized < 0` AND `>= 0.5%` AND `>= 30 min` —
with nothing in it observing the loss CHANGING. The winner/loser hold
substitute failed the persistence test: ratio 0.62 in the first half of the
book against 2.54 in the second, 1.04 intraday at shuffle p = 0.343.

NOT REPLACED. Reviving it needs a stored mark-to-market series, which does not
exist and cannot be reconstructed. The hold comparison was deliberately not
promoted to analytics because it fails the same test.
`tests/test_holding_loser_retired.py`

## `overexposure` · RETIRED 2026-09-02
Retired as a NAME, not a guard. The alias was already dead: `_overexposure_task`
emits `constitution_violation`/`max_trade_risk`, gates on the trader's DECLARED
limit and abstains when the capital requirement is unavailable. The entry-time
check is untouched and still runs.

## What still runs here
The position-monitor beat, the live premium-loss check
(`live_checks.evaluate_live_premium_loss`), and the entry-time exposure check
that emits `constitution_violation`.

`portfolio_concentration_service.py` was archived 2026-09-03 — its detector was
retired 2026-09-01 and its only importers were already archived.
