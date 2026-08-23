# Behavioural-engine logic review, before pattern-by-pattern

23 Aug 2026. **Review only. No code, no change to `revenge_trade`.** Checked
against `app/`.

**Verdict: no change to the shared engine is required before starting
pattern-by-pattern.** Two findings are recorded that belong to specific detector
reviews, and one honest gap that has no owner yet.

---

## 1. What is the engine trying to detect?

**A decision made against the previous trade rather than on its own terms.**

Not prediction — the design of record is explicit that an alert's job is to
convert an automatic action into a deliberate one, not to forecast. Not P&L
either: rest-of-session outcome can rank detectors but cannot judge the product,
because a trader who stops after an alert produces no further P&L to measure.

That framing survives intact and is the reason the engine detects *observable
behaviour* — a loss, a re-entry, a size increase — rather than claiming
psychological intent it cannot see.

## 2. How the four kinds of evidence work together

They do **not** combine into a number. Each answers a different question and each
can be absent without disabling the others:

| evidence | question | needs |
|---|---|---|
| structural | did this sequence happen? | nothing |
| trade-relative | how much of what was risked was lost? | the trade only |
| account-relative | did it damage the account? | equity |
| personal-relative | is this unusual for them? | history |
| declared rule | did they break a commitment they made? | their own setting |

The frozen `revenge_trade` matrix shows the intended composition: two ordinal
axes, each taking the **highest** level any frame establishes — a lattice join.
Two properties follow structurally rather than by promise: an abstaining frame
can never lower a level, and personal history can only raise one. "This is normal
for them" is unreachable by construction.

Declared-rule evidence is deliberately kept apart: breaking your own cooldown is
a fact about a commitment, not about harm, so it raises severity to `caution` and
never to `danger` on its own.

## 3. A brand-new trader

Gets structural detection on trade one from all 27 detectors, plus trade-relative
safety on long options — premium paid is exact from the first trade and is the
most common retail F&O position here. Account-relative works only if equity is
known. Personal abstains.

**This is real protection, and its numbers are the unjustified ones.** Cold start
runs on `COLD_START_DEFAULTS`, the 86 constants whose calibration is exactly what
pattern-by-pattern exists to examine.

## 4. Before baselines mature

Three states, not two: `mature` / `immature` / `unavailable`. Both non-mature
states use the declared fallback carrying **its own** provenance, and both record
`personalised: false`. The fallback is never relabelled as personal, and copy
follows the split — only a mature window may say "faster than you usually
re-enter".

A metric whose requirement has not been declared resolves to `unavailable` rather
than being assumed ready. Every metric is in that state today, and that is
correct: assuming would invent the requirement at the moment of use.

## 5. Preventing habits from becoming "normal"

Four mechanisms, all present:

1. **Frame separation** — safety reads account- and trade-relative only.
2. **`violates_kind` at resolution time** — now guards 6 `universal_safety`
   thresholds. It refuses HISTORY, SESSION and POPULATION, permits CAPITAL.
3. **Safety bounds** — a ceiling on insensitivity, applied after the floors so it
   is the last word. Mechanism live, values pattern-owned.
4. **Contamination exclusion** — harmful sequences derived from the trade record
   never train the gap baseline, plus robust stats and capped adaptation.

**The honest limit:** the seven thresholds personal history actually moves are
not classified safety, so mechanisms 2 and 3 do not currently constrain them.
That is deliberate — they describe tempo, not harm — but it means the live
protection against "my P75 is high because I overtrade" is capped adaptation
alone, which slows drift without bounding the level.

## 6. Does capital still have the right role? **No — not yet.**

This is the sharpest finding in the review.

Capital appears in exactly one live place: `_apply_capital_ratios`, deriving
three rupee floors — and there it **suppresses**. `revenge_min_loss_inr` = 1% of
capital acts as a gate, so a larger account raises the bar. Measured: 8 alerts at
₹50k, **0** at ₹5L.

The protective role — account-relative safety, where a large loss *triggers*
rather than gates — is designed, frozen into the matrix as A3, and **not built**.
It is additionally blocked by `margin_snapshots` having no scheduled producer.

So today capital's only live role is the wrong one. It is corrected in the first
detector, not in the shared layer, which is the right place — but until then the
answer to this question is no.

## 7. Is abstention used correctly?

Semantically yes: `NOT_DETECTED` and `ABSTAINED` are distinct, `Evidence` refuses
to be truthy so `if evidence:` cannot silently treat an abstention as a "no", and
the engine records an abstention as `info` with its reason so it is countable
without notifying.

