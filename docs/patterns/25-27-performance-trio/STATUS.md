# 25–27 — performance trio · **1 LIVE, 2 RETIRED**

Only `win_rate_collapse` survives. This file covers it; the two retirements are
carried by their own suites.

## 26 — `win_rate_collapse` · KEEP
v1.0.0 · exit-triggered · **session-scoped** · `performance`/**`analytics`** · notification level 0

Today's win rate against the trader's own baseline, at a severe deterioration
tier only, with a minimum of 8 trades and a baseline confidence floor.

**Changed 2026-09-03.** It declared `trigger="session"`, which the engine
ignored — the exit loop skipped `entry` and ran everything else, so it has
always run on the exit path. `trigger` was doing two jobs: when the engine
dispatches, and what the detector's subject is. Now `trigger="exit"` (where it
actually runs) plus `scope="session"` (what it judges). No behaviour change and
no version bump.

**It cannot reach a trader, deliberately.** `severity="info"`,
`disposition=analytics`, notification level 0. As of 2026-09-03 that is
enforced at both ends rather than being a coincidence of hardcoded severity.
Whether the performance domain should ever be notifiable is an open product
question and is not answered here.

## 25 — `time_of_day_bias` · RETIRED 2026-09-01
Its learned danger hours did not survive into a second time period. Nightly
learning and storage are deliberately KEPT; only the trader-facing
interpretation is gone. `tests/test_time_of_day_bias_retired.py`

## 27 — `strategy_breakdown` · RETIRED 2026-09-02
Required a win-rate collapse AND a profit-factor collapse together, and the
profit-factor half never bound: 4 firings, the identical set to
`win_rate_collapse`, zero unique. A second name for one finding.
`tests/test_strategy_breakdown_retired.py`
