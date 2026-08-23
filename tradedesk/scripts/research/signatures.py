"""
One row per LOSING round-trip across all 203 sessions, with the raw facts every
loss-chasing signature needs. Signatures are computed offline from this, so one
replay answers all of them.

Analysis only - scratchpad, nothing in app/.
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
OUT = "docs/research/data/signatures.json"


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

    def und(sym):
        try:
            return _ps(sym or "").underlying or sym or ""
        except Exception:
            return sym or ""

    def risk(t):
        return estimate_capital_at_risk(
            t.instrument_type, t.tradingsymbol or "", t.direction or "LONG",
            float(t.avg_entry_price or 0), int(t.total_quantity or 0))

    rows, session_rows = [], []
    for day in sorted(by_day):
        await _replay_day_once(day, by_day[day], 50000.0, NO_RULES)
        async with SessionLocal() as db:
            ids = (await db.execute(select(BrokerAccount.id).where(
                BrokerAccount.broker_name == "synthetic"))).scalars().all()
            ts = list((await db.execute(
                select(CompletedTrade)
                .where(CompletedTrade.broker_account_id.in_(ids))
                .order_by(CompletedTrade.exit_time.asc()))).scalars())
        if not ts:
            continue

        qtys = [int(t.total_quantity or 0) for t in ts]
        risks = [risk(t) for t in ts]
        med_qty = sorted(qtys)[len(qtys) // 2] if qtys else 0
        med_risk = sorted(risks)[len(risks) // 2] if risks else 0
        gaps_all = []
        for a, b in zip(ts, ts[1:]):
            if a.exit_time and b.entry_time and b.entry_time >= a.exit_time:
                gaps_all.append((b.entry_time - a.exit_time).total_seconds() / 60)
        med_gap = sorted(gaps_all)[len(gaps_all) // 2] if gaps_all else None

        session_rows.append({
            "day": str(day), "trades": len(ts),
            "pnl": sum(float(t.realized_pnl or 0) for t in ts),
            "med_qty": med_qty, "med_risk": med_risk, "med_gap": med_gap,
            "first_qty": qtys[0] if qtys else 0,
        })

        running = 0.0
        for i, t in enumerate(ts):
            pnl = float(t.realized_pnl or 0)
            running += pnl
            nxt = ts[i + 1] if i + 1 < len(ts) else None
            gap = None
            if nxt and nxt.entry_time and t.exit_time and nxt.entry_time >= t.exit_time:
                gap = (nxt.entry_time - t.exit_time).total_seconds() / 60

            # trades entered within 30 min of this exit
            burst = 0
            if t.exit_time:
                for x in ts[i + 1:]:
                    if x.entry_time and 0 <= (x.entry_time - t.exit_time).total_seconds() / 60 <= 30:
                        burst += 1

            rest = sum(float(x.realized_pnl or 0) for x in ts[i + 1:])
            rows.append({
                "day": str(day), "idx": i, "n_trades": len(ts),
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                "sym": t.tradingsymbol, "und": und(t.tradingsymbol),
                "dir": t.direction, "qty": int(t.total_quantity or 0),
                "risk": risk(t), "won": pnl >= 0, "pnl": pnl, "loss": abs(pnl),
                "ratio": abs(pnl) / risk(t) if risk(t) else None,
                "running_pnl": running, "rest_of_session_pnl": rest,
                "session_med_qty": med_qty, "session_med_gap": med_gap,
                "gap_to_next": gap,
                "next_sym": nxt.tradingsymbol if nxt else None,
                "next_und": und(nxt.tradingsymbol) if nxt else None,
                "next_dir": nxt.direction if nxt else None,
                "next_qty": int(nxt.total_quantity or 0) if nxt else None,
                "next_risk": risk(nxt) if nxt else None,
                "next_pnl": float(nxt.realized_pnl or 0) if nxt else None,
                "burst_30min": burst,
                "instrument_type": t.instrument_type,
            })

    json.dump({"trades": rows, "sessions": session_rows}, open(OUT, "w"))
    print(f"sessions={len(session_rows)} trades={len(rows)} losses={sum(1 for r in rows if not r['won'])}")

asyncio.run(main())
