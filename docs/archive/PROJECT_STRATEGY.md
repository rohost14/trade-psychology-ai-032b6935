# TradeMentor AI: Strategic Review & Roadmap

## 1. Market Research & Gap Analysis
**The Landscape:**
*   **Journaling Giants:** Edgewonk, TraderSync, TraderVue.
    *   *Focus:* Post-trade analysis. "What went wrong yesterday?"
    *   *Strengths:* Beautiful charts, equity curves, tag analysis.
    *   *Weakness:* Passive. They tell you you *did* revenge trade, but they don't stop you *while* you are doing it.
*   **Psychology Apps:** ReThink, various meditation apps.
    *   *Focus:* Mindfulness, guided breathing.
    *   *Weakness:* Disconnected from the actual trading execution.

**The "Blue Ocean" Gap for TradeMentor AI:**
**Real-Time Intervention (The "Airbag" Concept).**
No major tool acts as an active risk manager that sits *between* the trader and the broker API to literally say "Stop" or "Cooldown" in real-time. By leveraging the Zerodha API, TradeMentor AI can be the first **Active Risk Guardian**.

## 2. Codebase Audit
**Current Status:**
*   **Backend (Strong Foundation):**
    *   `TradeSyncService`: Capable of full synchronization (Orders, Trades, Positions).
    *   `RiskDetector`: Logic for "Consecutive Losses", "Revenge Sizing", "Overtrading" is already implemented.
    *   `Webhooks`: Real-time ingestion via Zerodha Postbacks is set up.
    *   `Celery`: Asynchronous processing architecture is present (crucial for scaling).
    *   **Verdict:** The "Brain" is 80% ready.

*   **Frontend (Missing/Incomplete):**
    *   The `frontend` directory seems to be missing or misconfigured in the root check.
    *   **Verdict:** Needs immediate attention to visualize the backend's power.

*   **Missing Plumbing:**
    *   **WebSocket Stream:** You are relying on Postbacks (Webhooks). Ideally, an active WebSocket connection (Ticker) allows for faster P&L monitoring for "Open Position Anxiety" detection.
    *   **Emergency "Kill Switch":** The backend can detect risk, but it cannot currently *act* (e.g., square off positions or block new orders).

## 3. Recommended Roadmap (The "Winning Features")

### Phase 1: The "Mirror" (Immediate Value)
*   **Goal:** Perfect Reflection of behavior.
*   **Feature:** **Automated Journal**.
    *   Users hate manual entry. Auto-sync trades, categorize them, and use LLM to write a "Daily Recap" email/WhatsApp message.
    *   *Tech:* `TradeSyncService` + `LLM Service`.

### Phase 2: The "Guardian" (Unique Value Prop)
*   **Goal:** Active Protection.
*   **Feature:** **The Kill Switch / Cooldown Mode**.
    *   If `RiskDetector` flags "Revenge Trading" (e.g., 3 losses in 15 mins), the system should:
        1.  Send a WhatsApp Alert (Implemented).
        2.  (New) **Block new orders** (by untrusting the API token temporarily or utilizing a "Guardian" PIN).
    *   *Tech:* Needs new `OrderManager` service.

### Phase 3: The "Coach" (Retention)
*   **Goal:** Improvement over time.
*   **Feature:** **Pre-Market Visualization**.
    *   Before market opens, WhatsApp the user: "Yesterday you lost money by overtrading at 10 AM. Today, let's focus on waiting for the first hour."
    *   *Tech:* `Scheduler` + `LLM` + `Historical Analysis`.

## 4. Key Gaps to Fix Now
1.  **Frontend Re-initialization:** We need to confirm where the React app lives.
2.  **Redis Setup:** Ensure Redis is stable for the Celery tasks (critical for the real-time webhooks).
3.  **Deployment:** Move from `localhost` to a cloud server (Render/Railway/AWS) so webhooks work 24/7.
