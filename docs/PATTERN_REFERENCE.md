# Behavioral Pattern Reference

TradeMentor AI monitors 23 distinct behavioral and psychological patterns in a trader's activity.
Every time a trade is fully closed, all 23 patterns are evaluated against everything that has
happened in the session so far. This document describes each pattern in plain terms.

**Philosophy**: Mirror, not blocker. These patterns show traders factual observations about their
own behavior. Nothing is blocked. Everything is a reflection.

---

## How the System Works

### When Alerts Fire
An alert is evaluated the moment a position closes completely — both the opening leg and the
closing leg of a trade have been processed. All 23 patterns are checked at that moment against
the full history of today's closed trades.

### Risk Score
Each pattern that fires adds points to a session risk score (ranging from 0 to 100). As the score
rises, the session state advances through: Stable → Pressure → Tilt Risk → Tilt → Breakdown →
Recovery. The score accumulates throughout the day.

### Personalized Thresholds
Thresholds work in three layers. The first layer is what the trader themselves declares in their
profile — their daily trade limit, daily loss limit, maximum position size, and cooldown duration.
The second layer is research-backed defaults derived from SEBI FY2022–24 studies, NSE market
data, and behavioral finance research. The third layer is a set of absolute floors that cannot be
set lower regardless of user configuration. Where a user's declared value exists and is stricter
than the research default, the user's value takes priority.

### Strategy-Aware Suppression
When the system identifies that a trade is part of a deliberate multi-leg strategy (such as a
straddle, strangle, or spread), several patterns are suppressed for that trade's legs. A losing
hedge leg is not a behavioral problem — it is by design.

---

## The 23 Patterns

---

### 1. Consecutive Loss Streak

**Risk added per firing**: 20 points  
**Alert levels**: Caution at 3 consecutive losses, Danger at 5

**What it is**: This pattern tracks an unbroken string of losing trades within the session. After
three consecutive losses, research shows that emotional decision-making measurably degrades.
After five, near-universal emotional impairment is documented across trading and poker research.

**When it triggers**: The pattern counts backward from the most recent trade. If the last three
completed trades (including the one just closed) are all losses, caution fires. If the last five
are all losses, danger fires. The streak resets the moment any trade is profitable.

**Threshold defaults**: Caution at 3 losses, Danger at 5 losses.  
**Personalization**: Both thresholds can be adjusted through the system's behavioral baseline
feature, which learns the individual trader's typical patterns over 30 sessions.

**Note**: Applies across all instruments and underlyings — five NIFTY losses count the same as
three NIFTY losses followed by two BANKNIFTY losses.

---

### 2. Revenge Trade

**Risk added per firing**: 25 points  
**Alert levels**: Caution within 20 minutes of a loss, Danger within 5 minutes

**What it is**: Entering a new trade too quickly after a significant loss. Cortisol (the stress
hormone) stays elevated for 20–35 minutes after a financial loss, per Cambridge research. A
Cambridge/Herbert 2008 study found that 73% of trades placed within 15 minutes of a loss are
also losing trades. The impulse to immediately recover peaks within the first 3–8 minutes.

**When it triggers**: The system looks at the most recently closed trade before the current one.
If that trade was a loss greater than ₹500, and the new trade entry happened within 20 minutes
of that loss, caution fires. If the new entry happened within 5 minutes, danger fires. Scratch
trades (losses below ₹500) are excluded to avoid noise.

**Threshold defaults**: Caution window 20 minutes, Danger window 5 minutes, Minimum qualifying
loss ₹500.  
**Personalization**: The caution window expands to match the trader's declared cooldown period
(whichever is longer).

**Known fix applied**: Previously, this pattern would miss the very first potential revenge trade
in a session when only one prior trade existed. This has been corrected.

---

### 3. Overtrading Burst and Daily Count

**Risk added per firing**: 10 points  
**Alert levels**: Caution or Danger (context-dependent)

