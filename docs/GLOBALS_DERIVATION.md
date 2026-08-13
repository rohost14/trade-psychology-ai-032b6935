# Deriving the global constants from the tradebook

Findings only. Nothing here is implemented.

**Recomputed 13 Aug 2026 on a repaired harness.** The first version of this
document was measured on sidecars that had silently lost **182 of 2,175 fills
(8.4%)**, across **61 of 203 sessions**: the replay posted one webhook per CSV
*fill*, but Zerodha posts once per *order*, and `Trade.order_id` carries
`UniqueConstraint(broker_account_id, order_id)`, so every tranche after the
first was discarded. Production was never affected —
`tradebook_import_service` writes the per-fill trade_id there. `read_fills` now
merges tranches into the order they belong to (quantity conserved exactly), and
the alert count rose from 358 to **388**.

What survived the repair, and what did not, is recorded honestly in §7.

The question this answers is not "are the constants implemented correctly" —
they are — but "where do the values come from, and does the year of real trades
agree with them." Measured on 2,175 fills / 203 sessions / 971 round trips,
₹50,000 capital, via the reproducible replay (359 alerts, verified identical
across two runs).

Sources of authority used: **this tradebook only.** No SEBI figure, no cited
study, no third-party threshold appears below. Where an outside number is
mentioned it is to record that it did *not* reproduce.

---

## 0. First: what the three layers actually are

Worth stating exactly, because the layers are easy to conflate and the
distinction decides what is safe to change.

| layer | what it is | what it reads | what it emits |
|---|---|---|---|
| **L1** | the 27 detectors in `detector_registry.py` | one `CompletedTrade` + its session context | `RiskAlert` + `BehaviorEvent` |
| **L2** | one meta-detector, `evaluate_death_spiral` | today's `BehaviorEvent`s — their **severity** and **nature domain** | its own alert |
| **L3** | `compute_scores` → driver scores → `behavior_risk` headline → band | today's `BehaviorEvent`s | a number and a word |

Two properties of this design that matter:

1. **L1 detectors do not read any score.** Each fires on its own thresholds.
   `behavior_scores_service.py` states the rule explicitly — *"Detectors must
   never consume these scores (derived-state ban)"*. So there is no
   `if score > X then alert` path anywhere in L1.
2. **L2 counts domains, not score.** `death_spiral` requires ≥2 distinct nature
   domains at `danger`+ inside a 180-minute window; `critical` needs 3 domains
   *and* discipline *and* risk *and* continued escalation *and* compression.
   This is the "this + this + this → alert" logic — and it is driven by
   **domain co-occurrence**, never by the accumulated number.

L3 is therefore the only part that is purely derived state. That is by design,
not by accident.

---

## 1. Do the assigned weights match what the patterns cost?

`RISK_DELTAS` assigns each pattern a weight (revenge 25, death_spiral 30,
martingale 20, …). No entry carries a citation. The tradebook can rank them
directly: after each alert, was the rest of the session negative, versus a
matched null taken from the same year?

Nulls, all from this tradebook: at an arbitrary trade boundary the rest of the
session is negative **56%** of the time; after a losing trade **58%**; after two
losing trades **61%**. Loss-triggered detectors are judged against the
loss-matched null, so mean reversion cannot masquerade as a finding.

