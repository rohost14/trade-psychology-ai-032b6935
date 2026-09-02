# Pending and To-Do

**Opened 29 Aug 2026. Bookkeeping only — no audit, no code changes.**

**Last pass 2 Sep 2026, after the pattern review sequence closed.** That pass
added the residue of four reviews that had never been carried across (5, 8, 17
and §27 `strategy_breakdown`), promoted three recurring findings to
**CROSS-CUTTING CLASSES**, and corrected five entries that had gone stale —
`sl_percent_options` (fixed), Pattern 16 `excess_exposure` (retired, not
validated), the `trading_capital` single point of failure (restated against a
detector that still exists), the `panic_exit` claim (moot), and two detector
counts. **Stale entries are struck through and kept, never deleted** — a
register that quietly drops what it got wrong cannot be trusted about what it
still holds.

**Third pass 2 Sep 2026, after `c107300`:** F6 and F20 are **CLOSED** — see
their entries. B1 closes with them. One new item was opened by the work:
`is_spread` is a second presence-only suppression that F6 did not reach.

**Second pass 2 Sep 2026, after `5844381`:** F5 moved to FIXED and separated
from F6, which stays open and is now sharper — see that entry. B1/B2/B3 closures
are at the foot of the file. The `STRUCTURE_GAP_SECONDS` question was measured
and the change **rejected on its evidence**; what remains is a shape-aware
grouping investigation, recorded as an open question and not as a solution.

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

## What this file owns, and where the rest lives

**Updated 2 Sep 2026 after the pattern review sequence closed.** This file owns
the **behavioural engine and pattern-review** register: detector verdicts still
open, residue each review recorded rather than actioned, and the cross-cutting
classes those reviews exposed. It is deliberately **not** the whole-project
backlog, and nothing here is copied from another file.

| what | lives in | not here because |
|---|---|---|
| engine/infra defects, dead API surfaces, migration tracking, dead functions, L3 remnants, parked threshold decisions, unverified claims | `docs/ENGINE_BACKLOG.md` §1-§6 | that file already carries them with its own evidence-of-verification rule |
| Zerodha approval, Gate 3, MD account, business/legal, launch infra, mobile, monetisation | `docs/PENDING.md` | user/Zerodha/business actions, zero code-blocking |
| design-system debt | `docs/DESIGN_MIGRATION.md` | disposable; delete when its status table is green |
| per-pattern evidence, contracts and current behaviour | `docs/patterns/<n>-<name>/` | the review and the STATUS file are the primary record; this file carries only what was left **open** |
| the live per-pattern verdict tracker | `docs/patterns/00-shared/BEHAVIOURAL_PATTERNS.md` → REVIEW STATUS | one row per pattern; the table below is the subset still open |

**Standing caveat on everything below** (`ENGINE_BACKLOG.md` §7): every
calibration in this register rests on **one trader's tradebook**. A second book
from someone who trades differently is worth more than another year from the
same person.

---

## OPEN DETECTOR QUEUE — 7, none reviewable today

**The pattern review sequence is COMPLETE.** Every pattern has a verdict; there
is no next review. What remains is open on a **data gap or a decision**, not on
time — so starting one means reviewing a detector whose evidence is already
known to be missing. Verified against `detector_registry` on 2 Sep 2026:
**15 detectors, 19 pattern types, 4 aliases.**

| # | detector | state | the exact unblock |
|---|---|---|---|
| Q1 | `overtrading_burst` | **DEFERRED** | more book. 12 alerts / 10 sessions and it **never fired alone**; n cannot move a threshold in either direction, and being rare is not a reason to delete something |
| Q2 | `end_of_session_mis_panic` | **DEFERRED — data gap** | a dataset carrying **`product`**, its first gate. See the full entry under PENDING VALIDATION, which already records the four questions the deferred review must answer |
| Q3 | `strategy_breakdown` | **DEFERRED — data gap + an unasked decision** | sessions where its two conditions disagree, **and** a decision about whether an `info`/`analytics` detector may ever reach a trader. See §27 below — the second half was never recorded |
| Q4 | `revenge_trade` | **FROZEN by decision** | new data only. No new threshold, no episode rule, no score, no replacement, no global confidence gate. `docs/research/REVENGE_FINAL_EVIDENCE_REVIEW.md` |
| Q5 | `holding_loser` | **RESEARCH FURTHER** | duration is measurable; the predicate is not. `28-position-monitor/review.md` |
| Q6 | `overexposure` | **MODIFY, blocked** | live broker-margin validation (below). Its quantity is wrong on arithmetic — 100% of futures — not on the price substitution |
| Q7 | `capital_mismatch` | **housekeeping, routed here** | excluded from the review group by decision: it never reads a position, trade, order, fill or P&L. It is a **precondition for the exposure detectors' correctness** — they divide by `trading_capital` and it asks whether that denominator is real. Pinned by `test_f21_capital_mismatch_is_excluded_from_death_spiral_on_purpose` |

---

## PENDING DECISION

### F2 — absence is rendered as a behavioural claim

An empty `exit_order_types` produces *"No stop-loss order detected"*, and a
`num_entries=1` stub produces *"opened in a single fill"*. Both state a
**negative finding** where the honest answer is that nothing was seen.

**What must be decided:** what a detector says when the data it needs is
unavailable. `abstained()` and `Insufficiency` already exist and are used by 6
of what were then 23 detectors (**15 today**), so the mechanism is there; the open question is per-detector —
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

### ~~F5~~ **FIXED** · ~~F6~~ **CLOSED 2026-09-02 (`c107300`)** — hedge and structure semantics

**These were filed as one item and have separated.** F5 was a wrong *reading* —
a defect with one correct answer. F6 is a product decision about what a
classification EARNS. Fixing the first does not answer the second, and the
sequencing recorded in `PHASE0_CLASSIFICATION.md:125-129` held: *"F5 before F6:
F5 corrects the classification, F6 then decides what an unknown classification
earns."*

