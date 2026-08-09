# Entry-time detection — plan

Companion to `docs/ENTRY_TIME_DETECTION.md` (what fires when, today). **Nothing implemented.**

The goal is alerts that arrive while the trader can still act, **without** buying that
earliness with false positives. Those two pull against each other: exit-time detection is
accurate partly *because* it waits for the outcome. Everything below is about paying for
earliness with better context rather than with precision.

---

## 1. Questions I asked, and what the code answered

### Q. Is entry-time detection actually harder, or just different?

Harder, in three specific ways.

**Partial fills.** One order can complete in several fills. Three fills of a 300-lot order
look like three entries unless something coalesces them.

**Multi-leg structures.** A four-leg iron condor arrives as four fills within seconds. At
exit time we know it was one structure. At entry, naively, it is four trades on four
instruments — which would fire `overtrading_burst` (4 in a burst), `fomo_entry` (multiple
unrelated instruments in a short window) and `size_escalation` (rising quantity) all at
once, all wrong. **This is the single largest false-positive risk in the whole change.**

**Intent is unknown.** At exit, `size_escalation` is a fact about what happened. At entry, a
larger position might be a planned scale-in. We are asserting a pattern from partial
evidence, which is exactly what the review warned against ("do not claim to know the
trader's emotional state from transactions alone").

### Q. Do we already have anything that solves the multi-leg problem?

**Yes, more than I credited in the earlier audit, and it changes the design.**

`strategy_detector.py` classifies 12+ multi-leg structures (straddle, strangle, four spread
types, iron condor/butterfly, futures hedge, calendar, synthetic) into `StrategyGroup` +
`StrategyGroupLeg` rows, and `trade_tasks.py:523` calls it. `EngineContext.strategy_group`
is populated, and `behavior_engine.py:506` uses it to suppress **eight** detectors when the
trade is part of a structure:

```
revenge_trade · martingale_behaviour · size_escalation · consecutive_loss_streak
rapid_reentry · no_stoploss · post_loss_recovery_bet · direction_instability
```

So the FP-suppression *pattern* already exists and works. Two gaps:

1. **The count-based detectors are not in that set.** `overtrading_burst`,
   `daily_overtrading`, `fomo_entry` and `expiry_day_overtrading` still count legs as
   trades. That is the B3 defect from the earlier audit, now located precisely: grouping
   exists, the counters just do not consult it.
2. **It only runs at exit.** `strategy_detector.py`'s own docstring says so:
   *"The FIRST leg of a strategy may still fire some alerts (we don't know it's a strategy
   leg until the second leg closes). Full entry-time detection (using open Positions before
   any leg closes) is a Phase 2 improvement."*

**Conclusion: entry-time strategy grouping is a hard prerequisite, not a nice-to-have.**
Without it, entry-time detection makes multi-leg traders' experience dramatically worse.

### Q. Can we even tell an entry from an exit at fill time?

Yes — and there is a live bug here.

`PositionLedgerService.apply_fill` maintains signed position state per
`(symbol, product)`: `+qty` for BUY, `−qty` for SELL (`trade_tasks.py:468`). From the
position before and after a fill, every fill classifies cleanly:

| Before → after | Classification | Entry-time detection applies? |
|---|---|---|
| 0 → ±n | **open** | yes |
| ±n → ±(n+m) | **add / scale-in** | yes, and it is the interesting case for sizing patterns |
| ±n → ±(n−m) | **reduce** | no |
| ±n → 0 | **close** | no — this is the exit path |
| +n → −m | **flip** | yes (it opens a new position), and it is behaviourally loud |

**The bug:** `_entry_rules_task` is gated on `trade.transaction_type == "BUY"`
(`trade_tasks.py:643`). A BUY that *covers a short* is an exit, not an entry — so today,
closing a short position can fire a "cooldown violated, position is OPEN" alert. Every
short-selling trader gets false cooldown and restricted-window alerts on the way out of
positions. This is live now, independent of anything in this plan.

### Q. Which detectors are safe to run at entry, and which are not?

The useful split is not "entry vs exit" — it is **binary fact vs inference**.

**Binary — the condition is fully known at entry, no inference:**

| Detector | Why it is binary |
|---|---|
| `opening_5min_trap` | entry timestamp inside the opening window |
| `end_of_session_mis_panic` | MIS + entry timestamp after 15:10 |
| `expiry_day_overtrading` | expiry date + count (needs grouped counts) |
| constitution rules (restricted window, cooldown, trade limit, loss limit) | arithmetic against a rule the user wrote |
| `no_stoploss` (live form) | "this open position has no SL order attached" — an order-book fact |

