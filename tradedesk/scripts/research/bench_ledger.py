"""Query design + cost, and the contract walked over REAL ledger rows."""
import asyncio, sys, time
sys.path.insert(0, "D:/trade-psychology-ai"); sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.path.insert(0, r"C:\Users\being\.claude\jobs\33a73186/tmp")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from sqlalchemy import select, func

async def main():
    from app.core.database import SessionLocal
    from app.models.broker_account import BrokerAccount
    from app.models.position_ledger import PositionLedger
    from app.models.completed_trade import CompletedTrade
    from app.core.instrument_risk import risk_basis

    async with SessionLocal() as db:
        ids = (await db.execute(select(BrokerAccount.id).where(
            BrokerAccount.broker_name == "synthetic"))).scalars().all()
        cts = list((await db.execute(select(CompletedTrade).where(
            CompletedTrade.broker_account_id.in_(ids)))).scalars())
        print(f"{len(cts)} completed trades in the lab account\n")

        # ---- A. per-position query, the shape the index serves ----
        async def per_position(ct):
            return list((await db.execute(
                select(PositionLedger)
                .where(PositionLedger.broker_account_id == ct.broker_account_id,
                       PositionLedger.tradingsymbol == ct.tradingsymbol,
                       PositionLedger.occurred_at >= ct.entry_time,
                       PositionLedger.occurred_at <= ct.exit_time)
                .order_by(PositionLedger.occurred_at))).scalars())

        # warm
        await per_position(cts[0])
        single, multi = [], []
        for ct in cts:
            t = time.perf_counter()
            rows = await per_position(ct)
            dt = (time.perf_counter() - t) * 1000
            (multi if len(rows) > 2 else single).append(dt)
        def stat(v):
            return f"n={len(v)} mean={sum(v)/len(v):.2f}ms max={max(v):.2f}ms" if v else "n=0"
        print("PER-POSITION QUERY (uses idx_position_ledger_account_symbol)")
        print(f"  single-fill positions : {stat(single)}")
        print(f"  multi-fill positions  : {stat(multi)}")

        # ---- B. one query for the whole session, grouped in memory ----
        t = time.perf_counter()
        allrows = list((await db.execute(
            select(PositionLedger)
            .where(PositionLedger.broker_account_id.in_(ids))
            .order_by(PositionLedger.tradingsymbol, PositionLedger.occurred_at))).scalars())
        dt = (time.perf_counter() - t) * 1000
        print(f"\nSESSION-WIDE QUERY, grouped in memory: 1 query, {len(allrows)} rows, {dt:.2f}ms")
        print(f"  vs {len(cts)} per-position queries totalling "
              f"{sum(single)+sum(multi):.2f}ms")

        # ---- C. walk the REAL ledger rows through the contract ----
        print("\nCONTRACT WALKED OVER REAL LEDGER ROWS")
        from collections import defaultdict
        bysym = defaultdict(list)
        for r in allrows:
            bysym[r.tradingsymbol].append(r)
        for sym, rows in bysym.items():
            qty = 0; avg = 0.0; n_adv = 0; out = []
            for r in rows:
                if r.entry_type == "OPEN":
                    qty, avg, n_adv = r.fill_qty, float(r.fill_price), 0
                elif r.entry_type == "INCREASE":
                    d = 1.0 if qty > 0 else -1.0
                    adv = (avg - float(r.fill_price)) / avg * 100 * d
                    rb_b = risk_basis("CE", sym, "LONG" if qty > 0 else "SHORT", avg, abs(qty))
                    nq = qty + r.fill_qty
                    navg = float(r.avg_entry_price_after)
                    rb_a = risk_basis("CE", sym, "LONG" if qty > 0 else "SHORT", navg, abs(nq))
                    if adv > 0:
                        n_adv += 1
                        out.append(f"REPORT#{n_adv} {adv:+.1f}% adverse, exposure "
                                   f"{rb_b.amount:,.0f}->{rb_a.amount:,.0f}")
                    else:
                        out.append(f"IGNORE {adv:+.1f}% (favourable/flat)")
                    qty, avg = nq, navg
                elif r.entry_type in ("DECREASE",):
                    qty += r.fill_qty
                elif r.entry_type in ("CLOSE", "FLIP"):
                    qty, avg, n_adv = 0, 0.0, 0
            if out:
                print(f"  {sym}")
                for line in out:
                    print(f"     {line}")

asyncio.run(main())