**What it is**: Two distinct overtrading signals under one category. The burst check identifies
too many trades packed into a 30-minute window — a sign of emotional escalation. The daily count
check flags when a session's total trade count exceeds safe limits. SEBI FY2023 data: traders
with more than 6 trades per day had a 94% probability of net loss; above 12, it approached 99%.

**When it triggers**:

Burst check (30-minute rolling window):
- 8 or more trades within 30 minutes, when not all of them are profitable → Danger
- 5 or more trades within 30 minutes, when the session is in loss → Caution
- 5 or more trades within 30 minutes, when the session is in profit but some burst trades lost → Caution
- 5 or more trades within 30 minutes, all profitable, session profitable → No alert (not a problem)

Daily count check (only evaluated if the burst check does not fire):
- 12 or more trades today → Danger
- 7 or more trades today → Caution

**Threshold defaults**: Burst caution at 5, burst danger at 8, daily caution at 7, daily danger
at 12.  
**Personalization**: The daily trade limit adjusts to the trader's declared limit in their
profile (whichever is stricter). The danger threshold auto-sets at 1.5 times the caution limit.

**Correction applied**: The daily count now correctly includes the trade that just triggered the
check. Previously, the count was off by one — the alert fired one trade later than intended and
displayed the wrong number.

---

### 4. Size Escalation After Losses

**Risk added per firing**: 15 points  
**Alert levels**: Caution only

**What it is**: Position size increasing steadily across consecutive trades on the same underlying
while the trader is in a loss. This is an early warning of averaging-down behavior or emotional
position escalation. A consistent 30% increase across three trades compounds to 2.2 times the
original size.

**When it triggers**: Looks at the last three completed trades on the same underlying. If those
three trades show a strictly increasing position size, and at least one of the first two was a
loss, and the total increase from the first to the third exceeds 30%, caution fires.

**Threshold defaults**: 30% escalation required to trigger.  
**Personalization**: Not user-configurable.

**Note**: Applies only within the same underlying — NIFTY lot sizes and SENSEX lot sizes are
never compared against each other as they differ significantly.

---

### 5. Rapid Re-entry

**Risk added per firing**: 15 points  
**Alert levels**: Caution only

**What it is**: Re-entering the exact same instrument within minutes of a losing exit on that
same instrument. Options pricing takes approximately 5 minutes to stabilise after a volatile
price move. Entering before that window closes is almost never analytical — it is emotional.

**When it triggers**: If the most recent prior trade on the exact same instrument (same strike,
same expiry) was a loss, and the new entry happens within 5 minutes of that loss, caution fires.
Re-entries after a profitable exit are not flagged — those may be deliberate scalping.

**Threshold defaults**: 5-minute re-entry window.  
**Personalization**: Not user-configurable.

**Note**: This checks the exact instrument (including strike and expiry), not just the underlying.
Switching from one NIFTY strike to another is not detected here; that is covered by the Options
Premium Averaging Down pattern.

---

### 6. Panic Exit

**Risk added per firing**: 10 points  
**Alert levels**: Caution only

**What it is**: Closing a trade at a loss within 5 minutes of entry, without a stop-loss order
in place. The distinction matters: exiting via a pre-set stop-loss means the exit plan was in
place before the trade was entered. Exiting manually within 5 minutes at a loss, with no stop
order, is a panic response.

**When it triggers**: If a trade closes at a loss within 5 minutes of entry, AND the exit was
not through a stop-loss order (regular or stop-market), caution fires.

**Threshold defaults**: Hold time under 5 minutes.  
**Personalization**: Not user-configurable.

**Note**: The stop-loss detection relies on Zerodha reporting the exit order type correctly in
fill records. If fill data is missing, the stop-loss check is bypassed and a false alert may fire.

---

### 7. Martingale Behaviour

**Risk added per firing**: 20 points  
**Alert levels**: Caution at 1.5× doubling, Danger at 2.0× doubling

**What it is**: The martingale pattern — doubling down position size after losses in hopes of
one large recovery. SEBI data shows traders who averaged down on losing options positions lost
three times more than those who did not. The pattern is culturally normalised in India as
"lowering my average cost," but for options it is mathematically destructive.

