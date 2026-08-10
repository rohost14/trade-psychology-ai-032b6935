# What to test on the desk

Hands-on cases for http://127.0.0.1:8901. Each one names what should happen, so
you are checking a prediction rather than reading output and wondering.

**Read this first.** Most detectors compare one **closed** trade against the ones
before it. A BUY on its own tells them almost nothing — the *Round trip* button
buys and sells fifteen minutes apart in one click, which is the unit the engine
actually reasons in. If nothing fires after a single buy, that is correct.

When something does not fire and you expected it to, press **"Why didn't it
fire?"** before assuming a bug. It asks all 27 detectors about the session as it
stands and shows the numbers they are reading.

---

## 1. The floor between a scratch and a loss

Losing ₹400 and re-entering is not revenge. Losing ₹600 and re-entering is.

| | |
|---|---|
| Setup | Reset. Capital ₹5,00,000. |
| Do | Buy 50 @ 100, sell 50 @ 92 (−₹400). Then buy 150 @ 100. |
| Expect | **No revenge alert.** ₹500 is the floor — below it, the engine calls it a scratch. |
| Then | Reset, same shape but sell @ 88 (−₹600), re-enter. |
| Expect | Revenge is now detected. |

If both are silent the floor is broken; if both fire, it is not being read.

---

## 2. A streak needs three

| | |
|---|---|
| Do | Two losing round trips. |
| Expect | Nothing. Everybody loses twice. |
| Then | A third. |
| Expect | `Consecutive losses`, caution. A fifth takes it to danger. |

---

## 3. A win breaks the run

Two losing round trips, then a **winning** one, then two more losses.

**Expect:** no streak alert. Two and two is not five — the win resets it.

---

## 4. Doubling after every loss

Round trip losing 50 lots. Then 100. Then 200. Then 400.

**Expect:** `Averaging down` at danger, describing the progression 50→100→200→400.

**Also expect — and this is the fix you asked for:** you should *not* also get
"Rising position size" and "Recovery bet" as separate alerts. They describe the
same fact. They appear under **Detected, not shown** as `same_story`.

Before this was fixed, that single trade produced seven alerts.

---

## 5. Three lots is invisible

Same as above but stop at three round trips.

**Expect:** no martingale alert. The progression detectors need at least three
*prior* trades before they look. A reasonable floor, and not an obvious one —
worth knowing when reading live data.

---

## 6. Your own rules are louder than the behaviour

| | |
|---|---|
| Setup | Set **Cooldown 15 min**, Apply. |
| Do | Round trip at a loss, then buy again after 2 minutes. |
| Expect | `Rule breach` at danger, and it routes to the accountability partner. |
| Also | `revenge_trade` appears under **Detected, not shown** — "constitution breach took precedence". |

The rule you wrote for yourself is the more specific statement, so it wins.

---

## 7. Several rules at once is still one alert

Set cooldown 15, max consecutive losses 3, max position 2%. Then trade a losing
streak that breaks all three.

**Expect:** one `Rule breach` alert saying how many of your rules broke — not one
alert per rule.

---

## 8. The opening minutes

| | |
|---|---|
| Setup | Set the clock to `2026-08-05 09:17`. |
| Do | Buy a call at 140, sell at 70 eight minutes later. |
| Expect | `opening_5min_trap` in **Detected, not shown** — it is analytics-only by design, because entering at the open is common and innocent. It never alerts. |

Now do the same profitably. It should not even be detected.

---

## 9. One position, not three trades

Buy 50, buy 50 more, sell 100.

**Expect:** one closed trade of 100, not three. No overtrading alert — adding to
a position is one decision executed in pieces.

---

## 10. Flipping through zero

Buy 50. Then **sell 100**.

**Expect:** the long closes and a short of 50 opens. Two positions, not one of
double size. Watch the open-positions panel show −50.

---

## 11. Scaling out is not indecision

Buy 150. Sell 50, sell 50, sell 50 at rising prices.

**Expect:** no `direction_instability`, no overtrading. Taking profit in pieces
is one careful decision.

---

## 12. Rolling a strike

Buy `NIFTY26AUG24500CE`, lose on it, then buy `NIFTY26AUG24600CE`.

**Expect:** no `same_symbol_obsession`. A different strike is a different
position, and rolling is routine — flagging it would make the alert useless to
anyone who trades options seriously.

---

## 13. Averaging into a losing option

Round trip losing 40% of premium on a call. Twice. Then buy the same strike a
third time.

**Expect:** `Adding to a losing option`. Try it again with only a 10% loss —
should stay silent, because a 10% move on an option is an ordinary morning.

---

## 14. Delivery trades are invisible

Set Product to **CNC** and trade anything.

**Expect:** nothing at all. CNC is filtered out before the engine sees it —
deliberate product scope, not a bug.

---

## 15. Commodities run late

Set exchange **MCX**, symbol `CRUDEOIL26AUGFUT`, clock `16:30`, and trade.

**Expect:** no square-off panic. 16:30 is mid-session for MCX even though NFO
closed an hour earlier.

---

## What to send me

If something does not match, the useful report is:

1. What you did — the orders, in order
2. What you expected
3. What appeared, including the **Detected, not shown** panel
4. The output of **"Why didn't it fire?"**

That fourth one usually settles it on its own. Three of the bugs found this week
looked exactly like "nothing happened".

---

## Cleaning up

**Delete everything this desk created** removes every row under the desk's
synthetic account and touches nothing else — not the scenario suite, not
anything real.
