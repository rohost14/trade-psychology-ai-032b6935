# -*- coding: utf-8 -*-
"""
Can /status report today's usage for the two PER-TRADE rules?

`per_trade_loss_limit` and `max_position_size` are not cumulative. The question
is whether a per-session PEAK ("the worst single trade today", "the largest
single position today") is computable and reliable enough to show a trader.

  * per-trade loss   -> min(realized_pnl) over the session. Pure arithmetic on
                        the same unit the other status rows use.
  * position size    -> max(capital_requirement / trading_capital). Goes through
                        `quantities_for_trade`, WHICH IS ALLOWED TO ABSTAIN. If
                        it abstains often, the peak is not the real peak and
                        showing it would be a false statement.

Measures the abstention rate first, because that is the thing that decides it.
"""
import asyncio
from collections import Counter, defaultdict

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.risk_quantities import quantities_for_trade
from app.models.completed_trade import CompletedTrade


async def main():
    async with SessionLocal() as db:
        trades = (await db.execute(
            select(CompletedTrade).order_by(CompletedTrade.exit_time)
        )).scalars().all()

    print("completed trades: %d" % len(trades))

    # ── 1. per-trade loss: does every trade have a usable P&L? ────────────
    have_pnl = sum(1 for t in trades if t.realized_pnl is not None)
    print("\n1. PER-TRADE LOSS")
    print("   realized_pnl present : %d / %d (%.1f%%)"
          % (have_pnl, len(trades), 100.0 * have_pnl / max(len(trades), 1)))

    # ── 2. capital at risk: how often does the risk layer abstain? ────────
    usable = 0
    notes = Counter()
    by_exchange = defaultdict(lambda: [0, 0])
    for t in trades:
        rq = quantities_for_trade(t, margin=None)
        ex = (t.exchange or "?")
        by_exchange[ex][1] += 1
        if rq.usable_for_capital_rules:
            usable += 1
            by_exchange[ex][0] += 1
        else:
            notes[(rq.capital_requirement.note or "?")[:60]] += 1

    print("\n2. CAPITAL AT RISK (max_position_size)")
    print("   usable_for_capital_rules : %d / %d (%.1f%%)"
          % (usable, len(trades), 100.0 * usable / max(len(trades), 1)))
    for ex, (u, n) in sorted(by_exchange.items()):
        print("     %-8s %5d / %5d usable" % (ex, u, n))
    if notes:
        print("   abstention reasons:")
        for note, n in notes.most_common(6):
            print("     %5d  %s" % (n, note))

    # ── 3. what would the session peaks look like? ────────────────────────
    by_day = defaultdict(list)
    for t in trades:
        if t.exit_time:
            by_day[t.exit_time.date()].append(t)

    CAPITAL = 100_000.0
    worst_losses, peak_pcts, days_partial = [], [], 0
    for day, ts in by_day.items():
        losses = [float(t.realized_pnl) for t in ts if (t.realized_pnl or 0) < 0]
        if losses:
            worst_losses.append(abs(min(losses)))
        pcts, abstained = [], 0
        for t in ts:
            rq = quantities_for_trade(t, margin=None)
            if rq.usable_for_capital_rules:
                pcts.append(float(rq.capital_requirement.amount) / CAPITAL * 100)
            else:
                abstained += 1
        if pcts:
            peak_pcts.append(max(pcts))
        if abstained:
            days_partial += 1

    def pct(xs, p):
        xs = sorted(xs)
        return xs[min(int(len(xs) * p / 100.0), len(xs) - 1)] if xs else float("nan")

    print("\n3. SESSION PEAKS  (%d sessions)" % len(by_day))
    print("   worst single loss / day  median Rs %.0f   p90 Rs %.0f   max Rs %.0f"
          % (pct(worst_losses, 50), pct(worst_losses, 90), max(worst_losses or [0])))
    print("   largest position / day   median %.1f%%   p90 %.1f%%   max %.1f%%   (capital Rs %.0f)"
          % (pct(peak_pcts, 50), pct(peak_pcts, 90), max(peak_pcts or [0]), CAPITAL))
    print("   sessions where >=1 trade ABSTAINED: %d / %d (%.1f%%)"
          % (days_partial, len(by_day), 100.0 * days_partial / max(len(by_day), 1)))


asyncio.run(main())