**When it triggers**: Looks at the last two or three completed trades on the same underlying.
If at least two of those trades are losses, and any consecutive step in the size sequence shows
a ratio of 1.5 times or more, caution fires. If any step reaches 2.0 times (a full double),
danger fires.

**Threshold defaults**: Minimum 2 losses required, caution at 1.5× ratio, danger at 2.0×.  
**Personalization**: Not user-configurable.

**Note**: Applies within the same underlying only. Requires the pattern to have already been
building in prior trades — a single oversized trade after losses is caught by the Post-Loss
Recovery Bet pattern instead.

---

### 8. Cooldown Violation

**Risk added per firing**: 25 points  
**Alert levels**: Analytics-only (never shown as a user-facing alert)

**What it is**: Trading during an active cooldown period. Cooldowns are triggered by patterns
like consecutive losses. Tracking whether traders respect or override their cooldowns feeds
the personalization engine — if someone always skips cooldowns, the system adjusts its signals.

**When it triggers**: If an active, unexpired cooldown exists for the account when a trade
completes, a violation is recorded internally.

**Note**: This is the only pattern that never produces a visible alert. It contributes to the
risk score and is used for analytics and personalization but is never shown to the trader.
Research showed that displaying cooldown reminders had the opposite effect — traders felt
nagged rather than helped.

---

### 9. Rapid Flip

**Risk added per firing**: 15 points  
**Alert levels**: Caution only

**What it is**: Reversing the direction of a trade on the same instrument within 10 minutes.
Going from long to short (or short to long) on the same instrument within a 10-minute window
indicates confusion about market direction, not a revised analysis. In Indian volatile markets,
10 minutes is considered the minimum time needed for a legitimate directional re-assessment.

**When it triggers**: If a prior trade on the same instrument (same symbol) exited with a
different direction, and the current entry happened within 10 minutes of that exit, caution fires.

**Threshold defaults**: 10-minute confusion window.  
**Personalization**: Not user-configurable.

**Note**: Requires both trades to have a direction recorded. Trades missing direction data
(common in some equity products) are excluded.

---

### 10. Excess Exposure

**Risk added per firing**: 15 points  
**Alert levels**: Caution above 5% of capital, Danger above 10%

**What it is**: A single trade placing too large a percentage of the trader's capital at risk.
Kelly criterion analysis for typical F&O win rates (45%) and reward ratios (1.5:1) suggests
half-Kelly optimal sizing of roughly 6%. SEBI data shows profitable traders average 4–6% per
trade; loss-making traders average 20–50%.

**When it triggers**: The capital at risk for the completed trade is estimated (premium paid for
options buyers; SPAN margin approximation for futures and options sellers) and compared to the
trader's declared trading capital. Above 5% triggers caution; above 10% triggers danger.

**Threshold defaults**: Caution at 5% of capital, Danger at 10%.  
**Personalization**: Both thresholds adjust to the trader's declared maximum position size.
The danger threshold auto-sets at twice the caution threshold.

**Requires**: Trading capital must be declared in the user profile. Without it, this pattern
cannot fire.

**Limitation**: For options sellers and futures traders, the SPAN margin estimate understates
true risk. This is a known and accepted approximation — it is conservative in that it may
produce false alerts but will not miss large exposure events.

---

### 11. Session Meltdown

**Risk added per firing**: 30 points (highest single-pattern delta)  
**Alert levels**: Caution at 40% of daily loss limit, Danger at 75%

**What it is**: The session's total realized loss crossing a meaningful fraction of the trader's
daily loss limit. Prospect theory research shows the "break-even effect" — the impulse to take
increasingly risky trades to recover losses — begins around 40–50% of the daily limit.
Professional trading desk intervention typically happens at 50%; hard stops at 80%.

**When it triggers**: The running sum of all today's closed trades is compared to the daily loss
limit. At 40% of the limit in losses, caution fires. At 75%, danger fires.

**Daily loss limit source** (in priority order):
1. Trader's declared daily loss limit in their profile
2. 5% of declared trading capital
3. If neither is available, this pattern cannot fire

