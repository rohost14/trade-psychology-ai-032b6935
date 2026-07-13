# Behavioral Engine v2 — Pattern Specification (Document 1)

Status: Design Specification
Scope: Existing 24 patterns only
Goal: Define which patterns survive, merge, move to analytics, and how each should work in production.

---

# Core Principle

Every pattern must belong to ONE of these categories:

1. Universal Risk

   * Dangerous regardless of trader type.
   * Examples: Excess exposure, session meltdown.

2. Personal Baseline

   * Fires when trader behaves unusually relative to themselves.
   * Examples: Overtrading, unusual sizing.

3. Constitution Violation

   * Trader violates self-defined rules.
   * Examples: Cooldown violation, max trades/day.

No pattern should rely entirely on a fixed hardcoded number.

Hierarchy:

User Constitution
↓
Personal Baseline
↓
Universal Defaults

---

# Pattern 1 — Consecutive Loss Streak

Status: KEEP

Current Problems:

* Fixed 3 / 5 thresholds
* No trade references
* Doesn't consider size of losses

Production Logic:

Trigger Score Based

Signals:

* Consecutive losses
* Total loss amount
* Loss % of capital
* Same-symbol repetition
* Increasing trade frequency

Alert Levels:

Low:

* Constitution threshold exceeded

Medium:

* Constitution exceeded
* Session P&L negative

High:

* Constitution exceeded
* Position sizing increasing

Required Context:

* Loss trades list
* Symbols
* P&L
* Time

Type:

* Emotional Trading

Notification:

* High only

---

# Pattern 2 — Revenge Trade

Status: KEEP

Current Problems:

* 20 min hardcoded
* ₹500 hardcoded
* Timing alone is weak

Production Logic:

Use confidence score.

Signals:

* Recent loss
* Re-entry speed
* Same underlying
* Larger position size
* Session red
* Same symbol

Confidence:

0-100

Only alert >70

Required Context:

* Losing trade
* New trade
* Size comparison

Type:

* Emotional Trading

Notification:

* High confidence only

---

# Pattern 3 — Overtrading Burst

Status: KEEP

Current Problems:

* 5 trades fixed
* Scalper false positives

Production Logic:

Compare:

Current 30-min trade count

vs

Personal burst baseline

Fallback:

* Universal default

Separate into:

A. Burst Overtrading
B. Daily Overtrading

Type:

* Personal Baseline

Notification:

* Burst only

---

# Pattern 4 — Size Escalation

Status: KEEP

Current Problems:

* Cross instrument comparison
* Raw quantity comparison

Production Logic:

Must compare:

Position Risk %

not quantity

Sequence:

Loss
↓
Loss
↓
Loss

Position size increasing

Same underlying required.

Type:

* Emotional Trading

Notification:

* In-app

---

# Pattern 5 — Rapid Reentry

Status: KEEP

Change:

Analytics only.

Reason:
Many profitable traders re-enter.

Use:

* Same symbol
* Same underlying

Track frequency.

Type:

* Analytics

Notification:

* None

---

# Pattern 6 — Panic Exit

Status: KEEP

Change:
Analytics only.

Never push.

Exclude:

* SL triggered exits

Signals:

* Hold duration
* Loss size
* Exit reason

Type:

* Analytics

Notification:

* None

---

# Pattern 7 — Martingale Behaviour

Status: KEEP

Very Important

Logic:

Same underlying

Loss
↓
Increase size
↓
Loss
↓
Increase size

Use Risk %

not quantity.

Type:

* Universal Risk

Notification:

* Push

---

# Pattern 8 — Cooldown Violation

Status: REDESIGN

Only exists if user enabled cooldown.

Otherwise disabled.

Logic:

Trade entered during user cooldown.

Type:

* Constitution Violation

Notification:

* Push

---

# Pattern 9 + Pattern 16

Rapid Flip
Options Direction Confusion

Status: MERGE

New Pattern:

Direction Instability

Levels:

Level 1:

* Exact instrument reversal

Level 2:

* Underlying reversal

Level 3:

* Multiple flips

Type:

* Emotional Trading

Notification:

* In-app

---

# Pattern 10 — Excess Exposure

Status: KEEP

Split Into:

A. Position Risk

Single position too large.

B. Portfolio Concentration

Single underlying dominates account.

