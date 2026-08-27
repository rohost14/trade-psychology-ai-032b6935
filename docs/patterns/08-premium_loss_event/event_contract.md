# Pattern #8 — final event contract before implementation

27 Aug 2026. **Design only. No code, no threshold changed.** Follows
`three_layer_contract.md`, which was approved in direction.

**Pattern 8 stops being a behaviour detector.** It becomes a **real-time
risk-state detector**: it reports what is true about a position, and it supplies
that fact to the detectors that judge behaviour. Its `nature` is already `risk`
rather than `emotional`, so the registry has been describing it correctly all
along — the copy, the severity and the alerting disposition were not.

---

## 1. What the universal 40/60/80 live alert is for

Three candidates were on the table. Only one survives.

| candidate | verdict |
|---|---|
| **Behavioural intervention** — "you are doing something wrong" | **No.** A large premium loss is a market outcome. The bands select money (6% of positions, 38% of the loss) but say nothing about *how* the trade was taken. Every behavioural test in this series that could have connected loss magnitude to a decision has failed. |
| **Action prompt** — "you should exit" | **No.** That is advice, on a position whose thesis, hedges and plan we cannot see. It also breaks the product's stated philosophy: *mirror, not blocker*. |
| **Safety notification** — "this has passed a level you may not have noticed" | **Yes.** |

> **The job is to close the gap between what is true about the position and what
> the trader currently knows.**

That gap is real **only when the trader is not looking.** Someone watching the
screen already has the number — the frontend computes live P&L client-side from
the tick stream. The alert exists for the trader who has the tab closed, is in a
meeting, or is looking at a different position.

This is why **live matters and exit does not**: at exit the trader necessarily
knows, because they just closed it.

It also satisfies the design of record — *"convert an automatic action into a
deliberate one"* — with the automatic action being **drift**, not the trade. It
makes no prediction, assigns no fault, and asks for nothing.

**Consequence for copy:** the alert states the number and stops. It does not say
"bleeding", "destruction", "you should", or "before it gets worse."

## 2. Ownership — four detectors, four subjects

| detector | owns | answers |
|---|---|---|
| **Pattern 8** `premium_loss_event` | **magnitude** | how much of the premium is gone |
| **`constitution_violation`** rule `sl_percent_options` | **the trader's line** | have they reached the exit point they declared |
| **Pattern 2** `adding_to_adverse_position` | **behaviour** | did they act on the position while it was under water |
| **Pattern 12** `no_stoploss` | **protection** | was anything guarding the position |

Each is a different sentence about the same position. **None is a substitute for
another**, which is why they are not merged.

## 3. The constraint that shapes the consolidation

`Layer.SAFETY` is load-bearing, not descriptive:

> *"SAFETY findings may never be suppressed by anything learned from the trader,
> because a habit is not a licence."*

`premium_loss_event` resolves from `UNIVERSAL_SAFETY` thresholds, so it is a
SAFETY finding. **A behavioural detector may not silence it.**

**The resolution is that the fact is never dropped — it is either the alert or it
is carried inside the alert that wins.** Merging is not suppressing when the
number still reaches the trader. That is exactly the mechanism
`_consolidate` already uses for multiple constitution breaches, which fold into
one alert carrying `also_breached`.

## 4. The event contract

### Facts — always produced, never alerts

| fact | source | lifetime |
|---|---|---|
| `premium_loss_pct`, current band, crossing timestamp | Pattern 8 live state | while the position is open |
| `has_protective_order` | Pattern 12, **when live order state exists** | while the position is open |

Both attach to any alert about that position.

### Alerts — at most one per position per escalation step

Priority, most specific first:

1. **`constitution_violation` (`sl_percent_options`)** — the trader's own promise. Strongest, because they set it.
2. **`adding_to_adverse_position`** — they *acted*. A decision was made.
3. **`premium_loss_event`** — the market moved. No decision involved.

The winner **absorbs the others' facts into its context and message.** The
losers keep their `BehaviorEvent` with a `_suppressed` marker, exactly as
`_consolidate` already does — *"it stops being shouted, which is different from
being hidden."*

**Scope is the position, not the account or the session.** Two bleeding
positions are two stories.

### Where each event fires

| event | trigger | severity | disposition |
|---|---|---|---|
| band crossing, position open | live, on crossing | 40/60/80 → caution/danger/critical | **alerting** |
| declared boundary crossed, open | live, on crossing | constitution ladder | **alerting** |
| add while under water | on the add | Pattern 2's existing matrix | alerting |
| **position closed at N% down** | exit | **`info`** | **analytics-only** |

**The exit-path demotion to `info` is the single change that removes the
live/exit double-report**, with no dedup surgery: `info` never becomes a
`RiskAlert` (`behavior_engine.py` — *"info = analytics-only"*).

## 5. Alert examples for the overlapping cases

Position: NIFTY 25000 CE, bought at ₹100 × 75, now ₹55. **45% of premium gone.**

**A — nothing else is true.**
> ⚠️ **NIFTY25AUG25000CE is 45% down on premium** (₹3,375 of ₹7,500).
`premium_loss_event`, caution. The only case where Pattern 8 speaks in its own voice.

**B — the trader declared "I exit at 25%".**
> ⚠️ **You said you exit options at 25%. NIFTY25AUG25000CE is 45% down** (₹3,375 of ₹7,500).
`constitution_violation`, rule `sl_percent_options`. Carries `premium_loss_pct: 45`, `band: "caution"`. Pattern 8 folds in as `same_position:constitution_violation`.

