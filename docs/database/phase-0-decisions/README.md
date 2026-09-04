# Phase 0 — Decisions

**No code. No schema change. Nothing is implemented in this phase.**

Eight findings are decisions rather than defects. Each needs a human answer
before any work is worth doing, because the answer changes — or removes — the
task. Doing Phase 8 (retirement) before these are settled would mean deleting
things that turn out to be needed, or fixing things that are about to be deleted.

Audit source: `../DATABASE_ARCHITECTURE_AUDIT.md` (frozen).

---

## D1 · Retire `behavioral_events`? — M5, blocked by M16

**Audit:** §18.1, §8.3 · Severity medium · Confidence HIGH

**The situation.** Two populated generations of the same concept, with different
schemas and non-overlapping dates:

```
behavioral_events   133 rows   2026-02-09 → 2026-04-15   event_type, trigger_trade_id, context, delivery_status
behavior_events     145 rows   2026-07-29 → 2026-07-30   detector, evidence, input_snapshot, idempotency_key, shadow
```

**The complication (M16), which is why this is not a simple delete:**
`analytics.py` and `zerodha.py` **still read `behavioral_events`**. It is not
merely retained history — it is on live read paths.

**Questions for you:**
1. Are the 133 Feb–April rows worth keeping? They are the only surviving record
   of detector output for that period.
2. Do `analytics.py` / `zerodha.py` read it as a deliberate fallback (union with
   the new table), or is that a stale read that silently returns nothing for any
   recent period?

**Decision options:** (a) keep both, document the split; (b) migrate the 133 rows
into `behavior_events` and retire the old table; (c) retire the table and accept
losing Feb–April behavioural history.

**Decision: RETIRE.** Export the 133 rows; do NOT migrate row-by-row (69% unmappable). Coverage via the D4 backfill. Approved 2026-09-04.

---

## D2 · Is Row Level Security meant to be real? — M1

**Audit:** §15.1 · Severity medium · Confidence HIGH

RLS is enabled on **15 tables**, **zero policies** exist, and the application
role has `rolbypassrls = TRUE` and owns the tables. It therefore provides no
protection whatsoever. Tenant isolation currently rests entirely on the
application layer.

The 15 tables are also an odd subset — `orders` and `behavior_events` have it;
`users`, `trades`, `positions` and `broker_accounts` do not — which suggests it
was inherited from Supabase defaults rather than designed.

**Questions:** Do you want database-level tenant isolation? If yes, it needs
policies and a non-bypassing role, and the table selection needs a principle. If
no, leaving RLS enabled with no policies is misleading to any future reviewer.

**Decision options:** (a) implement real RLS properly; (b) disable RLS on the 15
and rely on the app layer explicitly and documentedly; (c) leave as-is and
document why.

**Decision: DISABLE now.** Full design for later in `../_shared-reference/RLS_FUTURE_DESIGN.md`. Approved 2026-09-04.

---

## D3 · Is `alert_checkpoints` a live feature or residue? — M4

**Audit:** §7.2 · Severity medium · Confidence HIGH

```
DB     41 columns
model  18 columns
missing from the model: 23
```

The 23 invisible columns (`counterfactual_pnl_t30`, `money_saved_basis`,
`outcome`, `user_exit_price`, `minutes_to_exit` …) describe a fully-formed
feature. The table holds 1 row. Its only non-archived consumer is
`app/services/alert_checkpoint_service.py`; a second consumer is in `_archive/`.

**Question:** Is alert-outcome measurement a live feature, a paused one, or
abandoned?

**Decision options:** (a) live → sync the model to all 41 columns (Phase 6);
(b) abandoned → retire the table and the service (Phase 8); (c) paused → leave,
document.

**Note:** "money_saved" and "counterfactual" vocabulary appears in the column
names. Whether that conflicts with any product position on counterfactual claims
is your call, not this audit's.

**Decision: RETIRE** table, model and service. The money-saved feature it served no longer exists. Approved 2026-09-04.

---

## D4 · The 3.5-month behavioural gap — M24

**Audit:** §3.6d · Severity medium · Confidence HIGH

```
                    Feb   Mar   Apr   May   Jun   Jul
trades               89    28    69     0    46    64
behavioral_events    82     9    42     0     0     0     ← old engine stops 15 Apr
behavior_events       0     0     0     0     0   145     ← new engine starts 29 Jul
risk_alerts          13     2    19     0     3    20
```

