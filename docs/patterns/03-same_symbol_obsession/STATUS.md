# 3 — `same_symbol_obsession` · **COMPLETE**

v2.0.0 · exit-triggered · `emotional`/`alerting` · notification level 2

## What it reports
The session's relationship with **one underlying**: returning to it, losing on
it, returning again. **The only detector that sees persistence WITHOUT
escalation** — on 4 of 20 episodes nothing else in the engine fires at all.

## Current logic
1. All session trades on the same **underlying** (any strike or expiry) plus the
   current one.
2. Fires when `losses >= obsession_min_losses` (3).
3. Severity: **`danger` if `max(qty) > qty[0]`**, else `caution`.
4. Records `concurrent_pairs` — attempts held simultaneously rather than
   sequentially.
5. Dedup key carries the underlying; re-arms on **severity escalation only**.

## Constants
| key | value | why |
|---|---|---|
| `obsession_min_losses` | 3 | definitional — what "repeatedly" means |
| ~~`obsession_min_reentries`~~ | **deleted** | unreachable: `losses ≥ 3` implies `reentries ≥ 2` |

Severity uses **no constant** — `max(qty) > qty[0]` is the identity. A loss-count
tier was tested and **rejected**: `{3:11, 4:6, 5:2, 6:1}` is a smooth decay with
no break anywhere.

## Replay (corrected 203-session baseline)
**22 alerts / 21 days** · danger 17 · caution 5
**0 firings** now peak mid-episode and score caution (was 8). Severity can no
longer fall as an episode grows.

## Why exit-triggered, not entry
Measured: entry-triggering would fire **later in 14 of 20 episodes** (up to 155
min) and **never in 6**. Earlier in **zero**. You cannot know a position lost
until it closes. The exit alert still precedes another attempt in **70%** of
episodes, median **17 minutes**.

## Limitations
- Premise unsupported by averages: returning to an underlying is 31.9% after a
  loss vs 33.6% after a win. Counts a thing that happens, not an elevated
  tendency. Kept because the tail is real (₹7,784 · ₹7,745 · ₹6,251).
- Overlapping positions count as attempts (24 of 49 firings) — recorded, not
  excluded.

Detail: `same_symbol_obsession_review.md` · `same_symbol_obsession_contract.md`
