# `revenge_trade` — implementation contract

23 Aug 2026. **Proposal. Nothing implemented.** Builds on the approved conceptual
contract in `revenge_trade.md`; that document is the *what*, this is the *how*,
mapped onto the foundation as it now exists.

Read §1 first. It is the finding that changes the design, and it was not visible
until the foundation made the frames explicit.

---

## 1. The central defect: capital is currently used to SUPPRESS, not to protect

Today's detector gates on a rupee floor:

```python
min_loss = ctx.thresholds.get("revenge_min_loss_inr", 500)   # = 1% of capital
_typical = self._typical_loss(ctx)
if _typical:
    min_loss = max(min_loss * 0.5, _typical * 0.5)
if abs(last_pnl) < min_loss:
    return None                                   # ← larger account, higher bar
```

`revenge_min_loss_inr` resolves to **1% of capital** (rung 4). So the bigger the
account, the larger a loss must be before the detector will look at it at all.
Capital raises the bar.

Measured, not argued — the same 40 sessions, capital changed and nothing else:

| capital | `revenge_trade` alerts |
|---|---|
| ₹50,000 | 8 |
| ₹5,00,000 | **0** |

**This is backwards.** Account-relative measurement exists to say *"that loss was
big enough to matter to your account"* — it is a reason to **fire**, not a reason
to stay quiet. Used as a floor, it does the opposite: the trader with more at
stake gets less protection.

The correction is not to change the number. It is that account-relative belongs
in the **safety trigger** and must never appear in a **suppression gate**. That
distinction is what the frames are for, and it is the reason to do this detector
first.

---

## 2. Reference frames

`revenge_trade` uses all four. That is why it is the right detector to validate
the architecture — it exercises every path.

| frame | what it answers here | input | available |
|---|---|---|---|
| **Account** | did the prior loss damage the account? | `loss_vs_account(prior_loss, ctx.account_risk)` | trade 1, **if** equity known |
| **Trade** | did the prior trade lose most of what was risked on it? | `loss_vs_trade(prior_loss, estimate_capital_at_risk(prior))` | **trade 1, always** |
| **Personal** | is this loss / gap / size unusual **for them**? | `loss_vs_own_losses`, `gap_vs_own_gaps`, `size_vs_own_sizes` | after maturity |
| **Structural** | did a re-entry follow a loss, on the same instrument, larger? | ordering, symbol identity, quantity | **trade 2, always** |

`DetectorSpec.frames = (ACCOUNT, TRADE, PERSONAL, STRUCTURAL)` — the first
assignment, made while reading the detector, as intended.

---

## 3. Structure: one trigger, three independent judgements

The detector answers a **structural** question first, then judges the answer in up
to three frames. It never averages them.

```
STRUCTURAL GATE  (no thresholds, no history)
  prior CompletedTrade closed at a loss, and
  current trade entered after it, and
  gap ≥ 0                                        → else NOT_DETECTED

then, independently:

  SAFETY   account-relative: prior loss ≥ [S1]% of equity      → fires alone
           trade-relative:   prior loss ≥ [S2]% of capital-at-risk → fires alone
           neither may be suppressed by anything personal

  PERSONAL loss unusual for them (percentile of own losses)
           gap fast for them   (percentile of own gaps)
           size up for them    (ratio to own median)
           → requires maturity; abstains without it

  DECLARED trader's own cooldown_after_loss, if set → a breach is a fact
```

**No points. No sum.** The existing implementation adds `signal_points_*` into a
confidence score; §9 explains why that has to go.

---

## 4. Cold start — a brand-new trader, first ever session

| frame | day one | why |
|---|---|---|
| Structural | **works** | "you re-entered four minutes after a loss" needs no history and no numbers |
| Trade-relative | **works** | `estimate_capital_at_risk` is instrument-aware: premium paid for a long option is exact |
| Account-relative | works **iff** equity known | otherwise abstains — see below |
| Personal | **abstains** | three data points is not a distribution |

So a new trader gets: the structural observation, trade-relative safety, and
account-relative safety when we can see the account. They do **not** get "this is
unusual for you", which is honest — we do not know them yet.

