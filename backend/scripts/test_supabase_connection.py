import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)

async def test_connection():
    broker_account_id = '550e8400-e29b-41d4-a716-446655440000'
    
    with open('test_results.txt', 'w', encoding='utf-8') as f:
        try:
            async with engine.begin() as conn:
                f.write("Testing Supabase connection...\n\n")
                
                # First, check if broker_account exists, create if not
                f.write("Step 1: Checking/creating broker_account...\n")
                result = await conn.execute(text("""
                    SELECT id FROM broker_accounts WHERE id = :id
                """), {'id': broker_account_id})
                
                if not result.fetchone():
                    f.write("  - Broker account not found, creating test account...\n")
                    await conn.execute(text("""
                        INSERT INTO broker_accounts (
                            id, broker_name, status, created_at
                        ) VALUES (
                            :id, 'TEST_BROKER', 'active', NOW()
                        )
                    """), {'id': broker_account_id})
                    f.write("  ✓ Test broker account created\n")
                else:
                    f.write("  ✓ Broker account exists\n")
                
                # Now test inserting position
                f.write("\nStep 2: Inserting test position record...\n")
                test_position_id = '12345678-1234-1234-1234-123456789abc'
                await conn.execute(text("""
                    INSERT INTO positions (
                        id, broker_account_id, tradingsymbol, exchange, 
                        asset_class, instrument_type, product,
                        quantity, average_price, created_at
                    ) VALUES (
                        :id, :broker_id, 'TEST-SYMBOL', 'NSE',
                        'equity', 'EQ', 'CNC',
                        10, 100.50, NOW()
                    )
                """), {
                    'id': test_position_id,
                    'broker_id': broker_account_id
                })
                f.write("  ✓ Position record inserted successfully\n")
                
                # Query it back
                f.write("\nStep 3: Querying back the position...\n")
                result = await conn.execute(text("""
                    SELECT id, tradingsymbol, quantity, average_price 
                    FROM positions 
                    WHERE id = :id
                """), {'id': test_position_id})
                row = result.fetchone()
                
                if row:
                    f.write(f"  ✓ Record found!\n")
                    f.write(f"    - ID: {row[0]}\n")
                    f.write(f"    - Symbol: {row[1]}\n")
                    f.write(f"    - Quantity: {row[2]}\n")
                    f.write(f"    - Avg Price: {row[3]}\n")
                else:
                    f.write("  ✗ Record not found!\n")
                
                # Clean up
                f.write("\nStep 4: Cleaning up test data...\n")
                await conn.execute(text("DELETE FROM positions WHERE id = :id"), {'id': test_position_id})
                f.write("  ✓ Test position deleted\n")
                
                f.write("\n" + "="*50 + "\n")
                f.write("✓✓✓ SUPABASE CONNECTION SUCCESSFUL ✓✓✓\n")
                f.write("="*50 + "\n")
                
        except Exception as e:
            f.write(f"\n✗✗✗ CONNECTION FAILED ✗✗✗\n")
            f.write(f"Error: {e}\n")

if __name__ == "__main__":
    asyncio.run(test_connection())
