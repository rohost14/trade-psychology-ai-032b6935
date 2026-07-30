# Competitive analysis — TradeZella

Researched 2026-07-31 from tradezella.com (home, features, pricing). Their `/features` marketing page and pricing were readable; some sub-pages were not. Everything below is either quoted from their site or verified against our own code.

**Summary:** TradeZella is the closest thing to a direct competitor we have found. They are building the same product — an AI trading journal that detects behavioural patterns and reports what they cost — with substantially more surface area, a much larger broker network, and a US-centric market. Our defensible advantages are real but narrow, and they are not the ones we would have guessed.

---

## 1. What they are

An AI-powered trading journal and analytics platform. Self-described as *"the AI trading journal that knows your trades, builds your game plan, and reviews"* automatically.

**Their stated audience:** unprofitable traders building discipline · developing traders refining strategy · profitable traders scaling · prop-firm traders managing compliance · trading communities and mentors.

Note how closely the first two match ours (`PRODUCT.md`: serious active traders plus improving traders).

**Pricing:** $35 / $59 / $99 per month; 25% off annual ($315 / $531 / $891). **No free tier and no free trial advertised.**

At ₹2,900–8,200 per month, this is steep for Indian retail. That is an opening for us, not a threat — but only if our pricing is deliberate rather than accidental.

---

## 2. Feature comparison

### They have it, we do not

| Feature | Notes | Should we? |
|---|---|---|
| **500+ broker and prop-firm sync, unlimited accounts** | Their moat. We support exactly one broker and are single-user until Zerodha compliance approval. | Not soon. Different problem. |
| **Trade replay** — tick-by-tick reconstruction, Level 2, time and sales, drawing tools, shareable | Post-trade forensics | No. Needs tick data we do not hold. |
| **Backtesting** — tick-level, bar-by-bar replay, multi-strategy comparison | | **No.** A different product. |
| **Playbook / setup tagging** | Lets them answer "which of my setups actually makes money". We have no concept of a setup at all. | **Yes**, if auto-inferred |
| **R-multiple statistics** | We compute expectancy; R-multiple is the more standard discipline metric | **Yes**, cheap |
| **Prop-firm sync** — rule monitoring, daily drawdown, pass-rate forecasting | | No. Not our market. |
| **Community** — private Spaces, mentor mode, live challenges, leaderboards | | **No.** Gamification, against the charter. |
| **Zella University** — bootcamps, webinars, courses | | Not now |
| **50+ customisable reports** | We ship fixed analytics tabs | Partially |
| **AI agents as named characters** — Habit, Risk Management, Sentiment (tilt), Custom | Same idea as our engine, but *legible* | **Yes.** Best idea on their site. |
| **Screenshots and voice memos on entries** | | **No.** Manual input. |

### We have it, they do not

1. **Real-time intervention.** Our engine runs per completed trade on live postbacks and raises alerts *during the session*. TradeZella is fundamentally a journal reviewed afterwards; their "steps in when it matters" copy is new and unproven. **This is our largest structural advantage and it is architectural, not cosmetic — they cannot add it by shipping a screen.**

2. **Behaviour→money as fact rather than model output.** We attribute cost to the specific trades that triggered each detection, through `trigger_completed_trade_id`. They advertise *"Trained on 20.2B trades. Knows your patterns better than you do."* — a model trained across other people's data. **Ours is reconcilable against a contract note. Theirs is not falsifiable.** In a product whose entire premise is trust, that difference matters more than feature count.

3. **My Record.** Pre-trade lookup of your own realised history on the instrument you are about to trade. They analyse after the fact; we answer before it. No equivalent found on their site.

4. **My Rules constitution**, with tighten-instantly and loosen-behind-friction. A behavioural mechanism, not a report. They have "risk guardrails" inside reporting, which is not the same thing.

5. **Zero manual input by design.** Their product leans on journaling, notes, screenshots, voice memos and trade ratings. Our own measured evidence — 55 alerts fired, 0 outcomes recorded — says that does not happen. We should read their reliance on it as a weakness, not a gap.

6. **Indian F&O native.** NSE session windows, expiry-day detection, MIS/NRML products, lots and multipliers, ₹ raw P&L with no charge estimation, WhatsApp as a delivery channel. They are US-centric.

7. **Guardian mode** — alerting a nominated third person.

### Both have it

Automated journaling from broker sync · behavioural pattern detection · time-of-day analysis · tilt detection · best and worst day · calendar view · win rate and profit factor · AI chat grounded in the user's own trades · loss-recovery framing.

**Correction to an earlier assessment in this repo:** we already ship a 90-day calendar (`PatternCalendar` on My Patterns). It is not a missing feature. It is *buried on a secondary screen and coloured by alert severity rather than by money*, which is a placement and encoding problem, not a capability gap.

---

## 3. What to take, in priority order

1. **The agent framing.** Naming the watchers — Habit, Risk, Tilt — turns an abstract 28-detector engine into something a trader can hold in their head. Almost pure packaging, near-zero engineering, largest perceived gain. Our detectors already group this way.
2. **Promote the calendar to the Dashboard and colour it by money**, not severity. The component exists.
3. **Best and worst day.** Trivial from data we already hold.
4. **Setup tagging with per-setup P&L.** The one real capability gap that fits our charter. **Must be auto-inferred from the trade shape** — strike distance, expiry proximity, direction, time of entry — because a tag the trader has to type is a tag that will not exist.
5. **R-multiple** alongside expectancy.

## 4. What to refuse

- **Community, leaderboards, challenges.** Gamification, explicitly against the product charter.
- **Backtesting and trade replay.** Different products; both need tick data we do not have.
- **Prop-firm sync.** Not our market.
- **Deeper manual journaling.** Their screenshots-and-voice-memos direction is exactly the input our evidence says will not be provided.

## 5. The honest strategic read

They are ahead on breadth, brokers, and packaging. We are ahead on **timing** (live rather than retrospective), **provability** (your own trades rather than a model over everyone's), and **fit** (Indian F&O, one broker done properly).

The risk is not that they out-feature us — they already do. It is that they out-*explain* us. Their agent framing communicates a behavioural engine better than our alert feed does, and that is the cheapest thing on this list to fix.

The pricing gap is the commercial opening: no free tier, ₹2,900+ a month, and a US-shaped product for an Indian F&O trader who wants their Kite data understood.
