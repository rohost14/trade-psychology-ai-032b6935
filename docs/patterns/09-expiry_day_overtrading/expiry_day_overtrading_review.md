# Pattern #9 — `expiry_day_overtrading` · review

27 Aug 2026. Detector `1.0.0`, `behavior_engine.py:2771`. Measured against the
corrected book: **189 sessions, 912 positions**. Replay reference: **28 alerts /
28 days** of 203 sessions.

**No code changed. Findings only.**

---

## Current behaviour

```
guard    instrument_type in (CE, PE, FUT)  and  is_expiry_day(symbol, entry_date)
subject  today's trades on the SAME UNDERLYING, counted as structures not legs
gate     entry_ist.hour < 13  ->  silent            ("cold start")
danger   today_count >= 8
caution  today_count >= 5  OR  today_lots >= 10
```

`today_lots = sum(total_quantity)`. `today_count = count_structures(...)` so a
recognised multi-leg spread is one decision, not four.

The three constants live in `trading_defaults.py:181-183` and are declared in
`threshold_registry.py:148-165` as `Kind.PERSONAL_BASELINE`, `Source.HISTORY`,
percentile 75 / 90 / 75.

---

## What is correct

- **The guard is right.** `is_expiry_day` parses the symbol's own expiry and
  handles weekly, monthly and holiday-shifted expiries. No `weekday() == 3`
  hardcoding.
- **Same-underlying scoping is right.** NIFTY expiry activity is not evidence
  about a SENSEX position.
- **Structures, not legs.** `count_structures` collapses a recognised spread to
  one decision, so a condor is not four trades. The count can only fall, so this
  can only make the detector quieter.
- **The detector is pure.** No DB, no Redis, no network, no clock. Everything
  comes from `ctx`. Safely replayable, safely testable.
- **The registry `PatternCopy` is clean** — *"Expiry-day activity" / "Trades and
  lots on an instrument expiring today." / "Expiry-day options move on time
  decay as much as direction, and the clock does not reverse."* No statistics,
  no intent claim. **The problem is not here.**
- **Dedup works.** Key is `pattern_type` alone, 24 h, no `_WORSEN_METRIC` entry.
  55 raw detections collapse to **28 alerts on 28 days** — one per day, with one
  caution→danger escalation. This is not a per-trade spammer.

---

## Problems found

### P1 — the detector has no discriminative power. It is a filter.

| | |
|---|---|
| expiry-day positions in the book | 142 (16% of all) |
| entered before 13:00, excluded by the gate | 87 |
| **eligible: expiry + CE/PE/FUT + entry ≥ 13:00** | **55** |
| **of those, the detector fired on** | **55** |
| of those, the detector stayed silent on | **0** |

**It fires on 100% of the positions it is allowed to judge.** The trade-count
logic never decides anything. What the detector actually says is *"you traded an
expiring instrument in the afternoon"* — a fact about the calendar, not a
finding about behaviour. A detector that never says no is not measuring
anything.

### P2 — `today_lots` is in contracts, not lots. That is why P1 happens.

`total_quantity` is contracts — `completed_trade.py:34` says so explicitly:
*"Peak position size (in units, lot_size already factored)"*. A NIFTY lot is 75
contracts, SENSEX 20. The constant it is compared against is **10**.

```
total_quantity on expiry positions:  min 20   median 150   max 1500
single positions already clearing the "10 lot" line:  142 of 142  (100%)
```

The `today_lots >= 10` clause is not a threshold. It is `True`. **71% of firings
(39 of 55) came from the lots clause alone with a trade count under five**, and
the count at firing was **1 on eight occasions** — a detector named
*overtrading* firing on the trader's first expiry trade of the day.

The number is also **shown to the trader**, mislabelled:

```
[caution] 1 NIFTY trades / 750 lots today on expiry. ...
[caution] 3 NIFTY trades / 2250 lots today on expiry. ...
[caution] 2 SENSEX trades / 220 lots today on expiry. ...
```

