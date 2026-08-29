"""
Instrument master — resolve a contract specification as of a trade date.

    THIS MODULE IS NOT WIRED TO ANY DETECTOR.

Two backends, tried in order, with a hard rule between them:

    1. EXCHANGE-STATED  (NSE F&O bhavcopy, per date)   -> AUTHORITATIVE
    2. DERIVED          (parse the tradingsymbol)      -> DERIVED
    3. neither                                         -> UNAVAILABLE

Backend 1 is the only one valid for a historical trade, because it is the only
one that knows what the contract was ON THAT DAY. Backend 2 exists because the
live path genuinely has nothing else: an order postback carries a tradingsymbol
and no contract specification, so refusing to derive would make the engine
silent in real time. It is marked DERIVED so a caller can tell the difference.

There is no backend that fabricates. A missing lot size is never 1, a missing
segment is never equity, a missing expiry is never today.

WHY NOT KITE'S INSTRUMENTS DUMP
-------------------------------
Verified against the Kite Connect docs: the dump is 12 columns, currently-active
contracts only, regenerated daily, with no effective dating and no contract
multiplier. Kite's own documentation warns that exchanges reuse
`instrument_token` after expiry. It is a fine source for what is tradable today
and unusable as a historical master.
"""
from __future__ import annotations

import csv
import io
import logging
import zipfile
from bisect import bisect_right
from datetime import date
from typing import Iterable, Optional

from app.core.contract_spec import (
    FIN_INSTRM_TP, ContractSpec, Reliability, Segment, SpecSource,
)
from app.core.exchange_support import Support, support_for

logger = logging.getLogger(__name__)

BHAVCOPY_URL = ("https://nsearchives.nseindia.com/content/fo/"
                "BhavCopy_NSE_FO_0_0_0_{day:%Y%m%d}_F_0000.csv.zip")


# ---------------------------------------------------------------------------
# Store — append-only, effective-dated
# ---------------------------------------------------------------------------

class InstrumentMaster:
    """
    An append-only, effective-dated set of contract specifications.

    Keyed on `(exchange, tradingsymbol)` because Kite documents that
    `instrument_token` is reused across expiries. Each key holds its records
    sorted by effective date, and resolution takes the latest record AT OR
    BEFORE the requested date — never a later one, so a lot-size revision
    cannot reach backwards into a closed trade.

    Records are immutable once added. `add` refuses to overwrite an existing
    `(key, effective_date)` with different content rather than silently
    replacing it, because a silent replacement is how history stops being
    history.
    """

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], list[ContractSpec]] = {}

    def add(self, spec: ContractSpec) -> None:
        key = (spec.exchange.upper(), spec.tradingsymbol.upper())
        bucket = self._by_key.setdefault(key, [])
        for i, existing in enumerate(bucket):
            if existing.effective_date == spec.effective_date:
                if existing != spec:
                    raise ValueError(
                        f"immutability violated: {key} on {spec.effective_date} "
                        f"already recorded with different content. A revision "
                        f"must be a NEW effective date, not a rewrite.")
                return
            if existing.effective_date > spec.effective_date:
                bucket.insert(i, spec)
                return
        bucket.append(spec)

    def add_all(self, specs: Iterable[ContractSpec]) -> int:
        n = 0
        for s in specs:
            self.add(s)
            n += 1
        return n

    def __len__(self) -> int:
        return sum(len(v) for v in self._by_key.values())

    def as_of(self, tradingsymbol: str, exchange: str,
              on: date) -> Optional[ContractSpec]:
        """The record in force on `on`, or None. Never a later record."""
        bucket = self._by_key.get((exchange.upper(), tradingsymbol.upper()))
        if not bucket:
            return None
        dates = [s.effective_date for s in bucket]
        i = bisect_right(dates, on)
        return bucket[i - 1] if i else None


# ---------------------------------------------------------------------------
# Backend 1 — the exchange states it
# ---------------------------------------------------------------------------

