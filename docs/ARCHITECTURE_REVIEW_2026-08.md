# Behaviour engine — architecture review

Findings only. Nothing here is implemented.

Written 13 Aug 2026, after the L3 retirement, to answer one question before the
pattern-by-pattern pass begins: **is this the right architecture, and does it
work for a trader who is not the one whose tradebook we measured?**

Evidence: the codebase as it stands, plus `docs/GLOBALS_DERIVATION.md` (one
year, 2,175 fills, 203 sessions).

---

## 1. The layers, as built

The code names three. There are four, and the unnamed one is where the bugs live.

| layer | what it does | reads | writes |
|---|---|---|---|
| **L0 — threshold resolution** | `get_thresholds(profile)` merges universal floor → research default → personal baseline → user-declared constitution | `UserProfile`, `detected_patterns["baseline"]` | the `thresholds` dict every detector reads |
| **L1 — detectors** | 27 declarative specs; each fires on its own thresholds, per `CompletedTrade` | primary state + the trade + L0's dict | `RiskAlert` + `BehaviorEvent` |
| **L2 — meta-detector** | `evaluate_death_spiral`: ≥2 distinct nature domains at danger+ inside 180 min | today's `BehaviorEvent`s | its own alert |
| **~~L3 — scores~~** | **removed 2026-08-13** | — | — |
| **L4 — interruption** | mute, staleness, session cap, channel routing, guardian budget | severity + registry metadata | what the trader actually receives |

Two rules hold and are worth keeping: detectors never consume another
detector's output (A.10), and derived state is never an input to detection.
Those rules are why removing L3 could not change what fires.

**L4 has no name in the architecture.** It is spread across `trade_tasks.py`,
the severity module and the registry. Every one of B1–B7 (the structural bugs
closed on 12 Aug — the cap dropping criticals, the budget counting rows instead
of interruptions, muting one pattern silencing others) lived in L4. A layer with
no name has no owner and no test surface, and it is now the layer that decides
everything the trader experiences.

---

## 2. The adaptive layer is the answer to "works for every trader" — and it is half-wired

This is the most consequential finding in this document. The engine is *designed*
to personalise: `get_thresholds` implements a continuous confidence blend,

    effective = confidence × personal + (1 − confidence) × default

with per-metric confidence = `min(1, n / target)` — deliberately no activation
cliff, so a trader with 3 sessions gets defaults and one with 40 gets their own
numbers. That design is sound. It substantially does not run.

### 2.1 Two writers, one key, incompatible shapes

| writer | trigger | shape |
|---|---|---|
| `behavioral_baseline_service.compute_and_store` | Zerodha sync/connect, manual API | **flat**: `daily_trade_limit`, `burst_trades_per_15min`, `revenge_window_min`, `consecutive_loss_caution`, `consecutive_loss_danger`, `session_count` |
| `ai_personalization_service` (→ `baseline_service.compute_baseline`) | analytics / personalization endpoints | **`{"metrics": {…}}`**, 9 metrics each with `value`, `confidence`, `n`, `stddev` |

Both write `user_profile.detected_patterns["baseline"]`. `get_thresholds`
branches on which shape it finds: `metrics` present → Phase 3 blend; otherwise →
a legacy branch that assigns flat values directly, with **no confidence and no
blend**.

So which personalisation algorithm a trader gets depends on which service wrote
last. That is not a tunable; it is a race.

There is a second-order effect: `behavioral_baseline_service` skips recompute if
`existing["computed_at"]` is under 24h old, and *both* shapes carry
`computed_at`. Each writer's freshness guard can be satisfied by the other
writer's timestamp.

### 2.2 The legacy branch drops 2 of its 5 values on a name mismatch

| written | looked for | transfers |
|---|---|---|
| `daily_trade_limit` | `daily_trade_limit` | yes |
| `consecutive_loss_caution` / `_danger` | same | yes |
| `burst_trades_per_15min` | `burst_trades_per_30min_caution` | **no** |
| `revenge_window_min` | `revenge_window_caution_min` | **no** |

Different names, different windows (15 vs 30 min). No exception, no log — the
keys simply never match, and two personalised thresholds silently stay at their
research defaults.

### 2.3 Nothing recomputes on a schedule

`api/profile.py:804` describes the baseline as running "nightly". There is no
beat entry for either service. It is opportunistic, behind a 24h guard that the
other writer can satisfy. A trader who stops opening the app stops adapting.

### 2.4 The `uses_baseline` map is wrong in 4 of 27

`DetectorSpec.uses_baseline` is the declared map of which detectors adapt to the
trader. Checked against what each detector actually reads:

| detector | declares | reality |
|---|---|---|
| `consecutive_loss_streak` | `uses_baseline=True` | reads `consecutive_loss_caution/danger` + `daily_loss_limit` — **the blend touches none of them** |
| `expiry_day_overtrading` | `uses_baseline=True` | reads `expiry_overtrading_*` — never blended |
| `winning_streak_overconfidence` | `uses_baseline=True` | uses a **session-local** average quantity, not the personal baseline |
| `revenge_trade` | **does not declare it** | reads `revenge_window_caution_min`, which **is** blended |

### 2.5 Nine metrics computed, three wired

`baseline_service` computes `avg_daily_trades`, `typical_peak_pnl`,
`typical_drawdown`, `median_reentry_after_loss_min`, `avg_winner_hold_min`,
`avg_loser_hold_min`, `win_rate`, `profit_factor`, `median_position_risk_pct`.

