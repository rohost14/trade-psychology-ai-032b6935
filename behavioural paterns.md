**CORE MECHANICAL DATA SIGNALS**

These are raw signals extracted from trades, orders, and timing. They are not behaviors by themselves.

**1\. Trade Timing Signals**

Entry timestamp

Exit timestamp

Time gap between consecutive trades

Holding duration

Time-of-day buckets

Session-relative timing (early session, mid session, late session)

**2\. Size & Exposure Signals**

Quantity per trade

Change in quantity across trades

Exposure relative to user's recent average

Size variance over a rolling window

**3\. Outcome Signals**

Realized PnL

PnL sequence

Consecutive win/loss streaks

Distribution of wins vs losses

Magnitude of wins vs losses

**4\. Risk Discipline Signals**

Presence or absence of stop-loss orders

Time delay between entry and stop-loss placement

Stop-loss modification direction

Exit timing relative to loss expansion

These signals feed all higher-level behaviors.

PART 2 - PRIMARY BEHAVIORAL BIASES

These are fundamental psychological drivers. Every higher-level pattern maps to one or more of these.

**Loss-Triggered Impulse Bias**

Behavior User exhibits impulsive actions immediately following a loss.

Detectable via

New trade entered shortly after a losing trade

Multiple consecutive losing trades without meaningful cooldown

Increase in position size after loss

Reduced holding time after loss

Increased trade frequency following loss

This bias underlies revenge trading, martingale behavior, and tilt.

**Fear-Based Exit Bias**

Behavior User exits positions prematurely or irrationally due to fear of loss or loss expansion.

Detectable via

Winners exited significantly faster than losers

Frequent exits shortly after unrealized profit spikes

Loss exits delayed beyond statistically normal holding time

Stop-loss moved further away from entry instead of closer

Increased exit activity during drawdowns

**Overconfidence Bias**

Behavior User increases risk-taking after a sequence of wins or a large win.

Detectable via

Sudden increase in position size after profitable streak

Increased trade frequency after positive PnL

Reduced stop-loss discipline after wins

Higher exposure immediately following a high-PnL trade

**Recency Bias**

Behavior User assumes recent outcomes will repeat and adjusts behavior accordingly.

Detectable via

Repetition of same trade direction after wins

Reduced diversification after recent success

Persistence with losing patterns due to short-term success

Strategy rigidity immediately after a profitable run

**Opportunity Addiction (Compulsive Participation)**

Behavior User feels compelled to trade regardless of quality or outcome.

Detectable via

Trading every session without breaks

Consistently high trade count despite poor expectancy

Minimal variation in trade timing regardless of outcomes

No reduction in activity after losses

This is not strategy failure but compulsion.

**Loss Normalization Bias**

Behavior User becomes comfortable with frequent small losses, accumulating drawdown silently.

Detectable via

High frequency of small losing trades

Low variance PnL but negative expectancy

Many trades closed near small loss thresholds

Lack of large wins to offset cumulative losses

**Hope & Denial Bias:**

Behavior User holds losing positions hoping for reversal instead of acting rationally.

Detectable via

Loss holding duration significantly longer than win holding duration

Stop-loss widening after adverse move

Exit only after substantial loss expansion

Repeated delayed exits in losing trades

**Strategy Drift Bias**

Behavior User unintentionally shifts trading behavior within a session or day.

Detectable via

Sudden change in holding duration patterns

Sudden change in position sizing logic

Sudden change in trade frequency mid-session

Switching instruments or directions rapidly

This indicates loss of rule adherence.

PART 3 - NAMED BEHAVIORAL PATTERNS

These are user-facing interpretations built on top of primary biases.

**Revenge Trading**

Behavior User re-enters trades emotionally after losses.

Detectable via

Consecutive losing trades

Short time gap between losing exit and new entry

No meaningful cooldown period

Loss-triggered impulse bias present

**Overtrading**

Behavior User takes excessive trades beyond reasonable frequency.

Detectable via

Trade count exceeding personal baseline

Multiple trades within short time windows

Re-entries without outcome resolution

Opportunity addiction bias present

**Martingale Behavior**

Behavior User increases exposure after losses to recover faster.

Detectable via

Position size escalation after losing trades

Increasing exposure despite drawdown

Loss-triggered impulse bias combined with size escalation

**Inconsistent Position Sizing**

Behavior User lacks stable risk sizing logic.

Detectable via

High variance in quantity without PnL justification

Size increases after losses

Size decreases after wins

No stable baseline sizing behavior

**Emotional Exit**

Behavior User exits trades based on emotion rather than structure.

Detectable via

Winners exited too early

Losses held too long

Frequent exit modifications

Fear-based exit bias present

No Cooldown After Loss

Behavior User fails to pause after emotional or financial damage.

Detectable via

Trades entered within minutes of loss

No reduction in activity after losing streaks

Loss-triggered impulse bias

After-Profit Overconfidence

Behavior User becomes reckless after profits.

Detectable via

Increased trade frequency after green trades

Larger positions immediately after wins

Reduced stop-loss discipline post-profit

Overconfidence bias present

Chop Zone Addiction (Behavioral Version)

Behavior User repeatedly trades without directional conviction.

Detectable via

Many small trades with short holding time

Low variance PnL

High frequency without net progress

Opportunity addiction bias

PART 4 - COMPOUND BEHAVIORAL STATES

These represent advanced psychological degradation.

Tilt / Loss Spiral

Behavior User enters a cascading state of poor decisions after losses.

Detectable via

Multiple negative behaviors in same session

Loss-triggered impulse + overtrading + size escalation

Rapid accumulation of behavioral events

Deteriorating PnL with increasing activity

False Recovery Chase

Behavior User attempts to "get back to zero" emotionally.

Detectable via

Increased frequency after cumulative loss

Acceptance of poor risk-reward

Larger size with shorter holding

Hope bias combined with loss normalization

Emotional Looping

Behavior User cycles between fear, regret, and impulse repeatedly.

Detectable via

Alternating holding times

Alternating position sizes

Repeating behavioral patterns across days

No learning effect over time

PART 5 - AI LEARNING LAYERS (NO USER INPUT)

**Trade Embeddings**

Each trade represented as a vector using:

Timing features

Size features

Outcome features

Sequence position

Used for clustering and similarity detection.

Behavioral Classifier

Model predicts dominant biases:

Loss-triggered impulse

Fear-based exit

Overconfidence

Opportunity addiction

Trained on user's historical behavior.

Time-Based Behavior Modeling

Identifies:

High-risk time windows

Low expectancy periods

Personal performance rhythms

Self-Learning Personalization

Weekly retraining on recent trades:

Updates user's behavioral fingerprint

Adjusts thresholds dynamically

Refines future warnings and nudges

Loss patterns

Consecutive win/loss streaks

4\. Risk Behavior

Stop loss placement

Stop loss adherence

Trailing SL behavior

Exit panic