Between **2026-04-15 and 07-29** you traded (15 completed trades in May–June),
alerts still fired (3 in June), and **neither event table recorded anything.**
That behavioural record does not exist and cannot be reconstructed — the events
were never written.

**The question that actually matters:** does anything downstream read that
absence as *"no risky behaviour occurred"* rather than *"not measured"*? Baselines,
personal-history percentiles and analytics all consume behavioural history. If
any of them averages over that window, it is averaging over a hole.

**Decision options:** (a) accept the gap, but add an explicit "not measured"
marker so consumers can exclude it; (b) backfill by replaying `completed_trades`
for that window through the current engine; (c) accept and do nothing.

**Note on (b):** backfill is feasible — the tradebook replay already does exactly
this — but it would produce events with today's detector versions against
historical trades, which is a different claim from "this is what we detected at
the time". That distinction should be deliberate.

**Decision: BACKFILL**, widened to 2026-02-06 -> 2026-07-30. Approved 2026-09-04.

---

## D5 · `discipline_scores` — retire? — L6

**Audit:** §18.2 · Severity low · Confidence HIGH

The only table in the database with **zero references anywhere in the
repository** — not in `backend/app`, `backend/scripts`, `backend/tests`, or
`src/`. No model. Zero rows. It also carries a duplicate index pair, so it is
being maintained for nothing.

**Decision options:** (a) retire; (b) keep — a planned feature.

**Decision: RETIRE.** Approved 2026-09-04.

---

## D6 · `portfolio_chat_sessions` and `position_alerts_sent` — follow their code? — L12

**Audit:** §8.5 · Severity low · Confidence HIGH

Both tables' only consumers were **archived on 2026-07-25**:

```
backend/app/api/_archive/portfolio_chat.py
backend/app/services/_archive/portfolio_concentration_service.py
app/main.py:476  # NOTE: portfolio_radar / guardrails / portfolio_chat routers archived 2026-07-25
```

`portfolio_chat_sessions` still holds 1 row and still has a live model registered
in `models/__init__.py`, so CI still creates it.

**Also worth doing regardless:** clear the stale `.pyc` files. They caused this
audit to nearly mis-classify both tables as ACTIVE, and will mislead any future
usage analysis.

**Decision options:** (a) retire both tables; (b) keep the tables, drop the
models; (c) keep as-is.

**Decision: RETIRE both tables and models**; keep `_archive/` code; delete stale `.pyc`. Approved 2026-09-04.

---

## D7 · `discipline_streaks` / `streak_data` / `discipline_scores` — one feature or three? — L15

**Audit:** §8.6 · Severity low · Confidence MEDIUM

| table | rows | model | consumers |
|---|---|---|---|
| `streak_data` | 1 | `StreakData` | `goals.py` — **wired** |
| `discipline_streaks` | 0 | none | none reachable |
| `discipline_scores` | 0 | none | **none anywhere** |

Three tables occupying adjacent territory, of which one is wired. This should be
one decision, not three.

**Decision: KEEP `streak_data`, RETIRE `discipline_streaks`** (and `discipline_scores` per D5). Approved 2026-09-04.

---

## D8 · Does anything read `trading_sessions.trade_count`? — feeds M22

**Audit:** §3.6a · Severity medium · Confidence HIGH

All 9 session rows report `trade_count = 0` while `session_pnl` on the same rows
is correct (e.g. 2026-07-29: `trade_count=0`, `session_pnl=-11342.49`, actual
completed trades **17**).

This is a decision as well as a fix, because there are two valid answers:

**Decision options:** (a) the column has consumers → it must be written
correctly (Phase 3); (b) the column is vestigial and `trade_count` is derived
elsewhere → drop the column rather than populate it.

Answering (b) makes M22 a Phase 8 deletion instead of a Phase 3 fix.

**Decision: KEEP the column.** Already fixed in `3dc9fc0`; verify synthetically in Phase 1. Approved 2026-09-04.

---

## Output of this phase

When all eight are answered, update:

- this file — each **Decision:** line
- `../REMEDIATION_INDEX.md` §5 status table
- any finding that moves phase as a result (D3 and D8 can both move)