**F5 — FIXED (`5844381`).** The futures-hedge branch now requires the option leg
to be `LONG`. `FUT LONG + PE SHORT` and `FUT SHORT + CE SHORT` no longer carry a
protective-hedge label and fall to `MULTI_LEG_UNKNOWN`. No new strategy type was
introduced — naming a shape we have not decided should receive any particular
treatment would build a taxonomy to preserve a classification. The other six
FUT+option combinations are unchanged and pinned by tests.

> **F6 CLOSED 2026-09-02 (`c107300`).** `_structure_suppresses` replaces the
> presence test: **only a RECOGNISED structure may suppress, and the set is
> three detectors, not five.** `MULTI_LEG_UNKNOWN` earns nothing; an absent,
> empty or unreadable `strategy_type` fails closed. `revenge_trade` and
> `no_stoploss` were removed from the set entirely. Measured ON vs OFF over the
> reference book: **197 -> 201 alerts, +4, all `revenge_trade`**, every other
> detector unchanged, P&L and trade count identical. Pinned by
> `tests/test_strategy_suppression.py` (40 tests).
>
> **One thing did NOT close, and it is recorded as its own item below:**
> `martingale_behaviour` is still silent inside a `MULTI_LEG_UNKNOWN` group,
> through a second presence-only mechanism this change did not touch.
>
> The original finding is kept below, because the reasoning is what justifies
> the shape of the fix.

**F6 — the finding, as recorded before the fix.** The chain, all three links verified in code:

1. A risk-adding `FUT LONG + PE SHORT` now classifies as `MULTI_LEG_UNKNOWN`
   — correct, and it is what F5's fix produces.
2. `strategy_detector.detect_and_save` builds the `StrategyGroup`
   **unconditionally**, whatever the classification.
3. `behavior_engine.py:822` tests `if ctx.strategy_group and …` — **presence,
   never type** — so `MULTI_LEG_UNKNOWN` earns exactly the same suppression as
   a recognised structure: `revenge_trade`, `martingale_behaviour`,
   `rapid_reentry`, `no_stoploss` and `post_loss_recovery_bet` all go quiet.

**So the structure has lost the wrong NAME and kept the wrong SILENCE.**
Classification correctness is fixed; suppression semantics are not, and the two
were never the same question.

**DECIDED 2026-09-02: an unrecognised cluster earns NOTHING.** Both readings
were defensible in the abstract; the book decided it. 70% of the UNKNOWN
groups are the same option type, all bought, at adjacent strikes — a second
helping of one directional view, not a structure — so granting them
hedge-grade silence suppressed exactly the behaviour the detectors exist to
show. The rule adopted is narrower than "suppress recognised structures":
suppression is a claim that **the detector's subject does not exist**, which
is why only three of the five qualified.

**Also still open, unchanged by the fix:** the hedge/structure semantic itself
— what ratio and what degree of simultaneity constitute a hedge. The classifier
still never reads quantity, so a 1×2 ratio spread classifies as a defined-risk
vertical. This is D1 in `PHASE0_CLASSIFICATION.md`, deliberately out of scope of
a correctness fix, and the margin work removed its urgency without removing it:
scanning legs jointly reproduces the capital consequence of a hedge to −0.3%
with no hedge rule in the model at all, so *capital* no longer needs it
answered. **Structure naming is still needed for messaging and for
suppression.**

---

### Shape-aware grouping — a separate investigation, not a chosen solution

**Raised 2026-09-02 while verifying B1. Recorded because measuring it produced a
result that argues AGAINST the obvious change.**

Two grouping windows disagree about "entered together":
`detect_and_save` uses `ENTRY_WINDOW_MINUTES = 15`; `cluster_legs` uses
`STRUCTURE_GAP_SECONDS = 30`. The reference book's one real futures hedge —
2025-12-31 `SOLARINDS26JAN12000PE` then `SOLARINDS26JANFUT`, **38 s apart** —
falls between them: grouped by the first path, not clustered by the second.

Raising the global window was measured over the whole book and **it does not
cleanly capture hedges** — it trades a false negative for a false positive:

| gap | sessions whose count changes | what changes |
|---|---|---|
| 30 → **60 s** | **2** | 2025-12-31, the real hedge, +38 s — **captured** ✓ · 2025-09-08 `24800PE` → `24900CE`, **+35 s** — two directional entries on a day of 11 that cycles the same two strikes, collapsed into one "strangle" ✗ |
| 30 → **120 s** | **4** | the same two, plus INDHOTEL CE→PE +80 s and NIFTY CE→PE +104 s — both directional pairs ✗ |

**This reproduces the reason the constant is 30 and not 120.** Its own comment
records the earlier finding: *"buying a call and then a put a minute later
classifies as a straddle and collapsed to one 'disciplined decision', which is
the opposite of what that behaviour is."*

**DECISION TAKEN: leave `STRUCTURE_GAP_SECONDS` at 30.** Not deferred for want
of effort — measured, and the change was rejected on its own evidence.

**What is open** is the question underneath: a FUT+option hedge is legged
differently from an options structure, so one global seconds-window cannot serve
both. A **shape-aware** grouping rule might, and that is what needs
investigating. **It is not a chosen solution and nothing about it is designed
yet** — recording the option is not adopting it. Any such rule changes
`count_structures`, so it changes what the overtrading detectors see and must be
measured before, not after.

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

### ~~F20~~ **CLOSED 2026-09-02 (`c107300`)** — `overexposure` consumed other detectors' output

