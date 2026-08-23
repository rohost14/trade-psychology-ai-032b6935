# `revenge_trade` — implementation plan

23 Aug 2026. **Plan only. No code written.** Matrix frozen per review:
(A0,B2) and (A1,B2) → `info`; (A0,B3) and (A1,B3) → `caution`; no other cell moves.

---

## 0. Two dependencies found while planning

Both are facts about the current code, not design choices.

**a. The personal frame needs two baseline metrics that do not exist.**
`baseline_service` computes exactly five: `daily_trades_p75`,
`burst_per_30min_p75`, `reentry_after_loss_p25`, `loss_streak_p60`,
`loss_streak_p85`.

| personal signal | metric needed | status |
|---|---|---|
| gap fast for them | `reentry_after_loss_p25` | **exists** |
| loss unusual for them (P1) | percentile of their own losing-trade sizes | **does not exist** |
| size up for them | percentile/median of their own position sizes | **does not exist** |

Computing a distribution of observed values is not inventing a threshold — it is
measurement. *Which* percentile marks "unusual" is P1 and stays unresolved, so the
metric will be computed and stored while the A2-via-personal route stays abstained
until P1 is decided.

**b. The gap baseline is contaminated today.**
`reentry_after_loss_p25` learns from every re-entry including harmful sequences,
so the detector's own positives drag "normal" downward until it silences itself.
`clean_for_learning(values, excluded_indices)` accepts the argument and **nothing
has ever passed it**.

**Corrected after review — the exclusion source must not be the detector's own
output.** Reading prior `RiskAlert`s would create
`detector → RiskAlert → baseline → detector`: the baseline would depend on what
the detector previously decided, so a threshold change would silently rewrite the
history it is measured against, and a detector that mis-fired once would keep
teaching itself that it was right.

The exclusion is therefore defined **structurally, from the trade record alone**:

> A re-entry gap is excluded from learning when the trade that produced it
> followed a losing trade **and itself closed at a loss**.

Every term is observable in `CompletedTrade` — no alert, no threshold, no
detector verdict. It is a statement about what happened, not about what we said
about it. The same sequence facts already exist on `CompletedTradeFeature`
(`entry_after_loss`, `minutes_since_last_round`), so this is a read of data the
pipeline already produces.

**Documented source of exclusions**: `CompletedTrade` sequence within a session —
prior trade's `realized_pnl < 0`, this trade's `realized_pnl < 0`, ordered by
`exit_time`. Recorded in the baseline output so the exclusion is auditable rather
than implicit.

**c. The registry entry is wrong for the new design.** `revenge_trade` is declared
`uses_constitution=True` and **not** `uses_baseline=True`, though the new design
depends on personal percentiles.

---

## 1. Removed

### Constants

| constant | current value | why |
|---|---|---|
| `revenge_min_loss_inr` | 1% of capital, else ₹500 | capital used as a suppression gate — the defect (8 alerts at ₹50k → 0 at ₹5L) |
| `revenge_min_loss_pct_capital` | 1.0 | only feeds the above |
| `signal_points_critical` | 30 | weighted score |
| `signal_points_high` | 20 | weighted score |
| `signal_points_medium` | 10 | weighted score |
| `signal_points_low` | 5 | weighted score |

Deleted from `COLD_START_DEFAULTS` and from `_CAPITAL_RATIOS` **only after** the
rewrite lands and nothing reads them — the ordering that avoids the class of
failure where a constant is removed while a caller still expects it.

`signal_points_*` are read only by `revenge_trade`; verified before deletion, not
assumed.

### Logic

| removed | why |
|---|---|
| the `min_loss` gate (`if abs(last_pnl) < min_loss: return None`) | §1 of the contract |
| `_typical_loss()` | mislabelled — reads `ctx.session_trades`, so it is session-scoped, presented as personal, and requires 3 losses *today* |
| the additive `confidence` accumulation | replaced by observability-based confidence |
| severity derived from the same signals as confidence | the two axes must not share inputs |
| inline `size_ratio >= 1.5` | B3 uses a plain inequality: larger than the position that lost |

