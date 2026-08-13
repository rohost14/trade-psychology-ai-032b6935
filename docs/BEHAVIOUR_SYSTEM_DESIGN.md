# The behavioural alert system — design

Design of record, written 13 Aug 2026. Nothing here is implemented yet.

This document reasons from first principles about what a real-time behavioural
alert should be. It deliberately cites no external study. Where the tradebook is
used it is used as *this trader's* evidence, never as a population claim.

Companion documents: `docs/ARCHITECTURE_REVIEW_2026-08.md` (what exists today
and what is broken in it), `docs/GLOBALS_DERIVATION.md` (what the year of trades
says about the current constants).

---

## 1. What an alert is for

The product's job is not to predict the next hour. It is to **convert an
automatic action into a deliberate one.**

Tilt is a state in which trading becomes reactive: the trader is no longer
choosing each trade, they are continuing a sequence. An alert's entire mechanism
of action is to interrupt that sequence with a moment of awareness. Whether the
market then goes up or down is not the alert's business.

This has a sharp consequence for how the system is judged. A year of replayed
trades was scored on *rest-of-session P&L*, which measures prediction. That is
the wrong yardstick for a product whose job is awareness — it can rank detectors
by how much money follows them, but it cannot say whether an alert helped.
The only honest measure of help is **behaviour change** (`heeded`), and that is
unmeasurable until alerts reach a live trader.

So: rank detectors with lift, judge the product with heeded, and never conflate
the two.

**Corollary — an alert must never assert a forecast.** "You have lost three in a
row" is true whatever happens next. "This is likely to get worse" is a claim we
cannot support and, on the current data, would frequently be wrong.

---

## 2. Four principles

**P1 — A threshold is right when crossing it means "unusual *for you*".**
Forty trades a day is a scalper's ordinary Tuesday and a positional trader's
breakdown. The signal is never an absolute level; it is displacement from the
trader's own normal. Any constant that encodes an absolute level is wrong for
almost every individual by construction.

**P2 — Alert on transitions, not on states.**
Entering an unusual state is the event. Remaining in it for three hours is not
six more events. This also happens to be what the tradebook shows — the first
danger event of a day carries +5 lift and every escalation stage after it
measures worse — but the principle stands on its own: repetition adds no
information, only fatigue.

**P3 — The unit of measurement is the trader's own distribution.**
Trading outcomes are skewed and fat-tailed, so the summary statistic must be
robust: percentile rank, median, IQR or MAD — never mean ± stddev. (Today the
baseline stores `stddev` and nothing consumes it; that is the wrong dispersion
measure for this data anyway.)

**P4 — Day one must work, and must not lie about working.**
A new user has no history — Zerodha returns no trade history, so this is every
new user, not an edge case. Defaults are therefore load-bearing. They are
legitimate as **priors**, and illegitimate as laws. The system must be able to
say which numbers are earned and which are borrowed.

---

## 3. The architecture

### 3.1 Detectors emit measurements, not verdicts

Today each detector decides severity itself by crossing one of two global
constants. Instead, a detector reports what it observed:

```
{ metric: "consecutive_losses",  value: 3,  at: 11:42 }
{ metric: "minutes_to_reentry",  value: 4,  at: 11:46 }
{ metric: "size_vs_typical",     value: 2.1, at: 11:46 }
```

The detector keeps its logic — *what* to measure and when the measurement is
meaningful. It loses the job of deciding *how bad* that value is, because that
judgement needs the trader's history and does not belong in 27 separate places.

### 3.2 One shared layer answers three questions

For any metric, generically:

1. **Where does this sit in your history?**
   Percentile of `value` within this trader's own past values of this metric,
   shrunk toward the prior while the sample is small.
2. **Is this a transition?**
   The first crossing of the unusual band today for this metric.
3. **What happened the last times you were here?**
   A factual recall from the trader's own record.

### 3.3 The alert rule

> Alert when the value is **unusual for you** AND it is a **transition** AND
> data certainty is good. Otherwise record it, show it in history, never push.

Severity is the percentile itself:

| severity | meaning |
|---|---|
| `info` | inside your normal range — evidence only |
| `caution` | outside your normal range |
| `danger` | ≈ p80 of your own history for this metric |
| `critical` | ≈ p95 |

