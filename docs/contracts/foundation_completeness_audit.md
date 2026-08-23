# Is the behavioural-engine foundation complete?

23 Aug 2026. **Audit only. No code.** Checked against `app/`, not against the
design documents.

**Short answer: no — but four of the twelve items cannot be completed in the
shared layer at all, and treating them as foundation work would be a mistake.**

That distinction is the finding. Some of what looks like a foundation gap is a
per-detector decision wearing a foundation-shaped hole, and building a shared
mechanism for it would produce exactly the kind of speculative architecture the
last two weeks removed.

---

## 1. Status of the twelve areas

| # | area | state | why |
|---|---|---|---|
| 1 | Reference frames / safety vs personal | **mechanism done, empty** | `Layer`, `frames`, `violates_kind` all exist; `violates_kind` guards **0** thresholds because none is classified `universal_safety` |
| 2 | Cold start | **done** | 27 detectors run from trade one on `COLD_START_DEFAULTS`; most are structural. The *numbers* are unjustified, which is pattern work |
| 3 | Abstention / evidence semantics | **done** | `Evidence`, `Insufficiency`, `abstained()`, and the engine adapter (Step 1). Reachable by any detector that wants it |
| 4 | Baseline learning + contamination | **done** | robust stats, capped adaptation, outlier exclusion, and harmful-sequence exclusion derived from trades (Step 2) |
| 5 | Universal safety bounds + provenance | **mechanism done, empty** | `violates_kind` runs at resolution; bounds clamp after floors; **0 bounds declared**, by design |
| 6 | Account-risk / session denominator | **done in engine, blocked outside** | resolved once, frozen, recorded, abstains honestly. No detector reads it yet, and `margin_snapshots` has no producer |
| 7 | Canonical state / fact ownership | **done** | one definition, single writer, guard test against re-forking |
| 8 | `DetectorResult` contract | **done** | engine accepts both types; adapter tested |
| 9 | Explainability | **done** | thresholds + provenance stored per alert; measurements carry denominators |
| 10 | Severity vs confidence | **NOT done** | see §2 — and only half of it is shared |
| 11 | Runtime / query guarantees | **done** | measured; detectors do zero IO; `_load_context` constant in session size; query budget — all guarded |
| 12 | Scalability / observability | **partly** | engine metrics exist; two genuine defects are infrastructure, not foundation |

---

## 2. The real gaps, and who owns them

### G-A. No threshold is classified `universal_safety` — **required, shared**

`violates_kind` is enforced at resolution time and protects nothing, because the
guarded set is empty. 84 of 100 resolved thresholds are `fallback`, the Kind with
no constraint, and **every threshold personal history actually moves is one of
them**.

Classifying *what a threshold is* is a shared-layer question — `Kind` is a
statement about the number's nature, not about any detector's logic. The *values*
stay per-detector.

**This is the single highest-value remaining foundation item.** Without it, the
central invariant is machinery guarding nothing.

### G-B. `UNIVERSAL_FLOORS` mixes directions under one comparison — **required, shared**

Ten floors, applied as `if value < floor: raise to floor`. For
`consecutive_loss_caution` a bigger number is *looser*, so this is a noise floor;
for `revenge_window_caution_min` a bigger window is *stricter*, so the same line
is a sensitivity floor. One operator, two opposite meanings.

`Sensitivity` now exists and the floors do not use it. Declaring each floor's
direction is shared work and changes no value.

### G-C. Maturity has no shared definition — **required, shared**

`Maturity` is an enum in the registry; `measurements` takes `min_sample` from the
caller; `_pct_metric` records a `confidence` but gates nothing. So "is this metric
mature enough to use" is currently answered by each caller, or not at all.

The **mechanism** is shared: a metric declares what must accumulate, and a helper
answers mature / immature / unavailable — the three states already specified for
P2. The **numbers** are per-metric and stay unresolved.

Without this, every detector migration reinvents the same three-way check, which
is how the nine competing definitions of a session fact happened.

### G-D. Confidence has no shared definition — **required, shared (severity is not)**

This is the half of item 10 that belongs to the foundation.

**Severity is pattern-specific by nature.** It is a claim about harm from a
specific behaviour and cannot be computed generically. Building a shared severity
mechanism would be inventing a scoring system, which is what we removed.

**Confidence is not pattern-specific.** "How well could we see this" is the same
question everywhere: data quality of the trade, how many frames were measurable
rather than abstaining, the maturity of any percentile used, whether inputs
parsed. Today seven call sites compute it differently, one of them by summing
invented points.

