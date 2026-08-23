# `revenge_trade` — final implementation plan

23 Aug 2026. **Plan only. No code.** Supersedes `revenge_trade_implementation_plan.md`,
which was written before F1–F5 existed. The frozen contract
(`revenge_trade_implementation.md`) is unchanged and remains the specification.

What changed since that plan: the foundation it assumed is now built, so three
things it described as "declared maturity", "confidence from observability" and
"per-class handling" now have concrete APIs — `maturity.assess()`,
`confidence.from_observables()` and `instrument_risk.risk_basis()` with
`loss_vs_risk_basis()`. The plan below is written against those rather than
against intentions.

---

## 1. What stays

Unchanged, and deliberately so — these are the parts of the current detector that
are right.

| kept | why |
|---|---|
| The structural trigger: prior trade closed at a loss, current entered after it | Observable, needs nothing, correct |
| `strategy_group` suppression | Multi-leg entries seconds apart are a structure, not a re-entry. Already built |
| The nested `same_symbol` / `same_underlying` tiers | Exclusive, not additive — the one genuinely well-argued line in the block being deleted. Becomes B2's membership rule |
| `cooldown_after_loss` as a declared rule | `user_rule` Kind, already correct |
| Consolidation placement — behind `same_symbol_obsession`, ahead of `rapid_reentry`, absorbed by `death_spiral` | Unvalidated but out of scope; changing it would confound the replay |
| The 24-hour per-pattern dedup | Keeps the accepted systematic-re-entry false positive to one alert a day |

## 2. What is deleted

| deleted | reason |
|---|---|
| `revenge_min_loss_inr` (1% of capital / ₹500) | Capital used as a **suppression gate** — the defect. 8 alerts at ₹50k, 0 at ₹5L |
| `revenge_min_loss_pct_capital` | Feeds only the above |
| `signal_points_critical/high/medium/low` (30/20/10/5) | The old score in miniature: invented weights summed over non-independent observations, gating whether the trader is told anything |
| `_typical_loss()` | Mislabelled — reads `ctx.session_trades`, so it is session-scoped and presented as personal, and needs 3 losses *today* |
| The additive `confidence` accumulation | Replaced by `confidence.from_observables` |
| Severity derived from the signals that feed confidence | The two axes must not share inputs |
| The inline `size_ratio >= 1.5` | B3 is a plain inequality — larger than the position that lost. One fewer invented number |

Constants are removed from `COLD_START_DEFAULTS` and `_CAPITAL_RATIOS` **only
after** the rewrite lands and a grep confirms no reader remains.

## 3. What is redesigned

### 3a. Structure — one gate, then independent frames

```
STRUCTURAL GATE          no thresholds, no history, no capital
  → NOT_DETECTED / ABSTAIN(MISSING_INPUT) / SUPPRESSED(strategy leg)

SAFETY     account:  loss_vs_account(prior_loss, ctx.account_risk)   → A3
           trade:    loss_vs_risk_basis(prior_loss, risk_basis(...)) → A2
PERSONAL   loss / gap / size percentiles, each gated by maturity.assess → A2, B1
DECLARED   cooldown_after_loss breach → floor of caution
```

Each frame abstains alone. None can suppress another.

### 3b. Severity — the frozen matrix, read not computed

`A` = highest level any magnitude frame establishes. `B` = highest reaction level.
Both lattice joins, so an abstaining frame can never lower a level and personal
history can only raise one.

| | B0 | B1 prompt | B2 targeted | B3 escalated |
|---|---|---|---|---|
| **A3** | caution | danger | danger | critical |
| **A2** | info | caution | danger | danger |
| **A1** | info | info | info | caution |
| **A0** | info | info | info | caution |

`severity = max(table[A][B], caution if declared_breach else info)`

### 3c. Confidence — separate, and shared

`confidence.from_observables(data_quality, sample_confidences, inputs_parsed)`.
The weakest link. Never feeds the table.

### 3d. Trade-relative, per instrument class

`risk_basis()` labels the denominator; `loss_vs_risk_basis()` abstains when
`is_comparable` is false. Spreads and unclassifiable instruments therefore
abstain **mechanically**, not by a rule written in the detector.

### 3e. Registry

`version` → `3.0.0`; `uses_baseline=True`; `frames=(ACCOUNT, TRADE, PERSONAL,
STRUCTURAL)` — the first assignment. Returns `DetectorResult`.

