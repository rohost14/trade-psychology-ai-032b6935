# behavior_events Partitioning — Design, History, Operations
*P2 Runtime Architecture Migration · finalized 2026-07-15*

## 1. Why partition this table at all

`behavior_events` is the engine's evidence log: every detection writes a row.
The Principal Engineer review (S8) ranked it the **first thing that breaks at
scale** — at the 50k-user target it takes 5–15M rows/day of JSONB-heavy data.

Two problems on a normal (unpartitioned) table at that volume:

1. **Retention.** Evidence older than ~90–180 days must be removed. On a
   normal table that's `DELETE ... WHERE detected_at < X` over millions of
   rows: hours of runtime, table bloat, vacuum pressure, index churn. On a
   partitioned table it's `DROP TABLE behavior_events_y2026m07;` — an
   instant metadata operation.
2. **Query locality.** Scores, death spiral, and analytics only ever read
   recent windows. Partition pruning means those queries touch one or two
   month-tables instead of scanning years of history.

**Why we did it NOW, at ~zero rows:** Postgres cannot convert an existing
table to partitioned in place. The only path is new-table + copy + swap.
With 0 rows that swap is free; with a billion rows it is a weekend outage.
We paid the cost while the cost was nothing.

## 2. Why MONTHLY child tables — and what they actually are

Postgres declarative partitioning physically stores each range as its own
child table (`behavior_events_y2026m07`, `..m08`, ...). This is plumbing,
not schema you manage:

- Application code reads and writes **only `behavior_events`** — Postgres
  routes every row to the right child automatically (verified live: a test
  insert landed in `behavior_events_y2026m07`).
- Monthly granularity matches the retention unit (drop whole months) and
  keeps per-partition size sane at target volume (~150–450M rows/month →
  still large; sub-monthly granularity is a later knob if ever needed).

## 3. History: original design → user challenge → final design

| | Original (067 v1) | Final (067 v2 + task) |
|---|---|---|
| Future partitions | 12 pre-created (Jul'26–Jun'27), **manual** yearly addition documented in a comment | **Auto-created by a Celery beat task** — rolling window of current month + 3 ahead |
| After the pre-created range ran out | Rows silently fall into the DEFAULT partition; nothing errors, but DEFAULT grows unbounded and the partitioning benefit quietly evaporates — a manual chore that **fails silently** | Cannot happen while the task runs; DEFAULT demoted to pure safety net |
| Legacy table after copy | `DROP TABLE` in the migration | **Kept** as `behavior_events_legacy`; drop is an explicit manual step after verification |