A shared `confidence_from(...)` over those observables is foundation work. What
each detector does with it is not.

### G-E. Instrument class is not a shared concept — **required, shared**

`estimate_capital_at_risk` returns a *loss ceiling* for a long option and *margin
posted* for a short option or future, with **no label distinguishing them**.
`grep` for any `InstrumentClass` returns nothing.

So any detector reasoning trade-relative must re-derive the class and re-learn
that 80% of one is not comparable to 80% of the other. That is shared, it is a
fact about instruments rather than about any detector, and the `revenge_trade`
contract already proved a single threshold across classes is an error rather than
a simplification.

`Measurement` should carry the class alongside `denominator_label`, so the stored
evidence says which kind of denominator was used.

### G-F. `confidence_alert_gate = 50` — **required decision, shared, not a value I set**

One unvalidated constant decides whether *any* detection reaches a trader. It is
engine-level by your own ruling. It needs a decision or an explicit "keep 50 and
say why"; either way it is foundation, not pattern.

---

## 3. Explicitly NOT foundation

Recording these so they are not smuggled in as completeness.

| item | classification | why |
|---|---|---|
| S1, S2a–d, P1, P3, B1 values | **pattern-specific** | each is a claim about one behaviour, argued from that detector's evidence |
| Severity mapping / the A×B matrix | **pattern-specific** | already frozen for `revenge_trade`; another detector may need a different shape |
| Migrating detectors to `DetectorResult` | **pattern-specific** | one at a time, behind a replay |
| `margin_snapshots` producer | **infrastructure** | gates A3 in the field; no logic change |
| WebSocket head-of-line blocking | **infrastructure** | real-time defect, exists today at one user |
| Worker concurrency, NullPool churn, stream amplification | **infrastructure** | `SCALABILITY_50K_ANALYSIS.md` |
| `EpisodeRole` / `EpisodeHint` | **optional** | kept by your decision; still unconsumed |
| baseline `divergence` | **optional** | computed, stored, read by nothing. Delete if unclaimed by the third detector |
| `_apply_history_v1_metrics` legacy path | **optional** | two baseline shapes still resolve; removable once no v1 baselines remain |
| Consolidation family ordering | **optional** | hand-picked, unvalidated, silently decides which alert is seen. Worth evidence eventually, not now |

---

## 4. Remaining implementation plan

Six items. All shared, none introduces a threshold, score, weight or
detector-specific logic.

| # | change | classification | risk |
|---|---|---|---|
| **F1** | Classify the safety-relevant thresholds as `universal_safety` (Kind only, no values) | required / shared | **behavioural** — those keys stop resolving from history. Replay gate |
| **F2** | Declare a `Sensitivity` direction on every `UNIVERSAL_FLOORS` entry; apply the floor in the declared direction | required / shared | behaviour-neutral if directions are stated correctly; replay confirms |
| **F3** | Shared maturity helper: mature / immature / unavailable, per metric, values unresolved | required / shared | inert until a caller uses it |
| **F4** | Shared `confidence_from(observables)`; do not migrate detectors to it yet | required / shared | inert |
| **F5** | `InstrumentClass` as a labelled concept; `estimate_capital_at_risk` returns the class with the number; `Measurement` carries it | required / shared | behaviour-neutral — same numbers, newly labelled |
| **F6** | Decide `confidence_alert_gate`: keep 50 with a stated reason, or change it | required / shared decision | **behavioural** if changed |

**F1 is the only one that certainly changes behaviour**, and it is the point:
thresholds that should never have been learnable will stop being learned. It
needs the replay and every difference classified.

F2 and F5 should be behaviour-neutral; if either is not, the direction or the
class was mis-declared and the replay will say so.

Suggested order: **F5 → F3 → F4** (all inert, no gate) → **F2** (replay) →
**F1** (replay) → **F6** (decision).

---

## 5. The honest caveat

Four of the twelve audited areas — DetectorResult adoption, severity, per-frame
thresholds, and whether `measurements.py` is the right shape — **cannot be
validated without a detector consuming them.** Every one of the six changes above
adds mechanism that is inert until something uses it.

That is the same risk named in the engine review: eight foundation pieces already
have no consumer, and these add to that count before reducing it. The foundation
is not complete, and it also cannot be *proved* complete in the shared layer
alone. After F1–F6 the honest statement is "the shared mechanisms exist and are
enforced where they can be", not "the foundation is validated".

**If any of F1–F6 turns out to be hard to specify without a detector in front of
it, that is evidence it is not foundation work.** I would rather say that at the
time than build a general mechanism for one case.