This makes `critical` a real class (~5% of occurrences per metric) rather than
the 2-in-388 it is today, which in turn makes the session cap's critical
exemption protect something.

### 3.4 What the trader sees

Not a score. The measurement, its place in their own record, and what happened
before:

> **3rd loss in a row.** More than 9 of every 10 of your sessions never get
> here. The last 14 times you did: you kept trading on 11 of them.

Every clause is a fact about the trader. Nothing forecasts.

---

## 4. What this does to the 83 constants

They do not disappear. Most of them **change status** — from law to prior.

| type | count | what happens |
|---|---|---|
| **Definitional** — define the measurement unit (`fomo_window_min`, `spiral_window_min`, `*_min_samples`) | ~20 | stay global. "Within 30 minutes" is what is being measured, not a judgement about the trader |
| **Already relative** — ratios against the trader's own number (`meltdown_caution_pct` = 40% of *your* declared loss limit, `constitution_approaching_pct`) | ~15 | stay as they are. **These are the model the rest should follow** |
| **Judgement thresholds** — where the line sits (`daily_trade_limit: 7`, `consecutive_loss_caution: 3`, `revenge_min_loss_inr: 500`) | ~43 | become **priors**, displaced by the trader's own percentiles as evidence accumulates |
| **Inert** — the confidence axis, live in 1 detector of 27 (`signal_points_*`, `confidence_alert_gate`) | 5 | build out or delete; decide explicitly |

The worst of the judgement group are the **absolute-rupee** ones —
`revenge_min_loss_inr: 500`, `profit_giveaway_min_peak: 1500`. ₹500 is 1% of
₹50,000 and 0.1% of ₹5,00,000. These cannot be universal at all and should be
expressed against capital or against the trader's own typical trade.

Notably `revenge_min_loss_inr` is *already* half-fixed inline
(`max(500 × 0.5, typical_loss × 0.5)`), which is evidence the engine has been
reaching for this design by hand.

### 4.1 The three personalisation mechanisms that exist today

Nobody designed this; it accreted, and unifying it is most of the work:

1. the confidence blend in `get_thresholds` — 3 keys, and mostly does not run
   (two writers, one JSONB key, incompatible shapes);
2. ratios against user-declared limits — `meltdown_*`, `constitution_*`;
3. ad-hoc computation inside detectors — `_typical_loss`, session-local averages.

One mechanism should survive: (1), fixed, with (2) as a special case of it.

---

## 5. Cold start

With no history there is no percentile, so:

- every metric starts at its prior, and the threshold dict reports
  `source: "prior"` so the UI can say *"our starting number, not yours yet"*;
- personal displaces prior continuously via the existing shrinkage
  (`confidence = min(1, n / target)`), never at a cliff;
- below a minimum n the personal percentile is not used at all — a percentile
  over three observations is noise;
- Console CSV import remains the only way to arrive with history, which makes
  it a first-class onboarding path rather than a settings-page feature.

---

## 6. Why this is better than what we had

| | before | after |
|---|---|---|
| what severity means | which global line you crossed, implying a forecast | where the value sits in **your** distribution — a fact |
| who it fits | a trader who does ~7 trades a day | every trader, by construction |
| repeat alerts | every recurrence competes for the cap | one per transition |
| what the trader sees | a band nothing rendered | their own record at that moment |
| judgement constants | ~43 defended as universal law | ~43 priors, honestly labelled, displaced by evidence |
| new user | same numbers as everyone, silently | prior, and the UI can say so |

---

## 7. What has to be built, in order

1. **One baseline writer, one versioned shape, on a schedule.** Everything below
   depends on the trader's own distribution actually existing. Today two
   services race on one key and neither is scheduled.
2. **Self-describing thresholds** — `{value, source, confidence}` instead of a
   bare number. Makes `uses_baseline` derivable rather than hand-maintained
   (it is wrong in 4 of 27 today) and makes cold start inspectable.
3. **Per-metric history + percentile service.** The measurement store the whole
   design rests on.
4. **Severity from percentile; priority as one named policy in L4.** Replaces
   the two-constant crossing and gives the interruption layer a home.
5. **Then pattern by pattern** — each detector's pass becomes "is this the right
   *measurement*", which is a real question, rather than "is 7 the right
   number", which is unanswerable in the abstract.

Steps 1–2 are defect repair and worth doing whatever happens to the rest.
