# Engine backlog — the one live list

Last verified 22 Aug 2026.

**Entry rule:** nothing appears here until it has been verified against the
current code or database. A doc, an audit report or an earlier conversation is a
*claim*; only code or the DB is evidence. Every item below records how it was
checked. Items that could not be verified are in §5, marked as such, and must not
be acted on until they are.

This replaces the scattered findings in the six documents archived on 21 Aug and
the stale ones archived on 22 Aug. `docs/NEXT_SESSION.md` remains the narrative
orientation; this is the checklist.

---

## 1. Open — HIGH

### ~~H1. Two baseline services race on one JSONB key~~ — CLOSED `05962ae`
`baseline_service.py:67` writes `{computed_at, days_window, sessions_analyzed, trades_analyzed, metrics{}}`.
`behavioral_baseline_service.py:289` writes a flat `{daily_trade_limit, burst_trades_per_15min, revenge_window_min, consecutive_loss_caution, consecutive_loss_danger, session_count, computed_at}`.
Both land at `user_profile.detected_patterns["baseline"]`.

Verified: both writers read directly; `threshold_resolution.py:188-192` documents
the race in its own comment.

Consequences, each confirmed by key-diffing the shapes against the reader:
- `threshold_resolution.py:314` reads `sessions_analyzed`; the flat shape only has
  `session_count`, so **`baseline_sessions` silently reports 0** whenever a sync
  wrote last — and the Rules page would render that as the trader's own number.
- `baseline_win_rate` / `baseline_profit_factor` exist only under `metrics`, so
  they are always `None` on the flat path.
- Nested path blends by confidence; flat path assigns directly at confidence 1.0.
  **The same trader gets different thresholds depending on which service ran last.**

Blocks the largest group of constant work (percentile-of-own-history). Do behind
the replay harness — `threshold_resolution` was deliberately written to be
value-identical, so changing it changes thresholds.

### H2. Migration applied-state is tracked only in prose, and the prose disagrees
77 files, `003`→`079`, gaps at 001/002/015/026. **No migration runner, no
`schema_migrations` table, no Alembic** anywhere in the repo.

Verified by search across `backend/scripts/`, `app/core/database.py`, and for any
application reference to `migrations/`.

- 078 — **applied 22 Aug, user confirmed.**
- 077 — disputed: project memory says not applied, `docs/PENDING.md:67` says
  applied 2026-08-04. Unresolved.
- 074 — mentioned in neither. Degrades safely (`admin_settings_service.py:103`
  falls back to code defaults).

The defect is the tracking mechanism: nothing in the repo can answer "is 077
applied?".

---

- **The database this project develops against is full of test residue.**
  4,607 users, 2,736 broker accounts and 1,199 accounts holding one or two
  completed trades each, in a product with no real users. `tests/conftest.py`
  points at `settings.DATABASE_URL` — the live Supabase instance — and rolls back
  per test, so only the paths that commit leak. They have been leaking for a
  while. This corrects an earlier claim of mine: I cited "0 feature rows against
  1,515 completed trades" as evidence for the feature-pipeline bug. The bug was
  real and is fixed, but that row count was not a trader's book and should not
  have been quoted as one.
- **`pattern_prediction_service` looks up a pattern type that does not exist** —
  `pattern_counts.get("revenge_trading")` against a vocabulary that includes
  `revenge_trade` and never `revenge_trading`. Always 0, so the history factor in
  the revenge probability is dead. Left alone on purpose: it changes user-visible
  probabilities and belongs with the parked frontend-vocabulary work.
  **Superseded 27 Aug by §2 M0** — this is one of FIVE dead names in that file,
  not one, and the vocabulary count is now 32 rather than 33. Read M0.

- **WebSocket delivery is head-of-line blocked, today, at one user's scale.**
  `websocket.py:59` awaits each socket in turn with a 2-second timeout, and it is
  called from inside the single event-subscriber loop. One trader on a bad mobile
  connection stalls delivery of *every other user's* alerts for up to two seconds
  per socket. This is a real-time correctness defect in a product whose claim is
  that the alert lands while the decision is live — and it cannot be observed
  with one user. `docs/SCALABILITY_50K_ANALYSIS.md` ceiling 3.
- **`margin_snapshots` has no scheduled producer.** Rows are written only by
  `margin_service.get_margin_status`, reachable only from
  `GET /api/zerodha/margins`. So the account-risk denominator (live since
  `c8519f3`) reaches its GOOD rung only if the trader happened to open a page
  that fetched margins; otherwise it falls to declared capital or abstains. The
  obvious fix — snapshot everyone before the open — is what Kite's 3 req/s
  shared key forbids at scale: 50,000 fetches is 4.6 hours of exclusive API
  budget. Three options are written up in the scalability analysis; **the choice
  is a product decision** about what the engine may claim, and it touches the
  frozen capital-relative constants.

