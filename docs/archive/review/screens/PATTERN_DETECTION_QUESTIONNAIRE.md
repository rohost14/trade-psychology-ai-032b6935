# Trader Survey — Understanding Your Trading Habits
### (Google Form — 3 minutes, 14 questions)

> Introductory text shown to trader:
> *"Hey! We're building a trading psychology tool and want to understand how real traders actually trade. No right or wrong answers — just tell us what you actually do, not what you think you should do. Takes 3 minutes."*

---

**Q1. What kind of trader are you?**
*(Select one)*

- [ ] Scalper — I make many trades a day, hold for minutes
- [ ] Day trader — I make a few trades a day, close everything by 3:30 PM
- [ ] Swing trader — I hold trades for 1–5 days
- [ ] Positional — I hold for weeks or more
- [ ] Mix of styles

---

**Q2. On a typical trading day, how many trades do you make?**
*(Select one)*

- [ ] 1–2
- [ ] 3–5
- [ ] 6–10
- [ ] 11–20
- [ ] More than 20
- [ ] I trade only a few times a week

---

**Q3. What do you mainly trade?**
*(Select all that apply)*

- [ ] NIFTY / BANKNIFTY / SENSEX Options (buying CE or PE)
- [ ] Stock Options (buying CE or PE)
- [ ] Options selling (selling CE or PE)
- [ ] NIFTY / BANKNIFTY Futures
- [ ] Stock Futures
- [ ] Equity / stocks (delivery)

---

**Q4. How much of your total trading capital do you typically put into a single options trade (as premium paid)?**
*(Select one — honest answer!)*

- [ ] Less than 2%
- [ ] 2% – 5%
- [ ] 5% – 10%
- [ ] 10% – 20%
- [ ] More than 20%
- [ ] I don't think in percentages — I just buy what I can afford

---

**Q5. How much of your total trading capital do you typically use as margin in a single futures trade?**
*(Select one — skip if you don't trade futures)*

- [ ] Less than 5%
- [ ] 5% – 15%
- [ ] 15% – 30%
- [ ] 30% – 50%
- [ ] More than 50%
- [ ] I use whatever margin is available

---

**Q6. Do you set a stop loss on your trades?**
*(Select one)*

- [ ] Always — I set SL before entering every trade
- [ ] Usually — most of the time
- [ ] Sometimes — depends on the trade
- [ ] Rarely
- [ ] Never — I exit manually when I feel it's right
- [ ] Not for options — the premium is my stop loss

---

**Q7. When you set a stop loss on a futures or equity trade, where do you typically put it?**
*(% loss from your entry price — skip if you don't trade futures/equity)*

- [ ] Less than 0.5%
- [ ] 0.5% – 1%
- [ ] 1% – 2%
- [ ] 2% – 3%
- [ ] More than 3%
- [ ] I don't use a fixed % — I use support/resistance levels

---

**Q8. For options trades, at what point do you usually exit a losing position?**
*(% of premium lost — skip if you don't buy options)*

- [ ] I exit when I've lost about 30% of the premium
- [ ] I exit at about 50% loss on premium
- [ ] I exit at 70–80% loss
- [ ] I let it go to near zero
- [ ] It depends on time left to expiry
- [ ] I don't have a fixed rule

---

**Q9. After taking a loss, how long do you usually wait before your next trade?**
*(Select one — be honest, not what you think you *should* do)*

- [ ] I re-enter immediately — I'm looking for the next setup right away
- [ ] A few minutes
- [ ] 5–15 minutes
- [ ] 15–30 minutes
- [ ] 30 minutes or more
- [ ] I stop for the day after a significant loss

---

**Q10. Have you ever increased your position size after a loss to try and recover it faster?**
*(Select one)*

- [ ] Never
- [ ] Once or twice, but I know it's wrong
- [ ] Yes, sometimes when I feel confident about the next trade
- [ ] Yes, often — it feels like the right thing to do in the moment

---

**Q11. At what point in a losing day do you usually stop trading?**
*(Select one)*

- [ ] I have a fixed daily loss limit — I stop when I hit it
- [ ] When I've lost around 1–2% of my capital for the day
- [ ] When I've lost around 3–5% for the day
- [ ] When I've lost 5–10% for the day
- [ ] I don't really have a fixed rule — I trade until the market closes or I feel done
- [ ] I rarely have losing days where I need to stop early

---

**Q12. How long have you been trading F&O (Futures & Options)?**
*(Select one)*

- [ ] Less than 6 months
- [ ] 6 months – 1 year
- [ ] 1–3 years
- [ ] 3–5 years
- [ ] More than 5 years

---

**Q13. How many trading alerts or warnings per day would feel genuinely useful — not annoying?**
*(Select one)*

- [ ] 1–2 max — I only want to hear about the serious stuff
- [ ] 3–5 — catch the important patterns without overwhelming me
- [ ] Up to 10 — I want detailed feedback on my session
- [ ] As many as needed — I want full visibility

---

**Q14. When you're clearly having a bad trading day, what would actually help you?**
*(Select one)*

- [ ] Just show me what's happening — I'll decide what to do
- [ ] Send me an alert so I'm aware, but let me keep going
- [ ] Push notification on my phone — I need something that breaks my focus
- [ ] Force a mandatory break — I know I ignore soft warnings when I'm emotional

---

*Thank you! Your answers will directly shape how we build alerts and behavioral tracking.*

---

## What We Do With the Answers (Internal — Not Shown to Traders)

Aggregate results from 50–100 traders give us:

| Survey Question | What It Tells Us |
|---|---|
| Q4, Q5 | Real position sizing norms by instrument type → replaces our fake 5% threshold |
| Q7, Q8 | Real SL % ranges by instrument → drives no-stoploss and loss-aversion detection |
| Q9 | Real cooldown behavior distribution → sets revenge trading time window defaults |
| Q10 | How common revenge sizing actually is → calibrates detection sensitivity |
| Q11 | Real daily loss tolerance → what "too much" actually means to traders |
| Q1, Q2 | Style + frequency distribution → overtrading baseline per style |
| Q13 | Alert tolerance → our daily cap target |
| Q14 | Intervention preference distribution → what % want hard stops vs soft |

This replaces ~71 magic numbers with data from actual traders.