Both changes came from a direct user challenge ("create tables by hand for
lifetime?", "why drop legacy?") — both were correct.

## 4. The Celery job

**Task:** `app.tasks.maintenance_tasks.ensure_behavior_event_partitions`
**Schedule:** 1st and 15th of every month, 02:00 IST (twice monthly purely
for redundancy — the task is idempotent).

What it does each run:
1. For current month + 3 months ahead: check `pg_tables` for
   `behavior_events_yYYYYmMM`.
2. If missing → `CREATE TABLE ... PARTITION OF behavior_events FOR VALUES
   FROM (month-start) TO (next-month-start)`.
3. Existing partitions are skipped — running it twice, or after a missed
   month, is harmless.

Month arithmetic is unit-tested including year rollover (Dec→Jan). Failure
retries twice with 5-min backoff and logs ERROR. Even a task dead for
3+ months only means rows land in DEFAULT — data is never lost, and rows
can be re-homed from DEFAULT later.

## 5. Two schema consequences of partitioning (accepted, documented)

Postgres requires unique constraints on partitioned tables to include the
partition key. Therefore:

- **No DB-level primary key.** The table is append-only evidence; nothing
  joins into it by `id`. The ORM keeps its declarative `id` pk (mapper
  only); the DB keeps `id` as an indexed plain uuid column.
- **The idempotency unique index is `(broker_account_id, idempotency_key,
  detected_at)`.** Semantics preserved because `detected_at` is
  deterministic per key — the engine always sets it to the trigger trade's
  exit time, so a retry/re-sync produces the identical tuple and still
  conflicts. This assumption is load-bearing: if detected_at semantics
  ever change for keyed events, revisit this index.

## 6. Current live state (verified 2026-07-15)

- `behavior_events` — partitioned parent (relkind `p`), 4 indexes
- Partitions: `y2026m07 … y2026m10` (created via the task's own logic —
  the automation is proven live) + `behavior_events_default`
- Insert routing verified (test row → y2026m07, rolled back)
- `behavior_events_legacy` — **0 rows** (the engine had never run live
  before the swap, so the copy step was a no-op). Safe to drop whenever:
  `DROP TABLE behavior_events_legacy;`

## 7. Ops runbook

| Action | Command / where |
|---|---|
| Check partitions exist | `SELECT tablename FROM pg_tables WHERE tablename LIKE 'behavior_events_y%' ORDER BY 1;` |
| Retention (drop a month older than policy) | `DROP TABLE behavior_events_y2026m07;` |
| DEFAULT partition should stay empty | `SELECT COUNT(*) FROM behavior_events_default;` — nonzero means the beat task missed months; create the proper partitions, then re-home rows |
| Force partition creation now | trigger `ensure_behavior_event_partitions` from admin tasks / celery |
| Drop the legacy shell | `DROP TABLE behavior_events_legacy;` (0 rows, safe now) |

Retention policy itself (90 vs 180 days, cold archive before drop) is a
product decision deferred until real volume exists.


---
---

# PART 2 — How the Behavioral Engine Works (End-to-End)
*Added on user request, 2026-07-15. Honest status: code-complete; shadow
soak/cutover awaits live trading days; one real gap found by the user's own
question (capital validation, section 4).*

## 1. The core loop

```
Zerodha fill (webhook, ~instant)
  -> trade saved, positions synced, FIFO pairs entries/exits
Position CLOSES -> CompletedTrade (a full round trip, the engine's unit)
  -> behavior_lock per account (ordering); idempotency pre-check (retries safe)
BehaviorEngine.analyze()
  -> loads: profile+constitution, today's trades, cooldowns, strategy group,
     exit order types; thresholds = Constitution > Baseline > Defaults
     (+ SessionState shadow-fold compared per trade - the migration gate)
27 registered detectors run (registry-driven)
  -> each returns event(s) with severity + confidence + evidence
  -> suppression marks (strategy legs / constitution wins) - never deletes
EVERY detection -> BehaviorEvent row (evidence, idempotent insert)
Non-info, non-suppressed -> RiskAlert (the notification record)
  -> dedup: per pattern (per rule for constitution), escalation passes,
     re-arm when the driving metric worsens >=20%
Death Spiral meta-check (reads today's evidence, 4 domains)
Routing: severity x staleness -> in-app (WebSocket, instant) / push /
guardian WhatsApp (eligible patterns only, 3/month hard budget)
Scores recompute on read: 4 drivers -> Behavior Risk headline
```
ALSO at every FILL (entry-time, position still open): overexposure/All-In
ladder, portfolio concentration, cooldown + no-trade-window constitution
checks - inline in the worker with live LTP.

## 2. What fires, when (user-facing summary)

| You do this | Engine fires | Severity | Where you see it |
|---|---|---|---|
| Re-enter within your cooldown after a loss (same underlying / bigger size / session red stack confidence) | revenge_trade or constitution cooldown rule | caution-danger | in-app; push at danger |
| 3 / 5 losses in a row | consecutive_loss_streak (or YOUR consec rule) | caution/danger | in-app + push |
| 5+ round-trips in 30 min while losing | overtrading_burst | caution/danger | in-app/push |
| Cross your daily trade count | daily_overtrading / YOUR daily_trades rule | ladder | in-app/push |
| Size up after losses (same underlying) | martingale / size_escalation / recovery_bet | up to danger | push at danger |
| Lose 40/60/80% of option premium (expiry-adjusted) | premium_loss_event | caution/danger/critical | push at 60%+ |
| Flip direction within minutes (CE<->PE or long<->short); 3+ flips = whipsaw | direction_instability | caution/danger | in-app |
| Chase one underlying: 3+ losses, repeated re-entries, size rising | same_symbol_obsession | caution/danger | in-app/push |
| Hit 80/100/120% of ANY of your own rules | constitution_violation ("YOUR rule" framing) | caution/danger/critical | in-app -> push -> guardian-eligible |
| Session loss at 40/75% of your daily limit | session_meltdown | caution/danger | push + guardian |
| Enter during your historical losing hour (needs 30+ sessions of data) | time_of_day_bias | caution | in-app |
| Enter oversized while position OPEN: 1.5x/2x limit, 30%/50% of capital | overexposure -> labeled "ALL-IN BET" at 50% | up to critical | push, immediate |
| One underlying = 40/60/80% of open book (2+ underlyings) | portfolio_concentration | up to critical | push |
| Multiple systems agree you're spiraling AND you keep trading after the breach | death_spiral | warning/danger/critical | in-app -> push -> push+guardian |
| Panicky quick exits, cutting winners early, opening-trap trades, fast re-entries | evidence ONLY (info) | - | Analytics/Journal, feeds scores - never interrupts |

Every alert carries its evidence: the exact trades (symbol, qty, P&L,
times), thresholds crossed, and for confidence-scored patterns the signal
list - the frontend shows WHY, not just WHAT. Surfaces: bell + Alerts page
(live via WebSocket), Dashboard "Behavior Risk" chip (Normal/Elevated/High/
Critical), My Patterns score card (headline + 4 driver bars + top
contributors with age), Journal/EOD for the analytics-only patterns.

## 3. My Rules tab - yes, it exists (top-level nav, /my-rules)

Rules users predefine (onboarding step 4 - prefilled recommendations from
experience + capital, explicitly ACCEPTED for ownership - or later in the
tab): daily loss limit (Rs) | max trades/day | max risk per trade (% of
capital) | cooldown after loss (min) | stop after N consecutive losses |
no-trade windows (IST) | guardian on/off.

Tab sections: live "today vs your rules" progress bars (green <80%, amber
approaching, red breached), cooldown countdown, today's violations +
30-day count per rule, full change history, edit dialog.

Change control (the psychological core): TIGHTEN = instant, always.
LOOSEN = friction dialog ("You are relaxing your own rules... this will be
recorded"), and during market hours the change only takes effect NEXT
session - the mid-tilt limit raise is dead. Every change audited
(constitution_history); the override itself is a behavioral signal.
Settings cannot bypass any of this.

## 4. The wrong-capital problem - HONEST STATUS: real gap, not yet built

User scenario: actual margin Rs 20k, declared capital Rs 80k. Consequence
today: every %-of-capital rule is 4x too loose - overexposure fires at 4x
the real threshold, "2% daily loss" is actually 8% of real money, and the
onboarding recommendations were computed from fiction. NOTHING currently
validates declared capital against broker reality; it is trusted as a
"factual input".

What makes the fix cheap: the webhook path already fetches live Zerodha
margins on every fill (Redis-cached 60s) and margin_snapshot rows exist.
The data is in hand; the reconciliation isn't.

Designed fix (next build slot):
1. Nightly + on-broker-connect: compare declared trading_capital vs total
   deployable (available margin + margin used) from the margins API.
2. Persistent discrepancy (e.g. declared > 1.5x actual for 3+ sessions)
   -> nudge: "Your rules assume Rs 80k capital; your account shows Rs 22k.
   Your rules are effectively 4x looser than you set them." One-tap update.
3. Updating capital DOWN = tightening = instant; dependent Rs-rules (daily
   loss) get a recompute prompt.
4. NEVER auto-overwrite - capital drives rule psychology; silent changes
   break ownership. Nudge + confirm only.
Why a band + persistence test, not equality: margin != capital exactly
(funds parked elsewhere, pledged holdings) - hence nudge, not enforcement.

## 5. Everything else, one paragraph each

PERSONALIZATION: nightly (18:15 IST) baseline learning computes YOUR
normals (trades/day, re-entry pace, hold times, win rate, profit factor,
peak/drawdown), each metric with its own confidence; thresholds blend
continuously conf x personal + (1-conf) x default. A 25-trade/day scalper
gets an overtrading line at 38; a 2-trade positional at 3. No cliffs; cold
start = research defaults. EVIDENCE VS NOTIFICATION: every detection is
stored (partitioned, idempotent) even when suppressed - suppression only
silences the ping, never the record, so scores and the death spiral always
see the truth. SCORES: Tilt/Risk/Discipline/Strategy from evidence with
90-min exponential decay; headline = dominant driver (Tilt 95 reads ~95,
never an average). GUARDIAN: only meltdown, constitution breach and
critical death spiral can ever reach the guardian WhatsApp, max 3/month -
and critical spiral additionally requires the trader KEPT OPENING positions
after the breach; the trader who stops is spared. OPS: every stage timed,
e2e SLO (<3s) measured per trade, admin /engine-metrics with red flags
including "state drift - MIGRATION BLOCKED".

## 6. Honest "is everything done?" checklist

| Area | Status |
|---|---|
| 8 roadmap phases (0-7) + P0/P1 review fixes + P2 increment 1 | DONE - 10 smoke suites + engine tests + parity gate green |
| Every user-raised issue this project (558% false positive, 5:05pm alerts, dead adaptive wiring, profile-ignored bug, duplicate events, silent skips, partition lifecycle, legacy-drop caution) | FIXED and validated |
| Shadow soak -> detector cutover -> day-cache -> delete rescan | PENDING live trading days (by design - the shadow schedule) |
| Capital-vs-margin validation (section 4) | KNOWN GAP - designed, not built |
| behavioral_analysis_service retirement; fomo/overconfidence confidence; precision metrics (needs feedback labeling); live-price rules; nav restructure | DEFERRED, documented |
| User actions | drop behavior_events_legacy; /my-rules browser pass; trade a session then check /engine-metrics |