## 2. Open — MEDIUM

### ~~M-1. The Pattern 6 confirmation replay has not run~~ — CLOSED 27 Aug

Superseded twice over. The **Pattern 8 confirmation replay ran clean to 203/203**
and reported **330 alerts / 203 sessions**, with `profit_giveaway` at **0** — the
result M-1 was owed. A second full replay ran for **Pattern 9**.

The original failure was environmental, not an engine change: the attempt reached
session 5 of 203 in 72 minutes because the **Memurai (Redis) service was
stopped**, so every `publish_event` and `admin_settings` read waited on a refused
`localhost:6379`.

**Operating rules for the replay, all learned the hard way:**

- `Start-Service Memurai` (admin) before starting. Verify with a `ping`.
- **Do not pipe through `tail`** — it buffers until exit, which is why a stalled
  run took 72 minutes to notice. Redirect to a file instead.
- **Run `python -u`.** Redirecting without `-u` block-buffers stdout, so the log
  sits at 0 bytes and a healthy run is indistinguishable from a hung one.
- **Do not run pytest against the same database concurrently.**
- **Never start a second replay while one is running.** They serialise on the
  same rows, deadlock, and the symptom looks exactly like a code regression.
  `tradedesk/.replay.lock` exists to prevent this — **do not delete it to clear
  the way.** On 27 Aug a `nohup ... &` child outlived the task that reported
  "completed", the lock was deleted on the assumption the process was dead, and
  two replays ran against one database. Check for a live process
  (`Get-CimInstance Win32_Process | Where CommandLine -like '*replay_tradebook*'`)
  before touching the lock; if a run was killed, `--wipe` the partial synthetic
  rows before restarting.
- Budget **40 min to ~2 h** depending on database latency. The docstring's 15 min
  is wrong.

### M0. `pattern_prediction_service` speaks a vocabulary the engine retired

Found 2026-08-27 while researching giveback-as-context for Pattern 6. **Recorded,
deliberately NOT fixed there** — it is a live defect on two API surfaces and
deserves its own change, not a silent ride-along on a retirement.

**All five of its prediction keys name patterns the engine cannot emit:**

| key it writes | what the engine actually has |
|---|---|
| `revenge_trading` | `revenge_trade` |
| `tilt_loss_spiral` | **retired** — already in `RETIRED_PATTERN_NAMES` |
| `overtrading` | `overtrading_burst` / `daily_overtrading` |
| `fomo` | `fomo_entry` |
| `recovery_chase` | never existed |

They are dict keys (`predictions["tilt_loss_spiral"] = ...`), not
`pattern_type == "..."` comparisons, so
`test_pattern_contract.test_no_shipping_module_compares_against_a_retired_pattern_name`
does not catch them. **This is precisely the drift class that test was written
for, arriving through a hole in it.**

The service is live: `api/analytics.py:1095` and `api/reports.py:159, 228`.

Second, smaller problem in the same file: `pattern_prediction_service.py:241`
adds 15 points to a tilt probability when `drawdown_from_peak > 2000` — an
**unsourced absolute rupee literal on a per-trader quantity**, of exactly the
kind the capital-ratio rung exists to replace. It is also the one surviving
consumer of the giveback as *context*, which is the shape Pattern 6's research
concluded was defensible — so it should be reviewed alongside that, not patched.

**Do not fix in isolation.** The right unit of work is: correct the vocabulary,
widen the contract test to catch dict keys as well as comparisons, and decide
whether the tilt heuristic should exist at all.

### M1. The frontend duplicates a catalogue the backend already serves
`GET /api/risk/patterns` serves pattern copy from the registry, and its docstring
states it exists so *"the copy cannot drift from the pattern name again — which
is exactly what happened when it lived in three frontend Record maps"*.
`AlertContext.tsx`'s `BACKEND_TO_FRONTEND_TYPE` and `formatPatternName` are those
maps. `usePatternCatalogue.ts` already consumes the endpoint.

Reconciled 22 Aug (`a67fc4f`) so they cannot disagree today. **Deleting them in
favour of the catalogue is the actual fix** and is still open.

### M2. `PatternType` cast is false for 14 pattern types
`AlertContext.tsx:216` casts `as PatternType`, a 20-member union. 14 real pattern
types are not members. Display degrades gracefully via the title-case fallback, so
this is type-safety debt rather than a live user-facing bug — but any
`Record<PatternType, …>` lookup returns `undefined` for them.

Verified by live import of `all_pattern_types()` diffed against the union.

