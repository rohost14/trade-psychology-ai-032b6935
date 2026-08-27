"""
Live premium-loss risk state — evaluated on the tick, never against the database.

WHY THIS EXISTS

`premium_loss_event` used to be checked by a 60-second Celery beat that re-read
the world every cycle: one query for every connected account, then per account a
positions query, a profile query and a full `resolve_thresholds` walk. At 10,000
users that is roughly 20,001 database round trips a minute, in a serial loop, to
check a number that only changes when a price does. At 2 ms per round trip it
consumes 40 seconds of a 60-second budget; at the 30-50 ms actually measured
against this Supabase instance it cannot finish inside its own period at all.

So the state moves into memory, beside the one shared KiteTicker that already
receives every price, and the database is touched only when the state CHANGES —
a fill, a close, a rules edit, a restart.

WHAT THIS IS, AND IS NOT

Pattern #8 stopped being a behaviour detector in its 2026-08-27 review. It is a
**risk-state** detector: it reports what is true about a position and supplies
that fact to the detectors that judge behaviour. It makes no claim about why a
trade was taken. A large premium loss is a market outcome, and every test that
could have tied loss magnitude to a decision has failed.

The alert's job is narrow and worth stating exactly: **close the gap between what
is true about the position and what the trader currently knows.** That gap exists
only when they are not looking — anyone watching the screen already has the
number, because the frontend computes live P&L client-side from this same tick
stream. So this speaks on a CROSSING, never on a state, and never at exit, where
the trader necessarily knows because they just closed it.

TWO LAYERS, AND WHY THEY STAY TWO

  universal   40 / 60 / 80 percent of premium, +15pp on expiry day.
              `Kind.UNIVERSAL_SAFETY` — objective, never personalised, and a
              trader's habits may never raise it.
  declared    `sl_percent_options`, the exit rule the trader wrote down.
              `Kind.USER_RULE` — a commitment, and the stronger reference when
              it is TIGHTER.

They are different sentences about the same position and both can be true. This
module reports whichever boundary is crossed; it does not blend them into one
number, because that would destroy the distinction `Kind` exists to protect.

PURITY

`evaluate` and `evaluate_batch` perform no I/O of any kind: no database, no
Redis, no network. They are given a price and return crossings. That is the
property the tests assert and the reason this can run on every tick.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple
from uuid import UUID

logger = logging.getLogger(__name__)

#: Which boundary a crossing belongs to. Never merged - see the module docstring.
UNIVERSAL = "universal"
DECLARED = "declared"

#: Severity per universal band, in ascending order. The percentages themselves
#: are NOT defined here - they are resolved thresholds, passed in per position,
#: so a change to `trading_defaults` cannot be silently contradicted by this file.
_UNIVERSAL_SEVERITIES = ("caution", "danger", "critical")


@dataclass(frozen=True)
class Crossing:
    """One boundary, crossed once, by one position."""

    broker_account_id: str
    tradingsymbol: str
    instrument_token: int
    kind: str                 # UNIVERSAL | DECLARED
    severity: str
    loss_pct: float
    boundary_pct: float
    band_index: int           # -1 for DECLARED; 0/1/2 for the universal bands
    entry_price: float
    last_price: float
    quantity: int
    epoch: str
    expiry_day: bool


@dataclass
class PositionWatch:
    """
    One open long option, and how far it has already been reported.

    `epoch` identifies the position itself rather than the symbol: it comes from
    the ledger's OPEN/FLIP moment, so a symbol traded, closed and re-entered the
    same day is two positions with two independent memories. Reusing Pattern 2's
    concept rather than inventing a second one.
    """

    broker_account_id: str
    tradingsymbol: str
    instrument_token: int
    epoch: str
    avg_entry_price: float
    quantity: int
    #: Ascending universal boundaries, already expiry-shifted by the builder.
    universal_bands: Tuple[float, ...]
    #: The trader's own exit rule, already expiry-shifted, or None if undeclared.
    declared_pct: Optional[float]
    expiry_day: bool = False

    #: Highest universal band already reported for THIS epoch. -1 = none yet.
    highest_band_fired: int = -1
    #: Whether the declared boundary has already been reported for this epoch.
    declared_fired: bool = False

    def loss_pct(self, ltp: float) -> Optional[float]:
        """
        Percentage of the premium paid that is currently gone.

        None when it cannot be computed. A long option's downside is the premium,
        so a reading past 100% is a data defect rather than a loss, and it is
        clamped for the same reason the exit-time detector clamps it: "180% of
        premium lost" reaching a trader would cost the credibility of every other
        number on the screen.
        """
        if self.avg_entry_price <= 0 or ltp is None or ltp < 0:
            return None
        pct = (self.avg_entry_price - float(ltp)) / self.avg_entry_price * 100.0
        if pct <= 0:
            return None
        return min(pct, 100.0)

    def evaluate(self, ltp: float) -> List[Crossing]:
        """
        Crossings produced by this price, and the state change that records them.

        At most one universal crossing per call: a price that jumps straight past
        two bands reports the HIGHER one, because that is what is true, and marks
        the lower as already covered. Telling a trader "you passed 40%" when they
        are at 85% would be accurate and useless.
        """
        pct = self.loss_pct(ltp)
        if pct is None:
            return []

        out: List[Crossing] = []

        # The declared rule first: it is the trader's own line, and when it is
        # tighter than the universal band it is what they asked to hear about.
        if (self.declared_pct is not None
                and not self.declared_fired
                and pct >= self.declared_pct):
            self.declared_fired = True
            out.append(Crossing(
                broker_account_id=self.broker_account_id,
                tradingsymbol=self.tradingsymbol,
                instrument_token=self.instrument_token,
                kind=DECLARED,
                severity="danger",
                loss_pct=round(pct, 1),
                boundary_pct=self.declared_pct,
                band_index=-1,
                entry_price=self.avg_entry_price,
                last_price=float(ltp),
                quantity=self.quantity,
                epoch=self.epoch,
                expiry_day=self.expiry_day,
            ))

        highest = self.highest_band_fired
        reached = -1
        for i, boundary in enumerate(self.universal_bands):
            if pct >= boundary:
                reached = i
        if reached > highest:
            self.highest_band_fired = reached
            out.append(Crossing(
                broker_account_id=self.broker_account_id,
                tradingsymbol=self.tradingsymbol,
                instrument_token=self.instrument_token,
                kind=UNIVERSAL,
                severity=_UNIVERSAL_SEVERITIES[min(reached, len(_UNIVERSAL_SEVERITIES) - 1)],
                loss_pct=round(pct, 1),
                boundary_pct=self.universal_bands[reached],
                band_index=reached,
                entry_price=self.avg_entry_price,
                last_price=float(ltp),
                quantity=self.quantity,
                epoch=self.epoch,
                expiry_day=self.expiry_day,
            ))

        return out


class LiveRiskState:
    """
    Every open long option, indexed by the token its price arrives on.

    Sized for the job: 10,000 traders with ~3 open option positions each is
    30,000 watches at roughly 200 bytes, about 6 MB. Ticks are throttled to one
    per second per instrument and the ticker is capped at 3,000 instruments, so
    the worst case is ~3,000 evaluations a second over ~10 watches each - float
    comparisons, no allocation of consequence.
    """

    def __init__(self) -> None:
        self._by_token: Dict[int, List[PositionWatch]] = {}
        self._by_account: Dict[str, List[PositionWatch]] = {}
        self._lock = threading.RLock()

    # ── state, changed only when a position or a rule changes ─────────────

    def replace_account(self, broker_account_id: str, watches: Iterable[PositionWatch]) -> None:
        """
        Swap in this account's whole watch list.

        Whole-account replacement rather than per-position patching: the caller
        has just read the account's positions from the database anyway, and a
        partial update is how a closed position gets left behind alerting on a
        price it no longer holds.

        Band memory is carried across for positions whose epoch is unchanged, so
        a rebuild triggered by an unrelated fill cannot re-announce a band the
        trader has already been told about.
        """
        acct = str(broker_account_id)
        with self._lock:
            previous = {(w.tradingsymbol, w.epoch): w for w in self._by_account.get(acct, ())}
            fresh: List[PositionWatch] = []
            for w in watches:
                old = previous.get((w.tradingsymbol, w.epoch))
                if old is not None:
                    w.highest_band_fired = old.highest_band_fired
                    w.declared_fired = old.declared_fired
                fresh.append(w)
            self._drop_locked(acct)
            self._by_account[acct] = fresh
            for w in fresh:
                self._by_token.setdefault(w.instrument_token, []).append(w)

    def drop_account(self, broker_account_id: str) -> None:
        with self._lock:
            self._drop_locked(str(broker_account_id))

    def _drop_locked(self, acct: str) -> None:
        for w in self._by_account.pop(acct, ()):
            holders = self._by_token.get(w.instrument_token)
            if not holders:
                continue
            remaining = [h for h in holders if h.broker_account_id != acct]
            if remaining:
                self._by_token[w.instrument_token] = remaining
            else:
                self._by_token.pop(w.instrument_token, None)

    def clear(self) -> None:
        with self._lock:
            self._by_token.clear()
            self._by_account.clear()

    # ── the hot path: no I/O, ever ────────────────────────────────────────

    def evaluate(self, instrument_token: int, ltp: float) -> List[Crossing]:
        """Crossings caused by one price. No database, no Redis, no network."""
        with self._lock:
            holders = list(self._by_token.get(int(instrument_token), ()))
        out: List[Crossing] = []
        for w in holders:
            out.extend(w.evaluate(ltp))
        return out

    def evaluate_batch(self, prices: Dict[int, float]) -> List[Crossing]:
        """Crossings caused by a whole tick batch."""
        out: List[Crossing] = []
        for token, ltp in prices.items():
            try:
                out.extend(self.evaluate(int(token), float(ltp)))
            except (TypeError, ValueError):
                continue
        return out

    # ── introspection, for tests and diagnostics ──────────────────────────

    @property
    def watch_count(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._by_account.values())

    def watches_for(self, broker_account_id: str) -> List[PositionWatch]:
        with self._lock:
            return list(self._by_account.get(str(broker_account_id), ()))


#: Process-local singleton. It lives beside the shared ticker, which is already
#: one connection for all users, so there is exactly one of these per worker that
#: receives ticks.
live_risk_state = LiveRiskState()


def build_watches(
    positions: Iterable,
    thresholds: Dict,
    broker_account_id: str,
    is_expiry_day_fn=None,
) -> List[PositionWatch]:
    """
    Turn an account's open positions into watches. Pure: give it rows and
    resolved thresholds, it returns objects. The caller owns the database read.

    Long options only, mirroring the exit-time detector: a short option receives
    premium rather than paying it, so a percentage of premium lost is meaningless
    there.
    """
    caution = float(thresholds.get("premium_loss_caution_pct", 40))
    danger = float(thresholds.get("premium_loss_danger_pct", 60))
    critical = float(thresholds.get("premium_loss_critical_pct", 80))
    shift = float(thresholds.get("premium_loss_expiry_shift_pct", 15))
    declared_raw = thresholds.get("sl_percent_options")

    out: List[PositionWatch] = []
    for pos in positions:
        symbol = getattr(pos, "tradingsymbol", "") or ""
        if not symbol.endswith(("CE", "PE")):
            continue
        qty = int(getattr(pos, "total_quantity", 0) or 0)
        if qty <= 0:
            continue          # short options: premium received, not destroyed
        token = getattr(pos, "instrument_token", None)
        if not token:
            continue
        entry = float(getattr(pos, "average_entry_price", 0) or 0)
        if entry <= 0:
            continue

        expiry = False
        if is_expiry_day_fn is not None:
            try:
                expiry = bool(is_expiry_day_fn(symbol))
            except Exception:
                expiry = False

        bump = shift if expiry else 0.0
        declared = None
        if declared_raw:
            try:
                declared = float(declared_raw) + bump
            except (TypeError, ValueError):
                declared = None

        out.append(PositionWatch(
            broker_account_id=str(broker_account_id),
            tradingsymbol=symbol,
            instrument_token=int(token),
            epoch=str(getattr(pos, "opened_at", None) or getattr(pos, "id", symbol)),
            avg_entry_price=entry,
            quantity=qty,
            universal_bands=(caution + bump, danger + bump, critical + bump),
            declared_pct=declared,
            expiry_day=expiry,
        ))
    return out
