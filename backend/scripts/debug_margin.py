
import asyncio
import logging
from app.core.database import SessionLocal
from app.services.margin_service import margin_service
from app.models.broker_account import BrokerAccount
from sqlalchemy import select

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_margin():
    async with SessionLocal() as db:
        # Get first account
        result = await db.execute(select(BrokerAccount))
        account = result.scalars().first()
        
        if not account:
            print("No broker account found.")
            return

        print(f"Checking margin for account: {account.id} (User: {account.user_id})")
        
        # Check margin status
        try:
            status = await margin_service.get_margin_status(account.id, db)
            print("\n--- Margin Status Result ---")
            print(status)
            
            if "equity" in status:
                print(f"\nEquity Utilization: {status['equity'].get('utilization_pct')}%")
                print(f"Available: {status['equity'].get('available')}")
                print(f"Used: {status['equity'].get('used')}")
                print(f"Live Balance: {status['equity'].get('breakdown', {}).get('live_balance', 'N/A')}")
        except Exception as e:
            print(f"Error fetching margin: {e}")

if __name__ == "__main__":
    asyncio.run(debug_margin())