> **Removed, not filtered.** The emotional multiplier is gone; `overexposure`'s
> severity is now whatever its own ladder computed. Pinned by
> `test_the_emotional_size_bump_is_gone_and_must_not_return` and by two source
> assertions in `tests/test_strategy_suppression.py`. Zero effect on the
> reference replay — the entry path it lives on is not exercised there.
>
> **What decided it was not A.10 on its own.** The query filtered on detector
> and severity and **nothing else** — it never excluded SUPPRESSED events, and
> suppression is notification-only, so those rows exist. A `revenge_trade`
> silenced by a strategy group therefore sent the trader **no alert of its own
> and still made a different alert critical**. Not told about the finding, told
> about an unrelated breach more loudly because of it. Adding *"and not
> suppressed"* would have been a third patch on a dependency the architecture
> forbids outright, so the dependency went instead.

**The finding, as recorded before the fix.** It queried `BehaviorEvent` for
`revenge_trade`, `martingale_behaviour` and `post_loss_recovery_bet` at danger+
and promoted its own severity. The registry states the rule verbatim:
*"Dependency rule (A.10): no detector may consume another detector's output."*

**What had to be decided:** whether this cross-detector dependency was
**intentional** — it was documented in the code as the "Emotional multiplier
(doc 4 P32)", i.e. a deliberate product feature — or whether it **violated the
architecture contract**.

---

### `is_spread` is a second presence-only suppression — OPEN, found closing F6

**Found 2026-09-02 while verifying F6, and it is why `martingale_behaviour` did
not move in the ON/OFF replay.**

F6 fixed the *notification* suppression. A **second, independent** mechanism
reads the same field the same way:

```
behavior_engine.py   is_spread = ctx.strategy_group is not None   -> risk_basis(...)
```

`risk_basis` then reports the denominator incomparable for a "spread", and the
detector **abstains before suppression is ever consulted**. It is presence-only,
exactly as F6 was, so `MULTI_LEG_UNKNOWN` silences the detector through this
path even now.

**Measured directly** (`_detect_martingale_behaviour`, same inputs, varying only
the group):

| `strategy_group` | F6 suppresses? | detector result |
|---|---|---|
| none | no | **fires** |
| `MULTI_LEG_UNKNOWN` | **no** (fixed) | **still abstains** |
| `iron_condor` | yes | abstains |

Three call sites: `revenge_trade`, `adding_to_adverse_position`,
`martingale_behaviour`. Only martingale abstains outright — for the other two it
narrows one frame.

**Why it was not fixed with F6:** it is marked `# F7` in the code and it is a
*denominator comparability* question, not a notification one. Changing it
changes what a detector measures, which is detector semantics and was out of
scope. `post_loss_recovery_bet` has no such path — its zero in the replay is
genuine.

**What must be decided:** whether a spread's denominator is incomparable
because the legs are *grouped*, or because the structure is *recognised* — the
same question F6 just answered for suppression, asked about risk basis.

---

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

### ~~Pattern 16 `excess_exposure` — review DEFERRED~~ — **RETIRED 2026-09-01**

> **SUPERSEDED, and not by the validation this entry was waiting for.** The
> detector was **retired** with the exposure hierarchy (`0602aa8`) on grounds
> that hold at any margin number, so the deferral below was lifted from a
> different direction than it anticipated.
>
> **No universal exposure threshold survives and none replaced its 5/10.** A
> trader who DECLARED 40% was told DANGER at 35% — inside their own rule —
> because `safety_bounds` clamps a declared value so it may only tighten, and
> the alert could not tell 35% from 45%. Outcome evidence never supported it:
> per round 0-5% won 40.2%, 5-10% 37.4%, 10-15% 43.1%, 15-25% 43.9% — no trend;
> only 25%+ separated, at n=10 with 81% of that bucket from ONE position. At ₹1L
> the removal drops **520 alerts on 724 rounds** that a trader declaring
> NOTHING used to receive. Single-position exposure is now solely a breach of
> the trader's own declared limit via `constitution_violation`'s
> `max_trade_risk`. Evidence: `docs/patterns/28-position-monitor/`.
>
> **The live broker-margin validation immediately below is still open** — it now
> unblocks `overexposure` (Q6) and `max_trade_risk`, not this detector.

**Original entry, kept as the record. Deferred 29 Aug 2026, before review, by
decision.** Not reviewed, not modified, not deleted at that time.

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

## Surfaced by the Pattern 5 review — NOT actioned. **Filed 2 Sep 2026.**

**Seven limitations were recorded in `05-overtrading/STATUS.md` under
"Limitations, recorded not closed" and none of them reached this register.**
`daily_overtrading` was changed on 26 Aug (it now fires on the declared limit
only); `overtrading_burst` was deferred and untouched. These are the leftovers
of that change, not reasons to revisit it.

| # | limitation | why it is still open |
|---|---|---|
| 5.1 | **Three surfaces read the declared daily trade limit** — `constitution_violation` (exit, engine), `position_monitor_tasks:1431` (entry, fires `constitution_violation` with rule `daily_trade_limit`), and now `daily_overtrading` | **No consolidation family covers them.** Two detectors now say the same sentence about the same declared number and the existing suppression picks the constitution one. This is the family decision arriving early; nothing in the Pattern 5 change pre-empted it |
| 5.2 | **They do not count the same way.** `constitution_violation` counts **legs** (`len(ctx.session_trades) + 1`); `daily_overtrading` counts **structures** (`count_structures`) | Identical on this book — it collapses only **8 legs of 912** — but they **will disagree for a multi-leg trader against the same declared number**. The book cannot show the disagreement, which is why it was recorded rather than fixed |
| 5.3 | `daily_trade_danger = 12` still exists in `trading_defaults.py` and is still resolved | It has **no detector reader** now. Not removed on purpose: `api/constitution.py` and `api/behavioral.py` surface it |
| 5.4 | `daily_trade_limit` (p75-derived) still exists and is still resolved | Read by `/api/risk`, `/api/behavioral`, the Rules page and `rule_suggestion_service`. Only the **alerting** path stopped using it |
| 5.5 | **The SEBI attribution is unsourced** — `daily_trade_limit 7 SEBI FY2023 (>6/day → 94% loss probability)` | **No source document for it exists in the repo.** Out of scope for that change; still wrong to leave. See the cross-cutting recount below |
| 5.6 | **The burst check's silent fall-through** — ≥ caution, session flat or up, no losers — produces **no event and no record** | A suppression nobody can audit. Distinct from an abstention, which at least records itself |
| 5.7 | **No replay re-run.** The expected delta was exactly −52 `daily_overtrading` alerts on a `--no-rules` book and nothing else | **That is an expectation, not a measurement.** PENDING VALIDATION in substance; recorded here with its pattern |

