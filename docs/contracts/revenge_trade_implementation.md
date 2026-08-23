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

**Severity = harm if the behaviour is real**, read from the two-axis table in
§7A. Trigger magnitude alone never sets it: a large loss is evidence about what
they were reacting to, not proof that the reaction was revenge.

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

---

## 7A. How the evidence combines — exact decision logic, no score

**The semantic correction this section exists for.** A large prior loss is
evidence about the **size of the trigger**. It is not evidence that a re-entry was
revenge, and it is not severity on its own. `S2a` does not mean "80% of premium
lost = revenge trade". It means "the loss they were reacting to was large in
trade-relative terms" — and that signifies only once the structural gate has
already established that a re-entry followed.

So the detector reasons on **two ordinal axes** and reads a table. No sum, no
weight, no count of signals.

### Axis A — trigger magnitude: how big was the thing they reacted to

Levels are named claims, each with a stated membership rule. `A` is the
**highest level any frame establishes** — a lattice join, never an average.

| level | established when | frame |
|---|---|---|
| **A0** `unquantified` | every magnitude frame abstained | — |
| **A1** `ordinary` | at least one frame measured the loss and none reached A2 | any |
| **A2** `large` | trade-relative ratio ≥ `S2[class]` **or** loss ≥ their own `P1` percentile | trade / personal |
| **A3** `account_threatening` | account-relative ratio ≥ `S1` | account |

Two properties follow from taking the maximum, and both are the point:

- **An abstaining frame can never lower A.** Missing equity cannot reduce the
  severity of a large trade-relative loss.
- **Personal history can only raise A, never lower it.** "This is normal for them"
  is unreachable — no rule in the logic removes a level. That is the
  non-suppression guarantee, structural rather than promised.

### Axis B — reaction structure: how much does the re-entry look like a reaction

Levels are conjunctions of observable facts, ordered by **specificity of the
claim**, not by how many facts are true.

| level | established when |
|---|---|
| **B0** `unrelated` | re-entry outside the caution window, or a different underlying with no other tie |
| **B1** `prompt` | re-entry inside the caution window |
| **B2** `prompt_and_targeted` | B1 **and** same underlying (the exact same symbol is the stronger tier of that same fact, never both) |
| **B3** `prompt_targeted_and_escalated` | B2 **and** the new position is larger than the one that lost |

B2 and B3 are **nested**: B3 is unreachable without B2. That is precisely why they
are levels and not points — the observations are not independent, so adding them
was never valid.

### The table

Severity is read from (A, B). Every cell is a stated decision.

| | **B0** unrelated | **B1** prompt | **B2** targeted | **B3** escalated |
|---|---|---|---|---|
| **A3** account-threatening | `caution` | `danger` | `danger` | `critical` |
| **A2** large | `info` | `caution` | `danger` | `danger` |
| **A1** ordinary | `info` | `info` | `info` | `caution` |
| **A0** unquantified | `info` | `info` | `info` | `caution` |

**Amended after persona validation** — see §7A.1. The two B2 cells were `caution`
in the first draft; a scalper reaches B2 dozens of times a day as ordinary tempo,
and with no magnitude established there is nothing to separate that from tilt.

The corners, because a table is only as good as its edges:

- **(A3, B0)** — an account-threatening loss with no re-entry pattern is
  `caution`, not `danger`. This detector is about the *reaction*; without one
  there is nothing here to call revenge. The loss itself is another detector's
  business.
- **(A0, B3)** — fast, same underlying, larger position, and the loss could not be
  sized at all: `caution`. The structure is real and observable; the harm is not
  established, so it does not escalate. **This is the cold-start cell, and it
  fires on day one.**
- **(A3, B3)** — the only `critical`. Account-threatening loss, immediate targeted
  re-entry, larger position.
- **A0 and A1 rows are identical.** Deliberate: "measured, and it was ordinary" and
  "could not measure" should lead to the same action. Separating them would let
  abstention behave like evidence.
- **(A1, B2) and (A0, B2)** are `info`, not `caution` — the amendment in §7A.1.
  Prompt plus same-underlying with no magnitude established is indistinguishable
  from an active trader's ordinary rhythm.