**Threshold defaults**: Caution at 40% used, Danger at 75% used.  
**Personalization**: Daily loss limit is always taken from the user's declaration when available.

---

### 12. FOMO Entry

**Risk added per firing**: 15 points  
**Alert levels**: Caution only

**What it is**: Scattering trades across multiple unrelated underlying instruments in a short
window — the signature of fear-of-missing-out. Buying two different NIFTY strikes is a strategy.
Buying NIFTY calls, BANKNIFTY calls, and a RELIANCE option all within 30 minutes is chasing
multiple markets simultaneously and indicates lack of focus.

**When it triggers**: Counts the number of distinct underlying instruments entered within a
rolling 30-minute window. The threshold varies by context:
- Expiry day: 2 or more different underlyings within 30 minutes
- First 30 minutes of market (open rush): 2 or more different underlyings
- Last 30 minutes before close (pre-close panic): 2 or more different underlyings
- Any other time: 3 or more different underlyings within 30 minutes

**Threshold defaults**: General window 3 underlyings, reduced to 2 at open, close, and expiry.  
**Personalization**: Not user-configurable.

**Note**: Expiry is detected from the instrument's actual expiry date embedded in its symbol,
not by checking if today is a Thursday. This correctly handles both weekly and monthly expiries.

---

### 13. No Stop-Loss

**Risk added per firing**: 20 points  
**Alert levels**: Caution above 25% premium loss, Danger above 50%

**What it is**: Holding an options or futures position through significant losses without a
pre-placed stop-loss order. The primary detection is the exit method — if the trade was closed
via a stop-loss order (regular or stop-market), the mechanism worked and no alert fires.
Only manual exits through market or limit orders trigger this pattern.

**When it triggers**: All of the following must be true:
1. The instrument is an option (call or put) or a futures contract
2. The trade closed at a loss
3. The exit was not through a stop-loss or stop-market order
4. The position was held for at least 5 minutes (to exclude deliberate ultra-fast scalps)
5. The loss exceeded 25% of the premium or margin at stake

Severity escalates: above 50% loss on the at-stake amount, danger fires.

**Expiry modifiers**:
- Weekly expiry day: same thresholds (25%/50%), same minimum hold of 5 minutes
- Monthly expiry day: lower threshold — 20% loss is enough to trigger caution (theta is at
  maximum all day on monthly expiry and erodes premium far faster)

**Personalization**: Not user-configurable.

---

### 14. Early Exit (Disposition Effect)

**Risk added per firing**: 10 points  
**Alert levels**: Caution only

**What it is**: A session-level statistical pattern detecting the classic disposition effect —
cutting winning trades much faster than losing trades. Shefrin & Statman (1985) identified this
as one of the most documented biases in retail trading. SEBI FY2022 data: Indian retail traders
sold winning positions 2.7 times faster than losing positions, with the effect being 2–3 times
stronger in Indian retail than in institutional trading.

**When it triggers**: When the current trade is a winner, the system computes the average hold
time of all today's winning trades versus all today's losing trades. If the average winning hold
is less than 40% of the average losing hold, AND the average winning hold is under 60 minutes,
caution fires.

Requires at least 3 prior winning trades and 3 prior losing trades before it can compute a
meaningful session average — it needs enough data to be statistically valid.

**Threshold defaults**: Winners held less than 40% as long as losers, with winners averaging
under 60 minutes.  
**Personalization**: Not user-configurable.

**Note**: This is the only purely statistical, session-level pattern. It looks at averages across
the day, not individual trade characteristics.

---

### 15. Winning Streak Overconfidence

**Risk added per firing**: 15 points  
**Alert levels**: Caution (3 wins + size jump), Danger (5 consecutive wins regardless of size)

**What it is**: The "hot hand fallacy" — consecutive wins creating overconfidence and leading
to oversized subsequent positions. Research data: after 3 consecutive wins, retail traders
increase their next position size by 40–80%. After 5 consecutive wins, the overconfidence is
extreme and the pattern fires regardless of whether the trader has increased size.

