# Behavioral AI Engine: E2E Simulation Report

This report documents the automated testing of the AI trading psychology engine. By spawning an isolated sandbox database user, we inject precise sequences of trades to verify that the RiskDetector correctly catches behavioral flaws like Revenge Trading and Overtrading, and escalates them to Database Cooldowns.

## Scenario 1: The 4-Loss Revenge & Overtrade
**Action:** Trader takes 4 consecutive losing trades within 10 minutes. 2 minutes after the 4th loss, trader enters a 5th trade with triple the position size.
**Results:**
- Revenge Sizing Alert Triggered: ✅ PASSED
- Loss Spiral / Consecutive Loss Alert Triggered: ✅ PASSED
- Generated Alerts: consecutive_loss, revenge_sizing, overtrading, fomo

## Scenario 2: Severe Overtrading (Machine Gun)
**Action:** Trader opens and closes 8 positions in under 4 minutes.
**Results:**
- Overtrading Alert Triggered: ✅ PASSED
- Severity Escalatation: danger

## Scenario 3: Database Cooldown Ingestion
**Action:** Check if the above danger-level behaviors automatically locked the trader out via `cooldown_until`.
**Results:**
- Database Cooldowns Active: ✅ PASSED (Count: 2)