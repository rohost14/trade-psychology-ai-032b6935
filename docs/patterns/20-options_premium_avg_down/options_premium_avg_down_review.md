# Pattern 20 — `options_premium_avg_down`

**Review, 30 Aug 2026. Findings only. NO CODE CHANGED — see §Implementation decision.**

Review-order 20. Source-list **#16**, recorded as *"IMPLEMENTED, in no
consolidation family — can fire beside every pattern describing the same
re-entry"*.

Measured against the real book — **175 sessions, 740 rounds** — running both
real detectors in process. Scripts: `docs/patterns/_measurement/p20_avgdown.py`,
`p20b.py`.

> **Harness note, and it is new.** `adding_to_adverse_position` was recorded as
> **unmeasurable from the CSV harness** because it reads a fill sequence the
> round reconstruction discards. That was true of the reconstruction, not of the
> tradebook — `read_fills` returns individual fills, so the sequence can be
> rebuilt and classified exactly as the ledger classifies it. It is now
> measurable, **64 firings**, and `validate()` asserts it fires before any
> overlap number is trusted. Without that assertion every comparison here would
> have been a false zero.

---

## The question asked

> Is `options_premium_avg_down` a distinct behavioural pattern, or a specific
> manifestation of `adding_to_adverse_position`?

**Neither.** It is not a manifestation of that detector — the two never describe
the same object and never state the same fact. But it is also not what its own
name says: **it does not detect averaging down at all.**

---

## Current behaviour

Fires on a completed **LONG CE/PE** trade when, earlier in the same session,
**any other long option on the same UNDERLYING** closed with a realised loss of
**≥ 20% of premium paid**.

```python
if ct.instrument_type not in ("CE", "PE") or ct.direction != "LONG": return None
for prior in ctx.session_trades:
    ...
    if prior_parsed.underlying != ct_parsed.underlying: continue
    prior_loss_pct = abs(prior_pnl) / prior_premium * 100
    if prior_loss_pct >= loss_threshold_pct: prior_losers.append(...)
```

There is **no** requirement that the position be the same contract, the same
strike, the same expiry, or even the same option type; **no** requirement that
any position be open; and **no** inspection of a fill sequence. The "prior
losers" are closed rounds with realised P&L.

| | |
|---|---|
| registry | `1.0.0`, `nature=emotional`, `disposition=alerting`, `trigger=exit`, `notification_level=1` |
| severity | **`caution`, hardcoded** — never `danger`, so never notifiable |
| consumes | `session_trades`, `completed_trade`, `thresholds`, `instrument_parser` |
| evidence | underlying, count of prior losers, worst loss %, current premium paid |
| confidence | **none set** |
| threshold | `premium_avg_down_loss_pct = 20` — **no `THRESHOLD_SPECS` record** |
| consumers | `/api/analytics/options-behavior` → `OptionsBehaviorCard`; `daily_reports_service`; `ENTRY_DECIDABLE`; frontend routing + display |

**The engine's own index already records the truth.** `behavior_engine.py:35`:

```
17. options_premium_avg_down    (re-entry on same underlying options after prior loss)
```

---

## What is correct

**It is pure.** No database, no wall clock, no `await`. 53 lines.

**It withholds.** 154 trades had a prior same-underlying long-option loss; it
fired on **44**. The 20% floor declines **71%** of what it could judge — not the
Pattern 9 failure.

**The threshold comment describes the code honestly.** *"Premium averaging down:
re-entry on same options underlying after ≥20% loss"* — that is exactly what the
code does. The comment is right; the **copy** is not (Problem 1).

**Its message is literal about what it observed** — the count of prior losing
positions and the worst loss percentage. It does not assert intent.

**The 20% floor has a stated reason**: *"to exclude scratch trades that hit SL
cleanly"*, and it does that work.

---

## Problems found

### 1. The trader-facing copy describes a DIFFERENT DETECTOR'S behaviour

```python
"options_premium_avg_down": PatternCopy(
    "Adding to a losing option",
    "Additional quantity on an option position already down on premium.",
    "Averaging down an option fights both direction and time decay.",
),
```

