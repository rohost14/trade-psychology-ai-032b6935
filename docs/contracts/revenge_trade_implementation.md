# `revenge_trade` — final implementation contract

23 Aug 2026. **Proposal. Nothing implemented.** Supersedes the first draft of this
file. The conceptual contract (`revenge_trade.md`) remains the *what*; this is the
*how*, revised after review.

Five changes from the draft, all from the review:

1. Unresolved thresholds no longer block the detector. Each frame activates
   independently and abstains alone.
2. Trade-relative risk is instrument- and strategy-aware. A single percentage
   across long options, short options, futures and spreads is provably wrong —
   §4 shows why, from the estimator's own code.
3. `EpisodeRole`/`EpisodeHint` kept as an interface. No state machine.
4. Safety bounds stay as machinery with no values.
5. `confidence_alert_gate` is an engine decision, not this detector's.

---

## 1. The defect this detector exists to correct

`revenge_min_loss_inr` resolves to **1% of capital** and is used as a **gate**:

```python
min_loss = ctx.thresholds.get("revenge_min_loss_inr", 500)
if abs(last_pnl) < min_loss:
    return None            # bigger account → higher bar → less protection
```

Measured on 40 sessions, only capital changed: **8 alerts at ₹50k, 0 at ₹5L.**

Account-relative measurement is a reason to **fire**, never a reason to stay
quiet. It moves to the safety trigger and is removed from the gate.

---

## 2. Decision tree

Read top to bottom. Each frame is evaluated independently; none can suppress
another; any may abstain alone.

```
STRUCTURAL GATE — no thresholds, no history, no capital
├─ prior CompletedTrade exists in this session, closed BEFORE current entry?
│    no  → NOT_DETECTED  ("no re-entry to judge")
├─ prior trade closed at a loss (realized_pnl < 0)?
│    no  → NOT_DETECTED
├─ entry_time and prior exit_time both present, gap ≥ 0?
│    no  → ABSTAIN (Insufficiency.MISSING_INPUT — timestamps unusable)
└─ strategy_group present and this trade is a leg?
     yes → SUPPRESSED (existing behaviour, unchanged)

  ↓ structural fact established: a loss, then a re-entry, N minutes later.
    This alone is reportable at `info` and needs nothing else.

SAFETY — objective harm. Never learns. Nothing personal may suppress it.
├─ ACCOUNT-RELATIVE
│   ├─ ctx.account_risk.is_usable?          no → abstain (this frame only)
│   ├─ S1 decided?                          no → abstain (this frame only)
│   └─ loss_vs_account(prior_loss) ≥ S1     → SAFETY BREACH
└─ TRADE-RELATIVE                            (see §4 — per instrument class)
    ├─ instrument class resolvable?         no → abstain (this frame only)
    ├─ class is SPREAD/hedged?              yes → abstain (denominator invalid)
    ├─ S2[class] decided?                   no → abstain (this frame only)
    └─ loss_vs_trade(prior_loss) ≥ S2[class] → SAFETY BREACH

PERSONAL — unusual for them. Requires maturity. Bounded.
├─ loss unusual?   percentile(own losses)   immature → abstain (signal only)
├─ gap fast?       percentile(own gaps)     immature → abstain (signal only)
└─ size up?        ratio(own sizes)         immature → abstain (signal only)

DECLARED — their own commitment
└─ cooldown_after_loss set and gap < it     → BREACH (a fact, not an estimate)
```

**Output rule.** The detector emits when the structural gate passes. Severity is
set by what else was established (§7). A detector that establishes only the
structural fact emits `info`: recorded as evidence, never notified.

This is the change from the draft — the detector is never blocked by an
unresolved threshold. It reports what it can see and abstains, per frame, on what
it cannot.

---

## 3. Inputs

| input | source | absent → |
|---|---|---|
| prior `realized_pnl`, `exit_time` | `CompletedTrade` (session) | NOT_DETECTED / abstain |
| current `entry_time` | `CompletedTrade` | abstain |
| `instrument_type`, `direction`, `avg_entry_price`, `total_quantity` | `CompletedTrade` | trade-relative frame abstains |
| `tradingsymbol` both sides | `CompletedTrade` | same-instrument signal abstains; others unaffected |
| account equity | `ctx.account_risk` (frozen per session) | account frame abstains |
| own loss / gap / size distributions | baseline, long window | that personal signal abstains |
| `cooldown_after_loss` | profile | declared frame silent (not an abstention — no commitment made) |
| `strategy_group` | `ctx.strategy_group` | no suppression |