**Kept from the deleted block**: the nested-tier reasoning for
`same_symbol`/`same_underlying`. It is correct and becomes B2's membership rule.

---

## 2. Consumed

First consumer in every case — this is the point of doing this detector first.

| foundation piece | use here |
|---|---|
| `measurements.loss_vs_account` | A3 |
| `measurements.loss_vs_trade` | A2 via trade-relative, per instrument class |
| `measurements.loss_vs_own_losses` | A2 via personal (blocked on P1) |
| `measurements.size_vs_own_sizes` | informational; B3 itself needs no baseline |
| `measurements.gap_vs_own_gaps` | B1 window when mature |
| `evidence.Evidence` / `abstain()` / `Insufficiency` | per-frame abstention |
| `detector_result.DetectorResult` / `Layer` | result type carrying frame + measurements |
| `ctx.account_risk` | A3 denominator — **first reader** |
| `DetectorSpec.frames` | `(ACCOUNT, TRADE, PERSONAL, STRUCTURAL)` — first assignment |
| `safety_bounds.clamp_to_bound` | bounds on P1/P2 once B1 values exist; inert now |
| `clean_for_learning(excluded_indices=…)` | contamination exclusion |
| `EpisodeHint` | declared `role=ESCALATION`, consumed by nothing |

### New inputs

| input | source | new? |
|---|---|---|
| instrument class of the **prior** trade | `instrument_type` + `direction` on `CompletedTrade` | already present, newly read |
| `estimate_capital_at_risk(prior)` | existing helper | newly called for the prior trade |
| own losing-trade size distribution | **new baseline metric** | yes |
| own position-size distribution | **new baseline metric** | yes |
| harmful-sequence indices for learning exclusion | `CompletedTrade` sequence (loss → re-entry → loss), **not** `RiskAlert` — see §0b | yes |

---

## 3. Deliberately unresolved — each abstains, none blocks

| # | governs | behaviour while unresolved |
|---|---|---|
| **S1** | A3 boundary | account frame abstains; A3 unreachable; ceiling is `danger` |
| **S2a** | A2 for long options | trade frame abstains for long options |
| **S2b** | A2 for short options | abstains. Constraint recorded: **S2b < S2a**, from the semantics — SPAN is margin posted, not a loss ceiling |
| **S2c** | A2 for futures | abstains |
| **S2d** | A2 for equity/delivery | abstains — notional is not capital at risk |
| **P1** | A2 via personal | that signal abstains; metric still computed and stored |
| **P2** | B1 window percentile | three explicit states — see below |
| **P4** | `revenge_window_danger_min` | unused by the frozen matrix — B has no danger sub-tier |
| **M1** | maturity per metric | personal signals abstain until decided |
| **B1** | safety-bound values | bounds inert |

With everything above unresolved, the detector still runs: **structural gate →
A0 → B0–B3**, producing `info` up to B2 and `caution` at B3. That is strictly more
honest than today and is the cold-start behaviour the contract promises.

---

### P2 has three states, not two

Conflating "we learned this from you" with "we had nothing, so we used the
default" is how a trader ends up being told *your* limit about a number that was
never theirs.

| state | condition | window used | provenance recorded |
|---|---|---|---|
| **personalised** | metric present and mature | their `reentry_after_loss_p25` | `Source.HISTORY`, confidence from maturity, `personalised: true` |
| **immature** | metric present, sample below M1 | declared fallback | its own existing provenance — `Source.DECLARED` if the trader set a cooldown, else `Source.GLOBAL`; **`personalised: false`** |
| **unavailable** | no metric at all | declared fallback | same as immature, with `Insufficiency.NO_BASELINE` recorded |

The fallback is never relabelled as personal. `threshold_recorder` already emits
`personalised: false` with the reason when a `personal_baseline` Kind resolves
from `global`; the immature and unavailable states reuse that path rather than
inventing a second one.

Copy follows the same split: a personalised window may say "faster than you
usually re-enter"; the fallback may not, and says what it is.