**When it triggers**:
- Danger: The last 5 completed trades before the current one are all profitable. No size check
  needed — being on a 5-trade win streak when entering this trade is enough.
- Caution: The last 3 completed trades are all profitable, AND the current trade's position
  size is 1.3 times or more the average size of those 3 winning trades.

**Threshold defaults**: Danger streak at 5 wins, caution streak at 3 wins with 1.3× size jump.  
**Personalization**: Not user-configurable.

**Note**: The alert fires at the point of entering the next trade after a streak, not on the
wins themselves. It is a warning about the entry decision, not the outcome.

---

### 16. Options Direction Confusion

**Risk added per firing**: 20 points  
**Alert levels**: Caution only

**What it is**: Flipping between calls (bullish) and puts (bearish) on the same underlying
within a 10-minute window. A legitimate directional reassessment takes time — reading updated
price action, reconsidering the setup, deciding to reverse. Doing this within 10 minutes almost
always indicates confusion about market direction rather than a reasoned strategy change.

**When it triggers**: If a prior long options trade on the same underlying exited as the opposite
type (call became put, or put became call) within 10 minutes before the current entry, caution fires.
Only long options positions are checked — options sellers have different hedging dynamics.

**Threshold defaults**: 10-minute confusion window.  
**Personalization**: Not user-configurable.

**Note**: This may fire alongside the Options Premium Averaging Down pattern when the same
event qualifies for both — a call loss followed quickly by a put entry on the same underlying.
Both reflect different aspects of the same behavioral problem: confusion angle versus averaging
down angle.

---

### 17. Options Premium Averaging Down

**Risk added per firing**: 15 points  
**Alert levels**: Caution only

**What it is**: Re-entering options on the same underlying after already taking a significant
options loss on that underlying today. Unlike averaging down on equity (where the premise of
buying more at a lower price has some mathematical basis), options premium erodes through time
decay continuously — the "averaging down" strategy accelerates the loss rather than reducing
the average cost in any useful way. SEBI data shows traders who averaged down on losing options
positions lost three times more than those who did not.

**When it triggers**: When a new long options trade is entered on an underlying where at least
one prior long options trade today lost 20% or more of its premium, caution fires. The new trade
does not need to be a loss — the alert fires at entry, not exit.

**Threshold defaults**: Prior loss of 20% or more of premium paid qualifies.  
**Personalization**: Not user-configurable.

---

### 18. IV Crush Behavior

**Risk added per firing**: 10 points  
**Alert levels**: Caution only

**What it is**: A proxy for buying options into elevated implied volatility that then collapses.
The system cannot directly observe implied volatility, so it uses a behavioral proxy: a long
options position that loses 40% or more of its premium within 30 minutes. Theta decay alone
cannot cause a 40% loss in 30 minutes under normal conditions — when this happens, it almost
always means implied volatility collapsed after the entry (the classic IV crush event, common
around earnings announcements, policy decisions, and expiry).

**When it triggers**: If a long options position closes within 30 minutes of entry having lost
40% or more of its premium, caution fires.

**Threshold defaults**: Premium loss of 40% or more within 30 minutes.  
**Personalization**: Not user-configurable.

**Overlap handling**: This pattern and the Premium Destruction pattern can both fire for the
same fast large premium loss. When both qualify, only the higher-severity alert is kept. If both
are caution, IV Crush is dropped and Premium Destruction is kept (since Premium Destruction
escalates to Danger on repeat occurrences).

---

### 19. Premium Destruction

**Risk added per firing**: 25 points  
**Alert levels**: Caution (first occurrence today), Danger (second or more occurrences today)

**What it is**: An options position exiting with more than 60% of its premium lost, regardless
of how long it was held. Losing 60% or more of a premium in a single trade almost certainly
means either the entry was poorly timed, the position was held too long through an adverse move,
or the trade had no exit plan. Options losing more than 60% of premium have almost no realistic
recovery probability in the same session.

