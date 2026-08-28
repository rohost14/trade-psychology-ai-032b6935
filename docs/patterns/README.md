# Behavioural patterns — reviews, contracts and replay evidence

Everything about the pattern-by-pattern review lives here, one folder per
pattern, numbered in review order.

## Status

| # | pattern | status | replay (203 sessions) |
|---|---|---|---|
| [00](00-shared/) | *shared* — the pattern baseline (33 types at the time of writing; **30 since Patterns 4, 6, 9 and 10 were retired**), the martingale/adding distinction, the replay close-out | — | **578 alerts / 203 sessions** |
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

| [11](11-direction_instability/) | `direction_instability` | **REVIEW DONE — awaiting decision.** Verdict **MODIFY (registry truthfulness only)**; behaviour KEEP AS-IS, evidence insufficient. First pattern the measurement does NOT condemn: sequence null runs **1.21x above** chance (p = 0.187), where 4/6/10 all ran at or below it. Alert is factual, no invented statistic, 10 alerts / 203 sessions. No demonstrated consequence though (p = 0.892) | 10 / 9 |

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
