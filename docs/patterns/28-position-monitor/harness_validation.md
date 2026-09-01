# Open-book harness — validation record

**1 Sep 2026. Harness only. No pattern reviewed, no production code changed.**

`docs/patterns/_measurement/p28_openbook.py`

The rule this exists to satisfy: **if the harness cannot reproduce production
open-position state from production fills, every number downstream is worthless.**

---

## Design — it does not reimplement the state machine

The harness calls `position_ledger_service._compute_fill_effect`, the **pure,
no-DB function production uses for every fill**. It is the same code path that
decides `OPEN` / `INCREASE` / `DECREASE` / `CLOSE` / `FLIP`, the running
quantity, and the weighted average entry price.

Everything the harness computes itself is a place it can silently disagree with
production, so it computes almost nothing: it maintains a dict keyed by
**(tradingsymbol, exchange, product)** — product is part of the key, because the
same symbol in MIS and NRML is two independent positions that must not net (M1)
— and tracks `round_started_at` and `last_entry_at` alongside.

---

## Three checks, because one could not tell a harness bug from a data defect

The first attempt reported 16 mismatches and looked like a broken harness. It was
not. Separating the questions is what made that visible.

### V0 — is production's own ledger self-consistent? *(no harness involved)*

A running total must satisfy `qty_after[i] == qty_after[i-1] + fill_qty[i]`.

| | |
|---|---|
| self-consistent symbols | **34** |
| NOT self-consistent | **1** — `SRF26JUN2900CE/NRML` |

**`SRF26JUN2900CE` is impossible, not merely mis-ordered.** Four fills share one
timestamp, every one `fill_qty = -200`, and their stored `position_qty_after`
values are `[200, 200, 200, 400]`. Four equal decrements from any starting
quantity must give four *distinct* running totals. **No ordering of these rows
produces what production stored.**

Its earlier `INCREASE` shows the same thing from the other side: two `OPEN`/
`INCREASE` fills of 200 each at one timestamp, then a 400-lot increase whose
stored result (`qty 600`, `avg 14.0000`) is what you get from a **base of 200 @
18.00** — production skipped one of the two fills when computing the next state.

> **This is a production data defect, not a harness defect.** Both affected
> timestamps have fills sharing `occurred_at` **and** `created_at` to the
> microsecond, so they were written by one batch whose internal ordering did not
> match the state it wrote. Recorded for the pending register; **not fixed
> here** — it is outside a pattern review, and one symbol of 35.

The symbol is **excluded from V1**: production offers no correct answer to match,
so it can neither validate nor invalidate a harness.

### V1 — does the harness reproduce production, fill by fill?

**93 fills replayed across the 34 self-consistent symbols.**

| field | mismatches |
|---|---|
| `entry_type` | **0** |
| `quantity` | **0** |
| `avg_entry_price` | **0** |
| `realized_pnl` | 2 — see below |

**The three fields every one of these detectors reads match production exactly.**
`overexposure` and `portfolio_concentration` read quantity and price;
`holding_loser` reads quantity, average entry and timing.

**`realized_pnl` is not one of them, and does not match exactly.** Two rows
differ — `MAXHEALTH26AUG1200CE` by ₹0.0525 and `SENSEX26JUL77000PE` by ₹0.0040.
Cause: a ledger row can aggregate several exchange fills, with P&L summed at the
true sub-fill prices while `fill_price` is stored as the rounded weighted
average, so no single-price recomputation reproduces it. **Stated rather than
tuned away.** It bounds what this harness may be used for: **not P&L analysis.**

### V2 — the reconstructed book vs the `positions` table

| | |
|---|---|
| `positions` rows | 99 |
| `status = 'open'` | **0** |
| with `instrument_token` | 99 |
| with `entry_price_source` | **0** |

The ledger leaves **7 positions open** at its end. The `positions` table shows
all 7 as `status='closed'`, `total_quantity=0`, `realized_pnl=0`, and
**`last_exit_time = NULL`** — three of them with `average_entry_price = 0` and no
`first_entry_time`. They are **empty shells, not closes.**

Six are `26JUN` options last entered 15–18 Jun; one is `26AUG`. **They were not
closed by a fill — they expired, or the broker snapshot simply stopped carrying
them.** No closing fill exists, so the ledger holds them open forever.

**Two consequences that must be carried into the review:**

1. **`positions` is a broker snapshot, not a durable record of open state.** It
   does not preserve an open position across days, and it zeroes rows without
   writing an exit. The ledger is the better source for reconstruction — but:
2. **The ledger never sees an expiry.** A position closed by expiry has no
   closing fill, so ledger-derived hold time is unbounded. This matters directly
   for `holding_loser`, whose whole subject is elapsed time on an open position.

---

## Scope limits — binding on every measurement made with this harness

1. **`FLIP` is never exercised.** Entry types in the ledger are `OPEN` 47,
   `CLOSE` 39, `INCREASE` 8, `DECREASE` 6. The flip path — a position crossing
   zero — is validated by **nothing**. Any finding that depends on it is
   unsupported.
2. **The validation set is small and narrow**: 100 fills, 35 symbols, **one
   account**, 15 Jun – 30 Jul 2026, and **zero open positions at any point we can
   observe**. It validates the *state machine*, not the *population*.
3. **Not usable for P&L.** See V1.
4. **Validated ≠ complete.** V1 proves the harness agrees with production on the
   fills production recorded. It cannot prove production recorded every fill.
5. **Measurement runs on the reference book, not on this ledger.** The ledger is
   the *validation* target because it is production's own output. The tradebook
   CSV (175 sessions / 740 rounds) is the *measurement* target because it is the
   only sample with enough positions to say anything. The harness is the bridge:
   validated against production, applied to the book.

---

## Verdict

> **V1 PASSED.** `entry_type`, `quantity` and `avg_entry_price` reproduce
> production **exactly** on all 93 replayed fills.
>
> **The harness may be used** for firing, false-positive and threshold analysis
> on `overexposure` and `portfolio_concentration`, **subject to the five limits
> above**, and it may **not** be used for P&L analysis or for any claim resting
> on `FLIP`.
>
> **`holding_loser` remains unmeasurable as specified** — it needs unrealized
> P&L at T+30/60/90 minutes and we store no intraday price path. The expiry gap
> found in V2 makes this worse, not better.

---

## Incidental findings — for the pending register, not fixed here

* **`SRF26JUN2900CE` ledger rows are internally impossible** (above). One symbol
  of 35; batch-write ordering did not match the state written.
* **`entry_price_source` is NULL on all 99 rows.** The column exists — so
  **migration 077 IS applied**, settling a status the trackers record as
  disputed — but nothing populates it.
* **`positions` rows are zeroed without an exit.** `status='closed'` with
  `last_exit_time = NULL` and `realized_pnl = 0` on positions that certainly had
  a P&L outcome.
