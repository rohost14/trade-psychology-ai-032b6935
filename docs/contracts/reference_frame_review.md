# "Normal is not safe" — is it enforced?

23 Aug 2026. **Findings only. Nothing was changed.** Every claim below was
checked against the code in `app/`, not against a design document.

**Verdict: the principle is expressible and not enforced.** The machinery to
state it exists, is correct, and currently protects an empty set.

---

## 1. Is the principle enforced?

No — and it fails three times over, independently. Any one of these would be
enough to break it.

**(a) The rule is never called.**

```
grep -rn "violates_kind" app/     →  definition only, plus two comments
grep -rn "violates_kind" tests/   →  four call sites
```

`violates_kind()` (`threshold_resolution.py:110`) is correct. It is asserted in
tests over the current registry. It is not consulted when a threshold actually
resolves, so nothing stops a future resolution path from doing the illegal thing
at runtime.

**(b) There are no `universal_safety` thresholds.**

```
registry entries: 16      COLD_START_DEFAULTS keys: 86
   14  personal_baseline
    2  definitional
universal_safety keys: []
```

The rule guards `UNIVERSAL_SAFETY`, `PRODUCT_POLICY` and `USER_RULE`. Not one
threshold in the system is classified as any of the first two. The invariant is
enforced over nothing.

**(c) 70 of 86 live thresholds are `fallback`, which the rule does not constrain.**

`kind_for()` returns `FALLBACK` for anything unregistered, and `violates_kind`
places no restriction on `FALLBACK`. So 70 live thresholds may resolve from any
rung, including personal history, with no rule applied at all.

## 2. Where it is violated

Not hypothetically. **Every threshold that personal history actually moves is
classified `fallback`** — the one Kind with no constraint:

| key moved by history | source metric | Kind | floor |
|---|---|---|---|
| `daily_trade_limit` | their own `daily_trades_p75` | fallback | — |
| `daily_trade_danger` | derived ×1.5 | fallback | — |
| `burst_trades_per_30min_caution` | `burst_per_30min_p75` | fallback | 3 |
| `burst_trades_per_30min_danger` | derived ×1.6 | fallback | — |
| `revenge_window_caution_min` | `reentry_after_loss_p25` | fallback | 2 |
| `consecutive_loss_caution` | `loss_streak_p60` | fallback | 3 |
| `consecutive_loss_danger` | `loss_streak_p85` | fallback | — |

`consecutive_loss_caution` — "how many losses in a row before we say anything" —
is a safety-shaped question resolving from `Source.HISTORY`. Were it classified
`universal_safety`, `violates_kind` would reject that resolution outright. It is
not, so the rule permits precisely the resolution that suppresses it.

**`UNIVERSAL_FLOORS` is not a safety floor.** Its own header says "Never fire
alerts below these" — it is a *noise* floor that prevents over-alerting. It is
applied as `if values[key] < floor: raise to floor`, a **minimum on the threshold
number**, and for count-shaped keys a higher number means *less* sensitive. So it
bounds how sensitive a detector may become and places **no bound whatsoever on
how insensitive** personal history may make it.

The dict also mixes directions and applies one comparison to both: for
`consecutive_loss_caution: 3` a bigger number is less sensitive (noise floor),
while for `revenge_window_caution_min: 2` a bigger window is *more* sensitive
(sensitivity floor). Same operator, opposite meanings.

## 3. Cold start

**Yes, a new trader is meaningfully protected — but not by the mechanism the
architecture describes.**

What actually protects them: every detector runs from trade one against
`COLD_START_DEFAULTS`, and most of the 27 are structural — "you added to a losing
position", "you re-entered the same symbol four minutes after a loss", "this
position had no stop" are facts about a sequence and need no history. That is
real protection on day one and it works today.

What does *not* protect them, contrary to the design: `measurements.py` — the
three-family split (`loss_vs_account`, `loss_vs_trade`, `loss_vs_own_losses`) —
is imported by **nothing**. The cold-start argument in its docstring, that a new
user keeps trade-relative safety while the account family abstains, is currently
a description of an intended design rather than of running code.

And the account-relative family is weaker than intended for a separate,
already-recorded reason: `margin_snapshots` has no scheduled producer, so the
denominator reaches its GOOD rung only if the trader happened to load a page that
fetched margins.

