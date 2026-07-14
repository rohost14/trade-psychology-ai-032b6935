# Behavioral Engine v2 — Principal Engineer Review
*Brutal production review of the AS-BUILT system (not the paper spec). 2026-07-14.*
*Workload assumption: 50k users · 100 trades/user/day ≈ 5M trades/day · peak 09:15–11:00 · alert SLO 1–3s · target 500k users.*

**TL;DR: The behavioral logic is genuinely good. The runtime that executes it is a per-trade full-rescan monolith that will not survive 50k users without a re-architecture of the hot path. The spec (doc 2) described an O(1) state machine; what was built is an O(N²)-per-session query storm. At current single-user scale it is fine. At 5M trades/day it falls over — first the `behavior_events` table, then Supabase connections, then Celery queue depth. There is also one latent correctness bug (duplicate BehaviorEvents on bulk sync) that corrupts scores TODAY at any scale.**

---

## SECTION 1 — OVERENGINEERING REVIEW

| Component | Verdict | Notes |
|---|---|---|
| Detector Registry | **Keep exactly** | Cheap, declarative, already paying for itself (doc regen, versioning, stats). Zero runtime cost. |
| Detector versioning | **Keep** | One column + one lookup. Correctly cheap. |
| BehaviorEvent (evidence) layer | **Keep concept, fix implementation** | The idea (evidence ≠ notification) is right. The implementation writes 1 row per detection incl. info-noise with full JSONB evidence + input_snapshot on EVERY event. At 5M trades/day this is the single largest cost in the system. Needs severity-gated snapshotting and retention (see S8). |
| input_snapshot per event | **Overengineered as-built** | Session trade-ID arrays serialized per event per trade → O(N) JSONB per event, O(N²) per session. Replayability doesn't need it — replay reconstructs from CompletedTrades anyway (and does, in replay_engine.py, which never reads input_snapshot). **Recommend: drop or sample it.** It is write-amplification for a feature the replay tool doesn't use. |
| SessionState module | **Half-built abstraction** | Beautiful fold, ownership table, rebuild parity tests — and the LIVE engine doesn't use it. Only replay does. Either wire it into the hot path (the actual doc-2 design) or admit it's a replay utility. Currently it's documentation with unit tests. |
| Composite scores (4 drivers + headline) | **Keep** | Pure function over events, computed on request. Correctly lazy. The 120s dashboard poll needs a cache (S3). |
| Death Spiral | **Keep logic, fix trigger cost** | Runs per trade close and re-reads ALL today's BehaviorEvents each time → O(events)·per-trade. At 100 trades/day with multi-event trades that's rescanning thousands of rows daily per user. Should consume an in-memory/Redis domain-flag set, not re-query. |
| Constitution engine | **Keep exactly** | Highest product value per line of code in the system. Lock semantics, history, suppression — all justified. |
| Baseline confidence blend | **Keep** | Elegant, O(1) at read time, nightly compute. Exactly right. |
| Confidence signal-stacking (revenge) | **Keep** | Cheap, effective. |
| Replay harness | **Keep** | Best engineering investment in the project. Found real bugs 3 times. |
| Data-quality flags | **Keep, currently shallow** | Only source-based today. Fine — don't deepen until webhook-gap detection exists. |
| Guardian budget | **Keep** | One query per danger alert. Correct. |
| Dedup v2 (worsening re-arm) | **Keep, relocate** | Logic is right; implementation loads all 24h alerts into Python per trade. Move to keyed lookup (S3). |
| Entry-time tasks (concentration/entry-rules per fill) | **Partially overengineered dispatch** | Firing `check_portfolio_concentration` on EVERY fill (5M/day) when it only matters on position-opening fills, and each task opens 2–3 separate DB sessions. Gate on BUY/position-increase and coalesce sessions. |
| Explainability evidence arrays | Keep | Cheap relative to value. |

**Nothing deserves deletion. Two things deserve demotion (input_snapshot, per-fill concentration dispatch) and one thing must stop pretending (SessionState is not in the hot path).**

---

## SECTION 2 — COMPLEXITY ANALYSIS

N = trades so far in a user's session (up to ~100). E = BehaviorEvents today per user.

