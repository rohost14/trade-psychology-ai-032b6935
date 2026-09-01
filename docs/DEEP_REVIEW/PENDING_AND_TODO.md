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

### The "set a daily loss limit" prompt has nowhere to appear

**Created 30 Aug 2026 by the Pattern 17 change. Deliberately not fixed.**

`session_meltdown` used to derive a limit from capital and say so — *"which is
5% of your capital. You have not set a daily loss limit yet."* That copy was the
only place a trader with capital but no declared limit was told to set one, and
it went with the fallback, because it existed to label the invented number.

Those traders now get **no meltdown alert and no prompt**.

**What must be decided:** where the prompt lives instead. The hook already
exists — `SetupNudgeCard.tsx:49` tracks `daily_loss_limit != null` — so this is
wiring and copy, not new logic.

**Why not now:** it is a frontend change outside the approved scope of the
Pattern 17 correction, and it belongs in the consolidated pending-items pass
after the pattern reviews finish rather than interrupting them.

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

### Pattern 21 `end_of_session_mis_panic` — review DEFERRED

**Reviewed 30 Aug 2026 alongside `opening_5min_trap`, which was retired. This
one was NOT, and the distinction is the point: its evidence is ABSENT, not
contrary.**

Why it survived the review:

* Its subject is **mechanically checkable**, not inferred — "did you enter MIS
  20 minutes before a forced square-off" is a fact.
* Its **exchange-aware square-off is correct work** and fixed a real defect: a
  flat 15:00 `panic_start` flagged *every* evening MCX entry as panic, because
  MCX trades to 23:30. It derives from `exchange_constants`, not a second
  hardcoded constant.
* The effect points the **right way** — late entries won 23.1% against 39.8%
  for the rest of the day.

**THE EXACT UNBLOCK CONDITION: a dataset that carries `product`.**

