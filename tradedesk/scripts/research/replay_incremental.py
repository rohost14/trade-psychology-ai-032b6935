"""
Real-time simulation: inject the real ladder fill by fill and call the entry
task after each one, exactly as the fill pipeline would. Proves the alert lands
ON THE ADD rather than at exit.
"""
import asyncio, sys, time
from collections import defaultdict
from datetime import date
sys.path.insert(0, "D:/trade-psychology-ai"); sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from sqlalchemy import select
from tradedesk.scripts.replay_tradebook import quiet_logs
quiet_logs()

LADDERS = {
    date(2025, 11, 25): "NIFTY25NOV26000CE",   # -Rs 8,835, 4 adverse adds
    date(2025, 6, 12): "ASIANPAINT25JUN2400CE",  # -Rs 2,810, constant 200
    date(2025, 8, 12): "TITAN25AUG3600CE",     # adds while IN PROFIT - must stay silent
}

async def main():
    from tradedesk.scripts.replay_tradebook import read_fills
    from alertlab.runner.inject import Fill, inject
    from alertlab.runner.harness import ensure_lab_account, teardown_lab
    from app.core.database import SessionLocal
    from app.models.broker_account import BrokerAccount
    from app.models.risk_alert import RiskAlert
    from app.tasks.position_monitor_tasks import _adverse_add_task

    raw = read_fills("D:/trade-psychology-ai/docs/tradebook-CY6001-FO2025-26.csv")
    by_day = defaultdict(list)
    for f in raw:
        by_day[f["date"]].append(f)

    NO_RULES = dict(daily_loss_limit=None, daily_trade_limit=None,
                    max_position_size=None, max_consecutive_losses=None,
                    cooldown_after_loss=0)

    for day, symbol in LADDERS.items():
        async with SessionLocal() as db:
            await teardown_lab(db)
            await ensure_lab_account(db, capital=50000.0, **NO_RULES)
            acct = (await db.execute(select(BrokerAccount.id).where(
                BrokerAccount.broker_name == "synthetic"))).scalars().first()
        acct = str(acct)
        print(f"\n{'='*74}\n{day}  {symbol}\n{'='*74}")

        rows = [f for f in sorted(by_day[day], key=lambda x: x["at"])
                if f["symbol"] == symbol]
        timings = []
        for i, f in enumerate(rows, 1):
            await inject(Fill(symbol=f["symbol"], side=f["side"], qty=f["qty"],
                              price=f["price"], at=f["at"],
                              exchange=f.get("exchange", "NFO")))
            t0 = time.perf_counter()
            res = await _adverse_add_task(acct, symbol)
            timings.append((time.perf_counter() - t0) * 1000)
            if res.get("fired"):
                mark = f"ALERT [{res['severity']}]"
            elif "severity" in res:
                mark = f"deduped [{res['severity']}]"
            else:
                mark = res.get("skipped", "-")
            print(f"  fill {i}: {f['side']:<4} {f['qty']:>5} @ {f['price']:>8.2f}  "
                  f"-> {mark:<22} ({timings[-1]:.0f}ms)")
            if res.get("fired"):
                async with SessionLocal() as db:
                    a = list((await db.execute(select(RiskAlert).where(
                        RiskAlert.broker_account_id == acct,
                        RiskAlert.pattern_type == "adding_to_adverse_position",
                    ).order_by(RiskAlert.created_at.desc()).limit(1))).scalars())
                if a:
                    print(f"           {a[0].message[:118]}")
        print(f"  task latency: mean {sum(timings)/len(timings):.0f}ms  max {max(timings):.0f}ms")

    async with SessionLocal() as db:
        await teardown_lab(db)

asyncio.run(main())
