# Product North Star — What TradeMentor AI Must Be

**Date:** 2026-02-24 (Session 8)
**Trigger:** Real-world blowup — Rs.11k to Rs.3k capital in one session. App was silent.

---

## The Vision (In the User's Words)

"Today's trading day was a classic example of overtrading, blowing up the account. This can later be used by AI to stop trader and tell him that THIS had happened last time you traded this way, please stop. Today's loss could have been avoided. Did so much overtrading, no SL, holding losing trades, taking same kind of position again and again, from 11k capital to 3k capital. So much data about how the user trades — this can later, in a month or 3 weeks, if trader shows same pattern, could be stopped giving today's example."

---

## Three Pillars

### Pillar 1: REAL-TIME GUARDIAN (Stop the Blowup While It's Happening)

The app must intervene DURING the session, not after.

**What should have happened on Feb 24:**
```
Trade 1: LOSS -Rs.2,233 on NIFTY25500CE
  → Alert: "First loss of the day. Stay disciplined."

Trade 2: LOSS -Rs.1,853 on NIFTY25400CE (4 min after Trade 1)
  → ALERT: Revenge Trading detected. New trade 4 min after Rs.2,233 loss.
  → PUSH NOTIFICATION: "You just took a quick revenge trade. Remember your rules."

Trade 3: LOSS -Rs.1,245 on NIFTY25400CE (SAME INSTRUMENT)
  → CRITICAL ALERT: Same Instrument Chasing — lost on NIFTY25400CE twice
  → CRITICAL ALERT: 3 consecutive losses
  → CRITICAL ALERT: Capital down 48% (Rs.11k → Rs.5.7k)
  → PUSH + WHATSAPP: "STOP. 3 losses in a row. You've lost almost half your capital.
    Take a break. Come back tomorrow."
  → AUTO-COOLDOWN: 30-minute forced pause

Trade 4: LOSS -Rs.675 on VBL (ignoring cooldown)
  → DANGER: Ignoring cooldown
  → WHATSAPP TO GUARDIAN: "Trader has lost 55% of capital today and is ignoring cooldown."

Trade 5: LOSS -Rs.1,225 on BDL
  → CRITICAL: 5 consecutive losses, 0% win rate, Rs.7,230 total loss
  → CRITICAL: Capital blowup — Rs.11k → Rs.3k (73% drawdown)
  → WHATSAPP: Final warning with full session summary
```

**Requirements:**
- Detection runs AFTER EVERY TRADE (not just on manual sync)
- Alerts escalate in severity with each trade
- Multiple channels: in-app toast → push notification → WhatsApp
- Cooldown activates automatically at danger level
- Guardian notified at critical level

### Pillar 2: SESSION MEMORY (Learn From Every Blowup)

Every trading session is recorded as a "session story" that the AI remembers.

**Feb 24 Session Story (auto-generated):**
```json
{
  "date": "2026-02-24",
  "type": "blowup",
  "capital_start": 11000,
  "capital_end": 3000,
  "drawdown_percent": 73,
  "trades": 5,
  "wins": 0,
  "win_rate": 0,
  "total_pnl": -7230,
  "patterns_triggered": [
    "overtrading",
    "revenge_trading",
    "same_instrument_chasing",
    "no_stop_loss",
    "consecutive_losses",
    "capital_blowup",
    "holding_losers"
  ],
  "instruments": ["NIFTY25500CE", "NIFTY25400CE", "VBL26MAR480CE", "BDL26MAR1300CE"],
  "repeat_instruments": ["NIFTY25400CE"],
  "time_span_minutes": 120,
  "narrative": "Classic blowup session. Started with oversized NIFTY options position, lost Rs.2,233. Immediately revenge traded same instrument (NIFTY25400CE) twice more. No stop losses on any trade. Held losers hoping for recovery. Moved to VBL and BDL when NIFTY failed — classic tilt behavior. Total destruction: 73% of capital in ~2 hours.",
  "lesson": "After the 2nd consecutive loss, the probability of the 3rd being emotional is >80%. The pattern: big NIFTY loss → revenge on same instrument → tilt to random stocks. Trigger point is the 2nd loss."
}
```

