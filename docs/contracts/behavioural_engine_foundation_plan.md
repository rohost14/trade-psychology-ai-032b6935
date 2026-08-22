# Behavioural engine foundation — implementation plan

Plan only. No code written. 23 Aug 2026.

Reviewed against `docs/Redesign_Alerts_BehaviouralEngineV3.md` and the G1–G4
work already merged.

---

## 0. First, what the specification does and does not cover

The document is a **measurement-philosophy** document. Checked by term count, it
never mentions: **episodes (0), consolidation (0), replay (0), idempotency (0),
latency (0)**. "Explainability" appears twice, "performance" once.

So of the areas in scope, the spec genuinely governs: shared primitives, safety
vs personal, baselines/abstention, detector contract, explainability. It is
**silent** on episodes, cross-detector consolidation, replayability, state
ownership and hot-path performance.

For those five I would be *designing*, not implementing the document. Flagging
that rather than presenting invention as compliance.

---

## 1. Current gaps

More already exists than the framing suggests. Listing what is built first, so
the gaps are honest rather than inflated.

**Already built and working**

| capability | where |
|---|---|
| Consolidation by *meaning*, not a cap | `behavior_engine._consolidate`, `_COMPOSITES` — folds duplicate descriptions, keeps the suppressed event with a marker |
| Evidence persistence | `BehaviorEvent.evidence`, `input_snapshot`, `data_quality`, `confidence` |
| Idempotency | `BehaviorEvent.idempotency_key` |
| Shadow / canary rollout | `DetectorSpec.default_mode`, `detector_flags` |
| Derived-state ban | A.10, enforced by convention and by L3's removal |
| Per-detector versioning | `DetectorSpec.version`, stored on every alert |
| Strategy-leg suppression | `_STRATEGY_SUPPRESSED` |
| Replay golden master | `tradedesk/scripts/replay_tradebook.py` + `replay_diff.py` |
| Account-risk base | `app/core/account_risk.py` (G1) |
| Abstention primitives | `app/core/evidence.py` (G2) |
| Baseline learning rules | `app/core/baseline_rules.py` (G3) |
| Threshold registry + Kind | `app/core/threshold_registry.py` (G4) |

**The actual gaps**

- **G1–G4 are unconsumed.** `account_risk`, `evidence`, `baseline_rules` and the
  registry are all built and called by *nothing*. This is the single biggest
  gap, and it is deliberate — but it means the foundation currently costs
  maintenance and delivers zero behaviour.
- **Detectors cannot abstain.** They return `Optional[DetectedEvent]`, where
  `None` conflates "did not happen" with "cannot tell". `Evidence` exists but no
  detector can express it.
- **No safety/personal layer in the contract.** `DetectedEvent` carries one
  severity with no record of which layer produced it, so a universal-safety
  finding and a personal-deviation finding are indistinguishable downstream —
  and the "normal ≠ safe" rule cannot be enforced at runtime.
- **`baseline_rules` is not wired into `baseline_service`.** Median/MAD/capping/
  two-window exist as pure functions; the service still computes plain
  percentiles with no contamination protection and no capped adaptation.
- **`SessionState` is shadow-only.** Computed every trade, compared, discarded.
  Two implementations of session facts run in parallel with the DB row as
  authority.
- **Hot path unmeasured.** 27 detectors and 4–5 DB queries per completed trade.
  I have no latency numbers, so I will not claim there is a problem.

---

## 2. Components to build or modify

**Build**

| file | purpose |
|---|---|
| `app/core/detector_result.py` | The detector contract: a result type carrying `Evidence`, the layer that produced it (`safety` / `personal`), severity, confidence, and the measurements behind it. Wraps `DetectedEvent` rather than replacing it. |
| `app/core/measurements.py` | Shared primitives the spec asks for: loss magnitude, position size, timing gap, account impact — each returning value **plus** the denominator used and its provenance. One implementation, not 27. |

**Modify**

| file | change |
|---|---|
| `app/services/baseline_service.py` | Route metric computation through `baseline_rules`: robust stats, `clean_for_learning`, `cap_adaptation`, and the long/recent window pair. |
| `app/services/behavior_engine.py` | Accept `DetectorResult` alongside `DetectedEvent` (both, during migration); record abstentions; resolve `account_risk` once per session and freeze it. |
| `app/core/threshold_resolution.py` | Enforce `violates_kind` at resolution time, not only in tests. |
| `app/services/detector_registry.py` | Add per-detector `layer` and `evidence_requirements` so the contract is declarative like everything else. |

**Explicitly not building**

- **Episodes.** Not in the spec, no measured need, and a new state-machine over
  alerts is exactly the kind of architecture the last two weeks argued against.
