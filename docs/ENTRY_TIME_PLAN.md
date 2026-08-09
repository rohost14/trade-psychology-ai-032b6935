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

## 3a. Status

**E1 shipped 2026-08-09** (`124f7c2`). Coalescing window (5s, tumbling, SET NX concurrency,
inline fallback if Redis or the queue is down) · scale-in classified as add-to-loser /
add-to-winner from the ledger row alone, no price feed needed · exposure and concentration
moved under the opening-fill gate, since neither can rise on a DECREASE · entry copy names
the batch rather than one arbitrary leg. New: `app/services/fill_classification.py`,
`app/services/entry_batch_service.py`, `flush_entry_batch` task. 27 tests. 530 backend
tests pass.

**E0 shipped 2026-08-09** (`184ec0a`). Two defects fixed: the entry gate now reads the
ledger's fill classification instead of the order side, and position-monitor alerts are
recorded as `lifecycle="live"`. 13 tests. 503 backend tests pass.

**Two corrections to this document, found while implementing E0:**

- **`fomo_entry` never had the multi-leg problem.** It counts *distinct underlyings*, with
  an explicit comment: "buying 2 NIFTY strikes is not FOMO". A condor is one underlying.
  The count-based FP risk is `overtrading_burst`, `daily_overtrading` and
  `expiry_day_overtrading` only.
- **The E0 item "add count-based detectors to `_STRATEGY_SUPPRESSED`" was wrong and is
  dropped.** Suppression means *do not alert at all*, which would hide genuine overtrading
  by a spread trader — someone doing five condors in thirty minutes is overtrading. The
  correct fix is to count structures rather than legs, which needs grouping at count time.
  Moved to E2.

## 4. Decisions

Four questions were open. Answers and reasoning below.

### 4.1 Live `premium_loss_event` — is "this position is down 80%" advice?

**Decision: ship it, worded as an observation with no recommended action, and gate the
copy on the fact that we are not telling them what to do.**

The reasoning that settles it: we are describing something *already true about a position
the trader already holds*. SEBI's concern is personalised guidance about what to buy, sell
or hold. "Your NIFTY 24500 CE is down 78% of the premium you paid" contains no
recommendation — it is their own position's arithmetic, which their broker also shows them.
It becomes advice the moment we append "consider exiting", so we do not.

What tips the balance is the counterfactual. The alternative is to keep telling them the
same fact *after* they have closed the position, which is strictly less useful and no less
advisory. If the observation is legitimate at 15:30, it is legitimate at 11:48.

Two constraints that come with it: no exit suggestion, no "act now" framing, and the
severity stays as computed — we do not inflate it to force attention.

### 4.2 Do live alerts share the suppression budget with exit alerts?

**Decision: shared budget, but suppression is decided per *pattern-and-position*, not per
alert; and a live alert never blocks its own exit-time enrichment.**

The trader's attention is one budget — two systems each allowed eight alerts a day means
sixteen alerts a day, which is the fatigue problem twice. So: shared.

But the failure mode I raised is real — a noisy entry pass silencing the exit pass. The
resolution is that the *merge* removes the conflict. Once the exit pass enriches an existing
live alert rather than inserting a new one, there is no second alert to suppress. The two
passes only compete when they produce genuinely different findings, which is exactly when
both deserve to be counted.

The one hard rule: **the exit pass may always write its enrichment**, regardless of budgets,
because it carries the realized P&L that Analytics needs. Suppression governs
*notification*, never the record — the existing §1C.8 "evidence is never suppressed"
principle already says this.

### 4.3 Scale-in to a winner vs scale-in to a loser

**Decision: separate. `INCREASE` is classified by the position's unrealized P&L at the
moment of the fill, and only adding-to-a-loser feeds the sizing detectors.**

These are opposite behaviours wearing the same shape. Adding to a winner is what most
trading literature calls correct — pyramiding into strength. Adding to a loser is averaging
down, which is the behaviour `martingale_behaviour` and `options_premium_avg_down` exist to
catch. Treating them as one category would produce a false positive on every disciplined
scale-in, which is precisely the outcome you asked me to avoid.

We can already tell them apart: the ledger has the position's average price, and the price
stream has the live LTP, so unrealized P&L at fill time is available with no new data.

A third case worth naming now rather than discovering later: **adding to a loser that is
inside the trader's own plan** — a pre-declared two-tranche entry. We cannot distinguish
that from tilt at entry, and we should not pretend to. This is where §2.3's confidence
floor does the work: if the only signal is "added to a losing position", that is not enough
to alert live. It needs corroboration — size ratio, time since a loss, prior escalation in
the session.

### 4.4 E4 depends on the market-data account

**Decision: sequence E4 after E3, but treat the dependency as a hard gate, and build E4 so
it degrades to silence rather than to wrong answers.**

Live `premium_loss_event` needs a reliable price stream during market hours, which today
rides on the borrowed-token arrangement that Gap #1 was meant to replace (code done,
dormant, waiting on a dedicated account being provisioned).

The engineering consequence: E4 must treat "no live price for this position" as *skip*, not
as *zero*. A stale or missing LTP that gets treated as a price produces a fabricated loss
percentage on a real position — the worst possible false positive, and the same silent-zero
class this codebase has produced repeatedly. So: no cached price older than a defined
staleness bound is usable, and no alert fires without one.

That also means E4 can be built and shipped in shadow before the dedicated account exists —
it simply will not fire much until the feed is solid.

## 5. Remaining open questions

1. **`premium_loss_event` live is the biggest win and the biggest behaviour change.** An
The four questions above are decided in §4. What remains genuinely open, and needs a call
before the phase it belongs to:

1. **The coalescing window length (E1).** 5 seconds is my proposal. Longer catches more
   legged-in structures; shorter alerts sooner. A trader who legs into a spread deliberately
   over two minutes will not be coalesced at any sane window — E2's grouping from open
   positions is what covers that case, not the window.
2. **Whether E5 ships at all** (inferred patterns at entry). E3 and E4 deliver most of the
   value with almost none of the false-positive risk. E5 is where the risk lives, and the
   honest position is that it should only ship if the shadow-mode numbers justify it. That
   is a decision to take with data, after Phase 4, not now.