The detector's very first gate is `ct.product not in ("MIS","INTRADAY") →
return None`. The reference tradebook (`docs/tradebook-CY6001-FO2025-26.csv`)
has **no `product` column** — its header is
`symbol,isin,trade_date,exchange,segment,series,trade_type,auction,quantity,price,trade_id,order_id,order_execution_time,expiry_date`
— so the harness must assume all-MIS and every number is an **upper bound**. A
detector whose primary gate is invisible to the dataset cannot be judged on it.

**Live `CompletedTrade` rows DO carry `product`**, so the unblock is a replay or
measurement against production data rather than the Console export. No new
capability is needed — only data that has the column.

What the deferred review must then answer, recorded so it is not re-derived:

1. **Is the danger tier reachable?** `danger_count = 3` was never reached in 175
   sessions *even under the inflating all-MIS assumption* (0 sessions with 3+
   late entries; 2 reached 2). Same question `winning_streak_overconfidence`'s
   danger tier failed.
2. **Does the effect survive a real sample?** n = 13, permutation p = 0.185.
   Direction right, significance absent.
3. **Half the copy is contradicted by its own firings.** *"There is very little
   time for the position to work, and the exit is not yours to choose."* Median
   late hold is **2 minutes** and **9 of 13 were closed by the trader**, well
   before square-off. The first clause stands; the second does not.
4. **Both thresholds declare metrics that do not exist.**
   `end_session_mis_caution_count` and `_danger_count` declare
   `Source.HISTORY` with `late_mis_entries_p75` / `_p90`, and neither appears
   anywhere in the codebase. They sit permanently at their 2/3 fallbacks while
   reporting themselves personalised.

**Nothing about this detector — code, thresholds, copy, severity or
architecture — was modified.** It is the second detector deferred on a data gap
rather than a decision.

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

`rapid_reentry` and `opening_5min_trap` write evidence nothing trader-facing
reads. The list was four; `panic_exit` was retired 29 Aug and `early_exit` 30
Aug, and in both cases the unread evidence was *part of the case for retiring
them*. **The visibility question is closed; this
one is not.** It asks whether evidence with no reader should be WRITTEN at all,
which is a separate question about the value of the analytics disposition.

The closed rule does not depend on the answer: if we ever stop writing it, INFO
events still must not become alerts in the meantime.

## Surfaced by the money-rule independence validation — NOT actioned

**That investigation PASSED on 1 Sep 2026 and the architecture is unchanged.**
Neither item below is a code fault, and neither is a reason to modify a detector.

### 1. `trading_capital` is a single point of failure for `excess_exposure`

Measured with no money rules set:

| | `excess_exposure` firings |
|---|---|
| capital unset | **0** |
| capital ₹200,000 | **231** |

Every other detector is identical either way.

**The abstention is correct** — a percentage of capital cannot be computed
without capital, and the risk layer's standing rule is that a wrong confident
answer is worse than no answer. The consequence is what needs a decision:

> A trader who skips the capital field gets **no over-exposure protection at
> all** — not the universal 5%/10% safety band, not their own rule — silently,
> with nothing on screen saying why.

**State this precisely when it is picked up.** "Capital is required for
*exposure detection*" is true. "Capital is required for *the behavioural
engine*" is **false** — one detector of seventeen depends on it, and the
validation measured the other sixteen as unaffected.

**The product question:** should onboarding require capital, or should the UI
say what is lost by skipping it? Not a detector change either way.

### 2. `EngineContext.account_risk` has a stale docstring

It says:

> *"Detectors do NOT read this yet - no detector has been migrated."*

`revenge_trade` reads it — `loss_vs_account(prior_loss, ctx.account_risk)`. True
when written, false now.

**Effect is nil**, measured: 182 firings with an identical severity split
whether `account_risk` is None or a usable ₹200,000. The account frame can only
record `a_level = 1`, which the trade frame already reaches without capital, and
`revenge_account_loss_pct` (S1) is absent from the threshold set entirely.

**Why it is worth fixing anyway:** it is the kind of comment that stops someone
checking. This validation only found the read because a static scan contradicted
the prose.

**Fix:** correct the docstring to say `revenge_trade` consumes it for the
account frame, that the frame records a measurement and an abstention rather
than gating, and that it cannot influence severity until S1 is decided. One
comment, no behaviour.

## Surfaced by the Pattern 24 review — NOT actioned

### Multi-rule breaches are not grouped — a separate product decision

`constitution_violation` returns a LIST, and **41% of firing trades breach more
than one rule at once**:

| rules on one trade | trades | share |
|---|---|---|
| 1 | 425 | 59% |
| 2 | 185 | 26% |
| 3 | 88 | 12% |
| 4 | 21 | 3% |
| 5 | 2 | 0% |

Per-rule dedup is correct and must stay — a cooldown breach must not suppress a
later daily-loss breach, which `_pattern_dedup_key` documents. But nothing
turns "you broke three of your own rules on this trade" into one statement, and
each event is a separate `RiskAlert` row at `notification_level=4`.

**Deliberately not implemented at Pattern 24.** Grouping changes what a trader
receives, so it is a product decision about alert presentation, not a detector
fix. Recorded with the numbers so it can be decided rather than re-measured.

### `constitution_violation` is the largest alert source in the engine

**383 alerts after per-rule dedup** (a lower bound — the `_worsened` re-arm is
not modelled) across **126 of 175 sessions**, against **457 firings for every
other detector combined**. Roughly **46% of all alerts**, at the highest
notification level.

Not obviously wrong — a breach of your own declared rule *is* a breach, and the
copy is right that these are the trader's own numbers. **But it is the same
shape as the 54%-of-all-alerts figure that caused `daily_loss_limit` to be
pulled from `generate_defaults`, and it has never been asked as a product
question.** Recorded so it is asked deliberately.

## Surfaced by the Pattern 23 review — NOT actioned

**`post_loss_recovery_bet` was KEPT AS-IS on 1 Sep 2026.** Nothing below is a
defect serious enough to have changed it; all five are recorded deliberately.

### 1. No floor on the prior loss — the one substantive gap

Nothing requires the losses being "recovered" to be material. The seven firings'
total prior loss: **₹477, ₹478, ₹739, ₹1,361, ₹1,751, ₹1,990, ₹5,212** — two of
seven under ₹500, in a book where **42% of the 434 losing rounds are under ₹500**
and the median loss is ₹628.

The **size** observation stays true — a 4.0× position is a 4.0× position — but
the **recovery framing** does not fit. "Make it all back in one trade" after
₹478 describes a bet, not a recovery, and the message leads with the ₹478.

**`revenge_trade`'s `revenge_min_loss_inr = 500` is the nearest precedent and
was DELIBERATELY NOT borrowed.** Importing a sibling's constant is not deriving
one, and **7 firings cannot locate a floor**. Settling this needs more firings,
i.e. more data — not more analysis of this book.

### 2. The size baseline mixes a winner into a "post-loss" average

The loss test reads `prior[-2:]`; the size average reads `prior[-3:]`. **3 of 7
firings had a WIN as the third-from-last prior**, so "your recent average" is
partly the size of a trade that worked.

Aligning the two windows is a one-line change that **alters firing**, so it
needs its own before/after rather than being folded into a cleanup.

### 3. Neither multiplier has a `THRESHOLD_SPECS` record

`recovery_bet_caution_mul` (2.0) and `recovery_bet_danger_mul` (3.0) exist only
in `COLD_START_DEFAULTS` with an inline comment — no `Kind`, no provenance, no
maturity.

**Distinct from the earlier instances of this class: the values themselves
measure well.** The 2.0× line sits at roughly p78 of the post-loss size-ratio
distribution (median 1.20, only 24% reach 2.0×), so this is a bookkeeping gap,
not a calibration one. **Seventh known instance** of a missing or dead threshold
declaration across the review sequence.

### 4. The copy says "a loss"; the code requires two

*"A position materially larger than your average, entered after **a loss** on
the same underlying"* — the gate is `all(p < 0 for p in prior[-2:])`.

### 5. Overlap and consequence — evidence recorded, not acted on

**Unique coverage across the whole engine is zero.** All 7 firings are already
visible to something else — `same_symbol_obsession` 6/7, `revenge_trade` 5/7,
`adding_to_adverse_position` 2/7. Its contribution is the **size reading** at
`notification_level=2`, not coverage nothing else has. It IS distinct from the
other size detector: 4 of 7 fire alone against `martingale_behaviour`.

**Consequence runs opposite to the alert's implication.** Flagged trades won
**57.1%** at **+₹344** mean against −₹55 for the rest, permutation **p = 0.224**.
The copy's conditional framing — *"if this one also loses"* — is untouched by
this, and by the design of record rest-of-session P&L ranks rather than judges.
**But it cannot support the detector either**, and that is recorded in both
directions.

**If a future pass asks whether the size reading deserves its own alert, decide
it on the reading — not on these seven rows.** n = 7 means this detector is not
validated by this book; it is also not refuted.

## Surfaced by the Pattern 20 review — NOT actioned

### `/api/analytics/options-behavior` + `OptionsBehaviorCard` are dead on a timer

**A product decision, deliberately not taken as part of a detector retirement.**

All three sections of that card were fed by detectors that no longer emit:
`options_direction_confusion` and `iv_crush_behavior` were engine-v1 names the
endpoint never repointed (an earlier pass declined that on the same grounds),
and `options_premium_avg_down` was retired 30 Aug.

**It is not broken and not misleading.** Stored `RiskAlert` rows still exist and
are still true, so inside the lookback the card renders real history. Once they
age out, `has_data` is false forever and the card renders **nothing** —
`if (!data?.has_data) return null` — with `BehaviorTab` folding `onHasData` into
its own empty state. No permanently-empty surface appears; the section simply
stops existing.

**The two options:** repoint it at `premium_loss_event`, the one live options
detector — which changes what those sections mean — or archive the card and the
route together. Both are product calls. Pinned by
`test_the_options_behavior_endpoint_is_kept_for_historical_rows` so a later pass
cannot quietly repoint it.

### ~~`session_trades` is EXIT-ordered~~ — **FIXED 30 Aug**, and the real cause was bigger

Traced and closed. **The root cause was not ordering — it was the absence of any
upper bound.** `load_session_trades` filtered on `exit_time >= session_start`
with no ceiling, so it returned the whole day in both directions.

Live was accidentally safe: a trade that has not closed has no `CompletedTrade`
row, so the bound was implicit in the data. **The bulk path was not.**
`run_behavior_engine_full_session` runs after every row exists, so analysing
trade 3 of 10 handed the detectors trades 4 through 10. Measured: **1,808 of
3,616 entries — 50% — had not happened yet**, across 565 of 740 trades. The two
paths produced different alerts from the same session: `overtrading_burst` 248
against 13, `same_symbol_obsession` 111 against 49.

Fixed with `as_of` at the boundary. See `test_session_trades_ordering.py`.

**The remaining class was investigated and CLOSED 30 Aug** — see
`docs/patterns/00-shared/TEMPORAL_CONTRACT_INVESTIGATION.md`. No boundary rule
could close it (look-ahead 70 → 5 under the exit bound, and only → 3 under a
stricter entry bound), because it is not a boundary property. "Prior" is **three
relations** — OCCURRED, CONCLUDED, CONCURRENT — and the engine had one word for
all three.

`EngineContext.concluded_before_entry` now provides CONCLUDED once. The
investigation found the real defect was **not** the retired detector but
**`martingale_behaviour`, live and danger-tier: 9 of 32 firings rested on a loss
that concluded after the entry it explained**, the worst by 125 minutes.
Migrated along with `post_loss_recovery_bet` (same shape, latent);
`revenge_trade` and `rapid_reentry` moved onto the shared relation with their
firing sets provably unchanged. **32 → 26** martingale firings on the reference
book, exactly as predicted.

### CONCURRENT has no name in the engine — still open

The temporal investigation identified three relations and the engine now names
two. **CONCURRENT — overlapping lifetimes, one decision expressed as several
rows — is unnamed.** Three of the five Pattern 20 cases were straddle or spread
legs entered in the same minute and read as a sequence; `concluded_before_entry`
excludes them correctly, but only as a side effect of them not having concluded.

`strategy_group` already exists for structures and `session_trades` does not
express it. **No live detector was measured as affected**, which is why nothing
was built — a relation nothing consumes would be speculative.

### `constitution_violation`'s cooldown spells CONCLUDED as `<=`

`revenge_trade` used `<` and the shared relation is `<`. The cooldown rule still
spells its own `t.exit_time <= ct.entry_time` inline. **They disagree only at
identical timestamps** — a close and an entry in the same instant — and nothing
decides which is right. Deliberately not migrated: `constitution_violation` was
outside the approved scope, and changing `<=` to `<` there is a behaviour
question, not a refactor.

### `position_monitor_tasks` writes its own session-trades query

`position_monitor_tasks.py:755` builds the same fact with its own
`select(CompletedTrade)` instead of `session_facts.load_session_trades`. It is
**correct today** — the entry path evaluates an open position *now*, so nothing
future exists — but it is a second definition of a fact `session_facts` was
created to own, and it would not inherit a future boundary change. Recorded, not
changed.

### A third unsourced statistic in a threshold comment

*"SEBI data: traders who averaged down on losing options lost 3× more"*, with no
source anywhere in the repository. Removed with its threshold. Following
`expiry_day_overtrading` (which **shipped** its unsourced statistics to traders)
and `winning_streak_overconfidence`'s hot-hand claim. **Three instances is a
pattern, not three accidents** — worth a sweep of the remaining threshold
comments for claims that cite evidence nobody can produce.

## Surfaced by the Pattern 19 review — NOT actioned

### `BehaviorEngine._notional` now has zero callers

The last one was `winning_streak_overconfidence`, retired 30 Aug. The
`size_escalation` retirement had explicitly kept the helper *because* other
detectors read it — that premise is now false, and
`test_notional_is_now_readerless_and_kept_deliberately` pins the new fact
rather than hiding it.

**Kept rather than deleted, as a decision.** Removing a shared helper is a
judgement beyond a detector retirement, and its docstring carries the
cross-instrument comparability argument every sizing detector needed: quantity
is not comparable across instruments, rupees are. **Deleting it is one option
for the consolidated pass; reviving it for a future sizing detector is the
other.** `alert_outcome_service` has its own separate `_notional` — live and
unrelated.

### The F23 bug class is open — `is not None` on a numeric baseline

F23 was `avg_baseline is not None` passing for `0.0`, which turned a danger
gate into `current_qty >= 0` — unconditionally true. The fix was correct and
lived in `winning_streak_overconfidence` to the end, so **retiring the detector
removed the instance without closing the class.** Any `is not None` guard on a
numeric baseline elsewhere has the same defect. Not swept for; recorded.

### `danger_zone`'s pattern-driven CAUTION path is now fully unreachable

`caution_patterns` held two names. `rapid_reentry` emits `info`, which by the
closed INFO/evidence rule never becomes a `RiskAlert`, and `patterns_active` is
built from `RiskAlert` rows — so it could never reach the set. The only member
that could was retired 30 Aug.

**The set is deliberately left in place.** Pattern 13 classified the dead
`rapid_reentry` branch as a consumer/design inconsistency and **not** a bug,
precisely so it would not later be "fixed" into changing the alerting
philosophy. Deleting the pattern-driven CAUTION path is that same change by
another route. **It belongs to a danger-zone review, not to a detector
retirement**, and it is now the second detector review to arrive at this same
question.

### Orphaned comment block in `trading_defaults.py`

The *"Early exit (disposition effect / cutting winners)"* header and its two
SEBI claims survive at lines ~253-255, but the three keys beneath them went
with Pattern 18. **This is leftover from retirement commit `13755b4` — my own
change, not a pre-existing defect.**

### `uses_baseline` is a declaration nothing checks — second instance

`winning_streak_overconfidence` declared `uses_baseline=True` and read no
baseline at all; its "baseline" was an inline average over today's session.
The field has **zero readers**, so nothing broke.

This is the same class as `early_exit_winner_max_min` naming a metric nothing
produces, already recorded above. **Two instances now.** The fix is one
contract test over the spec declarations, not two corrections.

## Surfaced by the Pattern 18 review — NOT actioned

**Both were found by the `early_exit` review and deliberately left. Neither is
`early_exit`'s alone, which is why retiring it did not close them.**

### `trigger="session"` is declared and not honoured

The engine branches on `spec.trigger == "entry"` only. Everything else,
including `session`, falls through to the per-trade exit loop, so a
session-scoped finding is recomputed and re-emitted on every qualifying trade
after the condition first holds. On `early_exit` that produced 1.5 events per
firing session.

**It affects every detector that declares `trigger="session"`, so it is an
engine fix, not a pattern fix.** Either the engine honours the field or the
specs stop claiming it — but the field must not stay declared and ignored.

### `baseline_service` metrics that no threshold spec can reach

`early_exit_winner_max_min` declared `Source.HISTORY` with
`metric="winner_hold_p50"`. **`winner_hold_p50` is never produced anywhere in
the codebase** — `baseline_service` emits `avg_winner_hold_min`. So a threshold
declared PERSONAL_BASELINE sat permanently at its global fallback while
reporting itself personalised.

**This is the same class as the H1 key-name mismatch already found and fixed
once**, where two personalised values never reached their reader. That it
recurred means the declaration is unchecked: nothing asserts that a spec's
`metric` is a key some producer actually emits. **A contract test over
`THRESHOLD_SPECS` would close the class**, not just this instance.

### The hold-time asymmetry is computed and unread — a candidate analytics surface

`baseline_service` computes `avg_winner_hold_min` and `avg_loser_hold_min`
across the trader's full history with counts and confidence — 276 winners and
413 losers on the reference book, against the 3–5 per side that made the
detector noise. **Nothing reads them.**

The disposition effect is real, documented and the only observable answer to
"was that exit early". Retiring the detector removed the wrong *scope*, not the
question. Recorded as a possible analytics addition; **not proposed, and it is
half a product decision.**

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

## Surfaced by the `time_of_day_bias` retirement (Reviews 25-27)

**Reviews 25-27 are CLOSED.** `time_of_day_bias` RETIRED, `win_rate_collapse`
KEEP AS-IS, `strategy_breakdown` DEFERRED. Everything below is recorded, not
actioned.

---

# DEFERRED BY DECISION — three items, 2026-09-01

**Do not change any of these without a fresh decision.** Each is deferred for a
stated reason with the evidence behind it, not left over by accident. They are
grouped here so they are not mistaken for the incidental findings further down.

## 1. `best_hours` and `best_days` — insufficient evidence, do NOT use as behavioural signals

**Both surfaces are already removed** with the rest of the retirement. What is
deferred is any future revival: **neither may be used as a behavioural signal
until it is validated on its own.**

**They are NOT the same finding, and collapsing them would misstate the
evidence.** Each was measured separately with its own filter (`> 55%` win rate,
`n >= 5`), split across the two halves of the reference book:

| signal | full book | first half | second half | **in BOTH** | status |
|---|---|---|---|---|---|
| `best_hours` | `[14]` | `[]` | `[14]` | **NONE** | **MEASURED, UNSTABLE** |
| `best_days` | `[]` | `[]` | `[]` | **NONE** | **UNVALIDATED, NOT INVALIDATED** |

**`best_hours` — measured and unstable.** One hour, 14:00, and it appears in the
second half only, absent from the first. Chance p = 0.138 is not damning on its
own, but a signal present in one half and not the other cannot support a claim
about a trader's habits. Its n is also thin: hour 14 carries 18 trades in the
first half and 30 in the second.

**`best_days` — no evidence either way.** It fires **zero times at every slice**
of this book. That is not a finding against it; the book simply never triggers
it. Its surface was removed because it shares a methodology with signals that
were measured and contradicted, **not** because it was itself measured and found
wanting.

**Why deferred rather than decided.** The mirror-image evidence is what governs
both: for the *danger* direction the ranking does not persist at all — Spearman
rho between the two halves' hourly win-rate rankings is **+0.071** — and a "best"
list is the same ranking read from the other end. Validating either would need a
**persistence test across periods**, not merely a bigger sample: at 95%
confidence, separating a 55% hour from a 40% baseline needs roughly **n ≈ 100
trades in that hour**, against a producer gate of `n >= 5` where the interval is
**±43 points**. Choosing the required precision is a product judgement, and
nothing in this book decides it.

**Kept:** `_learn_time_patterns` still computes and stores both lists nightly, so
a future evidence pass has the data. `hourly_breakdown` and `daily_breakdown`
remain on `/time-analysis` as raw counts with **no classification attached** and
no reader today. **If a future surface renders them, the stability finding
applies again.**

## 2. `api/my_record.py`'s independent hourly signal — separate product decision

**Excluded from this pass by explicit instruction, and recorded so the resulting
inconsistency is a decision rather than an oversight.** It is a SECOND,
INDEPENDENT implementation that does not read `time_patterns` at all — it
computes from trades directly.

> *"Right now is your weakest window on NIFTY: 5 trades, 20% win rate, −₹14,270
> net."*

| | `time_patterns` path (retired) | `my_record.py` |
|---|---|---|
| timezone | IST-derived, compared to **browser-local** in the strip | **`now_ist.hour`** — correct |
| sample gate | `n >= 5`, invisible to the trader | `MIN_SAMPLE = 5`, and the count is **in the sentence** |
| delivery | **push** — alert, dashboard strip, daily report | **pull** — the trader opens My Record and asks |
| claim | *"You historically lose at 14:00"* | *"Right now is your weakest window… 5 trades"* |

**Why deferred rather than removed.** It carries **the same instability risk** —
"weakest window" is a ranking, and rankings are exactly what rho = +0.071 says do
not hold. But it is materially different in product terms on three axes at once:
the trader asked for it, the answer states its own sample, and the clock is
right. Whether a pull surface that shows its working is held to the same bar as a
push surface that does not is a product question, and it was not put.

Pinned untouched by `test_my_record_is_out_of_scope_and_untouched`, which asserts
it still never reads `time_patterns`, still uses `now_ist`, and still gates on
`MIN_SAMPLE`.

## 3. Readiness-score `warning` band — unreachable, needs a band decision

`_calculate_readiness_score`'s three bands are `ready` (≥ 80), `caution` (≥ 60)
and `warning` (below 60). With the danger-day −20 removed, **the remaining
penalties total at most 40** — `large_recent_loss` 20, `losing_streak` 15,
`expiry_day` 5 — so the floor is **exactly 60**, which is the `caution` cut.

| | before | after |
|---|---|---|
| reachable score range | 40 – 100 | **60 – 100** |
| `warning` cases in the 489,951-case sweep | 4,564 | **0** |

Every one of the 4,564 required the removed −20.

**DO NOT INVENT A REPLACEMENT FACTOR.** Substituting something to keep the band
alive would be choosing a threshold to preserve a scale, which is precisely the
move the retirement exists to stop. This is a consequence of the removal, not a
defect introduced by it.

**The open question is about the BAND, not the signal.** Either the remaining
penalties are too small for a three-band scale, or the scale should be two bands.
Both are product decisions with no evidence behind them, and neither was taken.
`Reports.tsx:192` still carries the `warning` branch and its `text-tm-loss`
colour, harmlessly. Pinned by
`test_the_warning_band_is_now_unreachable_and_that_is_recorded`, so the dead band
is a recorded fact rather than a later surprise.

---

# BLOCKING — `sl_percent_options` invents a USER RULE. Found 2026-09-01.

**Raised during the exposure-hierarchy verification, blocking that
implementation. Not fixed — it needs approval, and it is not an exposure
threshold.**

`threshold_resolution.py:527`:

```python
put("sl_percent_options", getattr(profile, "sl_percent_options", None) or 50.0,
    Source.FACT, 1.0, None)
