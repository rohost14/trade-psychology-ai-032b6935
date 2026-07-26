import asyncio
import httpx
from app.core.config import settings

async def check_api():
    print(f"Checking Supabase API at: {settings.SUPABASE_URL}")
    
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        print("❌ Supabase URL or Service Key not set in .env")
        return

    url = f"{settings.SUPABASE_URL}/auth/v1/health"
    headers = {
        "apikey": settings.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 200:
                print("✅ Supabase API connection SUCCESSFUL")
            else:
                print("⚠️  Supabase API connection returned unexpected status")

    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(check_api())