### 3f. Episode

Declares `EpisodeHint(role=ESCALATION, key=underlying+session)`. Consumed by
nothing.

## 4. Unresolved — each abstains, none blocks

| # | governs | while unresolved |
|---|---|---|
| S1 | A3 boundary | account frame abstains; A3 unreachable |
| S2a–d | A2 via trade-relative, per class | that class abstains. **S2b < S2a** is derivable, not invented: SPAN is margin posted, not a loss ceiling |
| P1 | A2 via personal | signal abstains; the distribution is already recorded and inert |
| P2 | B1 window percentile | three states — personalised / immature / unavailable, the last two using the declared fallback with its own provenance and `personalised: false` |
| M1 | maturity per metric | every personal signal abstains, since `assess()` returns UNAVAILABLE with no requirement declared |
| B1 | safety-bound values | bounds inert |

**When S1/S2 are decided they must be registered as `universal_safety`** — F1 made
that classification real, so `violates_kind` will then refuse to let them be
learned from the trader they protect.

## 5. How replay validates this

### 5a. What replay can and cannot exercise

The lab account has **no stored baseline and no margin snapshot**, and S1/S2 are
undecided. Therefore, during replay:

- account frame → abstains (no equity)
- trade frame → abstains (S2a–d undecided)
- personal frames → abstain (no baseline, and no maturity requirement declared)

**So `A` is necessarily `A0` for every alert in the replay.** Severity is fully
determined by `B`, and only the A0 row of the matrix is exercised.

That yields a hard, falsifiable structural prediction:

> **Every surviving `revenge_trade` alert must be `caution`, and must be a B3
> case — a re-entry on the same underlying, inside the window, with a larger
> position than the one that lost. No `danger` and no `critical` can occur.**

The current run has 7 caution and **1 danger**. The danger alert must disappear,
and its disappearance is explained by exactly one thing: `danger` requires A2 or
A3, and both are unreachable when equity and S2 are unavailable.

### 5b. Classification rule for every difference

Each difference must map to a named cell, or the run fails:

| class | meaning |
|---|---|
| **intended** | maps to a matrix cell, stated as `(A_level, B_level) → severity`. Example: "was caution, now info: A0 because all magnitude frames abstained, B2 because same underlying but no size increase" |
| **incidental** | ordering or tie-break only; no count, pattern or severity change |
| **unexplained** | anything I cannot name in those terms. **One unexplained difference fails the run** |

A disappearance that I can only describe as "the new logic is stricter" is
unexplained, not intended.

### 5c. What a clean replay would and would not prove

It would prove the structural and B-axis logic behaves as specified on a year of
real trades.

It would prove **nothing** about the account frame, the trade frame, the personal
frames, maturity, bounds or the A-axis above A0 — none of which the replay can
reach. Those rest entirely on DB and unit tests, and that separation will be
stated in the result rather than glossed.

### 5d. Second replay at a different capital

Because the deleted defect was capital-dependent, a second run at `--capital
500000` is required. Prediction: **identical to the ₹50k run**, because no
surviving path divides by capital. Today the same comparison gives 8 vs 0.

### 5e. Tests carrying what replay cannot

All 16 matrix cells table-driven · the lattice-join non-suppression property, with
a negative control · per-frame abstention · the five instrument classes · cold
start reaching (A0,B3) → caution and nothing higher · the scalper reaching B2 at
A1 → info · a `danger` constructible at low confidence.

## 6. Sequence

1. Rewrite `_detect_revenge_trade` to return `DetectorResult`; registry to `3.0.0`.
2. Full suite.
3. **Replay gate** at ₹50k — classify every difference.
4. **Replay** at ₹5L — expect identical to (3).
5. Delete the six constants once no reader remains; quick replay to confirm.

## 7. Honest risks

**The most likely outcome is a large drop in alerts**, because the replay can only
reach the A0 row and only B3 produces a visible alert there. If the answer is
zero, `revenge_trade` is silent on this trader's entire year — and that is a
finding about the matrix, not a success. I will report it as such.

**The detector will be more honest and less capable until S1/S2a are decided.**
It trades a wrong signal for no signal in the trade and account frames. That is
the right direction and it is still a reduction in coverage, which should be
stated to you plainly rather than framed as progress.
