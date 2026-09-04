# Row Level Security — design for a future project

**Status: DESIGN ONLY. Not scheduled, not implemented.**

Written as the output of Phase 0 decision **D2**. The immediate decision was to
**disable** RLS on the 15 tables that carry it, because in its current state it
provides no protection and is a tripwire. This document exists so that enabling
it properly later is a planned project rather than a rediscovery.

---

## 1. Why the current state must not simply be "enabled everywhere"

Verified on the live database:

```
RLS enabled on   : 15 tables      RLS disabled on : 35 tables
policies defined :  0
app role         : postgres,  rolsuper=false,  rolbypassrls=TRUE
table owner      : postgres  (the same role the application connects as)
```

**Enabling RLS on the remaining 35 tables today would change nothing**, because
the application role both owns the tables and has `rolbypassrls`. Owners bypass
RLS unless `FORCE ROW LEVEL SECURITY` is set, and `BYPASSRLS` overrides it
regardless.

So the choice is not "on or off". It is:

| option | actual protection | risk carried |
|---|---|---|
| enable everywhere as-is | **none** | tripwire on 50 tables instead of 15 |
| disable now (**chosen**) | none | none |
| the design below | **real** | needs its own testing |

**The tripwire matters.** RLS enabled with zero policies means *deny all* for any
role that does not bypass. The day the application moves to a least-privilege
role — a normal security hardening step — every RLS-enabled table returns
nothing, with no policy to fall back on. That is a total outage, and the cause
would not be obvious.

---

## 2. The blocker that makes this non-trivial: there is no `auth.uid()`

**This application does not use Supabase Auth.** Verified: no `auth.uid()`, no
`supabase.auth`, no `auth.users` table. Identity comes from the application's
own JWT:

```python
# app/api/deps.py:54
async def get_current_user_id(token = Depends(oauth2_scheme)) -> UUID:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    # sub = user_id
```

The JWT is minted after Zerodha OAuth and signed with the app's own secret. The
database has no knowledge of it.

**Consequence: the standard Supabase policy shape is unusable here.**

```sql
-- This is what almost every Supabase RLS example looks like.
-- Here it evaluates to NULL for every request, so the policy denies everything.
CREATE POLICY tenant ON trades USING (broker_account_id = auth.uid());
```

---

## 3. The design

Three pieces. All three are required; any one alone does nothing.

### 3.1 A second database role

The application must stop connecting as the owner.

```sql
CREATE ROLE tm_app LOGIN PASSWORD '<from secret store>';
-- deliberately: NOT superuser, NOT BYPASSRLS, NOT the table owner
GRANT USAGE ON SCHEMA public TO tm_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO tm_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO tm_app;
```

Migrations continue to run as `postgres`. Only the application uses `tm_app`.

### 3.2 Policies keyed on a session variable

Since the database cannot read the JWT, the application must tell it who is
asking, per transaction.

```sql
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON trades
  USING      (broker_account_id = current_setting('app.broker_account_id', true)::uuid)
  WITH CHECK (broker_account_id = current_setting('app.broker_account_id', true)::uuid);
```

Notes that matter:

- `current_setting(..., true)` returns NULL rather than raising when the setting
  is absent. With NULL the comparison is false, so the policy **denies** — fail
  closed, which is correct.
- `WITH CHECK` is as important as `USING`. Without it a caller could *insert* a
  row belonging to another account even though they could not read it.
- Tables keyed on `user_id` rather than `broker_account_id` (`broker_accounts`
  itself) need their own predicate.
- Admin tables (`admin_users`, `admin_audit_log`, `admin_settings`,
  `detector_flags`) are **not** tenant-scoped and need a different policy — or
  should be reached by a separate role entirely.

### 3.3 `SET LOCAL` on every transaction — the sharp edge

```python
# app/core/database.py — get_db dependency, conceptually
async def get_db(account_id: UUID = Depends(get_verified_broker_account_id)):
    async with SessionLocal() as session:
        await session.execute(
            text("SET LOCAL app.broker_account_id = :aid"), {"aid": str(account_id)}
        )
        yield session
```

**Why `SET LOCAL` and not `SET`:** the connection goes through **pgbouncer in
transaction mode** (port 6543). A plain `SET` binds to a pooled connection that
is handed to a different request as soon as the transaction ends — so the value
either vanishes or, far worse, **leaks to another tenant**. `SET LOCAL` is scoped
to the transaction and cannot leak.

**The failure mode to design against:** if any code path opens a session without
setting the variable, every policy denies and that path returns **empty results
rather than an error**. Silent, and it looks like "no data" rather than "broken".

---

## 4. Ordering — this sequence is not optional

1. Create `tm_app`, grant it, but keep the application on `postgres`.
2. Add the `SET LOCAL` to `get_db`. It is harmless while no policies exist.
3. Write policies for **one** low-risk table. Verify as `tm_app` that a wrong
   `app.broker_account_id` returns zero rows and the right one returns the rows.
4. Roll out table by table, verifying each.
5. **Only then** switch the application's connection string to `tm_app`.
6. Keep `postgres` for migrations and maintenance jobs permanently.

Reversing steps 5 and 4 causes a full outage.

---

## 5. What this does and does not buy

**Buys:** defence in depth. Today a missing `WHERE broker_account_id = ...` in
one endpoint is a cross-tenant data leak. With RLS it returns nothing instead.
That is a real improvement — the audit found no such bug, but it found no
mechanism preventing one either.

**Does not buy:** protection against the application asking for the wrong
account deliberately, since the app sets the variable itself. RLS constrains
mistakes, not a compromised application.

**Cost, stated honestly:** a new role, a change to the most-used dependency in
the codebase, ~50 policies, and a failure mode that presents as missing data
rather than an error. That is why it is a project, not a task.

---

## 6. Testing it before trusting it

- As `tm_app` with the variable **unset**: every tenant table returns 0 rows.
- As `tm_app` with account A set: only A's rows, on every table.
- As `tm_app` with account A set, attempt `INSERT` with account B's id: rejected
  by `WITH CHECK`.
- Under pgbouncer, two interleaved requests for different accounts: neither sees
  the other's rows. **This is the test that matters** — it is what `SET LOCAL`
  exists to guarantee.
- Every background job and Celery task: they open their own sessions and are
  often *not* request-scoped. Each needs a decision — either run as `postgres`,
  or set the variable explicitly.

---

## 7. Current decision

**Disable RLS on the 15 tables** (Phase 4). Document that tenant isolation is
enforced at the application layer, which the audit verified is holding — 216 of
229 handlers carry an auth dependency, and no user-facing IDOR was found.

Revisit this document when database-level isolation becomes a priority.
