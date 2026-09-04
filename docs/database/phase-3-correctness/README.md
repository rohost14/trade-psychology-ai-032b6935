# Phase 3 — Correctness Defects Inside the Live Window

Everything here falls **inside** the active trading window 2026-02-06 →
2026-07-30. The account being idle since then explains none of it.

Audit source: `../DATABASE_ARCHITECTURE_AUDIT.md` (frozen).
Depends on: Phase 1. **D8** in Phase 0 may move M22 to Phase 8.

---

## M22 · `trading_sessions.trade_count` is never written

**Audit:** §3.6a · DATA INTEGRITY · Severity medium · Confidence HIGH

All 9 session rows report `trade_count = 0` while `session_pnl` **on the same
row** is populated and correct:

```
session_date  trade_count  session_pnl     actual completed trades that day
2026-04-08         0          0.0000                  9
2026-04-09         0          0.0000                  8
2026-06-17         0        442.5000                  5
2026-06-18         0       7879.5000                  4
2026-07-29         0     -11342.4920                 17
2026-07-30         0        889.9475                  7
```

A session that saw 17 completed trades reports 0. This is the specification's
"field written but never reliably written" case: the column exists, is typed as
meaningful, and no writer populates it.

**Blocked on D8.** If nothing reads the column, the correct fix is to drop it
(Phase 8), not to populate it. Answer D8 first.

---

## M23 · 13 of 23 trading days have no `trading_sessions` row

**Audit:** §3.6b · DATA INTEGRITY · Severity medium · Confidence HIGH

```
distinct trading days in the book : 23   (by fill_timestamp)
distinct exit days                : 21
trading_sessions rows             :  9
```

Days with completed trades and no session row:

```
2026-02-06  2026-02-09  2026-02-11  2026-02-12  2026-02-23  2026-02-24
2026-03-02  2026-03-12  2026-03-17  2026-03-18  2026-04-06  2026-04-07
2026-06-16
```

The earliest session row is 2026-04-08, so the Feb/March absence is explained by
the feature arriving later. **`2026-06-16` is not** — it falls after that date
and still has no row.

`get_or_create_session` is meant to make this table complete by construction, so
one missing day inside the active period means at least one path creates trades
without ever calling it. Find that path; the backfill of historical days is a
separate, optional decision.

---

## M6 · 19 of 61 services commit sessions they do not own

**Audit:** §8.2 · MODIFY · Severity medium · Confidence HIGH

```
admin_settings_service      ai_personalization_service   alert_checkpoint_service
behavioral_baseline_service constitution_service         cooldown_service
detector_flag_service       gtt_service                  instrument_service
live_position_engine        margin_service               pnl_calculator
push_notification_service   rag_service                  retention_policy_service
retention_service           strategy_detector            token_manager
trade_sync_service
```

A service that commits a caller's session decides, on the caller's behalf, that
everything staged so far is final. A handler staging three writes and calling
such a service between the first and second gets the first committed and the
rest in a new transaction — partial failure then leaves partial state.

`pnl_calculator` committing is the most surprising: a calculator should not end
a transaction.

**Scope this deliberately.** This is a *shape* finding from static analysis;
whether any specific one causes incorrect state depends on its callers, which
was not traced. **Start with the three that write trading data** —
`trade_sync_service`, `live_position_engine`, `pnl_calculator` — and their
callers. Do not attempt all 19 at once.

---

## M12 · `trades.order_id` is fill-unique while `kite_order_id` is the real order id

**Audit:** §8.1 · MODIFY · Severity medium · Confidence HIGH

```
trades rows            : 318
distinct order_id      : 318   <-- unique, enforced by uq_trades_broker_order
distinct kite_order_id : 269   <-- the broker's actual order id
```

Nothing is broken — the constraint matches the real semantics. **The name does
not.** Any contributor treating `trades.order_id` as "the order" gets one row per
fill and concludes each fill was a separate order.

This is a naming/documentation fix, not a data fix. A rename touches a lot of
call sites; a clear comment plus a model docstring may be the proportionate
answer.

---

## M13 / M25 · Duplicate sources of truth for fills and P&L

**Audit:** §20.1 · INVESTIGATE · Severity medium · Confidence MEDIUM

Three places two sources can genuinely disagree:

1. **`trades` vs `position_ledger`** — both record fills, populated by different
   paths, different row counts (318 vs 100), and **nothing reconciles them**.