These can fire at entry at full severity. There is nothing to be wrong about.

**Inferred — entry gives us the trigger, but the reading could be innocent:**

`revenge_trade` · `rapid_reentry` · `size_escalation` · `martingale_behaviour` ·
`post_loss_recovery_bet` · `winning_streak_overconfidence` · `fomo_entry` ·
`same_symbol_obsession` · `direction_instability` · `options_premium_avg_down`

These need corroboration before they alert at entry (see §2.3).

**Outcome-dependent — stay at exit:** `early_exit`, `panic_exit`, `profit_giveaway`,
`consecutive_loss_streak`, `win_rate_collapse`, `strategy_breakdown`, `time_of_day_bias`.

### Q. Should detectors *move* to entry, or should entry be an additional pass?

**Additional pass.** Moving them would be the wrong risk:

- A missed or delayed postback would mean the detection is lost entirely. Keeping the exit
  pass means the exit remains a backstop that always runs.
- Some evidence only exists at exit (duration, whether the SL triggered, realized P&L). An
  alert raised at entry should be *enriched* at exit, not replaced.
- It is reversible. If entry-time `revenge_trade` proves noisy, we turn off the entry pass
  for that one detector and nothing regresses.

The schema already anticipates this. Migration 076 added `RiskAlert.lifecycle`
(`'post'` | `'live'`) and `trigger_position_id`, documented as *"'live' = raised while the
position was still open… lets the post-hoc engine merge its finding into an existing live
row instead of duplicating it."* Built, and currently unused — `_fire_position_alert` never
sets `lifecycle="live"`.

### Q. What does entry-time have that exit-time does not?

Worth stating, because it is the argument that entry can be *more* accurate, not just
earlier:

- **Live unrealized P&L** on every open position (shared KiteTicker already streams it).
- **Current portfolio state** — what else is open, what is losing right now.
- **The order book** — is there a stop-loss attached to this position *right now*.
- **Freshness** — "12 minutes after a ₹4,200 loss" is a live fact, not reconstructed.

`premium_loss_event` is the clearest case. Today it fires post-close, from realized P&L, and
its ≥80% band is `critical` — the severity that escalates to an accountability partner. The
same condition is knowable **live** from the price stream, while the position is open and
the trader can still act. Firing it live is strictly better information, and it is the
alert most likely to matter.

### Q. How do we know we have not made false positives worse?

We currently cannot — there is no precision instrument. That makes **Phase 4 of the review
plan (measurement) a prerequisite**, not a parallel track. Specifically we need
`not_useful` rates and per-pattern mute rates readable before entry detection is promoted
past shadow.

Two measurement routes, both available:

1. **Historical replay.** Fills are stored in `trades`, so an entry-time evaluation can be
   replayed over past sessions and compared against what the exit engine actually fired.
   Disagreements are the FP candidate list. This costs nothing and needs no users.
2. **Shadow mode.** `DetectorSpec.default_mode` (`off | shadow | canary | on`), the
   `detector_flags` table and `BehaviorEvent.shadow` all exist. An entry pass ships as
   `shadow`: it writes evidence, raises nothing, and we compare.

### Q. Does firing at entry double the alert volume?

Roughly, if unmanaged — most patterns would fire once live and once post. The
`lifecycle` merge is what prevents it: the exit pass looks for a live alert with the same
pattern and `trigger_position_id`, and enriches it instead of inserting.

Note this lands on top of four existing suppression layers (24h/2h dedup, 5-minute bucket,
8-per-session cap, per-pattern mutes), two of which only started working this week. Tuning
should happen after the merge exists, not before.

### Q. What breaks in analytics?

**One real integration risk.** Behaviour→money is defined as the realized P&L of flagged
trades, joined through `trigger_completed_trade_id`. A live alert has **no CompletedTrade
yet** — it references a position. If we ship live alerts without backfilling that link when
the position closes, every live alert silently contributes ₹0 to the behaviour-cost figure,
and Analytics quietly under-reports. The merge step must set
`trigger_completed_trade_id` on close. This is the kind of silent-zero that the earlier
audit found repeatedly and it needs an explicit test.

### Q. Are there cheap wins that do not need the full change?

Three, and they are worth doing regardless:

1. Fix the BUY-covers-short bug (§1, Q3) — it is a live false positive today.
2. Add the count-based detectors to strategy-group suppression — fixes leg-inflated
   `overtrading_burst` at exit, today, and is required for entry anyway.