| pattern | n | rest-of-session negative | matched null | **lift** | assigned weight |
|---|---|---|---|---|---|
| `expiry_day_overtrading` | 12 | 83% | 59% | **+25** | 20 |
| `size_escalation` | 7 | 71% | 59% | **+12** | 15 |
| `profit_giveaway` | 18 | 67% | 58% | +9 | 20 |
| `revenge_trade` | 26 | 65% | 58% | +7 | **25** |
| `consecutive_loss_streak` | 33 | 64% | 59% | +5 | 20 |
| `fomo_entry` | 26 | 54% | 55% | −1 | 15 |
| `martingale_behaviour` | 25 | 56% | 59% | −3 | 20 |
| `daily_overtrading` | 20 | 55% | 59% | −4 | 10 |
| `options_premium_avg_down` | 12 | 50% | 59% | −9 | 15 |
| `death_spiral` | 19 | 47% | 58% | −10 | **30** |
| `overtrading_burst` | 7 | 43% | 56% | −13 | 10 |
| `same_symbol_obsession` | 23 | 39% | 59% | **−20** | 20 |
| `premium_loss_event` | 5 | 20% | 61% | **−41** | 15 |
| `direction_instability` | 7 | 14% | 58% | **−43** | 15 |

Excluded for n < 5: `winning_streak_overconfidence`,
`end_of_session_mis_panic`, `post_loss_recovery_bet`. Their percentages are
noise.

**Result: rank agreement between assigned weight and measured lift is 0 of 14.**
The weights do not order the patterns the way their measured cost does. The
largest weight in the file, `death_spiral` at 30, sits on a pattern measuring
−10.

**One qualification, against my earlier claim.** On the repaired data the mean
assigned weight is **20.0** for patterns that predict loss and **16.7** for
those that do not. That is a weak signal in the *right* direction — the earlier
"17.5 vs 18.1, no information at all" was an artifact of the broken harness. So
the honest statement is narrower than the one this document originally made:
the weights do not *rank* correctly, but they are not pure noise either.

Reproduce with `python tradedesk/scripts/derive_constants.py <sidecar>.json`.

This is not a claim that the weights are *badly chosen*. It is a claim that they
were chosen against an intuition about how bad a behaviour *sounds*, and that
intuition does not correlate with what the behaviour did.

---

## 2. Does severity predict? It orders backwards.

The score multiplies by severity — info 0.5, caution 1.0, danger 1.5, critical
2.0 — and severity also decides which alerts may interrupt (`NOTIFIABLE`) and
which survive the session cap.

| severity | n | rest-of-session negative | matched null | lift | median ₹ after |
|---|---|---|---|---|---|
| `caution` | 166 | 60% | 57% | +3 | −388 |
| `danger` | 78 | 47% | 58% | **−11** | +200 |
| `critical` | 1 | 0% | 61% | — | +1,429 |

**Severity orders backwards.** `caution` is the mildly *more* predictive class
and `danger` the less predictive one — the opposite of what the vocabulary
promises and of what `NOTIFIABLE = {danger, critical}` assumes.

The obvious confound — danger fires later, so less session remains to go wrong —
is real. Danger's median is 13:03 against caution's 11:41. Holding the horizon
fixed at ≥3 trades remaining:

| severity | n (≥3 trades after) | negative | null | lift | median ₹ after |
|---|---|---|---|---|---|
| `caution` | 77 | 69% | 53% | **+16** | −706 |
| `danger` | 30 | 53% | 55% | **−2** | −734 |

**Correction to this document's first version.** It reported the inversion
*widening* to −12 under this control. On repaired data `danger` comes out at
**−2** — essentially null, not inverted. The ordering defect is real and
survives the control (caution +16 against danger −2 is the wrong way round), but
"danger alerts are followed by better sessions" was an artifact of the dropped
fills and should not be repeated.

A second explanation must be ruled out explicitly: *were the danger alerts
heeded?* No. This is a historical tradebook replayed offline — the trader never
saw a single one of these alerts. Nothing could have been heeded.

A second explanation must be ruled out explicitly: *were the danger alerts
heeded?* No. This is a historical tradebook replayed offline — the trader never
saw a single one of these alerts. Nothing could have been heeded. Whatever
`danger` is selecting for, it is not behaviour change.

So the severity axis, as built, amplifies the class that predicts *less*.

---

## 3. How long does an alert stay informative? Not 90 minutes.

`score_halflife_min = 90` decides that a danger alert at 09:30 still carries a
quarter of its weight at 12:30. Measured against a null over the same horizon:

