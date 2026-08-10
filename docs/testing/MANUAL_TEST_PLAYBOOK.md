# Manual Test Playbook — behavioural patterns and alerts

Trade-by-trade instructions for every detector: what to place, how long to wait,
what should fire, and at what severity.

Run it on the **Trade Desk** — `python tradedesk/server.py` → http://127.0.0.1:8901.
No broker login, no market hours, no Celery, no Redis. One terminal.

Every threshold quoted here was read out of `backend/app/core/trading_defaults.py`
at the time of writing. Where a number below disagrees with the code, **the code
is right and this document is stale** — check `COLD_START_DEFAULTS`.

---

## Before you start

**Most detectors need CLOSED trades.** They compare one completed round trip
against the ones before it. A BUY on its own produces almost nothing, and that
is correct, not a bug. Use the desk's **Round trip** button — it buys and sells
fifteen minutes apart in one click.

**The clock is yours.** Several detectors only look inside a time window: the
opening trap at 09:15–09:25, expiry rules on an expiry day, late-session rules
in the last half hour. Default is 10:00 on a Wednesday, deliberately quiet.

**Every detector defaults to ₹5,00,000 capital** unless you change it. The
constitution rules default to empty — set them explicitly when a test needs one.

**"Why didn't it fire?"** answers the question before you report a bug. It asks
all 27 detectors about the current session and shows the numbers they read.

---

## How to read a test

| | |
|---|---|
| **Setup** | capital, rules and clock to set first |
| **Trades** | exact orders, in order, with the gap before each |
| **Fires** | what must appear, and at what severity |
| **Silent** | what must NOT appear, and why |

Severities: `info` (evidence only, never alerts) · `caution` · `danger` ·
`critical`. Only `session_meltdown` and `constitution_violation` can reach an
accountability partner, at danger or above.

---

# 1. Emotional patterns

## 1.1 Consecutive losses
`consecutive_loss_streak` · caution at **3**, danger at **5**

**Trades** — three losing round trips, 30 min apart:

| # | Gap | Order |
|---|---|---|
| 1 | — | BUY 50 NIFTY26AUG24500CE @ 100 → SELL @ 94 |
| 2 | 30m | same, again |
| 3 | 30m | same, again |

**Fires:** `Consecutive losses`, caution — "3 consecutive losing trades".
Two more takes it to danger.

**Also check:** insert a **winning** round trip between #2 and #3. The streak
resets — two and two is not three.

---

## 1.2 Trade straight after a loss
`revenge_trade` · loss must exceed **₹500**, re-entry within **20 min**

| # | Gap | Order |
|---|---|---|
| 1 | — | BUY 50 @ 100 → SELL @ 88 (−₹600) |
| 2 | 5m | BUY 150 @ 100 |

**Fires:** `Trade straight after a loss`.

**Silent when:** the loss is under ₹500. Repeat with SELL @ 92 (−₹400) and
nothing fires — the engine calls that a scratch. This floor is real and it
already caught one wrong test of mine.

---

## 1.3 Immediate re-entry
`rapid_reentry` · same instrument within **5 min** of a losing exit

Same as above but re-enter after 3 minutes.

**Fires:** nothing — it is **info severity by design**. Profitable traders
re-enter quickly, so this is recorded as evidence and feeds revenge confidence
instead of alerting. It appears under **Detected, not shown**.

That is the correct behaviour. A visible alert here would be the bug.

---

## 1.4 Repeated same instrument
`same_symbol_obsession` · **3** losses and **2** re-entries on one underlying

Four losing round trips on `NIFTY26AUG24500CE`, 30 min apart, sizes 50 / 75 /
100 / 150.

**Fires:** `Repeated same instrument` — and danger rather than caution once the
size is climbing too.

**Silent when:** you roll to a different strike. Repeat with 24500CE, then
24600CE, then 24700CE — a different strike is a different position, and rolling
is routine.

---

## 1.5 Fast manual exit
`panic_exit` · manual exit inside **5 min** at a loss

One round trip held **3 minutes**, closed down 30%.

**Fires:** `Fast manual exit`.

---

## 1.6 Gains given back
`profit_giveaway` · **50%** of session peak erased, peak above ₹1,000

