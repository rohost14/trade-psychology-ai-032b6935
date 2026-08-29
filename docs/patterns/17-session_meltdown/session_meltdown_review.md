# Pattern 17 — `session_meltdown`

**Review, 29 Aug 2026. Findings only. No code changed.**

Review-order 17. Source-list **#11**, recorded as *"IMPLEMENTED, NOT VERIFIED in
replay — **invents a limit at 5% of capital when none declared**"*.

Measured against the real book — **175 sessions, 740 rounds** — running the real
detectors in process.

**This is the loudest detector reviewed so far.** `notification_level=4`, it
starts a **SOFT cooldown** (`cooldown_service:97`), it is in the danger zone's
`danger_patterns` set, and it is one of three `HIGH_DISTRESS_TYPES` that drive
cooldown escalation. Unlike Patterns 13–15 it genuinely interrupts.

---

## Current behaviour

**What it is supposed to detect.** A session losing enough of the day's budget
that continuing is the decision worth interrupting.

**Mechanism, end to end.**

1. **Strategy-leg guard** — if this trade belongs to a strategy group whose
   `net_pnl >= 0` and this leg lost, return `None`.
2. Take `session.session_pnl` and `thresholds["daily_loss_limit"]`.
3. If no declared limit: **`daily_loss_limit = trading_capital × 0.05`**, and
   set `limit_is_declared = False`. If there is no capital either, **return
   `None`**.
4. `session_pnl < -(limit × 0.75)` → **danger**; `< -(limit × 0.40)` → **caution**.
5. Copy branches on `limit_is_declared`.

| | |
|---|---|
| registry | `nature=risk`, `disposition=alerting`, `trigger=exit`, v1.0.0, **`notification_level=4`** |
| consumes | `session`, `completed_trade`, `thresholds` |
| severity | computed — `caution` / `danger` |
| evidence | `session_pnl`, `daily_loss_limit`, **`limit_source`**, `pct_used` |
| confidence | none set |
| dedup window | **2 hours** (`trade_tasks:1107`) |
| downstream | SOFT cooldown · danger-zone `danger_patterns` · `HIGH_DISTRESS_TYPES` · weekly report |

**Values in play.**

| value | where | classified? |
|---|---|---|
| `meltdown_caution_pct` = 0.40 | `COLD_START_DEFAULTS` | **not in `THRESHOLD_SPECS`** |
| `meltdown_danger_pct` = 0.75 | `COLD_START_DEFAULTS` | **not in `THRESHOLD_SPECS`** |
| **0.05 of capital** | **hardcoded inline in the detector** | **not a threshold key at all** |
| `daily_loss_limit` | the trader's onboarding rule | a profile fact, `Source.FACT` |

---

## What is correct

**The March defect is already addressed, and well.** The audit flagged "invents
a limit at 5% of capital when none declared". The detector now carries
`limit_is_declared` and branches the copy:

> declared — *"Today's P&L: ₹-2,025 — 40% of **your ₹5,000 daily limit** used."*
> derived — *"Today's P&L: ₹-2,025 — that is 40% of ₹5,000, **which is 5% of your
> capital. You have not set a daily loss limit yet.**"*

It never calls a derived number "yours", and the second message doubles as the
prompt to set a real one. `limit_source` is carried in the evidence. **That is
the right handling of an invented number** and it should not be undone.

**It abstains rather than fabricating.** No declared limit *and* no capital →
`return None`. It does not fall back to a global rupee figure.

**The strategy-leg guard is a real correctness feature.** A losing leg inside a
net-profitable structure is not a meltdown, and the detector refuses to say so.

**It is pure.** No database access, no wall clock, no imports in the body. Reads
`session`, `thresholds` and `strategy_group` from the context.

**The severity ladder works as designed.** 12 of 53 firing sessions escalate
`caution` → `danger` within the day.

