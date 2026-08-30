# The temporal contract of "prior trade"

**Investigation, 30 Aug 2026.**

> **IMPLEMENTED 30 Aug, approved.** `EngineContext.concluded_before_entry`
> provides CONCLUDED once. `martingale_behaviour` and `post_loss_recovery_bet`
> were migrated as the defects; `revenge_trade` and `rapid_reentry` moved onto
> the same relation with firing sets provably unchanged. Existence detectors
> untouched. Measured on the real book, every prediction in §5 matched exactly:
> martingale **32 → 26**, post_loss 7 → 7, revenge 182 → 182, rapid_reentry
> 14 → 14, and all eight existence detectors unmoved. The semantic baseline is
> byte-identical. Pinned by `backend/tests/test_temporal_contract.py` (22 tests,
> including all five shapes below). **CONCURRENT remains unnamed and open.**

Opened because the `as_of` boundary fix (`dfb4456`) removed every *future*
trade from `session_trades` but left 5 look-ahead cases in the retired Pattern
20 detector — and a stricter boundary rule would only have reached 3. That said
the remaining class is **not a boundary property**. This investigation asks what
it actually is.

The answer is that **"prior" is three different relations, the engine has one
word for all three, and conflating them is a live defect in a live alerting
detector** — not a curiosity about a retired one.

---

## 1. The 5 cases, in full

Every cited "prior loser", with its lifetime against the trade it was used to
explain:

| # | date | current (entry→exit) | cited prior (entry→exit) | relation |
|---|---|---|---|---|
| 1 | 2025-04-03 | `NIFTY…23300CE` 13:29→13:34 | `NIFTY…23200PE` 13:29→13:33 | **entered the same minute** |
| 2 | 2025-05-13 | `SENSEX…82700CE` 11:13→11:28 | `SENSEX…83000CE` 09:26→09:33 | concluded before — fine |
| | | | `SENSEX…80700PE` 11:13→11:28 | **identical lifetime** |
| 3 | 2025-05-21 | `DIXON…18000CE` 12:08→15:09 | `DIXON…17500CE` 11:01→15:09 | **still open at entry** |
| 4 | 2025-09-09 | `NIFTY…24950CE` 09:26→14:25 | `NIFTY…25000CE` 09:15→14:03 | **still open at entry** |
| 5 | 2025-09-16 | `NIFTY…25100PE` 10:16→11:22 | `NIFTY…25000PE` 10:17→11:22 | **entered a minute later** |

### Was the previous position actually still open when the new trade was entered?

**In 3 of 5, yes — literally open** (cases 2b, 3, 4). In the other 2 the "prior"
**had not been entered yet** (cases 1, 5).

### Can we legitimately call it a re-entry after a loss?

**No. In none of the five.** In every case the loss was unknown at the moment of
the entry it was used to explain — either because the position was still open,
or because it did not yet exist.

Cases 1, 5 and 2b are not sequential decisions at all. A CE and a PE on one
underlying entered in the same minute and closed in the same minute is a
**straddle**; two adjacent strikes a minute apart, closed together, is a
**spread or a scale-in**. Those are *one* decision expressed in two rows.

### Should the event only become eligible once the previous position was closed?

**Yes — and closed strictly before the new entry**, which is stronger than
"closed". Case 3 shows why: the prior closed at 15:09, the current was entered
at 12:08, and they closed in the same minute. "Closed at some point" is
satisfied; the trader still could not have known the loss when they entered.

The correct predicate is the one `revenge_trade` already uses:

```python
t.exit_time < ct.entry_time
```

---

## 2. Three relations, one word

| relation | predicate | question it answers |
|---|---|---|
| **OCCURRED** | `t.exit_time <= ct.exit_time` | did this trade happen in the session by now? |
| **CONCLUDED** | `t.exit_time < ct.entry_time` | was its outcome knowable when this decision was made? |
| **CONCURRENT** | lifetimes overlap | are these one decision expressed as several rows? |

**OCCURRED is the boundary already fixed.** It is right for counting: a trade
entered after this one but closed before it *is* one of today's trades, and
`overtrading_burst` counting it is correct.

**CONCLUDED is required by any detector whose message says "after X, you did
Y".** That is a causal claim, and it is false unless X had concluded.

**CONCURRENT is neither prior nor subsequent.** Nothing in `session_trades`
expresses it, which is why the straddle legs in cases 1/5 were read as a
sequence.

Applying CONCLUDED globally is **wrong** and measured so — it changes existence
detectors that have no causal claim to make:

| detector | OCCURRED | CONCLUDED | verdict |
|---|---|---|---|
| `overtrading_burst` | 13 | 2 | **CONCLUDED is wrong** — a burst is clustering of entries |
| `fomo_entry` | 32 | 24 | **CONCLUDED is wrong** — it counts entries in a window, and already bounds them at `ct.entry_time` |
| `end_of_session_mis_panic` | 1 | 0 | **CONCLUDED is wrong** — counts late MIS entries |
| `same_symbol_obsession` | 49 | 45 | **CONCLUDED is wrong** — persistence is existence |
| `martingale_behaviour` | 32 | 26 | **CONCLUDED is RIGHT** — see §3 |

So the answer to *"can we establish one canonical temporal concept"* is **no —
and that is the finding.** There are three, each detector needs a specific one,
and the bug is that the engine offers only an undifferentiated list.

---

## 3. THE LIVE DEFECT — `martingale_behaviour`, 9 of 32 firings

Not a retired-detector curiosity. `martingale_behaviour` is **live, alerting,
and one of the largest `danger` sources in the engine.**

```python
prior = sorted([t for t in ctx.session_trades if t.id != ct.id and t.exit_time],
               key=lambda t: t.exit_time)
run = 0
for t in reversed(prior):
    if float(t.realized_pnl or 0) < 0: run += 1
    else: break
```

