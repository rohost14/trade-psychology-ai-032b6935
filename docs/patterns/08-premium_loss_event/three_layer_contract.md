# Pattern #8 — the three-layer contract

27 Aug 2026. **Analysis and proposal only. No implementation, no threshold
changed.** Supersedes the implementation direction in `realtime_review.md`,
which jumped to architecture before the contract was settled.

**Headline: the strongest signal is (B) — but it is already detected, by
`adding_to_adverse_position`.** So the answer is not a new compound detector. It
is that Pattern 8 has been trying to be three different things at once, and
separating them removes most of what is wrong with it.

---

## 0. What this dataset can and cannot see

Stated first, because it bounds every conclusion below.

**CAN see:** every fill — symbol, side, quantity, price, timestamp. So a
position's entry *tranches* are visible, including adds made while already under
water, and the unrealised loss at the moment of each add is reconstructable.

**CANNOT see:** the intraday path between fills. A position that ended 45% down
might have sat at 40% for an hour or gapped there in one print.

> **Consequence: "crossed the boundary and the trader held" is NOT measurable on
> this dataset.** Any claim about holding-past-a-line is unevidenced here and
> must stay unevidenced until tick history exists. What *is* measurable is
> **adding** while beyond a boundary — an action, not an absence of one, and a
> strictly stronger observation.

## 1. Layer 1 — position state

**Premium loss % is a factual measurement about a position.** It is not a
decision and not a behaviour: the trader chose the entry, the market chose the
percentage.

| ended at least this far down | episodes | realized |
|---|---|---|
| 25% | 105 | −₹342,932 |
| 40% | **57** | **−₹252,380** |
| 60% | 26 | −₹135,571 |
| 80% | 10 | −₹83,620 |

Across 888 long-option episodes with a gross loss of **−₹672,032**, the 40% band
selects **6% of positions carrying 38% of the money**. That is real and it is why
the bands survived their review.

**But selecting money is not the same as warranting an alert.** The design of
record is explicit that an alert's job is *"to convert an automatic action into a
deliberate one"*. At exit, the position is closed and there is no action left to
convert. Live, there is.

## 2. Layer 2 — the user's commitment

`sl_percent_options` — *"I exit options when premium drops by"*, 30/50/70/100% —
is a **declared exit rule**. Reaching it is not a behavioural finding; it is a
rule boundary being touched, exactly like `max_consecutive_losses` or
`daily_loss_limit`.

**It belongs in `constitution_violation`, not in `premium_loss_event`**, for
three reasons the codebase already establishes:

1. **`Kind` forbids the merge.** `premium_loss_caution_pct` is
   `UNIVERSAL_SAFETY` — *"objective danger; never personalised"*.
   `sl_percent_options` is a `USER_RULE` — *"a commitment the trader made"*.
   Blending them into one number destroys the distinction the taxonomy exists to
   protect.
2. **Pattern 4 already resolved this exact shape.** `consecutive_loss_streak`
   died and the trader's declared `max_consecutive_losses` under
   `constitution_violation` carried the behaviour. Same problem, same answer.
3. **The constitution already has the machinery** — tighten-instantly,
   loosen-with-friction, the 80/100/120 ladder, per-rule dedup keys, and the
   `_CONSTITUTION_PAIRS` suppression that stops a rule breach and a behavioural
   pattern shouting the same thing.

**What should happen when the boundary is reached:** a `constitution_violation`
with `rule="sl_percent_options"`, stating *"you said you exit at 25%; this
position is 25% down."* Nothing more. It is a reminder of a commitment, not a
diagnosis.

**Interaction with the universal bands: two events, whichever comes first.** A
tighter personal rule speaks earlier. A looser one cannot push the universal
band out, because `safety_bounds` already enforces that declared values may only
tighten.

## 3. Layer 3 — behaviour after the boundary

**This is where the actionable episode would live, and it is the thing that was
worth testing.**

### The measurement

| detector | episodes | realized | **per alert** | deteriorated after |
|---|---|---|---|---|
| **A — ended ≥40% down** (ships today) | 57 | −₹252,380 | **−₹4,428** | — |
| **B — added while ≥25% down** | 18 | −₹107,928 | **−₹5,996** | **14 of 18** |
| **B — added while ≥30% down** | 13 | −₹92,792 | **−₹7,138** | **10 of 13** |
| **B — added while ≥40% down** | 3 | −₹42,724 | **−₹14,241** | 2 of 3 |

> **B concentrates money 1.4× to 3.2× harder per alert than A**, and in roughly
> four cases out of five the position got *worse* after the add.

The worst examples are unambiguous behaviour, not market noise:

| date | symbol | added at | ended | cost |
|---|---|---|---|---|
| 2026-01-06 | VBL26JAN520CE | **40.8% down** | 80.2% down | **−₹34,706** |
| 2025-09-22 | RECLTD25OCT420CE | 38.1% down | 83.6% down | −₹8,798 |
| 2025-11-25 | NIFTY25NOV26000CE | 34.4% down | 54.4% down | −₹8,835 |
| 2026-03-13 | DMART26MAR4300CE | 28.7% down | 80.3% down | −₹7,335 |

And they are **largely complementary, not substitutes** — overlap at the 25%
boundary is: both 13, only A 44, only B 5.

### The finding that decides it

**`adding_to_adverse_position` already fires on every one of these.** Its
condition is `adverse > 0` — *any* add while under water, with **no percentage
bar at all**. All 18 B-episodes are inside its 99 alerts.

So the compound *"boundary passed AND the trader added"* adds **nothing Pattern 2
does not already catch.** Building it would be a third detector saying a thing
already said.