**It is the only detector measuring cumulative session damage against a
budget.** 5% of its firings have no other detector on the same trade, and the
67% that co-fire with `excess_exposure` are answering a different question —
that one asks whether *this position* is too big, this asks whether *the day* is
over budget.

---

## Problems found

### 1. The 5% is hardcoded, and the module built to fix it is already in the context

`app/core/account_risk.py` exists specifically because of this detector. Its
docstring says so:

> *"Before this module there was no agreed answer, so `session_meltdown`
> **invented one inline (5% of declared capital)** and nothing else could reuse
> it. **Detectors must not each grow their own version of this.**"*

The module resolves an account-size denominator, freezes it per session, records
its source and quality on the session row, and is **already loaded into
`EngineContext.account_risk`** (`behavior_engine:634, 684`).

**`session_meltdown` does not read it.** It still computes
`trading_capital × 0.05` inline. `revenge_trade` reads `ctx.account_risk` at
line 1056; the detector the module was written for never migrated.

Two consequences beyond the duplication: the inline path uses **declared
capital**, a self-reported figure, where `account_risk` prefers Kite's
**`opening_balance`**; and the inline path has no abstention concept, where
`account_risk` records quality.

### 2. Two constants drive a `notification_level=4` detector with no classification

`meltdown_caution_pct` (0.40) and `meltdown_danger_pct` (0.75) are bare entries
in `COLD_START_DEFAULTS` with **no `THRESHOLD_SPECS` record** — no `Kind`, no
provenance, no maturity, no sensitivity.

**This does not mean the values are wrong.** A ladder at 40% and 75% of a limit
the trader set is a defensible **product policy**: it is a choice about when to
speak, not a claim about traders, so it needs no research to justify. What is
missing is the *declaration* — every other threshold in the system has to say
what sort of number it is, and these two never did.

The inline `0.05` is worse: it is not even a key, so nothing can classify,
override or explain it.

### 3. The registry copy claims something the detector does not measure

> *"Session P&L against your daily loss limit, **together with the pace of
> trading**."*

**There is no pace or trade-count logic in the detector.** It reads
`session_pnl` and a limit. The same class of defect as Pattern 15's copy, though
milder — here the first half is accurate.

### 4. Firing volume is entirely determined by a number we may have invented

| declared limit | implied capital at 5% | events | sessions | % of all sessions |
|---|---|---|---|---|
| ₹2,500 | ₹50,000 | **226** | 91 | **52%** |
| ₹5,000 | ₹1,00,000 | 111 | 53 | 30% |
| ₹10,000 | ₹2,00,000 | 16 | — | 9% |
| ₹25,000 | ₹5,00,000 | **1** | 1 | 1% |

At a ₹50,000 account — an ordinary retail size — this fires in **over half of
all sessions**, at 2.1 events per firing session, each carrying a soft cooldown
and a danger-zone upgrade.

That is not a defect in the arithmetic; it follows from the trader's session P&L
distribution (58% of sessions lose, median −₹559, worst −₹9,956) against a
₹2,500 budget. **But when the limit is derived rather than declared, a 52%
firing rate is our 5% choosing to interrupt half of this trader's days.** The
copy is honest about the number's origin; the *volume* consequence is not
visible anywhere.

### 5. A stale comment on `EngineContext.account_risk`

> *"Detectors do NOT read this yet - no detector has been migrated."*

`revenge_trade` reads it at line 1056. Minor, but it is the comment that would
tell the next reader whether adoption has begun.

---

## Evidence

| question | answer | strength |
|---|---|---|
| does it fire? | **111 events / 53 sessions** at a ₹5,000 limit; **226 / 91** at ₹2,500 | measured |
| how sensitive to the limit? | **226 → 1** across plausible capital sizes | measured |
| does the severity ladder work? | 12 of 53 sessions escalate caution → danger | measured |
| is it redundant? | **no** — 5% fire alone; the 67% overlap with `excess_exposure` answers a different question | measured |
| is it pure? | **yes** — no DB, no wall clock | verified |
| is the 5% justified? | **it is not even a threshold key**, and a canonical replacement exists and is already in context | verified |
| are 0.40 / 0.75 justified? | defensible as **product policy**; **undeclared** as anything | verified |
| does the copy match? | **no** — claims pace, measures none | verified |

