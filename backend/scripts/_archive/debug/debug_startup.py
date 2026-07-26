import sys
import os
import asyncio
# Add backend dir to sys.path
sys.path.append(os.getcwd())

async def test_startup():
    print("Attempting to import app.main...")
    try:
        from app.main import app
        print("Import successful!")
        
        print("Attempting to run lifespan startup...")
        # Simulate startup
        async with app.router.lifespan_context(app):
            print("Lifespan startup complete!")
            
    except Exception as e:
        print("\nCRASH DETECTED:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_startup())