750 contracts is 10 NIFTY lots. The trader is shown a number inflated by the lot
size — 75× for NIFTY, 20× for SENSEX — beside the word "lots". Median true size
in this book is **3 lots**; the message would call it 150.

### P3 — two fabricated statistics are presented to the trader as sourced fact

```python
danger : "NSE data: retail option activity in the last 2 hours of expiry day
          has a structural loss rate above 85%."
caution: "Each additional trade after 13:00 on expiry day statistically
          reduces your edge."
```

plus the code comment *"0DTE herding: NSE data shows retail activity spikes 3-5×
near expiry EOD."*

**There is no source.** The 85% figure traces to exactly one place in the repo —
`docs/archive/PATTERN_REFERENCE.md:513`, an **archived** document that asserts
"NSE market data shows" and cites nothing. No primary source, no study, no link.
The chain terminates in our own prose.

Both statements are falsifiable, and **both are false on this book** — see
Evidence. The second is not merely unsupported; the measured effect runs the
other way.

This is not confined to the alert list. `alert.message` becomes
`pattern.description` (`Alerts.tsx:486`) and renders in `Alerts.tsx:257`,
`AlertDetailSheet.tsx:267`, `AlertHistorySheet.tsx:78`, and the merged push body
(`trade_tasks.py:1238`). **`AlertDetailSheet.tsx:208` also pastes it into the AI
coach prompt** — *"I got a ... alert — {description} Can you explain what this
means for my trading?"* The invented statistic is fed to the model as context
and will be elaborated on.

### P4 — all three thresholds are declared personal and can never become personal

`expiry_day_trades_p75`, `expiry_day_trades_p90` and `expiry_day_lots_p75` are
**produced by nothing**. Verified by grep across `backend/` excluding the
registry itself: **0 occurrences each.**

So `Kind.PERSONAL_BASELINE` with `Source.HISTORY` is a description of an
intention. The resolution ladder finds no metric and falls through to the
hardcoded 5 / 8 / 10 permanently, for every trader, forever. Same defect class
as Pattern 7's `fomo_underlyings_*`.

The values themselves are unsourced round numbers with no derivation recorded.

### P5 — 25 of the 28 alert-days already carried another alert

From the 203-session replay artifact:

```
days with an expiry alert                          28
  expiry_day_overtrading was the ONLY alert         3
  co-firing:  adding_to_adverse_position 16 · options_premium_avg_down 13
              martingale_behaviour 11 · death_spiral 9 · same_symbol_obsession 8
              size_escalation 7 · direction_instability 4 · ...
```

On 89% of the days it speaks, detectors that are actually measuring a decision
have already spoken. It contributes a `danger`-domain vote to `death_spiral` on
those days without contributing a finding.

---

## Evidence

Everything below is this trader's book. Permutation tests, 20,000 resamples,
seed 7.

### The 85% claim

| entry window on expiry day | n | measured loss rate | claim |
|---|---|---|---|
| 13:00 or later | 55 | **61.8%** | >85% |
| 14:00 or later — the true "last 2 hours" | 26 | **53.8%** | >85% |
| 15:00 or later | 7 | **57.1%** | >85% |

Overstated by 23–31 points. The book-wide loss rate is ~60%, so the trader's
last-two-hours expiry trading is **not distinguishable from their ordinary
trading**, let alone catastrophic.

### "Each additional trade after 13:00 reduces your edge"

| nth post-13:00 expiry trade | n | win rate | mean P&L |
|---|---|---|---|
| 1 | 28 | 25.0% | −₹456 |
| 2 | 12 | 33.3% | −₹163 |
| 3 | 7 | 57.1% | −₹280 |
| 4 | 5 | 80.0% | +₹612 |
| 5 | 2 | 50.0% | +₹420 |
| 6+ | 1 | 100.0% | +₹38 |

**Correlation of trade-number with P&L: r = +0.260, p = 0.056, n = 55.**

The claim asserts r < 0. The observed sign is **positive**, and at n=55 it is
close to conventional significance in the direction *opposite* to the sentence
shown to the trader. This is not "insufficient evidence to confirm" — the
estimate points the other way.

