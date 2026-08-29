# Pending and To-Do

**29 Aug 2026. Bookkeeping only — no audit, no code changes.**

Every open item, with the **actual reason** it is deferred rather than a label.
Nothing here is resolved and nothing here is permanently deferred. Each entry
records what must be **decided** or **tested**, so the item can be picked up
without re-deriving why it was left.

Three states are used, and they are not interchangeable:

- **PENDING DECISION** — the code is not obviously wrong. Something must be
  decided first, and guessing would encode a product choice as a bug fix.
- **PENDING VALIDATION** — decided and implemented. Needs a measurement or a
  live observation that is not currently obtainable.
- **UNSUPPORTED** — the data cannot answer it. Not a to-do; the system must
  abstain, and the entry says what would change that.

---

## PENDING DECISION

### F2 — absence is rendered as a behavioural claim

An empty `exit_order_types` produces *"No stop-loss order detected"*, and a
`num_entries=1` stub produces *"opened in a single fill"*. Both state a
**negative finding** where the honest answer is that nothing was seen.

**What must be decided:** what a detector says when the data it needs is
unavailable. `abstained()` and `Insufficiency` already exist and are used by 6
of 23 detectors, so the mechanism is there; the open question is per-detector —
does an unseen stop-loss become silence, a lower-confidence note, or a
different message entirely?

**Why not now:** F1 landed on 29 Aug and exit order types now actually arrive on
the live path. The population of genuinely-missing cases has therefore just
changed, and deciding the abstention wording against the old population would
be deciding it against data that no longer exists. **Look at it after F1 has run
live for a while.**

---

### F4 — direction-aware denominator

`no_stoploss` references `direction` **zero times**, so its
`entry_price × qty` denominator is premium *paid* for a buyer and premium
*received* for a writer — two different quantities under one name.

**F13 has been REMOVED from this list.** It was filed as *"`opening_5min_trap`
admits futures but computes `loss_pct` only for CE/PE, so its large-loss branch
is unreachable"*. The Pattern 12 review read the code: the `else` branch
computes `capital_at_risk` for futures via `estimate_capital_at_risk`, and
`loss_pct` is computed **after** the branch, for both. Futures reach the loss
branch. The item was marked *reported* rather than verified in the consolidated
report and should never have been carried forward. **Not a bug.**

**What must be decided:** the correct direction-aware trading semantics for a
*loss-relative* denominator. This is **not** the capital question F17 settled.
F17 answered "what did the account commit"; this asks "what is this loss a
percentage **of**" — for a short option, is a doubling of premium −100% of the
credit received, or a percentage of margin, or something else? The two framings
give different numbers and different alerts.

**Why not now:** picking one silently changes what every `no_stoploss` and
`opening_5min_trap` alert claims. It is a product decision about what the trader
is told, not a defect with one correct answer.

---

### F5 and F6 — hedge and structure semantics

F5: the futures-hedge branch reads the option leg's **type** and never its
**direction**, so a FUT LONG + PE SHORT is labelled `futures_hedge_bullish` —
a risk-**adding** structure classified as a hedge.
F6: `MULTI_LEG_UNKNOWN` grants the **full** hedge suppression that was written
for recognised structures. A cluster we could not classify silences five
detectors.

**What must be decided:** a defined hedge/structure semantic — what ratio, what
degree of simultaneity, and what an *unrecognised* cluster earns — **before**
any classification or suppression changes.

**Why not now:** the margin work removed the urgency without removing the
question. Scanning legs jointly reproduces the capital consequence of a hedge to
−0.3% **with no hedge rule in the model at all**, so *capital* no longer needs
this answered. Structure naming is still needed for **messaging** and for
suppression, and both are product decisions. Changing suppression changes which
alerts survive.

---

### F12 — `duration_minutes` has two meanings in one column

The live ledger writes wall-clock minutes; the batch FIFO writes
`market_minutes`. An overnight hold is ~1,440 from one writer and ~375 from the
other, and a recompute can overwrite the value written by the first.

**What must be decided:** the canonical meaning of `duration_minutes` — wall
clock or market minutes — and then whether existing rows are migrated or the
column is split in two.

**Why not now:** every hold-time gate in the engine divides by this. Choosing
market minutes is defensible and choosing wall clock is defensible; picking one
without deciding is how the column came to hold both in the first place.

---

### F14 — "opened today" describes a close-scoped count

`daily_overtrading`'s message says *"positions opened today"* about a figure
that `session_facts` scopes on `exit_time` only.

