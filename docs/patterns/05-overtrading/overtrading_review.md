# Pattern #5 — `overtrading_burst` + `daily_overtrading`

26 Aug 2026. **Review only. No code changed, no threshold added or retuned.**

One method, `_detect_overtrading_burst`, emitting two pattern types with two
independent claims. Reviewed together because they share a method, a spec and a
family — but they need separate verdicts, because the evidence differs sharply.

| | verdict |
|---|---|
| **`daily_overtrading`** | **MODIFY — the alert must stop making its current claim.** On the only book we have, it fires on the trader's *better* sessions, and the trades it implicitly warns against made money. |
| **`overtrading_burst`** | **DEFER — not measurable here.** 12 alerts across 189 sessions, never once firing alone. Insufficient evidence in either direction; do not tune it, do not delete it. |

---

## 1. What they are supposed to detect

**Burst:** *"Positions opened inside a 30-minute window, counting a multi-leg
structure as one."* Rationale in the registry copy: *"Trades taken minutes apart
share one state of mind rather than separate assessments."*

**Daily:** *"Total positions opened today, counting a multi-leg structure as
one."* Rationale: ***"Past a certain count the day stops being a series of
decisions and becomes momentum."***

The daily claim is falsifiable and §5 tests it directly. It is the only thing
that would justify naming a count at all.

## 2. What the implementation does

`behavior_engine.py:1185-1353`, 169 lines, one method.

**Check 1 — burst.** Rolling 30-minute window ending at the current trade's
entry. `count_structures()` collapses a recognised multi-leg cluster to one.

- `burst_count >= burst_danger` (8) → **danger**
- suppressed entirely if `session_pnl > 0` **and** every trade in the window was
  profitable
- `>= burst_caution` (5) and `session_pnl < 0` → **caution**
- `>= burst_caution` and at least one loser in the window → **caution**
- otherwise falls through in silence to Check 2

**Check 2 — daily.** `daily_count >= daily_caution` (7) → **caution**;
`>= daily_danger` (12) → **danger**. Emits `daily_overtrading`, a different
pattern type from the same method.

| threshold | default | source, as recorded in `trading_defaults.py` |
|---|---|---|
| `burst_trades_per_30min_caution` | 5 | classified `fallback`, floor 3 |
| `burst_trades_per_30min_danger` | 8 | **unclassified, no source** |
| `daily_trade_limit` | 7 | **"SEBI FY2023 (>6/day → 94% loss probability)"** |
| `daily_trade_danger` | 12 | **"no source"** — the file says so itself |

**Personalisation.** Both caution values blend toward the trader's own history:
`daily_trade_limit` ← `daily_trades_p75`, `burst_trades_per_30min_caution` ←
`burst_per_30min_p75`. Both danger values are derived by multiplier
(`max(caution+1, caution×1.5)` and `max(caution+2, caution×1.6)`).

**Declared rules already reach this detector** — unlike Pattern 4.
`threshold_resolution.py:463-473` folds a declared `daily_trade_limit` in at
`Source.DECLARED`, but **only when it is tighter** (`if user_limit < derived`),
by the safety invariant in `safety_bounds.py`. So the trader can sharpen this
detector but never blunt it.

**Severity** caution/danger · **notification level 2** (danger pushes) ·
`overtrading_burst` is a SOFT cooldown trigger · both pair with the
constitution's `daily_trades` rule.

## 3. Purity and performance — **KEEP AS-IS**

No `await`, no `db.`, no `select(` in the body. Ran 912 times in this review
with no database connection. `count_structures` is pure. Two list
comprehensions and a sort per call. Negligible.

## 4. Evidence — 189 sessions, 912 positions, corrected trade set

Measured at the **cold-start defaults** (5 / 8 / 7 / 12), which is what every
new trader gets. Cross-checked against the stored 203-session replay: 52
`daily_overtrading` and 12 `overtrading_burst` alerts — matches this review's
independent dedup estimate of ~52 and ~12 exactly.

### 4a. What it fires

| | detections | → alerts | days | severity |
|---|---|---|---|---|
| `daily_overtrading` | 132 | **52** | 49 of 189 (**26%**) | 126 caution / 6 danger |
| `overtrading_burst` | 13 | **12** | 10 of 189 (**5%**) | 10 caution / 3 danger |

### 4b. The daily threshold is a quota, not a finding

This trader's own pace: **p25 = 3, p50 = 4, p75 = 7, max = 14** positions/day.

`daily_trade_limit` resolves from history as **`daily_trades_p75`**. A threshold
set at a trader's 75th percentile fires on 25% of their sessions **by
construction** — for any trader, forever, no matter how they behave. Observed
here: 26%.

**The alert rate is fixed by the derivation, not by the behaviour.** A trader
who halves their trading still gets alerted on a quarter of their sessions,
because the p75 moves down with them. That is not a detector; it is a quota.

