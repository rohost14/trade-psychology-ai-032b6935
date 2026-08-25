# Pattern #4 — resolving the severity question

25 Aug 2026. **No code changed. No threshold, percentile, multiplier or cutoff
invented.** Follows `consecutive_loss_streak_review.md`.

**Answer: one severity. Report the money, do not tier on it.** A real signal
exists, but it is continuous, and the only definitional boundary available
belongs to another detector.

---

## The bar

Not "does it rank" — everything ranks. The bar is whether a candidate separates
genuinely different **behaviour**. For a streak, the observable behaviour is
**what the trader does next**, which is measurable and is not an outcome the
product would be judging itself by.

## Candidate A — absolute loss

```
    1,000-2,000    21  ##################################
    2,000-3,000    27  ############################################
    3,000-4,000    17  ############################
    4,000-5,000    11  ##################
    5,000-6,000     5  ########
    6,000-8,000    11  ##################
    8,000-10,000    6  ##########
       10,000+      5  ########
```

p10 ₹1,425 · p25 ₹2,070 · p50 ₹3,232 · p75 ₹5,076 · max ₹12,866.
**Empty gaps wider than ₹1,000: two, at ₹9,635→₹10,660 and ₹11,015→₹12,670** —
both in the extreme tail, covering five points between them. Nothing inside the
range where 101 of 106 firings sit.

### It separates behaviour — the first thing in this review series to do so

Splitting the 106 firings at the median loss and asking what the trader did next:

| | n | **stopped for the day** | next trade bigger | next trade won |
|---|---|---|---|---|
| smaller half of losses | 53 | **39.6%** | 50.0% | 40.6% |
| larger half of losses | 53 | **17.0%** | 40.9% | 40.9% |

**+22.6pp, which is 2.6 SE.** For comparison, the same split by **streak
length** gives 33.9% vs 20.5% — **1.5 SE**, barely above the ~1.4 SE noise floor
this project has been rejecting everywhere else.

**And the mechanical bias runs the other way.** A larger cumulative loss usually
means a longer streak, which means later in the session, which means *fewer*
trades left — so it should make "stopped" *more* likely. The observed effect is
the opposite and survives that headwind.

**So: after a bigger loss this trader is markedly less likely to stop. That is a
real behavioural difference, and loss size sees it better than the count does.**

## Candidate B — loss as a percentage of the declared daily limit

**Cannot be computed on this dataset.** The trader declared no limit, the engine
returns `None`, and `resolve_thresholds` supplies no fallback. Any distribution
here would be one I manufactured by picking a limit.

**CORRECTION, 25 Aug — I said this was "already owned" and that was wrong.**
`constitution_violation`'s `daily_loss` rule fires at **80% / 100% / 120%** of
the declared limit. The streak branch fires at **50%**. Fifty is below eighty, so
it is an **earlier rung with an additional condition attached** — half the limit
gone *and* it went in an unbroken run — not a second voice saying the same thing.
The two form a ladder rather than a duplication.

**And it is not dead for real users either.** The onboarding wizard collects
`daily_loss_limit` and pre-fills a suggestion at **2% of declared capital**. It
is absent in the replay only because that run passes `--no-rules`. For a real
trader who completed onboarding, this value exists — and because it is derived
from their own capital at their own choosing, it adapts to account size and
style by construction, which is exactly what a fixed count cannot do.

## Candidate C — loss as a percentage of capital

```
    0-2%     3      8-10%   11
    2-4%    21     10-15%   12
    4-6%    27     15-20%   10
    6-8%    17       20%+    5
```

**This is candidate A divided by a constant.** Identical shape, identical gaps,
identical ranking. It cannot separate anything A does not.

It also inherits a problem the project has already ruled on: the replay harness
**excludes** `excess_exposure` and `session_meltdown` as CAPITAL_DERIVED, because
capital moved between ₹30,000 and ₹50,000 across the period, was withdrawn at
month end and topped up mid-month — *"there is no single number that makes '20%
of capital' mean anything."* Keying severity to capital would move this detector
into that same unvalidatable bucket.

## Is `0.5 × daily_loss_limit` justified?

| | |
|---|---|
| times it fired in 106 firings | **0** |
| times it has fired in production | **0** (no real users) |
| tests covering it | **0** |

**There is no evidence for it and none against it.** It is untested rather than
wrong. Its comment argues a real point — that three trades losing ₹12,000 should
not read quieter than five losing ₹1,500 — and §A above shows loss size genuinely
does carry information the count does not. But the `0.5` itself has never been
exercised, and the dimension it measures is already owned by
`constitution_violation`.

## The simplest defensible approach

**One severity. State the money.**

> *"3 consecutive losing trades — ₹3,232."*

Reasoning, in order:

1. **The count cannot carry severity.** 63 sessions with a 3+ run observed
   against 63.0 expected by chance. A tier on it asserts something the data
   denies.
2. **Loss size carries a real signal (2.6 SE) but no boundary.** The
   distribution is one smooth mode with gaps only in a five-point tail. Any
   cutoff would be chosen, not found — and choosing one is exactly what this
   review is not permitted to do.
3. **The trader's own declared limit is available and is NOT owned elsewhere at
   this level** — see the correction above. It is the strongest reference in the
   engine: their number, derived from their capital, collected at onboarding.
4. **Percent of capital adds nothing** and costs validatability.

So the honest position is that **no tier is supported**, and the detector should
say one true thing at one severity rather than two things at two.

### What that costs, stated plainly

Dropping the danger tier means this pattern **stops producing push
notifications** (notification level 2 reaches push at danger). That is a product
decision, not a measurement one: 21 of 106 firings currently reach danger, all of
them via the count, and the count is chance. The choice is between pushing on
noise and not pushing.

If a tier is wanted anyway, the least indefensible version is **the trader's own
limit at 100%** — their number, not ours — and that requires first deciding
whether `constitution_violation` or this detector owns that statement. That is a
families question and belongs to whichever review reaches it.

## What is NOT proposed

No percentile. No multiplier. No cutoff. No personalisation of the counts. No
merge with `constitution_violation`. No deletion. And no change to
`consecutive_loss_caution` = 3, which stays as the definition of "repeatedly" —
it decides *whether there is something to say*, which is a different job from
deciding *how loudly to say it*.
