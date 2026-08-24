# Patterns 1 and 2 — close-out against the corrected replay

25 Aug 2026. **No detector changed.** The corrected 203-session replay is now
the baseline; every earlier figure is superseded.

---

## The baseline

**578 alerts across 203 sessions**, against 388 on the contaminated run. The
increase is mostly arithmetic, not behavioural: **912 completed positions against
742**, because carry-forward now closes 170 positions that previously never
closed at all — their closing fill was misread as opening a short, so no
`CompletedTrade` was ever produced.

Three patterns remain excluded by the harness: `no_stoploss` (no order-type
column), `excess_exposure` and `session_meltdown` (capital-derived and
unvalidatable). Rules were off, so `constitution_violation` and
`cooldown_violation` cannot fire.

| pattern | alerts | days | severities |
|---|---|---|---|
| `adding_to_adverse_position` | 99 | 56 | caution 69 · danger 21 · critical 9 |
| `consecutive_loss_streak` | 78 | 56 | caution 63 · danger 15 |
| `daily_overtrading` | 52 | 49 | caution 49 · danger 3 |
| `profit_giveaway` | 48 | 20 | caution 15 · danger 33 |
| `premium_loss_event` | 41 | 39 | caution 23 · danger 9 · critical 9 |
| **`martingale_behaviour`** | **39** | **36** | **danger 27 · caution 12** |
| `death_spiral` | 39 | 39 | danger 39 |
| `options_premium_avg_down` | 30 | 30 | caution 30 |
| `size_escalation` | 30 | 30 | caution 30 |
| `fomo_entry` | 29 | 29 | caution 29 |
| `expiry_day_overtrading` | 28 | 28 | caution 27 · danger 1 |
| `same_symbol_obsession` | 22 | 21 | danger 17 · caution 5 |
| `overtrading_burst` | 12 | 10 | caution 9 · danger 3 |
| `direction_instability` | 10 | 9 | caution 9 · danger 1 |
| `winning_streak_overconfidence` | 7 | 7 | caution 7 |
| `revenge_trade` | 7 | 7 | caution 7 |
| `post_loss_recovery_bet` | 5 | 5 | caution 4 · danger 1 |
| `end_of_session_mis_panic` | 2 | 2 | caution 2 |

## Pattern 1 — `martingale_behaviour`

**Every firing satisfies the final definition. Five checks, all PASS.**

| check | result |
|---|---|
| risk actually increased | **PASS** — 31 of 31 |
| at least 2 trailing consecutive losses | **PASS** |
| ratio at or above the caution multiple | **PASS** |
| danger only at or above 2.0× | **PASS** |
| caution strictly below 2.0× | **PASS** |

**The multipliers hold on the corrected risk measure and are not retuned.**
Ratio distribution: min **1.53×**, p50 **2.45×**, max **11.63×**. Twelve firings
land in the 1.5–2.0× caution band and nineteen at danger — so both tiers are
populated and neither is vestigial. Nothing in the corrected replay exposes a
defect in either number, so neither moves.

**21 of 31 escalations are into a different underlying**, which confirms the
review's central correction: measuring in capital at risk rather than quantity
was necessary, because the cross-instrument case is the majority, not the
exception.

**9 firings are on a winning current trade.** Correct and deliberate — the
escalation happened regardless of how that trade turned out, and this detector
reports the decision, not the outcome.

**False positives:** none found. Every firing has a genuine increase in capital
at risk following at least two consecutive losses.

**False negatives:** not re-measured here. The 22 the old implementation missed
are now caught by construction, since the step measured is the one the trader
took.

**Timing:** exit-triggered, which is correct — the evidence is a *closed* loss.

## Pattern 2 — `adding_to_adverse_position`

**Every firing satisfies the definition. Four checks, all PASS.**

| check | result |
|---|---|
| every firing has at least one adverse add | **PASS** — 64 of 64 |
| every adverse move is strictly positive | **PASS** |
| `critical` only with 3+ adverse adds | **PASS** |
| `info` only with a single non-doubling add | **PASS** |

