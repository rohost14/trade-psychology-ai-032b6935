# Alert Lab

Synthetic trades, **real** detection logic. Drives the actual pipeline — ledger,
fill classification, coalescing, entry checks, strategy grouping, BehaviorEngine,
dedup, consolidation, receipts — with fabricated fills, so alert behaviour can be
validated without waiting for a market session.

Nothing in `app/` or `src/` is modified. Every seam is applied from outside.

---

## Terminals and commands

**One terminal. No Celery worker, no Redis, no frontend build.**

```bash
python alertlab/server.py
```

Then open **http://127.0.0.1:8900**.

Click a scenario on the left; it runs and the timeline replays. "Run every
scenario" does the suite. "Wipe lab data" clears the synthetic account.

<details>
<summary>Optional second terminal — the same runs from a CLI</summary>

```bash
python alertlab/scripts/run.py              # every scenario
python alertlab/scripts/run.py K-01 B-05    # named scenarios
python alertlab/scripts/run.py --json       # machine-readable, for CI
python alertlab/scripts/run.py --teardown   # wipe the lab account
```

Exit code is non-zero when a scenario fails, so it drops into CI unchanged.
</details>

**Why no worker or Redis.** Celery runs in eager mode — `.delay()` and
`.apply_async()` execute the real task bodies inline. Redis is an in-memory
fake implementing the seven operations the pipeline uses. Both are set up by
`runner/harness.py`.

**Requires** the same `backend/.env` the app uses (`DATABASE_URL`), because the
lab writes real rows to a synthetic account and reads them back. That is the
point: dedup, consolidation and the suppression layers all query the database, so
an in-memory fake would test nothing.

---

## What it shows

- **Assertions** — `must_fire` and `must_not_fire`, each with why it matters
- **Fills** — the session replaying at readable speed
- **Alerts raised** — severity, message, evidence, latency
- **Suppression trace** — every detection that did *not* become an alert, and
  which layer stopped it. The panel no other tool provides, and the one that
  matters most: twelve of fifteen defects found reviewing this week's work were
  something firing wrongly or vanishing silently
- **Guardian routing** — which alerts would reach an accountability partner.
  Delivery is parked; the routing decision is testable now
- **Positions** — open, closed, and recognised multi-leg structures

---

## Scenarios

`scenarios/catalogue.py` — 19 implemented against the 118 catalogued in
`SCENARIOS.md`. Roughly half the assertions are negative, matching where the
defects actually are.

Adding one is a few lines: fills, capital, and the two assertion lists.

The highest-value ones:

| ID | Why it exists |
|---|---|
| `K-01` | A clean session must produce **zero** alerts. Everything else asks "does it fire"; this asks "does it ever shut up". |
| `B-05` | Two iron condors. Eight legs, two decisions. Read as eight trades until this week and fired danger-severity overtrading. |
| `D-05` | Covering a short is an exit. Treated as an entry, every short seller got false cooldown alerts on the way *out*. |
| `B-12` | Six losses, constant size, patient gaps. Losing is not misbehaving — conflating them destroys trust in every other alert. |
| `C-11b` | Doubling after **wins** is pyramiding, not martingale. |

---

## Things the lab taught us while being built

Worth recording, because they are non-obvious properties of the real system:

**A constitution breach outranks the behaviour behind it.** When a rule the
trader wrote is broken, ordinary behavioural alerts are suppressed —
`revenge_trade` goes quiet behind `constitution_violation`. Deliberate: the rule
alert is louder and more specific. It also means isolating a behavioural pattern
in a scenario requires *not* tripping a rule at the same time, which is why
`C-01a` runs on roomy limits.

**The engine resolves "today" from the wall clock.** Not just the tasks — the
engine itself, when it builds `session_trades`. A scenario dated in the past saw
an empty session, so every detector that compares against earlier trades silently
found no history. The clock therefore advances *with* the scenario, pinned to
each fill's own timestamp.

**Negative scenarios can pass for the worst possible reason.** Early on, every
fill was failing to process (`asyncio.run` inside a running loop) and every
`must_not_fire` passed because nothing ran at all. Injection failures are now
surfaced as scenario errors rather than swallowed.

---

## What it does not cover

Stated so nobody assumes otherwise:

- Celery retry, queue behaviour, task routing
- The real 5-second coalescing countdown — the batching logic is exercised, the
  timer is not (eager mode ignores `countdown`)
- Real Redis semantics beyond the seven operations modelled
- WebSocket delivery to a browser
- Actual WhatsApp or push transmission — parked with the business number

The lab narrows what a live session has to prove. It does not replace one.

---

## Teardown matters

Lab alerts live in the same `risk_alerts` table `/api/admin/detection-quality`
reads. Every run tears down automatically, but if one crashes, run
`--teardown` — otherwise the synthetic data distorts the metrics that measure the
real engine.
