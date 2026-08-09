# Vocabulary audit — severity, pattern names, duplicate alerts

Findings only. Nothing changed. 2026-08-09, after Phase 1.

Three questions: why do we have so many severity words, do we have one pattern under two
names, and are live alerts being sent twice. All three turn out to share a cause, and the
third one is worse than "duplicates".

---

## 1. Severity — how many vocabularies do we actually have?

### 1.1 What the engine emits

`behavior_engine.py` writes four values. Literal assignments: `caution` ×15, `danger` ×11,
`info` ×9. `critical` is never a literal — it is produced through a variable in two places:

| Emitter | Rule | Line |
|---|---|---|
| `premium_loss_event` | premium lost ≥ 80% (caution ≥40, danger ≥60, **critical ≥80**) | `behavior_engine.py:1836` |
| `premium_loss_event` | repeat destruction the same day escalates danger → critical | `:1852` |
| `constitution_violation` | breach ≥ 120% of the user's own limit | `:2357` |

**So `danger` and `critical` are two genuinely different levels, not aliases.** Critical
means "past the point the rule was written for" — 80% of the premium gone, or 120% of your
own limit. `constitution_violation` is also `guardian_eligible`, so critical is precisely
the severity that should reach a human being.

That is what makes the Phase 1 bug (A1) more than theoretical: the WhatsApp gate read
`severity != "danger"`, so **the two worst things the engine can say were the two it could
never send** — including the guardian-eligible one.

`info` is analytics-only: recorded as evidence, never notified.

### 1.2 The competing vocabularies

Six distinct severity-ish vocabularies exist. Three are legitimate, three are drift.

| Vocabulary | Where | Verdict |
|---|---|---|
| `info/caution/danger/critical` | engine, `RiskAlert.severity`, `app/core/severity.py` | **canonical** |
| `low/medium/high` on *insights* | `daily_reports_service.py:749+`, `order_analytics_service.py:134+` | legitimate — different object (a report insight, not an alert). Bad that it reuses the word `severity`. |
| `low/medium/high` as `risk_level` | `cooldown.py:51+` | legitimate — a session risk level, correctly named something else |
| `low/medium/high` as alert severity | `demoData.ts` (every demo alert), `types/api.ts:432` | **drift** — the guest fixtures use a vocabulary the API never emits |
| `danger/caution/positive` | `types/patterns.ts:32`, `alertSeverity.ts` | **drift** — cannot express `critical` or `info`, and `positive` is never emitted by anything |
| `critical/danger/caution/positive` **inverted** | `behavior_engine.py:541` | **drift + dead** — see below |
| `high/medium/low` as signal *importance* | `behavior_engine.py:711+` | legitimate — confidence-signal weighting, a different axis |

### 1.3 Four `_SEV_RANK` tables, one of them backwards

```
behavior_engine.py:541   {"critical": 0, "danger": 1, "caution": 2, "positive": 3}   ← DESCENDING
behavior_summary.py:17   {"info": 0, "caution": 1, "medium": 1, "danger": 2, "high": 2, "critical": 3}
trade_tasks.py:841       {"info": 0, "caution": 1, "danger": 2, "critical": 3}
trade_tasks.py:1113      {"info": 0, "caution": 1, "danger": 2, "critical": 3}
```

Three agree that a higher number is worse. `behavior_engine.py:541` says the opposite, and
also contains `positive` (never emitted) while missing `info` (emitted nine times).

**It is currently dead** — defined inside `_run_detectors` and never read. That is the only
reason it is not causing a live bug. It is a loaded gun for the next person who copies it:
used with the same `>` comparison the other three use, it would rank `positive` above
`critical` and pick the least severe alert as the worst.

`behavior_summary.py` carries `medium` and `high` as aliases, which is the *correct*
defensive move given §1.2 — but it also defaults missing severities to `"medium"`
(`behavior_summary.py:34`), a value the engine never writes.

### 1.4 The frontend cannot express `critical`

```ts
// types/patterns.ts:32
export type PatternSeverity = 'danger' | 'caution' | 'positive';

// alertSeverity.ts:45
if (s === 'danger' || s === 'critical' || s === 'high') return 'danger';
```

