# Pattern #6 follow-up — alert volume and episode dedup

27 Aug 2026. **Analysis only. No code changed.** Closes the open item left by
`STATUS.md`: *"the per-day rate did not improve … the review's 'same story told
several times' problem stands."*

**Verdict: MODIFY TO EPISODE-BASED — but for correctness, not volume.** The
episode key costs nothing (100 alerts → 100 on this book) and closes a latent
false-negative. **The re-arm must stay.** Dropping it is what would cut volume,
and measurement shows it would cost the trader ₹65,769 of unreported
deterioration.

---

## Correction to the figures in `STATUS.md`

`STATUS.md` records **~95 alerts**. The correct number is **100**. My earlier
simulation modelled the first-fire, the severity escalation and the metric
re-arm, but **omitted the 2-hour elapsed-window rule** — a session runs 09:15 to
15:30, so that clock does expire and does re-fire. Every count below models
`_is_deduped_full` completely, using real trade timestamps.

The direction of the finding is unchanged; the number was five too low.

## 1. What a giveback episode is

> **An episode is a fall from ONE high-water mark.**
>
> - **Starts** when the session sets a high-water mark and then falls from it.
> - **Identified by** that high-water mark — `facts.peak_pnl`.
> - **Ends** when the session sets a NEW high-water mark. The old giveback has
>   been fully recovered; anything that falls after that is falling from
>   somewhere else.
> - **Resets** at the session boundary, because `peak_pnl` does.

`peak_pnl` is monotonic non-decreasing within a session, so *"the peak changed"*
is an exact, cheap episode boundary. **`(session_date, peak_pnl)` names an
episode and both halves already exist** — no new state, no new table, nothing
another detector can observe. This is the same shape as Pattern 2's position
epoch and Pattern 3's underlying key.

**A new episode should legitimately produce a new alert**, because a giveback
from a *higher* high is new information about a different quantity of money.

## 2. Are the alerts one episode repeated, or distinct events?

**135 detections → 100 alerts → 49 episodes, across 48 of 189 sessions.**

| alerts in one episode | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| episodes | **23** | 12 | 7 | 4 | 2 | 1 |

Composition of the 100:

| | count |
|---|---|
| first alert of an episode | **49** |
| genuine severity escalation (caution → danger) | **6** |
| same-severity re-arms on `worst_giveaway` | **45** |

**Episodes per session: 47 sessions have exactly one, 1 session has two.**

So the answer is: **they are the same episode, repeated — but each repeat is a
genuinely worse number.** `worst_giveaway` is `facts.max_drawdown`, a running
maximum, and the re-arm requires +20%. Every repeat means the giveback grew by
at least a fifth beyond the last figure the trader was given.

## 3. Current behaviour vs episode-based dedup

| option | key | window | re-arm | **alerts** | max/episode |
|---|---|---|---|---|---|
| **A — current** | `pattern_type` | 2h | yes | **100** | 6 |
| **B — episode key, else unchanged** | `(type, day, peak)` | 2h | yes | **100** | 6 |
| **D — episode key, no re-arm** | `(type, day, peak)` | 2h | no | **68** | 3 |
| **C — episode key, escalation only** | `(type, day, peak)` | — | no | **55** | 2 |

**A and B produce not merely the same count but the identical set of alerts.**
The episode key changes nothing on this book, because 47 of 48 affected sessions
contain exactly one episode.

**The volume is not an episode-identity problem. It is the re-arm.**

## 4. What each option removes, and what it costs

The cost is measured as *unreported deepening*: for each episode, how much
further the giveback fell after the last alert that option would raise — the
news the trader never gets.

| option | alerts | episodes that deepened unheard | **money unreported** |
|---|---|---|---|
| **A / B** | 100 | 4 of 49 | **₹3,054** |
| **D** | 68 | 17 of 49 | **₹32,486** |
| **C** | 55 | 25 of 49 | **₹65,769** |

The worst individual cases under C:

| day | peak | last told | actually ended | unheard |
|---|---|---|---|---|
| 2025-11-25 | ₹806 | ₹2,310 down | **₹11,145 down** | **₹8,835** |
| 2026-01-23 | ₹1,238 | ₹1,578 down | ₹9,472 down | ₹7,894 |
| 2026-01-05 | ₹1,064 | ₹1,573 down | ₹7,927 down | ₹6,354 |

**On 2025-11-25 the trader would be told they were ₹2,310 below their peak, on a
day that finished ₹11,145 below it, and would hear nothing further.**

