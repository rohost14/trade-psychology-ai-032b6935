# 2 — `adding_to_adverse_position` · **COMPLETE**

v2.0.0 · **entry-triggered — fires on the `INCREASE` fill** · `risk`/`alerting`

## What it reports
An **open** position moved against the trader and they increased exposure in it.
Size does **not** need to increase — 95 of 96 real adverse adds were *smaller*
than the position held, median 0.67×.

## Current logic
1. Reads the position's **fill sequence** from `PositionLedger`
   (`ctx.position_fills`), gated on `num_entries > 1` — skips ~90% of trades.
2. An add is adverse when `(avg_entry − fill_price) / avg_entry × direction > 0`.
   Direction-symmetric: a long filling lower and a short filling higher are the
   same event.
3. Exposure via `instrument_risk.risk_basis`; **abstains** on spreads.
4. Severity — two ordinal axes, no score:

| | add < held | add ≥ held |
|---|---|---|
| 1 adverse add | info | caution |
| 2 | caution | danger |
| 3+ | danger | critical |

5. Dedup: **one alert per severity level per position epoch**
   (`OPEN`/`FLIP` timestamp). Close → re-entry is a new episode.

## Constants
**None.** Both axes are definitional — "more than once", and "at least as much
again" (the identity 1.0). No percentage threshold: measured adverse depth is
one smooth mode, and the median move when adding is 10.6% against vs 10.4% in
favour, so magnitude carries no information — only the sign.

## Replay (corrected 203-session baseline)
**99 alerts / 56 days** · caution 69 · danger 21 · critical 9
64 firings verified: **4/4 checks PASS**. 57 episodes, never more than 2 firings
each. Dedup verified in the real path: ASIANPAINT caution→danger, NIFTY
caution→danger→critical, a second symbol correctly its own episode.

## Limitations
- **Cross-strike sequences are out of scope** — 53 occurrences / 30 days,
  deliberately excluded; strike progression alone is not evidence. Separate
  research.
- Short / futures / equity proven **synthetically only**.
- Per-episode dedup can't be audited from the replay sidecar (stores no
  details); verified by tests and direct inspection.

Detail: `adding_to_adverse_position_contract.md` (+ `_evidence`, `_validation`,
`_datapath`)
