# Behavioral Engine v2 — Architecture Specification (Document 2)

Status: Proposed Architecture

Goal:

Build a real-time behavioral intelligence engine for Indian F&O and intraday traders that:

* Works for ₹5,000 traders and ₹50 lakh traders
* Learns trader behavior
* Detects risk in real time
* Avoids alert fatigue
* Scales to lakhs of users
* Supports future AI coaching

---

# Core Philosophy

Current Engine:

Trade
↓
Run 24 detectors
↓
Alert

Problem:

Every pattern is independent.

This creates:

* Duplicate alerts
* Contradictions
* Alert fatigue
* Hardcoded thresholds

New System:

Trade
↓
Update User State
↓
Run Behavioral Engine
↓
Run Risk Engine
↓
Run Constitution Engine
↓
Calculate Confidence
↓
Generate Alert

Everything becomes state-driven.

---

# System Layers

The engine consists of 3 layers.

Layer 1:
Universal Risk Engine

Layer 2:
Personal Baseline Engine

Layer 3:
Trading Constitution Engine

All alerts must pass through these layers.

---

# Layer 1 — Universal Risk Engine

Purpose:

Detect mathematically dangerous behavior.

Applies to every user.

No customization.

Examples:

* Excess Exposure
* Session Meltdown
* Martingale
* Recovery Bet
* Premium Destruction

Question:

"Could this behavior destroy capital?"

If yes:

Risk Engine owns it.

Examples:

Position Risk:

Current Trade Risk
÷
Trading Capital

Daily Drawdown:

Current Loss
÷
Daily Loss Limit

Profit Giveback:

Peak PnL
vs
Current PnL

This layer prevents account destruction.

---

# Layer 2 — Personal Baseline Engine

Purpose:

Learn normal behavior.

Question:

"Is the trader acting unusually?"

Examples:

Trader A:

3 trades/day normally

Today:

14 trades

Alert

Trader B:

25 trades/day normally

Today:

14 trades

No alert

This layer creates personalization.

Without this layer:

Every user gets the same alerts.

---

# Layer 3 — Trading Constitution Engine

Purpose:

Enforce trader's own rules.

Question:

"Did the trader break their own commitment?"

Examples:

User Rule:

Maximum daily loss:
₹5,000

Current loss:
₹6,200

Alert

User Rule:

Cooldown:
20 min

Entered after:
5 min

Alert

Psychologically strongest layer.

Reason:

The user created the rule.

---

# Event Driven Architecture

Current systems often do:

Trade
↓
API Request
↓
Run Engine

Bad.

Engine becomes slow.

Instead:

Trade Event
↓
Queue
↓
Worker
↓
Behavior Engine
↓
Notification

Everything becomes asynchronous.

---

# Real Time Event Types

The system should process:

Trade Opened

Trade Closed

Position Modified

SL Modified

Position Squared Off

Session Start

Session End

Market Open

Market Close

Each event updates state.

---

# Processing Flow

Trade Event Arrives

Step 1

Update User State

Step 2

Update Session Metrics

Step 3

Run Relevant Patterns

Step 4

Calculate Scores

Step 5

Generate Alerts

Step 6

Route Notifications

---

# User State Model

Most Important Component

Do NOT recalculate history every trade.

Store live state.

Example:

user_state

{
session_pnl
peak_pnl
consecutive_losses
consecutive_wins
today_trade_count
today_loss_count
current_tilt_score
current_risk_score
current_fomo_score
last_loss_time
last_trade_time
}

Every event updates state.

O(1) operations.

No history scanning.

This is how you scale.

---

# Session State

Separate object.

session_state

{
pnl
peak_pnl
drawdown
trades_today
winners
losers
avg_winner_hold
avg_loser_hold
}

Reset daily.

---

# Position State

Needed because you have open positions.

position_state

{
total_open_risk
concentration_by_symbol
concentration_by_underlying
option_exposure
futures_exposure
}

Used by:

* Excess Exposure
* Concentration Risk
* Recovery Bet

---

# Baseline Learning Engine

Runs after market close.

Not on every trade.

Daily Job:

18:15 IST

Input:

Last 30-60 sessions

Output:

behavior_baseline

{
avg_daily_trades
p95_daily_trades

avg_position_risk

avg_hold_time

avg_reentry_delay

avg_win_rate

preferred_symbols

preferred_hours

danger_hours

typical_peak_pnl

typical_drawdown
}