The repo default of 7 and this trader's p75 happen to be the same number, so
both paths agree here. **Agreement is not evidence** — they agree by
coincidence, and only one of them can move.

### 4c. The distribution has no break at 7

| positions/day | 1 | 2 | 3 | 4 | 5 | 6 | **7** | 8 | 9 | 10 | 11 | **12** | 13 | 14 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sessions | 20 | 24 | 28 | **32** | 22 | 13 | **14** | 13 | 9 | 7 | 4 | **1** | 1 | 1 |

One mode at 4, then decay. **The 6 → 7 step is the only place in the tail where
the count goes *up* (13 → 14, ×1.08).** The caution line is placed at a local
rise, not at a break. The largest drops are 4 → 5 (×0.69) and 5 → 6 (×0.59) —
both *below* the line — and 11 → 12 (×0.25), which is where `daily_danger` sits
and is a three-session tail.

### 4d. The one apparently positive result is arithmetic — retracted

A first pass found that firings with a higher `daily_count` were more often the
session's last trade: 27.3% → 43.9%, **+16.7pp, 2.0 SE**. Above the ~1.4 SE
floor this series uses, and it would have been reportable.

**It is an artefact, and the control kills it.** `daily_count` at firing *is*
the position's index in the session. A firing at count 12 is nearer the end than
one at count 7 by definition, so it is trivially more likely to be last.

| count | detector says "stopped" | **session lengths alone say** |
|---|---|---|
| 7 | 26% | **28%** |
| 8 | 39% | **36%** |
| 9 | 35% | **39%** |
| 10 | 46% | **50%** |
| 11 | 57% | **57%** |
| 12 | 33% | **33%** |
| 13 | 50% | **50%** |
| 14 | 100% | **100%** |

The right-hand column involves no detector — it is `P(L == c | L >= c)` computed
from the distribution of session lengths. **The two columns are the same
curve.** The detector measured the shape of the session-length distribution.

In Pattern 4 the equivalent bias ran *against* the observed effect, which is why
that result survived. Here it runs *with* it, and nothing survives.

### 4e. Testing the actual claim: "becomes momentum"

Three observable markers of momentum-rather-than-decision, measured on trades
past the line versus trades before it, **within the same heavy sessions**:

| | positions 1-6 | **positions 7+** | direction |
|---|---|---|---|
| median gap between trades | 4 min | **9 min** | **slower** |
| median capital at risk | ₹8,044 | **₹7,213** | **smaller** |
| win rate | 44.7% | 42.6% | −2.1pp, **0.4 SE** |

**All three point away from the claim.** Past the line this trader slows down
and sizes down. The win rate does not move.

### 4f. Heavy days are this trader's *best* days

| | sessions | total P&L | mean | median | green |
|---|---|---|---|---|---|
| **heavy (≥ 7 positions)** | 50 | **−₹3,359** | **−₹67** | −₹356 | 44% |
| light (< 7) | 139 | **−₹138,135** | **−₹994** | −₹832 | 41% |

> **Heavy days are 26% of sessions and 2% of the book's loss. The light days
> carry 98% of the damage.**

And the 141 positions taken at or past the line **made ₹1,265** — 60 winners
against 79 losers, net positive.

Index-matched control, removing the composition effect (a 1-trade day is no
longer compared against the opening of a 10-trade day):

| position | heavy win rate | light win rate | diff |
|---|---|---|---|
| 1 | 48.0% | 33.1% | **+14.9pp** |
| 4 | 48.0% | 33.8% | +14.2pp |
| **all 1-6** | **44.7%** | **36.1%** | **+8.6pp, 2.4 SE** |

**The difference is already there at position 1**, before any line exists to
cross. Heavy days are a different *kind* of day from the first trade — this
trader keeps trading on days that are going well. The count is a symptom of the
day, not a cause of anything.

**Stated plainly: `daily_overtrading` sends 52 alerts, on the sessions where
this trader does least badly, about trades that were net profitable.**

### 4g. The burst rule cannot be judged on this book

13 detections, 12 alerts, 10 sessions (5%). Counts at firing: 5 (×8), 6 (×2),
8 (×2), 9 (×1). Fired while the session was down: 8 of 13.

**n = 13 supports no threshold decision in either direction.** That is the
finding. The claim — trades minutes apart share one state of mind — remains
plausible and untested. Do not tune it on 13 points; do not delete something for
being rare.

## 5. Overlap — and a family problem

`daily_overtrading` **fired alone on 2 of its 49 days.**
`overtrading_burst` **fired alone on 0 of its 10 days.**

| co-fires with `daily_overtrading` | days | share of its days |
|---|---|---|
| `adding_to_adverse_position` | 25 | 51% |
| `martingale_behaviour` | 23 | 47% |
| `death_spiral` | 22 | 45% |
| `size_escalation` | 21 | 43% |
| `fomo_entry` | 18 | 37% |
| `expiry_day_overtrading` | 15 | 31% |