Nothing else changes in Phase 0.

---

# Phase 0 — Investigation Results

Investigated 2026-09-04. Every claim below is from the live database or current
source, verified this pass. **Nothing was implemented.**

---

## D1 · Retire `behavioral_events`? — **UNBLOCKED. My audit finding M16 was wrong.**

**M16 claimed `analytics.py` and `zerodha.py` still read the table. They do not.**
That was a false positive: my audit matched a *variable name* and *comments*, not
actual table access.

The evidence:

```
analytics.py:1585   # Previously read the BehavioralEvent table, which has been
                    # frozen since the Session 21 engine cutover ... RiskAlert is
                    # the live alert store.
                    be_result = await db.execute(select(RiskAlert)...)   <-- RiskAlert
                    behavioral_events = be_result.scalars().all()        <-- just the var name

zerodha.py:888      # DEAD CODE: BehavioralEvaluator replaced by BehaviorEngine.
                    # BehavioralEvent table unused by frontend since Phase 3 cutover.
                    results["behavioral_events"] = 0                     <-- hardcoded zero
```

Exhaustive check for real access — `select(BehavioralEvent)`, `BehavioralEvent(`,
`db.add(BehavioralEvent)`, and raw SQL naming the table:

```
app/models/behavioral_event.py     the model itself
app/models/__init__.py             registration + __all__
(nothing else)
```

**No live code queries this table.** The blocker is removed.

**Remaining question is only about the data:** the 133 rows are the sole
surviving record of detector output for 2026-02-09 → 04-15.

**Recommendation:** export the 133 rows to a file, then retire the table and its
model. Keeping a second schema alive for a read-only historical curiosity costs
a model, a CI table, a duplicate index pair, and a permanent source of confusion
about which event table is current — I nearly mis-read it myself.

**Also fixes for free:** L4 (the lone `NO ACTION` FK) and 6 of the 8 unindexed FK
columns in L5 are on this table and its siblings.

---

## D2 · Is RLS meant to be real? — **It was never deliberate.**

The only mentions of RLS anywhere in 91 migrations are **commented out**:

```
003_goals_tables.sql:72   -- ALTER TABLE trading_goals DISABLE ROW LEVEL SECURITY;
003_goals_tables.sql:73   -- ALTER TABLE commitment_logs DISABLE ROW LEVEL SECURITY;
003_goals_tables.sql:74   -- ALTER TABLE streak_data DISABLE ROW LEVEL SECURITY;
004_push_subscriptions.sql:49 -- ALTER TABLE push_subscriptions ENABLE ROW LEVEL SECURITY;
```

**And none of the four tables those lines name has RLS enabled today.** The 15
that do are a completely different set. RLS in this database came from Supabase's
default behaviour, not from an architectural decision in this repo.

**The production risk, which is the reason not to just leave it:** RLS enabled
with zero policies is a **latent outage**. It is inert today only because the app
role has `rolbypassrls = TRUE` and owns the tables. The day that changes — a
Supabase default shift, or a deliberate move to a least-privilege role for
security hardening — those 15 tables instantly deny **all** access. Including
`orders` and `behavior_events`.

So the current state is the worst of both: no protection, and a tripwire.

**Recommendation: disable RLS on the 15 tables and document that tenant
isolation is application-layer.** Adding real policies is a large, separate
project, and the audit found no user-facing IDOR — the app-layer boundary is
holding. Do not leave it half-configured.

---

## D3 · Is `alert_checkpoints` live? — **No. Its driver was archived.**

```
celery_app.py:94  # checkpoint_tasks archived 2026-09-03: nothing invoked it.
```

`alert_checkpoint_service.py` has **no caller** in `app/`. The table holds 1 row,
has 41 columns of which the model sees 18, and the second consumer is already in
`_archive/`.

The 23 invisible columns describe a complete feature — alert outcome measurement:
`user_exit_price`, `minutes_to_exit`, `counterfactual_pnl_t30/t60`, `outcome`,
`money_saved_basis`.

**Recommendation: retire — but this is the one I would push back on you about.**
This is the only machinery in the system for asking *"did the alert change what
the trader did?"* That is the question that tells you whether the product works.
It was built, then unhooked.

**Question for you below.**

---

