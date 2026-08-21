> **ARCHIVED 21 Aug 2026 — do not use as a current reference.**
>
> Superseded by `docs/GLOBALS_DERIVATION.md` (13 Aug 2026), which re-derived
> every one of these findings from the tradebook after the replay harness was
> repaired. This file still describes RISK_DELTAS, the behaviour score and the
> band systems, all of which were removed in 16d79ce.

---

# Global constants — findings

Findings only. Nothing here is implemented.

Scope: the constants that belong to no single detector, so the
pattern-by-pattern pass will never reach them — signal points, the confidence
gate, the behaviour score, the bands, the death-spiral composite, the
constitution ladder, the guardian budget, and baseline maturity.

---

## G0 — The audit undercounted. There are not 109 constants.

`docs/THRESHOLD_AUDIT.md` counted 109 in `trading_defaults.py`. That file is not
the only place thresholds live.

**`RISK_DELTAS` in `behavior_engine.py:84` — 36 more.** One weight per pattern,
no citation on any of them, and they are not decoration: they are the entire
input to the session risk score, and the multiplier in every driver score.

```python
"consecutive_loss_streak": 20,   "revenge_trade": 25,
"overtrading_burst": 10,         "size_escalation": 15,
"martingale_behaviour": 20,      "cooldown_violation": 25,
...
```

Why is revenge 25 and martingale 20? Nothing says. These numbers decide which
driver dominates the headline the trader sees.

Plus inline literals in `behavior_scores_service.py` that never reached
`trading_defaults` at all:

| literal | line | meaning |
|---|---|---|
| `75` | 100 | assumed confidence when an event has none |
| `0.5` | 104 | contribution below this is discarded as noise |
| `10` | 98 | weight for a pattern missing from `RISK_DELTAS` |

**Running total: 109 + 36 + 3 = ~148**, and the three inline ones are invisible
to any search of the defaults file.

---

## G1 — `RISK_DELTAS` disagrees with the detector registry

| | |
|---|---|
| entries in `RISK_DELTAS` | 36 |
| live pattern types | 33 |
| in `RISK_DELTAS`, not a live pattern | `iv_crush_behavior`, `options_direction_confusion`, `premium_destruction`, `rapid_flip` |
| live pattern with **no** weight | `capital_mismatch` |

The four dead entries are harmless (retired patterns, never looked up).
`capital_mismatch` is not.

**And the two consumers disagree about what a missing key means:**

```python
# behavior_engine.py:320    — session risk score
RISK_DELTAS.get(e.event_type, Decimal("0"))

# behavior_scores_service.py:98 — driver score
float(RISK_DELTAS.get(ev.detector, 10))
```

So a `capital_mismatch` event moves the session risk score by **0** and the
driver score by **10**. Same event, same missing key, two different answers,
neither of them chosen deliberately.

**Severity: MEDIUM.** A live detector contributes nothing to one score and an
arbitrary default to the other.

---

## G2 — Three band systems over two scores, none agreeing

| system | thresholds | vocabulary | defined in |
|---|---|---|---|
| `session_state` | 40 / 70 / 90 | normal · caution · danger · blowup | `trading_session_service.py:40`, hardcoded |
| `_behavior_state` | 20 / 40 / 60 / 80 | Stable · Pressure · Tilt Risk · Tilt · Breakdown | `behavior_engine.py:128`, hardcoded literals |
| `behavior_risk` band | 30 / 60 / 80 | normal · elevated · high · critical | `score_band_*` in `trading_defaults` |

The first two read **the same number**. `new_risk` is computed once in
`behavior_engine.py:323` and then fed to `_behavior_state(new_risk, peak)` AND
to `TradingSessionService.update_risk_score(...)`, which independently maps it
through its own thresholds. One score, two vocabularies, two sets of cut
points, and a score of 45 is simultaneously "caution" and "Tilt Risk".

The third is a different computation entirely (decayed, confidence-weighted
per-driver) that happens to also be 0–100 and also produce a band.

Only one of the three is in `trading_defaults`. The other two are literals in
service code, which is why an audit of the defaults file missed them.

**Severity: MEDIUM.** Not a crash; a guarantee that any future tuning changes
one and silently desynchronises the others.

---

## G3 — The confidence axis is load-bearing for one detector in twenty-seven

Restating from `THRESHOLD_AUDIT.md` because it determines whether tuning
`confidence_alert_gate` means anything.

Signal stacking is implemented **only in `revenge_trade`**. Every other
behavioural detector leaves `confidence=None`, which resolves to
`DATA_QUALITY_CONFIDENCE` — `GOOD` = 100.0 on any live postback.

Consequences:

1. `confidence_alert_gate` (50) can only ever gate `revenge_trade`. For the
   other 26 detectors, confidence is 100 by construction and the gate is dead
   code.
2. In the driver score, `conf = confidence / 100` is therefore `1.0` for almost
   every event. A term that is constant contributes nothing — the formula reads
   as four factors and behaves as three.

`signal_points_*` (30/20/10/5) has the same reach: one detector.

**Severity: MEDIUM.** The architecture is described as two-axis; one axis is
active in 4% of the surface.

---

## G4 — The score formula, and what is actually unjustified in it

`behavior_scores_service.py:103`