**5.2 is the one with teeth.** Two detectors, one declared number, two counting
units — and the trader sees one number in their rules.

## Surfaced by the Pattern 8 review — NOT actioned. **Filed 2 Sep 2026.**

`premium_loss_event` was **KEEP AS-IS**, then rebuilt at v3.0.0 as a real-time
risk-state detector on the tick path. Seven limitations were recorded in
`08-premium_loss_event/STATUS.md`; **one reached this register** (the resting
order book, under Pattern 12). The other six are below.

| # | limitation | state |
|---|---|---|
| 8.1 | **No ticker means no live premium alerts.** The 60-second beat is gone, so the tick stream is the only source | Same exposure that already exists for live prices, and the ticker has reconnect logic — but it is a **new dependency for this pattern and is not covered by a test** |
| 8.2 | **No test drives a real Zerodha socket.** Frames are synthesised to the exact wire layout `_handle_binary` parses | The socket itself is never exercised. PENDING VALIDATION, and it needs a live session |
| 8.3 | `sl_percent_futures` had the same unused-field problem | **Partly closed 2 Sep** — it was removed as a user input and no longer resolves to an invented `1.0` as `Source.FACT`. Nothing reads it; whether the field itself should exist is untouched |
| 8.4 | **Pattern 8 and Pattern 12 are 92% duplicated on the same denominator with conflicting severities** | The resting-order-book half of this is filed (Pattern 12, RESEARCH FURTHER). **The duplication itself is not.** Until live stop-loss state exists, Pattern 8 cannot carry protection as context and the two overlap on nearly everything they see |
| 8.5 | **Averaging down still quietens it** — `loss_pct` is measured against `avg_entry_price`, so an add lowers the percentage | The engine is not blind: `adding_to_adverse_position` fires on the add. But the interaction is unstated and untested |
| 8.6 | The repeat rule's promotion is gone with the severity it operated on | The count survives in the evidence. Recorded so a future pass does not re-derive why the promotion vanished |
| 8.7 | **40 / 60 / 80 remain unsourced round numbers** | They select the top 6% of outcomes and 35% of the losses on one trader's book. **Explicitly out of scope of the exposure work** — the `sl_percent_options` fix says the severe-loss ladder must not move — but "not now" is not "sourced". See the cross-cutting recount below |

### Patterns 1, 2 and 3 — coverage caveats, pointer only

Recorded in their own STATUS files and **not repeated here**, because each is an
instance of the standing one-trader caveat rather than an open item: instrument
coverage outside long options is synthetic (Pattern 1, book is 727 LONG / 15
SHORT); cross-strike sequences are deliberately out of scope (Pattern 2, 53
occurrences / 30 days, separate research); overlapping positions count as
attempts (Pattern 3, 24 of 49 firings, recorded not excluded).

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

### 1. `trading_capital` is a single point of failure for exposure detection

> **RESTATED 2026-09-02 — the finding survives, its subject does not.**
> `excess_exposure` was retired on 1 Sep, so the measurement below describes a
> detector that no longer exists. **The consequence is unchanged and now
> attaches to `constitution_violation`'s `max_trade_risk`**, which divides by
> the same field, and to `overexposure` (Q6) and `capital_mismatch` (Q7). The
> product question is identical and still unanswered; only the name changed.
> Do not read the 231-firing figure as a live number.

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
engine*" is **false** — one detector of the seventeen then registered depended on it (**that detector,
`excess_exposure`, is now retired — see the restatement above**), and the
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

## Surfaced by the Pattern 17 review — NOT actioned. **Filed 2 Sep 2026.**

`session_meltdown` was **MODIFIED** on 30 Aug: the undocumented
`trading_capital * 0.05` is gone from both the detector and `api/risk.py`, and
with no declared `daily_loss_limit` it now abstains. **No replacement percentage
was substituted** and tests forbid one. Two of that review's problems survived
the change; only the stale-docstring half of one reached this file.

### 1. Two constants drive a `notification_level=4` detector with no classification

The **40 / 75** ladder was explicitly **not** part of the Pattern 17 change and
is pinned separately. It remains what the review called it: two numbers deciding
the tiers of the loudest detector in the engine, with no `THRESHOLD_SPECS`
record, no `Kind`, no provenance and no maturity.

**Distinct from the 5% that was removed.** The 5% was *invented and described to
the trader as theirs*; the 40/75 is documented and was explicitly endorsed. That
makes it a **bookkeeping gap, not a calibration one** — the same distinction
drawn for `post_loss_recovery_bet`'s multipliers, and the same fix: a
`THRESHOLD_SPECS` record, not a new number.

### 2. `account_risk` vs Kite `opening_balance` — the denominator question

The review recorded that `ctx.account_risk` is an account **SIZE**, not a limit,
and that the canonical account-risk denominator is Kite's `opening_balance`
rather than `equity_total` (which stores `live_balance` and moves with
utilisation).

