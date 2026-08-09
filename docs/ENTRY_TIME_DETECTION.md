# When do alerts actually fire? Entry vs exit

Findings only. 2026-08-09.

You asked whether alerts only fire after a trade closes, because an alert that arrives after
the money is gone is worth much less. Short answer: **partly true, and more fixable than I
expected.** An entry-time layer already exists and works — it is just very small, and the
24 detectors that carry the product sit on the other side of it.

---

## 1. What runs when, today

Three separate detection paths, not one.

### Path A — entry time (already live)

`process_webhook_trade` (`trade_tasks.py:622–660`) calls these **inline on every fill**,
seconds after the order completes:

| Check | When | Detects |
|---|---|---|
| `_overexposure_task` | every fill | position size vs capital-at-risk limits |
| `_concentration_task` | every fill | portfolio concentration in one underlying |
| `_entry_rules_task` | BUY fills only | restricted no-trade window · cooldown-after-loss |
| `check_holding_loser_scheduled` | 30 min after a BUY | position still open and losing |

These write through `_fire_position_alert`, which creates the alert, publishes the WebSocket
event, and dispatches push/WhatsApp — **while the position is open**. The copy already says
so: *"entered NIFTY 12 min after a ₹4,200 loss — position is OPEN."*

So the machinery for in-the-moment alerts exists and is wired. I missed it in the earlier
audit because these are called as private `_*_task` functions rather than dispatched as
Celery tasks by name.

### Path B — exit time (the main engine)

`BehaviorEngine` runs per **CompletedTrade** — a flat-to-flat round. Of its 27 detectors:

```
trigger="exit"     24
trigger="session"   3
trigger="entry"     0
```

`DetectorSpec` documents the gap in its own comment: `trigger: str  # exit | session
(entry arrives Phase 6)`. Phase 6 was planned and never built for these.

### Path C — bulk sync

`run_behavior_engine_full_session` replays the engine over the day's completed trades.
Same detectors, same exit-time constraint.

---

## 2. Which exit-time detectors could fire at entry

This is the substance of your question. A detector can move to entry time if its decision
needs only **the entry itself plus prior session context** — not the outcome.

### Decidable at entry (14)

| Detector | What it needs, and why entry is enough |
|---|---|
| `revenge_trade` | this entry's timestamp vs the last loss — the outcome is irrelevant |
| `rapid_reentry` | same instrument re-entered after a losing exit |
| `overtrading_burst` | count of **entries** in 30 min (currently counts completed rounds) |
| `daily_overtrading` | same, per session |
| `size_escalation` | this entry's qty vs the running average |
| `martingale_behaviour` | size increase after losses on the same underlying |
| `post_loss_recovery_bet` | oversized entry following a loss |
| `winning_streak_overconfidence` | size increase after wins |
| `fomo_entry` | several unrelated instruments inside a short window |
| `opening_5min_trap` | entry timestamp inside the opening window — purely an entry fact |
| `end_of_session_mis_panic` | MIS entered after 15:10 — purely an entry fact |
| `expiry_day_overtrading` | expiry date + entry count |
| `same_symbol_obsession` | repeat entries on one symbol |
| `direction_instability` | direction of this entry vs the previous ones |
| `options_premium_avg_down` | this entry adds to an already-losing option leg |

That is 15 of the 24, and several are *purely* entry facts. `opening_5min_trap` fires on
"you entered in the first eight minutes" — a condition fully known at the moment of entry,
currently reported after the position closes.

### Better as a live check while the position is open (2, and these may be the most valuable)

| Detector | Today | Live version |
|---|---|---|
| `premium_loss_event` | after close, from realized P&L | we already stream LTP for every open position. 80% of premium gone is knowable **live**, and that is the `critical` severity that escalates to a guardian. Today it fires once the trader has already taken the loss. |
| `no_stoploss` | "exited manually with no SL on record" — needs the exit | "this position is open and has no stop-loss order attached" is knowable at entry and is the version that can change the outcome |

