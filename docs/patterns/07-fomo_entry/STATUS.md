# Pattern #7 — `fomo_entry` · **COMPLETE**

27 Aug 2026. Detector `1.0.0` → `2.0.0`. Evidence in `fomo_entry_review.md`.
This also closes the mandated review of `fomo_symbols_at_open`.

---

## Current logic

`behavior_engine.py`, `_detect_fomo_entry`.

```
guard      instrument_type in (CE, PE, FUT)      — equity never considered
window     trailing `fomo_window_min` (30) from this entry, over session_trades
count      distinct parse_symbol(...).underlying, INCLUDING the current trade
threshold  fomo_symbols_in_window (3) — ONE value, every context
fire       count >= threshold  ->  severity "caution"
```

The context — expiry day, market open, pre-close — is still computed from the
symbol's own expiry and the instrument's own exchange hours, and is still
**reported** on the evidence as `context_note` / `is_expiry_day`. **It no longer
changes the count.**

## What changed

| | before | after |
|---|---|---|
| thresholds | 4 — expiry **4**, open **2**, pre-close **3**, general 3 | **one: `fomo_symbols_in_window` (3)** |
| `fomo_symbols_at_open` | 2 | **deleted** — the mandatory review's outcome |
| `fomo_symbols_at_close` | 3 | **deleted** — unreachable |
| `fomo_expiry_day_symbols` | 4 | **deleted** — unreachable |
| message | *"Scattering across underlyings indicates FOMO — not a focused plan."* | *"3 different underlyings entered within 30 min (market open): …"* |
| registry copy | *"…usually chasing movement rather than acting on a view."* | *"Breadth is worth seeing on its own. It is not evidence about why the trades were taken."* |
| `fomo_symbols_in_window` kind | `PERSONAL_BASELINE`, `Source.HISTORY` | **`FALLBACK`**, no source, no metric |
| version | 1.0.0 | 2.0.0 |

**Unchanged, deliberately:** `fomo_window_min` (30), `fomo_symbols_in_window`
(3), severity `caution`, disposition `alerting`, `is_expiry_day`, the
per-exchange session bounds, and the underlying-counting rule.

## Why

**Two thresholds could not fire.** Across 142 expiry-day entries the maximum
breadth ever reached was **3** against a threshold of **4**. Across 50 pre-close
entries the maximum was **2** against a threshold of **3**. A threshold above the
highest value its own branch has ever produced is not conservative; it is
absent. Both were removed rather than replaced, because replacing them means
inventing a number this book cannot justify.

**The open threshold of 2 produced 39% of all output.** 29 of the detector's 74
firings, at 3.6:1 against the general threshold, on a state — two underlyings
inside half an hour — occurring in 20% of all entries. It sat in
`safety_bounds.MANDATORY_REVIEW` flagged for *"measured ~4:1 over-firing"*; that
is now measured, confirmed and resolved.

**The clustering claim is at chance.** A permutation null keeping each session's
exact entry times **and** its exact multiset of instruments, permuting only which
was traded when — breadth and activity held constant, deliberate clustering
destroyed — run through the real detector over 200 permutations per session:

| | observed | chance | ratio |
|---|---|---|---|
| firings | **74** | 78.4 | **0.94** |
| market-open branch | 37 | 36.2 | **1.02** |

The trader's pairing of instrument to moment carries no information, so the
alert cannot say the instruments were chased *together*. And the flagged trades
**win more often than this trader's average** — 45.9% against 39.9%, with the
general branch at 51.4% — so it cannot say they were bad either.

## Measured effect (189 sessions, 912 positions)

| | before | after |
|---|---|---|
| detections | 74 | **46** |
| sessions | 41 (22%) | **26 (14%)** |
| by branch | general 37 · open 37 · expiry 0 · close 0 | general 37 · open 8 · **expiry 1** · close 0 |
| firings at 2 underlyings | 29 | **0** |

The 29 open-branch firings at two underlyings are gone. The expiry branch fires
**once** now that it uses a reachable threshold.

## Tests

`tests/test_fomo_entry.py` — **64 tests, the detector's first.** All contexts on
the general threshold (parametrised); open silent at 2; expiry and pre-close
falling through; strikes of one underlying counting once; the current trade
included; the window edge; equity excluded; the threshold still configurable;
the three deleted keys gone from both defaults and specs; the registry no longer
claiming a personalisation it cannot perform; no fomo baseline metric produced
by any producer; severity, disposition and purity unchanged; and per-exchange
session bounds still honoured (NSE vs MCX).

**The copy tests assert the CLAIM, not the vocabulary.** 19 intent phrases —
chasing, impulse, panic, "focused plan", "indicates fomo", "fear of missing out"
and so on — are checked against both the registry copy and the live message.
The bare word `fomo` is **not** banned: `fomo_entry` is the pattern_type, stored
rows carry it and the registry is keyed on it, so a separate test allows the
token as an identifier and forbids it as a claim. Verified to fail when the old
copy is reintroduced, rather than passing vacuously.

`test_threshold_registry.py` — one test adjusted with its subject. It asserted
`fomo_symbols_at_open` carries `review_required`; that review is now complete
and the spec is gone. Follows the precedent already recorded in that test for
`revenge_window_danger_min`: the spec goes, the `MANDATORY_REVIEW` entry stays so
the reason survives. Strengthened to check all three retired constants keep
their recorded reasons and are absent from defaults and specs.

**Full backend 1,342 passed. Frontend typecheck clean, 102 tests pass.**

## Limitations, recorded not closed

1. **`fomo_window_min` (30) and `fomo_symbols_in_window` (3) remain unsourced.**
   This review established which constants were wrong, not what the right ones
   are. Both are marked as hypotheses in `trading_defaults.py`.
2. **No personalisation exists.** `fomo_underlyings_per_window_p75` is produced
   by nothing; the classification now says `FALLBACK` rather than claiming
   otherwise. A test fails if any producer starts emitting it, so the
   classification cannot silently go stale.
3. **The three pace/breadth detectors share no consolidation family** —
   `fomo_entry`, `overtrading_burst`, `daily_overtrading`, overlapping 62% on
   this book. Same finding as Pattern 5 §5, now with a second detector attached.
   **For the families review.**
4. **An `alerting` detector with no danger tier**, so it can never reach a
   notification. Left as-is by instruction; worth deciding alongside the
   disposition question.
5. **Equity is excluded by design**, so breadth into cash stocks is invisible.
6. **No replay confirmation.** Backed by 1,342 tests and the in-process
   measurement above, not by a harness replay — the same gap recorded for
   Pattern 6 in `ENGINE_BACKLOG` M-1, and blocked by the same stopped Memurai
   service.
