# Trade Desk

Place trades by hand and watch the real behavioural engine react.

```
python tradedesk/server.py      →  http://127.0.0.1:8901
```

One terminal. No Celery worker, no Redis, no broker login, no OAuth, no market
hours.

## Why this exists

The scenario suite proves the engine behaves correctly against 108 situations
**I** wrote. That is worth something, and it is not the same as you being able
to check it — you did not choose those trades, and a passing suite is still my
word about my own work.

Here you choose. Every alert comes from the same production code the live system
runs: `backend/app/services/behavior_engine.py` and the 27 detectors, imported,
never copied, never simplified.

## What you control

| | |
|---|---|
| Capital | any figure — several detectors and every rule reason as a fraction of it |
| Your rules | daily loss limit, trade limit, max position %, cooldown, consecutive losses |
| The clock | set it, or wait N minutes before an order |
| Orders | instrument, side, quantity, price, product, exchange |

The clock matters more than it looks. `opening_5min_trap` only examines
09:15–09:25, expiry rules need an actual expiry day, square-off rules need the
last half hour. Trading at 10:00 on a Wednesday means nothing about the time
itself can fire, so the first thing you see is caused by your trades.

## What you see

**Alerts**, as they fire, with severity and the message a real user would get.

**Detected, not shown** — every detection that did *not* become an alert, and
which layer stopped it: deduplicated, shadow mode, info-tier, or a constitution
breach taking precedence. No other tool in this project shows this, and it is
the half that matters when you are asking whether the thing is honest.

**Would reach your accountability partner** — the routing decision. Delivery is
parked until the business number exists; the decision is testable now. Only
`session_meltdown` and `constitution_violation` are eligible, at danger or above.

**Why didn't it fire?** — the button that makes this worth using. It asks all 27
detectors about the session as it stands and reports each verdict, alongside the
facts the engine is reading and the limits it is checking against.

It does **not** re-implement any detector's conditions in order to explain them.
A second copy of "martingale needs three prior trades" would drift from the
first and then confidently explain behaviour the engine no longer has. It calls
the real functions, reports silence as silence, and shows you the inputs. You
draw the conclusion — that is the point, since you are checking my work rather
than reading my summary of it.

## Things worth trying

Nothing here is scripted, so these are starting points rather than a script.

- Lose ₹400, then re-enter bigger. Nothing fires — ₹500 is the floor that
  separates a scratch from a loss worth flagging. Now lose ₹600 and repeat.
- Buy 50, buy 50 more, sell 100. One position, not three trades.
- Sell 100 while long 50. The position flips through zero: one round closes and
  a short opens, and the engine treats them as two positions.
- Set the clock to 09:17, buy a call, sell it eight minutes later at half price.
- Four losses, doubling the size each time. Then try three — the progression
  detectors need at least three prior trades before they look, which is a
  reasonable floor and not an obvious one.
- Set a 15-minute cooldown, lose, and re-enter after two. The rule you wrote is
  louder than the behaviour behind it, so the constitution alert fires and the
  ordinary pattern is held back — visible in "detected, not shown".
- Leave a position **open** and press the probe. Entry-time detectors evaluate
  against positions that have not resolved; that is the newest code in the
  system and it runs in shadow.

## Data

Everything lives in the normal database, under a reserved synthetic account
(`00000000-0000-4000-8000-000000000011`) that exists for this purpose and
nothing else.

**Delete everything this desk created** removes every row under it and touches
nothing else — not the scenario suite's account, not anything real.

The desk and the Alert Lab use different accounts on purpose. The suite tears
its account down before *every* scenario, so sharing one would mean a suite run
deletes your open positions from under you. Both can run at once.

## Not modified

No file under `backend/app` is changed by any of this. The seams — fake Redis,
eager Celery, a frozen clock — are applied from outside, and are the same ones
`alertlab/runner/harness.py` uses, imported rather than duplicated.

If your trading finds a production bug, it gets reported and you decide what
happens next. Three were found that way this week.