**Why it was not swapped:** *"swapping the denominator moves every firing
count."* That is a measurement plus a decision, not a refactor, and it was
outside the approved scope of a change whose whole point was to stop inventing
capital figures.

**Related and already filed:** the stale `EngineContext.account_risk` docstring
(under the money-rule validation), and `equity_utilization_pct`'s denominator
(under Pattern 28). All three are the same question asked at three layers —
**what is the account-risk denominator, and does every surface use the same
one?** Worth deciding once rather than three times.

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

### ~~`panic_exit` carries the identical unverifiable claim~~ — **MOOT 2026-08-29**

> `panic_exit` was **RETIRED** the same day this was filed, for an unrelated and
> larger reason: its subject did not exist. The claim went with the detector, so
> there is nothing left to fix. **Kept because the class is not moot** — the
> same "asserted from the exit fill's order type" shape is what Pattern 12's own
> message was corrected for, and it is what the resting-order-book item below
> would finally close.

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

### §27 `strategy_breakdown` — the DEFER's residue. **Filed 2 Sep 2026.**

**This section is a correction of this file, not of the review.** Until now
`strategy_breakdown` appeared here exactly once, as a status word inside the
heading above. Its evidence and its contract were written into
`docs/patterns/25-27-performance-trio/performance_trio_review.md` §27 and never
carried across — so the only open detector with a recorded behavioural contract
had no entry in the register that is supposed to hold them.

| # | finding | numbers |
|---|---|---|
| P1 | **On this book it is EXACTLY `win_rate_collapse`. Zero unique firings** | both fire 4, **identical sets**, unique to `strategy_breakdown` = **0**. The profit-factor condition never excluded anything — a session winning 11% of its trades almost always has a wrecked profit factor |
| P2 | **The redundancy cannot be settled at n = 2** | 2 sessions is not enough to conclude PF never binds. Enough to say the second signal **has not earned its place**; not enough to remove it. PF collapse is **not** vacuous in isolation — 6 of 26 qualifying sessions have it — but as the second half of an `AND` it added nothing |
| P3 | shares §26's defects exactly | `trigger="session"` declared and not honoured; `info` with **no Strategy Health reader** |

**Recommended behavioural contract, recorded:**

> **Subject.** Two independent performance signals degrading together, which is
> stronger evidence than either alone.
>
> **Must be able to differ from its own first signal.** A detector whose second
> condition never binds is a copy of the first under another name, and should
> either be shown to differ or be folded into it.

**Why DEFER and not DELETE:** 100% overlap across 4 events on 2 sessions cannot
carry a retirement — that would repeat the error of acting on evidence too thin
to hold the conclusion. **Not KEEP either**: "keep" would imply it has been
shown to add something, and it has not. Folding it into `win_rate_collapse` is
the obvious consolidation and is **not justified on 2 sessions**.

**Unblock — and it is in TWO parts, which the review recorded as one.**

1. **Data.** Enough sessions reaching the 8-trade gate to observe whether the
   profit-factor condition ever excludes a win-rate collapse. On this book only
   **26 of 175** sessions reach that gate and **2** pass. That is a constraint of
   data, not of method — no further analysis of these 175 sessions supplies it.
2. **A decision that was never asked** — see the entry immediately below. Even
   with those sessions, the detector cannot reach a trader.

### The `performance` domain cannot produce a notifiable event — PENDING DECISION

**Found by the A1 `death_spiral` measurement, stated in commit `f46c25f`'s
message, and never filed until now.** The commit put it in one line: *"A whole
domain could never contribute: both `performance` detectors hardcode
`severity="info"` against a `>= danger` gate."*

Verified in code 2 Sep 2026:

```
behavior_engine.py:3540   strategy_breakdown   severity="info"   hardcoded
behavior_engine.py:3496   win_rate_collapse    severity="info"   hardcoded
registry, both:  nature="performance", disposition="analytics",
                 notification_level=0, trigger="session"
```

Combined with the **closed** INFO/EVIDENCE rule — `info` never becomes a
`RiskAlert`, never influences `danger_zone` or severity escalation — this means
**neither performance detector can reach a trader by any route**, at any sample
size. `death_spiral` was the one consumer that read the domain at all, and it is
retired.

**What must be decided:** whether the `performance` domain is
evidence-and-analytics forever, or whether one of these two is meant to become
trader-facing. Both readings are defensible and the code states neither.

**Why this is not a bug and must not be "fixed":** promoting an INFO pattern to
a trader-facing alert is an **explicit product decision, never a bug fix** —
that rule is closed and enforced by `test_info_evidence_visibility.py` (12
tests). Hardcoding a higher severity to make the domain reachable would be
exactly the change the rule exists to stop.

**Why it matters for Q3:** it makes `strategy_breakdown`'s recorded unblock
**necessary but not sufficient**. Collecting the disagreeing sessions answers
"does the second condition bind"; it does not answer "and then what happens",
because today the answer is *nothing*. Whoever picks up Q3 should take both
halves or neither.

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

# ~~BLOCKING~~ — `sl_percent_options` invents a USER RULE. **CLOSED 2026-09-02.**

> **FIXED, and the section is kept as the record of what was wrong.**
> `threshold_resolution.py:554-555` now reads
> `_slo = getattr(profile, "sl_percent_options", None)` and puts
> `_slo if _slo else None` — an undeclared rule resolves to **None**, not to an
> invented 50.0 at `Source.FACT`. A trader who configured nothing is no longer
> told they configured something, and the fabricated band no longer pre-empts
> the universal 40/60/80 ladder. `sl_percent_futures` was removed as a user
> input the same day. **The 40/60/80 thresholds did not move** — but they are
> still unsourced, which is Pattern 8's limitation 8.7 and the recount below.
>
> Everything from here to the end of this section is the original finding,
> preserved because the *class* it names is not closed.