---

## 4. Trade-relative risk is not one number

`estimate_capital_at_risk` returns different *kinds* of quantity per instrument,
and a single S2 percentage across them is wrong. From the code:

| class | denominator returned | what it means | is 100% loss possible? |
|---|---|---|---|
| **Long option** (LONG CE/PE) | premium paid — **exact** | the maximum possible loss | **Yes, routinely.** Expiring worthless is a normal outcome |
| **Short option** (SHORT CE/PE) | SPAN ≈ 12–20% of notional | **margin posted**, not a loss ceiling | Loss is **unbounded**; losing 100% of margin is near-catastrophic |
| **Futures** | SPAN ≈ 12–20% of notional | margin posted | Unbounded both ways |
| **Spread / hedged** | over-estimated (docstring says so) | denominator too large | ratio understated → detector under-fires |
| **Equity / unknown** | full notional | delivery value | ~never; ratio always tiny → frame never fires |

So "lost 80% of capital at risk" means two completely different things: a long
option buyer having a bad but ordinary day, and a short seller in serious trouble.
**One threshold cannot carry both.**

Consequences for this contract:

- **S2 becomes S2[class]**, one decision per class, each unresolved (§8).
- **Spreads abstain.** The docstring already admits the denominator is wrong; an
  understated ratio would produce a confident false negative, which is worse than
  silence. `ctx.strategy_group` identifies these.
- **Equity abstains** until someone decides what trade-relative risk means for
  delivery. Notional is not it.
- The stored evidence must record **which class and which denominator** were used
  (`Measurement.denominator_label` carries this), or the alert cannot be checked.

---

## 5. Cold start

| frame | trade 1 | why |
|---|---|---|
| Structural | **works** | needs no numbers at all |
| Trade-relative | **works for long options**, subject to S2 | premium paid is exact from the first trade |
| Trade-relative | abstains for spreads and equity | §4 |
| Account-relative | works **iff** equity known and S1 decided | otherwise abstains |
| Personal | **abstains** | three points is not a distribution |

A brand-new trader therefore gets the structural observation immediately, plus
trade-relative safety on long options — the most common F&O retail instrument —
and account-relative safety when we can see the account.

**Infrastructure blocker, stated again because it gates the account frame in
production:** `margin_snapshots` has no scheduled producer, so `ctx.account_risk`
reaches GOOD only if the trader loaded a page that fetched margins. Until that is
resolved the account frame will mostly abstain in the field regardless of S1.
Product decision, not a detector one.

---

## 6. Maturity, abstention, and bad habits

**Maturity is per metric.** Each personal signal carries its own counter and
abstains alone; there is no global "baseline ready" flag.

**Abstention is a first-class outcome.** `Evidence` / `Insufficiency` distinguish:

- `NOT_DETECTED` — no loss, or no re-entry. We looked and it did not happen.
- `ABSTAINED` — we could not see. Never rendered as an alert, always recorded.

Today `None` means both, which is why the 203-session replay cannot distinguish a
clean year from an unmonitored one.

**Three defences against habit becoming licence:**

1. **Frame separation.** Safety reads account- and trade-relative only. No
   personal input can reach it, enforced by `violates_kind` once the safety
   thresholds are classified `universal_safety`.
2. **Safety bounds**, with direction declared per key:
   - re-entry window — `HIGHER_IS_STRICTER`; the habitual fast re-enterer has a
     low p25 that shrinks their window to nothing. Bound is a **minimum**.
   - loss-meaningfulness percentile — `HIGHER_IS_LOOSER`; large habitual losses
     raise their own p60. Bound is a **maximum**.
   **Values unresolved (B1). Machinery only.**
3. **Contamination exclusion.** Confirmed revenge sequences must not train the gap
   baseline, or the detector's positives drag "normal" down until it silences
   itself. `clean_for_learning(values, excluded_indices)` accepts this argument
   and **nothing has ever passed it**. Wiring it is part of this work.

---

## 7. Severity and confidence

