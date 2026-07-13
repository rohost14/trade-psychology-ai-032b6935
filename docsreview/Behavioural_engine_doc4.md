This is where your product starts becoming significantly more valuable than a simple alert engine.
Most trading apps stop at:
> "You took 5 trades."
You should eventually reach:
> "Your behavior is deteriorating. Probability of a bad decision is increasing."
That's what these patterns do.
---
# Behavioral Engine v2 — New Pattern Roadmap (Document 4)
## Purpose

The 24 patterns detect events.

These new patterns detect states.

Difference:

Current:

```text
Revenge Trade
Martingale
Overtrading
```

These are events.

Future:

```text
Tilt
FOMO
Death Spiral
Strategy Breakdown
```

These are behavioral states.

Humans operate in states, not individual events.

---

# Tier Classification

## Tier A (Must Build)

* Tilt Score
* Death Spiral
* Same Symbol Obsession
* Concentration Risk

---

## Tier B (High Value)

* Time Of Day Bias
* Win Rate Collapse
* Strategy Breakdown

---

## Tier C (Advanced)

* All In Bet

Requires real-time open positions.

---

# Pattern 25 — Tilt Score

## Problem

Today:

User gets

* Revenge alert
* Loss streak alert
* Overtrading alert

3 separate notifications.

Reality:

Trader is tilted.

The system should recognize the state.

---

## Definition

Tilt Score measures emotional deterioration.

Range:

```text
0-100
```

---

## Inputs

### Consecutive Losses

0-25 points

---

### Revenge Trades

0-20 points

---

### Recovery Bets

0-20 points

---

### Martingale Events

0-20 points

---

### Profit Giveaway

0-15 points

---

## Example

Trader:

3 losses

*

2 revenge trades

*

1 recovery bet

Score:

```text
78
```

---

## Output

### 0-30

Normal

---

### 30-60

Elevated

---

### 60-80

High Tilt

---

### 80+

Critical Tilt

---

## Alert

Example:

> Your Tilt Score is 84. Current behavior differs significantly from your normal trading pattern.

---

## Why Important

This becomes the primary emotional risk indicator.

Everything else feeds into it.

---

# Pattern 26 — Death Spiral

Most important future pattern.

---

## Problem

Retail traders rarely blow up from one trade.

They blow up from a sequence.

Example:

```text
Loss
↓
Revenge
↓
Loss
↓
Size Increase
↓
Loss
↓
Recovery Bet
↓
Large Loss
```

Death Spiral.

---

## Definition

Detect accelerating self-destructive behavior.

---

## Required Conditions

Any 4 of:

### Consecutive Losses

---

### Revenge Trade

---

### Martingale

---

### Recovery Bet

---

### Overtrading Burst

---

### Session Meltdown

---

### Profit Giveaway

---

## Example

```text
Loss
Loss
Loss

Revenge Trade

Recovery Bet

Profit Giveaway
```

Death Spiral fires.

---

## Severity

### Warning

4 signals

---

### Danger

5 signals

---

### Critical

6+

---

## Notification

Push

Guardian

Highest priority.

---

## Why Important

This may become your single most valuable detector.

---

# Pattern 27 — Same Symbol Obsession

Very common in Indian F&O.

---

## Problem

Trader becomes emotionally attached.

Example:

```text
NIFTY CE loss

Re-enter

Loss

Re-enter

Loss

Re-enter
```

Not trading.

Chasing.

---

## Current System

Loss streak only sees:

```text
Trade
Trade
Trade
```

Misses symbol fixation.

---

## Logic

Track:

Losses

per underlying

per session

---

## Signals

### Same Underlying

Repeated

---

### Multiple Losses

3+

---

### Multiple Re-entries

2+

---

### Increasing Size

Bonus weight

---

## Example

```text
BANKNIFTY

-1500

-2000

-1800

-3000
```

Same symbol.

Same day.

Alert.

---

## Notification

In-app

Danger if size increasing.

---

## Why Important

Extremely common retail behavior.

Probably more valuable than FOMO.

---

# Pattern 28 — Time Of Day Bias

Uses learn_patterns output.

---

## Problem

Trader consistently loses at certain times.

Keeps trading there.

---

## Example