**Episode dedup verified in the real path**, with carry-forward enabled and
Redis up so the entry-batch pipeline actually ran:

```
2025-06-12  ASIANPAINT25JUN2400CE   caution -> danger              (one episode)
2025-11-25  NIFTY25NOV26000CE       caution -> danger -> critical  (one episode)
            SUNPHARMA25DEC1900CE    caution                        (its own episode)
2026-01-29  SENSEX26JAN82000CE      caution -> danger -> critical  (one episode)
```

**One alert per severity level per episode, and a second symbol correctly gets
its own.** Offline, 64 firings across 57 episodes with `{1 firing: 50, 2
firings: 7}` — never more than two — and 54 of 57 episodes have all-distinct
severities, so the three remaining same-severity repeats are exactly what dedup
suppresses.

**Closed → new entry does not fire**, and **favourable adds stay silent** —
both asserted in the integration test that drives the genuine pipeline, and both
confirmed by the LT case, which now reads as two profitable closes rather than a
fabricated short.

**Real-time entry triggering confirmed working end to end** for the first time:
Redis was down or intermittent on every earlier run, so the entry-batch path had
been silently falling through to the inline path.

## The one number that moved the wrong way

`revenge_trade` fell from **38 alerts to 7**, while the trade count rose. That is
backwards and I have not fully attributed it.

Ruled out: the session alert cap (it bit twice all year, never on this pattern)
and family consolidation.

What is established: **the trade sequence changed.** 172 carried positions now
close on the following session — 71 at a profit, 101 at a loss — and each one
occupies the "previous trade" slot with an exit time unrelated to that day's
rhythm. `revenge_trade` gates on *both* "the previous trade lost" *and* "the gap
is under 20 minutes", so both conditions are sensitive to which trade is
previous. A profitable carried close breaks the chain outright; a loss-making one
that closes early can push the gap past the window.

That is a plausible mechanism, not a proven attribution, and I am not claiming
more. **No action taken:** `revenge_trade` is frozen by decision, and its
research conclusion — that no fill-level signature separates post-loss from
post-win behaviour — did not rest on the alert count. If anything, the old 38 was
partly an artefact of misread fills.

## Remaining limitations — carried, not closed

1. **Instrument coverage outside long options is synthetic for both patterns.**
   The book is 727 LONG against 15 SHORT, 16 equity rows and 2 futures, and every
   escalation in it is a long option. Directional symmetry is proven by
   construction and by synthetic tests; it has never met a real short.
2. **Cross-strike sequences stay out of Pattern 2.** 53 occurrences on 30 days,
   deliberately excluded because strike progression alone is not evidence of
   anything. Open as separate research on post-loss rotation. Scope not expanded.
3. **Pattern 2's per-episode dedup cannot be audited from the replay sidecar**,
   which stores no alert details. It is verified instead by unit tests and by
   direct inspection of three replayed sessions.
4. **The post-win control remains negative for both patterns.** Neither makes a
   predictive claim; both report a fact.
5. **`no_stoploss`, `excess_exposure` and `session_meltdown` remain unvalidatable**
   by this harness for the reasons above.

## Status

| Pattern | Full-replay result | Problems | Changes required | Status |
|---|---|---|---|---|
| **1 `martingale_behaviour`** | 39 alerts / 36 days · 31 firings, **5/5 definition checks PASS** · ratio 1.53–11.63×, both tiers populated | none found | **none** — multipliers hold on the corrected measure | **COMPLETE** |
| **2 `adding_to_adverse_position`** | 99 alerts / 56 days · 64 firings, **4/4 checks PASS** · dedup gives ≤1 alert per severity per episode, verified in the real path | none found | **none** | **COMPLETE** |
| **3 `same_symbol_obsession`** | 22 alerts / 21 days · danger 17 · caution 5 | severity rule, dead constant and dedup already fixed in `09f3d28`; entry-triggering measured and **rejected** (later in 14/20 episodes, never in 6) | contract items already shipped; nothing outstanding | **COMPLETE** |