| Subsystem | Time | Space | Mem growth | CPU | DB cost | Net | Queue |
|---|---|---|---|---|---|---|---|
| analyze() context load | O(N) query + O(N) rows/trade → **O(N²)/session** | O(N) | Low | Medium | **High** (5–8 queries/trade) | Low | — |
| 27 detectors | O(N) each, some O(N·parse) → O(27N)/trade | O(N) | Low | **High** (Python, instrument_parser re-parses same symbols dozens of times per trade) | — | — | — |
| BehaviorEvent writes | O(events) | O(E) rows | **Very High** (unbounded table, ~1–3 rows/trade ⇒ 5–15M rows/day at target) | Low | **Very High** | Low | — |
| Dedup (both paths) | O(alerts_24h) load/trade | O(A) | Low | Low | Medium | — | — |
| Death spiral | O(E)/trade | O(E) | Low | Medium | **High** (full-day event scan per trade) | — | — |
| Scores endpoint | O(E)/request | O(E) | Low | Low | Medium | Low | — |
| Constitution service | O(1) | O(1) | Very Low | Very Low | Low | — | — |
| Baseline nightly | O(90d trades)/user/night | O(T) | Low | Medium | Medium (nightly, off-peak) | — | Low |
| Position monitor (per fill) | O(positions) | O(P) | Low | Low | Medium ×3 sessions/task | Low | **High** (3–4 extra tasks/fill) |
| Notification path | O(1) | O(1) | Very Low | Low | Low | Medium | Low |
| Replay | O(window·N) | O(T) | — | High (offline) | High (offline) | — | — |

**Hidden complexity**: instrument_parser called inside loops inside detectors inside a 27-detector loop — same symbol parsed hundreds of times per trade. No memoization.
**Interaction complexity**: suppression matrix (strategy × constitution × options-overlap) + dedup escalation + worsening re-arm interact in one function chain; currently correct, verified only by smoke tests; a new detector author WILL get this wrong without a written invariants doc.
**Maintenance complexity**: behavior_engine.py ≈ 2,400 lines, one class. Registry mitigates, file size doesn't.
**Operational complexity**: LOW today (no Redis state, no Kafka) — the flip side is that Postgres carries everything.

---

## SECTION 3 — REAL-TIME FEASIBILITY (50k users, 5M trades/day)

Peak: assume 40% of volume in 09:15–11:00 ⇒ ~2M trades/105min ⇒ **~320 completed trades/sec**, burstier in first 15 min (likely 800–1000/s spikes).

**Verdict: the current implementation does NOT meet 1–3s at this load. It meets it at ~1–5k users.**

Per completed trade the webhook path performs (measured from code): trade upsert + position sync + margin + FIFO + **analyze(): profile query, session get/create, session-trades query (grows to 100 rows), cooldowns, strategy group, exit order types, dedup 24h-alert load, event+alert inserts, death-spiral full-event load, session risk update** + 3–4 spawned Celery tasks each opening fresh DB sessions. Conservatively **12–18 Postgres round-trips per trade**. At 320/s ⇒ **4–6k QPS** against a single Supabase Postgres through Supavisor — plus insert volume of 5–15M behavior_events rows/day. Not survivable.

Bottleneck ranking (first to fall):
1. **behavior_events INSERT volume + table bloat** — unpartitioned, JSONB-heavy, 2 indexes; write amplification from info events + input_snapshot.
2. **Supabase connection ceiling** — position_monitor tasks open 2–3 `SessionLocal` each; 4 tasks/fill × 320/s ⇒ thousands of short-lived pooled connections/sec. Supavisor already showed fragility (idle-in-transaction incidents during this project).
3. **behavior_lock serialization + silent skip** — per-account lock with 3×2s retries then **skips detection and returns success** (`behavior_skipped: True`). A scalper's burst (10 fills/30s) guarantees skipped detections at exactly the moments that matter most. This is a *correctness* hole disguised as a scaling valve.
4. **Celery queue depth** — ~4–5 tasks/trade ⇒ 20–25M tasks/day on Redis broker; workers dominated by DB wait.
5. **Death-spiral/dedup rescans** — O(day) reads per trade.
6. Notification path — fine (async, low volume).

**Race/ordering/duplication:**
- Per-account lock gives ordering within an account (good) — at the price of item 3.
- **CONFIRMED DEFECT: duplicate BehaviorEvents on bulk sync.** `run_behavior_engine_full_session` re-runs analyze() over trades the webhook path already processed. Alert dedup absorbs the RiskAlerts, but **event inserts have no idempotency** — every manual sync duplicates the day's evidence rows. Consequences: driver scores inflate after each sync; death spiral counts duplicated domain events (false criticals possible); detector-stats corrupted. This is live today at single-user scale. Fix: event-level idempotency key `(broker_account_id, detector, trigger_completed_trade_id)` unique index, upsert-ignore.
- Out-of-order webhooks: FIFO layer's problem; engine tolerates via sorted() but dedup `detected_at` reference can mis-window on late fills. Low frequency, acceptable.
- **DEFECT (data lineage): time_of_day_bias consumes `danger_hours` computed by legacy `_learn_time_patterns` from `Trade.pnl` — which is always 0.** With pnl=0, win_rate defaults to 50%, the `<35%` filter never matches ⇒ danger_hours is permanently empty ⇒ the detector is dead on arrival. baseline_service deliberately avoided Trade.pnl; time_patterns was never migrated. Must be rebuilt on CompletedTrades before the detector is real.