**What the evidence cannot say:** the trader's real `daily_loss_limit` and
capital are not in the book, so every firing count above is conditional on an
assumed value. The *shape* — highly limit-sensitive — is solid; any single count
is not.

Also untested here: the **strategy-leg guard**, because the harness builds no
strategy groups. Its logic is simple and reads correctly, but it has no
measurement behind it.

---

## Recommended behavioural contract

> **Subject.** The session's cumulative realised loss against the day's budget.
> Not a single position, and not the pace of trading.
>
> **The budget is the trader's declared `daily_loss_limit` when they have set
> one.** When they have not, it is derived from the **canonical account-size
> denominator**, and the alert must say so — never "your limit".
>
> **Fires** at a declared fraction of that budget, escalating once a second
> fraction is passed.
>
> **Abstains** when neither a declared limit nor an account size is available.
> It does not fall back to a global rupee figure.
>
> **Does not fire** on a losing leg of a net-profitable structure.
>
> **Interrupts.** This is one of the few detectors that should, and its volume
> is therefore a product concern, not only a correctness one.

---

## Exact changes required

Three, in order of how much they change behaviour. **None is implemented.**

**1. Copy — no behaviour change.** Remove *"together with the pace of trading"*.
The detector does not measure it.

**2. Classify the two constants — no behaviour change.** Give
`meltdown_caution_pct` and `meltdown_danger_pct` a `THRESHOLD_SPECS` record.
On the evidence they are `Kind.PRODUCT_POLICY` — our choice about when to speak,
not a claim learned from traders — which also means they must never resolve from
a learned source. **This registers existing values; it does not introduce or
retune a threshold.**

**3. Adopt `ctx.account_risk` in place of the inline `0.05` — THIS CHANGES
FIRING, and needs its own approval and its own measurement.** The module exists
for this detector and says so, the value is already in the context, and the
inline path uses self-reported capital where the module prefers Kite's
`opening_balance`. But swapping the denominator moves every firing count, and it
depends on **migration 080** being applied — the module degrades to the declared
capital rung until then. **This should not ride along with items 1 and 2.**

Recorded for later, **not** fixed here:

- the stale `EngineContext.account_risk` comment (§5);
- `excess_exposure`, its most frequent co-firing detector, is **deferred** and
  currently abstains on futures and short options, so the 67% overlap figure
  will move once Pattern 16 is unblocked.

---

## Verdict — **MODIFY**

The behaviour is sound and the detector deserves to exist. It measures the one
thing nothing else measures, it abstains rather than fabricating, its guard
against strategy legs is correct, it is pure, and its handling of a derived
limit — refusing to call our number "yours" — is the standard the rest of the
engine should meet.

**Not KEEP AS-IS**, because three things are demonstrably wrong: a hardcoded
denominator that a purpose-built module already replaces and that the detector
is already handed, two unclassified constants driving the loudest alert in the
system, and copy describing a measurement that does not exist.

**Not DELETE or DEFER.** Nothing here is redundant and nothing is blocked —
items 1 and 2 can proceed immediately, and item 3 is a separable decision.

**The thing I would not touch** is the `limit_is_declared` branch. It is the
detector's best feature and the direct answer to the audit note that opened this
review.

---

# Provenance check — 30 Aug 2026

Requested before any change. **No values changed, none invented.**

## 1. `daily_loss_limit` — genuine user input

**Yes, and more thoroughly than most.** An onboarding slider
(`OnboardingWizard.tsx`, min ₹1,000 / max ₹1,00,000 / step ₹1,000, default
₹5,000), pre-filled from `POST /api/constitution/generate`, and one of the six
`RULE_FIELDS` in `constitution_service` — so it carries a tighten direction,
change history, and the loosen-requires-override gate.

