# State ownership audit

23 Aug 2026. Every finding below was checked against the code, not against a
plan document.

The question asked: **does every state field have exactly one owner?** The answer
was no, in three different ways, and one of them was shipping a wrong number to
the user.

---

## 1. `trading_sessions.trade_count` — had NO writer at all

`increment_trade_count` existed on `TradingSessionService` and had **zero call
sites** outside its own test. Nothing else wrote the column. It was therefore `0`
for every session ever recorded.

Two live consumers read it anyway, and both degrade silently rather than
erroring:

| consumer | effect of `trade_count == 0` |
|---|---|
| `app/api/analytics.py:3244` → session-log → `SessionLog.tsx` | every session in the log rendered **"0 trades"** |
| `app/api/session_intent.py:215` | `actual_trades = 0` compared against the trader's declared maximum, so `trades_ok` was **always true** — the end-of-day intent review always told the trader they had kept to their trade limit, whatever they did |

The second is the serious one. It is a feature whose entire job is to tell a
trader whether they honoured their own rule, and it could only ever return "yes".

**Fixed.** `behavior_engine._load_context` now derives it, next to `session_pnl`.

## 2. `session_pnl` — one writer, plus a dormant second

Derived correctly by the engine (CRIT-1, earlier). But `add_session_pnl` sat
beside it, also zero-callers, ready to become a second writer the moment someone
reached for the obvious-looking method.

**Fixed.** Both incremental setters deleted, not left dormant. A test asserts
they have not come back.

### Why derive rather than increment

A retried Celery task, a replay, or a late fill all re-run `analyze` on the same
trade. Deriving from the session's CompletedTrades gives the same answer every
time; incrementing double-counts. `test_reanalysis_does_not_double_count` pins
this.

---

## 3. The facts with three computers each

These are **not fixed** — they are reported, because fixing them changes
user-visible numbers and the choice of which computation is canonical is a
product decision, not a refactor.

| fact | computers | they disagree because |
|---|---|---|
| `consecutive_losses` | `behavior_engine._detect_consecutive_loss_streak` · `danger_zone_service._count_consecutive_losses` · `pattern_prediction_service._get_current_state` · `SessionState` (shadow) | **scope**: the engine counts within the session; danger-zone counts the last 10 completed trades **across days**; prediction counts today's `Trade` fills |
| `session_pnl` | engine (`CompletedTrade` sum, persisted) · `pattern_prediction_service` (`Trade.pnl` sum) · `SessionState` (shadow) | **table**: `CompletedTrade.realized_pnl` vs `Trade.pnl`, the latter written by `pnl_calculator` onto closing fills for "backward compat" |
| `trades_today` / `trade_count` | engine · `pattern_prediction_service` (counts fills) · `SessionState` (shadow) | a multi-fill exit is one CompletedTrade and several `Trade` rows |
| `peak_pnl` / `drawdown_from_peak` | `profit_giveaway` detector (local, CompletedTrade) · `pattern_prediction_service` (fills) · `SessionState` (shadow) | same table split; `reports.py:225` additionally hardcodes `drawdown_from_peak: 0` on the simulate endpoint |

The concrete user-facing consequence of the `consecutive_losses` split: a trader
who lost three yesterday and one today sees the danger-zone banner say **"4
consecutive losses. Take a break."** while the alert engine, correctly scoped to
the session, says nothing. Both are live. Neither is wrong by its own definition,
which is exactly the problem — the definition was never chosen, it was written
three times.

**Recommendation, not yet done:** the engine's session-scoped
`CompletedTrade`-based computation is the one to keep. `Trade.pnl` is a
compatibility shim on closing fills and should not be a denominator for anything.
That makes `danger_zone_service` and `pattern_prediction_service` consumers of
the engine's numbers rather than independent computers. Needs approval — it
changes what the danger-zone banner says.

---

## 4. Clean — verified, no action

| field | owner |
|---|---|
| `positions` table | `TradeSyncService.sync_positions`, sole writer |
| `alerts_fired` | `consume_alert_budget` (single UPDATE); `increment_alerts_fired` is the older read-modify-write and is still present — see note below |
| `risk_denominator*` | `account_risk.freeze_for_session`, write-once by construction |
| `risk_score`, `peak_risk_score`, `session_state` | no writers, deliberately — retired with L3 on 13 Aug. Columns remain pending a migration |
| `closing_equity` | `close_session`, EOD task only |

`increment_alerts_fired` remains and is a genuine second writer to
`alerts_fired`, currently masked by a per-account Redis lock. It is documented in
place in `trading_session_service.py` and left alone here because it belongs to
the alert-budget path, not to session facts.

---

## 5. `SessionState` is still shadow-only

`grep "ctx.session_state"` in `behavior_engine.py` returns nothing. It is folded,
compared, and discarded on every trade. It duplicates every field in the table
above, which is why it appears in each row — but it cannot cause a disagreement
the user sees, because nothing reads it.

That makes it the cheapest of the three problems and the one with a clear exit:
either detectors start reading it (and the legacy recompute goes) or it goes.
Leaving it shadowing indefinitely is the only outcome that keeps the duplication
permanently.