**C — the trader adds another lot at ₹55.**
> ⚠️ **You added to NIFTY25AUG25000CE while it was 45% down** (now ₹15,000 at risk, average ₹77.50).
`adding_to_adverse_position`. Carries `premium_loss_pct_at_add: 45`. Pattern 8 folds in.
*This is the case the evidence says matters most — 14 of 18 such positions got worse, at −₹5,996 per episode against −₹4,428 for the plain threshold.*

**D — declared 25%, and they add.**
> ⚠️ **You added to NIFTY25AUG25000CE at 45% down — past the 25% exit you set.** Now ₹15,000 at risk.
`constitution_violation` wins on priority, carrying `also_fired: ["adding_to_adverse_position", "premium_loss_event"]`. **One alert, three facts.**

**E — 45% down, no protective order (Pattern 12, when live).**
> ⚠️ **NIFTY25AUG25000CE is 45% down on premium, with no stop-loss order on it.**
`premium_loss_event` carrying `has_protective_order: false`. **Not a second alert** — protection is context on magnitude, exactly as `three_layer_contract.md` §7 proposed.

**F — it then reaches 60%.**
> ⚠️ **NIFTY25AUG25000CE is now 60% down** (₹4,500 of ₹7,500).
New band, new alert. Escalation always passes.

**G — it recovers to 30%, then falls to 62%.**
**Silence.** The 60 band was already reported for this position epoch.

**H — closed at 62%.**
**No alert.** `info` event only, feeding Analytics and the daily report.

## 6. Dedup and consolidation behaviour

| dimension | rule |
|---|---|
| **key** | `(pattern_type, position_epoch)` — the epoch being the ledger's `OPEN`/`FLIP`, reusing Pattern 2's existing concept |
| **band memory** | highest band fired per epoch; a band never re-fires |
| **escalation** | a higher band always passes |
| **recovery** | never re-arms a band already fired. A genuine new position (`OPEN`/`FLIP`) resets |
| **two positions** | independent — the epoch is in the key. **Fixes the measured bug where 7 of 48 detections were swallowed, including a critical at 86.7%** |
| **cross-detector** | one alert per position per step; losers keep a `_suppressed` `BehaviorEvent` |
| **live vs exit** | cannot collide — exit is `info` and never alerts |

**What this removes:** the account-scoped exit dedup, the live/exit double-report,
and recovery-relapse spam. **What it preserves:** every fact, in the suppression
trace.

## 7. Tests required before this ships

**Pattern 8 state and crossings**
1. crossing 40 emits once; sitting at 42 emits nothing
2. 40 → 60 → 80 emits three times, escalating
3. recovery to 20 then back to 45 does **not** re-emit 40
4. `OPEN`/`FLIP` resets band memory
5. two positions on one account alert independently
6. stale LTP (>2s) emits nothing — no fabricated percentage
7. expiry-day shift applies live exactly as at exit
8. exit path emits `info` and produces **no** `RiskAlert`

**Consolidation**
9. Pattern 8 alone → Pattern 8 alerts
10. Pattern 8 + constitution → constitution alerts, carrying `premium_loss_pct`
11. Pattern 8 + Pattern 2 → Pattern 2 alerts, carrying loss at the add
12. all three → constitution alerts, `also_fired` lists both
13. folded detectors keep a `BehaviorEvent` with `_suppressed`
14. **two positions, different stories → two alerts** (no cross-position folding)
15. Pattern 12 state, when present, attaches as context and does **not** add an alert

**Invariants**
16. `premium_loss_event` never resolves from a personal baseline (`violates_kind`)
17. no personal value loosens a universal band; a tighter declared one fires earlier
18. bands unchanged: 40 / 60 / 80 / +15pp
19. `nature="risk"` and the copy asserts no intent
20. the detector stays pure; no DB on the tick path

**Scale**
21. crossing evaluation performs **zero** DB reads
22. state rebuild happens on fill/close/rules-change, not per tick

## 8. What is NOT in this contract

- **No threshold changes.** 40/60/80 and the +15pp shift stand.
- **No merge** of Patterns 8 and 12.
- **No Pattern 12 live path** — still blocked on discarded `TRIGGER PENDING` events.
- **No holding-past-boundary detector** — unevidenced without tick history.
- **No change to Pattern 2's severity matrix.** Adding depth as *context* is
  proposed; using it for severity would need its own evidence.
- **No new consolidation family for the pace detectors** — separate question.

## 9. Open decisions for approval

1. **Does `premium_loss_event` keep `disposition="alerting"`?** It still alerts
   in case A. Recommendation: **yes**, with the exit path emitting `info`.
2. **Should `sl_percent_options` become a `RULE_FIELD`?** Required for case B.
   Recommendation: **yes** — it is already a declared commitment in everything but
   name, and `RULE_FIELDS` is what gives it tighten-instantly/loosen-with-friction.
3. **Is a band crossing with nothing else worth a push at `notification_level=3`?**
   Under the "safety notification" purpose the answer is probably a lower level
   for `caution` and the current one for `critical`. **Not proposed — flagged.**
4. **`sl_percent_futures` has the same problem** and no detector reads it either.
   Out of scope here; needs the same treatment.
