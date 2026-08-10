# Alert Lab — scenario catalogue

What must be tested, and why each case exists. Companion to `PLAN.md`.

Status: **written and passing — 108 scenarios.** See `alertlab/scenarios/` for
the code and `python alertlab/scripts/run.py` to run them.

For testing by hand rather than by suite, see `tradedesk/WHAT_TO_TEST.md`.

---

## How to read this

Every scenario has an ID, a trader story, and **both halves of the assertion**:

- `must_fire` — the pattern, at the stated severity
- `must_not_fire` — what a naive implementation would wrongly raise

**The second half is the point.** Twelve of the fifteen defects found reviewing this
week's work were false positives or silent suppressions. A suite that only asserts
presence would have passed on every one of them.

Severity vocabulary: `info` (evidence only, never alerts) · `caution` · `danger` ·
`critical` (the guardian tier).

---

## A. Capital tiers — the same behaviour at every size

Thresholds are largely percentages of declared capital, so identical behaviour must
produce identical *patterns* at every tier while the ₹ figures scale. A bug here reads as
"the product only works for people like the developer".

Run **A-01 through A-08 with one fixed behaviour** — three losing trades then a
double-size entry — changing only capital.

| ID | Capital | Typical lot value | What to watch |
|---|---|---|---|
| A-01 | ₹10,000 | one NIFTY lot exceeds capital | Does *every* trade trip `excess_exposure`? A trader who cannot afford one lot should get a coherent message, not a permanent alarm. |
| A-02 | ₹25,000 | one lot ≈ 40–60% of capital | The realistic floor for F&O. Position-size rules must be usable, not constantly breached. |
| A-03 | ₹50,000 | one lot ≈ 20–30% | |
| A-04 | ₹1,00,000 | comfortable single lot | The reference tier — most thresholds were tuned here. |
| A-05 | ₹5,00,000 | multi-lot normal | |
| A-06 | ₹10,00,000 | | |
| A-07 | ₹20,00,000 | | Does anything overflow or lose precision in ₹ formatting? |
| A-08 | ₹1,00,00,000 | | A ₹50k loss is 0.5% — must NOT read as a meltdown. Percentage rules must not be swamped by absolute ones. |

**A-09 — capital not declared.** `trading_capital` is null. Percent-of-capital rules must
degrade to silence, not to a divide-by-zero or a 0% denominator that fires everything.

**A-10 — capital stale.** Declared ₹5,00,000, account actually holds ₹50,000.
`capital_mismatch` must fire; percentage rules must not silently run on the wrong base.

**A-11 — same ₹ loss, two tiers.** ₹20,000 lost at ₹25k capital vs at ₹1Cr. One is a
session-ending event, the other is noise. Severity must differ.

---

## B. Trader archetypes

Each archetype runs a full realistic session. These are the shapes real people trade in,
and each has a signature failure mode.

**B-01 Scalper.** 30–60 round trips, holds of 30 seconds to 3 minutes, small size, same
instrument repeatedly.
`must_fire`: `overtrading_burst`, `daily_overtrading`.
`must_not_fire`: `rapid_reentry` on every single re-entry — that is their entire method,
and alerting on all of it is noise, not insight.

**B-02 Intraday directional.** 3–6 trades a day, one underlying, clear entries and exits.
The baseline. `must_not_fire`: anything, on a clean day. **A quiet session must be quiet.**

**B-03 Option buyer.** Long CE/PE only, premium decay is the enemy.
`must_fire`: `premium_loss_event` at the 40/60/80 bands, `opening_5min_trap` when they buy
into the open and it collapses.

**B-04 Option seller.** Short strangles/straddles held for the day, NRML.
`must_not_fire`: `premium_loss_event` — that detector is long-only by design, and firing
it on a seller would be wrong in both direction and meaning.

**B-05 Spread trader.** Bull call spreads, iron condors, 2–4 legs entered together.
`must_fire`: nothing, on a disciplined day.
`must_not_fire`: `overtrading_burst`, `daily_overtrading`, `revenge_trade`,
`size_escalation`, `direction_instability`, `rapid_reentry`, `no_stoploss`.
**This is the single most important negative scenario in the catalogue.** Two condors read
as eight trades and produced a danger-severity overtrading alert until this week.