Three reach a threshold (`daily_trade_limit`, `burst_*`,
`revenge_window_caution_min`). Two more are passed through as raw values
(`baseline_win_rate`, `baseline_profit_factor`). **Four are computed, stored, and
read by nothing** — including `typical_drawdown` and `median_position_risk_pct`,
which are the two most obviously useful for sizing and risk patterns.

---

## 3. Reading it from each seat

**Trader.** The product's claim is "this is *your* pattern." For most detectors
it is currently "this is the pattern of a trader we imagined." Two of my
personalised numbers are dropped on a typo-class mismatch, and which
personalisation I get depends on which endpoint I last visited. If I trade 40
lots a day and the default assumes 6, the alerts are noise; if I trade twice a
week, they never fire.

**Quant.** The architecture's separation is correct and unusually disciplined —
the derived-state ban is exactly right, and it is why L3 could be removed
safely. The defect is that the calibration unit is the *population* when it
should be the *individual*. The measured example: SEBI's ">6 trades/day → 94%
loss" does not reproduce on this trader, whose busy days end negative **48%** of
the time against a 56% baseline. A global constant encoding a population claim is
wrong for any individual by construction; the only defensible global is a
*prior*, to be displaced by the trader's own distribution.

**Mathematician.** `confidence = min(1, n/target)` is a reasonable shrinkage
estimator and the continuous blend has no cliff, which is right. Two gaps: it
shrinks toward a default that carries no uncertainty of its own, and the metric
is a median with a stored `stddev` that nothing consumes — so a trader whose
daily count is 6±1 and one whose is 6±9 get identical thresholds. Dispersion is
available and discarded.

**Analyst.** Four computed-and-unread metrics, and the two most useful ones
(`typical_drawdown`, `median_position_risk_pct`) are among them. The data to
personalise sizing and drawdown patterns is already being produced.

**Engineer.** Two writers on one JSONB key with no schema version is the root
cause of §2.1 and §2.2 and will cause the next one too. The fix is a version tag
and a single writer, not more careful key names.

**Product.** Cold start is a hard constraint, not an edge case: Kite returns no
trade history, so every new user starts with zero baseline and only Console CSV
import can fill it. That makes the defaults genuinely load-bearing for day one —
and makes it essential that the code says which numbers are defaults and which
are earned. Right now `get_thresholds` returns one flat dict where the two are
indistinguishable.

---

## 4. What I would change, in order

**C1 — one writer, one shape, versioned.** Collapse the two baseline services
into one that writes `{"version": 2, "metrics": {...}}`. `get_thresholds` reads
`version` rather than sniffing shape. Delete the legacy branch once nothing
writes v1. *This alone fixes §2.1 and §2.2.*

**C2 — schedule it.** One nightly beat task, batched over active accounts.
Opportunistic recompute on sync is a scale hazard at 10k users and a
correctness hazard at 1.

**C3 — make the threshold dict self-describing.** Return
`{value, source: "floor"|"default"|"personal"|"declared", confidence}` per key
instead of a bare number. Detectors keep reading `.value`. This buys three
things at once: the `uses_baseline` map becomes derivable instead of hand-
maintained (fixing §2.4 permanently), the UI can honestly say "your number" vs
"our starting number", and cold-start behaviour becomes inspectable.

**C4 — wire the four dead metrics, or delete them.** `typical_drawdown` and
`median_position_risk_pct` should drive the sizing and drawdown detectors. If
they will not be used, stop computing them.

**C5 — use dispersion, not just the median.** Where a threshold means "unusual
for you", it should be a percentile or a z-score of the trader's own
distribution, not `median × 1.5`. `stddev` is already stored.

**C6 — name L4 and give it a home.** The interruption layer decides everything
the trader experiences and is currently scattered. It is also where the
measured problem now sits: `docs/GLOBALS_DERIVATION.md` found `danger` alerts
are followed by *better*-than-baseline sessions (−10 lift, widening to −12 at
fixed horizon), so the axis L4 uses to decide loudness is inverted. That is a
question about **what severity should mean**, and it should be settled before
the pattern-by-pattern pass, because every pattern inherits the answer.

**C7 — do not reintroduce per-pattern weights without measuring them first.**
The retired set ranked 2 of 14 against measured cost. If a weight ever returns,
derive it (`tradedesk/scripts/derive_constants.py`) and store the evidence next
to the number.

---

## 5. What is genuinely good and should not be touched

- The **derived-state ban** and the no-detector-consumes-a-detector rule. These
  are why L3 came out cleanly, and they are rarer in practice than they sound.
- The **declarative registry**. Adding a detector is one spec plus one method;
  the engine iterates the list rather than a hardcoded chain.
- **Per-detector versioning** with alerts storing the version that produced
  them, so a threshold change never silently reinterprets old alerts.
- The **continuous confidence blend** as a design. It is the right shape. It
  just needs to actually run.
- **Feature flags per detector** (`off/shadow/canary/on`) — the safe path for
  changing any detector in the pattern pass that follows.

---

## 6. Open question this review cannot settle

What should `severity` mean, now that it does not predict? Two candidates:

1. **How much the behaviour has already cost** — a fact, consistent with the
   project's existing rule that behaviour-to-money is realised P&L of flagged
   trades and never a counterfactual.
2. **How confident we are the pattern is real** — moving severity onto the
   confidence axis that G3 found is inert for 26 of 27 detectors.

Both are defensible. It is a product decision, it governs L4, and every
per-pattern decision inherits it — so it comes first.
