# Phase 6 — Model / Schema Hygiene

High volume, low individual risk. **127 mismatches** between the SQLAlchemy
models and the live database, plus the missing vocabulary constraints.

This phase exists as its own workstream because the items are numerous and
mechanical, and because Phase 1's drift check will start from a baseline of
exactly these — Phase 6 is how that baseline gets burned down.

Audit source: `../DATABASE_ARCHITECTURE_AUDIT.md` (frozen).
Depends on: **Phase 1** (the drift check defines the baseline).
**D3** in Phase 0 decides whether `alert_checkpoints` is in scope or retired.

---

## The full drift, measured

```
models pointing at a table that does not exist ......  0   GOOD
model columns missing from the DB ...................  0   GOOD
DB columns missing from the model ................... 26
type / precision mismatches ......................... 55
nullability mismatches .............................. 45
primary-key mismatches ..............................  1   (H1 — Phase 2)
```

The first two lines are genuinely good: nothing the code expects to write is
absent. Every mismatch is the database holding *more* or *differently-typed*
structure than the model admits.

---

## M4 · `alert_checkpoints` — the model describes 44% of the table

**Audit:** §7.2 · MODIFY · Severity medium · Confidence HIGH
**Blocked on D3.**

```
DB     41 columns
model  18 columns
missing 23
```

The 23 invisible columns: `trigger_quantity`, `trigger_avg_entry_price`,
`trigger_capital_at_risk`, `trigger_instrument_token`, `trigger_symbol`,
`trigger_exchange`, `trigger_instrument_type`, `trigger_direction`,
`user_exited_quantity`, `user_exit_price`, `user_exit_time`, `user_exit_pnl`,
`minutes_to_exit`, `price_at_t5/t30/t60`, `counterfactual_pnl_t30/t60`,
`completed_at`, `outcome`, `money_saved_basis`, `confidence`,
`checkpoint_status`.

Any read through `AlertCheckpoint` returns a partial row; any write leaves 23
columns at their defaults. **If D3 says "retire", this moves to Phase 8 and no
model work is needed.**

---

## L3 · Three semantic type mismatches

**Audit:** §7.3 · MODIFY · Severity low · Confidence HIGH

These three are not stylistic and should be fixed regardless of the other 52:

| column | model | live DB | why it matters |
|---|---|---|---|
| `completed_trades.pnl_pct` | `Numeric(8,2)` | **`double precision`** | the model promises fixed 2-decimal precision; the DB stores binary float. Values written outside the ORM are not rounded, and equality comparison is unsafe |
| `completed_trades.quality_score` | `Integer` | **`smallint`** | the model would accept values the column rejects (>32767) |
| `trades.raw_payload` | `JSON` | **`jsonb`** | `jsonb` normalises key order and drops duplicates; round-tripping through the ORM does not reproduce the stored bytes |

---

## L1 · 52 `VARCHAR(n)` vs `text` mismatches

**Audit:** §7.4 · GOOD WITH NOTE · Severity low · Confidence HIGH

In PostgreSQL `text` and `varchar` are the same storage with no performance
difference, so **at runtime this is harmless** and no length is enforced in
production either way.

The reason it is not entirely free: **CI creates `VARCHAR(20)` columns where
production has unbounded `text`**, because the test suite builds from the models.
A value longer than the declared limit is accepted in production and rejected in
CI. The tests are stricter than reality — the safe direction — but the two are
not the same schema.

**This may correctly end in "change the models to `Text`" or "accept and
baseline".** It is 52 columns of mechanical edit either way.

---

## L2 · 45 nullability mismatches

**Audit:** §7.5 · MODIFY · Severity low-to-medium · Confidence HIGH

The two directions have different consequences and should be handled
differently:

**Model stricter than the DB (~35 columns)** — e.g. `trades.status`,
`trades.order_id`, `holdings.product`, `instruments.lot_size`, most
`created_at`/`updated_at`. The model says `nullable=False`; the database permits
NULL. **Anything writing outside the ORM can insert a NULL that application code
assumes cannot exist**, and the ORM reads it back into a non-optional field.
This is the direction that can actually bite.

**Model looser than the DB (~10 columns)** — e.g. `behavior_events.created_at`,
`monthly_snapshots.created_at`, `strategy_groups.status`. The database enforces
NOT NULL while the model thinks it is optional. Safe at runtime; means CI permits
rows production would refuse.

---

## M11 · Business vocabulary has no database protection

**Audit:** §11.3, §19.3 · MISSING · Severity medium · Confidence HIGH

**Only 9 CHECK constraints exist across 50 tables**, six of them on two tables.
Every status, severity and pattern-name column is unconstrained free text:

| column | enforced where | DB protection |
|---|---|---|
| `risk_alerts.severity` | application constants | **none** |
| `risk_alerts.pattern_type` | detector registry | **none** |
| `behavior_events.detector` | detector registry | **none** |
| `behavior_events.severity` | application constants | **none** |
| `positions.status`, `completed_trades.status` | application constants | **none** |
| `trades.status` | broker payload | **none** |
| `broker_accounts.status` | application constants | **none** |

`risk_alerts.severity` is the sharpest case — it decides whether a trader is
interrupted, and the database would accept any string at all.

**Evidence the team wants this:** `risk_alerts.lifecycle` and
`risk_alerts.outcome` **do** have CHECK constraints, on the same table. The
pattern is established and simply not applied to `severity` or `pattern_type`.

---

## L7 · Stored vocabulary has already drifted

**Audit:** §10.4 · INVESTIGATE · Severity low · Confidence MEDIUM

```
risk_alerts.pattern_type : overtrading=9 ... overtrading_burst=4 ... consecutive_loss=9
behavior_events.detector : consecutive_loss_streak=14 ... overtrading_burst=11
```

The same behaviour is stored under more than one name, and across the two tables
the names differ (`consecutive_loss` vs `consecutive_loss_streak`).

**Not automatically a defect** — stored rows are a historical record and names
legitimately change. It is flagged because nothing distinguishes "a name we
retired" from "a typo", and a consumer filtering on `overtrading_burst` silently
misses the `overtrading` rows.

**Settle this before M11.** Adding a CHECK constraint requires knowing which
values are legal, including historical ones.

---

## L4 · The single `NO ACTION` foreign key

**Audit:** §6.3 · INVESTIGATE · Severity low · Confidence HIGH

```
behavioral_events.trigger_trade_id -> trades   ON DELETE NO ACTION
```

Every other optional lineage pointer uses `SET NULL`. This one would **block**
deletion of a `trades` row referenced by any `behavioral_events` row.

Practical exposure is limited because `behavioral_events` is the superseded
table — **and if Phase 8 retires it, this finding disappears with it.** Sequence
accordingly.

---

## Exit criteria

- [ ] D3 answered; M4 either synced or moved to Phase 8
- [ ] L3 — the three semantic type mismatches resolved
- [ ] L1 — decided: change models to `Text`, or accept and baseline
- [ ] L2 — the ~35 model-stricter columns reviewed (the direction that can bite)
- [ ] L7 settled, then M11 — CHECK constraints on the vocabulary columns that warrant them
- [ ] L4 — resolved, or confirmed moot by Phase 8
- [ ] Phase 1 drift baseline reduced accordingly; check still green