**B-06 Positional / NRML.** Holds overnight, few trades, multi-day.
`must_not_fire`: `end_of_session_mis_panic` (not MIS), `holding_loser` on a deliberate
multi-day hold.

**B-07 Commodity / MCX.** Trades 17:00–23:30 IST.
`must_fire`: `end_of_session_mis_panic` near *MCX* square-off (~23:25), not at 15:10.
`must_not_fire`: anything triggered by NSE hours. A flat 15:00 cutoff once made every
evening MCX entry read as end-of-session panic.

**B-08 Expiry specialist.** Trades only Thursdays, heavy volume, cheap OTM options.
`must_fire`: `expiry_day_overtrading` past the count, with the higher expiry-day premium
thresholds applied.

**B-09 BTST.** Buys near close, sells next morning.
`must_not_fire`: `end_of_session_mis_panic` if the product is NRML/CNC.

**B-10 Beginner, first ever session.** No history, no rules set, three trades.
`must_not_fire`: anything needing a baseline. Cold start must be quiet, not confidently
wrong. This is the first impression the product makes.

**B-11 Recovering from a blowup.** Yesterday −₹80,000, today opens at 3× normal size.
`must_fire`: `post_loss_recovery_bet`, `size_escalation`.
Cross-session state must actually carry.

**B-12 Disciplined trader having a bad day.** Follows every rule, still loses six in a row.
`must_fire`: `consecutive_loss_streak`.
`must_not_fire`: `revenge_trade`, `martingale_behaviour`, `size_escalation` — losing is
not misbehaving, and conflating them destroys trust in every other alert.

---

## C. Per-detector coverage

Every one of the **33** pattern types, each with a positive case and the near-miss that
must stay silent. The near-miss is where false positives live.

| ID | Detector | Positive | Near-miss that must stay silent |
|---|---|---|---|
| C-01 | `revenge_trade` | entry 8 min after a ₹4,200 loss, 3× size | same entry 90 min later; after a ₹120 scratch loss; after a *winning* trade |
| C-02 | `rapid_reentry` | same symbol re-entered 2 min after a losing exit | different symbol; re-entry after a win |
| C-03 | `consecutive_loss_streak` | 5 losses in a row | 4 losses broken by a win in the middle |
| C-04 | `session_meltdown` | deep loss + accelerating pace | deep loss with pace slowing (they stopped) |
| C-05 | `post_loss_recovery_bet` | 3× size after a loss on the same underlying | 3× size after a loss on an unrelated underlying |
| C-06 | `profit_giveaway` | +₹30k peak, closes +₹4k | +₹30k peak, closes +₹28k |
| C-07 | `panic_exit` | fast manual close at a loss, no SL | fast close at a *profit*; SL-triggered exit |
| C-08 | `fomo_entry` | 4 distinct underlyings in 20 min | 4 NIFTY strikes in 20 min (one underlying — must not fire) |
| C-09 | `winning_streak_overconfidence` | size doubles after 4 wins | size doubles after 4 losses (that is martingale, not overconfidence) |
| C-10 | `size_escalation` | qty rising across losing trades, same underlying | qty rising across *winning* trades; qty rising on different underlyings |
| C-11 | `martingale_behaviour` | 1→2→4→8 lots after each loss | 1→2→4 lots after each *win* (pyramiding) |
| C-12 | `excess_exposure` | one position at 60% of capital | 60% of capital spread across six positions |
| C-13 | `no_stoploss` | manual exit at a loss, no SL on record | SL order triggered the exit |
| C-14 | `options_premium_avg_down` | adds to an option down 40% | adds to an option *up* 40% |
| C-15 | `premium_loss_event` | long CE down 85% of premium | short CE down 85% (seller — must not fire); long CE down 20% |
| C-16 | `overtrading_burst` | 9 entries in 25 min | 2 iron condors (8 legs) in 25 min — **must not fire** |
| C-17 | `daily_overtrading` | 15 trades in a session | 15 legs = 4 structures |
| C-18 | `expiry_day_overtrading` | 10 NIFTY trades on expiry after 13:00 | same 10 trades on a Monday |
| C-19 | `opening_5min_trap` | 09:17 entry, exits −45% in 8 min | 09:17 entry that closes green |
| C-20 | `end_of_session_mis_panic` | 3 MIS entries after 15:00 | 3 NRML entries after 15:00; 3 MIS entries at 11:00 |
| C-21 | `cooldown_violation` | re-entry 4 min into a 15-min cooldown | re-entry at minute 16 |
| C-22 | `constitution_violation` | 12 trades against a limit of 10 | 8 trades against a limit of 10 (approaching, at caution) |
| C-23 | `same_symbol_obsession` | 6 trades on one strike, net negative | 6 trades on one strike, net positive |
| C-24 | `direction_instability` | long→short→long on one underlying in 15 min | a CE + PE straddle (opposite by design — must not fire) |
| C-25 | `early_exit` | winners closed at a third of usual hold time | a winner closed early because a target was hit |
| C-26 | `win_rate_collapse` | today 15% vs 55% baseline | today 45% vs 55% baseline |
| C-27 | `strategy_breakdown` | one structure type consistently losing | one bad day for a structure that usually works |
| C-28 | `time_of_day_bias` | a losing hour repeated across weeks | one bad hour, once |
| C-29 | `overexposure` (entry) | position opened above the capital limit | position opened just under |
| C-30 | `portfolio_concentration` | 80% of exposure in one underlying | evenly spread across four |
| C-31 | `holding_loser` | position down 3% held 45 min | down 3% held 5 min; up 3% held 45 min |
| C-32 | `death_spiral` | several domains firing in one session | one pattern firing repeatedly (not multi-domain) |
| C-33 | `capital_mismatch` | declared ₹5L, deployable ₹50k | declared ₹5L, deployable ₹4.8L |