**When it triggers**: When a long options trade closes having lost 60% or more of its premium.
If this is the first such trade today, caution fires. If any prior trade today also lost 60% or
more of its premium, danger fires.

**Threshold defaults**: 60% premium loss threshold.  
**Personalization**: Not user-configurable.

---

### 20. Expiry Day Overtrading

**Risk added per firing**: 20 points  
**Alert levels**: Caution (5 or more trades, or 10 or more lots), Danger (8 or more trades)

**What it is**: Excessive trading on the instrument's own expiry date. NSE market data shows
retail option activity in the last two hours of an expiry day has a structural loss rate above
85%. The combination of time decay accelerating, bid-ask spreads widening, and emotional 0DTE
(zero days to expiry) herding creates a statistically hostile environment for retail traders
who continue trading late into expiry.

**When it triggers**: Only after 13:00 IST (a conservative warm-up filter to allow legitimate
morning expiry trades). After that point, if the total count of today's completed trades on this
underlying reaches the threshold, the alert fires.

**Threshold defaults**: Caution at 5 trades or 10 lots, Danger at 8 trades.  
**Personalization**: Not user-configurable.

**Correction applied**: The trade count now correctly includes the current trade. Previously it
was off by one — the alert fired one trade late and displayed the wrong count.

---

### 21. Opening 10-Minute Trap

**Risk added per firing**: 10 points  
**Alert levels**: Caution (one condition met), Danger (both conditions met)

**What it is**: Entering a derivative position in the first 10 minutes after market open
(09:15–09:25 IST) and losing. The opening window has the widest bid-ask spreads of the day as
overnight gaps resolve, order books stabilise, and option pricing adjusts. NSE data shows 78%
of retail opening-window derivative trades are unprofitable.

**When it triggers**: The trade must be an option or futures contract entered between 09:15 and
09:25 IST and must close at a loss. At least one of these must also be true:

- Quick reactive exit: the trade was closed within 15 minutes of entry (spread damage or
  impulse entry that immediately reversed)
- Large premium loss: the trade lost 30% or more of its premium

If only one condition is met, caution fires. If both are met simultaneously, danger fires.
Profitable opening trades are never flagged — those may be deliberate strategies.

**Threshold defaults**: Window ends 10 minutes after open (09:25), quick-exit threshold 15
minutes, large-loss threshold 30% of premium.  
**Personalization**: Previously hardcoded; now configurable through the threshold system.

---

### 22. End-of-Session MIS Panic

**Risk added per firing**: 15 points  
**Alert levels**: Caution at 2 MIS trades after 15:00 IST, Danger at 3 or more

**What it is**: Intraday (MIS product) trades entered after 15:00 IST. Zerodha automatically
squares off all MIS positions before market close — for equity markets at 15:15 IST, for
futures and options at 15:25 IST. Voluntarily entering a new intraday position with minutes
until a forced automatic exit means you cannot manage the trade — you are simply gambling on
the last few minutes of the session.

**When it triggers**: The count of MIS trades entered after 15:00 IST today is compared to the
threshold. At 2 or more trades, caution fires with the time remaining until automatic squareoff.
At 3 or more, danger fires.

**Exchange-aware squareoff times**:
- Futures and Options (NSE F&O, BSE F&O): 15:25 IST
- Equity Intraday (NSE, BSE): 15:15 IST

**Threshold defaults**: Caution at 2 total MIS trades after 15:00, Danger at 3 or more.  
**Personalization**: Not user-configurable.

**Correction applied**: The count now correctly includes the current trade. Previously it was
off by one — the alert fired one trade late and displayed the wrong count in the message.

---

### 23. Post-Loss Recovery Bet

**Risk added per firing**: 20 points  
**Alert levels**: Caution at 2× average size, Danger at 3×

**What it is**: After two consecutive losses on the same underlying, placing one significantly
oversized position — the "I'll make it all back in one trade" impulse. This is among the most
thoroughly documented biases in retail trading literature. It differs from the Martingale pattern,
which requires a progressive escalation across multiple trades. This fires for a single outsized
bet after any two losses, regardless of what came before those two losses.

