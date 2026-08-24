"""What have the entry-time detectors actually produced in shadow?"""
import asyncio, sys
from collections import Counter
from datetime import datetime, timedelta, timezone
sys.path.insert(0, "D:/trade-psychology-ai"); sys.path.insert(0, "D:/trade-psychology-ai/backend")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from sqlalchemy import select, func
from tradedesk.scripts.replay_tradebook import quiet_logs
quiet_logs()

async def main():
    from app.core.database import SessionLocal
    from app.models.behavior_event import BehaviorEvent
    from app.models.broker_account import BrokerAccount

    async with SessionLocal() as db:
        total = (await db.execute(select(func.count()).select_from(BehaviorEvent))).scalar()
        shadow = (await db.execute(select(func.count()).select_from(BehaviorEvent)
                                   .where(BehaviorEvent.shadow.is_(True)))).scalar()
        print(f"behavior_events rows: {total:,}   of which shadow: {shadow:,}")

        rows = list((await db.execute(
            select(BehaviorEvent).where(BehaviorEvent.shadow.is_(True))
        )).scalars())
        if not rows:
            print("\nNO SHADOW EVENTS AT ALL.")
        else:
            print("\nby detector:", dict(Counter(r.detector for r in rows).most_common()))
            at_entry = [r for r in rows if (r.evidence or {}).get("at_entry")]
            print(f"tagged at_entry: {len(at_entry)} of {len(rows)}")
            if at_entry:
                print("  entry-time by detector:",
                      dict(Counter(r.detector for r in at_entry).most_common()))
                print("  severities:", dict(Counter(r.severity for r in at_entry)))
                oldest = min(r.detected_at for r in at_entry)
                newest = max(r.detected_at for r in at_entry)
                print(f"  span: {oldest:%Y-%m-%d} to {newest:%Y-%m-%d}")

        # who is in this database at all?
        accts = list((await db.execute(select(BrokerAccount.broker_name,
                                              func.count(BrokerAccount.id))
                                       .group_by(BrokerAccount.broker_name))).all())
        print("\nbroker accounts by kind:", dict(accts))

asyncio.run(main())