### Is post-13:00 expiry trading worse at all?

| comparison | difference | p |
|---|---|---|
| post-13:00 expiry vs pre-13:00 expiry, mean P&L | −₹289/trade | 0.231 |
| post-13:00 expiry vs all non-expiry, mean P&L | −₹58/trade | **0.863** |
| post-13:00 expiry vs pre-13:00 expiry, win rate | −7.8 pp | 0.381 |
| post-13:00 expiry vs all non-expiry, win rate | −1.2 pp | **0.885** |

Against the population the alert implicitly contrasts with — the rest of the
trader's trading — the effect is **₹58 per trade at p = 0.86**. Nothing.

### The fair test: is a heavy expiry session a worse session?

The detector is about *volume*, so test volume at the day level.

| expiry trades that day | days | mean session P&L | mean expiry P&L |
|---|---|---|---|
| 1 | 10 | −₹272 | −₹802 |
| 2 | 12 | −₹604 | −₹223 |
| 3 | 6 | −₹1,717 | −₹254 |
| 4 | 8 | **+₹1,128** | +₹1,179 |
| 5+ | 9 | +₹126 | −₹562 |

**Expiry-trade-count vs session P&L: r = +0.107, p = 0.485, n = 45.** Again the
wrong sign for the hypothesis, and nowhere near significant.

### And expiry days are this trader's *better* days

| | n | green days | mean session P&L |
|---|---|---|---|
| sessions with expiry-day activity | 45 | **51.1%** | **−₹225** |
| sessions with none | 144 | 38.9% | −₹912 |

Difference +₹688/session, p = 0.465 — not significant, but the direction is
consistent with everything above and flatly inconsistent with the detector.

### Would fixing the units rescue it?

Dividing by real lot sizes (NIFTY 75, BANKNIFTY 35, FINNIFTY 65, MIDCPNIFTY 140,
SENSEX 20, BANKEX 30):

```
true lots per position:  min 1   median 3   max 20
single positions at/above 10 TRUE lots:              17 of 142  (12%)
eligible trades whose CUMULATIVE true lots >= 10:    32 of 55   (58%)
```

A units fix moves the pass rate from 100% to 58%. **That restores discrimination
but does not create a finding** — there is nothing for the threshold to separate,
because the sections above show no outcome difference to separate on. It would
make a meaningless alert fire less often.

### Limits of this evidence

- **n = 55 eligible positions, 45 expiry-active sessions, one trader.** Small.
  No single test here would be decisive alone.
- What makes it decisive is **consistency of sign**: trade level, trade
  sequence, day level and day-type all point the same way, and it is the
  opposite of the direction the detector asserts. Four independent looks do not
  accidentally all lean against the hypothesis.
- **A market-wide claim about retail expiry losses may well be true.** SEBI's
  published F&O studies say most retail derivative traders lose money. That is
  not what this detector says. It says *this trader's* expiry afternoon is
  dangerous and *each additional trade* makes it worse, and it says so with a
  specific number we invented. P1's 100% pass rate is independent of any of
  this: whatever the market does, a detector that never withholds is not
  detecting.
- **Not tested:** intraday timing within the afternoon, position hold duration on
  expiry, and whether expiry-day behaviour differs during a drawdown.

---

## Recommended behavioural contract

**The trader's expiry-day trade count is not evidence about their state, and we
should stop saying it is.**

Expiry-day-ness is real and useful — but as **context that changes another
detector's arithmetic**, which is exactly how the engine already uses it:

- `premium_loss_event` shifts its bands +15 pp on expiry day
  (`premium_loss_expiry_shift_pct`)
- `no_stoploss` uses `no_stoploss_expiry_loss_pct` / `_hold_min`
- `fomo_entry` retains expiry as a `context_note` after Pattern 7 collapsed it
  to one threshold

That is the correct role, and it is already filled. A standalone alert that
counts expiry trades adds a filter, two invented statistics and a wrong number,
and on 89% of the days it speaks it is speaking over detectors that have actually
found something.

