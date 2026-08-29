# Canonical Trading Semantics

**29 Aug 2026. Audit deliverable 1. No code changed in this document.**

What the engine believes about instruments and direction, established from code.
Companion to [`SEMANTIC_CONTRACT.md`](SEMANTIC_CONTRACT.md), which defines the ten
structural concepts (position, trade, fill, exit, …).

---

## 1. The instrument × direction matrix

All eight combinations, measured through the real `classify()` / `risk_basis()`
path after the Stage-1 and F3 fixes:

| combination | class | denominator kind | at risk (worked example) | comparable |
|---|---|---|---|---|
| **Buy Call** | `long_option` | `loss_ceiling` | ₹9,000 (premium paid) | ✓ |
| **Sell Call** | `short_option` | `margin_posted` | ₹225,000 (SPAN of contract notional) | ✓ |
| **Buy Put** | `long_option` | `loss_ceiling` | ₹9,000 | ✓ |
| **Sell Put** | `short_option` | `margin_posted` | ₹225,000 | ✓ |
| **Buy Future** | `futures` | `margin_posted` | ₹225,000 | ✓ |
| **Sell Future** | `futures` | `margin_posted` | ₹225,000 | ✓ |
| **Buy Equity** | `equity` | `notional` | ₹290,000 | ✓ |
| **Sell Equity** | `equity` | `notional` | ₹290,000 | ✓ |

*(NIFTY 25000 strike, qty 75, premium 120, future at 25000; RELIANCE 100 @ 2900.)*

### Direction is never inferred from CE/PE — verified

**The single most important thing to state, because the audit brief asks for it
twice: nothing in the engine treats CE as bullish or PE as bearish.**

`classify()` (`core/instrument_risk.py`) branches on `instrument_type` for the
*class* and on `direction` for long-vs-short. `LONG` on a CE and `LONG` on a PE
are both `long_option` — the engine holds "I bought an option", not "I am
bullish". Verified by execution, all eight rows above.

The one detector that ever reasoned about CE→PE as a directional statement was
`direction_instability`, retired 28 Aug 2026 after measurement contradicted its
premise. `grep` confirms zero remaining occurrences.

### What direction means per instrument

| instrument | LONG means | SHORT means | loss bound |
|---|---|---|---|
| option | bought it, paid premium | **wrote it**, received premium | LONG: premium. SHORT: **unbounded** |
| future | bought the contract | sold the contract | unbounded both ways |
| equity | own the shares | borrowed and sold | LONG: to zero. SHORT: **unbounded** |

### The one remaining gap in this matrix

**Short equity is given the same `notional` denominator as long equity.**
`estimate_capital_at_risk`'s EQ branch returns full notional regardless of
direction. A short equity position posts roughly 20% margin and has unbounded
loss, so `notional` is neither its capital at risk nor its margin. Classified
**GAP**, not FIX NOW — deciding the right denominator for short equity is the
same product question as MTF and real broker margin (D7/D8).

---

## 2. NEW FINDING — the parser cannot read a class of real NSE stock options

**FIX NOW. Found by measuring the impact register against the real book rather
than reasoning about it.**

`_RE_MONTHLY_OPT` (`services/instrument_parser.py:46`):

```python
r"^([A-Z&]+)(\d{2})(JAN|FEB|…|DEC)(\d{3,6})(CE|PE)$"
```

Three defects, each excluding real symbols:

| defect | excludes | count in the book |
|---|---|---|
| `(\d{3,6})` requires ≥3 digits | 2-digit strikes — `NMDC25APR74CE`, `YESBANK25APR18CE`, `SUZLON25NOV56CE` | **10 symbols** |
| no decimal allowed | `ASHOKLEY25AUG122.5CE`, `NYKAA25JUL207.5CE` | **4 symbols** |
| `[A-Z&]+` excludes `-` | `BAJAJ-AUTO25AUG8500CE` | **3 symbols** |

### Measured impact on the 189-session reference book

```
affected symbols : 17 of 722   (2.4%)
affected fills   : 38 of 2,175 (1.7%)
underlyings      : ABFRL ASHOKLEY BAJAJ-AUTO GMRAIRPORT IREDA NHPC
                   NMDC NYKAA SJVN SUZLON TATASTEEL YESBANK
```

**Before F9 these fell through to the equity branch**, so a real stock option
was carried as `instrument_type="EQ"`, `underlying=<the entire symbol>`,
`strike=None`, `expiry_key=""`. Consequences on the actual book:

- `premium_loss_event` and `options_premium_avg_down` **skipped them** — they
  guard `instrument_type in ("CE","PE")`
- `excess_exposure` used **full equity notional** rather than premium paid
- `same_symbol_obsession` could never group two of them — the underlying was the
  whole symbol, so every contract was its own underlying
- strategy grouping never saw them as option legs

