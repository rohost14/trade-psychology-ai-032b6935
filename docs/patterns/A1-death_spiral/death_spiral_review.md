# A1. `death_spiral` — RETIRED 2026-09-02

The last unreviewed pattern in the queue, and the only L2 meta-detector. Two
measurement passes over the same 203-session book, the second with declared
rules because the first could not reach two of its three tiers.

---

## What it claimed

A **state**, not a count: *"several independent behavioural domains are
deteriorating together in one session."*

`behavior_scores_service.evaluate_death_spiral`, run once per CompletedTrade by
`trade_tasks._run_death_spiral` over every BehaviorEvent since IST midnight.
Events at **severity ≥ danger** were grouped by their spec's `nature` domain:

| tier | condition |
|---|---|
| `caution` | ≥ 2 domains |
| `danger` | ≥ 2 domains **and** `risk` present |
| `critical` | ≥ 3 domains **and** discipline **and** risk **and** continued escalation **and** compressed ≤ 180 min |

Constants: `spiral_warning_domains` 2 · `spiral_critical_domains` 3 ·
`spiral_window_min` 180 · `spiral_domain_min_severity` `"danger"`. Confidence
hardcoded 90.0. Guardian-eligible through a hardcoded name check, because as an
alias it had no `DetectorSpec`.

---

## Pass 1 — no declared rules (203 sessions)

**10 firings (4.9%), all `danger`, all `emotional+risk`.**

- **Set-identical to a two-detector conjunction.** "A danger *emotional* alert
  and a danger *risk* alert happened today" selects **exactly the same 10
  sessions**.
- **A strict subset of a simpler rule.** Against "≥2 danger alerts from 2
  detectors": both 10, current-only **0**, simpler-only **4**. The domain
  requirement added nothing and *removed* four sessions — including
  **2025-11-06, −₹11,015, the 4th-worst day in the book**, rejected only
  because both its detectors carried `nature="risk"`.
- **Not separable from the near miss it excluded.** Sessions with 2+ danger
  events in one domain (n=11) had a *worse* median P&L: **−₹3,918 vs −₹2,764**.
  Permutation test on the median gap: **p = 0.222**.
- **Order-independent, 10 of 10.** The danger tier contains no timestamp.
- **Always second.** 10 of 10 firings came after a danger alert already
  delivered. Both constituents are notifiable, so the composite cannot exist
  until the trader has been told.
- **Incremental on 4 of 10.** 4 fired with zero trades remaining.
- **`performance` unreachable.** Both its detectors hardcode `severity="info"`
  against a ≥ danger gate.

## Pass 2 — one declared rule (`daily_loss_limit = 5000`, capital ₹200,000)

Run to test the one thing pass 1 could not: `caution` and `critical` both need
the `discipline` domain, which needs a declared rule.

**79 sessions of 203 — 38.9%; 87 alerts.** Ladders: `danger` only 66 ·
`danger→critical` 7 · `caution` only 5 · `caution→danger` 1.

| finding | number |
|---|---|
| firings containing `constitution_violation` | **79 of 79 (100%)** |
| both domains carried by `constitution_violation` + `session_meltdown` — which read the **same** declared `daily_loss_limit` | **48 of 79 (61%)** |
| `session_meltdown` the *only* risk contributor | 15 of 79 (19%) |
| danger firings preceded by a danger alert already delivered | **50 of 72 (69%)** |
| incremental danger firings | 11 of 72 (**15%**) |
| incremental caution firings | **0 of 5** |
| danger firings with zero trades remaining | 17 of 72 |
| sessions existing only because of `session_meltdown` | 11 |

**The sequence claim, corrected.** `caution` was order-independent 5 of 5 and
`danger` 22 of 25 — together **91% of firings carry no timestamp at all**.

`critical` is different, and my first reading of it was **wrong**. I recomputed
each day's verdict over its COMPLETE event set and got 2 critical sessions with
a window that never bound. The live task evaluates **incrementally**, once per
completed trade, deduped by severity escalation — so it sees short spans and
fires where an end-of-day recomputation sees a span past 180 minutes and falls
back to `danger`.

From the actual alert rows: **79 sessions fired, 87 alerts**, ladders
`danger` only **66**, `danger→critical` **7**, `caution` only **5**,
`caution→danger` **1**. So `critical` fired on **7 sessions** and the
compression window **did** discriminate.

That is a real distinction and it is retracted from the case against the
detector. It does not rescue it: the tier reached **8.9%** of firings, and it
made no difference to the other 91%, which remain a restatement of alerts
already delivered.

---

## The absorption was dead code

`BehaviorEngine._consolidate` looked for `death_spiral` among the event types
**the engine had just produced**. The engine never produced it — it was written
afterwards by `trade_tasks`, from BehaviorEvents. So the branch never ran.

- **0** `absorbed:` markers in the database, across 145 BehaviorEvents.
- On a real `critical` session (**2026-07-29**), **14 RiskAlerts** were written
  across **6 pattern types**, none suppressed.

The master pattern document asserted the opposite — *"absorbs every other alert
when it fires"* — and carried it as the detector's headline open issue.

## Firing counts: three published numbers, one measured

| source | count |
|---|---|
| master table (22 Aug audit) | 29 alerts / 29 sessions |
| replay artifact | 16 |
| **measured, current registry, no rules** | **10 / 203** |
| **measured, one declared rule** | **79 / 203** |

The 29 predates eleven retirements. The 16 is the artifact's own pre-retirement
figure. Reconciled to the measured pair.

---

## Verdict: RETIRE

1. **Not distinct** — 100% of rules-on firings contain `constitution_violation`,
   already `notification_level=4` and guardian-eligible alone.
2. **Not additive** — 15% incremental at danger, 0% at caution.
3. **Not actionable** — no earlier than its own inputs; median 2 trades left,
   the same as every simpler gate tested.
4. **Not a spiral** — 38.9% of sessions.

**Nothing replaced it.** Every constituent alert still fires, unchanged.

## What was kept

- **Historical rows.** `death_spiral` RiskAlerts and BehaviorEvents are not
  deleted, and still render by name via `formatPatternName`. They are marked
  **Retired** in the Alerts UI so a stored row cannot read as a live rule.
- **`check_guardian_budget`**, which shared the module and nothing else.
- **The `nature` taxonomy**, still used to classify detectors.

## Stated limitation

The 38.9% rate is a function of the rule declared. A different
`daily_loss_limit`, or a trader who declares a different rule, changes the
volume — and the 61% double-count is specific to `daily_loss_limit`, because
that is what `session_meltdown` reads. The **structural** findings do not depend
on it: one domain had one detector, a whole domain was unreachable, 91% of
firings carried no timestamp at all, and the composite was always preceded by
its own inputs.

A ₹15,000 sensitivity replay was offered and **declined as unnecessary**.

---

**Enforced by** `backend/tests/test_death_spiral_retired.py` (21) and
`src/test/retiredPatterns.test.tsx` (6).
**Measurement scripts** `docs/patterns/_measurement/a1_death_spiral.py`,
`a1b_reachability.py`, `a1c_cost.py`, `a1d_episodes.py`, `a1e_gates.py`,
`a1f_rules_replay.py`, `a1g_analyse.py`, `a1h_followup.py`.