| horizon after the alert | n | negative | null | lift |
|---|---|---|---|---|
| 15 min | 139 | 56% | 53% | **+3** |
| 30 min | 186 | 55% | 51% | **+4** |
| 45 min | 199 | 51% | 53% | −2 |
| 60 min | 217 | 47% | 54% | −7 |
| 90 min | 225 | 51% | 55% | −4 |
| 180 min | 243 | 56% | 58% | −2 |

Unchanged by the harness repair. Whatever information an alert carries is spent
inside roughly **30 minutes**.
A 90-minute half-life keeps it materially alive for three hours. If the score
survives at all, the half-life implied by this tradebook is ~20–30 min, not 90 —
and the honest reading is that the decay curve is modelling persistence the data
does not show.

---

## 4. The L2 premise: are multiple domains worse than one?

`death_spiral` is the only place the "this + this + this" logic lives, and its
premise is that independent domains firing together mean escalation. Tested
directly, independent of the detector — for every alert, how many distinct
`danger`+ nature domains were already open that day:

| danger+ domains open | n | negative | null | lift | median ₹ after |
|---|---|---|---|---|---|
| 0 | 128 | 62% | 57% | **+5** | −416 |
| 1 | 62 | 48% | 58% | −10 | +200 |
| 2 | 36 | 53% | 60% | −7 | −100 |

And by raw alert count, the thing the master spec explicitly forbids using:

| alerts so far today | n | negative | null | lift |
|---|---|---|---|---|
| 1 | 67 | 61% | 57% | **+5** |
| 2 | 44 | 57% | 57% | 0 |
| 3 | 33 | 58% | 58% | 0 |
| 4+ | 101 | 51% | 59% | −7 |

Unchanged in shape by the harness repair, on 2.5x the sample at 2 domains
(14 → 36).

Neither co-occurrence nor accumulation predicts a worse rest-of-session. The
single most informative moment in the whole dataset is the **first** danger
event of the day, with nothing else open (+5). Every escalation stage after it
measures worse than the null.

The spec's instinct — *state, never raw counts* — was sound, and the state
version does not rescue it: domains behave the same way counts do.

---

## 5. What this means, from several angles

**As a trader.** The loud alerts arrive at the bottom. By the time three things
have gone wrong, the worst of the day is usually behind you — and that is
exactly when the product shouts. An alert that reliably fires at the low is
worse than useless if it is framed as a warning about what comes next.

**As a quant.** Every one of these detectors is conditioning on a local extreme,
and conditioning on an extreme guarantees reversion in the next window. That is
a selection effect, not an edge. The correct control is the matched null used
above, and the effects survive it — which means the anti-signal is real and not
an artifact of the loss condition. The sample is thin (n = 5–28 per pattern, one
trader, one year, one regime); it supports **ranking** detectors, and it does not
support fitting a coefficient. Nothing in section 1 should be read as "set the
weight to 11."

**As a mathematician.** The score is
`Σ weight × severity_mult × confidence × decay`. Section 1 says the weights are
uninformative, section 2 says the severity multiplier has the wrong sign,
section 3 says the decay constant is roughly 3× too slow, and `confidence` is
1.0 for 26 of 27 detectors (G3) so it is not a term at all. Four factors: one
inert, one inverted, two unsupported. The formula's structure is fine; its
inputs do not survive contact with the data.

**As an engineer.** Four band vocabularies exist over this number
(`session_state` 40/70/90, `_behavior_state` 20/40/60/80, `score_band_*`
30/60/80, and `risk_state` which is not a band at all). None of the four is
rendered anywhere: `BehaviorRiskBadge` is defined and never imported,
`BehaviorScoresCard` lives only in `_archive/`, `behavior_state` is sent over
the WebSocket and read by nothing, and Dashboard fetches `/api/risk/state` only
to extract two limit fields. So ~55 of the ~148 constants currently feed an
output with no consumer.