### 7A.1 Persona validation

Walked cell by cell. One amendment came out of it; everything else holds.

**Scalper, ~90-second tempo, 40 trades/day, small losses.** Every re-entry is
inside a 20-minute window (B1) and usually the same underlying (B2). Losses are
small, so trade-relative sits below `S2a` and their own losses cluster at their
p50 — A1.

That lands on **(A1, B2)**, which the draft table made `caution`. For this trader
that is their entire day: dozens of caution alerts describing normal tempo.

The contract claimed the defence was "percentile of their own gaps — 90s is their
p50". **That defence requires maturity, and cold start does not have it.** Until
the gap baseline matures the window is the 20-minute default and every re-entry
qualifies. The claimed protection arrives weeks after the flood.

**Amendment: (A0, B2) and (A1, B2) become `info`.**

The reasoning is epistemic, not a tuning knob. At B2 with no magnitude
established, promptness plus same-underlying is exactly what an active trader's
ordinary rhythm looks like, and we have neither a loss size nor a baseline to
separate the two. `info` is the honest answer: recorded as evidence, visible in
analytics, not pushed at them. It is the same abstention principle applied to a
cell rather than a frame.

This costs a real detection: a first-week trader who loses, comes straight back
to the same underlying at the same size, and is genuinely on tilt is now `info`
rather than `caution`. That is a deliberate trade — we cannot distinguish them
from the scalper without either magnitude or history, and inventing the
difference is what this whole exercise exists to stop.

**Systematic re-entry at a level.** Reaches (A1–A2, B3) every time, so `caution`
or `danger`, repeatedly. Already accepted as an unfixable false positive — intent
is unobservable. Worth noting the existing 24-hour per-pattern dedup limits it to
one alert a day rather than one per re-entry, which makes the accepted cost
bearable rather than punishing.

**Cold-start user, no equity, long options.** Account abstains (no equity), trade
abstains (S2a undecided), personal abstains (no history) → **A0**. With the
amendment they get `info` up to B2 and `caution` at B3. So a brand-new trader is
told exactly one thing: *you came back to the same underlying with a bigger
position right after a loss.* Every word of that is directly observed. Correct.

**Missing equity — which is most users today.** A3 is unreachable, so **`critical`
never fires in production**. That is not a matrix defect but it is a fact worth
stating plainly: until `margin_snapshots` has a scheduled producer, one of the
four severity levels is dead in the field, and anything downstream that assumes
`critical` occurs — copy, dashboards, routing — is untested against reality.

**Invalid trade-risk denominator (spreads, equity/delivery).** Trade frame
abstains, so A comes from account and personal only. A spread trader with no
equity and an immature baseline sits permanently at A0 and can only ever reach
`caution`, via B3. Consistent with the frame design, and mostly moot because
strategy-group suppression already removes the legs.

**Long-option buyer.** This is where `S2a` is dangerous. A near-total premium loss
is routine — options expire worthless every week — so if `S2a` is set low, A2 is
reached constantly, and **(A2, B2) is `danger`**. "Lost most of a cheap option,
re-entered the same underlying within twenty minutes" describes an ordinary expiry
afternoon for a large fraction of this market.

Not a matrix problem, but a hard constraint on the decision: **`S2a` set too low
converts a routine outcome into a danger alert.** Of all the unresolved numbers,
this is the one where an incautious value does the most damage.

**Options seller.** The denominator is SPAN margin, not a loss ceiling. Losing 80%
of posted margin is close to catastrophic, where losing 80% of a premium is a
normal Tuesday. Two consequences:

- A required ordering, derivable from the semantics rather than invented:
  **`S2b` must be materially lower than `S2a`.** The same ratio means a far worse
  event on a short position.
- Sellers trading defined-risk spreads are suppressed or abstained anyway, so this
  mostly bites the naked seller — the one it should bite.

### 7A.2 (A0, B3) — confirmed, and why

**Confirmed. Structural escalation is a caution-level signal with no measurable
loss magnitude, deliberately.**

Every element of B3 is directly observed and needs no threshold, no baseline and
no capital: a trade closed at a loss; a new position was entered inside the
window; on the same underlying; larger than the one that just lost. The sentence
"you came straight back to the same thing with more size after losing" is true
whether or not we can size the loss.

