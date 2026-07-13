"""
SessionState — rebuildable session-scoped behavioral state (Engine v2 §1B.1).

STATE OWNERSHIP TABLE (A.7 — every field has exactly ONE owner)
────────────────────────────────────────────────────────────────
Owned by SessionState (this module — session facts, reset daily):
    session_pnl, peak_pnl, drawdown_from_peak, trade_count,
    winners, losers, consecutive_losses, consecutive_wins,
    total_loss_amount, avg_winner_hold_min, avg_loser_hold_min,
    last_loss_time, last_trade_time, first_trade_time

Owned by TradingSession DB row (persistence layer, NOT duplicated here as
authority — SessionState.rebuild() derives the same numbers from trades;
the DB row remains the store the current engine reads):
    risk_score, peak_risk_score, alerts_fired, session_date

Owned by baseline (user_profile.detected_patterns.baseline — Phase 3):
    all *_baseline metrics

Owned by constitution (user_profile rule fields — Phase 2):
    all declared limits

DERIVED STATE (scores — Phase 5) lives elsewhere and is NEVER an input to
detectors (A.10 derived-state ban).
────────────────────────────────────────────────────────────────

Design rule: this object is a PURE FOLD over the session's CompletedTrades.
rebuild(trades) from scratch and update(state, trade) incrementally MUST
produce identical results — that property is what makes Redis caching safe
later (crash/eviction/bulk-sync → rebuild from Postgres, never trust cache).
Phase 1 uses rebuild() only (replay harness + parity tests); the incremental
path and Redis layer arrive with entry-time detection (Phase 6).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Optional


@dataclass
class SessionState:
    session_pnl: Decimal = Decimal("0")
    peak_pnl: Decimal = Decimal("0")
    drawdown_from_peak: Decimal = Decimal("0")

    trade_count: int = 0
    winners: int = 0
    losers: int = 0

    consecutive_losses: int = 0
    consecutive_wins: int = 0
    total_loss_amount: Decimal = Decimal("0")   # sum of |losses| this session

    winner_hold_minutes: List[float] = field(default_factory=list)
    loser_hold_minutes: List[float] = field(default_factory=list)

    first_trade_time: Optional[datetime] = None
    last_trade_time: Optional[datetime] = None
    last_loss_time: Optional[datetime] = None

    @property
    def avg_winner_hold_min(self) -> Optional[float]:
        return (sum(self.winner_hold_minutes) / len(self.winner_hold_minutes)
                if self.winner_hold_minutes else None)

    @property
    def avg_loser_hold_min(self) -> Optional[float]:
        return (sum(self.loser_hold_minutes) / len(self.loser_hold_minutes)
                if self.loser_hold_minutes else None)

    # ── The fold ──────────────────────────────────────────────────────────

    def update(self, trade) -> "SessionState":
        """
        Apply one CompletedTrade (or compatible object with realized_pnl,
        entry_time, exit_time, duration_minutes) to the state. O(1).
        """
        pnl = Decimal(str(trade.realized_pnl or 0))

        self.trade_count += 1
        self.session_pnl += pnl

        if self.session_pnl > self.peak_pnl:
            self.peak_pnl = self.session_pnl
        self.drawdown_from_peak = self.peak_pnl - self.session_pnl

        hold_min = None
        if trade.entry_time and trade.exit_time:
            hold_min = (trade.exit_time - trade.entry_time).total_seconds() / 60
        elif getattr(trade, "duration_minutes", None) is not None:
            hold_min = float(trade.duration_minutes)

        if pnl > 0:
            self.winners += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            if hold_min is not None:
                self.winner_hold_minutes.append(hold_min)
        elif pnl < 0:
            self.losers += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            self.total_loss_amount += abs(pnl)
            self.last_loss_time = trade.exit_time
            if hold_min is not None:
                self.loser_hold_minutes.append(hold_min)
        # pnl == 0: scratch trade — counts, breaks no streak either way

        if trade.exit_time:
            if self.first_trade_time is None:
                self.first_trade_time = trade.entry_time or trade.exit_time
            self.last_trade_time = trade.exit_time
        return self

    @classmethod
    def rebuild(cls, trades) -> "SessionState":
        """
        Rebuild from scratch: fold over trades sorted by exit_time.
        This is THE recovery path — cache loss is never data loss.
        """
        state = cls()
        for t in sorted(trades, key=lambda t: t.exit_time or datetime.min):
            state.update(t)
        return state