**How it's used later:**
- Stored in DB (new `session_stories` table or enriched journal)
- AI coach references it: "Remember Feb 24th when you lost 73% on a session just like this?"
- Pattern matching: When trader starts showing same behavior → preemptive warning
- BlowupShield uses it for "capital defended" calculations

### Pillar 3: PREDICTIVE INTERVENTION (Stop Before It Starts)

3 weeks later, trader starts a session:

```
Trade 1: BUY NIFTY options, oversized position
  → AI checks: "Last time trader bought oversized NIFTY options (Feb 24), they lost 73%.
    Same day of week. Same time of day. Same instrument type."
  → PREEMPTIVE WARNING: "Heads up — this looks like your Feb 24 setup.
    That day you went from Rs.11k to Rs.3k. You traded NIFTY25400CE twice
    after the first loss. Today, set a hard stop: if this trade loses,
    NO more NIFTY options today."

Trade 1 result: LOSS
  → AI: "First loss. Remember Feb 24 — the blowup started exactly like this.
    You took 4 more trades after the first loss and lost everything.
    Take a 15-minute break before your next trade."

Trade 2: BUY NIFTY25400CE (same instrument as loss)
  → AI: "You're doing it again. Feb 24: NIFTY25400CE after a loss → Rs.3,098 lost.
    This is the revenge pattern. STOP."
  → PUSH + WHATSAPP
```

**Requirements:**
- Session stories stored and indexed by patterns
- AI coach has access to historical session stories in its context
- Pattern similarity matching: current session vs past blowups
- Preemptive warnings based on early signals (instrument type, position size, time of day)

---

## What Must Work (Non-Negotiable)

| Feature | Current Status | Must Be |
|---------|---------------|---------|
| Consecutive loss detection | BROKEN (Trade.pnl=0) | Working, real-time |
| Capital drawdown alert | NOT IMPLEMENTED | Working, escalating severity |
| Same instrument chasing | NOT IMPLEMENTED | Working, real-time |
| Overtrading detection | Working (count-based) | Enhanced with loss context |
| Push notifications | Dead code | Working for danger/critical |
| WhatsApp alerts | Dead code | Working for critical + guardian |
| DangerZone auto-trigger | Never called | Auto after every sync |
| Cooldown enforcement | Code exists | Auto-activated on danger |
| Session story generation | NOT IMPLEMENTED | Auto after market close |
| AI memory of past blowups | NOT IMPLEMENTED | In chat context |
| Predictive warnings | NOT IMPLEMENTED | Pattern similarity matching |

---

## Implementation Priority

### NOW (Pattern Detection Fix — Session 8)
1. Fix frontend: Add 4 critical patterns
2. Fix backend: RiskDetector uses CompletedTrade
3. Fix backend: DangerZone uses CompletedTrade
4. Wire: DangerZone auto-triggers after sync

### NEXT (Notification Pipeline)
5. Wire push notifications to danger alerts
6. Wire WhatsApp to critical alerts
7. Test with real Twilio credentials

### THEN (Session Memory)
8. Design session_stories table
9. Auto-generate session story at EOD
10. Store in DB, index by patterns
11. Add to AI chat context

### FUTURE (Predictive Intervention)
12. Pattern similarity matching
13. Preemptive warnings in AI chat
14. "Remember when..." references in coach insight
15. BlowupShield integration with session stories

---

## The Test

When this is done, the app should be able to:

1. **During a blowup:** Alert the trader on every losing trade with escalating severity. Push notification after 2nd loss. WhatsApp after 3rd. Cooldown after 3rd. Guardian alert after 5th.

2. **After a blowup:** Generate a session story with full narrative, patterns, instruments, and lessons learned.

3. **Before the next blowup:** When trader starts showing the same pattern, reference the previous blowup by date, specific numbers, and specific instruments. "You did this before on Feb 24. You lost Rs.7,230. Stop now."

This is what makes TradeMentor AI different from every other trading journal. It's not just a mirror — it's a mirror with memory.