**What must be decided:** the **D5** session-scope question — "closed today" is
right for streaks and P&L, "opened today" is right for counting decisions, and
both facts are needed. That is two facts, not one.

**Why not now:** the copy is a one-line change, but writing it before D5 means
writing it twice. **Blocked on D5, not on effort.**

---

### F20 — `overexposure` consumes other detectors' output

It queries `BehaviorEvent` for `revenge_trade`, `martingale_behaviour` and
`post_loss_recovery_bet` at danger+ and promotes its own severity. The registry
states the rule verbatim: *"Dependency rule (A.10): no detector may consume
another detector's output."*

**What must be decided:** whether this cross-detector dependency is
**intentional** — it is documented in the code as the "Emotional multiplier
(doc 4 P32)", i.e. a deliberate product feature — or whether it **violates the
architecture contract** and the code must change.

**Why not now:** it is a conflict between two things we wrote, not a bug with
one correct answer. Exactly one of them has to give: either A.10 gains a stated
exception for presentation-tier severity, or the multiplier is removed.
Removing it changes severity, which no cleanup pass may do unasked.

---

## PENDING VALIDATION

### Patterns 3, 7 and 8 — remeasurement after the instrument-classification fixes

F15 and F16 changed how **17 symbols across 38 fills (1.7%)** of the reference
book are classified. Three closed patterns had their inputs genuinely move:

| pattern | why it must be remeasured |
|---|---|
| **8** `premium_loss_event` | guards `instrument_type in ("CE","PE")` and those fills were typed `EQ`, so it **could not see them at all**. A coverage change cannot be reasoned about from the old measurement |
| **3** `same_symbol_obsession` | groups on `underlying`, which for those symbols was the entire tradingsymbol — two contracts on the same stock could never group. The correction can only **increase** firing |
| **7** `fomo_entry` | counts distinct underlyings, and every unreadable contract counted as its own — the input was wrong in a known direction |

**What must be tested:** one replay across the 189-session book, after the
fixes. **One replay covers all three** — per the pace rule, never one per
pattern, and never a second replay to explain a composite.

**Not a reopening.** Their prior decisions stand until a measurement says
otherwise. Patterns 1, 2 and `overtrading_burst` moved for a small subset and
are worth folding into the same pass only because the replay is already running.
**All five retirements (4, 6, 9, 10, 11) stand** — each rests on a chance rate,
an arithmetic identity, a shuffle null or an outcome comparison, none of which
instrument typing can reach.

### Pattern 16 `excess_exposure` — review DEFERRED

**Deferred 29 Aug 2026, before review, by decision.** Not reviewed, not
modified, not deleted.

**Why:** F17 changed its capital input two days earlier. It now takes the
capital requirement from the canonical risk layer, and that layer **abstains on
futures and short options** until a broker margin figure exists. Live broker
margin capture is implemented but has never run — every number in its 21 tests
is a fixture.

So the detector is currently silent on exactly the instruments where its
question matters most. **Reviewing it now would measure a temporarily incomplete
detector** and reach a verdict about a state it is not going to stay in.

**What must happen first:** the live broker-margin validation immediately below.
Once a real `OPEN` fill has produced a `position_margin_observations` row and
that figure has reached `excess_exposure` as `MarginSource.BROKER`, the detector
is in its intended state and can be judged.

**Nothing is assumed about the outcome.** The original audit recorded it as
*"IMPLEMENTED, NOT VERIFIED — zero test mentions AND excluded from replay"*,
which is a separate problem from the F17 change and is still open.

### Live Kite broker-margin validation

Migration 081 is **applied**. The capture path, persistence, resolution and
consumption are implemented and covered by 21 in-process tests using fakes.

**What must be tested:** a real `OPEN` fill on a live account during market
hours, producing an actual `position_margin_observations` row, and confirming
the captured figure reaches `excess_exposure` / `max_trade_risk` as
`MarginSource.BROKER`.

**Why not now:** requires an open market and a real position. Nothing has been
captured from Kite yet — every number in the tests is a fixture.

**Until then**, capital-relative detectors abstain on futures and short options.
That is correct behaviour, not a regression, but it means those two rules are
currently silent for a futures or option-selling account.

### Kite `/margins/orders` vs the public SPAN calculator

The model was validated against Zerodha's public calculator and against four
real Kite figures read manually. The two endpoints answer the same question but
**agreement between them has never been tested directly.** Needs a live token.

---

## UNSUPPORTED — the system must abstain

Not to-do items. Each says what would change it.