### ~~M3. Guest-mode fixtures emit a vocabulary the API cannot produce~~ — CLOSED `e56268b`
`src/lib/demoData.ts` — 17 occurrences of retired `severity: 'high' | 'medium'`,
and `pattern_type` values `revenge_trading`, `loss_aversion`, `overtrading` that
are not in the registry.

Already masked by compensating render code (`PatternCalendar.tsx:32` tests
`severity === 'high'`). That compensation is how the two previous fixture bugs
hid — see the `DEMO_HABITS`/`session-log` cases in project memory.

### M4. Orphaned frontend goals subsystem, live backend
`useGoals.ts` has zero importers; `goalsApi.ts`, `goalsManager.ts` and four
`components/goals/*` files are reachable only through it. No `Goals.tsx`, no
route. Backend keeps 6 endpoints, the router registration and the
`commitment_logs` table. `GET /api/goals/commitment-log` has no caller at all.

`StreakTrackerCard.tsx` in the same folder **is** live — do not sweep the folder.

### M5. Dead API surfaces
`/api/danger-zone/*` — 7 of 7 unreferenced by live frontend code (the service is
still used via `zerodha.py:895`; only the HTTP surface is dead).
`/api/behavioral/baseline` has no caller but **mutates** the baseline into the
flat shape — a dead endpoint that can flip a live trader's thresholds (see H1).
Also unreferenced: `/api/personalization/{time-analysis,symbol-analysis,intervention-timing}`,
`/api/analytics/{risk-score,dashboard-stats,recalculate-pnl,ai-insights}`.

### M6. ~20 dead functions in `backend/app/services/` and `api/`
AST scan cross-referenced against every non-archived `.py`. Includes both email
formatters (~250 lines of templating with no path to a user — `config.py:76`
confirms SMTP is admin-OTP only), `websocket.py:{289,294}`, four in
`instrument_service.py`, and `behavioral_baseline_service.get_current_baseline`.

### M7. Stale L3 remnants in the persistence layer
`trading_session.py:60,61,64` — `risk_score`, `peak_risk_score` permanently 0 and
`session_state` permanently `"normal"`, with a `CheckConstraint` still policing
four values only one of which can occur. `behavioral_event.py:54`
`risk_score_at_event` written by nothing. Docstrings at
`trading_session.py:18-21` and `state/session_state.py:15` still describe the
deleted 40/70/90 ladder.

Verified: zero assignments to those attributes anywhere outside tests/scripts.

### ~~M8. Design-lab routes ship unguarded~~ — CLOSED `3995ec9`
`App.tsx:127-131` routes `/landing-lab`, `/soft-lab`, `/soft-web-lab`,
`/design-lab`, `/dashboard-lab` with no `import.meta.env.DEV` guard. `lazy()`, so
no bundle cost, but publicly reachable in production.

---

## 3. Open — LOW

- `threshold_resolution.py:242-244` — comment says the key list "does NOT include
  revenge_window_caution_min"; the loop below **does** list it. The stated outcome
  is right by accident (the flat shape emits `revenge_window_min`, so the lookup
  misses). Will mislead whoever fixes H1.
- `config.py:136` — `# Gupshup WhatsApp (replaces Twilio)` above six `GUPSHUP_*`
  settings. Twilio is the active provider; the migration never happened.
- `zerodha.py:887-891` — self-labelled dead block referencing `docs/DEAD_CODE.md`,
  which is now in `docs/archive/`. Ships a hardcoded `0` in the sync response.
- `src/lib/constants.ts` — `SEVERITY_ORDER` using the retired `high`/`medium`
  vocabulary, plus `RISK_COLORS`, `RISK_STATES`, `POLLING_INTERVAL`,
  `BROKER_ACCOUNT_ID` (a hardcoded demo UUID). Zero importers on all of them.
- 27 unused shadcn primitives in `src/components/ui/`.

---

## 4. Closed since 21 Aug