- **A trade-normalisation table.** The spec suggests storing many normalised
  values per trade. Most detectors need two or three, computable on demand.
  A schema change should follow evidence of repeated recomputation, not precede it.
- **Anything replacing consolidation.** It already folds by meaning and is better
  than what the spec sketches.

---

## 3. Sequence

Each step ends with the full suite; steps 2 and 4 additionally with a replay.

1. **`measurements.py`** — pure functions, no callers. Zero risk, and it is what
   every later step depends on.
2. **Wire `baseline_rules` into `baseline_service`.** First step that changes
   numbers: capped adaptation and outlier exclusion will move baselines.
   Behaviour differences are expected here and get classified, not suppressed.
3. **`DetectorResult` + registry `layer`** — contract only, no detector adopts it.
4. **Migrate ONE detector** (`revenge_trade`, which already has the contract
   drafted) to the new result type, abstention, and `account_risk` for its
   safety floor. Replay, classify every difference.
5. **Freeze `account_risk` per session** in `_load_context`, consumed by that one
   detector.
6. **Stop** and report before touching detector two.

Step 4 is where the foundation stops being theoretical. If it does not make
`revenge_trade` demonstrably better, the design is wrong and better found at one
detector than twenty-seven.

---

## 4. Testing and replay

- **Unit**: pure primitives, table-driven across the persona set in the contract
  (₹5k scalper → ₹50L trader, and the consistently-losing trader, which is the
  case that breaks self-relative systems).
- **Contract invariants**: a `universal_safety` result may never carry a
  personal-baseline provenance; an abstention may never become an alert.
- **Replay, per your rule — explainable parity, not equality.** Every difference
  classified as: *intended* (a rule we changed), *incidental* (ordering/ties), or
  *unexplained* (stop and investigate). A run with unexplained differences is a
  failed run.
- **Baseline-contamination test**: replay the year, feed confirmed revenge
  sequences back into the gap baseline, assert the baseline does **not** drift
  downward. This is the specific failure mode of a self-relative engine and
  nothing currently tests it.

---

## 5. Performance and scalability

Current per completed trade: 4–5 DB queries in `_load_context`, then 27
detectors over in-memory state. Detectors are pure and cheap; the queries
dominate.

- `account_risk` adds **one** query per *session*, not per trade, because it is
  frozen — that is a performance property of the session-scoping decision, not
  just a correctness one.
- Two baselines (long + recent) roughly double baseline computation, but that is
  nightly and batched, off the hot path entirely.
- The real scale risk is unchanged and already documented: **Kite's 3 req/s is
  per API key and shared across all users**. Margin fetches for the account-risk
  base must go through a throttled worker with a per-day cache, never inline.
- I will **measure** `_load_context` before optimising anything. I have no
  numbers, and the last time I asserted a performance claim without measuring
  (the "5x flush slowdown") I was wrong.

---

## 6. What I think is problematic or overengineered in the specification

1. **Two baselines per metric, for every metric, is premature.** Long + recent
   doubles the state and the reasoning for a product with one live user. The
   *divergence* idea is genuinely good; I would build it for one or two metrics
   where escalation matters (position size, re-entry gap) rather than as a
   universal rule.

2. **"Store multiple normalised values for every trade"** conflates a modelling
   idea with a schema decision. Compute on demand; persist only what proves
   expensive to recompute.

3. **The 13-point checklist applied to all 27 detectors before any code** is
   ~370 specification fields. The `revenge_trade` contract took real effort and
   surfaced two things only writing it revealed. Twenty-seven of those, up front,
   will produce documents nobody re-reads. Contract *the detector you are about
   to change*, immediately before changing it.

4. **Unrealised/live monitoring is presented as new.** It is built
   (`live_position_engine.py`, migration 076, nine tests) and parked on GTT
   visibility. The spec should record the blocker rather than re-propose the
   feature.

5. **The severity ladder in §"alert vs intervention" is capital-relative**
   ("10% of your account") in a document that spends its first third arguing
   against capital as a denominator. Consistent only under the two-layer split —
   worth stating explicitly, because read alone it contradicts the opening
   argument.

6. **One genuine tension I cannot resolve from the document.** It requires
   abstention when evidence is insufficient, *and* universal safety rules that
   fire for brand-new users. Those collide when the safety rule itself needs data
   we lack — a ₹10k loss is only catastrophic *relative to* an account size, and
   with no equity we cannot say. G1 chose to abstain. That is defensible, but it
   means a brand-new user with no margin data gets **no** account-safety
   protection at all, which may not be what the document intends. This needs a
   product decision.