**Severity = harm if the behaviour is real.** From the safety frames only.

| severity | condition |
|---|---|
| `critical` | safety breach **and** the new position is larger than the one that lost |
| `danger` | safety breach in either safety frame |
| `caution` | no safety breach; mature personal signals present |
| `info` | structural fact only, or personal signals immature |

**Confidence = how well we could see it.** From data quality, how many frames
were measurable, how mature the percentiles were, whether the symbol parsed.

Neither derives from the other. Severity may be `danger` at low confidence; that
combination is exactly what the two axes exist to express.

**Removed: the points system.** `signal_points_critical/high/medium/low`
(30/20/10/5) summed across incommensurable observations to produce a number that
gated whether the trader was told anything. Four invented weights, no derivation —
L3 in miniature. Every argument that retired the behaviour score applies verbatim.
The replacement is not a better weighting; it is to stop summing.

**Kept from that block**: the reasoning that `same_symbol` and `same_underlying`
are nested rather than independent, so they are exclusive tiers. That argument is
correct, and it is also the argument for deleting the arithmetic around it.

**`confidence_alert_gate` (50) is out of scope.** It affects every detector and
belongs to the engine review. This contract does not change it and does not depend
on its value: severity is set by harm, and the gate's rewrite-to-`info` behaviour
applies afterwards as it does today.

---

## 8. Old → new threshold mapping

| current | value | disposition |
|---|---|---|
| `revenge_min_loss_inr` | 1% of capital / ₹500 | **DELETE** — capital as suppression (§1) |
| `revenge_min_loss_pct_capital` | 1.0 | **DELETE** with it |
| `revenge_window_caution_min` | 20 (or own p25) | **KEEP**, reclassify `personal_baseline`, add bound direction `HIGHER_IS_STRICTER` |
| `revenge_window_danger_min` | 5 | **UNRESOLVED (P4)** — already flagged mandatory-review |
| `signal_points_*` ×4 | 30/20/10/5 | **DELETE** (§7) |
| `_typical_loss` (inline, 3 losses, session-scoped) | — | **DELETE** — mislabelled; replaced by the personal frame over the baseline window |
| size-escalation `1.5` (inline literal) | 1.5 | **UNRESOLVED (P3)** — or derived from their own size distribution, removing the constant |
| `confidence_alert_gate` | 50 | **UNCHANGED** — engine-level |
| `cooldown_after_loss` | user-set | **UNCHANGED** — `user_rule`, already correct |

### Unresolved decisions

| # | decision | what would settle it | blocks |
|---|---|---|---|
| **S1** | account-relative trigger: prior loss ≥ ?% of equity | product decision on what counts as account damage. Cannot be derived from one tradebook whose capital moved ₹30k–₹50k | account frame only |
| **S2a** | long option: loss ≥ ?% of premium paid | research — a 100% premium loss is routine, so the line is not obvious | trade frame, long options |
| **S2b** | short option: loss ≥ ?% of SPAN posted | research — unbounded downside, different meaning entirely | trade frame, short options |
| **S2c** | futures: loss ≥ ?% of SPAN posted | research | trade frame, futures |
| **S2d** | equity/delivery: what is capital at risk at all? | product — notional is not it | trade frame, equity |
| **P1** | percentile marking a loss "meaningful for them" | measurable against the tradebook | personal signal only |
| **P2** | percentile marking a gap "fast for them" | measurable against the tradebook | personal signal only |
| **P3** | size-escalation multiple, or derive it | measurable | personal signal only |
| **P4** | `revenge_window_danger_min` | mandatory review | severity split within personal |
| **M1** | maturity thresholds per metric | sample-stability check, not yet run | personal frame |
| **B1** | safety-bound values and directions | evidence + product. **Deliberately empty** | bounds inert until set |

**None of these blocks the detector.** Each disables exactly one frame or signal,
and that frame abstains and says so. This is the substantive change from the
draft.

---

## 9. Evidence and explainability

Reconstructible from stored data alone:

- trigger: prior trade id, its loss, its exit time, current entry time, the gap
- per frame: the `Measurement` — value, denominator, `denominator_label`,
  quality, and for personal signals the sample size
- **which instrument class was used for the trade-relative denominator**, since
  the same ratio means different things per class (§4)