"Additional quantity on an option position already down on premium" **is
`adding_to_adverse_position`'s definition**, verbatim in substance. This
detector adds no quantity to anything — the position it names is new, and the
losing position it refers to is closed.

**This is the `cooldown_violation` failure exactly** (Pattern 15: *"Its registry
copy describes that other detector's mechanism, not its own"*), and the
`size_escalation` failure before it.

### 2. It is not an average-down. 0 of 44.

| | |
|---|---|
| firings where any "prior loser" was still an **open position** | **0 of 44** |

Every prior is a closed round. Averaging down means adding to a position you
still hold. **The detector cannot fire on that case by construction.**

What the 44 actually are:

| | n |
|---|---|
| a prior loser is the **same contract**, re-entered after closing | 21 |
| a prior loser is a **different option entirely** | 23 |
| at least one prior loser is the **opposite type** (CE vs PE) | 20 |
| **every** prior loser is the opposite type | **9** |

### 3. Nine firings are a direction change called an average-down

Entering a CE after a PE lost is a **change of view**, not averaging down the
PE. The detector groups by underlying, so it cannot tell them apart. Real
firings:

```
2025-04-03  NIFTY2540323300CE   prior: NIFTY2540323200PE
2025-06-17  SENSEX2561781600CE  prior: SENSEX2561781500PE
2025-10-20  NIFTY25O2025900CE   prior: NIFTY25O2025800PE
```

**`direction_instability` was retired 2026-08-28** for being unable to separate
an emotional reversal from a change of view. This detector makes the same
undecidable call as a side effect, without having been designed to.

### 4. LOOK-AHEAD — 5 of 44 use an outcome not known at decision time

`session_trades` is ordered by **exit**. A "prior" position can therefore have
been **still open** when the current trade was entered, and its loss unknown.

| | |
|---|---|
| firings where a qualifying prior was still open at this trade's entry | **5 of 44 (11%)** |
| gap (prior exit − this entry), median | −30 min (honest); range −313 to **+277** |

For those five the message *"You entered X **after** N losing options
position(s)"* is **false**. The trader entered a second position while the first
was open; the loss the alert cites had not happened yet.

This is the same class as the retired `panic_exit`'s defect — **selecting on an
outcome rather than on the behaviour** — and here it is worse, because the
outcome is used to describe a decision taken before it existed.

### 5. Its real subject is already covered, and it is nearly never alone

| co-firing detector | n | share of 44 |
|---|---|---|
| `same_symbol_obsession` | 31 | **70%** |
| `revenge_trade` | 21 | 48% |
| `post_loss_recovery_bet` | 5 | 11% |
| `martingale_behaviour` | 5 | 11% |
| `premium_loss_event` | 4 | 9% |
| `rapid_reentry` | 4 | 9% |
| **fired alone** | **7** | **16%** |

Its true subject — re-entry on one underlying after a loss — is
`same_symbol_obsession`'s, which sees 70% of these, and `revenge_trade`'s.

The 7 unique firings, in full:

```
2025-04-03  NIFTY2540323300CE    OPPOSITE TYPE (direction change)   gap +5min  → +Rs 225
2025-05-13  SENSEX2551380700PE   OPPOSITE TYPE (direction change)   gap -99min → -Rs 476
2025-05-13  SENSEX2551382700CE   different strike, same type        gap +15min → +Rs 1,040
2025-05-21  DIXON25MAY18000CE    different strike, same type        gap +181min→ -Rs 75
2025-06-20  SENSEX25JUN81500PE   SAME CONTRACT re-entry             gap -130min→ -Rs 630
2025-07-16  ICICIGI25JUL2100CE   SAME CONTRACT re-entry             gap -58min → -Rs 146
2025-10-20  NIFTY25O2025900CE    OPPOSITE TYPE (direction change)   gap -185min→ -Rs 248
```

**Three of the seven are direction changes. Two are look-ahead** (positive gap =
the prior had not closed yet). **Two are same-contract re-entries** an hour or
more later — the only ones that describe something coherent, and both are
`same_symbol_obsession`'s subject at contract level.

### 6. `severity` is hardcoded `caution`, so it has never notified

`NOTIFIABLE = {"danger", "critical"}`. 44 events, all `caution`, **zero
notifications** in 175 sessions. It reaches the Alerts screen and the analytics
card, never a push.

### 7. The one threshold has no spec record and an unsourced justification

```python
# SEBI data: traders who averaged down on losing options lost 3× more.
'premium_avg_down_loss_pct': 20,
```

**No source anywhere in the repository.** Third instance of this class after
`expiry_day_overtrading` (which shipped its statistics to traders) and
`winning_streak_overconfidence`'s hot-hand claim. This one is a code comment,
not trader-facing. `premium_avg_down_loss_pct` has **no `THRESHOLD_SPECS`
record**.

### 8. No confidence is set

Every event inherits the engine's data-quality default (100/75/50), so the
confidence a surface reads is a property of the pipeline, not of the evidence.

---

## Evidence

| question | answer | strength |
|---|---|---|
| does it fire? | **44 events / 19 sessions** of 175 | measured |
| does it withhold? | **yes** — 110 of 154 eligible (71%) | measured |
| is any firing an actual average-down? | **no — 0 of 44** have an open prior | measured |
| does `adding_to_adverse_position` cover option averaging? | **yes — 64 firings, 100% LONG options** | measured |
| do the two ever state the same fact? | **no** — 8 co-fire, describing different objects | measured |
| unique coverage | **7 of 44 (16%)** | measured |
| are those 7 coherent? | **2 of 7** — the rest are direction changes or look-ahead | measured |
| look-ahead firings | **5 of 44 (11%)** | measured |
| direction changes called average-downs | **9 of 44** | measured |
| consequence | flagged mean −₹218 / win 34.1% vs other long options −₹35 / 40.0% | measured, n=44 |
| is it pure? | **yes** | verified |
| is the copy accurate? | **no** — it describes `adding_to_adverse_position` | verified |

**What the evidence cannot say.** One trader, one book. The 7 unique firings are
too few to characterise a behaviour, and that is itself the finding rather than
a gap to be filled.

---

## Overlap with `adding_to_adverse_position`

**They are different objects, and this is the core of the answer.**

| | `adding_to_adverse_position` | `options_premium_avg_down` |
|---|---|---|
| level | **position** | **session** |
| scope | one symbol, one open position | one underlying, any contract |
| input | the **fill sequence** | closed rounds' realised P&L |
| requires an add? | **yes** — that is the subject | **no** |
| requires a loss? | unrealised, at the moment of the add | realised, after the fact |
| firings | **64** | 44 |
| co-firings | **8**, stating different facts | |

The 8 co-firings show the distinction rather than a duplication:

```
2025-09-02  NIFTY2590224700PE
  avg_down : You entered NIFTY2590224700PE after 1 losing options position on NIFTY today (worst loss: 22%).
  aap      : NIFTY2590224700PE: added 75 to a position already 29% against you (21.05 -> 15.00).
```

`aap` describes the fill sequence **inside this position**. `avg_down` describes
**other positions closed earlier today**. Two facts about one trade.

**And `adding_to_adverse_position` already IS the option-premium-averaging
detector.** All **64 of its 64** firings are LONG options — quantity added to an
open long option that had already lost premium. That is precisely what
`options_premium_avg_down`'s copy promises and never delivers:

```
NIFTY2541723300PE: added to this position 2 times while it moved against you, from 17% down...
SENSEX2560380000PE: added 20 to a position already 12% against you (40.76 -> 36.00).
```

**So consolidation in the direction the brief anticipated is not available.**
There is nothing to fold in: the option-premium case is not a subset of this
detector's firings, it is the *other* detector's entire output. Adding an
"options premium" evidence flag to `adding_to_adverse_position` would document
something already true of 100% of its events.

---

## Recommended behavioural contract

> **The subject `adding_to_adverse_position` owns and should keep.** Quantity
> added to a position — option or otherwise — that had already moved against the
> trader. Measured on the fill sequence, at the moment of the decision, with no
> reference to how it turned out.
>
> **The subject this detector actually has**, if it is to have one: re-entering
> the **same contract** after closing it at a loss. Not the same underlying —
> that groups a CE with a PE and calls a change of view an average-down.
>
> **Never uses an outcome that post-dates the decision.** A position still open
> when the next trade was entered is not evidence about that entry.
>
> **Never claims "averaging down" for a new position.** Averaging down is
> adding to something you still hold.

---

## Implementation decision — **NOT IMPLEMENTED. Stopping for your call.**

The brief pre-authorised two outcomes. **The evidence supports neither**, so I
have written the review and changed no code.

- **Consolidate into `adding_to_adverse_position`** — *not available*. They are
  different objects (position vs session, fills vs closed P&L, add vs new
  entry), they never state the same fact, and the option-premium case is
  already 100% of `aap`'s output. Folding a session-level re-entry rule into a
  position-level fill-sequence detector would put two subjects in one detector,
  which is the opposite of the architecture the reviews have been converging on.
- **Keep it separate as a genuinely different behaviour** — *not supported*.
  Its behaviour is re-entry after a loss, which is `same_symbol_obsession`'s
  (70% of firings) and `revenge_trade`'s (48%). It fires alone 7 times in 175
  sessions, and 5 of those 7 are a direction change or look-ahead.

**What the evidence does support is DELETE**, and that was not on the list, so I
am not doing it unasked — the standing rule is no implementation without
approval.

### If you approve deletion, the change and its blast radius

| site | action |
|---|---|
| `behavior_engine.py` | remove detector + retirement note; correct the index line at :35 |
| `detector_registry.py` | remove `DetectorSpec` and `PatternCopy` |
| `trading_defaults.py` | remove `premium_avg_down_loss_pct` (no `THRESHOLD_SPECS` record to remove) |
| `entry_detectors.py` | remove from `ENTRY_DECIDABLE` |
| `AlertContext.tsx` | remove routing; **keep** display name |
| `daily_reports_service.py`, `report_tasks.py` | **keep** labels — historical rows |
| counts | registry 19 → **18**, pattern types 25 → **24**; 8 retirement suites repin |
| tests | new `test_options_premium_avg_down_retired.py`; check `alertlab` scenarios (4 `Expect`s — precedent is to leave lab files, 8 retired names already live there) |

**The one consequence you should decide on explicitly:**
**`/api/analytics/options-behavior` and its `OptionsBehaviorCard` are driven by
this pattern alone.** Its other two sections (`options_direction_confusion`,
`iv_crush_behavior`) are already permanently empty — v1 names a previous pass
deliberately did not repoint. Deleting this detector leaves the card with **no
data source at all**, and a card that can never populate is the
*misleading-empty* class this codebase treats as a real bug. **Removing the card
is a product decision, not a detector retirement**, and I would want it decided
rather than assumed.

### Recorded for the consolidated pass, not fixed

- `premium_avg_down_loss_pct` has no `THRESHOLD_SPECS` record.
- The unsourced *"SEBI data: traders who averaged down on losing options lost 3×
  more"* comment — third instance of this class.
- **`session_trades` is exit-ordered, and detectors read it as if it were
  decision-ordered.** This detector's look-ahead is one symptom; the ordering is
  shared, so other session-scope detectors may have the same exposure. **Not
  swept for — recorded as its own question**, because it is an engine-level
  contract, not a Pattern 20 defect.

---

## Verdict — **DELETE**, pending your approval, with the analytics card decided separately

**Not KEEP AS-IS.** The copy describes another detector; 0 of 44 firings are the
behaviour the name claims; 5 of 44 use outcomes that post-date the decision.

**Not MODIFY.** Narrowing it to same-contract re-entry — the only coherent
subject in its output — leaves 2 firings in 175 sessions, both of which
`same_symbol_obsession` already sees.

**Not CONSOLIDATE.** Nothing to fold: `adding_to_adverse_position` is already
the option-premium-averaging detector, on 100% of its 64 firings.

**Not RESEARCH FURTHER.** The measurements that decide it are run.

**What must be said plainly about what deletion costs:** 7 alerts in 175
sessions disappear, of which 2 are coherent. That is a smaller loss than
`winning_streak_overconfidence`'s 6-of-6 unique coverage — but the analytics
card that depends on this pattern is a real, separate cost, and it needs its own
decision.