**What Pattern 2 lacks is not detection — it is weighting.** It already carries
`deepest_adverse_pct` and `first_adverse_pct` in its evidence, but its severity
keys on whether the trader *doubled down in size*, never on *how far under water
they were*. An add at 2% down and an add at 41% down are the same severity today.

**And neither detector knows the trader's declared line.**

### What is not measurable, and must not be claimed

- **Holding past the boundary** — needs the intraday path. Unevidenced here.
- **Re-entry after a boundary breach** — `revenge_trade` (frozen) and
  `rapid_reentry` own that question; not Pattern 8's to answer.
- **Increasing risk elsewhere while a position is beyond the boundary** —
  measurable in principle, not measured here, and it is `excess_exposure`'s
  subject.

## 4. The proposed contract

> **`premium_loss_event` reports one fact: how much of the premium paid for a
> long option is currently gone.**
>
> - It is a **measurement of position state**, not a claim about the trader. The
>   copy is already correct on this.
> - **It alerts only where the trader can still act** — while the position is
>   open. Once closed, the same measurement is a record, not an alert.
> - It is **`UNIVERSAL_SAFETY`**. No personal baseline may quieten it and the
>   trader may not raise it.
> - **It does not carry the trader's commitment.** A declared exit rule is a
>   different statement with a different owner.
> - **It does not diagnose behaviour after the boundary.** Adding to a losing
>   position is `adding_to_adverse_position`'s subject; the depth of the loss is
>   *context* it should be able to use, not a second detector.

## 5. Event model

| # | event | owner | fires | severity from | disposition |
|---|---|---|---|---|---|
| 1 | premium loss crossed a universal band | `premium_loss_event` | **live**, on a band crossing while open | 40 / 60 / 80 (+15pp expiry) | **alerting** |
| 2 | position closed having lost N% of premium | `premium_loss_event` | at exit | — | **analytics-only** (`info`) |
| 3 | declared exit boundary reached | `constitution_violation`, `rule="sl_percent_options"` | **live**, on crossing | the constitution ladder | **alerting** |
| 4 | added to a position already under water | `adding_to_adverse_position` | on the add | existing matrix, **with depth as new context** | alerting (unchanged) |
| 5 | no protective order on a losing position | `no_stoploss` | exit today; live when order state exists | existing | unchanged — **see §7** |

**Events 1 and 3 are the two layers acting at whichever boundary is reached
first.** They are separate rows because one is a safety floor and the other is a
promise; `_CONSTITUTION_PAIRS` is the existing mechanism for stopping them
shouting together.

**Event 2 is the change that resolves the biggest complaint in the last review.**
The exit path currently duplicates what the live path already said and reports it
at `notification_level=3`. Demoted to `info` it becomes what it actually is — the
record — and the double-report disappears without any dedup surgery.

## 6. Real-time vs analytics-only

| | real-time | analytics-only |
|---|---|---|
| premium loss % as a **number** | yes — already on the WS price stream, no alert needed | yes, in reports |
| **band crossing** while open | **yes, alerting** | — |
| **declared boundary** crossing | **yes, alerting** | — |
| position **closed** at N% down | — | **yes, `info`** |
| adding while under water | already live via Pattern 2's entry path | — |

**Layer 1 stays available in real time without alerting** — the frontend already
receives ticks and computes live P&L client-side. A trader watching the screen
does not need an alert to know a number that is on the screen. The alert exists
for the trader who is *not* watching, which is the crossing, not the state.

## 7. Pattern 8 and Pattern 12, without duplicate alerts

**Measured overlap: 44 of Pattern 8's 48 firings are also `no_stoploss` firings
— 92%** — because for a long option both compute the same percentage of the same
premium. They differ only in bands (25/50 against 40/60/80) and in
`no_stoploss`'s two extra gates.

**And they contradict each other.** `NIFTY26FEB25750CE` at 59.8% of premium is
**caution** to Pattern 8 and **danger** to Pattern 12. Same trade, same number,
two alerts, two severities.

**They must stay separate until live stop-loss state is reliable**, and the
separation should be by *subject*, not by threshold:

- **Pattern 8 owns the magnitude.** How much of the premium is gone.
- **Pattern 12 owns the preparation.** Whether anything was protecting the
  position.

**Pattern 8 should carry stop-loss state as context when it exists** — *"down
60%, and nothing is protecting it"* is one alert carrying two facts, which is
strictly better than two alerts. **That is not available yet**: the `orders`
table only fills on sync, so live SL state is unknown. The data does arrive —
`order_stream_service` explicitly discards `TRIGGER PENDING` — but until it is
kept, this stays a design note.

**No merge on current evidence.** The overlap is an artefact of a shared
denominator, not proof they are one pattern.

## 8. Verdicts

**Pattern 8 — MODIFY, and the contract above is the change.** Not a new detector,
not new thresholds. Split what it is currently doing: alert on live crossings,
demote the exit path to analytics, hand the declared boundary to
`constitution_violation`, and hand the after-boundary behaviour to Pattern 2
where it already lives.

**Pattern 12 — RESEARCH FURTHER, blocked**, unchanged from the last review.
Its subject is real and distinct; its live form needs order state that is
currently discarded.

**The strongest detector question, answered directly:** *"declared boundary
reached + trader continues"* concentrates money materially better than *"loss
threshold reached"* — **but it is already built**. The gap worth closing is not a
new episode detector; it is that `adding_to_adverse_position` cannot see how far
under water an add was made, and neither detector can see the line the trader
drew for themselves.

## 9. What would change the answer

- **Tick history**, which would make "crossed and held" measurable and could
  turn holding-past-a-boundary into a real episode. Not available.
- **A second trader's book.** Every number here is one trader; the B-set is 18
  episodes.
- **Live order state**, which would let Pattern 8 carry protection as context and
  would unblock Pattern 12.