## 4. Sequence

Each step is independently testable and reversible. Replay gates marked.

**Step 1 — engine accepts `DetectorResult` alongside `DetectedEvent`.**
`_run_all_detectors` currently assumes `DetectedEvent` (touches `.shadow`,
`.event_type`, `.suppressed_reason`, `.thresholds_used`). Add an adapter so a
detector may return either; `DetectorResult` carries `layer`, `measurements` and
`evidence` into the stored record. No detector returns the new type yet.
*Behaviour-neutral. No replay needed.*

**Step 2 — two new baseline metrics + contamination exclusion.**
Add the loss-size and position-size distributions; pass `excluded_indices` for
trades belonging to confirmed revenge sequences.
*Changes `reentry_after_loss_p25`, which feeds `revenge_window_caution_min` — a
real behavioural change.* **Replay gate.** Note the replay's lab account carries
no stored baseline, so this path is exercised by
`test_baseline_integration_db.py` rather than by the replay; that limitation is
already documented and must not be presented as a clean result.

**Step 3 — rewrite `_detect_revenge_trade` to the frozen matrix.**
Structural gate → per-frame measurement with abstention → A/B levels → table →
severity; confidence computed from observability. Returns `DetectorResult`.
Registry: `version` → `3.0.0`, `uses_baseline=True`, `frames=(…)`.
*Large behavioural change.* **Replay gate, every difference classified.**

**Step 4 — delete the six constants** once verified unread.
*Behaviour-neutral by construction.* Quick replay to confirm.

---

## 5. Expected behavioural change — predicted before running it

Stated now so the replay is a test rather than a surprise.

**Alerts should fall sharply on the ₹50k tradebook.** The 40-session run produced
8 `revenge_trade` alerts. Under the frozen matrix most will be (A1,B2) — prompt,
same underlying, ordinary loss — which is now `info`. **I expect roughly 0–3
alerts to survive**, the survivors being B3 cases.

**In the other direction, the capital gate is gone**, so a ₹5L account goes from
0 alerts to the same treatment as ₹50k. That is invisible on this tradebook and
must be tested by replaying at a higher capital.

**A drop is the expected outcome, not a regression** — but the burden is on the
diff to show every disappearance is explained by a matrix cell, not by an
accident. Any alert that vanishes for a reason I cannot name in those terms is
`unexplained` and fails the run.

---

## 6. Tests

- **Matrix**: all 16 cells table-driven, asserting severity per (A,B).
- **Non-suppression**: a personal signal, however extreme, never lowers A or B —
  the property the lattice join provides, asserted rather than assumed.
- **Abstention**: each frame abstains independently; missing equity leaves the
  trade frame working; an immature baseline leaves structural working.
- **Instrument classes**: long option, short option, future, spread, equity — the
  first two behave differently on the same ratio; spreads and equity abstain.
- **Cold start**: a trader with one prior trade, no equity, no baseline reaches
  (A0,B3) → `caution` and nothing higher.
- **Scalper**: repeated B2 at A1 produces `info`, not `caution` — the amendment.
- **Severity ≠ confidence**: a `danger` at low confidence is constructible.
- **Negative controls** on the two properties that matter: disable the lattice
  join and the non-suppression test must fail; disable abstention and the
  cold-start test must fail.

---

## 7. Honest risks

**The replay cannot validate the personal frame.** The lab account has no stored
baseline, so P1/P2/maturity paths will not execute during a replay. They are
covered by DB integration tests only. A clean replay is evidence about the paths
it exercised and silent about these — the same limitation recorded for the
baseline work, restated because it applies with more force here.

**`critical` remains unreachable in the field** until `margin_snapshots` has a
producer. The A3 path is implemented and correct; it will simply not fire. Per
your instruction this is an infrastructure issue and does not alter the logic —
but it means step 3's replay cannot exercise A3 either.

**The largest uncertainty is how many alerts survive.** If the answer is 0, the
detector is silent on this trader's whole year and that is a finding about the
matrix, not a success. I will report it as such rather than as parity.
