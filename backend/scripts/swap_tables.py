import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)

async def swap_tables():
    with open('swap_results.txt', 'w', encoding='utf-8') as f:
        try:
            async with engine.begin() as conn:
                f.write("Swapping positions tables...\n\n")
                
                # Step 1: Rename positions -> positions_backup  
                f.write("Step 1: Renaming 'positions' to 'positions_backup'...\n")
                await conn.execute(text("ALTER TABLE positions RENAME TO positions_backup"))
                f.write("  ✓ Done\n\n")
                
                # Step 2: Rename positions_history -> positions
                f.write("Step 2: Renaming 'positions_history' to 'positions'...\n")
                await conn.execute(text("ALTER TABLE positions_history RENAME TO positions"))
                f.write("  ✓ Done\n\n")
                
                f.write("="*50 + "\n")
                f.write("✓✓✓ TABLE SWAP SUCCESSFUL ✓✓✓\n")
                f.write("="*50 + "\n")
                f.write("\nThe table 'positions' now has the correct schema!\n")
                
        except Exception as e:
            f.write(f"\n✗✗✗ SWAP FAILED ✗✗✗\n")
            f.write(f"Error: {e}\n")

if __name__ == "__main__":
    asyncio.run(swap_tables())
