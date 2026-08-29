"""
Validate `app.core.margin_model` against real broker margins.

NOT A PYTEST. It reaches the public internet, so it must never run in CI or
gate a commit. Run it by hand when the model changes:

    python backend/tests/margin/validate_against_broker.py

ORACLE
------
Zerodha's public SPAN calculator (https://zerodha.com/margin-calculator/SPAN/)
returns the broker's own span / exposure / netoptionvalue / spread / total for
an arbitrary position, without authentication. It is the same number a Kite
user is charged, so it is a true oracle rather than a second estimate.

We use it instead of Kite `/margins/orders` only because that needs a live
access token; the two answer the same question. Keep the request count modest —
this is somebody else's public endpoint, not an API we are entitled to hammer.

INPUTS
------
Public NSE files, no login:
    bhavcopy  https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_<YYYYMMDD>_F_0000.csv.zip
    FOVOLT    https://nsearchives.nseindia.com/archives/nsccl/volt/FOVOLT_<DDMMYYYY>.csv

A caveat that limits how far the error figures can be pushed: the oracle prices
from a live intraday snapshot, while the bhavcopy gives a settlement close. The
two underlying references differ by a few tenths of a percent on a quiet day,
and that difference passes straight into the result. Residuals below roughly 1%
are therefore at the noise floor of this comparison and should not be read as
model accuracy.
"""
from __future__ import annotations

import csv
import io
import os
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.margin_model import Leg, Segment, compute_margin  # noqa: E402

TRADE_DATE = date(2026, 8, 28)
CACHE = Path(os.environ.get("CLAUDE_JOB_DIR", "/tmp")) / "tmp"
UA = {"User-Agent": "Mozilla/5.0"}
ORACLE = "https://zerodha.com/margin-calculator/SPAN"

#: Zerodha scrip suffix -> the expiry it actually denotes. Established by
#: matching against the expiry list in the bhavcopy, not assumed: NIFTY's
#: monthly expiry is a TUESDAY here, not the Thursday that older code and docs
#: still hardcode.
EXPIRY_OF = {"26SEP": "2026-09-29", "26OCT": "2026-10-27", "26NOV": "2026-11-23"}


# --------------------------------------------------------------------------- data

def _get(url: str) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / urllib.parse.quote(url, safe="")
    if cached.exists():
        return cached.read_bytes()
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        body = r.read()
    cached.write_bytes(body)
    return body


def load_bhavcopy(day: date) -> list[dict]:
    url = ("https://nsearchives.nseindia.com/content/fo/"
           f"BhavCopy_NSE_FO_0_0_0_{day:%Y%m%d}_F_0000.csv.zip")
    z = zipfile.ZipFile(io.BytesIO(_get(url)))
    return list(csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0]))))


def load_volatility(day: date) -> dict[str, float]:
    url = f"https://nsearchives.nseindia.com/archives/nsccl/volt/FOVOLT_{day:%d%m%Y}.csv"
    text = _get(url).decode("utf-8", "replace")
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        clean = {k.strip(): (v or "").strip() for k, v in row.items()}
        try:
            out[clean["Symbol"]] = float(
                clean["Applicable Annualised Volatility (N) = Max (F or L)"])
        except (KeyError, ValueError):
            continue
    return out


def ask_broker(legs: list[dict]) -> dict | None:
    """One call to the oracle. `legs` are already in its parameter vocabulary."""
    parts = ["action=calculate"]
    for leg in legs:
        parts += [
            f"exchange[]={leg['exchange']}", f"product[]={leg['product']}",
            f"scrip[]={leg['scrip']}", f"option_type[]={leg.get('option_type', 'CE')}",
            f"strike_price[]={leg.get('strike', '')}",
            f"qty[]={leg['qty']}", f"trade[]={leg['trade']}",
        ]
    body = "&".join(parts).encode()
    req = urllib.request.Request(
        ORACLE, data=body,
        headers={**UA, "Content-Type": "application/x-www-form-urlencoded",
                 "X-Requested-With": "XMLHttpRequest"})
    import json
    # The oracle intermittently returns an all-zero block for a valid
    # multi-leg position. Zerodha's own JS treats a response without a
    # "total" as an invalid entry and warns that leaving it in place makes
    # the upstream API "reject all subsequent calls", so this is a known
    # failure mode of the endpoint rather than a property of the position.
    # An unhedged short with span == 0 is not a real answer; retry it.
    for attempt in range(3):
        with urllib.request.urlopen(req, timeout=60) as r:
            payload = json.loads(r.read().decode())
        total = payload.get("total")
        if total and float(total.get("total") or 0) > 0 and float(total.get("span") or 0) > 0:
            return total
        time.sleep(1.2)
    return total or None


# --------------------------------------------------------------------------- cases

