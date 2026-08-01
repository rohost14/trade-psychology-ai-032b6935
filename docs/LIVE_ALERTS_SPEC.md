# Spec — alerts that arrive while the trade is still open

Written 2026-08-01. Item 1 from the Alerts discussion: the change that decides whether this product is a mirror or a diary.

**Not implemented. This is the spec to argue with before any code.**

---

## 1. The problem, precisely

`BehaviorEngine.analyze()` is called **once per `CompletedTrade`, after FIFO closes a position.** Its own docstring says so. Every alert the product has ever raised is therefore a receipt: by the time "Revenge Trade" fires, the revenge trade is closed and the money is gone.

The measured consequence is already in the repo: **55 alerts fired, 0 outcomes recorded.** We treated that as an engagement problem. It is partly a missing UI (now fixed — the feedback endpoint existed and nothing called it), but mostly it is that **an alert about a closed trade has no available action.**

## 2. Correction to my earlier claim

I said several detectors "can already evaluate mid-position" and that this was mostly wiring. **That was wrong, and the registry disproves it.**

`DetectorSpec.consumes` defaults to `("session_trades", "completed_trade", "thresholds")`, and every one of the **26 detectors** either takes that default or declares an explicit tuple that also contains `completed_trade`. There is no detector today that can run without a closed trade.

So this is new work, not a rewiring. The rest of the spec assumes that.

## 3. What is actually computable before close

Seven behaviours are decidable at **entry** or **during** a position, from data we already receive:

| Behaviour | Decidable at | Inputs we already have |
|---|---|---|
| `no_stoploss` | entry + N minutes | open position, absence of an SL/SL-M order for it |
| `size_escalation` | entry | entry qty vs trailing average entry size |
| `revenge_trade` | entry | minutes since last realised loss, loss size |
| `rapid_reentry` | entry | time since previous exit in same underlying |
| `cooldown_violation` | entry | active `Cooldown` rows |
| `overtrading_pace` | entry | count of entries today vs threshold |
| `session_meltdown` | tick | session realised + unrealised vs daily loss limit |

The first six fire on an **order event**. The seventh fires on a **price tick** and is the only one needing the stream.

## 4. Design

**A separate `LivePositionEngine`, not a modification of `BehaviorEngine`.**

Reasons: `BehaviorEngine` is the money-truth path and is tested against completed trades; making its context optional would weaken every existing detector's guarantees. The two engines share thresholds (`trading_defaults.py`), the `RiskAlert` model, and the severity vocabulary — nothing else.

```
Zerodha postback (ORDER COMPLETE, transaction_type=BUY/SELL opening)
        │
        ├─► existing path: FIFO → CompletedTrade → BehaviorEngine   (unchanged)
        │
        └─► new: LivePositionEngine.evaluate_entry(position, session)
                    │
                    └─► RiskAlert(lifecycle='live', trigger_position_id=…)
                              │
                              └─► Redis Stream → WS → browser   (existing bus)

KiteTicker tick (already streaming for prices)
        └─► LivePositionEngine.evaluate_tick(open_positions, session)
                    └─► session_meltdown only, debounced
```

**Schema.** `RiskAlert` gains two nullable columns — `lifecycle` (`'live' | 'post'`, default `'post'`) and `trigger_position_id`. Nullable and defaulted so every existing row and query keeps working. No new table.

**Dedupe is the hard part.** A live `revenge_trade` at entry and a post-hoc `revenge_trade` on the same trade at close are the same finding twice. Rule: when `BehaviorEngine` writes an alert whose `trigger_completed_trade_id` resolves to a position that already has a `live` alert of the same `pattern_type`, it **updates that row** to `lifecycle='post'` and fills the money, rather than inserting. The user sees one alert that gains its cost when the trade closes.

**Suppression.** One live alert per `(position, pattern_type)`, ever. `session_meltdown` fires at most once per session. Ticks are debounced to one evaluation per 15s per account. The published guidance is that the default for a new event should be silence, and we have 28 detectors and a measured 0% response rate — the bar goes up, not down.

## 5. What the user sees

The alert row already built in `/alerts-lab` needs one addition: a `LIVE` marker and, while the position is open, the response buttons change meaning — "I closed it" / "Holding anyway" instead of the retrospective pair. Everything else (the record line, the one-tap loop) already works and needs no change.

**What it must not become:** a blocker. The charter is mirror-not-blocker. A live alert states what is happening and what the trader's own record says; it never disables a button, never nags twice, and never says "don't".

## 6. Risks, honestly

- **False positives cost far more when live.** A wrong receipt is noise; a wrong warning mid-position erodes trust permanently. Every live detector should ship behind the existing `detector_flags` shadow mode first — write the alert, do not surface it, compare against what the post-hoc engine concludes at close. Promote only when they agree.
- **Zerodha postback latency is not guaranteed.** If the postback arrives after the position is already closed, the live path must detect that and drop rather than emit a "live" alert about a closed trade.
- **The 3 req/sec REST limit does not apply to the tick stream**, but `evaluate_entry` must not make REST calls — everything it needs has to come from the postback payload and cached session state.
- **Solo-login is still the gate.** This is worth building only if the Zerodha multi-user approval lands; until then it is testable on one account.

## 7. Sequencing

1. Schema migration (`lifecycle`, `trigger_position_id`) — additive, no behaviour change.
2. `LivePositionEngine` with **one** detector: `no_stoploss`. It is the least ambiguous, needs no history, and is the easiest to validate by hand.
3. Shadow mode for a full session; compare live vs post-hoc conclusions.
4. Surface it. Add `revenge_trade` and `cooldown_violation` only after the first survives a week.
5. `session_meltdown` on ticks last — it is the only one touching the stream.

**Do not build all seven at once.** The failure mode is a wall of live alerts nobody trusts, which is strictly worse than the current wall of receipts nobody reads.