**Raised during the exposure-hierarchy verification, blocking that
implementation. Not fixed at the time — it needed approval, and it is not an
exposure threshold.**

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

# Surfaced by the Pattern 28 final verification — NOT actioned

### `equity_utilization_pct` is broker margin / live balance, NOT capital deployed / declared capital

Verified in `margin_service._analyze_segment`:

```
utilization_pct = net_blocked / live_balance * 100
net_blocked     = max(0, exposure + span + option_premium)   # BROKER-reported
live_balance    = the account's liquid funds
```

**Numerator:** real blocked margin as the exchange holds it — better than
anything we compute. **Denominator:** the broker's live balance, **not** the
self-reported `trading_capital` that `capital_mismatch` exists to nudge about.

So the informational surface can honestly say *"₹40,000 of ₹50,000 of your
account is blocked as margin — 80% utilised"*. It **cannot** say *"80% of your
declared capital is deployed"* without changing the denominator. **The two are
related but different questions.** No detector reads either, so nothing is
mis-firing; this governs the **wording** of the UI when it is built.

Also noted: the model's own comment warns that `equity_total` stores
`live_balance`, which moves with utilisation, and that
`equity_opening_balance` is the canonical account-risk denominator. Whichever
the UI uses must be stated.

### `instrument_master.resolve` classifies an unparseable NFO symbol as cash equity

`resolve("ZZZGARBAGE99", "NFO")` returns `Segment.EQUITY`, `usable=True`,
`multiplier=1` — so `quantities_for_trade` gives it a **NOTIONAL** capital
requirement (`"cash delivery value"`) instead of abstaining, and the old
`_exposure_value` accepted it too.

**Pre-existing, in the instrument layer — not introduced by Pattern 28**, and not
reachable from real data, because live symbols come from Kite and parse. But an
unparseable symbol *on an F&O exchange* should abstain rather than silently
become equity. Recorded for the instrument-master owner; **not fixed here**,
because it is outside a verification pass.

### The constitution ladder fires `caution` at 0.80 of a declared exposure limit

**A semantic mismatch to decide, not a defect.** The stated expectation was
*"user rule = 80% → position at 75% does not alert"*. Measured:

| position | ratio | outcome |
|---|---|---|
| 60% | 0.75 | silent |
| **75%** | **0.94** | **`caution` — "approaching"** |
| 80% | 1.00 | `danger` — breached |
| 85% | 1.06 | `danger` — breached |

`caution` is **not notifiable** (`NOTIFIABLE = {danger, critical}` in
`core/severity.py`), so there is **no push** — but a `RiskAlert` row is written.

This is the **pre-existing** 0.80 / 1.00 / 1.20 ladder that governs *every*
constitution rule — daily loss, per-trade loss, cooldown — and Pattern 28 was
explicitly told not to modify ladders. Changing it for exposure alone would make
that rule inconsistent with the others; changing it for all of them is a separate
product decision. **Left exactly as it was.**

### `_is_contract_expired` misreads a real 1st-of-month expiry — found 2026-09-02

`reconciliation_tasks._is_contract_expired` branches on `expiry_date.day == 1`
to detect `instrument_parser`'s **monthly proxy** date, and then refuses to
expire the contract until the whole month has passed.

**A weekly contract that genuinely expires on the 1st is indistinguishable from
that proxy**, so it stays "live" for up to another month and
`_expire_stale_positions` will not zero it.

Surfaced because two tests in `test_integration.py::TestOptionsExpiryCleanup`
construct `yesterday = date.today() - 1` and assert it is expired — which is
true on 29 days a month and **false on the 2nd**, when yesterday is the 1st:

```
today=2026-09-02  yesterday=2026-09-01 (day=1)  -> expired? False
today=2026-09-03  yesterday=2026-09-02 (day=2)  -> expired? True
```

**Two separate things here, both recorded and neither fixed:** the tests are
date-dependent and will fail on the 2nd of every month, and the predicate has a
real collision between the proxy convention and genuine 1st-of-month expiries.
The proxy exists because the parser does not resolve the exact last-Thursday;
fixing it properly means resolving real expiry dates, not adjusting the branch.
**Out of scope** — found while verifying migration 083, which touches no date,
position or expiry code.

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

## Recorded during the A1 `death_spiral` retirement (2026-09-02)

Found while tracing that detector's consumers. **Neither belongs to A1** and
neither was touched there — scope discipline, recorded for the consolidated
pass instead.

> **A third A1 finding is filed under Reviews 25-27, not here:** *"a whole
> domain could never contribute — both `performance` detectors hardcode
> `severity="info"` against a `>= danger` gate"*. It was stated in commit
> `f46c25f`'s message and never filed at all until 2 Sep. It sits with §27
> because its live consequence is `strategy_breakdown`'s unblock, not
> `death_spiral`'s retirement.

### `portfolio_concentration` leftovers — PENDING DECISION (Pattern 28)

Retired 2026-09-01, and its `_ALIAS_NATURE` entry went with the A1 retirement.
Three references survive in live code:

- `BehaviorEngine._FAMILIES`, in the "the position is too big" family
- a comment in `position_monitor_tasks.py`
- `app/services/portfolio_concentration_service.py`, an entire module

The family tuple is the one with behavioural weight: a family member that can
never fire cannot win or be folded, so it is inert — but it is also a name in a
consolidation rule that no longer means anything. Decide whether Pattern 28's
retirement should have swept these, then do it in one pass.

### `no_stoploss` writes events nothing judges — PENDING DECISION

It is in the replay's `UNJUDGEABLE` set (a tradebook has no order type), so its
alerts are excluded from every count — yet it still writes BehaviorEvents, and
those events were counted as a `risk` domain contributor by `death_spiral` on
35 sessions before that detector was retired. With the composite gone nothing
reads them for that purpose. Not a defect; a question about whether an
unjudgeable detector should produce evidence rows at all.

