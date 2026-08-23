"""
Identify episode candidates across the FULL 203-session book.

Analysis only - this lives in the scratchpad and touches nothing in app/.

An episode candidate, per the v2 hypothesis:
  a realized loss on instrument X, followed by one or more re-entries into X
  (same underlying) within the session, with the exposure trajectory recorded.

Records everything, filters nothing, so the hypothesis can be falsified rather
than confirmed.
"""
import asyncio
import json
import sys
from collections import defaultdict

sys.path.insert(0, "D:/trade-psychology-ai")
sys.path.insert(0, "D:/trade-psychology-ai/backend")
from sqlalchemy import select  # noqa: E402

NO_RULES = dict(daily_loss_limit=None, daily_trade_limit=None, max_position_size=None,
                max_consecutive_losses=None, cooldown_after_loss=0)
OUT = "docs/research/data/episodes_full.json"


async def main():
    from tradedesk.scripts.replay_tradebook import read_fills, _replay_day_once
    from app.core.database import SessionLocal
    from app.models.broker_account import BrokerAccount
    from app.models.completed_trade import CompletedTrade
    from app.core.trading_defaults import estimate_capital_at_risk
    from app.services.instrument_parser import parse_symbol as _ps

    fills = read_fills("D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26.csv")
    by_day = defaultdict(list)
    for f in fills:
        by_day[f["date"]].append(f)

    def underlying(sym):
        try:
            return _ps(sym or "").underlying or sym or ""
        except Exception:
            return sym or ""

    episodes = []
    sessions = 0
    for day in sorted(by_day):
        await _replay_day_once(day, by_day[day], 50000.0, NO_RULES)
        async with SessionLocal() as db:
            ids = (await db.execute(select(BrokerAccount.id).where(
                BrokerAccount.broker_name == "synthetic"))).scalars().all()
            ts = list((await db.execute(
                select(CompletedTrade)
                .where(CompletedTrade.broker_account_id.in_(ids))
                .order_by(CompletedTrade.exit_time.asc()))).scalars())
        sessions += 1
        if not ts:
            continue

        def risk(t):
            return estimate_capital_at_risk(
                t.instrument_type, t.tradingsymbol or "", t.direction or "LONG",
                float(t.avg_entry_price or 0), int(t.total_quantity or 0))

        # walk the session; for each loss, follow re-entries into the same underlying
        used = set()
        for i, t in enumerate(ts):
            if i in used or float(t.realized_pnl or 0) >= 0:
                continue
            und = underlying(t.tradingsymbol)
            chain = [i]
            for j in range(i + 1, len(ts)):
                nxt = ts[j]
                if underlying(nxt.tradingsymbol) != und:
                    continue
                if not (nxt.entry_time and ts[chain[-1]].exit_time
                        and nxt.entry_time >= ts[chain[-1]].exit_time):
                    continue
                chain.append(j)
                # the account closes on a win in this instrument
                if float(nxt.realized_pnl or 0) > 0:
                    break
            if len(chain) < 2:
                continue
            used.update(chain)
            legs = [ts[k] for k in chain]
            gaps = []
            for a, b in zip(legs, legs[1:]):
                if a.exit_time and b.entry_time:
                    gaps.append((b.entry_time - a.exit_time).total_seconds() / 60)
            qtys = [int(x.total_quantity or 0) for x in legs]
            risks = [risk(x) for x in legs]
            pnls = [float(x.realized_pnl or 0) for x in legs]
            episodes.append({
                "day": str(day),
                "underlying": und,
                "symbols": [x.tradingsymbol for x in legs],
                "attempts": len(legs),
                "qtys": qtys,
                "risks": risks,
                "pnls": pnls,
                "gaps": gaps,
                "exposure_grew": any(b > a for a, b in zip(qtys, qtys[1:])),
                "monotonic_growth": all(b >= a for a, b in zip(qtys, qtys[1:])) and qtys[-1] > qtys[0],
                "ended_in_win": pnls[-1] > 0,
                "total_pnl": sum(pnls),
                "instrument_type": legs[0].instrument_type,
                "directions": [x.direction for x in legs],
            })

    json.dump({"sessions": sessions, "episodes": episodes}, open(OUT, "w"))
    print(f"sessions={sessions} episode_candidates={len(episodes)}")

asyncio.run(main())