Every `critical` alert renders **identically to `danger`** — same colour, same label, same
border. A user who breaches 120% of their own loss limit sees the same row as one who
breached 100%. The distinction the engine works to compute is discarded at the last step.

`positive` exists in the type, in all four style maps, and in `_SEV_RANK` — and nothing
emits it.

### 1.5 Demo fixtures speak a language the API doesn't

`demoData.ts` alerts use `severity: 'high' | 'medium'` (lines 298–377). The real API returns
`caution`/`danger`/`critical`. It only *looks* fine because `normalizeSeverityStr` maps
`high→danger` and everything unknown→`caution`. Per the memory rule that guest fixtures
double as smoke fixtures, this is the same class that shipped the `₹NaN` habits bug — the
fixture is not a faithful sample of the endpoint.

---

## 2. Pattern names — is one pattern living under two names?

**Yes, and it is worse than one pattern with two names: there are three complete
generations of vocabulary in the tree at once.**

### 2.1 The canonical set

`REGISTRY` holds **27** detectors. The engine emits **28** distinct `event_type` values.
The extra one is `daily_overtrading`.

`detector_registry.py:145` has an `ALIASES` map — five pattern types that are emitted but
never registered, documented as "emitted by a detector under a different name than its spec":

```
daily_overtrading · death_spiral · overexposure · portfolio_concentration · holding_loser
```

So the real universe is **32 pattern types**: 27 registered + 5 aliases. This part is
deliberate and documented. But being outside `REGISTRY` has consequences that are not:

- **`BY_NAME.get("daily_overtrading")` is `None`.** In `send_danger_alert`
  (`trade_tasks.py:1354`) a missing spec falls back to `pattern_type == "death_spiral"`,
  so `daily_overtrading` can never be guardian-eligible. That may be the right outcome,
  but it is reached by accident, not by declaration.
- **Feature flags are silently coupled.** The engine iterates `REGISTRY`, so
  `daily_overtrading` events are produced by the `overtrading_burst` detector and inherit
  its flag. Flipping `overtrading_burst` to `off` also kills `daily_overtrading`, and the
  admin screen gives no hint of that.
- Anything keyed on pattern name has to know about `ALIASES`, and nothing does.

### 2.2 Three generations, all live

| Generation | Examples | Status |
|---|---|---|
| **v1** (engine v1) | `overtrading`, `revenge_sizing`, `consecutive_loss`, `tilt_loss_spiral`, `martingale`, `fomo`, `iv_crush_behavior`, `options_direction_confusion` | **the engine has not emitted these since v2** |
| **v2** (current) | `overtrading_burst`, `daily_overtrading`, `size_escalation`, `consecutive_loss_streak`, `revenge_trade`, `fomo_entry`, `martingale_behaviour` | canonical |
| **FE product taxonomy** | `position_sizing`, `capital_drawdown`, `same_instrument_chasing`, `loss_aversion`, `all_loss_session`, `premium_destruction` | a third vocabulary that exists only in the frontend |

So "overtrading" vs "overtrading burst" is not two names for one pattern — it is **three**:
`overtrading` (v1, dead), `overtrading_burst` + `daily_overtrading` (v2, live, two distinct
patterns), and `overtrading` again as a *frontend* display type that all of them collapse into.

### 2.3 v1 names still being compared against

Every one of these is a string comparison that can never match a live alert:

| File | What it does with a dead name |
|---|---|
| `AlertDetailSheet.tsx:29,46` (+ `buildFacts`) | key `overtrading` → no facts, no explanation, no context on our most common alert (F1) |
| `pattern_prediction_service.py` ×8 | `overtrading`, `fomo`, `tilt_loss_spiral` — predictions keyed on names that never arrive |
| `danger_zone_service.py:248–250` | `revenge_sizing`, `tilt_loss_spiral`, `fomo` |
| `daily_reports_service.py:771,773,847,850` | `options_direction_confusion`, `iv_crush_behavior`, `overtrading`, `fomo` |
| `report_tasks.py:277,297` | `overtrading` |
| `notification_rate_limiter.py:37` | `OVERTRADING_DETECTED = ("overtrading", …)` — though only `COOLDOWN_STARTED` is ever used |
| `push_notification_service.py` | fixed in Phase 1 |
| `alert_service.py` | fixed in Phase 1 |

