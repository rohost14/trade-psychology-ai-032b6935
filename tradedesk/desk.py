"""
A manual trading desk driving the real behavioural engine.

The scenario suite proves the engine behaves correctly against situations I
wrote. That is worth something and it is not the same as you being able to check
it, because you did not choose the trades and cannot see why any particular
alert appeared. This is the answer to that: you place the orders, you set the
capital and the rules and the clock, and every alert comes from the same
production code the live system runs — never a copy, never a simplification.

Three properties it has to have to be worth trusting:

  **Its own account.** The scenario suite tears its account down before every
  scenario. Sharing one would mean a colleague running the suite deletes your
  open positions mid-session. The desk trades as DESK, the lab as LAB, and both
  can run at once.

  **Nothing hidden.** Every alert carries the numbers that produced it, and
  every detection that did NOT become an alert is shown with the reason it was
  held back. A tool that only shows you what fired cannot answer the question a
  sceptic actually asks, which is why something did not.

  **State that persists.** A desk is not a scenario. Orders accumulate until you
  reset, so you can build a session up the way a real one happens.

No production code is modified. The seams — fake Redis, eager Celery, a frozen
clock — are the same ones the lab applies from outside, imported rather than
copied, because two copies of that plumbing is exactly the drift this project
keeps getting bitten by.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from alertlab.runner.collect import (
    collect_alerts, collect_positions, collect_structures, collect_suppressed,
)
from alertlab.runner.harness import (
    DESK, IST, account_id, ensure_lab_account, frozen_clock, lab_environment,
    quiet_logs, teardown_lab, use_identity,
)
from alertlab.runner.inject import Fill, inject

use_identity(DESK)


def _db():
    from app.core.database import SessionLocal
    quiet_logs()
    return SessionLocal


class Desk:
    """
    One trading session you drive by hand.

    The clock is desk state rather than a per-order argument: what time it is
    changes which detectors can fire at all — the opening trap, the square-off
    window, expiry-day rules — and making it explicit is the difference between
    testing the engine and testing whatever time it happened to be.
    """

    def __init__(self) -> None:
        self.capital: float = 500_000
        self.profile: Dict[str, Any] = {}
        self.clock: datetime = self._default_clock()
        self.orders: List[Dict[str, Any]] = []
        self._seen_alerts: set = set()
        self._seen_events: set = set()

    @staticmethod
    def _default_clock() -> datetime:
        """
        10:00 on a Wednesday in the current expiry month.

        Mid-session on an ordinary day: nothing about the time itself trips a
        detector, so the first thing you see is caused by your trades rather
        than by the clock.
        """
        return datetime(2026, 8, 5, 10, 0, tzinfo=IST)

    # ── setup ───────────────────────────────────────────────────────────────

    async def reset(self, capital: Optional[float] = None,
                    profile: Optional[Dict[str, Any]] = None,
                    clock: Optional[datetime] = None) -> Dict[str, int]:
        """Wipe the desk account and start again from a stated state."""
        if capital is not None:
            self.capital = float(capital)
        if profile is not None:
            self.profile = dict(profile)
        self.clock = clock or self._default_clock()
        self.orders.clear()
        self._seen_alerts.clear()
        self._seen_events.clear()

        factory = _db()
        async with factory() as db:
            deleted = await teardown_lab(db)
            await ensure_lab_account(db, capital=self.capital, **self.profile)
        return deleted

    async def apply_settings(self, capital: Optional[float] = None,
                             profile: Optional[Dict[str, Any]] = None) -> None:
        """
        Change capital or rules WITHOUT clearing the session.

        This is what makes a threshold argument settleable in seconds: keep the
        trades, move the line, look again. The engine reads thresholds per
        evaluation, so the next order is judged by the new numbers.
        """
        if capital is not None:
            self.capital = float(capital)
        if profile is not None:
            self.profile.update(profile)
        factory = _db()
        async with factory() as db:
            await ensure_lab_account(db, capital=self.capital, **self.profile)

    # ── trading ─────────────────────────────────────────────────────────────

    async def place(self, symbol: str, side: str, qty: int, price: float,
                    product: str = "MIS", exchange: str = "NFO",
                    advance_minutes: int = 0, note: str = "") -> Dict[str, Any]:
        """
        Place one order and return everything it caused.

        The clock advances BEFORE the fill, not after, so `advance_minutes` reads
        as "wait this long, then trade" — which is how a trader thinks about it,
        and it makes the gap between two orders the thing you set rather than
        something you compute.
        """
        if advance_minutes:
            self.clock = self.clock + timedelta(minutes=int(advance_minutes))

        fill = Fill(
            symbol=symbol.strip().upper(), side=side.upper(), qty=int(qty),
            price=float(price), at=self.clock, product=product.upper(),
            exchange=exchange.upper(), note=note,
        )

        with lab_environment(None):
            with frozen_clock(self.clock):
                outcome = await inject(fill)

        record = {
            "seq": len(self.orders) + 1,
            "at_ist": self.clock.strftime("%d %b %H:%M"),
            "symbol": fill.symbol, "side": fill.side, "qty": fill.qty,
            "price": fill.price, "product": fill.product, "note": note,
            "error": outcome.get("error"),
        }
        self.orders.append(record)

        state = await self.state(new_only=True)
        return {"order": record, **state}

    async def advance(self, minutes: int) -> Dict[str, Any]:
        """Move the clock without trading. Time alone changes some answers."""
        self.clock = self.clock + timedelta(minutes=int(minutes))
        return {"clock": self.clock.strftime("%d %b %Y %H:%M")}

    # ── reading back ────────────────────────────────────────────────────────

    async def state(self, new_only: bool = False) -> Dict[str, Any]:
        """
        Everything the desk knows right now.

        `new_only` returns just what changed since the last read, which is what
        makes an alert attributable to the order that caused it rather than
        appearing in an undifferentiated pile.
        """
        factory = _db()
        async with factory() as db:
            alerts = await collect_alerts(db)
            suppressed = await collect_suppressed(db)
            positions = await collect_positions(db)
            structures = await collect_structures(db)
            # `positions` is maintained by the Kite sync, which nothing here
            # runs, so that table stays empty on a desk driven by postbacks. An
            # "open positions" panel that is always empty is worse than no
            # panel: it reads as "you are flat" while you are carrying risk.
            # The ledger is written synchronously with every fill and is
            # authoritative for quantity, so the panel comes from there.
            positions["open"] = await _open_from_ledger(db)

        if new_only:
            fresh = [a for a in alerts if a["id"] not in self._seen_alerts]
            self._seen_alerts.update(a["id"] for a in alerts)

            def key(s):
                return (s["detector"], s["detected_at_ist"], s["message"])

            fresh_supp = [s for s in suppressed if key(s) not in self._seen_events]
            self._seen_events.update(key(s) for s in suppressed)
            alerts, suppressed = fresh, fresh_supp
        else:
            self._seen_alerts = {a["id"] for a in alerts}
            self._seen_events = {
                (s["detector"], s["detected_at_ist"], s["message"]) for s in suppressed
            }

        closed = positions["closed"]
        return {
            "alerts": alerts,
            "suppressed": suppressed,
            "open": positions["open"],
            "closed": closed,
            "structures": structures,
            "guardian": [a for a in alerts if a["would_route_to_guardian"]],
            "session_pnl": round(sum(c["pnl"] for c in closed), 2),
            "exposure": self._exposure(positions["open"]),
            "clock": self.clock.strftime("%d %b %Y %H:%M"),
            "capital": self.capital,
            "orders": len(self.orders),
        }

    def _exposure(self, open_positions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        What the account is currently carrying, against the capital you set.

        Present because several detectors and every constitution rule reason
        about position size as a fraction of capital, and a number you cannot
        see is a number you cannot check.
        """
        total = sum(abs(p["qty"]) * (p["avg_entry"] or 0) for p in open_positions)
        return {
            "notional": round(total, 2),
            "pct_of_capital": round(total / self.capital * 100, 2) if self.capital else 0,
            "positions": len(open_positions),
        }

    async def wipe(self) -> Dict[str, int]:
        """Delete every row this desk created. Nothing else is touched."""
        factory = _db()
        async with factory() as db:
            deleted = await teardown_lab(db)
        self.orders.clear()
        self._seen_alerts.clear()
        self._seen_events.clear()
        return deleted


async def _open_from_ledger(db) -> List[Dict[str, Any]]:
    """
    Open positions as the ledger sees them.

    Shaped exactly like the rows `collect_positions` returns for the `positions`
    table, so the UI cannot tell the difference and no caller needs to know
    which source answered.
    """
    from app.services.position_ledger_service import PositionLedgerService

    states = await PositionLedgerService.get_position_states_bulk(account_id(), db)
    return [{
        "symbol": symbol,
        "qty": state.qty,
        "avg_entry": float(state.avg_entry_price or 0),
        "product": product,
    } for (symbol, _exchange, product), state in states.items() if (state.qty or 0) != 0]