```python
contribution = weight × severity_multiplier × confidence × decay
decay = 0.5 ** (age_minutes / 90)
```

Every input is a chosen number:

| input | value | basis |
|---|---|---|
| `weight` | `RISK_DELTAS`, 36 values | none (G0) |
| `severity_multiplier` | info 0.5, caution 1.0, danger 1.5, critical 2.0 | none |
| `confidence` | ~always 1.0 | inert (G3) |
| `score_halflife_min` | 90 | none |
| noise floor | 0.5 | none, and inline |

The 90-minute half-life is the one with real behavioural reach: it decides that
a danger alert at 09:30 is worth a quarter of itself by 12:30. Nothing
justifies 90 over 45 or 180, and the choice materially changes what the trader
sees mid-session.

The headline is `dominant + 0.15 × mean(others)` — deliberately not a mean,
which is good design (a mean would let three calm domains hide one bad one).
`0.15` itself is unsourced.

**Severity: LOW-MEDIUM.** Coherent structure; every coefficient is a guess.

---

## G5 — Death spiral: the composite is anti-predictive and its gates are strict

From the outcome labelling over the year: `death_spiral` fires on 25 days, and
the rest of the session after it goes **negative 43%** of the time against a
matched base rate of 62%, with a median rest-of-session of **+₹656**. It is the
strongest anti-signal of any detector measured.

Its constants:

| constant | value | effect |
|---|---|---|
| `spiral_domain_min_severity` | `danger` | caution events never count toward a domain |
| `spiral_warning_domains` | 2 | 2 domains + capital at risk → danger |
| `spiral_critical_domains` | 3 | 3 domains **and** discipline **and** risk **and** continued escalation **and** compressed → critical |
| `spiral_window_min` | 180 | domains must fire within 3h to be "compressed" |

The critical path requires five simultaneous conditions. That is a deliberate
design (`master §1D.2 FINAL`) and it means `critical` is close to unreachable —
which interacts directly with the fix just shipped in `27c7c6d`, where
`critical` is the severity that survives the session cap.

**Worth measuring, not assuming:** how many times did `death_spiral` reach
`critical` in the year? If the answer is zero, then the cap exemption protects
a severity that never occurs.

**Severity: MEDIUM.** Anti-predictive with the loudest voice in the product,
and it suppresses its own inputs when it fires (`_COMPOSITES`).

---

## G6 — Guardian budget and constitution ladder

`guardian_monthly_budget` = 3. Correctly implemented — it counts
`delivered_whatsapp_at` this month, and that column **is** written
(`trade_tasks.py:1739`).

*Correction to an earlier finding of mine:* I stated in B7 that
`delivered_push_at` is "written only by the merged-push branch". That is stale.
There is a full receipts system — `_push_succeeded`, `_already_delivered`, and
writes on both channels. The B7 fix (the cap counted saved rows, not
deliveries) was still correct; the supporting claim was not.

`constitution_approaching_pct` 0.80 / `constitution_severe_pct` 1.20 — "you are
at 80% of your own limit" is a defensible product choice and needs no external
source, since the limit is the trader's own number. Lowest priority.

`baseline_target_sessions` 30 / `baseline_target_trades` 100 — these set how
fast personal thresholds displace defaults (`confidence = min(1, n/target)`).
Directly governs the blend that is the fix for most of bucket A in
`THRESHOLD_AUDIT.md`. Unsourced, and more consequential than it looks.

---

## What can actually be measured, and what cannot

The reproducible baseline makes a sensitivity sweep possible. For each
candidate value, replay the year and diff the sidecars — `replay_diff.py`
already separates real differences from ordering.

**Answerable now, without outcome labels:**

| question | method |
|---|---|
| Does `confidence_alert_gate` matter? | replay at 40 / 50 / 60; count alerts that change | 
| Does `score_halflife_min` matter? | replay at 45 / 90 / 180; compare band distribution |
| Does `death_spiral` ever reach critical? | count severities in the existing sidecar |
| How often is `capital_mismatch` raised? | count in the sidecar — decides whether G1 is urgent |
| Which band system disagrees with which, and when? | compute all three over the year from one replay |

A constant whose value changes **nothing** across a year of real trading is not
a threshold, it is decoration — and can be deleted rather than argued about.
That is the cheapest possible outcome and worth chasing first.

**Not answerable without outcome labels:** whether 50 is the *right* gate.
Sensitivity tells us the gate is load-bearing; only outcomes tell us where it
belongs. The labelling built in `bff2ff7` is the input for that, and it
currently has 300 labelled alerts from one trader — enough to rank detectors,
not enough to fit a coefficient.

---

## Suggested order

1. **Count things in the existing sidecar** — free, no replay: death-spiral
   severities, `capital_mismatch` frequency, band disagreement. Decides which
   of G1/G5 is real.
2. **Fix G1** — a live detector with no weight, and two different defaults for
   the same missing key. Small, unambiguous, no measurement needed.
3. **Sweep the gate and the half-life** — the two constants with the widest
   reach. Expect at least one to prove inert.
4. **Decide G2** — one score should have one vocabulary. Cheap to unify, and it
   stops future tuning desynchronising three places.
5. **Leave G3 as a stated architectural decision** — either stacking spreads to
   more detectors, or the docs stop calling it two-axis. Not a code fix.
