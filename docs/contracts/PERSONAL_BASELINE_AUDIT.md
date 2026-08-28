# Threshold registry & resolution — audit and fix

28 Aug 2026. Prompted by the same defect appearing in four consecutive pattern
reviews (P7, P9, P10, P11). **Investigated end to end, then fixed.**

> **This document replaces an earlier version that was wrong on its central
> claim.** That version said the registry contained "6 false declarations".
> It does not — see *The correction* below. The real defect was elsewhere, and
> more serious.

---

## The headline

**A trader could loosen a `UNIVERSAL_SAFETY` threshold by declaring a number.**

`_apply_profile_facts` maps a declared `max_position_size` onto
`max_position_pct_caution` and `max_position_pct_danger` — both
`Kind.UNIVERSAL_SAFETY` — using `Source.CAPITAL`. `violates_kind` did not refuse
it, because `CAPITAL` is not in `_LEARNED_SOURCES` (`{history, session,
population}`).

Measured before the fix:

| declared `max_position_size` | caution | danger |
|---|---|---|
| 3 | 3.0 | 6.0 |
| 5 (the universal line) | 5.0 | 10.0 |
| 10 | **10.0** | **20.0** |
| 25 | **25.0** | **50.0** |
| 40 | **40.0** | **80.0** |

`excess_exposure` reads both. So the detector that exists to say *"this position
is dangerously large"* went quiet for exactly the traders taking the largest
positions — the failure the whole `Kind` machinery was built to prevent.

It was **deliberate**, not a slip: `test_capital_derived_pair_is_marked_capital`
asserted it. Two parts of the codebase disagreed, and only one could be right.

## The correction

The earlier audit called the six `PERSONAL_BASELINE` specs with unproduced
metrics "false declarations". **They are not.** `threshold_registry`'s own
docstring is explicit:

> **WHAT `metric` DOES NOT MEAN** — A spec naming a metric does NOT mean that
> constant should become personal. It means personalisation is *available* for
> it… `personalise=False` on every entry is deliberate: this migration builds the
> path and changes no behaviour. Each detector flips its own at review, behind a
> replay.

`resolution_source` is documented as *"Rung that **would** answer **if**
personalisation were enabled"*. So `PERSONAL_BASELINE` + `metric=` +
`personalise=False` means **"this is the kind of thing that should be personal,
here is how it would be, and it is not switched on"** — which is exactly true.

Two existing tests enforce this and correctly rejected an attempt during this
work to set `personalise=True` on the hand-wired keys.

**What the four pattern reviews actually found** was that a metric named in a
spec has no producer. That is a gap in a *planned* path, not a lie about a live
one. Worth recording, not worth the alarm.

---

## Findings

### 1. Safety could be loosened — FIXED

Above. The one behaviour-affecting defect.

### 2. The resolver never reads the registry

`threshold_resolution.py` contains **zero** references to `spec.metric`.
Personalisation is four hand-written calls:

```python
place("daily_trade_limit",              "daily_trades_p75")
place("burst_trades_per_30min_caution", "burst_per_30min_p75")
place("revenge_window_caution_min",     "reentry_after_loss_p25")
place("consecutive_loss_caution",       "loss_streak_p60")
```

All four metrics are genuinely produced by `baseline_service`. **The baseline
machinery works** — it is wired for four thresholds, outside the registry.

**Not changed.** Making the registry drive resolution would change which
thresholds personalise, and needs its own replay. Recorded as the open item.

### 3. The registry did not describe the four that are personalised — FIXED

`daily_trade_limit` was **not in the registry at all**, so `kind_for()` returned
the default `FALLBACK`. The other three carried `FALLBACK` as an artifact of
being auto-generated from `_FLOOR_DIRECTIONS`. Now declared in `_GROUP_E` with
their real `Kind`, metric, percentile and maturity.

### 4. Unregistered keys default to a permissive Kind

`kind_for()` returns `FALLBACK` for anything unregistered, and `FALLBACK` permits
learned sources. **12 keys** the resolver writes are unregistered. None is
currently safety-shaped, but the direction of the default means a future
safety-critical key would be silently personalisable. A test now fails if a
`max_position_pct*` or `premium_loss*` key is missing from the registry.

### 5. Registry metadata that nothing reads

