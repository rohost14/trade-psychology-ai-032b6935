# What each detector assumes about the trader

Extracted from the code, then checked against 61 sessions of real F&O trading
(744 fills, 297 round trips).

**Why this document exists.** `martingale_behaviour` had correct code, 32 passing
tests, and a wrong idea of the behaviour: it assumed a trader who hammers one
instrument, and fired zero times for a trader who escalates by rotating symbols.
The scenarios could not catch it because they were written from the same
assumption. Verifying that a detector implements its stated logic and verifying
that the stated logic describes real traders are different claims, and only the
first was ever done.

Four detectors carried that same restriction. Three were found by reading, one
by grepping for it afterwards. This is the systematic version.

---

## The assumptions that have already cost us

### "The trader stays in one instrument"

Every sizing detector compared quantities, and quantity is only comparable within
one underlying — 50 Nifty against 2000 Industower is meaningless. The
restriction was correct on its own terms and made all four blind.

| Detector | Was | Now |
|---|---|---|
| `martingale_behaviour` | same underlying | falls back to notional value |
| `size_escalation` | same underlying | falls back to notional value |
| `post_loss_recovery_bet` | same underlying | falls back to notional value |
| `winning_streak_overconfidence` | same underlying | falls back to notional value |

Evidence: martingale went from **0 to 10** firings on the same tradebook.

**Still assuming same-underlying, deliberately and correctly:**
`same_symbol_obsession` (the pattern *is* one instrument), `direction_instability`
(a flip on one underlying is the pattern), `fomo_entry` (counts distinct
underlyings, so it needs them).

### "The session has enough trades to compare"

| Detector | Needs | Sessions that qualify |
|---|---|---|
| `martingale_behaviour` | 3+ prior | 22 of 61 |
| `size_escalation` | 3+ prior | 22 of 61 |
| `post_loss_recovery_bet` | 3+ prior | 22 of 61 |

Median session is **2 completed round trips**. These three cannot speak on 39 of
61 days regardless of what happened. Not wrong — a progression genuinely needs a
run — but it means "silent" carries far less information than it appears to.

### "Capital is a stable number"

Removed. Six thresholds were shares of declared capital; the trader's capital
moved between ₹30,000 and ₹50,000, was withdrawn at month end and topped up
mid-month. See `THRESHOLD_REWORK_PLAN.md`.

### "₹500 means the same to everyone"

Removed. `revenge_min_loss_inr` and `profit_giveaway_min_erosion` now measure
against the trader's own median losing trade.

---

## Assumptions still standing, and what would test each

| Detector | Assumes | How it could be wrong | Status |
|---|---|---|---|
| `no_stoploss` | a stop-loss order is recorded | Console tradebooks carry no order type; a trader using mental stops looks identical to one using none | **untestable from a tradebook** |
| `end_of_session_mis_panic` | product is MIS | product is inferred in replay; an NRML trader is invisible to it | **inferred, not known** |
| `premium_loss_event` | long options only | a seller who loses badly is a different pattern, deliberately excluded | intended |
| `options_premium_avg_down` | long options only | same | intended |
| `opening_5min_trap` | 09:15–09:25 matters | analytics-only, never alerts | intended |
| `time_of_day_bias` | enough history for a baseline | it was **neither clean nor starved** — the silence was an artefact (a CSV book carries no profile) and it was LIVE for any trader with 30+ sessions. Its danger hours do not survive into a second period | **RESOLVED 1 Sep 2026 — RETIRED**, learning kept |
| `win_rate_collapse` | a stable prior win rate | silent for the same artefact reason; its guards are sound (baseline confidence ≥ 0.5 **and** an 8-trade day) | **RESOLVED 1 Sep 2026 — KEEP AS-IS** |
| `strategy_breakdown` | strategies are identifiable | its two conditions (win-rate drop, profit-factor drop) never disagree in this book, so there is nothing to separate | **RESOLVED 1 Sep 2026 — DEFERRED**; unblock = sessions where they disagree |
| `expiry_day_overtrading` | expiry derived from symbol | a symbol/date mismatch makes every day non-expiry — this broke a scenario | fixed in tests, worth watching |
| `fomo_entry` | 3 instruments in 30 min is chasing | on expiry day the threshold was 2, which flags ordinary sessions | raised to 4 |

---

## The three that have never spoken

`time_of_day_bias`, `win_rate_collapse`, `strategy_breakdown` — silent across all
61 sessions.

They compare today against the trader's own baseline, so three months may simply
be too little history. **The twelve-month tradebook resolves this**, and it is
the clearest question that book can answer: if they stay silent across 250
sessions, they are not earning their complexity.

> **ANSWERED 1 Sep 2026 — Reviews 25-27, and the three answers differ.** Each was
> measured twice: as the engine sees it today, and with the baseline supplied
> from the book's own history, which is what a mature trader would present.
>
> The framing above was **wrong in one respect and it matters**: the silence was
> not "too little history". A CSV tradebook carries **no `UserProfile`**, so the
> baseline the three read was never written at all. Silence in replay was a
> property of the harness. `time_of_day_bias` in particular was **LIVE in
> production** for any trader with 30+ sessions, written on a nightly 18:15 IST
> beat, the whole time it read as "never fired".
>
> - `time_of_day_bias` — **RETIRED.** Supplied with a baseline it fires the
>   equivalent of ~81 alerts on a signal that does not survive into a second
>   time period (danger hours: full book `[12, 15]`, first half `[11, 12, 15]`,
>   second half **none**; rank correlation between halves rho = +0.071). The
>   nightly learning and storage are **KEPT** — only the trader-facing
>   interpretation is gone.
> - `win_rate_collapse` — **KEEP AS-IS.** Same artefact, sound guards.
> - `strategy_breakdown` — **DEFERRED.** Its two conditions never disagree in
>   this book. Unblock = sessions where they do.
>
> Evidence: `docs/patterns/25-27-performance-trio/`.

---

## Method, for the next person

Do not ask "did the detector fire". A blind detector is silent, and silence looks
like a clean session.

Ask: **does the behaviour exist in the data, and did the engine see it?**

`tradedesk/scripts/recall_check.py` counts six behaviours directly from a
tradebook — no engine, no shared thresholds, round trips rebuilt FIFO from raw
fills so a fault in position tracking cannot hide itself. Compare its counts
against the replay's. A behaviour present in one and absent from the other is a
recall gap with specific days attached.

It found the `same_symbol_obsession` gap (9 days of behaviour, 1 alert) that led
to `session_meltdown` being wrongly treated as a composite and absorbing every
other alert on 41 of 61 days.

Deliberately a second implementation. Everywhere else in this codebase a second
copy is the bug; here it is the instrument.