Why `caution` and not higher: harm is unestablished. A0 means we genuinely cannot
say how much was lost, and severity is a claim about harm.

Why `caution` and not `info`: escalation after a loss is not tempo. A scalper's
defence — this is simply how fast I trade — explains B1 and B2 and does not
explain deliberately increasing size immediately after losing. That is what makes
B3 survive the amendment that demotes B2.

This is also the cell that makes the whole cold-start argument real. Without it, a
trader in their first week with no equity data gets nothing but `info` from this
detector, and the claim that structural detection protects new traders would be
decorative.

### 7A.3 The amended table

| | **B0** unrelated | **B1** prompt | **B2** targeted | **B3** escalated |
|---|---|---|---|---|
| **A3** account-threatening | `caution` | `danger` | `danger` | `critical` |
| **A2** large | `info` | `caution` | `danger` | `danger` |
| **A1** ordinary | `info` | `info` | **`info`** | `caution` |
| **A0** unquantified | `info` | `info` | **`info`** | `caution` |

Two cells changed from the draft, both `caution` → `info`. No new constants, no
weights, no multipliers were introduced to achieve it.

### The declared-rule breach is separate

A breach of the trader's own `cooldown_after_loss` is a **fact about a commitment
they made**, not objective harm. So it:

- is always recorded in the evidence when it occurs;
- raises severity to **at least `caution`** — they broke a rule they set;
- **never** reaches `danger` or `critical` on its own, because those levels are
  about harm and a self-set cooldown does not measure harm.

Formally: `severity = max(table[A][B], caution if declared_breach else info)`.

### What severity never depends on

- **Confidence.** `danger` at 55% confidence is a legitimate output — that is why
  the axes are separate.
- **How many signals fired.** Counting is a weighted score with every weight set
  to one, and it inherits every objection to the score that was retired.
- **Personal history, downward.** No path lowers a level.

### Confidence, computed separately

Confidence answers *how well could we see this*, from four observable facts: the
trade's data quality (`GOOD`/`PARTIAL`/`UNKNOWN`), how many magnitude frames were
measurable rather than abstaining, the maturity of any personal percentile used,
and whether both symbols parsed. Reported and recorded alongside severity; it
never feeds the table.

### Still unresolved, and what each costs

| # | governs | if undecided |
|---|---|---|
| `S1` | the A3 boundary | A3 unreachable; account frame abstains; ceiling becomes `danger` |
| `S2a–d` | the A2 boundary via trade-relative | A2 still reachable via `P1` once personal matures |
| `P1` | the A2 boundary via personal | A2 reachable via `S2` once decided |
| `P2` | the B1 window | falls back to the existing `revenge_window_caution_min` |
| `B1` bounds | how far personal may move P1/P2 | bounds inert; personal percentiles unbounded until set |

**P3 is gone, not deferred.** The draft carried an inline `1.5×` size multiple. B3
as written needs no constant — "larger than the position that just lost" is
directly observable. If evidence later shows a bare inequality is too noisy, a
multiple can be introduced *with* that evidence. One fewer invented number.

## 8. Old → new threshold mapping

| current | value | disposition |
|---|---|---|
| `revenge_min_loss_inr` | 1% of capital / ₹500 | **DELETE** — capital as suppression (§1) |
| `revenge_min_loss_pct_capital` | 1.0 | **DELETE** with it |
| `revenge_window_caution_min` | 20 (or own p25) | **KEEP**, reclassify `personal_baseline`, add bound direction `HIGHER_IS_STRICTER` |
| `revenge_window_danger_min` | 5 | **UNRESOLVED (P4)** — already flagged mandatory-review |
| `signal_points_*` ×4 | 30/20/10/5 | **DELETE** (§7) |
| `_typical_loss` (inline, 3 losses, session-scoped) | — | **DELETE** — mislabelled; replaced by the personal frame over the baseline window |
| size-escalation `1.5` (inline literal) | 1.5 | **DELETE** — B3 uses a plain inequality (larger than the position that lost), so no constant is needed |
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
