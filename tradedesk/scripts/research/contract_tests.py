"""
Synthetic validation of the adding_to_adverse_position contract.

NOT production code and not a detector. Two things run side by side:

  * a REFERENCE MEASUREMENT of the contract - the smallest thing that can walk a
    fill sequence and say REPORT / IGNORE / ABSTAIN. It exists to be tested, not
    to be shipped.
  * the REAL neighbouring detectors, on the equivalent CompletedTrade stream, so
    the boundary between them is measured rather than argued.

No threshold anywhere. The only decisions are the sign of the move, whether
exposure went up, and how many times it happened.
"""
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import List, Optional
from uuid import uuid4

sys.path.insert(0, r"D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.core.instrument_risk import risk_basis  # noqa: E402
from app.services.behavior_engine import BehaviorEngine, EngineContext  # noqa: E402

engine = BehaviorEngine()
T0 = datetime(2026, 8, 24, 4, 0, tzinfo=timezone.utc)


# ── the reference measurement ────────────────────────────────────────────

@dataclass
class Fill:
    qty: int          # signed: + buy, - sell
    price: float
    minute: int = 0


@dataclass
class Event:
    kind: str         # open | add | reduce | close | flip
    verdict: str      # REPORT | IGNORE | ABSTAIN | -
    adverse_pct: Optional[float] = None
    exposure_before: Optional[float] = None
    exposure_after: Optional[float] = None
    adverse_add_index: Optional[int] = None
    note: str = ""


@dataclass
class Walk:
    events: List[Event] = field(default_factory=list)

    @property
    def reported(self):
        return [e for e in self.events if e.verdict == "REPORT"]

    @property
    def abstained(self):
        return [e for e in self.events if e.verdict == "ABSTAIN"]


def walk(fills: List[Fill], instrument_type: str, symbol: str,
         is_spread: bool = False) -> Walk:
    """
    Walk one symbol's fills and classify every event.

    Direction is the sign of the open position, so a long filling lower and a
    short filling higher are the same event with the same number.
    """
    out = Walk()
    qty = 0
    avg = 0.0
    adverse_adds = 0

    for f in fills:
        if qty == 0:
            qty, avg = f.qty, f.price
            adverse_adds = 0
            out.events.append(Event("open", "-"))
            continue

        direction = "LONG" if qty > 0 else "SHORT"
        d = 1.0 if qty > 0 else -1.0
        same_way = (qty > 0) == (f.qty > 0)

        if not same_way:
            closing = min(abs(f.qty), abs(qty))
            new_qty = qty + f.qty
            if new_qty == 0:
                out.events.append(Event("close", "-"))
                qty, avg, adverse_adds = 0, 0.0, 0
            elif (new_qty > 0) != (qty > 0):
                out.events.append(Event("flip", "-", note="new position, counters reset"))
                qty, avg, adverse_adds = new_qty, f.price, 0
            else:
                out.events.append(Event("reduce", "-",
                                        note=f"partial exit of {closing}"))
                qty = new_qty
            continue

        # ── an ADD ───────────────────────────────────────────────────────
        adverse = (avg - f.price) / avg * 100.0 * d
        rb_before = risk_basis(instrument_type, symbol, direction, avg, abs(qty),
                               is_spread=is_spread)
        new_qty = qty + f.qty
        new_avg = (avg * abs(qty) + f.price * abs(f.qty)) / abs(new_qty)
        rb_after = risk_basis(instrument_type, symbol, direction, new_avg,
                              abs(new_qty), is_spread=is_spread)

        if not rb_before.is_comparable:
            verdict, idx = "ABSTAIN", None
            note = f"{rb_before.kind.value}: exposure not reliably determinable"
        elif adverse > 0:
            adverse_adds += 1
            verdict, idx, note = "REPORT", adverse_adds, ""
        elif adverse == 0:
            verdict, idx, note = "IGNORE", None, "break-even: no adverse move"
        else:
            verdict, idx, note = "IGNORE", None, "added after a favourable move"

        out.events.append(Event("add", verdict, round(adverse, 2),
                                round(rb_before.amount, 2),
                                round(rb_after.amount, 2), idx, note))
        qty, avg = new_qty, new_avg

    return out


# ── the real detectors, on the equivalent CompletedTrade stream ──────────

def ct(symbol, itype, direction, qty, entry, exit_px, minute, dur=10):
    pnl = (exit_px - entry) * qty * (1 if direction == "LONG" else -1)
    return SimpleNamespace(
        id=uuid4(), broker_account_id=None, tradingsymbol=symbol, exchange="NFO",
        product="MIS", instrument_type=itype, direction=direction,
        total_quantity=qty, avg_entry_price=Decimal(str(entry)),
        avg_exit_price=Decimal(str(exit_px)), realized_pnl=Decimal(str(pnl)),
        pnl_pct=None, duration_minutes=dur,
        entry_time=T0 + timedelta(minutes=minute),
        exit_time=T0 + timedelta(minutes=minute + dur),
        num_entries=1, num_exits=1, closed_by_flip=False, status="closed",
        quality_score=None,
    )


def run_real_detectors(trades):
    """What the existing detectors say about the LAST trade in the stream."""
    if not trades:
        return {}
    out = {}
    c = EngineContext(
        broker_account_id=uuid4(),
        session=SimpleNamespace(session_pnl=Decimal("0"),
                                session_date=T0.date(), market_open=None),
        completed_trade=trades[-1], session_trades=trades[:-1],
        active_cooldowns=[], thresholds={},
    )
    for name in ("martingale_behaviour", "size_escalation",
                 "options_premium_avg_down", "same_symbol_obsession"):
        try:
            ev = getattr(engine, f"_detect_{name}")(c)
        except Exception as e:
            ev = None
            out[name] = f"ERROR {e}"
            continue
        out[name] = ev.severity if ev else "-"
    return out
