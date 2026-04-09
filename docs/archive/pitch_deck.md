# TradeMentor AI - Pitch Deck (3-4 Minute Pitch)

## Slide 1: The Problem & The Victim
**"90% of retail traders lose money. It's not the market, it's their mind."**

*   **The Problem:** Emotional trading (Greed, Fear, Tilt).
    *   Traders know *how* to trade (technical analysis), but fail to execute because of emotions.
    *   Common killers: Revenge Trading (recovering losses blindly), Overtrading (boredom), and Holding Losers (hope).
*   **Who's Affected:** 100 Million+ retail traders globally (Zerodha alone has ~12M users).
*   **The Gap:** Brokers give you charts and data, but no one protects you from *yourself* in real-time.

## Slide 2: The Insight & Why Me?
**"I built this because I lost money this way."**

*   **Why Me? (Founder Fit):**
    *   I am an active trader. I have experienced the "Tilt" where one bad trade leads to a spiral of losses.
    *   I realized that while trading, my IQ drops. I needed an external, rational guardian.
*   **Why Now?**
    *   **AI Maturity:** LLMs can now analyze complex behavioral data instantly, acting as a human-like coach.
    *   **API Access:** Brokers like Zerodha provide real-time data streams that make instant intervention possible.

## Slide 3: The Solution (Visuals)
**"Your Real-Time Risk Guardian."**

*(Visuals to show on slide)*
1.  **Dashboard:** Clean UI showing "Psychology Score: Caution (Revenge Trading Detected)".
2.  **WhatsApp Alert:** A notification screenshot: *"Stop! You've taken 4 losing trades in 1 hour. Cooldown enforced for 30 mins."*
3.  **The Intervention:** A blurred background of the trading terminal with a "Risk Lock" overlay.

*   **Core Value:** It stops you before you blow up your account. It's an airbag for your capital.

## Slide 4: Tech Approach
**"Speed is Safety."**

*   **Architecture (Real-Time Pipeline):**
    *   **Broker:** Zerodha Kite Connect (Websocket for live ticks/orders).
    *   **Backend:** FastAPI (Python) for high-performance async processing.
    *   **Brain:** Behavioral Analysis Engine + OpenRouter LLMs (Analyzing patterns vs. market context).
    *   **Database:** Supabase (PostgreSQL) for transactional speed and reliability.
*   **Data Flow:** Trade Placed -> Instant Pattern Check -> AI Risk Assessment -> Alert Sent (Latency < 200ms).

## Slide 5: Value & Go-To-Market
**"Cheaper than your next loss."**

*   **Business Model:** SaaS Subscription.
    *   Freemium: Basic tracking.
    *   Pro: Real-time WhatsApp alerts & Risk Locks ($10-20/month). *Value: Preventing one bad day pays for a year of subscription.*
*   **Go-To-Market:**
    *   **Communities:** Partnering with trading influencers/Telegram groups (trust-based).
    *   **Direct:** Twitter/X "Build in Public" showing live saves.

## Slide 6: Next Steps & Risks
**"From Watchdog to Co-Pilot."**

*   **Roadmap:**
    1.  **Mobile App:** Native notifications.
    2.  **More Brokers:** Expanding to Upstox, Angel One, Interactive Brokers.
    3.  **Journal:** Automated "Voice Notes" trading journal.
*   **Risks:** Reliance on Broker APIs (Platform risk).
*   **Mitigation:** Multi-broker support and "read-only" analysis modes.