def specs_from_bhavcopy(raw_zip: bytes, exchange: str = "NFO") -> list[ContractSpec]:
    """
    Turn one day's NSE F&O bhavcopy into contract specifications.

    Every field below is READ, not derived. That is the entire point: it
    removes the instrument-type guess (F9/F16), the strike and underlying parse
    (F15), and the expiry weekday rule (F11) in a single step, for all
    historical data.
    """
    z = zipfile.ZipFile(io.BytesIO(raw_zip))
    rows = csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0])))
    out: list[ContractSpec] = []

    for r in rows:
        segment = FIN_INSTRM_TP.get((r.get("FinInstrmTp") or "").strip())
        if segment is None:
            continue                       # not an F&O contract row
        try:
            trad = _as_date(r["TradDt"])
            expiry = _as_date(r["XpryDt"])
        except (KeyError, ValueError):
            continue
        symbol = (r.get("FinInstrmNm") or "").strip()
        if not symbol:
            continue

        out.append(ContractSpec(
            tradingsymbol=symbol,
            exchange=exchange,
            effective_date=trad,
            segment=segment,
            underlying=(r.get("TckrSymb") or "").strip() or None,
            expiry=expiry,
            strike=_as_float(r.get("StrkPric")),
            option_type=(r.get("OptnTp") or "").strip() or None,
            lot_size=_as_int(r.get("NewBrdLotQty")),
            contract_multiplier=None,      # not applicable on NFO
            source=SpecSource.EXCHANGE,
            reliability=Reliability.AUTHORITATIVE,
        ))
    return out


def _as_date(v: str) -> date:
    y, m, d = (v or "").strip()[:10].split("-")
    return date(int(y), int(m), int(d))


def _as_float(v: Optional[str]) -> Optional[float]:
    try:
        f = float((v or "").strip())
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def _as_int(v: Optional[str]) -> Optional[int]:
    try:
        n = int(float((v or "").strip()))
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


# ---------------------------------------------------------------------------
# Backend 2 — derive from the symbol, for the live path only
# ---------------------------------------------------------------------------

_DERIVED_SEGMENT = {
    ("CE", True): Segment.INDEX_OPTION, ("CE", False): Segment.STOCK_OPTION,
    ("PE", True): Segment.INDEX_OPTION, ("PE", False): Segment.STOCK_OPTION,
    ("FUT", True): Segment.INDEX_FUTURE, ("FUT", False): Segment.STOCK_FUTURE,
}

#: Underlyings that are indices. Used ONLY to pick index-vs-stock on the derived
#: path; the exchange-stated path never needs it.
_INDEX_UNDERLYINGS = frozenset({
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50",
    "SENSEX", "BANKEX", "SENSEX50",
})


def derive_spec(tradingsymbol: str, exchange: str, on: date) -> ContractSpec:
    """
    Best effort from the tradingsymbol alone. Marked DERIVED, never
    AUTHORITATIVE, and it does not invent a lot size.
    """
    from app.services.instrument_parser import parse_symbol

    p = parse_symbol(tradingsymbol or "")
    itype = p.instrument_type

    if itype is None:
        # F9/F16: an unreadable derivative is UNKNOWN. It is not equity.
        return ContractSpec.unavailable(
            tradingsymbol, exchange, on,
            "the tradingsymbol could not be read as a derivative, and it is "
            "not an equity ticker either")

    if itype == "EQ":
        return ContractSpec(
            tradingsymbol=tradingsymbol, exchange=exchange, effective_date=on,
            segment=Segment.EQUITY, underlying=p.underlying,
            source=SpecSource.DERIVED, reliability=Reliability.DERIVED)

    is_index = (p.underlying or "").upper() in _INDEX_UNDERLYINGS
    return ContractSpec(
        tradingsymbol=tradingsymbol, exchange=exchange, effective_date=on,
        segment=_DERIVED_SEGMENT[(itype, is_index)],
        underlying=p.underlying,
        expiry=None,          # a MONTH is known, a DATE is not. Never guess it.
        strike=p.strike,
        option_type=itype if itype in ("CE", "PE") else None,
        lot_size=None,        # not derivable from a symbol
        source=SpecSource.DERIVED, reliability=Reliability.DERIVED,
        note="derived from the tradingsymbol; expiry date and lot size unknown",
    )


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def resolve(tradingsymbol: str, exchange: str, on: date,
            master: Optional[InstrumentMaster] = None,
            allow_derived: bool = True) -> ContractSpec:
    """
    The one entry point. `on` is required — there is no signature that lets a
    caller accidentally value a 2025 trade with a 2026 contract.

    `allow_derived=False` for historical work, where a derived answer would be
    a quiet downgrade from a fact to a guess.
    """
    support = support_for(exchange)
    if support.support is Support.UNSUPPORTED:
        return ContractSpec.unavailable(
            tradingsymbol, exchange, on,
            support.unknown[0] if support.unknown else support.note)

    if master is not None:
        stated = master.as_of(tradingsymbol, exchange, on)
        if stated is not None:
            return stated

    if not allow_derived:
        return ContractSpec.unavailable(
            tradingsymbol, exchange, on,
            "no exchange-stated specification for this contract on this date, "
            "and derivation is disabled for historical resolution")

    return derive_spec(tradingsymbol, exchange, on)