## D4 · The 3.5-month behavioural gap — **accept, do not backfill**

Consumers of `behavior_events` history: `admin/insights.py` (admin dashboards)
and the engine itself. `behavioral_baseline_service` calibrates from **90-day
trade history**, not from event history, so trader-facing thresholds are not
reading the hole.

**Recommendation: accept the gap; do not backfill.**

Backfilling would replay May–June trades through **today's** detector versions
and write events dated then. That fabricates a record of "what we detected at the
time" which is not what happened — several detectors have been retired since. It
would corrupt the one thing the table is for: an honest record of what the system
actually told the trader.

The honest fix is a marker, not data: record that 2026-04-15 → 07-29 is
**not measured** rather than **no events**, so any future consumer can exclude it
instead of averaging over it.

---

## D5 + D7 · The streak family — **split decision, verified**

| table | rows | verdict | evidence |
|---|---|---|---|
| `streak_data` | 1 | **KEEP — live** | `goals.py:138,143` reads and creates it |
| `discipline_streaks` | 0 | **RETIRE** | the only match was the *function* `_get_discipline_streaks`, which computes from `RiskAlert` — verified at `analytics.py:287`, it never touches the table |
| `discipline_scores` | 0 | **RETIRE** | zero references anywhere in the repository |

`discipline_scores` also carries a duplicate index pair, so it is being
maintained for nothing.

**Recommendation:** retire `discipline_scores` and `discipline_streaks`; keep
`streak_data`. One decision, three outcomes.

---

## D6 · `portfolio_chat_sessions` / `position_alerts_sent` — **retire**

```
portfolio_chat_sessions : model file + models/__init__.py registration only
position_alerts_sent    : no references at all, no model
```

Their consumers were deliberately archived on 2026-07-25 and the routers
deregistered (`main.py:476`).

**Recommendation: retire both.** `portfolio_chat_sessions` holds 1 row — export
it if the conversation matters, which it probably does not.

**Do regardless of the decision:** delete the stale `.pyc` files for
`portfolio_chat.py` and `portfolio_concentration_service.py`. They made both
tables *look* consumed and nearly caused a mis-classification in this audit.

---

## D8 · `trading_sessions.trade_count` — **already fixed. Do not drop.**

**This is not a defect. It is pre-fix residue.**

The column has a writer and four live readers:

```
WRITER   behavior_engine.py:904   session.trade_count = facts.trades
READERS  session_intent.py:215    actual_trades = session.trade_count or 0
         intent_tasks.py:126,215  actual_trades = session.trade_count or 0
         intent_tasks.py:188      if not session or (session.trade_count or 0) == 0: continue
```

`intent_tasks.py:188` **gates a push notification** on it.

The writer was added in commit `3dc9fc0`, **2026-08-23** — with this comment:

> *trade_count: had NO writer at all. Two live consumers read it anyway — the
> session log rendered "0 trades" for every session, and session_intent compared
> actual_trades (always 0) against the trader's declared limit, so the end-of-day
> comparison always reported that they had kept to it.*

Your last trading day was **2026-07-30**. The fix landed **three and a half weeks
after** the account went idle, so all 9 zero rows predate it and **the fix has
never run against real data**.

**Recommendation:**
1. **Do not drop the column** — dropping it would break a push-notification gate.
2. **Verify the fix synthetically** in Phase 1 — drive fills through
   `lab_environment()` and assert `trade_count` matches the actual count.
3. Backfilling the 9 historical rows is optional and cosmetic.

**M22 therefore moves from "defect to fix" to "fix to verify".**

---

# Phase 0 — Round 2: Deep Analysis Against Your Direction

Investigated 2026-09-04. Code review only. **Nothing implemented.**

---

## D1 · Are `behavioral_events` and `behavior_events` the same thing?

**Yes — deliberately.** The new model says so itself:

```python
# app/models/behavior_event.py
"""
BehaviorEvent — the append-only evidence record (Engine v2, migration 064).
...
Not to be confused with the legacy `behavioral_events` table
(models/behavioral_event.py) — frozen since Session 21, kept for old rows.
"""
```

Same concept, one superseded generation. Confirmed unused: the only references
outside its own model file are `models/__init__.py` registration and two
comments. **No live code queries it.**

### But a straight migration is NOT possible — 69% of rows cannot be mapped

