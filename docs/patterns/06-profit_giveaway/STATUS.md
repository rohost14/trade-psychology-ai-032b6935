# Pattern #6 — `profit_giveaway` · **STATUS**

27 Aug 2026. Review approved with eight decisions; all eight implemented.
Detector `1.0.0` → `2.0.0`. Evidence in `profit_giveaway_review.md`.

---

## Current logic

`behavior_engine.py`, `_detect_profit_giveaway`.

```
peak    = facts.peak_pnl          # high-water mark of the REALIZED curve
current = facts.pnl
worst   = facts.max_drawdown      # deepest peak-to-trough today; a running maximum

if peak <= 0:                      -> nothing was built
erosion = peak - current
if erosion < min_erosion:          -> not worth naming at this trader's scale
                                      (min_erosion rises to their median losing trade)

went_red = the running total was below zero at any point AFTER the peak   # sticky

OCCASIONS   crossed_now   = current < 0                       # no min_peak gate
            past_pct_line = peak >= min_peak and erosion/peak >= caution_pct

SEVERITY    danger if went_red else caution                   # cannot fall within a session
```

Occasion and loudness are now separate questions. `went_red` decides **severity
only** — it does not create a firing occasion, so a session that flipped and
recovered speaks again only when the percentage line is crossed, and then at the
severity it already reached.

## What changed

| | before | after |
|---|---|---|
| green→red gate | `min_peak` **and** `min_erosion` | **`min_erosion` only** |
| erosion tiers | caution 50% / **danger 70%** | **one severity**; `profit_giveaway_danger_pct` deleted |
| re-arm metric | `erosion_pct` — unbounded, oscillates | **`worst_giveaway`** = `facts.max_drawdown`, a running maximum |
| severity within a session | could fall (danger → caution → danger) | **monotonic** |
| the `erosion_pct >= 1.0` literal | inline, unkeyed, untested | **deleted** — unreachable given a positive peak and negative current |
| copy | "the trade after a peak decides whether the day is kept" | reports the moment; forecasts nothing |
| dedup comment | claimed 24h and once-per-session | corrected: 2h with a deliberate re-arm |
| `consumes` | omitted `facts` | includes `facts` |

## Measured effect (189 sessions, 912 positions)

| | before | after |
|---|---|---|
| detections | 55 | **135** |
| **alerts after dedup** | **~38** | **~95** |
| sessions with an alert | 20 (11%) | **48 (25%)** |
| severity split | 41 danger / 14 caution | 107 danger / 28 caution |
| alerts per affected day | mean 1.90, max 4 | **mean 1.98, max 5** |
| sessions where severity fell | **2 of 20** | **0** |
| sessions where the re-arm metric fell | not tracked | **0** (guaranteed by definition) |
| firings on days closing green | 24 of 55 (10 of 20 days) | 35 of 135 (17 of 48 days) |

### The gate removal, measured directly

| | sessions | closing P&L |
|---|---|---|
| green→red sessions in the book | 33 | −₹95,963 |
| of which **previously silenced** by `min_peak` | 23 | −₹66,212 |
| **now covered** | **21 of 23** | **−₹65,200** |
| previously covered, still covered | 10 of 10 | — |

The two still silent are correctly excluded by `min_erosion`: 2025-07-25 (peak
₹141 → −₹90, a ₹231 giveback) and 2025-12-03 (peak ₹382 → −₹922), the latter
because the self-relative floor had risen above ₹1,304 for that session. **No
regression on anything that fired before.**

> **CORRECTION, same day.** The alert counts in this section say **~95**. The
> correct figure is **100**: that simulation modelled the first fire, the
> severity escalation and the metric re-arm but omitted the **2-hour elapsed
> window**, which does expire inside a 09:15-15:30 session. See
> `episode_dedup_analysis.md`, which models `_is_deduped_full` completely.
>
> **The conclusion below is also superseded.** The repeat alerts are NOT
> redundant: 45 of the 100 are same-episode repeats, but each required a
> monotonic `worst_giveaway` to grow >=20%, so each is a materially worse
> figure. Suppressing them would cost the trader **Rs 65,769** of unreported
> deterioration. The volume should stay.

## What did NOT improve — stated plainly

**Total alerts went from ~38 to ~95, and the per-day rate did not fall** (1.90 →
1.98, max 4 → 5). Problem #3 in the review — *"the same story told several
times"* — is **not solved by these changes.**

The increase is the direct, intended consequence of removing the `min_peak`
gate: 28 more sessions now qualify. The monotonic re-arm metric did not reduce
per-day volume, and on inspection it re-arms *more* readily than `erosion_pct`
did — `erosion_pct` spiked and then needed 20% above its own spike, which
accidentally suppressed later firings, while `worst_giveaway` grows steadily as
a session sinks so each +20% step is a genuine deepening.

Every re-arm now means the giveback actually got worse, which is the property
that was asked for. **Whether ~1 alert per affected session is the right volume
is a separate decision that has not been made** — it needs an episode key (one
peak, one alert, escalating only), which is a change nobody has approved.

## Limitations, recorded not closed

1. **`peak_pnl` is the high-water mark of the REALIZED curve only.** A trader up
   ₹10,000 on an open position who closes it at +₹2,000 has a recorded peak of
   ₹2,000; the giveback they actually felt is invisible. **Left unsolved by
   explicit instruction** — an engine-wide observability boundary, not a Pattern
   6 defect.
2. **The frontend renders `erosion_pct` wrong, and did before this change.**
   `AlertDetailSheet.tsx:92` prints `` `${fmtN(d.erosion_pct)}%` `` while the
   context stores a **ratio**, so a 51% giveback displays as **"0.5%"** and a
   487% one as "4.9%". Pre-existing, verified, **not fixed here** — outside the
   approved change list. Worth its own small fix.
3. **`erosion_pct` is still reported in context** and is still unbounded on the
   flip branch (observed to 42.8 on the widened set). It no longer decides
   severity or re-arms anything, but it is still shown to the trader — see (2).
4. **Volume per affected session is unchanged** — see above.
5. **`profit_giveaway_caution_pct` (0.50) remains unsourced.** The review found
   no break in the distribution supporting it and no research fixing a
   session-level giveback percentage. It survives as the percentage branch's
   only line because removing it would need a replacement, and the review
   proposed none.
6. **No replay re-run.** These numbers come from running the real detector over
   the corrected book in-process, which is how every Pattern 4-6 measurement was
   taken; a full harness replay would also re-derive every other detector and
   was not needed to measure this one.

## Tests

`tests/test_profit_giveaway.py` — **21 tests, the detector's first.** Groups:
the gate removal (small peak turning red now fires; `min_peak` still gates the
percentage branch; `min_erosion` still gates green→red; the self-relative floor;
peak of zero), one severity (5 parametrised givebacks 50-99% all caution; the
deleted key is unresolvable), the re-arm metric (it is `worst_giveaway`; never
decreases across a bouncing session; `erosion_pct` decides nothing), severity
monotonicity (does not fall on recovery; monotonic across a whole session),
reporting the moment (a recovered session is not described as "turned to loss";
a currently-red one is; the percentage message says "so far"), and the spec
(`facts` declared; the detector is still pure).
