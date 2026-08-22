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

- **`completed_trade_features` is empty in production.** 1,515 completed trades,
  **0** feature rows, verified against the live DB. Features are only written by
  `_compute_features_for_new_rounds` inside `pnl_calculator.calculate_and_update_pnl`,
  over a bounded recompute window. The consequence is on **My Record**: every
  feature-derived card ("your record after 2+ losses in a row", "after a loss",
  "on expiry day", "quick re-entry") is guarded by `f is not None` and so renders
  empty rather than erroring. Presumably always has.
- **`pattern_prediction_service` looks up a pattern type that does not exist** —
  `pattern_counts.get("revenge_trading")` against a vocabulary whose 33 types
  include `revenge_trade` and never `revenge_trading`. Always 0, so the history
  factor in the revenge probability is dead. Left alone on purpose: it changes
  user-visible probabilities and belongs with the parked frontend-vocabulary
  work.

## 2. Open — MEDIUM

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