Each one degrades silently: a lookup miss renders nothing, a filter matches nothing, a
prediction never fires. None of them raise. **This is the same failure mode as the severity
drift, and it is why nothing has ever gone red.**

### 2.4 The frontend mapping is lossy and incomplete

`AlertContext.tsx:117` maps backend → frontend types. Two problems:

**Collapse.** `size_escalation`, `martingale_behaviour` and `excess_exposure` all become
`position_sizing`. `panic_exit` becomes `early_exit`. `rapid_reentry` and `rapid_flip`
become `same_instrument_chasing`. Three engine patterns with different detectors, different
thresholds and different evidence arrive at the UI as one type.

**Gaps.** Unmapped names fall through raw (`:215`, `|| a.pattern_type`). Missing from the
map: `daily_overtrading`, `constitution_violation`, `cooldown_violation`,
`direction_instability`, `same_symbol_obsession`, `time_of_day_bias`, `win_rate_collapse`,
`strategy_breakdown`, `premium_loss_event`, `death_spiral`, `overexposure`,
`portfolio_concentration`, `holding_loser` — 13 of 32. The TypeScript cast to `PatternType`
hides this completely.

`types/patterns.ts:10` declares 20 `PatternType` values; **six** correspond to something
the engine emits today.

---

## 3. Duplicate live alerts — what I found is the opposite problem

You asked whether the same alert is sent twice. I could not find a mechanism that sends one
alert twice on the live path. I found something more serious: **on the live path, the first
alert of any pattern suppresses itself, and nothing is sent at all.**

### 3.1 The self-suppression — **FIXED 2026-08-09** (`a1267ed`)

The bucket query now excludes the alerts it was handed, by id. Nine tests added
(`backend/tests/test_alert_consolidation.py`); seven fail against the old code. The
function had no test before. §3.2–§3.4 below are **not** fixed.

`trade_tasks.py` order of operations in `run_risk_detection_async`:

```
:879   db.add(alert)
:899   await db.commit()                          ← alert is now in risk_alerts
:919   new_alerts = await _apply_alert_consolidation(broker_account_id, new_alerts, db)
:925   danger_alerts = [...]  → push / WhatsApp
:999   if new_alerts: publish_event("alert_update")  ← WS toast
```

And the consolidation itself (`:1280`):

```python
recent_result = await db.execute(
    select(RiskAlert).where(and_(
        RiskAlert.broker_account_id == broker_account_id,
        RiskAlert.detected_at >= five_min_ago,
    ))
)
recent_patterns = {a.pattern_type for a in recent_result.scalars().all()}

for alert in alerts:
    if alert.pattern_type in recent_patterns:
        ...suppress...
```

The query has no exclusion for the alerts being consolidated, and those alerts were
committed twenty lines earlier. `detected_at` is the **trade's** exit time
(`behavior_engine.py:271`), which on the live webhook path is seconds ago — inside the
5-minute bucket. So each new alert finds *itself* in `recent_patterns` and suppresses itself.

Verified against the real function with a stubbed DB:

```
committed-before-consolidation  -> notifiable=0     ← live path
not-yet-in-db (control)         -> notifiable=1     ← what was intended
```

**Consequences**, all three at once, because `new_alerts` is rebound at `:919`:
- no push (`:925` filters an empty list),
- no WhatsApp / guardian (same list),
- **no `alert_update` WebSocket event** (`:999` is `if new_alerts:`), so no live toast either.

The alert is still saved and still appears in history and on next page load. This is a
strong candidate explanation for **55 alerts with 0 outcomes**: if the live prompt never
arrives, there is nothing to respond to in the moment.

### 3.2 Why you still see alerts — the two paths behave differently

`run_behavior_engine_full_session` (bulk sync, `zerodha.py:881`) **does not call
consolidation at all**. It dispatches every non-stale alert directly (`:1210`).

| Path | Trigger | Consolidation | Guardian/merge split | Result |
|---|---|---|---|---|
| `run_risk_detection_async` | live webhook | yes → self-suppresses | yes | nothing delivered |
| `run_behavior_engine_full_session` | manual sync, EOD, retry | **no** | no | everything delivered |

