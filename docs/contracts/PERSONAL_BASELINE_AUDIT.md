# Registry audit — which thresholds are actually personalised?

28 Aug 2026. Requested after the same defect appeared in four consecutive pattern
reviews (P7, P9, P10, P11). **Findings only — nothing fixed.**

The answer is worse than the four instances suggested: **the registry's `Kind`
labels and the actual personalisation wiring do not overlap at all.**

---

## The headline

| | |
|---|---|
| specs labelled `Kind.PERSONAL_BASELINE` | **6** |
| …of those, actually personalised | **0** |
| thresholds actually personalised at runtime | **4** |
| …of those, labelled `PERSONAL_BASELINE` | **0** |
| **overlap between the two sets** | **NONE** |

Every threshold that says it is personal is not. Every threshold that is personal
does not say so.

## Why: the `metric` field is decorative

`threshold_registry.py` specs carry `metric=`, `resolution_source=` and
`percentile=`. **`threshold_resolution.py` never reads `spec.metric`** — zero
occurrences of `.metric` in the resolver.

Personalisation is done by four hand-written calls instead:

```python
place("daily_trade_limit",              "daily_trades_p75",       cast=...)
place("burst_trades_per_30min_caution", "burst_per_30min_p75",    ...)
place("revenge_window_caution_min",     "reentry_after_loss_p25", floor=1.0)
place("consecutive_loss_caution",       "loss_streak_p60",        ...)
```

So a spec declaring `metric="flip_interval_p25"` causes **nothing to happen**. It
reads as wiring and is documentation.

## The 6 specs labelled PERSONAL_BASELINE — all dead

Each declares a metric **no code produces**, and the field would not be read even
if one did. All six resolve to their hardcoded fallback, for every trader,
permanently.

| key | declared metric | producers | source |
|---|---|---|---|
| `rapid_flip_min` | `flip_interval_p25` | **0** | SESSION |
| `early_exit_winner_max_min` | `winner_hold_p50` | **0** | HISTORY |
| `end_session_mis_caution_count` | `late_mis_entries_p75` | **0** | HISTORY |
| `end_session_mis_danger_count` | `late_mis_entries_p90` | **0** | HISTORY |
| `opening_trap_quick_exit_min` | `hold_minutes_p25` | **0** | SESSION |
| `early_exit_ratio` | **none declared** | — | — |

*(`rapid_flip_min` goes with `direction_instability`, retired 28 Aug. The
remaining five stay live.)*

## The 4 that really are personalised — and are labelled wrong

| key | metric | producer exists? | registry `Kind` |
|---|---|---|---|
| `daily_trade_limit` | `daily_trades_p75` | ✅ | **not in the registry at all** |
| `burst_trades_per_30min_caution` | `burst_per_30min_p75` | ✅ | **FALLBACK** |
| `revenge_window_caution_min` | `reentry_after_loss_p25` | ✅ | **FALLBACK** |
| `consecutive_loss_caution` | `loss_streak_p60` | ✅ | **FALLBACK** |

All four metrics are genuinely written by `baseline_service.py`. **The baseline
machinery works.** It is wired for four thresholds, and the registry describes
none of them correctly.

## Why this matters

1. **`Kind` is load-bearing elsewhere.** `violates_kind` enforces that a
   personal baseline may never loosen a safety bound. A `Kind` that does not
   describe reality weakens a rule other code trusts.
2. **It has already misled four reviews.** P7, P9, P10 and P11 each independently
   found "declared personal, can never personalise" and treated it as a local
   defect. It is one systemic defect with local symptoms.
3. **A trader can be shown an invented number described as theirs.** Memory
   records exactly this happening once before, via a key-name mismatch on the
   baseline path.
4. **It hides what is missing.** Five live detectors would benefit from
   personalisation, the metrics were specified, and nobody wired them — but the
   registry reads as though the work is done.

## Not fixed here

No changes made. The obvious options, in ascending order of work:

- **Relabel only** — move the 5 surviving dead specs to `Kind.FALLBACK` and give
  the 4 working ones `PERSONAL_BASELINE`. Truthful registry, no behaviour change,
  no replay needed.
- **Make `metric` load-bearing** — have the resolver iterate specs instead of
  hand-written `place()` calls, so declaring a metric wires it. Changes which
  thresholds personalise, so it needs producers first and a replay.
- **Write the missing producers** — 5 metrics in `baseline_service.py`. Changes
  live thresholds for real traders; needs its own review.

**Recommendation: relabel only, as a standalone change.** It is the one option
that makes the registry honest without changing a single firing, and it stops the
next pattern review rediscovering the same thing.