2. **`positions` vs `position_ledger`** — position state exists both as a stored
   row and as something derivable by replaying the ledger. No check says they
   agree.
3. **P&L is computed in at least three places** — stored `realized_pnl` on
   `completed_trades`, unrealised P&L on `positions`, and a client-side live
   calculation in the frontend from streaming LTP. Different rounding or
   denominators produce a number the trader sees that does not match the others.

**This is an investigation, not a fix.** Establish first whether `trades` and
`position_ledger` are meant to be the same fact at different grains. The answer
determines whether anything needs to change at all.

---

## L16 · 22 trades with NULL `fill_timestamp`

**Audit:** §3.6c · DATA INTEGRITY · Severity low · Confidence HIGH

```
22 of 318 trades have fill_timestamp IS NULL
   all created 2026-02-06 (the first ingestion day)
   by status: COMPLETE 15, CANCELLED 5, REJECTED 2
   20 of the 22 DO have exchange_timestamp populated
```

Historical and bounded — confined to the first day of ingestion. But any query
grouping trades by `fill_timestamp` silently drops them, which is why the monthly
breakdown in §3.2 shows a `None` bucket of 22.

Low severity. Worth fixing when the area is next touched; 20 of 22 have a usable
`exchange_timestamp` fallback.

---

## M26 · Alert lineage is optional, so it can be silently absent

**Audit:** §4.3 · MODIFY · Severity medium · Confidence HIGH

Every link that would let you reconstruct *why* an alert fired is a nullable
column with `ON DELETE SET NULL`:

```
risk_alerts.trigger_trade_id               -> trades            ON DELETE SET NULL
risk_alerts.trigger_completed_trade_id     -> completed_trades  ON DELETE SET NULL
behavior_events.trigger_completed_trade_id -> completed_trades  ON DELETE SET NULL
behavior_events.risk_alert_id              -> risk_alerts       ON DELETE SET NULL
```

Deleting a `completed_trade` does not delete the alert it produced — it silently
blanks the alert's only pointer back to its cause. The alert survives as an
assertion with no evidence behind it.

`SET NULL` is a defensible choice — you do not want user-visible history
cascading away. The problem is the combination: with nullable columns and
`SET NULL`, there is **no way after the fact to distinguish "this alert never had
a trigger" from "the trigger was deleted"**.

**Same family as H2 and M13/M25** — all four are about a reference whose meaning
cannot be recovered from the schema. Consider them together.

**What to review next:** whether an alert with a null trigger should be
distinguishable from one whose trigger was removed. A `trigger_deleted_at` or a
non-null discriminator would do it; so would deciding the distinction does not
matter.

---

## M27 · The partial-commit risk in the ingestion pipeline

**Audit:** §14.8 · INVESTIGATE · Severity medium · Confidence MEDIUM

The ingestion pipeline commits at several points within one logical unit of
work: after order upsert, after ledger application, and again after behavioural
detection.

**One seam is already handled deliberately** — `trade_tasks.py:664` rolls back
flushed-but-uncommitted ledger data with the stated intent *"so the behavior
detection step below doesn't accidentally commit partial state"*. So the risk was
recognised.

**What could not be established from static reading** is whether *every* seam is
handled. A failure after the ledger commit but before the detection commit
leaves the fill persisted and the behavioural analysis absent, with a Celery
retry then re-running detection against an already-committed ledger.

**Why it is probably safe rather than certainly safe:** the deterministic
idempotency keys (§14.5) mean a re-run collides rather than duplicates. The
residual question is whether a re-run produces the *same* key when intervening
state has changed — which needs execution tracing, not reading.

**Directly related to M6** (19 services commit sessions they do not own) and best
investigated alongside it.

**Proof:** replay the ingestion pipeline through the Phase 1 fixture with an
induced failure between the ledger commit and the detection commit; assert the
resulting state is either complete or cleanly absent, never half-written.

---

## Exit criteria

- [ ] D8 answered, and M22 either fixed or moved to Phase 8
- [ ] M23 — the path that creates trades without a session identified
- [ ] M6 — the three trading-data services reviewed; ownership documented
- [ ] M12 — naming clarified in code or documented
- [ ] M13/M25 — reconciliation question answered (may end in "no change")
- [ ] L16 — dispositioned
- [ ] Synthetic replay: session rows and counts now correct for a fabricated trading day
