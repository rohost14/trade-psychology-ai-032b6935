# Phase 4 — Security

**No confirmed vulnerability was found in the audit.** Everything here is either
a control that appears to exist but does not hold, or hardening. Severity is
stated accordingly and deliberately not inflated.

Audit source: `../DATABASE_ARCHITECTURE_AUDIT.md` (frozen).
Depends on: **D2** in Phase 0 for the RLS work.

---

## M17 · An admin action can succeed while its audit row silently fails

**Audit:** §15.10 · SECURITY · Severity medium · Confidence HIGH

`app/api/admin/audit_writer.py`:

```python
    db.add(row)
    await db.commit()
except Exception as e:
    logger.error(f"audit_writer failed (action={action}): {e}")
```

The audit writer swallows every exception. **A destructive admin action —
deleting a user, erasing an account — can complete successfully while its audit
record is never written**, leaving only a log line.

The value of an audit log is that it is complete. A best-effort audit log cannot
answer "who deleted this account" with certainty.

**Coverage is otherwise good:** 28 `audit()` calls across 33 mutating admin
routes. The six without one:

```
auth.py    admin_login, admin_logout, totp_setup_confirm, totp_disable
system.py  test_email_delivery
tasks.py   backfill_duration_minutes
```

Four are authentication events with their own trail in `admin_login_events`, so
their absence is reasonable. `test_email_delivery` is harmless.
**`backfill_duration_minutes` is the notable one** — it mutates trading data and
writes no audit row.

**Question to settle:** should an audit-write failure be fatal to the action it
describes? That is a policy decision, not a code detail.

---

## M1 · Row Level Security is enabled but provides no protection

**Audit:** §15.1 · SECURITY · Severity medium · Confidence HIGH
**Blocked on D2 — do not implement before that decision.**

```
RLS enabled on   : 15 tables
RLS disabled on  : 35 tables
policies defined :  0
application role : postgres, rolsuper=false, rolbypassrls=TRUE, and table owner
```

Two independent reasons it is decorative: no policies exist, and the app role
bypasses RLS anyway.

**This is not a claim that data is exposed.** Tenant isolation via the
application layer is a legitimate architecture, and §15.7 found no user-facing
IDOR. The finding is that the schema *looks* as though a database-level control
exists on 15 tables when none is in force — exactly the thing that gets mistaken
for defence-in-depth in a later review.

The 15 tables are also an odd subset: `orders` and `behavior_events` have RLS;
`users`, `trades`, `positions` and `broker_accounts` do not.

---

## L10 · `connect_zerodha` accepts an unauthenticated `user_id` it never reads

**Audit:** §15.7 · MODIFY (dead parameter) · Severity low · Confidence HIGH

```python
async def connect_zerodha(
    redirect_uri: Optional[str] = None,
    user_id: Optional[str] = None,          # caller-supplied, no auth
    db: AsyncSession = Depends(get_db)
):
```

**Verified: the parameter is never read in the function body.** It is not an
IDOR today. It is an unused, unauthenticated, user-supplied parameter on an
auth-adjacent endpoint — the kind of thing that becomes a vulnerability the
moment somebody wires it up.

Smallest possible fix: delete the parameter, or document why it exists.

---

## L9 · `rag_service.py:280` interpolates a list into SQL

**Audit:** §15.8 · SECURITY (latent) · Severity low · Confidence HIGH

```python
patterns_array = "ARRAY[" + ",".join(f"'{p}'" for p in patterns) + "]"
pattern_filter = f"AND relevance_patterns && {patterns_array}"
```

**Not currently exploitable, for three independently verified reasons:**

1. The only caller passes a hardcoded empty list — `coach.py:593` calls
   `get_chat_context(..., patterns_active=[])`, which is falsy, so no
   interpolation happens at all.
2. `knowledge_base` **does not exist** in the live database.
3. **pgvector is not installed**, so the `<=>` / `::vector` query could not run.

**The action is conditional, and that is the whole point:** this must be
parameterised **before** RAG is ever enabled. It is cheap to fix now and easy to
forget later. 68 of the other 72 raw-SQL uses are already parameterised; the
remaining three interpolate trusted internal constants and are safe.

---

## L11 · `/api/metrics` is unauthenticated by design

**Audit:** §15.6 · SECURITY (hardening) · Severity low · Confidence HIGH

Its own docstring says: *"No auth (internal only — protect at the [ingress])"*.
That is a deliberate decision, not an oversight — but **the security of this
endpoint lives outside the codebase**. If the service is ever exposed without an
ingress rule, operational metrics become public.

**Action:** confirm the deployed ingress actually blocks `/api/metrics`. This
audit cannot see that, and no code change may be needed.

---

## What is already GOOD and needs no work

Recorded so it is not re-litigated:

- **216 of 229 handlers carry an auth dependency.** All 13 without one were
  assessed individually; none is an unintended exposure (§15.6).
- **The webhook is HMAC-verified** with `hmac.compare_digest` — constant-time,
  both body-checksum and header-checksum paths (§15.6).
- **Broker and admin credentials are encrypted at rest** via Fernet
  (`broker_account.py:64-92`); `password_hash` and `totp_secret_enc` likewise
  (§15.2).
- **Impersonation is read-only, enforced centrally** in middleware at
  `main.py:310` — a 403 on any non-safe method carrying `imp=True` (§15.9).
- **No user-facing IDOR found.** 22 of the 23 id-taking handlers are admin
  routes with `require_role`; the 23rd is L10 above (§15.7).

---

## Exit criteria

- [ ] M17 — audit-failure policy decided and implemented; `backfill_duration_minutes` audited
- [ ] M1 — D2 answered and implemented (which may mean disabling RLS, not adding policies)
- [ ] L10 — dead parameter removed or documented
- [ ] L9 — parameterised, or an explicit gate recorded that blocks enabling RAG until it is
- [ ] L11 — ingress rule confirmed
- [ ] Full suite green