**The account-relative path is weaker than it should be, for an infrastructure
reason.** `margin_snapshots` has no scheduled producer, so `ctx.account_risk`
reaches its GOOD rung only if the trader happened to load a page that fetched
margins. Otherwise: declared capital (PARTIAL) or abstain. **This must be resolved
before the account-relative safety trigger means anything in production** — see
`SCALABILITY_50K_ANALYSIS.md` §4. It is a product decision, not a detector one.

---

## 5. Maturity and abstention

Per metric, never one global flag.

| metric | counter | below maturity |
|---|---|---|
| own losing-trade distribution | count of losing CompletedTrades in the baseline window | that signal abstains |
| own loss→re-entry gap distribution | count of observed gaps | that signal abstains |
| own position-size distribution | count of trades | that signal abstains |

A signal that abstains contributes **nothing** — not a neutral value, not a
default. `Evidence` / `abstain()` from `evidence.py` carry this, and this detector
would be their first consumer.

**Today's implementation violates this twice.** `_typical_loss` requires 3 losses
and otherwise falls back to a flat ₹500 — an invented number standing in for
missing knowledge. And `None` currently means both "no revenge trade" and "could
not tell", so the 203-session replay cannot distinguish a clean year from an
unmonitored one.

### `_typical_loss` is mislabelled

```python
losses = sorted(... for t in (ctx.session_trades or []) ...)   # TODAY only
if len(losses) < 3: return None
```

It reads **today's session**, not the trader's history. It is a *session-relative*
measure presented as personal. Under this contract the personal frame draws from
the baseline (long window), and today's session may be used as rung 2 — but the
two must be labelled distinctly, because "unusual for you" and "unusual for you
today" are different claims.

---

## 6. Protection against bad habits becoming normal

Three mechanisms, all already built, none yet applied here.

1. **Frame separation.** The safety trigger reads account- and trade-relative
   measures only. No personal input can reach it, so no habit can quieten it.
   Enforced by `violates_kind` at resolution time once the safety thresholds are
   classified `universal_safety`.
2. **Safety bounds.** The personal signals may move only so far before a bound
   holds them. The direction matters and differs per key:
   - `revenge_window_*` — **HIGHER_IS_STRICTER**; a habitual fast re-enterer has a
     low p25, shrinking their window until nothing qualifies. The bound is a
     **minimum**.
   - loss-meaningfulness percentile — **HIGHER_IS_LOOSER**; a trader with large
     habitual losses raises their own p60. The bound is a **maximum**.
3. **Contamination exclusion.** Confirmed revenge sequences must not train the gap
   baseline — otherwise the detector's own positives drag "normal" downward until
   it silences itself. `clean_for_learning(values, excluded_indices)` exists for
   exactly this; **nothing currently passes `excluded_indices`.** Wiring it is part
   of this detector's work.

---

## 7. Constants and their provenance

Everything the detector touches today, with an honest status. **No value below has
been invented to complete this table.**

| constant | current | Kind | status |
|---|---|---|---|
| `revenge_min_loss_inr` | 1% of capital, else ₹500 | fallback | **REMOVE** as a gate — §1 |
| `revenge_min_loss_pct_capital` | 1.0 | fallback | **REMOVE** with it |
| `revenge_window_caution_min` | 20 min (or own p25) | fallback | **KEEP**, reclassify `personal_baseline` |
| `revenge_window_danger_min` | 5 min | fallback | **UNRESOLVED** — already flagged mandatory-review |
| `signal_points_critical/high/medium/low` | 30/20/10/5 | fallback | **REMOVE** — §9 |
| `confidence_alert_gate` | 50 | fallback | **UNRESOLVED**, and not this detector's to decide |
| `_typical_loss` min sample | 3 (inline) | none | **REPLACE** with declared maturity |
| size-escalation ratio | 1.5 (inline literal) | none | **UNRESOLVED** |
| `cooldown_after_loss` | user-set | user_rule | **KEEP** unchanged |

### Unresolved — each needs a decision, not a guess