---

## SECTION 4 — STATE ANALYSIS

| State | Owner | Verdict |
|---|---|---|
| TradingSession row (risk_score, session_pnl) | DB | **session_pnl is recomputed from trades inside _load_context on every call and written back as a side effect** — it's derived state masquerading as stored state. Either trust the fold or trust the row; currently both, reconciled per-trade. |
| SessionState (module) | code | Duplicate of the above responsibilities, used only by replay. **Merge direction: make SessionState the computation, TradingSession the persistence of its output.** |
| user_state | — | **Does not exist as designed.** Doc-2 fields (consecutive_losses, last_loss_time, tilt score) are recomputed from scratch per trade/request. Honest, but the "state model" of the spec is aspirational. |
| position_state | — | Also virtual: Position table + LTP cache read per task. Fine — this one genuinely shouldn't be duplicated into another store. |
| behavior_baseline | detected_patterns JSONB | Single-owner, nightly, clean. Keep. |
| constitution | UserProfile columns | Single-owner after the Phase 2 migration. Clean. |
| BehaviorEvents | table | Single source of evidence — correct — but **also the hot-path read model** for scores + death spiral, which is what makes every read O(day). Derived aggregates (per-domain danger flags, running driver sums) should be cached; events remain the source of truth. |

**Duplications**: session P&L exists in 3 forms (TradingSession row, per-call recompute, SessionState). Consecutive-loss streak computed independently in 3 detectors + constitution + SessionState. One shared per-context precomputation would delete ~5 copies of the same loop.

---

## SECTION 5 — DETECTOR ANALYSIS

- **All 27 on every event: acceptable in count, wasteful in shape.** 27 Python calls are nothing; 27 × O(N) rescans with repeated symbol parsing are not. Fix the shared work, not the fan-out: precompute once per analyze() — parsed underlyings, per-underlying trade groups, streak, pnl aggregates — and pass in ctx. Estimated 5–10× CPU reduction, zero behavioral change.
- **Grouping/indexing by event type: yes, at Phase-6 maturity.** Registry already has `trigger`; the loop ignores it. When entry-time events become first-class, filter by trigger — free win, field already exists.
- **Plugins: no.** In-process registry is correct at this team size. Plugin infrastructure would be pure ceremony.
- **Parallel execution: no.** Detectors are microseconds once shared work is hoisted; asyncio/thread fan-out adds overhead and ordering hazards for nothing. Sequential is right.
- **Ceiling**: with hoisted shared context, 100+ detectors stay sub-10ms CPU. The real ceiling is per-event WRITE volume, not detector count.

---

## SECTION 6 — EVENT PIPELINE REVIEW

Actual pipeline: webhook → Celery → [trade upsert → position sync → margin → FIFO → analyze (context+detect+persist) → death spiral → consolidation → notify] → spawned position tasks.

Latency budget per trade at scale (est.): queue wait 50–500ms (peak: seconds) · context queries 30–80ms · detectors <5ms (post-hoisting) · event/alert writes 10–30ms · death spiral 20–60ms · notify async. **The queue and the query count dominate; detector logic is irrelevant to latency.**

Reordering that pays:
1. **Notify before analytics-grade persistence** — compute alerts, dispatch push, then batch-write events. Cuts perceived latency by the write+spiral cost.
2. **Fold position-monitor tasks into the same worker invocation** (they already have the DB session and the fill) — removes 3–4 task hops and their connection churn.
3. **Cache per (account, day)**: profile+thresholds (invalidate on constitution change), today's dedup keys, domain-flag set for death spiral. Removes 4–6 queries/trade.
4. Margin fetch, WS publishes: already async/cached — fine.

---

## SECTION 7 — BEHAVIOREVENT REVIEW