- every abstention, with its `Insufficiency` reason
- the thresholds it was judged against — already stored via `_thresholds`
- when a safety bound held a personal value back, that fact and its reason

Copy must never say "your limit" about a number that is not the trader's; the
`personalised: false` marker exists for this.

---

## 10. Episodes — interface kept, machine not built

`revenge_trade` is the archetypal episode participant: a loss (trigger), a fast
re-entry (escalation), a larger position (escalation), a second loss (terminal)
are four detections of **one** behavioural event, and a trader should be told once
about the event rather than four times about its parts.

So the detector will **declare** `EpisodeHint(role=ESCALATION, key=<underlying +
session>)`. Nothing consumes it. That costs one field and no machinery, and it
means the data exists when episodes are built.

**The open question stays open**: an episode needs a lifetime, the session
boundary is the honest candidate, and a position held overnight makes it wrong.
That is the design problem to solve before anything consumes the hint, and it is
why nothing does yet.

---

## 11. Across capital bands and styles

| trader | today | proposed |
|---|---|---|
| **₹5,000** | floor ₹50 — nearly every loss qualifies; noisy | structural always; trade-relative on long options; personal after maturity; account-relative on genuine account damage |
| **₹50,000** | floor ₹500 — the band it was tuned on; 8 alerts / 40 sessions | similar volume, arbitrary floor replaced by their own distribution |
| **₹5,00,000** | floor ₹5,000 → **0 alerts** | fires normally — percentiles are scale-free |
| **₹50,00,000** | floor ₹50,000 → silent | same |

| style | risk | defence |
|---|---|---|
| Scalper, 90-second tempo | every re-entry looks fast | percentile of **their own** gaps — 90s is their p50 |
| Positional, 2 trades/week | never matures | personal abstains; structural and safety continue |
| Options seller, multi-leg | legs seconds apart | strategy-group suppression; spread denominators abstain (§4) |
| Systematic re-entry at a level | fast, same instrument, bigger | **no defence.** Intent is unobservable — a known, accepted false positive |

---

## 12. Foundation: consume and remove

**First consumer of** — this is the validation:

`measurements.py` (all four families) · `evidence.py` (per-signal abstention) ·
`DetectorResult` + `Layer` · `ctx.account_risk` · `DetectorSpec.frames =
(ACCOUNT, TRADE, PERSONAL, STRUCTURAL)` · `safety_bounds` (inert until B1) ·
`clean_for_learning(excluded_indices=…)` · `EpisodeHint` (declared, unconsumed).

**Removed**: `signal_points_*` ×4, `revenge_min_loss_inr`,
`revenge_min_loss_pct_capital`, `_typical_loss`, the inline `1.5`.

**Still without a consumer after this work**, and honestly so: baseline
`divergence`; `max_drawdown` and `longest_loss_run` (baseline-side, not used
here). If nothing claims `divergence` by the third detector, delete it.

---

## 13. Critical assessment

**What this contract gets right that the draft did not.** Frames now degrade
independently. The draft made the whole detector contingent on S1/S2; this one
ships structural on day one for everybody, trade-relative for long options as
soon as S2a is decided, and account-relative when both the number and the
denominator exist. Unresolved never means silent-and-unexplained — it means
abstained-and-recorded.

**The instrument split is the finding of this revision.** A single trade-relative
percentage across long options, short options, futures, spreads and equity is not
a simplification, it is an error: the estimator returns a *loss ceiling* in one
case and *margin posted* in another, and 80% of each are not comparable events.
The draft would have shipped that.

**What remains genuinely unresolved and matters most**: S2a. It governs the only
safety frame available to a brand-new long-option buyer, which is the most common
retail F&O position in this market. If nothing else is decided, decide that.

**What I would still delete but am keeping on your instruction**: nothing —
`EpisodeHint` as a declared field with no consumer is a fair call, and cheaper
than I argued. I would revisit it if a second detector cannot state its role
without inventing one.

**The honest limit.** This makes `revenge_trade` structurally correct and
explainable. It does not make it *validated*. Validation needs the ₹50k tradebook
replayed with the new logic, every difference classified, and a judgement about
which days the trader would themselves call revenge. Only `heeded` can settle it,
and that is live data nobody has yet.
