# Phase 5 — Performance & Scalability

**Read the caveat first.** The database currently holds 166,222 rows in one
reference-cache table and fewer than 400 in every other. At that size Postgres
prefers sequential scans regardless of indexing, so **`idx_scan` counts and
`EXPLAIN` plans cannot demonstrate anything here**. Every item below is judged
from index definitions, query shapes in code, and projected growth — not from
runtime statistics.

Audit source: `../DATABASE_ARCHITECTURE_AUDIT.md` (frozen).

---

## M2 · 21 groups of duplicate indexes

**Audit:** §12.2 · PERFORMANCE · Severity medium · Confidence HIGH

Twenty-one groups of indexes on the same table cover identical column lists.
Worst cases:

```
trading_sessions      4 indexes on identical columns
alert_checkpoints     3        completed_trades   3
positions             3        risk_alerts        3
```

plus 16 pairs including `users`, `instruments`, `trades`, `broker_accounts`,
`user_profiles`, `monthly_snapshots`, `position_ledger`, `discipline_scores`,
`behavioral_events`, `admin_users`.

The naming tells the story: each group has a short-form name (`idx_ct_broker`), a
long-form (`idx_completed_trades_broker_account_id`), and often a
constraint-generated `..._key`. The same index was created under different names
by successive migrations, and no migration ever dropped the earlier one.

### The trap — read before touching anything

**Several members are partial indexes and are NOT redundant.**
`idx_positions_open` and `idx_risk_alerts_undelivered` have names implying a
`WHERE` clause: they share leading columns but cover different row subsets.

The grouping was computed on `pg_index.indkey` (the column list), which **does
not distinguish a partial index from a full one**. Dropping on the strength of
this grouping alone would remove real indexes.

**Required first step:** for each of the 21 groups, compare `indpred`
(predicate), `indisunique`, and included columns. Only then decide. This
per-group check was deliberately **not** done in the audit.

---

## M19 · One UPDATE per matched fill inside the FIFO P&L loop

**Audit:** §12.6 · PERFORMANCE · Severity medium · Confidence HIGH

`app/services/pnl_calculator.py:415`:

```python
# Backward compat: assign P&L to closing fill in trades table
await db.execute(
    update(Trade).where(Trade.id == trade.id).values(pnl=float(trade_pnl))
)
```

One UPDATE round trip **per matched exit fill**, on the ingestion path, and —
critically — **while the account's Redis FIFO lock is held**. The round trips are
not merely numerous; they extend the lock hold proportionally to the trader's
fill count.

Invisible at 318 fills. Linear in fills thereafter.

The comment marks it as backward compatibility, and the P&L has another home in
`completed_trades.realized_pnl` — so this connects to the duplicate-source-of-truth
question in Phase 3 (M13/M25). **Establish whether `trades.pnl` still has a
consumer before optimising it**; the answer may be to delete the write, not batch
it.

---

## M7 · Growth protection was applied to the wrong curve

**Audit:** §13.2, §19.4 · MISSING / PERFORMANCE · Severity medium · Confidence MEDIUM

| table | grows with | partitioned | retention |
|---|---|---|---|
| `orders` | order lifecycle transitions | **yes**, 24 partitions | **yes**, drops old |
| `trades` | every fill | no | no |
| `position_ledger` | every fill (append-only) | no | no |
| `completed_trades` | every round trip | no | no |
| `behavior_events` | every detector firing | yes, 19 partitions | none |

One order produces **several** fills, so `trades` and `position_ledger` grow
faster than `orders` — yet `orders` is the one with both partitioning and
retention. The capability exists and was applied to the smaller curve.

`margin_snapshots` is worth separating: it grows on a schedule rather than with
user activity, so it accumulates even when nobody trades.

**Confidence is MEDIUM** because there is no observable growth rate to
extrapolate from — the database has no production volume yet.

---

## M8 · `idle_in_transaction_session_timeout = 0`

**Audit:** §13.3, §14.2 · PERFORMANCE · Severity medium · Confidence HIGH

```
max_connections                      60
statement_timeout                    2min
idle_in_transaction_session_timeout  0   (disabled)
```

A transaction left open by a crashed worker or a slow external call holds its
connection **and its locks** indefinitely, and nothing reclaims it. The 2-minute
`statement_timeout` bounds a single statement, not an idle transaction. With 60
connections shared between web, Celery and maintenance, a handful of stuck
transactions exhausts the pool.

Partially mitigated on `alert_tasks`, which set `time_limit`/`soft_time_limit`.
The other task modules do not.

---

## L5 · 8 FK columns with no supporting index

**Audit:** §12.4 · PERFORMANCE / GOOD WITH NOTE · Severity low · Confidence HIGH

```
behavior_events.trigger_completed_trade_id   behavior_events.risk_alert_id
behavior_events_legacy.trigger_completed_trade_id  behavior_events_legacy.risk_alert_id
behavioral_events.trigger_trade_id           behavioral_events.session_id
position_ledger.session_id                   risk_alerts.trigger_trade_id
```

Severity is low deliberately: **six of the eight are on the three behaviour-event
tables**, two of which are superseded or unused (Phase 8), and all are optional
lineage pointers rather than hot join paths.

Only two are worth a second look: `risk_alerts.trigger_trade_id` and
`position_ledger.session_id`, both on live tables.

---

## L13 · N+1 in journal semantic search

**Audit:** §12.7 · PERFORMANCE · Severity low · Confidence HIGH

`app/api/journal.py:579` — one SELECT per search result on a request path.
`WHERE id = ANY(:ids)` would replace it.

Low severity: the loop is `limit`-bounded and short by construction, and it sits
behind the RAG path which is not currently operational.

---

## GOOD, for the record

- **Partitioned indexes are correctly attached** — `orders` 6/6 across 24
  partitions, `behavior_events` 4/4 across 19. A parent index attached to no
  child indexes nothing while looking healthy; this is verified correct (§12.3).
- Most in-loop DB calls found by the AST scan are bounded by a fixed set
  (partitions, months, settings keys, one sync batch) and are **not** N+1 in any
  harmful sense (§12.5).

---

## Exit criteria

- [ ] M2 — all 21 groups checked for predicate/uniqueness differences **before** any drop
- [ ] M19 — `trades.pnl` consumer established; write batched or removed
- [ ] M7 — retention/partitioning decision for `trades`, `position_ledger`, `completed_trades`
- [ ] M8 — idle-transaction timeout decided; task time limits reviewed
- [ ] L5, L13 — dispositioned
- [ ] Synthetic replay: identical alerts/events before and after; no index dropped without evidence