Use:

* Open positions
* Capital

Never fixed rupees.

Type:

* Universal Risk

Notification:

* Push

---

# Pattern 11 — Session Meltdown

Status: KEEP

Highest Priority

Logic:

Current drawdown

vs

Daily loss limit

Sources:

1. Constitution
2. Baseline
3. Default

Type:

* Universal Risk

Notification:

* Push
* Guardian

---

# Pattern 12 — FOMO Entry

Status: KEEP

Current logic weak.

Add:

* Multiple underlyings
* Session negative
* High frequency

Confidence model.

Type:

* Emotional Trading

Notification:

* In-app

---

# Pattern 13 — No Stoploss

Status: KEEP

Very Valuable

Logic:

Large loss

AND

No SL order

Adjust for:

* Expiry proximity
* Instrument type

Type:

* Universal Risk

Notification:

* Push

---

# Pattern 14 — Early Exit

Status: KEEP

Move entirely to EOD Analytics.

Compare:

Winner hold time

vs

Loser hold time

Type:

* Analytics

Notification:

* None

---

# Pattern 15 — Winning Streak Overconfidence

Status: KEEP

Logic:

Winning streak

AND

Current position larger than normal

Compare against:

Personal sizing baseline

Type:

* Emotional Trading

Notification:

* High confidence only

---

# Pattern 17 — Options Premium Average Down

Status: KEEP

Logic:

Loss
↓
Re-enter
↓
Same direction
↓
Same underlying

Type:

* Emotional Trading

Notification:

* In-app

---

# Pattern 18 + Pattern 19

IV Crush
Premium Destruction

Status: MERGE

New Pattern:

Premium Loss Event

Levels:

40%
60%
80%

Add:

* Hold time
* Entry premium
* Exit premium

Type:

* Universal Risk

Notification:

* 80% only

---

# Pattern 20 — Expiry Day Overtrading

Status: KEEP

Logic:

Trade frequency

vs

Expiry baseline

Special rules for:

* 0DTE
* Weekly expiry

Type:

* Personal Baseline

Notification:

* Push only on severe cases

---

# Pattern 21 — Opening 5 Minute Trap

Status: KEEP

Analytics only.

Reason:
Trade already completed.

Type:

* Analytics

Notification:

* None

---

# Pattern 22 — End Of Session MIS Panic

Status: KEEP

Logic:

MIS entries

after 3 PM

AND

Negative session

AND

Repeated entries

Type:

* Emotional Trading

Notification:

* In-app

---

# Pattern 23 — Post Loss Recovery Bet

Status: KEEP

Very Important

Logic:

Loss sequence

followed by

outsized position

Different from martingale.

Martingale:
Progressive

Recovery Bet:
Single huge jump

Type:

* Universal Risk

Notification:

* Push

---

# Pattern 24 — Profit Giveaway

Status: KEEP

Logic:

Peak P&L erosion

Use:

Peak Profit %

not fixed ₹1000

Type:

* Emotional Trading

Notification:

* Push

---

# Patterns Moved To Analytics

* Panic Exit
* Early Exit
* Opening Trap
* Rapid Reentry

These should never interrupt traders.

Use Journal and EOD Reports.

---

# Patterns To Merge

1. Rapid Flip
   +
   Options Direction Confusion

→ Direction Instability

2. IV Crush
   +
   Premium Destruction

→ Premium Loss Event

---

# Patterns Requiring Open Position Data

* Excess Exposure
* Concentration Risk
* Session Meltdown
* Recovery Bet
* Martingale

These become significantly more accurate with live positions.

---

# Hardcoded Values To Remove

Remove all fixed values from:

* Consecutive losses
* Revenge window
* Daily trade limits
* Burst counts
* Position sizing multipliers
* Profit giveaway minimums
* Exposure limits
* Cooldown duration

Replace with:

1. User Constitution
2. Personal Baseline
3. Universal Default

in that order.

---

# Bugs That Must Be Fixed Before Architecture Work

Priority P0

* trigger_trade_id missing
* cross-instrument comparisons
* missing trade context
* poor dedup logic
* same-underlying validation
* quantity-based sizing comparisons

Priority P1

* overlapping alerts
* duplicate notifications
* missing open position awareness

Priority P2

* confidence scoring
* baseline integration

End of Document 1
