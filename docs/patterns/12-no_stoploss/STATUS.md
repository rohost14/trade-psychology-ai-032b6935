# 12 — `no_stoploss` · **MODIFIED**

v1.0.0 · exit-triggered · trade-scoped · `risk`/`alerting` · notification level 2

## What it reports
How far a losing position was allowed to run before it was closed, as a
percentage of the capital that position actually put at risk. Nothing more.

## Changed since the review
The review describes the old behaviour twice over.

**The claim (2026-08-29).** It used to end "No stop-loss order detected on this
trade", derived from the exit fill's order type. That asserted the absence of
something it had not looked at: the exit fill answers "was this exit executed
by a stop", not "did the trader have a resting stop". A trader holding a
resting SL who exits manually first shows MKT and would have been told they had
none — the inverse of the truth. The exit mechanism is now mentioned only when
it was actually observed.

**The denominator (F4, 2026-09-03).** It divided by premium paid for every
option regardless of direction. Correct for a long option, wrong way round for
a short one, where premium received is the maximum profit rather than the
capital at risk — the semantic baseline recorded "2900% loss of premium" at
danger severity. A short option now uses SPAN margin on strike x quantity via
`estimate_capital_at_risk`. The long path is byte-identical.

Two abstentions were added, both because a wrong confident answer is worse than
no answer: an unreadable strike (the fallback is known to be ~200x too small),
and an unknown direction (the two denominators differ by ~200x and neither
guess is defensible).

## Still open — and DATA-BLOCKED, measured 2026-09-03

Whether a resting stop EXISTED needs the order book. Kite does provide it and
we do persist it; the blocker is COVERAGE, and it is permanent.

**What Kite gives us** (`get_orders`): order_id, status, tradingsymbol,
exchange, transaction_type, order_type (MARKET/LIMIT/SL/SL-M), product,
variety, validity, quantity / pending / filled / cancelled, price,
trigger_price, average_price, order_timestamp, exchange_timestamp, tag, guid,
parent_order_id — **for the current day only**.

**What we persist**: all of it. `sync_orders_to_db` upserts every order
regardless of status, and the schema holds every field above. Live rows confirm
non-COMPLETE states survive: 344 orders, 262 COMPLETE, 50 CANCELLED, 29
REJECTED, 3 TRIGGER PENDING.

**Why it is still not enough.** `sync_orders_to_db` is called from two manual
API endpoints and **nothing schedules it** — the EOD beat syncs trades, not
orders. So the table holds whatever manual syncs happened to catch:

| | |
|---|---|
| completed trades | 5,701 across 41 exit days |
| days with ANY order data | 24 |
| **trades on a day with order data** | **112 — 2.0%** |

For 98% of trades, "no stop-loss order found" is indistinguishable from "no
sync ran that day". That is precisely the absence-as-claim defect removed from
this detector in the 2026-08-29 review, and re-introducing it with 2% coverage
would be worse than not having it.

**It cannot be backfilled.** Kite's `orders()` returns the current day only, so
the missing 17 days are permanently unavailable — unlike a threshold, this does
not become answerable by thinking harder.

**Even on the 2%, the dominant case is hard.** Of 34 SL orders, 27 are
CANCELLED, 3 TRIGGER PENDING, 4 COMPLETE. The common shape is a stop placed and
later removed, so judging protection means comparing cancellation time against
the position's life. `exchange_update_timestamp` supports that — but only where
there is data at all. And there is no bracket/cover linkage to lean on: 0 rows
carry a `parent_order_id` and every row is `variety='regular'`.

**Verdict: F4 is DATA-BLOCKED and no implementation was attempted.** The
detector's current behaviour is already correct — it reports how far a loss ran
and mentions the exit mechanism only when observed. Unblocking it needs
scheduled order sync going forward, and even then it would only ever be
answerable for trades after that change.

## Tests
`tests/test_no_stoploss_pattern12.py`, `tests/test_no_stoploss_denominator.py`
