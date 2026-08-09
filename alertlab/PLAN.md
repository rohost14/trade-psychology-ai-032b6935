# Alert Lab — plan

A synthetic environment for exercising the **real** alert pipeline with fabricated
trades, so behaviour can be validated without waiting for a live market session.

Status: **plan only. Nothing built.**

---

## 1. Why

Every fix shipped this week is verified at function level with stubs. Nothing has run
end to end. The pipeline changed more in one session than in any before it — the
consolidation self-suppression fix, delivery receipts, entry-time detection, live premium
monitoring, structure counting — and four suppression layers that had never executed in
production now do.

A code review found fifteen defects in that same work. Twelve of them were **false
positives or silent suppressions**: an alert that fired when it should not, or one that
vanished without an error. Unit tests did not catch them because each component was
individually correct; the defects lived in how the components met.

That is the gap this closes. Not "does the function return the right value" — "given a
trader doing a specific thing, does the right alert arrive, with the right severity, at
the right time, and does the wrong alert stay silent."

---

## 2. Hard constraints

These come from the brief and shape everything below.

| Constraint | Consequence |
|---|---|
| **No production code changes** | All seams via test-style patching from the lab. No clock module, no `is_synthetic` column, no new hooks in `app/`. |
| **Real detection logic only** | The lab calls `BehaviorEngine` and the real task functions. Zero reimplementation — a second copy would drift, which is the root cause of most bugs found this week. |
| **No separate database** | One synthetic broker account inside the existing DB. Teardown by FK cascade. |
| **No Redis, no Celery** | Deterministic in-process runs. An in-memory fake Redis is injected where the real code asks for one. |
| **No auth, tokens, sessions** | The lab never goes through HTTP auth. Scripts call the pipeline directly. |
| **Everything new lives in `alertlab/`** | Nothing added to `app/` or `src/`. |
| **Guardian delivery is out of scope** | But guardian *routing* is in scope — see §7. |

---

## 3. Does synthetic time actually work?

Mostly yes — and precisely where it does not matters, so here is the real answer.

**The 27 engine detectors are pure trade-time.** They read `entry_time`, `exit_time` and
`session_trades` off the objects handed to them. Give a synthetic trade a timestamp of
09:17 IST on an expiry Thursday and the detector behaves exactly as it would that day.
**No patching, no market hours, no clock tricks.** This covers `revenge_trade`,
`size_escalation`, `martingale_behaviour`, `consecutive_loss_streak`,
`overtrading_burst`, `opening_5min_trap`, `expiry_day_overtrading` and the rest.

**Five checks read the wall clock**, verified by inspection:

| Function | What it reads "now" for |
|---|---|
| `__entry_rules_impl` | restricted windows, cooldown gap, MIS square-off |
| `_holding_loser_task` | market-hours guard (`:252`), hold duration |
| `_monitor_live_premium` | market-hours guard (`:790`) |
| `_monitor_all_accounts` | market-hours guard (`:71`) — dead code, not scheduled |
| `_fire_position_alert` | `detected_at`, dedup window |

For these the lab **freezes the clock from outside**, the way the existing tests
monkeypatch modules. Because runs are in-process, patching `position_monitor_tasks.datetime`
is sufficient and touches nothing in `app/`.

So: **the lab never needs to run during market hours**, and it never needs a real clock.
Scenarios declare their own wall time.

Honest note: patching is more fragile than a real seam. If a module changes how it imports
`datetime`, a lab scenario silently starts testing the wrong hour. Mitigation in §8.

---

## 4. Where synthetic data enters

**At the fill, not at the trade.** This is the single most important design decision.

```
synthetic fill ─┐
                ├─→ PositionLedger.apply_fill      (OPEN/INCREASE/DECREASE/CLOSE/FLIP)
                ├─→ fill classification            (is this an entry? add-to-loser?)
                ├─→ entry batch + coalescing       (fake Redis)
                ├─→ entry-time checks              (limits, MIS window, overexposure)
                ├─→ strategy grouping              (condor recognised as one structure)
                ├─→ CompletedTrade construction    (on CLOSE/FLIP)
                ├─→ BehaviorEngine.analyze         (27 detectors)
                ├─→ dedup + consolidation          (windows, buckets, session cap)
                └─→ alert rows + delivery receipts
```

Injecting `CompletedTrade` rows directly would skip the top half — which is exactly where
this week's defects lived (BUY-covers-short, leg counting, the drain race, the coalescing
window). The lab must exercise the layer that broke.

**Skipped deliberately:** the HTTP webhook and its checksum. That is transport, not
behaviour, and it already has `test_webhook_checksum`.

---

## 5. Isolation and teardown

One reserved synthetic `broker_account` with a fixed UUID and a recognisable
`broker_user_id` (e.g. `LAB000001`). Everything the lab creates hangs off it.

Teardown is a single delete of that account; FK cascade removes trades, positions, ledger
rows, completed trades, alerts, events and sessions. A scenario run starts by clearing,
so runs are independent and repeatable.