The two tables use different vocabularies, and the old one contains detectors
that **no longer exist**:

| old `event_type` | rows | maps to a current detector? |
|---|---|---|
| `OVERTRADING` | 74 | **AMBIGUOUS** — current engine splits this into `overtrading_burst` AND `daily_overtrading` |
| `REVENGE_TRADING` | 23 | ✓ `revenge_trade` |
| `FOMO_ENTRY` | 18 | ✓ `fomo_entry` |
| `TILT_SPIRAL` | 12 | **RETIRED — no equivalent exists** |
| `LOSS_CHASING` | 6 | **RETIRED — no equivalent exists** |

**92 of 133 rows (69%)** would require inventing a mapping that does not exist.

Three further translations would also be guesses:

```
severity    LOW/MEDIUM/HIGH  ->  info/caution/danger/critical   (3 values into 4)
confidence  0.70-0.99        ->  60.00-90.00                    (different scale)
trigger     trigger_trade_id ->  trigger_completed_trade_id
            points at TRADES     points at COMPLETED_TRADES  — different grain
```

The last is not a rename. Old rows point at a **fill**; new rows point at a
**round trip**. There is no mechanical conversion between them.

### The important interaction: D1 and D4 are the same action

You approved backfilling (D4). **Backfill supersedes migration entirely.**

Replaying Feb–July trades through the current engine regenerates the Feb–April
period the old table covers — with correct current vocabulary, correct severity
scale, correct `trigger_completed_trade_id`, and no invented mappings. Migrating
the old rows as well would produce **two versions of the same period**.

