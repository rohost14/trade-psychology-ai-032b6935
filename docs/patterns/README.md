# Behavioural patterns — reviews, contracts and replay evidence

Everything about the pattern-by-pattern review lives here, one folder per
pattern, numbered in review order.

## Status

| # | pattern | status | replay (203 sessions) |
|---|---|---|---|
| [00](00-shared/) | *shared* — the 33-pattern baseline, the martingale/adding distinction, the replay close-out | — | **578 alerts / 203 sessions** |
| [01](01-martingale_behaviour/) | `martingale_behaviour` | **COMPLETE** | 39 alerts / 36 days |
| [02](02-adding_to_adverse_position/) | `adding_to_adverse_position` | **COMPLETE** | 99 / 56 |
| [03](03-same_symbol_obsession/) | `same_symbol_obsession` | **COMPLETE** | 22 / 21 |
| [99](99-revenge_trade-FROZEN/) | `revenge_trade` | **FROZEN** by decision | 7 / 7 |
| [04](04-consecutive_loss_streak/) | `consecutive_loss_streak` | **REVIEWED — awaiting approval** | 78 / 56 |
| — | `overtrading_burst` + `daily_overtrading` | next | 12 / 10 + 52 / 49 |

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