---

## D. Position and order mechanics

The layer where this week's defects actually lived.

**D-01 Partial fills.** One 300-lot order filling in three tranches. Must be **one** entry,
not three. Coalescing.

**D-02 Sliced order.** Trader deliberately splits into five tickets over 20 seconds. One
decision.

**D-03 Multi-leg entered together.** Four condor legs within 2 seconds → one structure.

**D-04 Multi-leg legged in.** Same four legs over 4 minutes. Beyond the 30s window they
count separately — *by design*. Documents the deliberate limit rather than pretending it
is covered.

**D-05 Covering a short.** Open short (SELL), cover (BUY). The BUY must **not** be treated
as an entry — it was, and every short seller got false cooldown alerts on the way out.

**D-06 Opening a short.** The opening SELL **must** be treated as an entry. Traders who
only short previously got no entry checks at all.

**D-07 Flip.** Long 100 → sell 150. Closes long, opens short. Must count as both.

**D-08 Scale in, winner.** Add above average price → `add_to_winner`, no sizing alert.

**D-09 Scale in, loser.** Add below average price → `add_to_loser`, feeds averaging-down.

**D-10 Add at exactly the average.** Neither. Must not guess.

**D-11 Partial exits.** Close 1/3, then 1/3, then 1/3. One CompletedTrade at the end, not
three.

**D-12 Equity, no expiry.** `RELIANCE` must not be parsed as a call option because the
ticker ends in "CE" — a real bug caught in testing this week.

**D-13 Same strike twice.** Two separate trades on one strike a minute apart. Two
decisions, not a two-leg structure.

---

## E. Time-of-day and calendar

Every scenario declares its own wall time; none require market hours.

**E-01** 09:15–09:25 opening window · **E-02** mid-session 11:00–14:00 ·
**E-03** 15:00–15:25 MIS run-up · **E-04** after 15:30, post-close ·
**E-05** expiry Thursday · **E-06** expiry-day premium thresholds shifted up ·
**E-07** MCX evening 20:00–23:30 · **E-08** weekend (nothing should run) ·
**E-09** trade spanning the session boundary · **E-10** entry today, exit tomorrow (BTST).

---

## F. Suppression and delivery gates

Four layers stack, and until this week two had never executed. Each needs a scenario
proving it fires **and** one proving it does not over-suppress.

