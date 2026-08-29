# Closed-Pattern Impact Register

**29 Aug 2026. INFORMATIONAL. No pattern is reopened, reviewed, retuned,
retired or restored by this document.**

Which of Patterns 1-11 had their measurement inputs changed by the
infrastructure phase, and which genuinely need remeasuring.

---

## Blast radius: two changes, not nine

Everything built this phase — `margin_model`, `risk_quantities`,
`instrument_master`, `contract_spec`, `exchange_support`,
`get_order_margins` — is **imported by no detector**. Verified by grep. None of
it can have moved a pattern measurement.

Only two changes touch code the engine actually runs:

**F15** — the option regex now reads 2-digit strikes, half-rupee strikes and
hyphenated underlyings. Measured on the reference book: **17 symbols across 38
fills of 2,175 (1.7%)**. Before F9 those were classified **EQUITY with the whole
symbol as the underlying**; between F9 and now they **abstained**.

**F16** — the `or "EQ"` fallback is gone at two call sites, so F9's abstention
reaches the live path instead of being converted back to equity.

Every verdict below follows from those two and nothing else.

---

## Register

| # | pattern | status | inputs changed? | prior decision still valid? | remeasure? |
|---|---|---|---|---|---|
| 1 | `martingale_behaviour` | COMPLETE | **yes, small** — 38 fills previously carried an equity notional denominator; they now carry option premium | **yes** | **optional** |
| 2 | `adding_to_adverse_position` | COMPLETE | **yes, small** — same-position grouping keyed on underlying | **yes** | **optional** |
| 3 | `same_symbol_obsession` | COMPLETE | **YES, materially** — it groups on `underlying`, and for those 17 symbols the "underlying" was the entire tradingsymbol, so **two contracts on the same stock could never group**. They can now | **unknown** — the direction is toward MORE grouping, i.e. more firing | **YES** |
| 4 | `consecutive_loss_streak` | RETIRED | no — loss-run counting is instrument-independent | **yes** | no |
| 5 | `daily_overtrading` | COMPLETE | no — a count of closes | **yes** | no |
| 5 | `overtrading_burst` | DEFERRED, live | **yes, small** — clusters by underlying via `count_structures` | **yes** | **optional** |
| 6 | `profit_giveaway` | RETIRED | no — drawdown from session peak is arithmetic on P&L | **yes** | no |
| 7 | `fomo_entry` | COMPLETE | **YES** — it counts DISTINCT underlyings, and 17 symbols each counted as their own underlying, **inflating the count** | **probably**, but the input was measurably wrong | **YES** |
| 8 | `premium_loss_event` | COMPLETE | **YES, materially** — it guards `instrument_type in ("CE","PE")` and therefore **never saw these 38 fills at all**. This is new coverage, not a shifted number | **unknown** | **YES** |
| 9 | `expiry_day_overtrading` | RETIRED | no — it fired on 55 of 55 positions it could judge; the finding was that it never withheld | **yes** | no |
| 10 | `size_escalation` | RETIRED | no — retired on the shuffle null (42 real vs 49.7 shuffled, p = 0.880) | **yes** | no |
| 11 | `direction_instability` | RETIRED | no — retired on outcome, and the book is 911 LONG vs 1 SHORT regardless | **yes** | no |
| 99 | `revenge_trade` | **FROZEN** | **yes, small** — `risk_basis` denominators for 38 fills | frozen, so no decision to revisit | no, while frozen |

---

## The three that need remeasuring — and why the bar is met

**Pattern 8 `premium_loss_event`** is the strongest case. It did not produce a
slightly different number on these trades; it **could not see them**. Its guard
is `instrument_type in ("CE","PE")` and their instrument type was `EQ`. Any
statement about its firing rate was computed over a book that was silently 1.7%
smaller than the real one. That is a coverage change, and coverage changes
cannot be reasoned about from the old measurement.

**Pattern 3 `same_symbol_obsession`** grouped on `underlying`, and for those
symbols the underlying was the whole tradingsymbol — so `SUZLON25NOV56CE` and
`SUZLON25NOV60CE` were two different "symbols". Repeated attempts at the same
stock were structurally invisible. The correction can only increase grouping,
so it can only increase firing.

**Pattern 7 `fomo_entry`** counts distinct underlyings, and the same defect
inflated that count: every unreadable contract was its own underlying. Its
inputs were measurably wrong in a known direction.

## The five retirements all stand

4, 6, 9, 10 and 11 were retired on findings that **do not depend on instrument
classification**: a chance rate against loss runs, arithmetic on a session peak,
a detector that never withheld, a shuffle null, and an outcome comparison. A
1.7% change in how a minority of contracts is typed does not reach any of those
arguments. **No retirement should be revisited.**

## What "optional" means

Patterns 1, 2 and `overtrading_burst` had inputs move for a small subset. The
change is real but its direction is not obviously decision-relevant, and each
prior decision was a KEEP. **Remeasuring them is cheap only if a replay is
already being run for 3, 7 and 8** — which it would be. Do them in the same
pass or not at all; do not start a replay for them alone.

---

## Cost, stated honestly

All three required remeasurements need **one replay**, not three. Per the pace
rule learned earlier: one replay per question, close on the independent
detectors, never a second replay to explain a composite. A replay takes **40
minutes to 2 hours** and this machine has failed several.

**This is not a request to run it.** It is the identification the brief asked
for. Nothing is reopened until pattern work resumes, and pattern work does not
resume in this phase.