A trailing run of consecutive losses, with **no entry guard**. Its claim is
explicitly causal — size escalated *after* a run of losses.

**9 of its 32 firings rest on at least one loss that concluded after the entry
it explains:**

```
2025-07-28  SENSEX25JUL81500PE   entered 09:15
    cited loss ALKEM25JUL5100CE        exited 10:43   =  88 min AFTER that entry
    cited loss DIXON25JUL17000CE       exited 10:32   =  77 min AFTER
    cited loss SHRIRAMFIN25JUL640CE    exited 10:15   =  60 min AFTER

2025-09-19  EICHERMOT25SEP7050CE entered 09:39
    cited loss LT25SEP3750CE           exited 11:44   = 125 min AFTER
```

A trade entered at 09:15 is being explained by a loss the trader did not see
until 10:43. **The alert states a cause that had not happened.**

Applying CONCLUDED leaves **26 firings (−6)**; three more survive with a shorter
run and different evidence.

### `post_loss_recovery_bet` — same code shape, 0 affected today

```python
prior = sorted([... same underlying ...], key=lambda t: t.exit_time)
last_two_pnls = [... for t in prior[-2:]]
if not all(p < 0 for p in last_two_pnls): return None
```

Identical structure, identical causal claim ("after 2+ losses, one oversized
bet"), **identical absence of a guard**. It happens to be unaffected on this
book — 0 of 7 firings. **That is luck, not protection**, and it is exactly the
kind of latent defect that appears when the book changes.

### `rapid_reentry` — accidentally safe

```python
gap_min = (ct.entry_time - last_same.exit_time).total_seconds() / 60
if 0 <= gap_min <= window:
```

The `0 <=` rejects a negative gap, so an unconcluded prior cannot fire it. The
protection is real but **incidental** — it reads as a range bound, not as a
temporal contract, and nothing records that removing it would reintroduce the
defect.

---

## 4. Does changing the rule affect other detectors?

**Yes, and this is why it must be central rather than per-detector.** Every
detector that needs CONCLUDED currently re-derives it, or fails to:

| detector | needs | has | status |
|---|---|---|---|
| `revenge_trade` | CONCLUDED | `t.exit_time < ct.entry_time` | correct, explicit |
| `constitution_violation` (cooldown) | CONCLUDED | `t.exit_time <= ct.entry_time` | correct, explicit — **but `<=` not `<`** |
| `rapid_reentry` | CONCLUDED | `0 <= gap_min` | correct, **incidental** |
| `martingale_behaviour` | CONCLUDED | — | **DEFECT, 9 of 32** |
| `post_loss_recovery_bet` | CONCLUDED | — | **DEFECT, latent** |
| `options_premium_avg_down` | CONCLUDED | — | defect, retired |
| `overtrading_burst` | OCCURRED | boundary | correct |
| `fomo_entry` | OCCURRED (entry window) | explicit bounds | correct |
| `end_of_session_mis_panic` | OCCURRED | boundary | correct |
| `same_symbol_obsession` | OCCURRED | boundary | correct |
| `win_rate_collapse`, `strategy_breakdown` | OCCURRED | boundary | correct |
| `constitution_violation` (trade count) | OCCURRED | boundary | correct |

**Four different spellings of one idea across three correct detectors, and two
detectors that simply forgot.** That is the definition of a concept that should
be provided once.

Note also `constitution_violation` uses `<=` where `revenge_trade` uses `<`. At
identical timestamps — a close and an entry in the same second — they disagree.
Nothing decides which is right today.

---

## 5. Proposed central contract — NOT IMPLEMENTED

Provide the relations once, on `EngineContext`, and let each detector declare
which it needs:

```python
ctx.session_trades          # OCCURRED — unchanged, already bounded by as_of
ctx.concluded_before_entry  # CONCLUDED — t.exit_time < ct.entry_time
ctx.concurrent_with         # CONCURRENT — overlapping lifetimes
```

Computed once per context build, not per detector. Then:

- `martingale_behaviour` and `post_loss_recovery_bet` read
  `concluded_before_entry` instead of `session_trades`.
- `revenge_trade`, `constitution_violation` and `rapid_reentry` read the same
  property instead of three hand-written predicates — **their firing sets must
  not move**, which is the regression test.
- Existence detectors keep `session_trades` and are untouched.

**Blast radius, measured:**

| | |
|---|---|
| `martingale_behaviour` | **32 → 26 firings** (−6); 3 more change evidence |
| `post_loss_recovery_bet` | 7 → 7 (latent defect closed, no visible change) |
| `revenge_trade` | 182 → 182, **must not move** |
| `constitution_violation` | unchanged, **pending the `<` vs `<=` decision** |
| `rapid_reentry` | 14 → 14, guard becomes explicit |
| every existence detector | unchanged |

**This changes live product behaviour** — 6 fewer `martingale_behaviour` alerts
on the reference book, all of them alerts that named a cause which had not
happened. That is a correctness improvement, but it is a behaviour change and
needs your approval rather than my judgement.

### Open question the investigation cannot decide

**CONCURRENT is unhandled and no detector currently declares it.** Cases 1, 5
and 2b were straddle and spread legs read as a sequence. `strategy_group`
already exists for structures, but `session_trades` does not express it, and no
live detector was measured as affected. Recorded as a separate question rather
than folded in — building a third relation nothing yet consumes would be
speculative.

### What is NOT proposed

- No threshold, severity or copy change.
- No detector merged or retired.
- **No patch aimed at the 5 Pattern 20 cases.** That detector is retired; those
  cases mattered only as the symptom that exposed `martingale_behaviour`.