### The `caution` tier is not notifiable, and 5 firings proved it silent

`NOTIFIABLE = {danger, critical}`. During the A1 measurement, 5 sessions
produced a `caution` death_spiral that wrote a RiskAlert row and pushed
nothing. That is the documented INFO/EVIDENCE design and is **not** reopened
here — noted only because it means "fired" and "was seen" differ by tier, which
matters for any future firing-count comparison.

# CROSS-CUTTING CLASSES — filed 2026-09-02

Each of these was recorded once per pattern as if it were that pattern's
problem. Counted across the sequence they are **classes**, and each closes in
one job rather than N.

## 1. Unsourced statistics — the count in this file was wrong

The Pattern 20 entry says *"Three instances is a pattern, not three accidents"*
and recommends a sweep. **The sweep is more load-bearing than that reads.**
Measured against `backend/app/core/trading_defaults.py` on 2 Sep 2026:

| line | claim | status |
|---|---|---|
| **133** | *"SEBI: traders who averaged down on losing options lost 3× more"* | **LIVE**, justifying `martingale_caution_multiplier` / `_danger_multiplier` |
| 270 | **the identical sentence**, recorded as *removed* with `premium_avg_down_loss_pct` and called *"third instance of that class"* | **a deletion note 137 lines below a surviving copy of the same claim.** It was deleted in one place and left in another |
| 61 | *"SEBI FY2023: traders with >6 trades/day had 94% loss probability"* | **LIVE** — Pattern 5's limitation 5.5 |
| 84 | *"SEBI data: 73% of trades within 15 min of a loss are also losing trades"* | **LIVE** |
| 105 | already self-documents as having **no source** | LIVE, flagged in place |
| 220 | *"SEBI/NSE data: 38% of retail intraday traders … give back"* | orphaned — its threshold went with `profit_giveaway` |
| 261 | *"SEBI FY2022: retail sold winning positions 2.7× faster"* | orphaned — already filed as Pattern 19's item 4 |

Plus the **40 / 60 / 80** severe-loss ladder (Pattern 8, limitation 8.7), which
is unsourced but explicitly out of scope of the exposure work.

**So: at least four live claims attached to live thresholds, two orphaned
comment blocks, and one claim that outlived its own deletion note.** Two of them
— `expiry_day_overtrading`'s and the hot-hand claim — **were shipped to traders**
before being caught, which is why this is not cosmetic.

**The job:** one sweep of every comment in `trading_defaults.py` and
`threshold_registry.py` that cites evidence, keeping only what a reader can
produce. **Do not delete a threshold to remove its comment** — the number and
its justification are separate questions, and three retirements turned on
exactly that distinction.

## 2. Declarations nothing checks — one contract test closes three instances

Three separate reviews found a spec field that claims something no producer
delivers, each recorded as that pattern's finding:

| instance | what was declared | what existed |
|---|---|---|
| Pattern 18 | `early_exit_winner_max_min`, `Source.HISTORY`, `metric="winner_hold_p50"` | `baseline_service` emits `avg_winner_hold_min`. **`winner_hold_p50` is never produced anywhere** |
| Pattern 19 | `winning_streak_overconfidence`, `uses_baseline=True` | it read no baseline at all — its "baseline" was an inline average over today's session. The field has **zero readers** |
| Pattern 23 | `recovery_bet_caution_mul` / `_danger_mul` | exist only in `COLD_START_DEFAULTS` with an inline comment — no `Kind`, no provenance, no maturity. **Seventh known instance** of a missing or dead threshold declaration |

Add Pattern 17's 40/75 ladder (above) and it is four.

**The fix is one contract test over `THRESHOLD_SPECS`**, not four corrections:
assert that every spec's `metric` is a key some producer actually emits, and
that `uses_baseline` matches whether the detector reads one. The H1 key-name
mismatch was this same class, found and fixed once — **it recurred because the
declaration is unchecked.**

## 3. The `analytics` disposition has no consumer contract

Four detectors are `disposition="analytics"` — `rapid_reentry`,
`premium_loss_event`, `win_rate_collapse`, `strategy_breakdown` — and **nothing
states what that disposition entitles them to.** The register already holds the
symptoms as three separate entries: `rapid_reentry` has no trader-facing reader
(Pattern 13); `danger_zone`'s pattern-driven CAUTION path is unreachable
(Pattern 19); the `performance` domain cannot produce a notifiable event
(§27 above). They are one question asked three times.

**What must be decided:** whether `analytics` means *"evidence written for a
surface that will exist"* or *"evidence written for nothing"*, and if the
latter, whether it should be written at all. The closed INFO/EVIDENCE rule does
**not** depend on the answer — INFO events must not become alerts either way.

**Related, smaller:** the four **aliases** (`daily_overtrading`, `overexposure`,
`holding_loser`, `capital_mismatch`) carry no `DetectorSpec` of their own, and
`daily_overtrading` still has **zero test mentions** despite being the emitted
half of a detector that was changed in August.

---

# REGISTER HYGIENE — filed 2026-09-02

Not findings about the engine; findings about the record of it.

## `STATUS.md` is missing for eight LIVE detectors

`docs/patterns/README.md` admits the convention lapsed after Pattern 11 and
names **two**. Measured: no `STATUS.md` exists for **12** `no_stoploss`
(MODIFIED), **13** `rapid_reentry` (KEEP), **17** `session_meltdown` (MODIFIED),
**23** `post_loss_recovery_bet` (KEEP), **24** `constitution_violation` (KEEP,
and the largest alert source in the engine), **26** `win_rate_collapse` (KEEP),
**27** `strategy_breakdown` (DEFER), **28** `overexposure` + `holding_loser`.