```

`UserProfile.sl_percent_options` is **nullable** — `None` until the trader sets
it. When unset this invents **50.0** and marks it **`Source.FACT`, confidence
1.0** — the provenance reserved for something the trader declared.

**It is registered as a USER RULE, not a default.** `constitution_service`
lists it in `RULE_FIELDS`; `live_risk_state`'s own docstring calls it
*"`declared` — the exit rule the trader wrote down … `Kind.USER_RULE`"*.

**A trader who configured nothing is told they configured something.**
`position_monitor_tasks.py:952-958` emits `pattern_type="constitution_violation"`
(`notification_level=4`, the highest in the engine) with:

> **"You set your options exit at 50% of premium. NIFTY…CE is 70% down."**

Verified live in case G of `hierarchy_verification.md` — profile with nothing
declared, and the DECLARED band fires at `boundary 50.0`.

### It also shadows the universal safety layer

The two layers exist to stay separate, and `_fire_position_alert` gives the
DECLARED crossing precedence, carrying the universal one only as
`details["also_crossed"]`. Because the invented 50 sits **between** universal
caution (40) and danger (60), the fabricated "user rule" fires first and demotes
the real safety finding to a sub-field.

Measured on the reference book (closed-round final loss, a **lower bound** on
live crossings — a round ending at −70% certainly crossed 50 and 60 intraday):

| band | rounds | share of 724 long-option rounds |
|---|---|---|
| ≥ 40% — universal caution | 26 | 3.6% |
| **≥ 50% — the invented "declared" band** | **16** | **2.2%** |
| ≥ 60% — universal danger | 10 | 1.4% |
| ≥ 80% — universal critical | 4 | 0.6% |

**On all 10 rounds that reach the real 60% danger band, the invented rule
pre-empts it.**

### The two resolvers disagree, and the wrong way round

| path | provenance |
|---|---|
| profile present, nothing declared (`:527`) | **`Source.FACT`, confidence 1.0** |
| no profile at all (`:683`) | `Source.GLOBAL`, confidence 0.0, *"repo default"* |

Having a profile makes the claim **stronger**. The cold-start path is honest; the
profile path is not.

### Class, and why it matters

This is the shape Pattern 24 fixed (the wizard writing `max_position_size:
50000`), Pattern 17 fixed (`session_meltdown`'s undocumented `capital * 0.05`),
and H1 closed for the daily limit — *"an invented daily limit is no longer
described as 'yours'"*. **This key was not covered by that sweep.**

`sl_percent_futures … or 1.0` at `:526` has the **identical shape and the same
`Source.FACT`**. Nothing reads it today, so it is latent.

### Scope

**Long options only** — `build_watches` gates on `CE`/`PE` and `qty > 0`.
Futures and naked shorts are unaffected because they have no severe-loss
coverage at all.

### NOT proposed here

Whether the fix is to abstain when unset, to re-provenance it as `GLOBAL`, or to
keep 50 as an explicit universal band under a different name is a **product
decision about the severe-loss layer**, which the exposure work was told not to
touch. **The 40/60/80 thresholds are not implicated and must not move.**

# Incidental findings from the same pass — recorded, not actioned

### ~~`_calculate_readiness_score`'s danger-day factor~~ — **CLOSED 2026-09-01**

**Decided: remove the factor.** A readiness score is a trader-facing decision
signal, so the rule that retired the alert applies to it too. The penalty is
**gone, not hidden** — keeping the arithmetic while dropping only the visible
detail string was the rejected option, because an unsupported signal moving a
decision number invisibly is harder to audit than one that at least states
itself. No replacement day or time factor was substituted.

Measured over all **489,951** reachable inputs: **54,439 (11.1%) move, every one
by exactly +20**; 435,512 (88.9%) identical; the surviving factors match case for
case. Bands: `caution → ready` 41,121 · `ready → ready` 8,754 ·
`warning → caution` 4,564. A trader affected only by this factor goes 80 → 100,
**both `ready`** — the cut is `>= 80`. Its one consequence is item 3 above.

### `POST /profile/detect-style` clobbers `detected_patterns`

Three writers touch the JSONB column and they do not agree on whether to merge.
`behavioral_baseline_service:143` **merges**; `ai_personalization_service`
**replaces** the whole dict; `api/profile.py:637` **replaces** it with an
incompatible three-key dict, destroying `time_patterns` **and** `baseline`. The
next nightly run would restore only the first. **It has no callers** — grep
across `src/` returns nothing — so it is latent, the same class as
`pre-trade-check`. **No test asserts which keys `detected_patterns` must
contain**, and that gap is what let a grep mislead the first review into calling
a live detector dead.

### `ai_personalization_service` computes its own `baseline` alongside the real one

It replaces rather than merges, so it will overwrite a fresher baseline from
`behavioral_baseline_service` if it runs later. Both derive it identically
today, so this is redundancy rather than a bug — and fragile if either changes.

### `PredictiveContextStrip` reads `chk.alert.title`, which the API never sends

`get_predictive_alert` returns `alerts[0]`, and no alert dict it builds has a
`title` key — so the strip's `label` is `undefined` for the server-side
predictive check. Pre-existing, unrelated to the retirement, found while tracing
its consumers. One-line fix in either direction; not taken here.

### Sunday, n = 14, in the day-of-week breakdown

Indian equity/F&O markets do not trade Sundays. Either these are a special
session or there is a timestamp defect. **Not investigated.**

## Closed on this pass — recorded so they are not re-raised

| # | verdict |
|---|---|
| **F21** | **Not a bug.** `capital_mismatch` is a housekeeping nudge, not a behaviour detector, and `death_spiral` counts behavioural domains. Its absence from `_ALIAS_NATURE` is correct and the consumer handles it safely. Pinned by a test. |
| **F24** | **Not a bug.** `adding_to_adverse_position` is the one `trigger="entry"` detector; the exit loop skips such specs deliberately and the entry-batch flush dispatches it. It runs. |

Fixed 29 Aug: **F1, F10, F18, F19, F22, F23** (and earlier **F3, F7, F8, F9,
F11, F15, F16, F17**). See `RISK_INFRA_PLAN.md`.