**One risk worth stating plainly.** Lab alerts land in the same `risk_alerts` table that
`/api/admin/detection-quality` reads, so a heavy lab session would distort the precision
and latency numbers we just built. Without an `is_synthetic` column — which the brief
rules out — the mitigation is: **always tear down after a run**, and treat any
detection-quality reading taken while lab data exists as void. The teardown script is not
optional housekeeping; it is what keeps the production metrics honest.

---

## 6. Run model

**Deterministic, in-process, no Celery, no Redis, no HTTP.**

A scenario is a list of fills with explicit timestamps plus a frozen wall clock. The
runner:

1. clears the synthetic account
2. seeds a profile — capital, limits, experience level
3. freezes the clock at the scenario's declared time
4. feeds fills in order, advancing the frozen clock as their timestamps advance
5. collects every `RiskAlert` and `BehaviorEvent` produced
6. compares against the scenario's expectations
7. tears down

Same input, same output, every time. No sleeping, no waiting for a 5-second window, no
worker. A hundred scenarios run in seconds and can sit in CI.

**What this consequently does not cover**, stated so nobody assumes otherwise:

- Celery retry, queue behaviour, task routing
- The *real* 5-second coalescing countdown (the batching logic is covered; the timer is not)
- Real Redis semantics — the fake models `rpush/lrange/rename/set NX`, not eviction or clustering
- WebSocket delivery to a browser
- Actual WhatsApp or push transmission

Those need a live session with the worker running. The lab narrows what a live session
has to prove; it does not replace it.

---

## 7. The lab UI

A page under `alertlab/` (own React entry, not added to the production router), or a
plain static page reading the runner's JSON output. Panels:

**Scenario runner** — pick a scenario or a suite, run, see pass/fail per expectation.

**Alert feed** — every alert the run produced, in order, with: pattern, severity, message,
evidence table, confidence, lifecycle (live vs post), and the **latency** between the
triggering fill's timestamp and the alert row.

**Guardian routing panel** — the part of the guardian system that *is* testable. Delivery
is parked, but the decision is not: which alerts were `guardian_eligible`, cleared the
severity floor, and would have been sent. Rendering them in their own panel validates the
routing and the third-person message body without any WhatsApp involvement. If a `caution`
alert appears here, that is a bug we can see.

**Suppression trace** — the most valuable panel, and the one no existing tool provides.
For every detection that did *not* become an alert: which layer stopped it (dedup window,
5-minute bucket, session cap, mute, strategy-group suppression, confidence floor,
staleness) and why. Twelve of fifteen defects this week were about something firing or
vanishing wrongly; this panel makes both visible.

**Expected vs actual** — a scenario declares what should fire and what must not. Both
halves are shown, because absence is the assertion that matters most.

---

## 8. Making it worth more than one afternoon

1. **Seed the suite from real defects.** Every bug fixed this week becomes a scenario:
   the condor that read as eight trades, the BUY that covered a short, the MCX position
   that silenced the NFO window, the live alert that took another instrument's P&L. That
   is a regression net built from things that actually broke.
2. **Negative assertions are first-class.** `must_not_fire` carries the same weight as
   `must_fire`. Most suites only assert presence; every false positive this week would
   have been caught by an absence assertion.
3. **Chaos toggles.** Duplicate a fill, drop one, deliver out of order, fail the ledger
   step. Three defects this week were exactly this class.
4. **Latency per scenario**, injected-time → alert-row time, against the 5s gate.
5. **CI gate**, not a tool someone remembers to open.
6. **Guard against patch rot.** A canary scenario asserts the frozen clock is actually in
   effect — if patching silently stops working, that scenario fails rather than every
   time-based scenario quietly testing the wrong hour.
7. **Later: replay a real tradebook CSV** through the same runner. Real behaviour, no
   synthetic bias, and it needs no new machinery.

---

## 9. Proposed layout

```
alertlab/
  PLAN.md              this file
  SCENARIOS.md         the catalogue — what must be tested and why
  runner/
    harness.py         clock freeze, fake redis, synthetic account lifecycle
    inject.py          build fills; drive the real pipeline
    collect.py         gather alerts, events, suppression reasons, latency
    assertions.py      must_fire / must_not_fire / severity / timing
  scenarios/
    *.yaml             declarative scenarios, grouped by the catalogue's sections
  scripts/
    run.py             run one scenario or a suite, print or emit JSON
    teardown.py        wipe the synthetic account
  ui/
    index.html         panels from §7, reading the runner's JSON
  README.md            how to run it
```

Nothing under `app/` or `src/` changes.

---

## 10. Open questions

1. **Profile seeding per scenario** — capital and limits drive most thresholds, so each
   scenario declares them. Should a scenario be able to run against *several* capital
   tiers automatically (the same behaviour at ₹25k and ₹1Cr), or is that a separate
   scenario each? Parameterising is less writing and more coverage; explicit scenarios are
   easier to read when one fails.
2. **How far to take the UI.** A JSON dump plus a plain table answers most questions. The
   suppression trace is the panel that earns real screen time.
3. **Where the pass/fail bar sits** — is a scenario that fires the right pattern at the
   wrong severity a failure, or a warning? My inclination: failure. Severity drives
   guardian routing and the critical tier.