90 sessions:

```text
09:15-10:00

+₹40,000

13:00-14:00

-₹65,000
```

System learns.

---

## Real Time Logic

User opens trade:

13:15

Check:

Historical window performance.

---

## Output

Example:

> Historically your worst performance occurs between 1 PM and 2 PM.

---

## Confidence

Needs:

Minimum:

30 sessions

---

## Notification

In-app

Pre-trade

---

## Why Important

This is real personalization.

---

# Pattern 29 — Win Rate Collapse

## Problem

Strategy stops working.

Trader continues trading.

---

## Example

Normal:

```text
58% win rate
```

Current:

```text
20%
```

Last 15 trades.

---

## Logic

Compare:

Recent Win Rate

vs

Baseline Win Rate

---

## Severity

### Mild

25% deterioration

---

### Severe

40% deterioration

---

## Critical

60% deterioration

---

## Notification

In-app

Danger if session losses also high.

---

## Why Important

Detects strategy failure.

Not psychology.

---

# Pattern 30 — Strategy Breakdown

Advanced version of Win Rate Collapse.

---

## Problem

Win rate collapse alone isn't enough.

Need multiple signals.

---

## Inputs

### Win Rate Collapse

---

### Profit Factor Collapse

---

### Average Winner Shrinking

---

### Average Loser Growing

---

### Early Exit Increasing

---

### Profit Giveaway Increasing

---

## Example

Normal:

```text
Profit Factor 1.8
```

Current:

```text
0.6
```

System detects degradation.

---

## Alert

> Current trading performance differs significantly from your 60-day baseline.

---

## Why Important

Professional-grade insight.

---

# Pattern 31 — Concentration Risk

Extremely important.

Should eventually become Universal Risk.

---

## Problem

Trader has:

```text
10 positions
```

but

```text
80%
```

of exposure is NIFTY.

Looks diversified.

Actually isn't.

---

## Logic

Calculate:

Underlying concentration.

---

## Formula

```text
Largest Underlying Exposure

÷

Total Exposure
```

---

## Levels

### Warning

40%

---

### Danger

60%

---

### Critical

80%

---

## Example

```text
NIFTY = 75%

BANKNIFTY = 15%

Others = 10%
```

Critical.

---

## Notification

Push.

---

# Pattern 32 — All In Bet

Most dangerous single-trade behavior.

---

## Problem

Trader decides:

> One trade will fix everything.

---

## Example

Capital:

```text
₹100,000
```

Single trade:

```text
₹70,000
```

exposure.

---

## Logic

Single Position Exposure

÷

Total Capital

---

## Levels

### Warning

30%

---

### Danger

50%

---

### Critical

70%

---

## Additional Weight

If:

* Recent losses
* Recovery Bet
* Martingale

then severity increases.

---

## Notification

Immediate Push.

---

# Future Composite Behavioral States

Eventually don't show:

```text
Martingale
Recovery Bet
Revenge Trade
```

Show:

---

## Emotional State

Tilt

0-100

---

## Risk State

Risk Score

0-100

---

## Discipline State

Constitution Score

0-100

---

## Performance State

Strategy Health

0-100

---

Example:

```text
Tilt: 82
Risk: 75
Discipline: 41
Strategy Health: 38
```

This tells the entire story in 4 numbers.

---

# Recommended Build Order

## Phase 1 (Immediately After Current Engine)

1. Tilt Score
2. Same Symbol Obsession
3. Concentration Risk

Highest ROI.

---

## Phase 2

4. Death Spiral
5. Time Of Day Bias

Strong personalization.

---

## Phase 3

6. Win Rate Collapse
7. Strategy Breakdown

Professional-grade analytics.

---

## Phase 4

8. All In Bet

After full open-position tracking exists.

---

# My Critical Opinion

If I were building this product for Indian retail F&O traders, the most valuable behavioral signals would likely be:

1. Tilt Score
2. Death Spiral
3. Same Symbol Obsession
4. Constitution Score
5. Session Meltdown
6. Concentration Risk

Those six alone would probably explain 70–80% of account-destroying behavior. Many of the original 24 patterns become much more useful when treated as inputs into these higher-level behavioral states rather than as standalone alerts.