The detector already prefers it and already says so. **Nothing to change.**

## 2. `ctx.account_risk` — an account SIZE, not a limit

`AccountRisk(value, source, as_of, quality, detail)`. A rupee figure resolved on
a three-rung ladder and **frozen on the session row** (migration 080, applied —
the columns are mapped):

| rung | source | quality |
|---|---|---|
| 1 | Kite `opening_balance` from this session | **GOOD** |
| 2 | `opening_balance` up to N days old | PARTIAL |
| 3 | `trading_capital` the trader declared | PARTIAL |
| — | none of the above | **ABSTAIN** |

**This corrects item 3 of the review above.** I wrote *"adopt `ctx.account_risk`
in place of the inline 5%"*. That is imprecise: `account_risk` replaces the
**capital figure** — self-reported `trading_capital` becomes a better-sourced,
quality-tagged, session-frozen number — but **the `× 0.05` remains and remains
unsourced**. Adopting it fixes the denominator's provenance, not the percentage.
They are two separate questions and the review ran them together.

## 3. The `5%` — not a documented default, and already superseded twice

- **Predates the visible history.** The only commit touching it
  (`3dd0232`, 12 Mar) changed `capital * 0.05` to `float(capital) * 0.05`. No
  commit introduces or justifies the number.
- **Not documented anywhere** as a daily-loss-limit default.
- **Superseded, by two different values, both inside this product:**

| source | value |
|---|---|
| `constitution_service` experience matrix (server) | **2%** beginner · **2%** intermediate · **2.5%** experienced · **3%** professional |
| `OnboardingWizard.tsx` when capital is typed | **2%** |
| **this detector's fallback** | **5%** |

So the detector's fallback is **higher than the "professional" tier** of our own
recommendation, and nearly triple what onboarding suggests.

**A plausible origin, offered as a hypothesis and not a finding:** every "5% of
capital" in the docs refers to **position sizing** (`max_position_size`), a
different rule. The daily-loss-limit 5% may be a bleed-through from it.

## 4. The `40%` / `75%` — documented, and explicitly endorsed

Not arbitrary. `docs/BEHAVIOUR_SYSTEM_DESIGN.md:136` — the design of record —
classifies `meltdown_caution_pct` under:

> **"Already relative — ratios against the trader's own number (`meltdown_caution_pct`
> = 40% of *your* declared loss limit)… stay as they are. These are the model
> the rest should follow."**

Also carried in `docs/contracts/THRESHOLD_INVENTORY.md`,
`docs/patterns/00-shared/BEHAVIOURAL_PATTERNS.md`, and two archived audits.

**These are the one part of this detector the design of record holds up as
correct.** The only gap is that they have no `THRESHOLD_SPECS` record — a
registration gap, not a value gap.

---

## Recommendation per input

| input | recommendation | why |
|---|---|---|
| `daily_loss_limit` | **KEEP — already uses user input** | onboarding slider, constitution rule, preferred by the detector, honestly labelled |
| `40%` / `75%` | **KEEP the values; centralize the registration** | endorsed by the design of record as the model to follow. Give them a `THRESHOLD_SPECS` record as `PRODUCT_POLICY`. **Registration only — no value moves** |
| `ctx.account_risk` | **CENTRALIZE the existing value** | replaces self-reported capital with a quality-tagged, session-frozen figure. Behaviour-changing, so its own approval. **Does not resolve the 5%** |
| **the `5%`** | **RESEARCH FURTHER — but the research is internal, not external** | it is not a documented default and our own product already answers the question twice, at 2–3%. The open question is which existing answer this should adopt, and whether the experience matrix should drive it. **Do not invent a third number** |

**Suggested order, unchanged from the review except that item 3 is now two
items:** copy fix → register 40/75 → adopt `account_risk` for the capital figure
→ *separately* decide what replaces the 5%.