| item | what would change it |
|---|---|
| **resting stop-loss orders** (Pattern 12's premise) | routing `sync_orders_to_db` into the live path and having a detector read the `orders` table. Kite provides the data; our pipeline discards it |
| **MCX / CDS capital requirement** | MCX's own scan ranges and exposure rates. mcxindia.com returns HTTP 403 to automation, so a browser download or member access is needed. **NSE's 9.3% / 14.2% floors are equity-derivative parameters and must never be applied to bullion** |
| **BFO margin** | a sourced BSE expiry rule and ICCL's own SPAN parameters |
| **short equity denominator** | a decision on what capital means for a short that posts ~20% margin against unbounded loss |
| **MTF funded fraction** | broker data Kite does not expose. MTF stays identified and its capital stays unavailable — **never a guessed leverage ratio** |
| **futures + long option** | the exchange charges **above the combination's arithmetic maximum loss**, so it withholds part of the hedge credit by a rule not present in anything published we have read. The model abstains |
| **multi-expiry structures** | the inter-month spread charge needs composite delta per month. Measured **29.6% low** without it, so the model abstains |
| **the +5–7% short-option residual** | cause not established. Ruled out: scan range, call/put symmetry, skew, look-ahead, exposure. Remaining suspect is repricing under the volatility shock. **No fudge factor may be introduced to close it** |
| cross-underlying hedging · sector exposure · order intent · automated vs manual · simultaneous leg holding | no correlation, sector, intent or timestamp-overlap data exists |

---

## Surfaced by the Pattern 13 review — NOT actioned

### ~~`danger_zone` INFO visibility~~ — **CLOSED 29 Aug 2026**

Decided, not pending. See
[`INFO_EVIDENCE_VISIBILITY.md`](INFO_EVIDENCE_VISIBILITY.md).

INFO patterns are evidence and analytics only. They must not create `RiskAlert`
rows, must not influence `danger_zone`, severity escalation or any trader-facing
alert, and the `rapid_reentry` CAUTION path must **not** be activated. Promoting
an INFO pattern to a trader-facing alert is an explicit future product decision,
never a bug fix.

Enforced by `backend/tests/test_info_evidence_visibility.py` — 12 tests. A change
that lets an INFO event reach `RiskAlert`, the danger zone or a notification
channel now fails the suite.

### Analytics-disposition evidence with no reader — still open

`rapid_reentry`, `panic_exit`, `early_exit` and `opening_5min_trap` write
evidence nothing trader-facing reads. **The visibility question is closed; this
one is not.** It asks whether evidence with no reader should be WRITTEN at all,
which is a separate question about the value of the analytics disposition.

The closed rule does not depend on the answer: if we ever stop writing it, INFO
events still must not become alerts in the meantime.

## Surfaced by the Pattern 12 review — NOT actioned

### `panic_exit` carries the identical unverifiable claim

Its message ends *"— no stop-loss order, quick manual exit."* and its registry
copy reads *"A quick manual close at a loss with no stop-loss order on record."*
Both are derived from the same `exit_types & _STOP_ORDER_TYPES` test on the exit
fill, so both assert the absence of something never looked at, and both were
structurally unknowable in production until F1.

**Deliberately not fixed with Pattern 12** — `panic_exit` is source-list #6 and
an unrelated, unreviewed pattern. It is recorded here so the defect is not lost.
It should be handled either in its own review or as an explicitly approved
copy-only change.

### Resting order book — RESEARCH FURTHER

The only route that would upgrade `no_stoploss` from a factual loss/exit signal
to a genuine *"a stop was available and was not used"* behavioural signal. Kite
returns the full day order book including cancelled and rejected orders, and our
`Order` model already stores `order_type`, `trigger_price`, `status` and
`pending_quantity`. What is missing is plumbing: `sync_orders_to_db` runs only
from two manual endpoints, the real-time path filters to `COMPLETE`, and no
detector reads the `orders` table. Kite's order book is also same-day, so
nothing can be backfilled.

## Closed on this pass — recorded so they are not re-raised

| # | verdict |
|---|---|
| **F21** | **Not a bug.** `capital_mismatch` is a housekeeping nudge, not a behaviour detector, and `death_spiral` counts behavioural domains. Its absence from `_ALIAS_NATURE` is correct and the consumer handles it safely. Pinned by a test. |
| **F24** | **Not a bug.** `adding_to_adverse_position` is the one `trigger="entry"` detector; the exit loop skips such specs deliberately and the entry-batch flush dispatches it. It runs. |

Fixed 29 Aug: **F1, F10, F18, F19, F22, F23** (and earlier **F3, F7, F8, F9,
F11, F15, F16, F17**). See `RISK_INFRA_PLAN.md`.