| # | what must be decided | why it cannot be derived here |
|---|---|---|
| **S1** | account-relative safety trigger: prior loss ≥ ?% of equity | A product claim about what counts as account damage. The conceptual contract says 5% and marks it illustrative. One trader's tradebook cannot validate it — the account size moved between ₹30k and ₹50k across the period, so no single equity figure makes the percentage mean anything. |
| **S2** | trade-relative safety trigger: prior loss ≥ ?% of capital at risk | Instrument-dependent. Losing 80% of an option premium and 80% of futures SPAN are different events. Probably needs a value per instrument class, which is a research question. |
| **P1** | which percentile marks a loss "meaningful for them" | p60 is a plausible default and is a choice. Measurable against the tradebook by comparing recall of days the trader themselves would call revenge. |
| **P2** | which percentile marks a gap "fast for them" | Same, in the other direction (p25). Same evidence available. |
| **P3** | size-escalation multiple | Currently 1.5 with no derivation. Could come from the trader's own size distribution instead, which would remove the constant. |
| **M1** | maturity thresholds per metric | The conceptual contract proposes 10 / 30 as illustrative. Needs the sample-stability check that has not been run. |
| **B1** | the safety bound values, and their direction | Deliberately empty. Each is a claim about one behaviour and must be argued from evidence when set. |
| **C1** | whether `confidence_alert_gate` stays a single global 50 | Affects every detector, so it belongs to the engine review, not here. |

**S1 and S2 are the two that block the safety layer.** Without them there is no
account-relative or trade-relative trigger, and the detector reduces to structural
plus personal — which is where it already is.

---

## 8. Severity and confidence

**Severity = harm if real. Confidence = certainty it is real.** They must not be
computed from the same inputs.

Proposed severity, subject to S1/S2:

| severity | condition |
|---|---|
| `critical` | safety trigger breached **and** the new position is larger than the one that lost |
| `danger` | safety trigger breached |
| `caution` | no safety trigger; personal signals present and mature |
| `info` | structural only, or personal signals immature — recorded, never notified |

Confidence comes from **how well we could see it**: data quality, how many
percentiles were mature, whether the symbol parsed. Not from severity, and not
from the number of signals — that conflates "several things are true" with "we are
sure", which are different.

Today's code derives severity partly from the same signals it scores for
confidence. That has to be separated, and it is a change in alert behaviour.

---

## 9. Why the points system must go

```python
confidence = float(pts["critical"])        # 30
if gap_min <= danger_window: confidence += pts["high"]      # +20
if same_symbol:              confidence += pts["high"]      # +20
if size_ratio >= 1.5:        confidence += pts["high"]      # +20
if session_pnl < 0:          confidence += pts["medium"]    # +10
```

**This is L3 in miniature.** Four invented weights, summed across incommensurable
observations, producing a number nobody can defend — and it gates whether the
trader is told anything, because below 50 the severity is rewritten to `info`.

Every argument that retired the behaviour score applies here unchanged. The
replacement is not a better weighting; it is to **stop summing**. Signals are
recorded individually as evidence, severity comes from harm, confidence comes from
observability. If a combination genuinely deserves escalation, that is a stated
rule about that combination, not an emergent property of arithmetic.

The one genuinely good thing in this block should be kept: the comment explaining
that `same_symbol` and `same_underlying` are nested rather than independent. That
reasoning is right and is the seed of the objection to the whole scheme.

---

## 10. Evidence and explainability

The alert must reconstruct from stored data alone:

- the trigger: prior trade id, its loss, its exit time, the current entry time, the gap
- each frame's measurement, with its denominator and provenance (`Measurement`
  carries `denominator_label` for exactly this)
- which signals abstained and why (`Insufficiency`)
- the thresholds it was judged against — **already stored**, via `_thresholds`
- when a safety bound held a personal value back, that fact and the reason

Copy must never say "your limit" about a number that is not the trader's. The
`personalised: false` marker added to the threshold record exists for this.

---

## 11. Consolidation and output

Unchanged, and correct as it stands. `revenge_trade` sits in the *"going back to
the same trade"* family behind `same_symbol_obsession` and ahead of
`rapid_reentry`; `death_spiral` absorbs it when both fire. Folded events keep
their `BehaviorEvent` with a `_suppressed` marker.

One open question, not a change: the family ordering is hand-picked and
unvalidated. It is out of scope here but should not be forgotten.

---

## 12. Across capital bands and styles

Behaviour under the proposed design. **The account-relative row depends on S1 and
is therefore provisional.**

