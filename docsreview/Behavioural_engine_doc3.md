This is probably the most important document after the architecture because it determines whether users see the system as a helpful coach or an annoying notification app.

One thing I want to challenge before the document:

**I would NOT allow users to customize every behavioral pattern.**

A common mistake is:

```text
Max losses = 20
Max daily loss = ₹50,000
Cooldown = 0 minutes
Max trades = 100
```

The user essentially disables protection.

So Constitution should be:

### User controls

* Daily loss limit
* Cooldown duration
* Max trades/day
* Max exposure/trade
* Max consecutive losses
* Trading hours restrictions
* Guardian settings

### User cannot control

* Martingale detection
* Revenge detection
* Recovery bet detection
* Profit giveaway detection
* Premium destruction detection

Those remain behavioral observations.

---

# Behavioral Engine v2 — User Constitution & Onboarding (Document 3)

## Purpose

The Constitution is a trader's personal rulebook.

Instead of:

> "The app thinks you should stop."

The message becomes:

> "You violated your own rule."

This creates much stronger psychological accountability.

---

# Constitution Principles

A Constitution Rule must be:

### 1. Measurable

Good:

* Max loss ₹5000

Bad:

* Trade carefully

---

### 2. Objective

Good:

* Stop after 3 consecutive losses

Bad:

* Stop when emotional

---

### 3. Trackable

Good:

* Max 8 trades/day

Bad:

* Avoid overtrading

---

# Constitution Layers

## Hard Rules

User-defined.

Examples:

* Daily loss limit
* Max trades/day
* Cooldown period

---

## Behavioral Rules

System-defined.

Examples:

* Revenge trading
* Martingale
* FOMO

Cannot be disabled.

---

# Onboarding Flow

## Step 1 — Trading Profile

### What do you trade?

Options Buyer

Options Seller

Intraday Equity

Futures

Mixed

---

### Experience

Beginner

0–1 years

Intermediate

1–3 years

Advanced

3+ years

---

### Trading Frequency

1–3 trades/day

4–10 trades/day

10–20 trades/day

20+ trades/day

---

### Primary Style

Scalper

Intraday

Swing

Mixed

---

# Step 2 — Capital

### Trading Capital

Range:

₹5,000
to
₹50,00,000+

Store exact value.

This powers:

* Exposure limits
* Drawdown limits
* Position sizing alerts

---

# Step 3 — Daily Loss Rule

Question:

### What is the maximum amount you are willing to lose in a day?

Examples:

₹500

₹1000

₹2500

₹5000

Custom

Store:

daily_loss_limit

---

# Step 4 — Consecutive Loss Rule

Question:

### After how many losses should you stop?

Options:

2

3

4

5

Custom

Store:

max_consecutive_losses

---

# Step 5 — Cooldown Rule

Question:

### How long should you wait after a loss?

Options:

5 min

10 min

15 min

30 min

Custom

Store:

loss_cooldown

---

# Step 6 — Max Trades Rule

Question:

### Maximum trades per day?

Examples:

5

10

15

20

Custom

Store:

max_daily_trades

---

# Step 7 — Position Risk Rule

Question:

### Maximum capital risked in one trade?

Options:

1%

2%

3%

5%

10%

Custom

Store:

max_trade_risk_pct

---

# Step 8 — Time Restriction Rule

Optional

Avoid trading:

09:15–09:30

13:00–14:00

15:00–15:30

Custom

Store:

restricted_windows

---

# Step 9 — Guardian

Optional

Add accountability partner.

Store:

guardian_enabled

guardian_phone

guardian_rules

---

# Constitution Object

Example:

```json
{
  "daily_loss_limit": 5000,
  "max_consecutive_losses": 3,
  "loss_cooldown_minutes": 15,
  "max_daily_trades": 10,
  "max_trade_risk_pct": 3,
  "restricted_windows": [
    "13:00-14:00"
  ],
  "guardian_enabled": true
}
```

---

# My Rules Tab

Separate tab.

Not hidden in settings.

Top-level navigation.

---

# Section 1 — Active Rules

Show:

Daily Loss Limit

Max Trades

Cooldown

Risk %

Consecutive Losses

Guardian

---

# Section 2 — Rule Status

Example:

Daily Loss

₹3200 / ₹5000

Trades

7 / 10

Cooldown

Active

Consecutive Losses

2 / 3

---

# Section 3 — Constitution Violations

Examples:

Today:

* Daily loss rule breached
* Cooldown violated

Last 30 days:

* 11 violations

---

# Rule Locking System

This is where I partially agree with your idea.

## What should be locked?

Yes:

* Daily loss limit
* Max trades
* Cooldown
* Consecutive losses

No:

* Capital
* Experience level
* Trading style

---

# Lock Period

Recommended:

30 days

after creation

or modification

---

# Why Lock?

Without lock:

```text
Losses today

Increase loss limit

Continue trading
```

Constitution becomes meaningless.

---

# Emergency Override

Important.

User can override.

But:

Show warning.

Require confirmation.

Track event.

Example:

Rule changed during active session.

Flag:

constitution_override

This itself becomes a behavioral signal.

---

# Beginner Defaults

Capital < ₹50,000

Experience Beginner

Default:

Daily Loss

2%

Max Trades

5

Cooldown

15 min

Consecutive Losses

3

Risk Per Trade

1%

Guardian

Suggested

---

# Intermediate Defaults

Capital

₹50,000–₹5,00,000

Default:

Daily Loss

2%

Max Trades

10

Cooldown

10 min

Consecutive Losses

4

Risk Per Trade

2%

---

# Advanced Defaults

Capital

₹5,00,000+

Default:

Daily Loss

2–3%

Max Trades

User-defined

Cooldown

5 min

Consecutive Losses

5

Risk Per Trade

2–3%

---

# Capital-Based Presets

## ₹5,000–₹25,000

Focus:

Survival

Aggressive protection

---

## ₹25,000–₹1,00,000

Focus:

Discipline

Balanced alerts

---

## ₹1L–₹10L

Focus:

Consistency

Behavior tracking

---

## ₹10L+

Focus:

Risk concentration

Drawdown control

---

# Constitution Violation Severity

Level 1

Approaching Rule

80%

Example:

₹4000 of ₹5000 loss

---

Level 2

Rule Breached

100%

Example:

₹5100 loss

---

Level 3

Severe Breach

120%+

Example:

₹6500 loss

Guardian eligible.

---

# Additional Constitution Rules Worth Adding

Not in onboarding initially.

Advanced settings.

### Stop Trading After Target

Example:

Stop after ₹10,000 profit.

---

### Max Symbol Exposure

Example:

No more than 30% capital in NIFTY.

---

### No Trading During Lunch

Example:

13:00–14:00.

---

### No Expiry Day Trading

Optional.

---

### Max Options Premium Decay

Example:

Exit if option loses 40%.

---

# Constitution Score

Create a score.

0–100.

Measures how often trader follows their own rules.

Example:

95+

Excellent

80–95

Good

60–80

Needs improvement

Below 60

High risk

This becomes one of the most powerful metrics in the entire platform.

---

# Final Philosophy

The Constitution should not attempt to predict behavior.

The Behavioral Engine predicts behavior.

The Constitution enforces commitments.

Those are two different systems and should remain separate.