**After F9 they are `UNKNOWN` and detectors abstain**, which is safer but is not
the fix. The regex is the defect.

**This changes the honest reading of F9.** I recorded F9 as having no impact on
the reference book. That was wrong — measured, it moves 38 fills from a wrong
equity classification to abstention. The impact register caught it.

---

## 3. What the engine currently cannot know reliably

Deliverable 6. Each of these must abstain, not infer.

| unknown | why | current behaviour |
|---|---|---|
| whether a resting stop-loss existed | see §4 | **infers it from the exit fill** |
| true broker margin per position | `margin_service` fetches Kite `span`/`exposure`/`option_premium`; **no detector consumes it** | uses self-reported `trading_capital` |
| MTF leverage / financing | no model exists; `estimate_capital_at_risk` has no `product` parameter | MTF charged as cash equity |
| order intent (placed → modified → cancelled) | `orders` table populated only on manual/EOD sync, read by one REST endpoint | invisible; only fills exist |
| target vs discretionary limit exit | `order_type` unreadable on the live path (F1) | cannot distinguish |
| cross-underlying hedge relationships | no correlation, beta, sector or index-constituent data anywhere | correctly not claimed |
| sector / correlated exposure | no sector taxonomy | correctly not claimed |
| equity holdings being hedged | holdings sync is explicitly skipped (`api/zerodha.py:860`) | invisible |
| automated vs manual trading | Kite exposes no such field | not claimed |
| whether two legs were held simultaneously | grouping matches on entry time ±15 min, never on overlap | assumes, does not verify |
| BSE index monthly expiry date | NSE's last-Thursday rule does not apply; no sourced BSE rule available | **abstains since F11** |
| strike of an unparseable option | §2 | **abstains since F9** |

---

## 4. Pattern 12 (`no_stoploss`) — observability verdict

**Deliverable 8. Verdict: the current claim is UNSUPPORTED. Do not implement.**

### Does Kite provide reliable resting stop-loss data?

**Yes.** `get_orders()` returns the full day order book including cancelled and
rejected orders, and our `Order` model already stores everything needed
(`models/order.py`): `order_type` (`MARKET`/`LIMIT`/`SL`/`SL-M`),
`trigger_price`, `status` (`OPEN`/`COMPLETE`/`CANCELLED`/`REJECTED`),
`pending_quantity`, `variety` (including cover orders).

**The data exists and the schema can hold it. The pipeline is where it is lost.**

### Does our ingestion preserve it?

| path | behaviour |
|---|---|
| `sync_orders_to_db` | syncs **all** orders including cancelled/rejected — **no status filter**. Correct. |
| but it is called from | **only two manual endpoints** (`api/zerodha.py:792`, `:857`). Explicitly removed from the routine sync — `trade_sync_service.py:389`: *"Orders sync removed"* |
| `order_stream_service` (real time) | `_FILL_STATUS = "COMPLETE"` — every intermediate status, including `TRIGGER PENDING`, is dropped |
| who reads the `orders` table | `order_analytics_service` only, backing one REST endpoint. **No detector.** |

**One more limit:** Kite's order book is same-day. A resting stop from a previous
session cannot be backfilled at all.

### What the detector actually claims vs what it can support

`no_stoploss` says *"No stop-loss order detected on this trade."* It derives that
from `ctx.exit_order_types` — the order type of the **exit fill** — via
`exit_trade_ids`, which is **structurally broken on the live path (F1)** and so
is always empty.

Even with F1 fixed, the exit fill's order type answers a **different question**:

| question | answerable? |
|---|---|
| "was this exit executed by a stop order?" | **yes**, once F1 is fixed — a fact about the fill |
| "did the trader have a resting stop-loss?" | **no** — requires the order book, which no detector reads |
| "did the trader ignore their stop-loss?" | **no** — requires the resting order *and* its trigger price |

A trader with a resting SL who exits manually first shows an exit type of `MKT`
and is flagged as having had no stop. That is the inverse of the truth.

### Verdict

**UNSUPPORTED as currently claimed.** The detector infers a behavioural fact
("you had no stop-loss") from price, duration and an exit-fill attribute that is
both unreliable and answers a different question.

Two coherent futures, neither of which is implementation work today:

1. **MODIFY to a fact** — after F1, claim only *"this exit was not a stop-loss
   execution"*, which is measurable and true. Loses the behavioural claim.
2. **RESEARCH FURTHER** — make the resting order book available to detectors
   (route `sync_orders_to_db` into the live path, have a detector read it). Then
   *"you had a stop at X and exited at Y instead"* becomes evidenced.

**Both require F1 first.** F1 is the prerequisite for even the narrow factual
version.

**A position losing 50% is a measurable fact. "The trader ignored their
stop-loss" is a behavioural claim, and the data as wired does not support it.**