def build_cases(rows, vols):
    """
    The grid the brief asks for: every moneyness, both option types, both
    directions, futures both ways, three expiries, two lot sizes, and spreads.
    """
    by_key = {}
    for r in rows:
        key = (r["TckrSymb"], r["XpryDt"], r["OptnTp"], r["StrkPric"])
        by_key[key] = r

    def opt(sym, exp, typ, strike):
        return by_key.get((sym, EXPIRY_OF[exp], typ, f"{strike:.2f}"))

    def fut(sym, exp):
        for r in rows:
            if (r["TckrSymb"] == sym and r["XpryDt"] == EXPIRY_OF[exp]
                    and r["FinInstrmTp"] in ("IDF", "STF")):
                return r
        return None

    # Underlying reference per (symbol, expiry) = that expiry's FUTURES price.
    # Each expiry has its own forward; see compute_margin's docstring.
    fut_px = {}
    for r in rows:
        if r["FinInstrmTp"] in ("IDF", "STF"):
            fut_px[(r["TckrSymb"], r["XpryDt"])] = float(r["SttlmPric"])

    def ref(sym, exp):
        return fut_px[(sym, EXPIRY_OF[exp])]

    nifty_spot = float(next(r["UndrlygPric"] for r in rows if r["TckrSymb"] == "NIFTY"))
    rel_spot = float(next(r["UndrlygPric"] for r in rows if r["TckrSymb"] == "RELIANCE"))
    cases = []

    # NIFTY options: strike ladder around spot, both types, both directions
    atm = round(nifty_spot / 50) * 50
    ladder = [("deep ITM", atm - 1200), ("ITM", atm - 500), ("ATM", atm),
              ("OTM", atm + 500), ("deep OTM", atm + 1500)]
    for label, strike in ladder:
        for typ in ("CE", "PE"):
            for trade in ("sell", "buy"):
                row = opt("NIFTY", "26SEP", typ, float(strike))
                if row:
                    cases.append(dict(
                        name=f"NIFTY 26SEP {int(strike)}{typ} {trade} ({label})",
                        segment=Segment.INDEX, sym="NIFTY", spot=ref("NIFTY", "26SEP"),
                        legs=[(row, 65 if trade == "buy" else -65)],
                        broker=[dict(exchange="NFO", product="OPT", scrip="NIFTY26SEP",
                                     option_type=typ, strike=int(strike),
                                     qty=65, trade=trade)]))

    # expiry sweep, same contract
    for exp in ("26SEP", "26OCT", "26NOV"):
        row = opt("NIFTY", exp, "CE", float(atm))
        if row:
            cases.append(dict(
                name=f"NIFTY {exp} {int(atm)}CE sell (expiry sweep)",
                segment=Segment.INDEX, sym="NIFTY", spot=ref("NIFTY", exp),
                legs=[(row, -65)],
                broker=[dict(exchange="NFO", product="OPT", scrip=f"NIFTY{exp}",
                             option_type="CE", strike=int(atm), qty=65, trade="sell")]))

    # futures, both directions, index and stock
    for sym, scrip, qty, spot, seg in (("NIFTY", "NIFTY26SEP", 65, ref("NIFTY", "26SEP"), Segment.INDEX),
                                       ("RELIANCE", "RELIANCE26SEP", 500, ref("RELIANCE", "26SEP"), Segment.STOCK)):
        row = fut(sym, "26SEP")
        if row:
            for trade, signed in (("buy", qty), ("sell", -qty)):
                cases.append(dict(
                    name=f"{sym} 26SEP FUT {trade}", segment=seg, sym=sym, spot=spot,
                    legs=[(row, signed)],
                    broker=[dict(exchange="NFO", product="FUT", scrip=scrip,
                                 option_type="CE", strike="", qty=qty, trade=trade)]))

    # stock options — different lot size, different segment parameters
    rel_atm = round(rel_spot / 20) * 20
    for typ in ("CE", "PE"):
        row = opt("RELIANCE", "26SEP", typ, float(rel_atm))
        if row:
            cases.append(dict(
                name=f"RELIANCE 26SEP {int(rel_atm)}{typ} sell (stock, lot 500)",
                segment=Segment.STOCK, sym="RELIANCE", spot=ref("RELIANCE", "26SEP"),
                legs=[(row, -500)],
                broker=[dict(exchange="NFO", product="OPT", scrip="RELIANCE26SEP",
                             option_type=typ, strike=int(rel_atm), qty=500,
                             trade="sell")]))

    # hedged structures — the cases a per-leg model gets badly wrong
    def two_leg(name, a, b):
        ra, rb = opt("NIFTY", "26SEP", a[0], float(a[1])), opt("NIFTY", "26SEP", b[0], float(b[1]))
        if not (ra and rb):
            return
        cases.append(dict(
            name=name, segment=Segment.INDEX, sym="NIFTY", spot=ref("NIFTY", "26SEP"),
            legs=[(ra, a[2]), (rb, b[2])],
            broker=[dict(exchange="NFO", product="OPT", scrip="NIFTY26SEP",
                         option_type=a[0], strike=int(a[1]), qty=65,
                         trade="sell" if a[2] < 0 else "buy"),
                    dict(exchange="NFO", product="OPT", scrip="NIFTY26SEP",
                         option_type=b[0], strike=int(b[1]), qty=65,
                         trade="sell" if b[2] < 0 else "buy")]))

    two_leg("bull call spread (sell ATM CE / buy OTM CE)", ("CE", atm, -65), ("CE", atm + 500, 65))
    two_leg("bear put spread (sell ATM PE / buy OTM PE)", ("PE", atm, -65), ("PE", atm - 500, 65))
    two_leg("short straddle (sell ATM CE + ATM PE)", ("CE", atm, -65), ("PE", atm, -65))
    two_leg("short strangle (sell OTM CE + OTM PE)", ("CE", atm + 500, -65), ("PE", atm - 500, -65))
    two_leg("long straddle (buy ATM CE + ATM PE)", ("CE", atm, 65), ("PE", atm, 65))
    two_leg("ratio spread (sell 2 OTM CE / buy 1 ATM CE)", ("CE", atm + 500, -130), ("CE", atm, 65))
    return cases