## 4. Can bad history become "normal" and suppress a safety signal?

**Yes. By construction, and it is measurable today.**

`daily_trade_limit` resolves to the **P75 of the trader's own daily trade
counts**. A trader who overtrades every single day has a high P75, so their limit
is high, so the overtrading detector goes quiet — for exactly the trader it
exists for. The same shape applies to `burst_trades_per_30min_caution` (their own
P75) and `consecutive_loss_caution` (their own P60).

`revenge_window_caution_min` takes the **P25 of their own re-entry gaps**: a
trader who always re-enters fast gets a narrow window, and `revenge_trade` stops
firing for the fastest re-enterer.

`MAX_ADAPTATION_PER_PERIOD = 0.20` limits how far a baseline may move *per
recompute*. It slows the drift; it does not bound the level. Five periods of
compounding is ~2.5×.

There is no ceiling anywhere. `UNIVERSAL_FLOORS` only sets minimums, and only on
6 of the 7 keys above.

## 5. Are the three frames separated correctly?

**In `measurements.py`, yes — cleanly, and it is unused. In the live detectors,
no.**

No detector declares its reference frame. `DetectorSpec` (`detector_registry.py:38`)
carries `name`, `method`, `version`, `default_mode` and no frame field.
`Layer(SAFETY|PERSONAL)` in `detector_result.py` is imported by nothing.

A concrete mixing, demonstrated by measurement rather than argued: `revenge_trade`
combines a **capital-relative** rupee floor (`revenge_min_loss_inr`, from the
parked `91975d4`) with a **personal-relative** `_typical_loss(ctx)` in one
decision. Replaying the same 40 sessions with capital changed from ₹50,000 to
₹500,000 and nothing else:

| pattern | ₹50k | ₹500k |
|---|---|---|
| `revenge_trade` | 8 | **0** |
| `profit_giveaway` | 5 | **0** |
| `consecutive_loss_streak` | — | unchanged |

The two detectors carrying capital-relative rupee floors go completely silent at
10× capital. `consecutive_loss_streak`, which has no such floor, is unaffected.
This is the empirical confirmation of the concern already parked against `91975d4`.

## 6. What the foundation needs — minimum, not elaboration

Four changes. Three are small; the second is the only one that changes behaviour,
and it needs a product decision before it is written.

**A. Classify the thresholds that are safety, and call the rule at runtime.**
The 70 `fallback` entries are unreviewed, not deliberately unconstrained. Until
some are `universal_safety`, `violates_kind` cannot protect anything. Then call
it inside `resolve_thresholds` rather than only in tests, so an illegal
resolution is refused when it happens.

**B. Add a ceiling concept. `UNIVERSAL_FLOORS` cannot express one.**
Today the system can say "never alert below 3 losses" and cannot say "always
alert by 8, whatever this trader's history says". A bound on insensitivity is the
whole content of "normal is not safe", and it is the one piece of machinery that
does not exist. **What those bounds should be is a product decision and must not
be invented here** — an arbitrary ceiling is the same mistake as an arbitrary
threshold, pointing the other way.

**C. Make each detector declare its reference frame(s), declaratively.**
A `frames` field on `DetectorSpec`, filled in during the pattern-by-pattern
review, one detector at a time as each is opened. Not a bulk annotation exercise
— the value is in deciding the frame while reviewing the detector, and a field
filled in by guesswork is worse than an empty one.

**D. Decide what to do with `measurements.py` and `Layer`.**
Both are correct and unused. They become real when the first detector is
migrated, which is the pattern-by-pattern phase. If that phase does not adopt
them, they should be deleted rather than left as an architecture that describes
code which does not exist.

### Deliberately not proposed

- No new thresholds, ceilings or numbers. B says a ceiling *mechanism* is
  missing; it does not say what the values are.
- No composite scoring. The frames stay separate.
- No change to `UNIVERSAL_FLOORS` values, and no detector touched.
- No rework of the abstention or baseline-contamination machinery: `Evidence`,
  `clean_for_learning` and `cap_adaptation` are correct and wired. `cap_adaptation`
  in particular is doing real work — it is simply not sufficient on its own,
  because slowing drift is not the same as bounding it.