3. Set `lifecycle="live"` in `_fire_position_alert` — the four existing entry-time alerts
   are currently mislabelled as post-hoc.

---

## 2. The design

### 2.1 A coalescing window on fills

Evaluate on a short debounce rather than per fill: when a fill arrives, start (or extend) a
per-account timer of **~5 seconds**, then evaluate once over everything that landed.

This one mechanism removes three FP sources: partial fills, multi-leg legs, and an order
split across several tickets. The cost is ~5 seconds of latency, which is irrelevant to a
human deciding whether to stay in a trade, and it strictly reduces DB work versus
evaluating per fill.

### 2.2 Entry-time strategy grouping

Extend `strategy_detector` to classify from **open positions plus the coalesced fill batch**,
not only from CompletedTrades. The classifier itself already exists — it needs a second
input adapter. Once a batch is classified as a structure, the entry pass applies the same
`_STRATEGY_SUPPRESSED` logic that exit already does, and count-based detectors count
**structures, not legs**.

### 2.3 A confidence floor for inferred patterns

Binary detectors alert at entry at their normal severity. Inferred detectors must clear a
higher bar at entry than at exit, because the outcome evidence is missing. The engine
already stacks weighted confidence signals with `importance` levels, so this is a threshold,
not new machinery: **an inferred pattern may raise a live alert only if its confidence
exceeds the entry floor; otherwise it records evidence and waits for the exit pass.**

The honest framing this preserves: at entry we can say *"this entry is 3× your average size,
12 minutes after a ₹4,200 loss"* — all facts. We should not say *"you are revenge trading."*
That was true at exit too, but it matters more here.

### 2.4 The lifecycle merge

```
entry  → evaluate → live alert   (lifecycle='live', trigger_position_id set)
exit   → evaluate → same pattern for the same position?
                      yes → enrich the live row: lifecycle='post',
                            trigger_completed_trade_id, realized P&L, duration
                      no  → insert as today
```

Deliberate decision: **a profitable outcome does not retract a live alert.** The behaviour
happened; the outcome does not validate it. The outcome is attached as fact, not verdict.

---

## 3. Phases

Each is shippable and revertible on its own.

**E0 — the three cheap fixes.** BUY-covers-short; count-based detectors into strategy
suppression; `lifecycle="live"` on existing entry alerts. All three are current defects.
Small, no new concepts.

**E1 — fill classification + coalescing.** Classify each fill (open/add/reduce/close/flip)
from the ledger, and add the debounce window. Ships with **no new detectors** — it is
plumbing, and it makes E0's fix structural rather than a patched condition.

**E2 — entry-time strategy grouping.** Second input adapter for `strategy_detector`, from
open positions. Verified by replay: every historical multi-leg structure that exit-time
grouping found must also be found at entry time from the same fills.

**E3 — binary detectors at entry.** `opening_5min_trap`, `end_of_session_mis_panic`, the
remaining constitution rules. Low risk by construction — nothing to be wrong about. First
real user-visible earliness.

**E4 — live `premium_loss_event` and live `no_stoploss`.** Off the price stream, throttled
per position. Highest value in the plan: these can change the outcome of the position the
trader is currently in. `premium_loss_event` needs a per-position evaluation throttle
(~30s) rather than per tick.

**E5 — inferred detectors at entry, in shadow.** The ten inference patterns, behind
`detector_flags` shadow mode, measured against replay and against the exit pass, promoted
individually. **Gated on Phase 4 measurement existing.**

**E6 — the lifecycle merge and the analytics backfill.** Could ship earlier if E3 produces
duplicate pairs; must ship before E5 volume arrives.

**Order:** E0 → E1 → E2 → E3 → E4 → (Phase 4 measurement) → E6 → E5.

---

## 4. Open questions for you

1. **`premium_loss_event` live is the biggest win and the biggest behaviour change.** An
   alert saying "this open position is down 80% of premium" while the position is live is
   very close to advice. Are you comfortable with that framing, or does it need different
   copy?
2. **Does an entry alert count against the same suppression budgets** as an exit alert, or
   do live alerts get their own allowance? My instinct: shared, because the trader's
   attention is one budget — but it means a noisy entry pass can silence the exit pass.
3. **Scale-ins.** Adding to a winning position and adding to a losing one are different
   behaviours. Do you want them treated separately, or is "add" one category?
4. **E4 needs the price stream during market hours to be reliable.** Gap #1 (dedicated
   market-data account) is still a pending action item on your side. Live
   `premium_loss_event` inherits that dependency — worth knowing before we sequence E4.