| # | Gap | Order |
|---|---|---|
| 1 | — | BUY 100 @ 100 → SELL @ 120 (+₹2,000) |
| 2 | 60m | BUY 100 @ 100 → SELL @ 112 (+₹1,200) |
| 3 | 60m | BUY 100 @ 100 → SELL @ 82 (−₹1,800) |

**Fires:** `Gains given back` — up ₹3,200 by noon, most of it handed back.

---

# 2. Sizing and risk

## 2.1 Averaging down (martingale)
`martingale_behaviour` · caution at **1.5×**, danger at **2.0×**, needs **3+ prior trades**

Four losing round trips, 25 min apart, doubling: **25 → 50 → 100 → 200**.

**Fires:** `Averaging down`, danger, naming the progression.

**Silent when:** you stop at three round trips. The progression detectors need at
least three *prior* session trades before they evaluate. A three-trade martingale
is invisible by design — worth knowing when reading live data.

**Also silent when:** you size up after **wins** rather than losses. That is the
mirror image and is a different pattern entirely.

**Consolidation check (this is the one that was broken):** on the fourth trade
you should get **one** sizing alert, not three. `Rising position size` and
`Recovery bet` describe the same fact and appear under **Detected, not shown**
marked `same_story`. Before this was fixed that single trade produced seven
alerts.

---

## 2.2 Rising position size
`size_escalation` · **30%** growth across three trades while losing

Four losing round trips at **50 → 100 → 150 → 200**, 25 min apart.

**Fires:** `Rising position size` — unless martingale also fires, in which case
martingale wins and this is folded. That is intended.

---

## 2.3 Recovery bet
`post_loss_recovery_bet` · **2.0×** the recent average after losses, needs 3+ prior trades

Three losing round trips at 50 lots, then one at **200**.

**Fires:** `Recovery bet` — or is folded into martingale if the earlier trades
also formed a progression.

---

## 2.4 Oversized exposure
`excess_exposure`

**Setup:** capital **₹5,00,000**, max position size **20%**.

One round trip of **4,000 lots @ 100** — ₹4,00,000, 80% of the account.

**Fires:** `Rule breach` (constitution), danger, and it routes to the
accountability partner.

---

## 2.5 Size up after wins
`winning_streak_overconfidence` · **3** wins then **1.3×** size

Four winning round trips at 50 lots, then a fifth at **150**.

**Fires:** at entry, in shadow — leave the fifth position **open** and press the
probe. This is one of the entry-time detectors and does not alert yet.

---

# 3. Options-specific

These were **completely dead on live trades until 9 August** — `instrument_type`
was NULL on every live completed trade and twelve guards read it. If any of these
go quiet again, that is the first thing to check.

## 3.1 Premium destruction
`premium_loss_event` · caution **40%**, danger **60%**, critical **80%**

BUY 50 `NIFTY26AUG24500CE` @ 120 → SELL @ 18 after 45 min (85% of premium gone).

**Fires:** `Premium destruction`, critical.

**Silent when:** you SHORT the option instead. Long-only by design — a seller
loses differently.

---

## 3.2 Adding to a losing option
`options_premium_avg_down` · prior option position must have lost **20%+**

| # | Gap | Order |
|---|---|---|
| 1 | — | BUY 50 @ 120 → SELL @ 72 (40% gone) |
| 2 | 30m | BUY 50 @ 100 → SELL @ 62 |
| 3 | 30m | BUY 100 @ 90 |

**Fires:** `Adding to a losing option`.

**Silent when:** the losses are only 10%. An ordinary morning on an option.

---

## 3.3 Expiry-day activity
`expiry_day_overtrading` · **5** trades caution, **8** danger

**Setup:** clock to an actual expiry Thursday, and use a symbol whose expiry
matches. The parser derives expiry from the symbol — a `26AUG` contract on a
different date is never an expiry day. This tripped one of my own scenarios.

Six round trips after 13:00.

**Fires:** `Expiry-day activity`.

---

## 3.4 Direction flip-flop
`direction_instability`

BUY `NIFTY26AUG24500CE`, lose on it, then within minutes BUY
`NIFTY26AUG24500PE` — the opposite view on the same underlying.

**Fires:** `Direction flip-flop`.