**Three detectors make a pace claim**: `daily_overtrading`,
`overtrading_burst`, `expiry_day_overtrading`. They appear together on **22
days**, where the trader receives two or three separate alerts about the same
property of the same session — 14 × (daily + expiry), 7 × (daily + burst), 1 ×
all three. None of the three is in a consolidation family.

## 6. Are the values justified?

**`daily_trade_danger` = 12: no.** The file itself says "no source". It fires on
3 of 189 sessions and it is the tier that pushes a notification.

**`burst_trades_per_30min_danger` = 8: no.** Unclassified, unsourced, and
reached 3 times in the book.

**`daily_trade_limit` = 7: the citation does not support the use.** Recorded as
*"SEBI FY2023 (>6/day → 94% loss probability)"*. **No source document for this
figure exists in the repo** — I searched `docs/` and found none, so the number
cannot be checked against what the study says. Setting that aside, the
structural problem stands on its own: **a population base rate about which
traders lose money is not a per-trader threshold for when to interrupt a
session.** For this trader, the population inference is exactly inverted — their
high-count days are their better days.

**`burst_trades_per_30min_caution` = 5:** classified `fallback` with a floor of
3, and untestable here (n=13).

## 7. Two structural findings that outlive this pattern

**`count_structures` changes almost nothing.** Across the whole book it collapses
**8 legs out of 912 (0.9%)**. The machinery is correct and conservative — it can
only lower a count — but on this trader it is inert. Not a defect; recorded so
nobody re-derives it.

**Correction to the Pattern 4 hand-off.** That review recorded that the
constitution's `daily_trades` rule "has the identical unreachable-warning
defect". Arithmetically true — `ceil(0.80 × 3)` is 3 — but **the onboarding
default for `daily_trade_limit` is 10, not 3**, and `0.80 × 10 = 8` is reachable.
So unlike `max_consecutive_losses` (default 3, where the warning rung was
unreachable for every default trader), this defect is **latent**: it bites only a
trader who declares a limit of 2, 3 or 4. Lower priority than Pattern 4 implied.

## 8. Verdict

### `daily_overtrading` — **MODIFY**

Not KEEP: the alert's stated claim is contradicted on the only book we have, in
all three markers, and the sessions it fires on are the trader's better ones.

Not DELETE outright: **this is one trader.** The measurement says this detector
is wrong *about this trader*, not that no trader over-trades. A count of
positions is also genuinely factual — unlike Pattern 4's streak, nothing about
"you have opened 9 positions today" is untrue.

Not DEFER: 189 sessions is enough to say the current form should not ship as-is.

### `overtrading_burst` — **DEFER**

12 alerts, never alone, no measurable structure. Insufficient evidence. Revisit
when a second book exists.

### Exact changes proposed — for approval, not implemented

| # | change | why |
|---|---|---|
| 1 | **Copy must stop claiming momentum.** *"Past a certain count the day stops being a series of decisions and becomes momentum"* is a psychological claim this book contradicts — past the line the trader is slower and smaller. | §4e |
| 2 | **Decide what `daily_overtrading` is for.** Either (a) demote to `analytics` disposition — count it, show it on Analytics, stop alerting; or (b) keep alerting but only against the trader's **declared** `daily_trade_limit`, which is a commitment rather than an inference, exactly as Pattern 4 resolved. **Recommendation: (b), with (a) as the fallback if no rule is declared.** | §4b, §4f |
| 3 | **Stop deriving the alert line from the trader's own p75.** A p75 threshold alerts on 25% of sessions by construction, independent of behaviour. | §4b |
| 4 | `daily_trade_danger` = 12 needs a source, a key classification and a test — or removal. It decides a push notification on 3 of 189 sessions. | §6 |
| 5 | Correct or remove the SEBI attribution on `daily_trade_limit`. Either cite a document that exists in the repo, or mark the number unsourced like its neighbours. | §6 |
| 6 | Put the three pace detectors in **one consolidation family**. 22 days produce two or three simultaneous alerts about the same property of the same session. | §5 |
| 7 | `overtrading_burst`: **change nothing.** | §4g |

**No replacement threshold is proposed**, and none should be chosen from this
book: the evidence says the current line is wrong, not where a right one would
be.

### What is NOT proposed

Deleting either detector. Retuning 5 / 8 / 7 / 12. Touching
`expiry_day_overtrading` (its own review). Touching `count_structures`. Changing
the declared-limit tightening invariant in `safety_bounds.py`.

### Recorded for later, not fixed here

- `burst_trades_per_30min_danger` and `daily_trade_danger` are both unclassified
  in the threshold registry while both decide a push.
- The burst check's silent fall-through (≥ caution, session flat or up, no
  losers in the window) produces no event and no record — the engine cannot
  later say it looked and declined.
- The constitution `daily_trades` latent unreachable-warning defect (§7).
