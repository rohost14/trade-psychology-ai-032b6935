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

## 3. The facts with three computers each — RESOLVED 2026-08-23

Reported first, then fixed once the canonical choice was approved. There turned
out to be **four** computers of the loss streak, not three: `pnl_calculator`
wrote a fifth definition into stored feature rows.

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

### The resolution

`app/core/session_facts.py` is now the single definition of all four facts, and
of `drawdown_from_peak`, `consecutive_wins`, `winners` and `losers` alongside
them. Every consumer reads it; nothing computes its own.

The definitions it fixes are in that module's docstring, which is the place to
change them. In short: the unit is a **CompletedTrade**, the scope is **one
session** bounded by the market open, a **flat trade breaks a streak**, peak is
**floored at zero**, and P&L is **raw**.

| was | now |
|---|---|
| `behavior_engine` counted the streak inline, summed session P&L inline, tracked peak inline in `profit_giveaway` | reads `ctx.facts` |
| `danger_zone_service` counted the last 10 trades across days; summed "today" from IST midnight | reads `session_facts.load_facts` |
| `pattern_prediction_service` computed all five facts from raw `Trade` fills | reads `session_facts.load_facts` |
| `pnl_calculator._build_feature` counted the streak across days, next to a session-scoped P&L in the same row | reads `session_facts.as_of(...)` at entry time |
| `SessionState` treated a flat trade as not breaking a streak | matches the canonical rule |
| `behavior_engine`'s `max_consecutive_losses` rule check counted its own streak | reads `ctx.facts` |
| `constitution.py` /status (My Rules) ran its own query from IST midnight and counted its own streak and P&L | reads `session_facts` |
| `coach.py` Section E computed today's P&L and peak from closed `Position` rows - a seventh unit | reads `session_facts` |
| `baseline_service` computed each historical day's peak, max drawdown and longest run inline | reads `session_facts.derive` per day |

Nine computers in total, not the three first reported.

### Two facts that were being conflated

`baseline_service` needed things the first cut of the module could not express,
and the honest fix was more names rather than a looser definition:

- **`max_drawdown`** - the deepest peak-to-trough *at any point*, as against
  `drawdown_from_peak`, the drawdown the session *ended* on. Up 20k, back to
  flat, back to 20k: the first is 20,000 and the second is 0. A baseline wants
  the first; a live "you are giving it back" alert wants the second.
- **`longest_loss_run`** - the longest run *anywhere* in the session, as against
  `consecutive_losses`, the run still going at the end.

Both are now defined once and tested. They were previously computed inline in
`baseline_service` with no name at all, which is how a baseline could end up
teaching the engine about a quantity the engine never measures.

`EngineContext` derives its own facts when a caller does not supply them, so a
context assembled in a test and one assembled by the engine cannot disagree.

### The behavioural changes, stated

1. **The danger zone fires less.** A trader who lost five on Friday and one on
   Monday morning used to read as a streak of six. Verified by negative control:
   restoring the old counter puts that trader at `DangerLevel.DANGER` with a
   `SOFT_COOLDOWN` on the strength of one loss today. Pinned by
   `tests/test_danger_zone_session_scope.py`.
2. **Prediction numbers change units.** `session_pnl`, `trades_today`,
   `consecutive_losses` and `drawdown_from_peak` on `/api/analytics` now count
   round-trips rather than fills, so they agree with every other surface.
   `minutes_since_last_trade` is now measured from the last CLOSE rather than the
   last order.
3. **New feature rows are session-scoped.** Old rows would have kept the old
   meaning — but the live database holds **zero** feature rows (see §6), so there
   is nothing to migrate. `scripts/backfill_trade_features.py` exists for when
   there is; run it with `--dry-run` first.
4. **`SessionState` shadow mismatches should drop**, because it and the engine
   now agree about scratch trades.
5. **My Rules and the AI coach change units.** Both counted a "trade"
   differently from the engine - My Rules from IST midnight, the coach from
   closed `Position` rows. Neither can now disagree with the alert that fires on
   the same rule.

### Deliberately left alone - different facts, not competing definitions

- `analytics.py` drawdown over a multi-day equity curve.
- `intent_tasks.py` streak of consecutive *days* on which intent was respected.
- `danger_zone_service`'s windowed order counts: burst detection wants order
  velocity, and three tranches of one exit are three orders in a minute.
- Period aggregates in `analytics.py` and `coach.py` Section D (7 days).

### Removed, not left dormant

- `danger_zone_service._get_today_pnl`, `._count_consecutive_losses`
- `pattern_prediction_service`'s 60-day raw-fill query, `total_trades` and
  `avg_revenge_time_minutes` — a third meaning of "a trade" in that file, feeding
  keys that `_calculate_probabilities` never read.

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


---

## 6. Found while doing this — reported, not fixed

**`completed_trade_features` is empty in the live database.** 1,515 completed
trades, **0** feature rows. Features are only written by
`_compute_features_for_new_rounds`, which runs inside
`pnl_calculator.calculate_and_update_pnl` over a bounded recompute window — so
trades created by any path that does not go through it (or that fall outside the
cutoff) never get features.

The consequence is on **My Record**: `my_record.py` guards every feature-derived
statistic with `f is not None`, so "your record after 2+ losses in a row", "after
a loss", "on expiry day" and "quick re-entry" degrade silently to empty rather
than erroring. They have presumably always been empty.

Not chased here because it is a pipeline question, not an ownership one. It does
mean the streak definition change has no stored data to migrate today.

**`pattern_prediction_service` looks up a pattern type that does not exist.**
Lines reading `pattern_counts.get("revenge_trading")` — the engine's 33 pattern
types include `revenge_trade`, never `revenge_trading`, so that lookup is always
0 and the history factor in the revenge probability is dead. Left alone
deliberately: it changes user-visible probabilities and belongs with the parked
frontend-vocabulary work, not with state ownership.