| trader | today | proposed |
|---|---|---|
| **₹5,000** | floor = ₹50; almost any loss qualifies; likely noisy | structural + trade-relative; personal after maturity. Account-relative fires on a genuinely account-threatening loss |
| **₹50,000** | floor = ₹500 — the band it was tuned on; **8 alerts / 40 sessions** | broadly similar, with the arbitrary floor replaced by their own distribution |
| **₹5,00,000** | floor = ₹5,000 → **0 alerts**, silenced | fires normally: personal frame scales by construction; account-relative fires on a large loss |
| **₹50,00,000** | floor = ₹50,000 → silent for almost everything | same as above. The percentile is scale-free; the rupee floor never was |

| style | risk | defence |
|---|---|---|
| Scalper, 90-second tempo | every re-entry looks fast | percentile of **their own** gaps: 90s is their p50 |
| Positional, two trades a week | never reaches maturity | abstains on personal; keeps structural and safety |
| Options seller, multi-leg | legs seconds apart after a losing leg | strategy-group suppression, already built |
| Systematic re-entry at a level | fast, same instrument, bigger | **no defence.** Intent is unobservable. Accept as a known false positive rather than pretend |

---

## 13. Foundation: consume, and remove

**Must be consumed** (first consumer in each case):

| piece | use |
|---|---|
| `measurements.py` | all four families — this is the validation of that module |
| `evidence.py` | per-signal abstention |
| `detector_result.py` — `DetectorResult`, `Layer` | separating safety from personal in the result |
| `ctx.account_risk` | account-relative trigger; **first reader** |
| `safety_bounds` | bounds on the personal percentiles, once B1 is decided |
| `DetectorSpec.frames` | first assignment |
| `clean_for_learning(excluded_indices=...)` | contamination exclusion; the argument exists and is never passed |

**Should be removed or changed:**

| piece | why |
|---|---|
| `signal_points_*` (4 constants) | §9 — invented weights summed across incommensurable evidence |
| `revenge_min_loss_inr` + `_pct_capital` | §1 — capital used to suppress |
| `_typical_loss` | mislabelled session-scoped measure; replaced by the personal frame with declared maturity |
| inline `1.5` size ratio | either a declared constant with provenance or derived from their own distribution |
| `EpisodeRole` / `EpisodeHint` | not needed by this detector, not needed by any. Delete unless something else claims them |

**Genuinely not needed here**, and that is fine: baseline `divergence` (a good
idea with no consumer yet), and `max_drawdown` / `longest_loss_run` (used by the
baseline, not by this detector).

---

## 14. Critical assessment

**The strongest reason to do this detector first** is §1. The frame taxonomy was
justified on principle; applying it to one detector immediately exposed that
capital is currently wired backwards — suppressing instead of protecting — and
the replay quantified it at 8 → 0. No amount of further foundation work would
have surfaced that.

**The contract is blocked on two numbers, and I will not invent them.** Without
S1 and S2 there is no safety layer, and the detector stays structural + personal —
better than today, but not the two-layer design. If those decisions are not made,
we should say so and ship the personal-frame improvement alone rather than pretend
the safety layer exists.

**The riskiest part is severity.** Separating it from confidence changes which
alerts a trader sees and at what level. That is a real behavioural change and
needs the replay, with every difference classified.

**What I think is over-built.** `EpisodeRole`/`EpisodeHint` are not needed here
and I cannot name a detector that needs them; they should go. The two-window
`divergence` is computed and stored for nobody. `threshold_recorder` records keys
*read* rather than *used*, so some irrelevant numbers will attach to alerts — the
right trade-off, but worth stating.

**What I think is right and should not be touched:** consolidation-by-meaning,
the strategy-group suppression, and the nested `same_symbol`/`same_underlying`
reasoning — which is the one part of the current points block that is genuinely
well argued, and is also the argument for deleting the rest of it.

**Honest scope.** This contract makes `revenge_trade` correct in structure. It
does not make it *validated*: that needs the ₹50k tradebook replayed with the new
logic, every difference classified, and — for the personal percentiles — a
judgement about which days the trader would call revenge. Only `heeded` can
ultimately judge the product, and that is live data we do not have.
