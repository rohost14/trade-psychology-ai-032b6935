# Pattern #8 — `premium_loss_event` · **COMPLETE (KEEP AS-IS)**

27 Aug 2026. Verdict **KEEP AS-IS** — the first detector in this series to
survive its evidence intact. Three non-behavioural cleanup items applied.
Evidence in `premium_loss_event_review.md`.

---

## Current behaviour — unchanged

```
guard      instrument_type in (CE, PE) AND direction == LONG
loss_pct   from stored pnl_pct, else (exit - entry) / entry
cap        loss_pct > 100  ->  clamp to 100 + WARN
bands      caution 40   danger 60   critical 80      (% of the premium PAID)
expiry     all three +15pp on the instrument's own expiry day
repeat     another LONG option today already past danger  ->  danger becomes critical
flag       hold < 30 min  ->  fast_collapse (evidence only, never severity)
```

**Nothing behavioural moved:** bands, expiry shift, repeat logic, severity
mapping and trigger timing are all exactly as they were.

## Why it was kept

| | |
|---|---|
| long options in the book | 888 of 912 positions (97%) |
| that lose ≥40% of premium | **57 — 6.4%** |
| detections | 48 on 39 of 189 sessions |
| **realized loss on flagged trades** | **−₹238,623** |
| book's gross loss | −₹690,545 |
| **share of all money lost** | **35%, from 5% of positions** |
| of the 48 worst positions by money | captures **83%** |

**Severity tracks magnitude** — caution median −₹3,011 at 54.4% of premium,
danger −₹3,218 at 70.6%, critical −₹5,670 at 85.5%. Critical's median loss is
**1.9× caution's**. No other reviewed detector has a tier that ranks money.

## What changed — cleanup only

**1. The stale `MANDATORY_REVIEW` flag is cleared.** `premium_loss_caution_pct`
was flagged as *"firing routinely without behavioural failure"*. Measured, only
6% of long options reach it, so the flag is **refuted, not confirmed** — and it
was removed rather than kept, because the other three entries in that set exist
to outlive constants that were *deleted*. This one is still in the code and
vindicated; an open-concern marker on it would be false. The reasoning note
above `_UNIVERSAL_SAFETY` was rewritten to record the outcome while keeping its
more important half: *"KIND IS NOT VALUE… a wrong number of the right kind is
still the right kind."*

**2. The two unsourced constants say so.** `premium_loss_expiry_shift_pct` (15)
and `premium_loss_fast_hold_min` (30) are marked `UNSOURCED` in
`trading_defaults.py`, with what is and isn't established: the expiry shift's
*direction* is well argued and engages on 12 of 48 firings, its *magnitude* has
no derivation; the fast-hold flag never touches severity, so the cost of it
being wrong is one wrong word in a message. **The repeat rule's `>= 1` is an
inline literal with no key and no source** — recorded at the code site, with the
measurement that makes it load-bearing (5 engagements, 2 promotions, so 2 of the
10 criticals come from it rather than from magnitude).

**3. The exit-time message no longer reads as live.** The median flagged trade
was held **1,341 minutes** — overnight — and the message was in the present
tense for a position that no longer existed.

| | |
|---|---|
| before | `NIFTY…CE: 85% of premium lost (₹6,375) in 10min — fast collapse, likely bought into peak IV.` |
| after | `Closed NIFTY…CE having lost 85% of the premium paid (₹6,375), held 10 min.` |

*"likely bought into peak IV"* went with the rewrite: the hold time is observed,
the reason for it is not, and this detector cannot see implied volatility at
entry. That was a judgement call slightly beyond the literal instruction, made
because it is the same unsupported-cause class the series has removed from every
other pattern's copy.

## Tests

`tests/test_premium_loss_event.py` — **31 tests, the detector's first.** They
pin the unchanged behaviour as firmly as the cleanup: the 40/60/80 bands
parametrised across nine boundary values, the constants, `UNIVERSAL_SAFETY`, the
long-only and options-only guards, the repeat rule in all four of its states,
the >100% cap, and purity. Plus the three cleanup items — the flag cleared while
the three retired entries survive, both constants marked `UNSOURCED`, the inline
literal recorded, the message describing a closed position, and no speculation
about why.

**Full backend suite: 1,373 passed, 0 failed.**

## Limitations, recorded not closed

1. **Exit-path dedup is account-scoped, so a second bleeding position is
   swallowed.** `_pattern_dedup_key` has no branch for this pattern, so the key
   is `"premium_loss_event"` alone. On the reference book **8 of 39 alert-days
   had two or more qualifying long options, and 7 detections were suppressed** —
   including `MAZDOCK25OCT3400CE` at **86.7%, critical**, silenced because
   another position had already alerted that day.
   **The live path does not have this bug**: `position_monitor_tasks._scope`
   keys on `(rule, symbol)`, and its comment records fixing exactly this. The
   exit path was never given the same treatment. **This is the strongest
   candidate for the next change to this detector** and was left alone only
   because the review's verdict was KEEP AS-IS and dedup is not a threshold.
2. **Averaging down silences it.** `loss_pct` is measured against
   `avg_entry_price`, so adding to a losing option lowers the average and the
   percentage the detector reads *falls* while the rupee loss *grows*. Worked
   example: one lot at 100, price 50 → 50% loss, fires. Add one lot at 50 →
   average 75, same price → **33.3%, silenced.** `adding_to_adverse_position`
   fires on the add itself, so the behaviour is not invisible to the engine —
   but this detector goes quiet at the moment the position gets bigger.
3. **The exit path reports what is over.** The live variant on the 60-second
   beat is the actionable one; this is the record.
4. **40 / 60 / 80 are round numbers.** They select the top 6% of outcomes and
   35% of the losses on the only book we have, which is evidence they are not
   badly wrong, not evidence they are right.
5. **Not guardian-eligible**, and **not the only source of `critical`** —
   `constitution_violation` and `death_spiral` emit it too. The REVIEW STATUS
   note claiming otherwise was wrong and is corrected.
6. **No replay confirmation**, same blocker as Patterns 6 and 7
   (`ENGINE_BACKLOG` M-1, stopped Memurai).