| | |
|---|---|
| Daily push read a key that never existed — every trader got "Discipline: 0/100" | `d412713` |
| `critical` folded into `danger` on the live alert path only | `49f70c3` |
| 14 pattern types unmapped, 10 phantom keys, 16 missing labels | `a67fc4f` |
| `fomo_entry` pre-close reused the market-open threshold | `a67fc4f` |
| `trading_sessions.trade_count` had NO writer — the session log showed "0 trades" for every day, and the end-of-day intent review always reported the trader had kept to their trade limit | `3dc9fc0` |
| Nine places computed a session fact for themselves; `consecutive_losses` alone had five definitions. `app/core/session_facts.py` is now the only one | `d8cde10`, `e70b457` |
| The live path never wrote a `completed_trade_features` row — only the bulk FIFO recompute did, so every My Record feature statistic rendered empty | `d0f6a5d` |
| A guard test now fails the build when anything outside `session_facts` computes a session fact; it immediately found a tenth computer (`early_warning_service`) | `d0f6a5d` |
| An alert stored no record of the thresholds it was judged against — unanswerable once baselines started moving | `326b421` |
| Hot path measured: detectors 3.2ms, `_load_context` 51.6ms, end-to-end 73ms. Guarded by query count, not wall clock | `c8519f3` |
| Account-risk denominator resolved once per session and frozen (G1 + migration 080 were unconsumed) | `c8519f3` |
| Danger zone counted the loss streak ACROSS DAYS — five losses on Friday plus one on Monday started a cooldown and a WhatsApp for a run that had ended. Now session-scoped; **fires less than it did** | `d8cde10` |
| Empty baseline claimed as personal knowledge | `38f0345` |
| Six dead constants | `9536230` |
| Replay harness dropping 8.4% of fills | `6812b3f` |
| **H1** — two baseline writers, one key, incompatible shapes | `05962ae` |
| Two personalised values silently dropped on a key-name mismatch | `05962ae` |
| `baseline_sessions` reporting 0 whenever a sync wrote last | `05962ae` |
| Three invented multipliers (median x1.5, /4, x0.5) | `05962ae` |
| An invented daily limit described to the trader as "yours" | `3f1eb6e` |
| Demo fixtures using 3 non-existent pattern types and retired severities | `e56268b` |
| **Pattern-vocabulary contract test** — 7 assertions, closes the drift class | `e56268b` |
| Comment misdescribing the baseline key mismatch (would misdirect the H1 fix) | `3995ec9` |
| `trading_session.py` documenting the deleted 40/70/90 ladder | `3995ec9` |
| Five design-lab routes publicly reachable in production | `3995ec9` |

---

## 5. Claimed but NOT verified — do not act on these yet

- **The v2 baseline is not replay-verified.** `05962ae` changes thresholds for
  any trader with a baseline. Unit-tested, not run against the tradebook.
- **Whether a capital-derived limit should reach an accountability partner.**
  `session_meltdown` is `guardian_eligible`, so today it can. Telling a third
  party someone breached a limit they never set is a further step than telling
  the trader. Undecided.

- **How often `fomo_entry`'s pre-close path fires.** The bug is verified in code;
  the frequency is not. The existing replay report is a summary only and predates
  the harness repair. Needs a replay.
- **Whether the three never-firing detectors (`time_of_day_bias`,
  `win_rate_collapse`, `strategy_breakdown`) are silent because the trader is
  clean or because they are blind.** Raised in `DETECTOR_ASSUMPTIONS.md` against
  61 sessions; the 203-session book has been run but this was never recomputed.
- **`typical_drawdown` and `median_position_risk_pct` computed and unread.**
  Claimed by an audit, consistent with the code I have read, but I have not
  personally grepped every reader.
- **`cooldown_violation` implemented twice** (`behavior_engine.py:2646` and
  `position_monitor_tasks.py:1175`). Both sites exist; whether they can disagree
  in practice is unverified.

---

## 6. Parked by decision, not forgotten

- **Capital-relative rupee floors** (`91975d4`, live). `revenge_min_loss_inr`,
  `profit_giveaway_min_peak` and `_min_erosion` derive from capital. Calibrated
  so ₹50,000 resolves to exactly the old 500/1500/500, so it is a no-op at the
  only account currently using it — but measured against the tradebook it
  excludes 91% of losses at ₹2,00,000 capital and 100% at ₹20,00,000, which
  would silence `revenge_trade` entirely. **Must not reach a second trader
  unchanged.** The user is deciding between reverting, the hybrid
  `min(capital %, trade %)`, and percentile-of-own-losses.
- **Percentile-of-own-losses for those same three floors** — the alternative to
  the above, so it is inside the same decision.
- **Frontend vocabulary final form** — deleting `BACKEND_TO_FRONTEND_TYPE` and
  `formatPatternName` in favour of `GET /api/risk/patterns`. Deferred
  deliberately: the maps are correct as of `a67fc4f`, the contract test fails
  the build if they drift, and `mapBackendAlert` is synchronous while
  `usePatternCatalogue` is an async hook — so it is a UI refactor with real
  regression risk and no bug attached. Fold into the Rules page work.
- **Whether a capital-derived limit may reach an accountability partner.**

---

## 7. Standing caveat on every threshold decision

Every calibration decision made so far rests on **one trader's tradebook**. It is
far better than the judgement it replaced and it is still one trader. A second
book from someone who trades differently would be worth more than another year
from the same person. Rescued from `THRESHOLD_REWORK_PLAN.md`, which is kept —
not archived — because its §3 specifies how to correct the capital-relative
conversion, and being contradicted by shipped code does not make a specification
stale when the shipped code is what is under review.