### Genuinely exit-only (7)

`early_exit`, `panic_exit`, `profit_giveaway`, `consecutive_loss_streak`,
`win_rate_collapse`, `strategy_breakdown`, `time_of_day_bias` — each one is a statement
about a completed outcome or a session aggregate. These belong where they are.

---

## 3. So is your concern right?

**Yes for roughly two thirds of the detectors, with one qualification.**

The qualification: for patterns whose subject is *the next trade* — revenge, overtrading,
cooldown, martingale — an exit-time alert is not useless. It lands before the next entry,
which is the decision it is trying to influence. For an intraday trader whose round lasts
four minutes, the practical delay is small.

But it is clearly worse, for three reasons:

1. **Some patterns are about the position you are in, not the next one.** No stop-loss, an
   oversized entry, averaging down, 80% premium destruction. Told at entry, the trader can
   still act on that position. Told after the exit, we are reporting history.
2. **A round can stay open for hours.** NRML positions, or an intraday position held to
   3:20pm. `opening_5min_trap` on a position entered at 9:17 and closed at 15:15 fires six
   hours after the fact.
3. **It weakens the product claim.** "Real-time behavioural alerts" currently means
   real-time relative to the *close*, not the entry.

---

## 4. What it would take

Not a rewrite. The pieces exist:

- **The trigger field is already there.** `DetectorSpec.trigger` is declarative and already
  carries `exit | session`; adding `entry` is the intended path.
- **The entry pipeline is already wired.** `process_webhook_trade` calls entry checks inline
  on every fill, with a working alert writer that pushes immediately.
- **`RiskAlert.lifecycle`already exists** (migration 076): `'post'` = raised after the trade
  closed, `'live'` = raised while the position was open, plus `trigger_position_id` so a
  post-hoc finding merges into an existing live row instead of duplicating it. The schema
  for exactly this was built and is unused — `_fire_position_alert` does not set
  `lifecycle="live"`, so today's live alerts are stored as `'post'`.
- **Live prices already stream** for every open position (shared KiteTicker), which is what
  a live `premium_loss_event` needs.

The real work is the **engine context**. Every detector currently reads
`EngineContext.completed_trade` — an object that by definition has an exit price and a
realized P&L. An entry-time run needs a context built from the fill plus open positions plus
session state, with no outcome. That is the actual Phase 6 job: a second context type, and
each moved detector rewritten against it.

Two things to decide before any of it:

- **Double-firing.** If `revenge_trade` fires at entry, must it stay silent at exit? The
  `lifecycle` + `trigger_position_id` columns were designed for exactly this merge, so the
  answer is probably "fire live, merge the post-hoc finding into the same row" — but it
  needs stating.
- **Thresholds change meaning.** `overtrading_burst` counting *entries* rather than
  completed rounds will fire earlier and more often against the same numbers. Same issue as
  the multi-leg counting problem: retune, and run it in shadow first.

---

## 5. Things found along the way

- **Three notification policies, not two.** Adding to the earlier audit: the entry/position
  path has its own — a 30-minute dedup, no 5-minute bucket, no session cap, straight to
  `send_danger_alert`. So the same alert type is governed by different rules depending on
  which path produced it. (Entry alerts were therefore never affected by the
  self-suppression bug.)
- **`position_monitor_tasks.py:543`** — `"has_danger": severity == "danger"` drops
  `critical` from the WebSocket payload. Same literal-comparison class as A1/F4.
- **A sixth `_SEV_RANK`** at `position_monitor_tasks.py:479`.
- **`monitor_open_positions`** (`:50`) has no caller and is not on the beat schedule — the
  event-driven inline checks replaced it. Dead code.
- **`cooldown_violation` exists twice**: as a registry detector at exit time, and as an
  entry-time constitution rule in `_entry_rules_task`. Two implementations, two thresholds
  (`user_cooldown_min` vs the detector's own), one concept.