**Silent when:** you buy the CE and PE **together**. That is a straddle, not
indecision. Also silent when you scale out of one position in three pieces.

---

# 4. Time-of-day

## 4.1 Opening-minutes entry
`opening_5min_trap` · window **09:15–09:25**

**Setup:** clock `2026-08-05 09:17`.

BUY 50 @ 140 → SELL @ 70 eight minutes later.

**Fires:** nothing — **analytics-only by design.** Entering at the open is common
and innocent, so it is recorded as evidence, never alerted. Check **Detected, not
shown**.

**Silent entirely when:** the opening trade is profitable. Not even recorded.

---

## 4.2 Chasing several instruments
`fomo_entry` · **3** instruments inside **30 min**

**Setup:** clock `09:20`.

Round trip NIFTY CE, then NIFTY PE at 09:30, then BANKNIFTY CE at 09:40 left
open.

**Fires:** at entry, in shadow. Use the probe.

---

## 4.3 Late intraday entries
`end_of_session_mis_panic`

**Setup:** clock `15:05`. Product **MIS**.

Three entries before the 15:30 square-off.

**Fires:** `Late intraday entries`.

**Silent when:** product is **NRML** — an overnight position has no square-off
pressure. Also silent on **MCX at 16:30**, which is mid-session there even though
NFO closed an hour earlier.

---

# 5. Your own rules

The constitution is the one part a trader writes themselves, so a breach is a
more specific statement than the behaviour behind it — and it wins.

## 5.1 Cooldown ignored

**Setup:** cooldown **15 min**. Apply.

Losing round trip, then re-enter after **2 minutes**.

**Fires:** `Rule breach`, danger, routes to the accountability partner.

**Also:** `revenge_trade` appears under **Detected, not shown** —
"constitution breach took precedence".

---

## 5.2 Several rules at once

**Setup:** cooldown 15, max consecutive losses 3, max position size 2%.

Trade a losing streak that breaks all three.

**Fires:** **one** `Rule breach` alert stating how many of your rules broke —
not one alert per rule.

---

## 5.3 Tightening versus loosening

Not testable on the desk — it is a `PUT /api/profile` behaviour. Covered by
`backend/tests/test_constitution_gate.py` (29 tests): tightening applies
instantly, loosening needs confirmation and waits for the next session if the
market is open.

---

# 6. Mechanics that must NOT alert

These are the false positives that matter most. Each is ordinary trading that a
naive implementation would flag.

| Do this | Must stay silent | Why |
|---|---|---|
| BUY 50, BUY 50, SELL 100 | overtrading | One position built in pieces |
| BUY 150, SELL 50 ×3 | direction instability | Scaling out is one decision |
| BUY 50, then SELL 100 | oversized position | The flip is two positions, not one double-sized |
| Straddle: BUY CE + BUY PE together | direction instability, burst | One structure, four fills |
| Iron condor: 4 legs at once | overtrading burst | One decision arriving as four fills |
| Product **CNC** | everything | Delivery is filtered out before the engine |
| Same order id delivered twice | size escalation | Idempotency guard — a doubled fill would look like a bigger position |

The last one is worth doing deliberately: it is the failure mode that does not
look like a bug, because a double-counted fill reads as a larger position rather
than an error.

---

# 7. Alert volume

The thing worth watching that no single test covers.

Trade a full session — twenty or so round trips, mixed wins and losses, across
several strikes.

**Expect:** somewhere in the low tens of alerts, not one per trade. If a single
closing trade produces more than three, something has regressed in
`BehaviorEngine._consolidate`.

Run `python alertlab/scripts/audit.py` for the automated version of this
question across all 108 scenarios — it reports, per trade, whether several
detectors described one fact, whether a composite fired alongside what it
summarises, and whether one trade produced several rule alerts.

---

# Reporting something

The useful report is four things:

1. The orders you placed, in order
2. What you expected
3. What appeared — including **Detected, not shown**
4. The output of **Why didn't it fire?**

The fourth usually settles it. Three of the bugs found in the week of 9 August
looked exactly like "nothing happened", and two of them were real.

---

# Cleaning up

**Delete everything this desk created** removes every row under the desk's
synthetic account (`00000000-0000-4000-8000-000000000011`) and touches nothing
else — not the scenario suite's account, not anything real.