- **Detectors producing events (not mutating state): correct.** Keep. State mutation from 27 places was the old engine's disease.
- **Too generic? No — slightly too heavy.** evidence JSONB is right; **input_snapshot is dead weight** (see S1); message duplicated between alert and event (denormalization is fine, but it's the 3rd copy including push payload).
- **Missing fields**: `session_date` (every consumer recomputes IST bucketing — should be a column), `idempotency_key` (the S3 defect), `schema_version` for evidence payloads (evidence shape already varies per detector version with no marker).
- **Verbosity**: info-severity noise events (weak-signal revenge at 30 confidence, every panic_exit) are ~half the write volume with near-zero read value. Severity-gate the persistence of sub-gate info events behind sampling, or aggregate them into a daily rollup.
- Would I rebuild it? No — I'd amend it: unique key, session_date, drop snapshot, gate info writes, partition by month.

---

## SECTION 8 — SCALABILITY REVIEW (500k users, 50M trades/day)

**Current implementation: no. Not a tuning matter — a redesign of the hot path.**

Breaks in order:
1. **behavior_events**: 50–150M rows/day, ~1–3 TB/month with JSONB. Unpartitioned. Dead at week one. Needs: monthly partitions, 90-day hot retention → cold storage, info-event suppression, snapshot removal.
2. **Single Postgres**: 40–60k QPS mixed read/write. Needs the O(1) state machine the spec promised: per-account running state (Redis or a state row) so analyze() does ~2 reads + batched writes instead of 12–18 round-trips. This is doc-2 §"User State Model" — specified, never built.
3. **Celery/Redis broker**: 200M+ tasks/day. Needs task coalescing (S6.2) and batch consumption; eventually a real log (Kafka/Redpanda) — but only at this tier, not before.
4. **Per-account lock**: serialized scalpers + silent skips become systemic detection loss. Needs ordered per-account streams (consistent-hash queues) instead of lock-and-skip.
5. Scores polling: 500k × chip polling ⇒ needs the cached aggregate + WS push, not per-request event scans.

**Redesign BEFORE that scale (priority order):** event idempotency + partitioning + retention → hot-path state (make SessionState real, kill per-trade rescans) → task coalescing → dedup/domain-flag caches → queue partitioning by account hash.

---

## SECTION 9 — FAILURE ANALYSIS

| Failure | Current behavior | Gap |
|---|---|---|
| Redis down | `_get_redis_client` raises inside task → lock acquisition fails → **detection silently skipped, task returns success**; LTP checks skip; event-bus publish fails (UI stale) | No degraded-mode: should fall back to no-lock-with-idempotency or requeue. At minimum: metric + alarm on `behavior_skipped`. Nothing counts these today. |
| Worker crash mid-analyze | Celery retry (3×) re-runs whole pipeline; trade upsert idempotent; alerts deduped; **events duplicated** (same S3 defect); risk_score double-incremented (update_risk_score is not idempotent) | Idempotency key fixes events; risk_score needs event-derived recompute or an applied-marker. |
| Duplicate webhook | `processed_at` guard catches post-pipeline dupes; in-flight concurrent dupe of same order blocked by fifo/behavior locks | Acceptable. |
| Delayed webhook (hours) | detected_at=trade time (correct), staleness gate blocks push (correct) — well handled | None. |
| Out-of-order fills | FIFO layer handles pairing; engine sorts; dedup window slightly mis-anchored | Acceptable; log skew metric. |
| Postgres down | Webhook task retries ×3 w/ backoff then DLQ? — **no dead-letter handling; after 3 retries the trade's behavioral processing is lost forever** (trade itself re-synced later, but webhook-path analysis never re-attempted; bulk sync would cover it — and currently double-writes events) | DLQ or a reconciliation sweep ("trades with processed_at NULL older than X"). |
| Push/WhatsApp down | send_danger_alert retries ×3, exponential — good; push failures non-fatal | Fine. Add delivery-failure metric. |
| Replay during live | Replay is read-only (validated) — safe. **Bulk sync during live** is the dangerous one: lock not taken by full_session path → concurrent with webhook analyze on same account → dedup races + duplicate events | Take behavior_lock in full_session; add the idempotency key. |

**Missing across the board: observability.** No metrics on skip counts, queue lag, per-stage latency, event write rate, dedup hit rate. The system cannot tell you it is failing — every failure above is silent-log-line only.

---

## SECTION 10 — IMPLEMENTATION DIFFICULTY (remaining/needed work)

| Work | Effort | Risk | Bug likelihood | Test burden |
|---|---|---|---|---|
| Event idempotency + partitions + retention | 1 wk | Low | Low | Medium |
| Hot-path state machine (real SessionState, cached thresholds/dedup/domains) | 3–4 wks | **Highest** — touches every detector's input contract | **Highest** (state drift vs rescan truth) | **Very High** — replay parity suite is the safety net; extend it to assert state==rescan on every historical trade |
| Task coalescing (fold position checks in) | 1 wk | Medium | Medium | Medium |
| Lock → ordered-queue partitioning | 2 wks | High (Celery routing, rebalancing) | Medium | High |
| time_patterns → CompletedTrade migration | 3 days | Low | Low | Low |
| Observability baseline (metrics + alarms) | 1 wk | Low | Low | Low |

Hardest & most bug-prone by far: the state machine cutover — which is precisely why the replay harness must gate it.

---

## SECTION 11 — SIMPLIFICATION OPPORTUNITIES (no accuracy loss)

1. **Hoist shared per-trade computation** out of 27 detectors (parsed symbols, streaks, aggregates) — deletes ~15 duplicated loops, 5–10× CPU cut.
2. **Drop input_snapshot**; replay never reads it.
3. **Gate info-event persistence** (sample or daily-rollup) — halves write volume, zero alerting impact.
4. **Merge session-P&L representations** into one (SessionState computes, TradingSession stores).
5. **Coalesce the 4-tasks-per-fill fan-out into one** — removes 15M+ tasks/day and 2/3 of connection churn.
6. **Single per-account day-cache** (thresholds, dedup keys, domain flags) — removes 4–6 queries/trade AND simplifies dedup code (keyed lookups replace list scans).
7. Config: 100+ flat keys in one dict — namespace by subsystem when it next grows; not urgent.
8. Split behavior_engine.py by nature-family (mechanical, registry makes it safe) — maintainability only.
9. Deployment/infra: already appropriately simple (FastAPI+Celery+Redis+Postgres) — **do not add Kafka/K8s/microservices at this tier.** The simplification here is resisting additions.

---

## SECTION 12 — FINAL VERDICT

| Category | /10 | Note |
|---|---|---|
| Architecture (design) | 8 | Layering, evidence model, registry, constitution: genuinely strong |
| Architecture (as-built hot path) | 4 | The O(1) state machine was specified and skipped; rescans everywhere |
| Scalability | 3 | Fine to ~1–5k users; 50k needs the state machine; 500k needs partitions+queues too |
| Maintainability | 7 | Registry + smoke suites + replay are excellent; 2,400-line engine file and copy-pasted loops drag it |
| Performance (per-event logic) | 7 | Detector logic cheap; I/O around it is the problem |
| Operational simplicity | 6 | Few moving parts (good); zero observability (bad); silent-skip failure modes (bad) |
| Developer experience | 7 | Adding a detector is genuinely one spec + one method; suppression/dedup interactions are tribal knowledge |
| Production readiness (current scale) | 6 | Works, validated, but carries the duplicate-events bug and no metrics |
| Production readiness (stated 50k workload) | 3 | Not without the S8 items |
| Future extensibility | 8 | Registry, events, versioning, replay = the right bones |

**Direct answers:**

1. **Overengineered?** The *governance* layer (registry, versioning, replay, evidence) — no, and it's the best part. The *write path* — yes in one place: input_snapshot + unconditional info-event persistence. The bigger sin is the opposite: the hot path is **under-engineered** relative to its own spec.
2. **Definitely simplify:** input_snapshot; info-event writes; 4-task fan-out per fill; triplicated session-P&L; duplicated per-detector loops.
3. **Definitely do NOT simplify:** BehaviorEvent evidence layer; detector registry; constitution engine; replay harness; suppression-at-notification-layer principle; guardian budget; baseline confidence blend.
4. **Comfortable at 50k users?** No — not as built. With the S8 priority list (≈6–8 weeks of hot-path work), yes.
5. **Comfortable at 500k?** No, and it shouldn't try to be yet. The redesigns are known and sequenced (S8); none require throwing the design away — the spec already contains the missing state machine.
6. **Real-time <3s?** Today at current scale: yes. At 50k peak: no — queue wait alone will blow the budget. After state-machine + coalescing: yes, with headroom.
7. **Would I approve implementation today?** For the current user base and a staged rollout: **yes, conditionally** — ship after fixing (a) duplicate BehaviorEvents on bulk sync [correctness, days], (b) silent behavior_skipped loss [correctness, days], (c) minimum observability [1 wk]. For the stated 50k workload: **no** — I would block until the hot-path state machine, event idempotency/partitioning, and task coalescing land. The team should feel good about the design and honest about the distance between the spec's runtime and the shipped one: the spec already knew the answer ("update state, run O(1) checks — never load 1000 trades and run 24 detectors"); the implementation still does the latter on every trade.

*Filed without implementation, per instruction. Priority queue if/when approved: S3 defect fixes → observability → hot-path state machine (replay-gated) → partitions/retention → coalescing.*