**As a developer.** There is a live latent defect on the way out:
`api/risk.py:172` can return `risk_state = "critical"`, while
`schemas/risk_alert.py:41` and `Dashboard.tsx:46` both declare only
`safe | caution | danger`, and the ternary at `Dashboard.tsx:190` maps anything
else to **"Trading Safely"**. It is inert only because nothing renders
`status_message`. This is the exact failure `core/severity.py`'s docstring was
written to prevent, one layer above where that fix was applied.

**As the product (the Kamath lens).** Zerodha's own public position is that the
broker should show the customer what happened and decline to predict what
happens next — nudges over gates, disclosure over restriction. The L1 alerts
already meet that bar: *"you have lost three times on NIFTY today"* is a fact
that is true regardless of what the market does at 14:00. The score, the bands,
and the escalation ladder are the parts that quietly became a forecast — and a
forecast is the one thing this data says we cannot do. The product's own stated
philosophy, "mirror, not blocker," is an argument against the score before any
of the numbers above are considered.

---

## 6. What follows

**Anti-predictive is not false.** A detector with negative lift is still
reporting something that happened. What negative lift argues against is
*interrupting* on it, and above all against making it *louder* than the rest.

The finding is not "the detectors are broken." It is narrower and more
actionable: **L1 is a mirror and mostly works; L3 is a forecast and does not.**
The escalation machinery — weights, driver scores, the headline, the four band
systems, the severity multiplier — is the part that claims to know where the
session is heading, and it is the part the tradebook contradicts.

Three of the four constant groups that section 1–4 examined have no consumer at
all, so removing them costs nothing the trader can see. `death_spiral`'s four
`spiral_*` constants **do** fire alerts and must be decided on their own terms:
its lift is −10 with the loudest voice in the product.

---

## 7. What survived the harness repair, and what did not

The first version of this document was measured on sidecars missing 8.4% of
fills. Everything was recomputed on a repaired harness (358 → 388 alerts, 205 →
245 labelled outcomes). Recorded plainly, because a finding that moves under a
better measurement deserves to be flagged rather than quietly restated:

| finding | before | after | verdict |
|---|---|---|---|
| L2 co-occurrence premise fails (0 domains best) | +5 / −11 / −8 | +5 / −10 / −7 | **holds** — and on 2.5x the sample at 2 domains |
| escalation by raw count fails | +2 / +1 / +3 / −9 | +5 / 0 / 0 / −7 | **holds** |
| alert signal dies by ~45 min, not 90 | +4 → −1 by 45m | +4 → −2 by 45m | **holds** |
| weights do not rank with cost | 2 of 14 | **0 of 14** | **holds, slightly stronger** |
| weights carry *no* information | means 17.5 / 18.1 | means **20.0 / 16.7** | **weakened** — weak signal in the right direction |
| severity orders backwards | caution +1, danger −10 | caution +3, danger −11 | **holds** |
| danger is *anti*-predictive at fixed horizon | −12 | **−2** | **retracted** — it is approximately null, not inverted |

Individual patterns moved more than the aggregates. `revenge_trade` went from
−2 to **+7** and `daily_overtrading` from +4 to **−4**; `expiry_day_overtrading`
strengthened from +13 to **+25**. Per-pattern verdicts from the first version
should not be carried forward — the pattern-by-pattern pass must read this
table, not that one.

**The L3 retirement decision is unaffected.** It rested on the two findings that
survived untouched (escalation does not predict; the decay constant outlives the
signal), on the 0-of-14 ranking, and on the fact that nothing rendered any of
it — not on the severity magnitude that has now been retracted.

Open and deliberately unanswered here: what severity should *mean* if it no
longer means "more likely to get worse". Decided separately on 13 Aug — the size
of the fact in the trader's own distribution — see `docs/NEXT_SESSION.md` §3.