For the **retirements** the gap is harmless — a retired detector has no "what it
does NOW", and its suite under `backend/tests/test_*_retired.py` records the
reasoning. For these eight it is not, because **a review is written before the
change and therefore describes the old behaviour.** Anyone reading
`12-no_stoploss/no_stoploss_review.md` today reads a detector that no longer
says what it says.

## `backend/docs/patterns/` is a shadow tree

Six empty directories — `05-overtrading`, `06-profit_giveaway`,
`20-options_premium_avg_down`, `21-session_windows`,
`24-constitution_violation`, `25-27-performance-trio` — untracked, zero files,
created by measurement scripts run with `backend/` as the working directory.
Harmless, and it already caused one misreading of the real folder as empty.
Delete, and give the measurement scripts a repo-root-relative output path.

---

# Landing page — VERIFIED LIVE 2026-09-02. Truthfulness, not design.

**Filed here because nothing else owns the verified state.**
`docs/LANDING_PAGE_AUDIT.md` predates the retirements and lists these as
marketing copy; two of them are now also **factually about detectors that do not
exist**. The landing-page *design* is a separate, paused track — **these must go
regardless of visual direction.**

| line | text | why it must go |
|---|---|---|
| `Welcome.tsx:454` | *"₹4.8Cr+ — Estimated losses prevented"* | Fabricated (zero real users) **and a counterfactual**. The project rule is that behaviour→money is the **realized P&L of flagged trades**, never an estimated saving. This is the exact claim the rule bans |
| `Welcome.tsx:390` | *"₹46,000 leaked per trader this year. Mostly to themselves."* | Unsourced per-trader figure. Same class as the `trading_defaults.py` recount above, shipped to the public |
| `Welcome.tsx:96` | showcases **`Early Exit`** with *"Cut winner at ₹1,800. It ran ₹4,100 more. 7× this week."* | **RETIRED 30 Aug.** Sells a detector that no longer exists, with invented numbers |
| `Welcome.tsx:119` | *"Meltdown Cascade — Loss streak + increasing position sizes = exponential, not arithmetic damage."* | This is `death_spiral`, **RETIRED 2 Sep**. Same problem, plus a mechanism claim the retirement measurement contradicts |
| `Welcome.tsx:237` | *"P&L Impact −₹18,400"* | Invented per-pattern cost |
| `Welcome.tsx:341, 354` | *"Circuit breaker prompts suggesting a cooldown period"* · *"Proven pattern disruption to stop cascade losses"* | Charter-banned blocker language against "mirror, not blocker", plus **"proven"** for something with no live outcome data |

**Not confirmed:** a grep for testimonials returned nothing, so that audit P0
may already be gone. Verify rather than assume.

**Every retirement from here on should check this file**, because a retired
detector on the landing page is a claim about a product feature that was
withdrawn.

---

## Closed on this pass — recorded so they are not re-raised

| # | verdict |
|---|---|
| **F21** | **Not a bug.** `capital_mismatch` is a housekeeping nudge, not a behaviour detector. *Updated 2026-09-02:* the original wording justified this through `death_spiral`'s `_ALIAS_NATURE`; both are retired. The fact is unchanged and now asserted directly — it is in the alert vocabulary and has no `DetectorSpec`. Pinned by a test. |
| **F24** | **Not a bug.** `adding_to_adverse_position` is the one `trigger="entry"` detector; the exit loop skips such specs deliberately and the entry-batch flush dispatches it. It runs. |

Fixed 29 Aug: **F1, F10, F18, F19, F22, F23** (and earlier **F3, F7, F8, F9,
F11, F15, F16, F17**). See `RISK_INFRA_PLAN.md`.

## Closed 2026-09-02 — strategy-classifier correctness (`5844381`)

Three defects of one shape: a structure was named without reading the property
that defines it. All three fixed in one commit, verified on both grouping paths
over the whole reference book.

| # | verdict |
|---|---|
| **B1** — futures hedge asserted without the option leg's direction | **CLOSED 2026-09-02.** The label was corrected in `5844381`; the downstream half — `MULTI_LEG_UNKNOWN` earning a recognised structure's silence — was closed by F6 in `c107300`. A risk-adding FUT + short-option pair now both loses the hedge label **and** earns no suppression. |
| **B2** — `IRON_BUTTERFLY` unreachable, and the label only ever wrong | **CLOSED.** The branch sat below a condor test that every real butterfly also satisfies, so it never ran; the only shape that could reach it was four legs in one direction, which is not a butterfly. Butterfly and condor are now decided together by one ordering test, body width separating them. A real butterfly is named one; malformed and single-direction shapes cannot reach the label. |
| **B3** — `iron_condor` was a catch-all, not a classification | **CLOSED.** It tested leg count and mixed direction only, so any four mixed-direction CE/PE legs matched — including the **inverted** structure whose risk runs the other way. It now requires 2 calls, 2 puts, four distinct strikes and both shorts strictly inside both longs. Everything else falls safely to `MULTI_LEG_UNKNOWN`. |

**Standing caveat on B1 and B3:** every case needing a short leg is exercised
only by synthetic tests. Exactly one symbol in the reference book ever goes net
short, so this trader's data cannot reach those branches. The logic is proven;
it is not proven against real data, and no book we hold can prove it.

**Recorded for the principle, not as a backlog item:** `MULTI_LEG_UNKNOWN` is an
**intentional uncertainty state** — *"these legs are one multi-leg decision and
we cannot name the strategy"* — not a failed classification. TradeMentor names
the small set of common structures whose semantics are unambiguous and is honest
about the rest; ratio, calendar-diagonal, custom and exotic structures are not
recognised by design. `classify_legs`' docstring now carries this. It matters
because F6 is a decision about what that state earns, and reading it as
"classification failed" would answer F6 by accident.
