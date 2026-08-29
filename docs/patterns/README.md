# Behavioural patterns — reviews, contracts and replay evidence

Everything about the pattern-by-pattern review lives here, one folder per
pattern, numbered in review order.

## Status

| # | pattern | status | replay (203 sessions) |
|---|---|---|---|
| [00](00-shared/) | *shared* — the pattern baseline (33 types at the time of writing; **28 since Patterns 4, 6, 9, 10, 11 and 14 were retired**), the martingale/adding distinction, the replay close-out | — | **578 alerts / 203 sessions** |
| [01](01-martingale_behaviour/) | `martingale_behaviour` | **COMPLETE** | 39 alerts / 36 days |
| [02](02-adding_to_adverse_position/) | `adding_to_adverse_position` | **COMPLETE** | 99 / 56 |
| [03](03-same_symbol_obsession/) | `same_symbol_obsession` | **COMPLETE** | 22 / 21 |
| [99](99-revenge_trade-FROZEN/) | `revenge_trade` | **FROZEN** by decision | 7 / 7 |
| [04](04-consecutive_loss_streak/) | `consecutive_loss_streak` | **RETIRED** — deleted 26 Aug, replaced by the user's own `max_consecutive_losses` rule | was 78 / 56, now **0** |
| [05](05-overtrading/) | `overtrading_burst` + `daily_overtrading` | **`daily_overtrading` COMPLETE** — now fires on the declared limit only · **`overtrading_burst` DEFERRED**, untouched | daily was 52 / 49, now **0** undeclared · burst 12 / 10, unchanged |
| [06](06-profit_giveaway/) | `profit_giveaway` | **RETIRED / COMPLETE** — the giveback is arithmetic, not behaviour. Measurement kept and now shown in Reports; giveback-as-context is RESEARCH FURTHER | was 100 / 48 days, now **0** |
| [07](07-fomo_entry/) | `fomo_entry` | **COMPLETE** — v2.0.0, one threshold for every context; two of the four could not fire | was 74 / 41 days, now **46 / 26** |
| [08](08-premium_loss_event/) | `premium_loss_event` | **COMPLETE** — v3.0.0. No longer a behaviour detector: a real-time **risk-state** detector on the tick path (zero DB on the hot path, sub-second), exit → analytics, declared boundary → `constitution_violation`. `event_contract.md` | exit alerts 41 → **0**; live path covered by 106 tests |
| [09](09-expiry_day_overtrading/) | `expiry_day_overtrading` | **RETIRED / COMPLETE** — it never withheld, firing on 55 of the 55 positions it could judge (a contracts-vs-lots units bug made its only reachable clause always true), and both trader-facing statistics were unsourced and measured false. Replay clean 203/203, every other detector identical | was 28 / 28, now **0** |

| [10](10-size_escalation/) | `size_escalation` | **RETIRED / COMPLETE** — its claim was ordering, and the real trade order fired *less* than shuffled (42 vs 49.7, p = 0.880); its gate hit the 1-in-6 chance rate; 37 of 42 alerts named an instrument absent from their own evidence. Coverage confirmed: `martingale_behaviour` + `post_loss_recovery_bet` keep the claim. **Closed on 25 mutation-checked tests; the confirmation replay was never obtained (6 environment failures) and could not have changed the decision** | 30 / 30, expect **0** |

| [11](11-direction_instability/) | `direction_instability` | **RETIRED / COMPLETE** — it could not separate an emotional reversal from a change of view; its only discriminator was a 10-minute clock and the clock sorted backwards (flagged flips +Rs 276 / 56% vs -Rs 73 / 42% unflagged; rest-of-session after a flip +Rs 953 vs -Rs 112, p = 0.095). **Level 1 untested — 911 LONG vs 1 SHORT — so the concept is not retired permanently** | was 10 / 9, now **0** |
| [12](12-no_stoploss/) | `no_stoploss` | **MODIFIED / COMPLETE.** Claim and dead branch fixed 29 Aug; firing set unchanged at 52/42. Not a Pattern 9: its gates withhold (52 of 434 judgeable losses = 12%), the 25% gate is selective (only 13.4% of losses clear it) and **29% of firings are trades no other detector sees**. What is wrong is one sentence — *"No stop-loss order detected"* is asserted from the exit fill's order type, checkable on **0 of 52** alerts here and structurally empty in production until F1. The weekly-expiry branch is a **no-op** (25/5 vs 25/5) yet carries 23 of the 52 firings. Consequence runs backwards and significantly (+Rs 815 raw p=0.024; +Rs 1,140 controlled p=0.025; +Rs 890 loss-matched p=0.020), which ranks but cannot judge | **52 / 42** (first ever measured — it was skipped from the replay as UNJUDGEABLE) |
| [13](13-rapid_reentry/) | `rapid_reentry` | **KEEP AS-IS / COMPLETE.** Source-list #5. The window is genuinely selective (17.7% of same-symbol post-loss re-entries, against a 20.7 min median gap) and the detector is pure - 40 lines, zero DB. But **no trader-facing surface reads it**: severity is hardcoded `info`, info never becomes a RiskAlert, and every consumer filters it out - `danger_zone`'s CAUTION path for it is **unreachable — recorded as a design inconsistency, not a bug**. 100% family overlap with `revenge_trade`, though that emits `info` on 13 of 14, so deleting promotes nothing. Outcome direction matches the copy (win rate 14.3% vs 33.8%) but **p = 0.508 at n=14 - insufficient** | **14 / 11** (first ever measured) |
| [14](14-panic_exit/) | `panic_exit` | **RETIRED / COMPLETE** — its subject did not exist. Sub-5-minute holds won at **38.3%** against **39.8%** for longer holds, so a fast exit is not a worse decision; it fired on the losing 60% and **ignored 69 identical-behaviour trades because they made money** — selection on OUTCOME, not behaviour, the same shape as `size_escalation`. A sub-5-min hold is **24% of everything this trader does**, and it fired on their CHEAPEST losses (median ₹308, 69% under ₹500). Its message made three unsupported claims in one sentence. **The fast exit as a neutral fact is NOT retired** — hold time stays on every CompletedTrade | was **108 / 77**, now **0** |

The live queue for every remaining pattern is the **REVIEW STATUS** table in
[`00-shared/BEHAVIOURAL_PATTERNS.md`](00-shared/BEHAVIOURAL_PATTERNS.md).

## The convention — every pattern gets these three

| file | answers |
|---|---|
| `<pattern>_review.md` | what it is meant to detect, what the code does, what is wrong with it, verdict |
| `<pattern>_contract.md` | what it *should* do, decided on evidence, before any code is written |
| **`STATUS.md`** | **what it does NOW** — current logic, constants and why each exists, replay numbers, limitations |

`STATUS.md` is the one to read first and the one to keep current. The review and
contract are historical once a pattern ships; STATUS is not.

Extra documents are added when a pattern needs them — Pattern 2 has `_evidence`,
`_validation` and `_datapath` because its contract took four rounds — but the
three above are the minimum for a pattern to be marked COMPLETE.

## Ground rules these reviews run under

- Evidence before change. A number is not adopted because it looks reasonable.
- Hardcoded is not wrong. Definitional, product-policy and universal-safety
  constants stay.
- No scores, no weighted sums. Counting is a score with every weight set to one.
- Replay is a mandatory gate; differences are classified intended / incidental /
  unexplained, and unexplained means the run failed.
- Limitations are recorded, not closed. A pattern can be COMPLETE with known
  gaps as long as they are written down.