# --------------------------------------------------------------------------- run

def main():
    rows = load_bhavcopy(TRADE_DATE)
    vols = load_volatility(TRADE_DATE)
    cases = build_cases(rows, vols)

    print(f"# Margin validation — {TRADE_DATE}, {len(cases)} cases\n")
    header = ("| case | qty | broker span | broker total | computed span | "
              "computed total | abs err | % err |")
    print(header)
    print("|---|---|---|---|---|---|---|---|")

    errors, failures, zero_cases = [], [], []
    for case in cases:
        try:
            broker = ask_broker(case["broker"])
        except Exception as exc:                       # noqa: BLE001
            failures.append((case["name"], f"oracle error: {exc}"))
            continue
        time.sleep(0.4)                                # be a good citizen
        if not broker:
            failures.append((case["name"], "oracle rejected the contract"))
            continue

        legs = []
        for row, signed_qty in case["legs"]:
            y, m, d = map(int, row["XpryDt"][:10].split("-"))
            legs.append(Leg(
                kind="FUT" if row["FinInstrmTp"] in ("IDF", "STF") else "OPT",
                qty=signed_qty, price=float(row["SttlmPric"]),
                expiry_days=max((date(y, m, d) - TRADE_DATE).days, 0),
                option_type=row["OptnTp"] or None,
                strike=float(row["StrkPric"]) if row["StrkPric"] else None,
                lot_size=int(row["NewBrdLotQty"]),
            ))

        got = compute_margin(legs, underlying=case["spot"],
                             annualised_vol=vols[case["sym"]],
                             segment=case["segment"])
        bt, ct = float(broker["total"]), got.total
        err = ct - bt
        if bt == 0:
            # Long-only positions: the broker blocks nothing. A percentage is
            # undefined, so these are scored exactly rather than averaged in.
            zero_cases.append((case["name"], ct))
            pct = float("nan")
        else:
            pct = err / bt * 100.0
            errors.append((case["name"], pct, err, bt, ct))
        qty = sum(abs(q) for _, q in case["legs"])
        print(f"| {case['name']} | {qty} | {float(broker['span']):,.0f} | {bt:,.0f} "
              f"| {got.span:,.0f} | {ct:,.0f} | {err:+,.0f} | {pct:+.1f}% |")

    print()
    if zero_cases:
        exact = sum(1 for _, ct in zero_cases if abs(ct) < 1e-6)
        print(f"zero-margin cases   : {exact}/{len(zero_cases)} computed exactly 0"
              + ("" if exact == len(zero_cases) else "  <-- MISMATCH"))
        for name, ct in zero_cases:
            if abs(ct) >= 1e-6:
                print(f"    broker 0, computed {ct:,.0f}   {name}")
    if errors:
        pcts = sorted(abs(e[1]) for e in errors)
        n = len(pcts)
        print(f"cases compared      : {n}")
        print(f"median |error|      : {pcts[n // 2]:.1f}%")
        print(f"90th pct |error|    : {pcts[int(n * 0.9)]:.1f}%")
        print(f"max |error|         : {pcts[-1]:.1f}%")
        print(f"within 5%           : {sum(1 for p in pcts if p <= 5)}/{n}")
        print(f"within 15%          : {sum(1 for p in pcts if p <= 15)}/{n}")
        print("\nworst cases:")
        for name, pct, err, bt, ct in sorted(errors, key=lambda e: -abs(e[1]))[:8]:
            print(f"  {pct:+8.1f}%  broker {bt:>12,.0f}  computed {ct:>12,.0f}   {name}")
    for name, why in failures:
        print(f"FAILED: {name} — {why}")


if __name__ == "__main__":
    main()
