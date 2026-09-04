# Baseline — frozen database state at audit time

Source: audit §2, §3.1, §3.2. **Re-confirmed live on 2026-09-04** before
freezing — the numbers below are current, not copied from the audit text.

Purpose: anything a phase does not deliberately change must still match this
afterwards. This is how you detect a fix that broke something adjacent.

---

## Structure

```
93  relations in schema `public` (relkind 'r' or 'p')
────────────────────────────────────────────────────
48  ordinary tables
 2  partitioned parents          orders, behavior_events
43  partition children           24 under orders, 19 under behavior_events
────────────────────────────────────────────────────
50  addressable tables
39  with a SQLAlchemy model
11  without a model  (8 correctly so)
 0  models pointing at a table that does not exist
```

```
54  foreign keys on base tables      44 CASCADE, 9 SET NULL, 1 NO ACTION
49  primary keys                     (50 tables — behavior_events has none: H1)
19  unique constraints
 9  CHECK constraints
208 indexes on base tables           423 including partitions
21  groups of duplicate indexes      (M2 — some are partial, see the caution)
30  triggers + 9 event triggers      (8 Supabase, 1 ours: tm_protect_partitioned_tables)
91  migration ledger rows            91 files, 0 drift, 79 adopt / 9 runner / 3 skip
```

## Row counts

```
instruments        166,222      <- 99.6% of all rows; reference cache, not user data
trades                 318
margin_snapshots       279
cooldowns              215
behavior_events        145      <- across all 19 partitions
behavioral_events      133      <- superseded generation
completed_trades       112
position_ledger        100
positions               99
schema_migrations       91
risk_alerts             57
journal_entries         20
incomplete_positions    10
trading_sessions         9
coach_sessions           5
users                    3      <- 1 real + 2 synthetic harness identities
broker_accounts          3
user_profiles            3
constitution_history     3
admin_audit_log          3
orders                   0      <- never written; see phase-9 (M14)
everything else        <= 2
```

## Server and connection

```
PostgreSQL 17.6 (aarch64-linux)
Supabase pooler, port 6543 (pgbouncer, transaction mode)
role: postgres, usesuper=false, rolbypassrls=TRUE, owns the tables
statement_timeout                    2min
idle_in_transaction_session_timeout  0        <- disabled (M8)
max_connections                      60
wal_level                            logical
archive_mode                         on
timezone                             Asia/Kolkata
default isolation                    read committed
RLS enabled on 15 tables, 0 policies             <- M1
```

## Date envelope

Every trading table's last write is **2026-07-30** — the account was
disconnected (`last_sync_at = 2026-07-31`, `status = token_expired`).
See phase-9 (M15).

```
trades, completed_trades, positions, risk_alerts,
position_ledger, journal_entries, trading_sessions,
instruments                          2026-02-06 .. 2026-07-30
behavioral_events                    2026-02-09 .. 2026-04-15
behavior_events                      2026-07-29 .. 2026-07-30   (2 days only)
margin_snapshots                     2026-02-06 .. 2026-04-09
```

---

## Re-runnable baseline check

Run from `D:\trade-psychology-ai\backend`. Any difference that a phase did not
intend is a regression.

```python
import asyncio, sys
sys.path.insert(0, ".")
from sqlalchemy import text
from app.core.database import SessionLocal

EXPECTED = {
    "relations": 93, "users": 3, "broker_accounts": 3, "trades": 318,
    "completed_trades": 112, "positions": 99, "position_ledger": 100,
    "risk_alerts": 57, "behavior_events": 145, "behavioral_events": 133,
    "journal_entries": 20, "trading_sessions": 9, "orders": 0,
    "instruments": 166222, "cooldowns": 215, "margin_snapshots": 279,
}

async def main():
    async with SessionLocal() as db:
        async def one(sql):
            return (await db.execute(text(sql))).scalar_one()
        actual = {"relations": await one(
            "SELECT count(*) FROM pg_class WHERE relnamespace='public'::regnamespace "
            "  AND relkind IN ('r','p')")}
        for t in EXPECTED:
            if t != "relations":
                actual[t] = await one(f'SELECT count(*) FROM "{t}"')
        for k, want in EXPECTED.items():
            got = actual[k]
            mark = "ok " if got == want else "DIFF"
            print(f"  {mark} {k:22} expected={want:<8} actual={got}")

asyncio.run(main())
```

**Note on `orders`:** expected 0 today because the table has never been written
to. The moment the account reconnects and a live order arrives, this number
should change — and that is the re-verification M14 is waiting for, not a
regression.