**This reverses part of my own review.** I recorded the repeat alerts as *"the
same story told several times"*. That was true of the **old** detector, where
`erosion_pct` oscillated and severity flip-flopped between caution and danger —
genuinely redundant and confusing. Since v2.0.0 the metric and the severity are
both monotonic, so a repeat can only mean *"it got materially worse"*. **The
volume is the information.** Cutting it is not a free win, and D and C are not
recommended.

## 5. False-suppression risk

**Measured, this book: zero.** No firing that an episode key would raise is
suppressed by the current `pattern_type` key. A and B are identical sets.

**But there is a real latent false negative in the current key**, and it is the
reason to make the change anyway:

`worst_giveaway` is `facts.max_drawdown`, which is **session-wide** and never
resets at a new peak. So a second episode's re-arm is compared against the
*first* episode's depth. Concretely:

> Session peaks at ₹5,000, falls to ₹1,000 — drawdown ₹4,000, alert raised.
> Recovers to ₹8,000, a new high. Falls to ₹5,000 — a ₹3,000 giveback from the
> new peak, but `max_drawdown` stays ₹4,000. No escalation, no +20% re-arm,
> inside 2 hours → **suppressed. The trader hears nothing about the second
> giveback.**

The one two-episode session in the book, **2026-02-06**, escaped this only by
coincidence — its second episode happened to escalate caution → danger, which
re-fires for a different reason:

| episode | peak | positions | severities |
|---|---|---|---|
| 1 | ₹1,667 | 2, 3 | caution, caution |
| 2 | ₹3,615 | 6, 7 | **danger**, danger |

An episode key makes that guaranteed rather than lucky.

**Risk in the other direction:** a sawtooth session — repeatedly making new highs
and giving them back — would get one first-alert per episode where today it gets
one per session. On this book the maximum is 2 episodes in a session, so there
is no volume explosion to fear here; on a different trader it is possible, and
that is worth stating rather than pretending the risk is zero.

## 6. Can episode identity come from existing state?

**Yes, entirely.** `ctx.facts.peak_pnl` is already computed by `_load_context`
and already read by this detector; `session_date` is already on the session.
The change is confined to `_pattern_dedup_key` in `trade_tasks.py`, which
already has per-pattern branches for `constitution_violation` (by rule) and
`same_symbol_obsession` (by underlying).

**No other detector is affected** — the branch is keyed on `pattern_type ==
"profit_giveaway"`. No migration, no new table, no per-tick state, no change to
`session_facts`.

One imperfection to record rather than fix: because `worst_giveaway` is
session-wide, **re-arms inside a second episode still compare against the
session's deepest point**, so a shallower later episode will fire once and then
stay quiet. Its first alert is guaranteed, which is the part that matters. A
per-episode drawdown would fix the remainder and is not proposed here — it would
be a new quantity, and the evidence does not yet ask for one.

---

## Answers

**Current alerts** — **100** (not the ~95 in `STATUS.md`; that omitted the 2h
window). From 135 detections, across 48 of 189 sessions.

**Distinct giveback episodes** — **49**. 47 sessions have one; one session has
two.

**Redundant alerts** — **none that are strictly redundant.** 45 of the 100 are
same-episode, same-severity repeats, but each required `worst_giveaway` to grow
≥20%, and that metric is monotonic. Each repeat is a materially worse figure,
not a restatement.

**Legitimate escalations** — **6** caution → danger transitions, plus the 49
episode-opening alerts.

**What episode-based dedup would change** — **nothing on this book: 100 → 100,
the identical set.** Its value is closing the latent false negative in §5, not
reducing volume.

**False-suppression risk** — **zero observed** for the episode key. The current
key carries a latent *false negative* instead: a second, shallower episode can
be silently swallowed because `max_drawdown` does not reset at a new peak.
Dropping the re-arm, by contrast, has a large and measured cost — ₹32,486 (D) or
₹65,769 (C) of unreported deepening.

**Recommended implementation** — one branch in `_pattern_dedup_key`:

```python
if pattern_type == "profit_giveaway":
    # One episode = one fall from one high-water mark. A new peak is a new
    # episode and deserves to be heard; `max_drawdown` is session-wide and
    # would otherwise let a second, shallower giveback be swallowed.
    return f"profit_giveaway:{(details or {}).get('peak_pnl', '')}"
```

Nothing else changes: the 2h window stays, the `worst_giveaway` re-arm stays,
severity stays monotonic. `peak_pnl` is already in the alert context.

**Final verdict — MODIFY TO EPISODE-BASED**, on correctness grounds only, with
the explicit finding that **the volume concern from the original review does not
survive measurement** and no volume reduction should be attempted.
