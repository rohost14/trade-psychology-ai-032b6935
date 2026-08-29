# Instrument Master — Specification

**29 Aug 2026. Deliverable 3. Design only; nothing implemented.**

The engine currently derives contract facts by parsing tradingsymbols and by
consulting hardcoded tables. Both are wrong in ways that have already been
measured. This specifies what an authoritative instrument master must hold.

---

## 1. Why the current approach fails — measured, not asserted

| assumption in the code today | reality | evidence |
|---|---|---|
| "NIFTY expires on the last Thursday" (`instrument_parser.py:176`) | NIFTY's 2026 monthly expiries are **2026-09-29, 10-27, 11-23 — Tuesdays** | bhavcopy `XpryDt`, VERIFIED |
| every exchange shares NSE's weekday rule | BSE differs; **no sourced BSE rule was found**, which is why F11 made it abstain | semantics audit |
| a tradingsymbol can be parsed into underlying/strike/type | **17 symbols / 38 fills** of the real book cannot be parsed — 2-digit strikes, decimal strikes, hyphenated underlyings | F15, measured |
| MCX `lot_size = 1` means one unit | Kite reports 1 for every MCX instrument; the contract is a **lot** | `mcx_contract_specs.py` |
| a symbol's lot size is a constant | lot sizes change; NIFTY has been 75 and is **65** in this data | bhavcopy `NewBrdLotQty` |

**The root defect is architectural, not a set of bugs: contract facts are being
*derived* when they are *published*.**

---

## 2. Authoritative fields

| field | authority | notes |
|---|---|---|
| `exchange` | Kite instruments / bhavcopy | NSE, NFO, BSE, BFO, CDS, MCX |
| `segment` | Kite instruments | |
| `tradingsymbol` | both | the join key — Kite warns `instrument_token` is **reused after expiry** |
| `instrument_type` | **bhavcopy `FinInstrmTp`** | IDF/IDO/STF/STO. Exchange-stated, no parsing |
| `underlying` | bhavcopy `TckrSymb` | exchange-stated |
| `expiry` | bhavcopy `XpryDt` + `FininstrmActlXpryDt` | **read, never compute** |
| `strike` | bhavcopy `StrkPric` | decimals occur (`ASHOKLEY25AUG122.5CE`) |
| `option_type` | bhavcopy `OptnTp` | |
| **`lot_size`** | **bhavcopy `NewBrdLotQty`, per date** | the historically-correct value |
| `tick_size` | Kite instruments | not in bhavcopy |
| `contract_multiplier` | **NEITHER** | see §5 — this is the open gap |
| `expiry_type` | derived from the expiry set | weekly/monthly; index has weeklies, stock does not |

**Kite's instruments dump is currently-active only, regenerated daily, with no
effective dating and no multiplier column** (12 columns, VERIFIED against the
Kite Connect docs). It is therefore usable as a *today* master and **unusable as
a historical one**.

**The bhavcopy is the historical master.** It is published per date, archived for
years, and states everything except tick size and multiplier.

---

## 3. Effective dating — the non-negotiable rule

> A historical trade must be valued with the contract specification in force on
> its own trade date, never with today's.

Storage shape: one row per `(exchange, tradingsymbol, effective_date)`, with the
resolver taking the latest row **at or before** the trade date. Rows are
**immutable once written**. A later change to a lot size creates a new row; it
must never rewrite an old one, and it must never trigger recomputation of a
closed trade.

Concretely: if NIFTY's lot moves from 65 to 75 next month, every 2026-08-28
position stays at 65 forever. This is the difference between a P&L that is stable
and one that silently changes when a contract is revised.

---

## 4. Refresh mechanism — designed, not implemented

| aspect | design |
|---|---|
| source | bhavcopy (historical + daily), Kite instruments (today's tradables, tick size) |
| frequency | once per trading day after settlement |
| effective date | the bhavcopy's own `TradDt` — never ingestion time |
| version | monotonic per `(exchange, tradingsymbol)` |
| validation | reject a batch where a lot size changes by more than a set factor, or where contract count moves sharply, without an explicit acknowledgement |
| change detection | diff each batch against the previous; **surface** lot-size, expiry and specification changes rather than absorbing them |
| failure handling | a missing day is a **gap**, not a zero. Resolution falls back to the last effective row and the record is marked stale |
| holidays | a 404 for a non-trading day is expected — distinguish it from an outage before alerting |
| immutability | append-only; a correction is a new row with a reason |
| last successful refresh | stored and exposed, so staleness is observable rather than assumed |

---

## 5. MCX — do not assume quantity semantics. **UNRESOLVED.**

Current state, VERIFIED by reading `app/services/mcx_contract_specs.py`:

- multipliers are **hardcoded** for a fixed list of prefixes
- sourced from **Zerodha Z-Connect, a third-party lot-size chart dated 2024, and
  mcxindia.com/products** — the file says so honestly in its own docstring
- unknown contracts return `None`, and `risk_basis` marks the result UNRELIABLE
  rather than guessing, which is the correct failure

What is **not** established and must be before MCX is supported:

1. What MCX's own contract specification says for lot size, quantity unit, price
   quotation unit and tick value — **from mcxindia.com directly**, not a chart.
2. Whether Kite's `quantity` for an MCX fill is lots or units, confirmed against
   a real fill rather than a forum post.
3. Whether `lot_size = 1` in Kite's dump is a data gap or a deliberate encoding.
4. How multiplier revisions are dated (COPPER changed from 1 MT to 2500 kg in
   2022 — under §3 that is a new effective-dated row, and pre-2022 trades keep
   the old value).

**Until 1-4 are answered from primary sources, MCX stays UNRELIABLE.** The
present behaviour — abstain on unknown contracts — is right and should not be
loosened to make coverage look better.

---

## 6. Consequences for the semantics audit findings

| finding | effect of an instrument master |
|---|---|
| **F15** — parser cannot read 17 real symbols | **dissolves** for historical NSE data. `FinInstrmTp`, `TckrSymb`, `StrkPric`, `OptnTp` are stated by the exchange, so nothing is parsed. The regex fix is still needed for the **live** path, where only a tradingsymbol arrives |
| **F11** — monthly expiry hardcoded to Thursday | **dissolves.** `XpryDt` is read |
| **F9 / F16** — unparseable derivative falls back to `EQ` | **dissolves** historically; still live on the real-time path |
| **F7** — contract multiplier missing from denominators | **does not dissolve.** Neither Kite nor the bhavcopy publishes a multiplier. §5 is the only route |

**This reorders the semantics work.** Three of the four parsing defects are
symptoms of deriving what is published. Fixing the regex is still correct for the
live path, but it is no longer the foundation.

---

## 7. What this spec does NOT decide

- whether to store the full instrument universe or only traded contracts
- backfill depth (the archive goes back years; the reference book needs ~2 years)
- where it lives — table shape is out of scope until the layer is approved
- BSE/BFO field mapping, which has not been examined at all