**Recommendation: RETIRE `expiry_day_overtrading` as a behavioural alert**, on
the Pattern 4 / Pattern 6 precedent, and keep expiry-day-ness where it already
lives — as a modifier inside detectors that measure a decision.

If the pattern is kept instead, **P2 and P3 are not optional**: the engine must
not display a fabricated statistic or a number mislabelled by a factor of 75.

---

## Exact changes required

Three mutually exclusive options. **Nothing below is implemented.**

### Option A — RETIRE (recommended)

1. Delete `_detect_expiry_day_overtrading` (`behavior_engine.py:2771-2830`).
2. Remove the `DetectorSpec` (`detector_registry.py:194`) and the `PatternCopy`
   (`:411`); leave a retirement note as Patterns 4 and 6 did.
3. Delete the three constants (`trading_defaults.py:181-183`) and their three
   `_spec` entries (`threshold_registry.py:148-165`) — with the three phantom
   metrics, nothing else reads them.
4. Update the engine header comment (`behavior_engine.py:41`) and the pattern
   count: **25 detectors, 31 pattern types** (`all_pattern_types()` stays the
   authority).
5. Confirmation replay. Expected: **−28 alerts**, and a `death_spiral` fall as an
   *arithmetic consequence* of one fewer danger-domain contributor on those 9
   co-firing days, exactly as in Pattern 8.

**Not** to be deleted: `is_expiry_day`, `count_structures`, and every
expiry-modifier threshold in other detectors. All have other readers.

### Option B — demote to analytics, Pattern 8's treatment

Keep the measurement, stop the alert: severity → `info`, disposition →
`analytics`, `notification_level` → 0, and **delete both statistical sentences**
from the message regardless. Preserves the expiry-activity count for Reports
without asserting anything. Costs the same 28 alerts.

### Option C — minimum honest fix, if the alert is kept

Only if the pattern stays an alert. Does not address P1 or P4.

1. **Fix the units.** Either rename `today_lots` → `today_contracts` and the
   constant to match, or divide by a real lot size. Contracts compared against 10
   is a bug either way.
2. **Delete both statistics.** Replace with what we can prove: *"N NIFTY trades
   today on an instrument expiring today."* Delete the "3-5× herding" comment.
3. **Reclassify the three thresholds** from `PERSONAL_BASELINE` to `FALLBACK`
   until a producer exists for their metrics — the Pattern 7 treatment of
   `fomo_symbols_in_window`. Declaring a value personal when it can never
   personalise is a false statement in the registry.

---

## Verdict

**RETIRE as a behavioural detector.** Option A.

The detector fires on **100% of the 55 positions it can see** and never
withholds, because a contracts-vs-lots units bug makes its only reachable
condition unconditionally true. Its two trader-facing statistics have no source
outside our own archived prose, and both are wrong when measured: the claimed
>85% loss rate is 54–62%, and "each additional trade reduces your edge" runs at
**r = +0.260** — the opposite sign. At day level the same reversal holds
(r = +0.107), and this trader's expiry-active sessions are their **better**
sessions (51.1% green vs 38.9%). Its three thresholds are declared personal
against metrics no code produces. On 25 of the 28 days it alerts, a detector that
measured an actual decision had already spoken.

Retiring it costs 28 alerts and no information. Expiry-day-ness stays where it
belongs and already works — as a modifier inside `premium_loss_event`,
`no_stoploss` and `fomo_entry`.

**Recorded for later reviews, not fixed here:**

- `opening_5min_trap` carries the same defect class — *"NSE data: 78% of retail
  opening-5-min derivative trades are unprofitable"* in `behavior_engine.py` and
  an equally unsourced entry in the archived reference. To be reviewed on its own
  turn; the claim should be checked then.
- `AlertDetailSheet.tsx:208` pastes raw `alert.message` into the coach prompt.
  Worth a policy decision independent of this pattern: whatever the engine writes
  becomes model context.