**F-01 Dedup window.** Same pattern twice in 24h → one alert.
**F-02 Severity escalation through dedup.** caution then danger → the danger **must** get
through. Escalation always passes.
**F-03 Stateful re-arm.** Martingale doubles again → fires again despite the window.
**F-04 Five-minute bucket.** Two of the same pattern 3 minutes apart → one notification.
**F-05 Self-suppression regression.** A single alert must **not** suppress itself. This
silently disabled every live notification until it was found.
**F-06 Session hard cap.** 10 danger alerts in a session → capped.
**F-07 Cap must not hide an escalation.** A `critical` arriving after the cap. Currently
suppressed — the scenario documents the behaviour and forces a decision.
**F-08 Per-pattern mute.** Muted pattern → saved, not notified.
**F-09 Strategy-group suppression.** Condor legs → the eight suppressed detectors stay quiet.
**F-10 Staleness gate.** Bulk-synced trade from three hours ago → saved, not pushed.
**F-11 Live-vs-post merge.** Entry alert then the position closes → one row, enriched,
carrying the completed trade.
**F-12 Merge across instruments.** Live alert on NIFTY, unrelated BANKNIFTY closes → must
**not** link. Behaviour-cost would otherwise report another instrument's money.
**F-13 Delivery receipts.** A retry must not re-deliver.
**F-14 Per-position dedup.** Two options both bleeding → **both** alert. One used to
silence the other for 30 minutes.

---

## G. Severity ladder

**G-01** each band boundary exactly (40/60/80 premium; 80/100/120% of a rule) ·
**G-02** `critical` reaches the guardian panel, `danger` does not ·
**G-03** `info` is recorded as evidence and never alerts ·
**G-04** an unknown severity string never escalates ·
**G-05** `/risk/state` reports `critical` as critical, not caution.

---

## H. Guardian routing — decision only, no delivery

Delivery is parked with the business number. The **routing decision** is testable now and
is rendered in its own panel (`PLAN.md` §7).

**H-01** a `critical` guardian-eligible pattern appears in the guardian panel.
**H-02** a `danger` non-eligible pattern does **not**.
**H-03** a `caution` alert never appears — if it does, the severity floor is broken.
**H-04** the guardian message body contains no P&L, no instrument, no broker client id,
and no second-person instruction. It is a third party's message and must read like one.
**H-05** monthly budget: the 4th eligible event in a month does not route.
**H-06** budget spends on the worst, not the first — currently first-come. The scenario
documents the gap.

---

## I. Chaos

Three of this week's defects were in this class.

**I-01** duplicate fill (same order id twice) → one entry ·
**I-02** out-of-order fills (exit before entry) → no crash, no phantom trade ·
**I-03** missing exit → position stays open, no CompletedTrade invented ·
**I-04** ledger step fails → entry checks skip rather than guess ·
**I-05** fill arriving mid-drain → lands in the next window, never lost ·
**I-06** malformed fill (null price, zero qty, empty symbol) ·
**I-07** duplicate alert delivery attempt → receipts prevent it ·
**I-08** clock skew — `created_at` before `detected_at` → discarded, not reported as fast.

---

## J. Cold start

**J-01** no history, no rules, first trade · **J-02** rules set, zero trades ·
**J-03** 3 sessions (below the 10-session suggestion gate) · **J-04** exactly at the gate ·
**J-05** history imported from tradebook CSV — must not raise back-dated alerts.

---

## K. Quiet-day control

**K-01** A clean, disciplined session: four trades, sensible size, two winners, rules
respected. **Zero alerts.**

The most important scenario in the catalogue. Everything else asks "does it fire". This
asks "does it ever shut up" — and a mirror that speaks constantly is one nobody looks at.

---

## Coverage summary

| Section | Scenarios | Focus |
|---|---|---|
| A | 11 | capital tiers |
| B | 12 | trader archetypes |
| C | 33 | every detector, positive + near-miss |
| D | 13 | fill and position mechanics |
| E | 10 | time of day, calendar |
| F | 14 | suppression and delivery gates |
| G | 5 | severity ladder |
| H | 6 | guardian routing |
| I | 8 | chaos |
| J | 5 | cold start |
| K | 1 | quiet day |
| **Total** | **118** | |

Roughly half are `must_not_fire`. That ratio is deliberate: the defects that reach
production in this system are overwhelmingly things that fired wrongly or vanished
silently, not things that failed to compute.