Two paths, two different notification policies, for the same alerts. That asymmetry is also
the most plausible source of a *perceived* duplicate: a pattern that stayed quiet live can
be delivered later by a sync.

### 3.3 No delivery idempotency — retries re-deliver

`RiskAlert` has `delivered_push_at` and `delivered_whatsapp_at` (migration 038, delivery
state machine). **Nothing writes either column.** They are only read:

- `admin/users.py:601–633` — "last push at" is therefore always null;
- `behavior_scores_service.py:285` — `check_guardian_budget`.

Two consequences:

1. **The guardian monthly budget is inert.** It counts alerts with
   `delivered_whatsapp_at IS NOT NULL` this month. That count is always 0, so
   `sent >= budget` is never true and the cap never engages. The protection described as
   "a guardian pinged weekly stops reading" does not exist. (Until Phase 1 it was worse:
   consent was not checked either.)
2. **`send_danger_alert` is `max_retries=3` with no record of what it already sent.** Push
   is best-effort inside its own `try`, but anything after it that raises — the DB reads for
   the user, the budget query — retries the whole task and re-sends. Narrow window, real.

### 3.4 One genuine double-notification by design

`run_risk_detection_async:961–989` splits alerts: guardian-eligible ones each get their own
`send_danger_alert` (push + WhatsApp), the rest get **one merged push** ("N risk patterns on
your last trade"). A trade that raises both kinds produces two notifications within
milliseconds — one merged, one individual — describing the same moment. That is the closest
thing to "the same alert twice" that I can demonstrate.

### 3.5 What I could not verify from code

Whether §3.1 matches what you actually observed. It predicts live silence on the first
alert of each pattern, which is testable in one session: fire a trade that trips a pattern,
then check whether `alerts_fired` on the session increments and whether
`notifications_dispatched` moves. If you *did* get a live toast for a first-of-pattern
alert, my reading is wrong somewhere and I want to know before anything is changed.

---

## 4. Direct answers

**Why so many severity words?** Six vocabularies. Three legitimate (alert severity, report
insight severity, signal importance — three different objects that unfortunately share the
word "severity"). Three are drift: the frontend's `danger/caution/positive`, the demo
fixtures' `high/medium`, and an inverted dead rank table in the engine.

**Are `danger` and `critical` different levels?** Yes. Critical = past the point the rule
was written for (80% premium loss, 120% of your own limit) and is the guardian-eligible one.
The frontend renders it identically to danger, so today the difference is invisible to users.

**Is `high` used where `danger` is meant?** Yes — in the demo fixtures and in
`types/api.ts:432`. Normalisers paper over it. Nothing is silently *lost* today, but the
fixtures no longer match the API, which is the condition that has already produced two
shipped bugs.

**One pattern with two names?** Three generations coexist. `overtrading` (v1, dead but still
compared against in seven files), `overtrading_burst` + `daily_overtrading` (v2, two real
and distinct patterns), and `overtrading` again as a frontend display type. 13 of 32 pattern
types are missing from the frontend map, and three distinct patterns collapse into one.

**Same alert sent twice?** Not that I can find. The live path currently sends *nothing* on
the first alert of a pattern; the sync path sends everything; delivery has no idempotency so
a task retry re-sends; and guardian-eligible + merged pushes can arrive together. Any of the
last three could read as a duplicate.

---

## 5. What this does to the plan

Phase 2 was "move pattern copy onto `DetectorSpec` and add a contract test". This audit says
the contract test is the whole point, and it needs to be wider than copy:

1. every emitted `event_type` is either in `REGISTRY` or in `ALIASES` — nothing else;
2. every pattern-name literal in the tree resolves to one of those (this alone would have
   caught seven files);
3. every severity literal is in `SEVERITY_ORDER` — kill the inverted table, give the
   frontend `critical`, fix the fixtures;
4. one `_SEV_RANK`, imported, not four.

Two items should be pulled **out** of Phase 2 and decided sooner, because they are not
vocabulary problems:

- **§3.1 self-suppression.** If confirmed, this is the highest-severity defect found so
  far — higher than anything in Phase 1, because it means the real-time product does not
  currently notify in real time.
- **§3.3 the un-written delivery columns**, which leave the guardian cap inert.
