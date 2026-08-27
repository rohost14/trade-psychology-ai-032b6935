# Does giveback context add signal to the detectors we already have?

27 Aug 2026. **Research only. Nothing implemented, nothing proposed for
implementation yet.** Follows the retirement of `profit_giveaway` as an alert.

**Verdict: PROMISING BUT NOT ESTABLISHED — do not build.** One of four detectors
shows a real effect at one gate and loses it at another. With single-digit counts
and eight comparisons, that pattern is what small samples look like, not what
signal looks like.

---

## The proposal

> MEANINGFUL PROFIT → MATERIAL GIVEBACK → CONTINUED TRADING → ABNORMAL RISK /
> FREQUENCY / RECOVERY → FURTHER DETERIORATION

The reframing is right, and it is what the research pointed at: **the giveback
stops being the finding and becomes the context**, with the finding moved to
what the trader does next. Link 4 is the only one that can carry an alert, and
the four detectors named for it already exist. So the question is not whether to
build a chain detector. It is whether being inside the chain makes
`revenge_trade`, `same_symbol_obsession`, `martingale_behaviour` and
`adding_to_adverse_position` mean more than they already do.

## Gates, and the sensitivity sweep

Both gates are percentiles of **this trader's own** distribution, so no rupee
figure is invented. The whole sweep is reported rather than one cut:

| profit gate | giveback gate | armed sessions | armed boundaries |
|---|---|---|---|
| p25 ₹902 | p50 ₹2,250 | **22 / 189** | 55 / 912 |
| p25 ₹902 | p75 ₹4,147 | 10 / 189 | 31 / 912 |
| p25 ₹902 | p90 ₹8,459 | 3 / 189 | 7 / 912 |
| p50 ₹2,280 | p50 ₹2,250 | 12 / 189 | 28 / 912 |
| **p50 ₹2,280** | **p75 ₹4,147** | **5 / 189** | 14 / 912 |
| p50 ₹2,280 | p90 ₹8,459 | 1 / 189 | 3 / 912 |
| p75 ₹4,713 | p50 ₹2,250 | 3 / 189 | 8 / 912 |
| p75 ₹4,713 | p75 ₹4,147 | 1 / 189 | 4 / 912 |

**The chain is rare at any defensible setting** — 12% of sessions at the loosest,
under 3% once either gate reaches the median. That is the first thing to know
about it.

## The confound, and why the first answer was wrong

The obvious test — compare each detector's armed-firing rate to the share of all
boundaries that are armed — is contaminated, by exactly the mechanism that
produced and then destroyed the Pattern 5 result. **Both quantities rise with
position in the session:**

| | pos 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| P(armed \| reached) | 0% | 2% | 2% | 8% | 8% | **17%** | 14% | 16% | 17% | 13% |

A giveback needs a peak to fall from, so armed boundaries cluster late.
`martingale_behaviour` needs three prior trades and `same_symbol_obsession`
needs three losses on one underlying, so their firings cluster late too. Two
things that both happen late look correlated whether or not they are.

Uncontrolled, the answer looked good — `same_symbol_obsession` +12.2pp at 2.3
SE, `martingale_behaviour` +19.6pp at 4.8 SE. **Those numbers are not reported
as findings; they are reported as the artefact.**

## The controlled test

For each detector, take the exact multiset of position indices at which it
fired, and sum `P(armed | reached position i)` over them. That is how many armed
firings its own position habits produce if the context is irrelevant.

**Loose gate — profit p25 (₹902) / giveback p50 (₹2,250):**

| detector | fired | armed | expected | ratio | z |
|---|---|---|---|---|---|
| `revenge_trade` | 7 | 1 | 0.7 | 1.41 | 0.4 |
| `same_symbol_obsession` | 22 | 4 | 2.7 | 1.48 | **0.9** |
| **`martingale_behaviour`** | 39 | **10** | **4.0** | **2.48** | **3.2** |
| `adding_to_adverse_position` | 93 | 7 | 5.2 | 1.34 | 0.8 |

**Strict gate — profit p50 (₹2,280) / giveback p75 (₹4,147):**

| detector | fired | armed | expected | ratio | z |
|---|---|---|---|---|---|
| `revenge_trade` | 7 | 1 | 0.3 | 3.96 | 1.5 |
| `same_symbol_obsession` | 22 | 3 | 0.8 | 3.78 | **2.5** |
| `martingale_behaviour` | 39 | 2 | 1.1 | 1.87 | **0.9** |
| **`adding_to_adverse_position`** | 93 | **5** | **1.3** | **3.81** | **3.3** |

Note what the control did to `same_symbol_obsession` at the loose gate: **2.3 SE
uncontrolled → 0.9 controlled.** The whole apparent effect was position.

## Reading it honestly

**The results flip between gates.** `martingale_behaviour` is z=3.2 at the loose
gate and z=0.9 at the strict one. `adding_to_adverse_position` is the exact
reverse — z=0.8 loose, z=3.3 strict. `same_symbol_obsession` is 0.9 then 2.5.
`revenge_trade` shows nothing either way and has only 7 alerts in total.

**A signal that changes which detector it belongs to when the gate moves is not
a signal.** If the effect were real it should at least be directionally stable
as the gate tightens. Strong-then-gone and weak-then-strong is the signature of
single-digit counts, and there are eight comparisons here.

**The strongest single result is `martingale_behaviour` at the loose gate: 10
observed against 4.0 expected, 2.5× its position-adjusted rate, z=3.2.** Ten is
a real count and the ratio is large. It is the one worth carrying forward. It
does not replicate at the strict gate, but there `martingale` has only 2 armed
firings, so nothing could replicate.

That is genuinely interesting and genuinely insufficient.

## What would settle it

1. **A second trader's book.** Every number here rests on one trader, and the
   whole question is whether an effect survives out of sample.
2. **Live `heeded` data.** The design of record is explicit that rest-of-session
   P&L ranks candidates but cannot judge the product — only whether the alert
   was acted on can, and only live.
3. **Pre-registering one gate.** Eight comparisons on counts under 10 is how
   noise gets promoted. If this is retested, the gate should be fixed in advance.

## If it is ever built

**Not as a detector.** The measured effect, such as it is, belongs to detectors
that already exist. The defensible shape is giveback-as-precondition raising the
**confidence** of an existing alert, never creating one — no new pattern type, no
new alert, no new severity tier, and no new threshold beyond the trader's own
percentiles which the ladder already computes.

`session_facts` already exposes everything required (`peak_pnl`,
`drawdown_from_peak`, `max_drawdown`), so the context costs nothing to obtain.

**Nothing is proposed for implementation.**

## Recorded while doing this

- **`pattern_prediction_service` already uses the giveback as context, badly.**
  `drawdown_from_peak > 2000` adds 15 points to a tilt probability — an
  unsourced rupee literal on a per-trader quantity.
- **All five of its prediction keys are names the engine cannot emit**:
  `revenge_trading` (real: `revenge_trade`), `tilt_loss_spiral` (**retired**),
  `overtrading` (real: `overtrading_burst` / `daily_overtrading`), `fomo` (real:
  `fomo_entry`), `recovery_chase` (never existed). They are dict keys rather
  than `pattern_type ==` comparisons, so `test_pattern_contract`'s retired-name
  check does not catch them. The service is live on `/api/analytics` and
  `/api/reports`. **This is a vocabulary-drift defect of the exact class that
  test was written for, and it needs its own fix.**