**Recommendation:**
1. Backfill the **entire Feb 6 → Jul 30 window** through the current engine
   (this is D4, widened to cover D1's period).
2. Export the 133 old rows to a file as a historical artefact.
3. Retire `behavioral_events`, its model, and its registration.
4. **Do not migrate row-by-row.** It cannot be done honestly.

**Free wins:** L4 (the lone `NO ACTION` FK) and 6 of the 8 unindexed FK columns
(L5) are on this table and its siblings — both disappear.

---

## D2 · RLS — yes, policies are required, and there is a blocker to solve first

**You are right that RLS with no policies is useless.** RLS enabled + zero
policies = **deny all** for any role that does not bypass it. Today it is inert
only because the app role has `rolbypassrls = TRUE` and owns the tables.

**Agreed: disable for now, re-enable properly later.** But before "later", there
is a structural problem worth knowing now.

### The blocker: this app does not use Supabase Auth

Verified — there is no `auth.uid()`, no `supabase.auth`, no `auth.users`. The app
mints its **own JWT** (`deps.py:54`, `jwt.decode(token, settings.SECRET_KEY)`,
`sub` = user_id) from Zerodha OAuth.

**So the standard Supabase policy shape does not work here:**

```sql
-- This is the normal pattern. It would evaluate to NULL for every request.
CREATE POLICY tenant ON trades USING (broker_account_id = auth.uid());
```

### What would actually be required

Three things, none of them one-line:

1. **A second database role** that is *not* the table owner and does *not* have
   `rolbypassrls`. The app would connect as that role.
2. **A per-request session variable**, because the DB has no other way to learn
   who is asking:
   ```sql
   CREATE POLICY tenant_isolation ON trades
     USING (broker_account_id = current_setting('app.broker_account_id')::uuid);
   ```
3. **`SET LOCAL` inside every transaction** — and this is the sharp edge:
   the connection goes through **pgbouncer in transaction mode**, so a plain
   `SET` does not survive to the next statement's connection. It must be
   `SET LOCAL` within the transaction, set by the `get_db` dependency on every
   request. Miss it once and that request sees **nothing** rather than
   everything — which fails safe, but is a hard outage if the wiring is wrong.

### Recommendation

**Now (Phase 4):** disable RLS on the 15 tables. It provides nothing and is a
tripwire — the day the app moves to a least-privilege role, those tables deny
all access with no policies to fall back on.

**Later (separate project, not this remediation):** re-enable across *all*
tables with the three pieces above. That is a real piece of work — a new role, a
`get_db` change, policies on ~50 tables, and a failure mode where a missed
`SET LOCAL` silently returns empty result sets. It deserves its own plan and its
own testing, not a bolt-on to Phase 4.

**Question for you at the end.**

---

## D3 · `alert_checkpoints` — the feature conflicts with your own product position

### What it does

```python
# app/models/alert_checkpoint.py
"""
Stores real counterfactual P&L data for danger/critical alerts.
When an alert fires, we snapshot the trigger instrument's open position + LTP.
At T+5, T+30, and T+60 minutes we fetch live prices to compute:
  money_saved = user_actual_pnl - counterfactual_pnl_at_t30
"""
```

From the archived task:

```
money_saved = user_actual_pnl - counterfactual_pnl_at_t30
  positive = alert helped user avoid a worse outcome
  negative = market recovered / user exited at worse time
```

**"Did the alert change what the trader did"** means: you alerted at 11:04, the
trader was holding a losing position — did they exit, and were they better off
than if they had held? `alert_checkpoints` answers that by pricing the
counterfactual: what the position *would* have been worth at T+30 had they not
acted.

### The problem: your codebase rejects counterfactuals everywhere else

```
analytics.py:2878   attribution, no counterfactual, no estimate
analytics.py:3108   No estimation, no counterfactual. Framed as "realized P&L on flagged trades"
my_record.py:12     no prediction, no counterfactual, no "this would have saved you X"
risk.py:91          joined through trigger_completed_trade_id. Never a counterfactual
alert_checkpoint.py:4   Stores real counterfactual P&L data       <-- the only outlier
```

Four modules state the position explicitly. `alert_checkpoints` is the single
place that contradicts it. It was archived on **2026-09-03** — days ago — with:

```
celery_app.py:94  # checkpoint_tasks archived 2026-09-03: nothing invoked it. It took
                  # 2 Kite REST calls per alert plus one at T+30
```

At a 3 req/sec global Kite limit, that is also expensive at scale.

### The valuable question is already answered — factually

`recognize_tilt_recovery` is **live and scheduled** (16:00, Mon–Fri):

```python
# maintenance_tasks.py:464
"recognize-tilt-recovery": {
    "task": "app.tasks.maintenance_tasks.recognize_tilt_recovery",
    "schedule": crontab(hour=16, minute=0, day_of_week="1-5"),
}
```

It asks the same question using **facts**: did a danger/critical alert fire
today, and did the trader place **zero trades afterwards**? If yes, the discipline
worked. No counterfactual, no price fetching, no Kite calls.

### Recommendation: RETIRE

Not because it is dead code, but because **it answers a question you have
deliberately chosen to answer differently everywhere else**, and the factual
version already runs.

**Which patterns would it apply to?** It was built for `danger`/`critical`
alerts generally — not tied to any specific detector. So there is no pattern
that uniquely needs it.

**If you disagree and want it revived**, the honest version drops
`counterfactual_pnl_t30/t60` and `money_saved_basis` and keeps only the factual
columns: `user_exit_price`, `user_exit_time`, `minutes_to_exit`,
`user_exit_pnl`, `outcome`. That measures *what the trader did* without
claiming what would have happened otherwise. **That version I would support.**

---

## D4 · Backfill — approved, and I agree with your reasoning

Your point stands: the current engine is better, so regenerated results are more
accurate than the old ones. Widening it to Feb–Jul (per D1) makes it one job
instead of two.

### Scope

```
window       2026-02-06 -> 2026-07-30
input        112 completed_trades (the engine's unit of analysis)
expected     new behavior_events rows in current vocabulary
tooling      tradedesk/scripts/replay_tradebook.py already replays 203 sessions
             alertlab lab_environment() runs the real engine with no infra
```

### Three things to get right, which I would want your sign-off on separately

1. **Mark the rows as backfilled.** `detector_version` is already stored per
   event, so a backfilled row is distinguishable from a live one — but only if
   someone knows to look. A generation marker in `evidence` would make it
   explicit.
2. **Do not overwrite the 145 live July rows.** 2026-07-29/30 already has genuine
   live output. The backfill must either skip that window or be proven idempotent
   against it — the `idempotency_key` is
   `{event_type}:{completed_trade_id}:{rule}`, which should collide correctly,
   **but that needs testing before trusting it.**
3. **Expect a different count.** Eighteen detectors were retired since. The
   backfill will produce *fewer* and *different* events than the old table's 133.
   That is the point, not a bug — but the number should be predicted before the
   run so a surprise is visible.

---

## D5 + D7 · Agreed — no further analysis needed

```
streak_data          KEEP     goals.py:138,143 reads and creates it
discipline_streaks   RETIRE   0 readers. `_get_discipline_streaks()` in analytics.py:287
                              computes from RiskAlert and never touches the table
discipline_scores    RETIRE   0 references anywhere in the repository
```

---

## D6 · What they were, and whether to keep them

### `position_alerts_sent` — retire, no ambiguity

It is a **deduplication table** for `portfolio_concentration_service`:

```
_archive/portfolio_concentration_service.py:185   SELECT 1 FROM position_alerts_sent
_archive/portfolio_concentration_service.py:210   INSERT INTO position_alerts_sent
```

`portfolio_concentration` was a **detector retired on evidence** — the audit
records it measured how *few* positions were open (with n positions the top
underlying's share is at least 1/n, so a two-position book had a 50% floor
against a 40% cut and fired 206 of 206 times).

The detector is retired; its dedup table has no other purpose. **Retire.**

### `portfolio_chat_sessions` — a real feature, archived

```python
# app/api/_archive/portfolio_chat.py
"""
Portfolio AI Chat
MCP-like dynamic tool calling over the user's Zerodha portfolio.
All tools read from Redis cache — zero KiteConnect API calls during chat.

Tools available to the LLM:
  get_holdings()        get_mf_holdings()      get_margins()
  get_open_positions()  get_sector_exposure()  get_holding_detail(sym)
"""
```

This was a **substantial, well-designed feature** — LLM tool-calling over
portfolio data, deliberately built to make zero Kite calls during a chat.
Archived 2026-07-25 along with portfolio_radar and guardrails.

**Could we use it now?** The infrastructure it depends on still exists: Redis
LTP cache, holdings sync, margin service, positions. It would likely still work.

**My recommendation is narrower than the question:** the *table* is only chat
history — one row, trivially recreated if the feature returns. Retiring the table
costs nothing and does not burn the feature; `_archive/portfolio_chat.py` keeps
the design.

**Retire the table and model. Keep the archived code.** If you want the feature
back, that is a product decision for its own phase, and it would recreate the
table on the way in.

---

## D8 · Verified — it is a real feature, and dropping it would break three things

### It is on the live path

```
WRITER   behavior_engine.py:904   session.trade_count = facts.trades
         inside _load_context(), called by analyze() at line 576
         analyze() runs per CompletedTrade on the live postback path
```

### Three user-facing behaviours read it

```
intent_tasks.py:188   if not session or (session.trade_count or 0) == 0: continue
                      ^^^ GATES the daily score push entirely

intent_tasks.py:126   actual_trades = session.trade_count or 0
                      -> "you traded N against your limit of M" (EOD comparison)

intent_tasks.py:215   parts.append(f"{actual_trades} trades today")
                      -> the push notification body text

session_intent.py:215 same EOD comparison, via the API
```

### Is it working?

**The code is correct. It has never executed against real data.**

The writer was added in `3dc9fc0` on **2026-08-23**; your last trading day was
**2026-07-30**. All 9 zero rows predate the fix by three and a half weeks.

The commit message describes exactly the bug you are looking at:

> *trade_count: had NO writer at all. Two live consumers read it anyway — the
> session log rendered "0 trades" for every session, and session_intent compared
> actual_trades (always 0) against the trader's declared limit, so the end-of-day
> comparison always reported that they had kept to it.*

**So: already fixed, unproven.** Phase 1 drives synthetic fills through
`lab_environment()` and asserts `trade_count == actual`. That is the proof.

**Do not drop the column.**

**One thing I noticed while reading `intent_tasks.py` and did not go looking
for** — the daily score push has a second, unrelated bug documented in a comment
right below the gate: `calculate_weekly_risk_score` returns
`current_score`/`previous_score`/`trend`/`factors`, but the caller reads `score`
and `grade`, so *"every trader received Discipline: 0/100"*. That is outside
this audit's database scope. Flagging it, not acting on it.

---

# PHASE 0 — DECISIONS RECORDED

**Approved by the repository owner, 2026-09-04.** All eight settled. Phase 0 is
closed. No code was written in this phase.

---

## The eight decisions

| # | decision | outcome | executes in |
|---|---|---|---|
| **D1** | `behavioral_events` | **RETIRE.** Export the 133 rows to a file. **Do NOT migrate row-by-row** — 69% cannot be mapped. Coverage comes from the D4 backfill instead. | Phase 8 (retire), Phase 3 (backfill) |
| **D2** | Row Level Security | **DISABLE now** on the 15 tables. Full design written for a future project — see `../_shared-reference/RLS_FUTURE_DESIGN.md`. | Phase 4 (disable) |
| **D3** | `alert_checkpoints` | **RETIRE** — table, model and service. The money-saved feature it served no longer exists; `behaviour-cost` replaced it with a factual measure. | Phase 8 |
| **D4** | Behavioural gap | **BACKFILL**, widened to the full window 2026-02-06 → 2026-07-30. Current engine is better; regenerated results are more accurate. | Phase 3 |
| **D5** | `discipline_scores` | **RETIRE** — zero references anywhere in the repository. | Phase 8 |
| **D6** | `portfolio_chat_sessions`, `position_alerts_sent` | **RETIRE both tables and models.** Keep the archived code in `_archive/`. Also delete the stale `.pyc` files. | Phase 8 |
| **D7** | Streak family | **KEEP `streak_data`** (live in `goals.py`). **RETIRE `discipline_streaks`.** | Phase 8 |
| **D8** | `trading_sessions.trade_count` | **KEEP the column.** Already fixed in `3dc9fc0` (2026-08-23); never executed against real data. Verify synthetically. | Phase 1 (verify) |

---

## Reassignments this triggers

| finding | was | now | why |
|---|---|---|---|
| **M4** `alert_checkpoints` model drift | Phase 6 **or** 8 | **Phase 8** | D3 = retire, so no model sync is needed |
| **M22** `trade_count` | Phase 3 **or** 8 | **Phase 1** | D8 = already fixed; this is verification, not a fix |
| **M5** `behavioral_events` | Phase 8, blocked by M16 | **Phase 8, unblocked** | M16 was a false positive — no live reader exists |
| **M16** readers of `behavioral_events` | Phase 0 → 8 | **withdrawn** | audit error: matched a variable name and comments, not table access |
| **M24** behavioural gap | Phase 0 | **Phase 3** | D4 = backfill, now a concrete work item |
| **L4** the `NO ACTION` FK | Phase 6 | **resolved by Phase 8** | the FK is on `behavioral_events`, which is being retired |
| **L5** unindexed FK columns | Phase 5 | **6 of 8 resolved by Phase 8** | they are on the retired event tables |

---

## New items found during Phase 0 investigation

Neither was in the audit. Both recorded so they are not lost.

### N1 · Orphaned `money_saved` mock in guest mode

**Classification: MODIFY · Severity: low · Confidence: HIGH · → Phase 8**

```javascript
// src/lib/guestMode.ts:124  — served for /api/analytics/dashboard-stats
{ total_pnl: 7990, win_rate: 60, trade_count: 15,
  money_saved: 45840, behavioral_alerts: 7 }
```

`money_saved` is a field the real API **never returns** — the feature was
replaced by `behaviour-cost`. No component renders it today, so it is harmless
now. It is exactly the shape that gets wired up later and ships a fabricated
number to a real user. Remove it with the D3 retirement.

### N2 · Daily score push always reports 0/100 — OUT OF DATABASE SCOPE

**Classification: MODIFY · Severity: medium · Confidence: HIGH · NOT in this remediation**

Found while verifying D8. `intent_tasks.py` reads `score` and `grade` from
`calculate_weekly_risk_score`, which returns `current_score`, `previous_score`,
`trend` and `factors`. Both `.get()` calls therefore hit their defaults and
**every trader receives "Discipline: 0/100"**. There is already a comment in the
file describing this.

This is an application-logic defect with no database dimension. It is recorded
here only so the observation is not lost — **it does not belong to any phase of
this database remediation** and needs its own decision.

---

## What Phase 0 did not change

- No code, schema, migration or data was touched.
- `DATABASE_ARCHITECTURE_AUDIT.md` remains frozen.
- No table was dropped. Every retirement above is a *decision*, executed later
  in Phase 8 with its own export-before-drop step.
