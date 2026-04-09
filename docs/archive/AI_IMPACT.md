# AI Impact Statement

**Role of AI:**
TradeMentor AI analyzes real-time trading data to detect detrimental emotional patterns (such as revenge trading or tilt). It acts as a rational "risk guardian," intervening with psychological stops and alerts when user behavior deviates from their defined discipline.

**Data Provenance:**
The system operates exclusively on the user's personal trading activity (orders, positions, P&L) accessed via the **Zerodha Kite Connect API**. It does not train on public datasets or store data for external model training; insights are derived strictly from the individual's specific live trading session and historical performance.

**Mitigation of Hallucinations:**
The AI is engineered to be **analytical, not predictive**. It strictly avoids forecasting market movements or suggesting trades. Interventions are triggered by deterministic logic (e.g., "3 consecutive losses") while the Generative AI provides the *contextual explanation*, ensuring actions are verifiable and grounded in hard data.

**Expected Outcome:**
The primary objective is to minimize capital erosion caused by emotional errors. By enforcing external discipline, the system aims to extend the user's trading longevity and foster sustainable, systematic trading habits.