`meaning`, `resolution_source`, `metric`, `percentile`, `maturity`,
`provenance`, and `personalisable_keys()` have **no readers outside the registry
and its tests**. Per the module's design these describe a path not yet built, so
this is documentation rather than dead code — but nothing enforces that they stay
truthful, which is how `flip_interval_p25` survived pointing at nothing.

### 6. A spec's fallback could contradict the live default

Found by writing the fix: `daily_trade_limit` was given `fallback=15` from memory
while `COLD_START_DEFAULTS` says `7`. An existing test
(`test_registry_fallbacks_match_the_live_constant`) already covers this class and
caught it.

### 7. `_CAPITAL_RATIOS` targets two retired keys

Rung 4 contains only `profit_giveaway_min_peak` and `_min_erosion`, whose
detector was retired 2026-08-27. The rung is live and its only entries feed
nothing. **Left alone** — the keys are deliberately retained as the rung's only
test vehicle, recorded in `trading_defaults`.

### 8. A parity oracle carries the old behaviour

`_get_thresholds_pre_ladder` is test-only and still contains the
declared-size→safety mapping. It is not a live path; its fixtures declare 3 and
4, both tightening, so parity is unaffected.

---

## The fix

**One behavioural change, and it is the bug.**

### `UNIVERSAL_SAFETY` is now its own bound

`safety_bounds.bound_for()`: a `Kind.UNIVERSAL_SAFETY` spec with no explicit
`safety_bound` is bounded at its own universal value.

This **invents no number**. The Kind means "objective danger; never
personalised", so the universal value is by definition the loosest the threshold
may become. It uses the mechanism already built for it — `clamp_to_bound`, whose
docstring describes precisely this gap — and an explicit `safety_bound` on a spec
still wins, so a detector review can still set a different one.

**Tightening still works.** A trader who declares a 3% cap still gets alerts at
3%. Only loosening past the universal line is refused, with a recorded reason.

**The declared rule is not lost.** `max_position_size` is a `RULE_FIELD` in
`constitution_service`, so it is still enforced as the trader's own commitment by
`constitution_violation`. What it may no longer do is move a safety line.

### Registry: `_GROUP_E`

The four genuinely personalised thresholds now have specs describing what they
are. `personalise` stays `False` — correct, because the registry-driven path is
not what supplies them.

### Clamp reasons no longer name a source they do not know

The message said *"your own history would have put this at X"*. The value that
prompted this came from a **declared rule**, not history. Now: *"this would
otherwise have resolved to X"*.

---

## Proof that behaviour did not change

Every threshold, four scenarios, before vs after:

| scenario | keys | changed |
|---|---|---|
| cold start | 80 | **0** |
| with a full v2 baseline (personalised) | 80 | **0** |
| declared `max_position_size=4` (tightening) | 80 | **0** |
| declared `max_position_size=40` (loosening) | 80 | **2** |

The two are `max_position_pct_caution` 40.0 → 5.0 and `max_position_pct_danger`
80.0 → 10.0 — the fix, and nothing else.

**Backend 1,552 passed / 0 failed. Frontend typecheck clean, 102 tests, 0 lint
errors.** 30 new contract tests.

**No replay was run.** It could not have shown anything: the 203-session replay
runs `--no-rules`, so no `max_position_size` is declared and the changed keys
never move. The scenario table above covers the case a replay could not.

---

## Is the PERSONAL_BASELINE system safe to rely on?

**For safety: yes, now.** Learned sources were already refused; the bound closes
the declared/capital route. Both are tested, including the property that *every*
`UNIVERSAL_SAFETY` threshold is bounded, so the guarantee is general rather than
a patch on the one key found to be reachable.

**For personalisation: it works, for four thresholds, outside the registry.**
Believe `Kind`; do not read `metric` as evidence that anything is wired.

**Remaining gaps, recorded not closed:**

1. **The registry does not drive resolution.** `spec.metric` is unread; the four
   live paths are hand-written. Until that changes, the registry documents intent
   and `Kind` is the only load-bearing field.
2. **Five specs name metrics with no producer** — `winner_hold_p50`,
   `late_mis_entries_p75`, `late_mis_entries_p90`, `hold_minutes_p25`, and
   `early_exit_ratio` (no metric at all). Availability declarations for work not
   done, which is legitimate, but nothing fails if a metric never arrives.
3. **12 resolver keys are unregistered** and default to permissive `FALLBACK`.
   Guarded for safety-shaped names only.
4. **`_CAPITAL_RATIOS` feeds a retired detector.**