**In practice, not yet used at all** — no detector abstains, because none has
been migrated. `None` still means both things everywhere in production.

## 8. Are severity and confidence separated?

**In the shared layer, yes.** Confidence is now the weakest link over
observables and adds no constant; severity is deliberately absent from the shared
layer because it is a claim about harm from one specific behaviour.

**In the live detectors, no.** `revenge_trade` still derives severity partly from
the same signals it scores for confidence, and `confidence_alert_gate` rewrites
severity to `info` below 50. Both are known and belong to that detector's review.

## 9. Are we rebuilding the score? Two places to watch.

**`signal_points_*` in `revenge_trade`** — 30/20/10/5 summed across
non-independent observations. This *is* the old score in miniature. Already
slated for deletion in the frozen contract.

**`death_spiral`** — and this one deserves a straight answer. It counts distinct
*domains* at severity ≥ danger inside a 180-minute window: 2 domains warns, 3 is
critical.

Counting is a weighted score with every weight set to one, by my own standard. In
its defence it counts **independent domains** rather than homogeneous points,
which is corroboration from separate witnesses rather than arithmetic, and it
adds two structural facts — time compression and continued escalation after a
breach state exists — that no score had.

But two things about it are genuinely unexamined:

- `spiral_warning_domains = 2` and `spiral_critical_domains = 3` are invented
  numbers, and the detector→domain mapping is hand-assigned.
- **It bypasses the threshold system entirely.** `evaluate_death_spiral` reads
  `COLD_START_DEFAULTS` directly (six times) and runs from `trade_tasks`, outside
  `_run_all_detectors`. So its constants get no ladder, no provenance, no floors,
  no safety bounds, and never appear in the `_thresholds` explainability record —
  while it is a composite that *absorbs* the alerts it summarises, so it is
  frequently the only thing a trader sees.

That is a real architectural inconsistency. It belongs to `death_spiral`'s own
review, not to the shared layer.

## 10. What was lost from the original engine?

**Lost, genuinely: prioritisation.** L3's score, whatever its faults, ordered
competing alerts. With 33 pattern types and a four-value severity enum, ties are
now broken by consolidation's hand-picked family ordering and then by nothing.
"Which of these matters most today" has no answer. This was removed and not
replaced, and I do not have a proposal that is not a score.

**Dead remnant:** `DetectedEvent.risk_delta` is declared and never set or read —
the field the old scoring consumed.

**Dormant, harmless:** `risk_score`, `peak_risk_score` and `session_state` columns
remain with a CHECK constraint policing four values of which only one can occur.

**Nothing else material.** The removal was replay-verified identical at the time,
which is itself the finding: the score changed no alert.

---

## 11. Against the three-layer engine

**Better, clearly:**

- Nothing is scored, so nothing must be defended as a weight.
- The derived-state ban is enforced by L3 not existing, rather than by convention.
- Every alert is a statement about an observable, and now carries the thresholds
  it was judged against with their provenance.
- Abstention is expressible; under L3 a silent detector and a clean session were
  indistinguishable.
- Session facts have one definition; nine competing ones existed.

**Worse:**

- No prioritisation (§10).
- More architecture with no consumer. Eight foundation pieces had none before
  F1–F5; those added five more. Every one has a named adoption point, and that is
  a promise rather than a fact until a detector consumes it.

**Still missing:**

- Account-relative safety in practice (§6).
- Any detector using frames, abstention, measurements or the instrument class.
- Severity as measurement rather than judgement, in the detectors.

**Not actually one layer:** `death_spiral` is a live meta-detector consuming other
detections. The architecture is L1 + one L2, whatever the documents say.

---

## 12. Verdict

**No change to the shared behavioural engine is required before pattern-by-pattern
begins.** Everything `revenge_trade` needs exists: frames, abstention, maturity,
confidence, instrument class, the safety-bound mechanism, and a frozen matrix.

Three things recorded, none blocking:

| finding | owner |
|---|---|
| `death_spiral` bypasses the ladder; its domain counts are invented | its own detector review |
| `signal_points_*` is the old score in miniature | `revenge_trade` review — already slated |
| Prioritisation was removed and not replaced | **unowned.** Worth a decision eventually; not a foundation gap |
| `risk_delta` is dead | optional cleanup |

**The one thing I would want said out loud before we start:** the foundation is
enforced where it can be and validated nowhere. `revenge_trade` is not just the
first detector — it is the experiment that tells us whether any of this was worth
building. If it does not come out demonstrably better, the correct response is to
delete mechanism, not to migrate detector two.