**When it triggers**: If the last two completed trades on the same underlying are both losses,
and the current trade's position size is 2 times or more the average size of the last three prior
trades on that underlying, caution fires. At 3 times or more, danger fires.

**Threshold defaults**: Caution at 2× average recent size, Danger at 3×.  
**Personalization**: Not user-configurable.

**Note**: Applies within the same underlying only. A massively oversized BANKNIFTY trade after
two NIFTY losses would not trigger this pattern because the underlying differs.

---

### Profit Giveaway

**Risk added per firing**: 20 points  
**Alert levels**: Caution at 50% erosion of session peak, Danger at 70%

**What it is**: Building significant profit during a session then giving most of it back in
subsequent trades — the "one more trade" trap. SEBI and NSE data show 38% of retail traders
with a profitable intraday session give back more than 50% of their peak gains in a single
subsequent trade. This pattern is distinct from Session Meltdown: meltdown fires when losses
exceed a percentage of the daily loss limit (requires being in the negative). This pattern fires
when profits erode past a percentage of the session's own peak — even if the trader is still
net positive for the day.

**When it triggers**: The system tracks cumulative session profit and finds the highest point
reached at any moment during the day. If the current profit has fallen 50% or more from that
peak, and the absolute erosion is at least ₹500, caution fires. If erosion reaches 70%, danger fires.

Requires the session to have peaked at ₹1000 or more — small fluctuations around breakeven
do not qualify.

**Threshold defaults**: Minimum peak of ₹1000, minimum erosion of ₹500, caution at 50%
erosion, danger at 70%.  
**Personalization**: Not user-configurable.

---

## Alert Overlap — When Multiple Patterns Fire for One Trade

Some patterns can fire simultaneously for the same trade. This is intentional — each pattern
captures a different dimension of the behavior. Known overlapping combinations:

| Pattern A | Pattern B | Scenario |
|-----------|-----------|----------|
| IV Crush Behavior | Premium Destruction | Fast large premium loss — only the higher-severity one is kept |
| Martingale Behaviour | Size Escalation | Increasing size on a losing underlying |
| Options Direction Confusion | Options Premium Avg Down | Call loss followed quickly by a put entry, same underlying |
| Revenge Trade | Rapid Re-entry | Re-entering same symbol within 5 min of a loss |
| Consecutive Loss Streak | Session Meltdown | Bad losing streak that simultaneously hits the daily limit |

The IV Crush / Premium Destruction overlap is the only one that is automatically deduplicated.
All other combinations can generate multiple alerts for one event.

---

## Patterns With Only One Severity Level

These patterns fire as caution only — there is no escalation to danger regardless of magnitude:

- Rapid Re-entry
- Panic Exit
- Rapid Flip
- FOMO Entry
- Options Direction Confusion
- Options Premium Averaging Down
- IV Crush Behavior
- Early Exit (Disposition Effect)

---

## Risk Score Reference

| Pattern | Points Added |
|---------|-------------|
| Session Meltdown | 30 |
| Revenge Trade | 25 |
| Premium Destruction | 25 |
| Cooldown Violation (internal only) | 25 |
| Consecutive Loss Streak | 20 |
| Expiry Day Overtrading | 20 |
| Options Direction Confusion | 20 |
| No Stop-Loss | 20 |
| Post-Loss Recovery Bet | 20 |
| Martingale Behaviour | 20 |
| Profit Giveaway | 20 |
| Size Escalation | 15 |
| Rapid Re-entry | 15 |
| FOMO Entry | 15 |
| Winning Streak Overconfidence | 15 |
| Options Premium Averaging Down | 15 |
| Rapid Flip | 15 |
| Excess Exposure | 15 |
| End-of-Session MIS Panic | 15 |
| Overtrading Burst | 10 |
| Panic Exit | 10 |
| IV Crush Behavior | 10 |
| Opening 10-Minute Trap | 10 |

---

*Last updated: 2026-06-12. Reviewed against all 23 patterns in the detection engine.*