Stored permanently.

---

# Baseline Activation

Do not activate immediately.

Requirements:

Minimum:

20 sessions

AND

100 completed trades

Before then:

Use defaults.

Reason:

Small samples create bad baselines.

---

# Alert Scoring System

Critical Upgrade

Current:

Detector Fires
↓
Alert

New:

Detector Score
↓
Alert Score
↓
Confidence

Example:

Revenge Trade

Recent Loss:
+25

Same Symbol:
+20

Bigger Size:
+20

Session Red:
+15

Fast Re-entry:
+20

Total:
80

Confidence:
80%

Alert

Below 50:

No alert

This dramatically reduces false positives.

---

# Composite Behavioral Scores

Do not stop at patterns.

Create meta scores.

---

# Tilt Score

Measures emotional instability.

Inputs:

* Consecutive losses
* Revenge trades
* Recovery bets
* Martingale
* Giveaway

Output:

0-100

---

# FOMO Score

Inputs:

* Multiple symbols
* Rapid entries
* Expiry overtrading

Output:

0-100

---

# Overconfidence Score

Inputs:

* Winning streak
* Size increase
* Exposure increase

Output:

0-100

---

# Risk Score

Inputs:

* Exposure
* Concentration
* Drawdown
* Premium destruction

Output:

0-100

---

# Why Scores Matter

Instead of:

5 alerts

User sees:

Tilt Score:
88

High emotional risk detected.

Far better UX.

---

# Alert Routing Engine

Every alert gets:

Severity

Confidence

Category

Then routed.

---

# Notification Levels

Level 0

Analytics

No notification

Examples:

* Panic Exit
* Early Exit

---

Level 1

In App

Examples:

* FOMO
* Rapid Reentry

---

Level 2

Push

Examples:

* Martingale
* Recovery Bet

---

Level 3

Critical Push

Examples:

* Session Meltdown

---

Level 4

Guardian

Examples:

* Severe Meltdown
* Severe Loss Spiral

---

# Guardian Architecture

Purpose:

Emergency accountability.

Not daily coaching.

Guardian should receive extremely few alerts.

Maximum:

1-3 alerts per month.

Guardian Patterns:

Session Meltdown

Extreme Loss Spiral

Constitution Breach

Examples:

"Trader exceeded self-defined loss limit by 60%."

Never send:

* FOMO
* Rapid Flip
* Early Exit

Too noisy.

---

# Deduplication Engine

Very important.

Without this:

Spam.

Example:

Martingale Alert

11:10

No second alert until:

Size increases again

or

Severity increases

Dedup Key

user
+
pattern
+
severity

---

# Alert Escalation

Allowed

Example:

Caution
↓
Danger

Should bypass dedup.

Severity upgrades are important.

---

# Scalability Architecture

Target:

5 lakh+ users

---

# Components

Frontend

React

Backend

Node/NestJS

Database

PostgreSQL

Cache

Redis

Queue

BullMQ

or

Kafka

Workers

Behavior Workers

Notification Workers

Baseline Workers

---

# Data Separation

Hot Data

Redis

Examples:

Current session

Current state

Current positions

---

Warm Data

Postgres

Examples:

Alerts

Trades

Profiles

Baselines

---

Cold Data

Analytics Warehouse

Optional later

---

# Worker Architecture

Worker A

Trade Processing

Worker B

Behavior Detection

Worker C

Notifications

Worker D

Baseline Learning

Worker E

Analytics

Never run everything together.

---

# Performance Rule

Never do this:

Load 1000 trades
Run 24 detectors

on every trade.

Instead:

Update State
Run O(1) checks

This is the difference between:

1000 users

and

500,000 users.

---

# Future AI Layer

Not required initially.

But architecture should support:

AI Coach

Inputs:

Behavioral Scores

Baselines

Constitution

Recent Trades

Outputs:

Personalized coaching

Examples:

"You usually stop trading after 3 losses. Today you've taken 7 losses and doubled size twice."

This becomes possible because all data is already structured.

---

# Final Architecture Summary

Trade Events
↓
Queue
↓
State Update
↓
Universal Risk Engine
↓
Personal Baseline Engine
↓
Constitution Engine
↓
Pattern Detection
↓
Behavior Scores
↓
Alert Scoring
↓
Notification Routing
↓
Guardian Escalation

The engine's primary unit should not be "alerts."

The engine's primary unit should be:

Behavioral State

Everything else should be derived from that.
