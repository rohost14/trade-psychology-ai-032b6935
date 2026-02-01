import asyncio
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models.position import Position
from uuid import UUID

async def check_positions():
    broker_account_id = UUID('550e8400-e29b-41d4-a716-446655440000')
    print(f"Checking positions for broker_account_id: {broker_account_id}")
    
    async with SessionLocal() as session:
        # Check all positions first
        stmt_all = select(Position)
        result_all = await session.execute(stmt_all)
        all_positions = result_all.scalars().all()
        print(f"Total positions in DB: {len(all_positions)}")
        for p in all_positions:
            print(f"  - ID: {p.id}, BrokerAccountID: {p.broker_account_id}, Symbol: {p.tradingsymbol}")

        # Check specific broker account
        stmt = select(Position).where(Position.broker_account_id == broker_account_id)
        result = await session.execute(stmt)
        positions = result.scalars().all()
        
        print(f"\nPositions for target account: {len(positions)}")
        for p in positions:
            print(f"  P: {p.tradingsymbol} | Qty: {p.quantity} | Val: {p.value}")

if __name__ == "__main__":
    asyncio.run(check_positions())
