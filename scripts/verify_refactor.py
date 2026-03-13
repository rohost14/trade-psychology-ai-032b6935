
import asyncio
import uuid
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.services.danger_zone_service import danger_zone_service
from app.services.cooldown_service import cooldown_service
from app.services.notification_rate_limiter import notification_rate_limiter, NotificationType

async def verify():
    print("Verifying Refactor...")
    
    # Generate a fake UUID
    broker_account_id = uuid.uuid4()
    account_id_str = str(broker_account_id)
    print(f"Testing with Account ID: {account_id_str}")

    try:
        # Test Notification Rate Limiter
        print("\n1. Testing Notification Rate Limiter...")
        can_send, reason = notification_rate_limiter.can_send(account_id_str, NotificationType.TILT_DETECTED)
        print(f"   Can send TILT_DETECTED? {can_send}")
        
        notification_rate_limiter.record_sent(account_id_str, NotificationType.TILT_DETECTED)
        print("   Recorded sent.")
        
        stats = notification_rate_limiter.get_notification_stats(account_id_str)
        print(f"   Stats: {stats['total_24h']} sent in 24h")
        assert stats['total_24h'] >= 1
        
        # Test Cooldown Service (Internal methods that don't need DB)
        print("\n2. Testing Cooldown Service (Internal calc)...")
        # We can't easily test DB methods without a real DB session, but we can test helper methods
        duration = cooldown_service._calculate_duration(account_id_str, "tilt")
        print(f"   Calculated duration for 'tilt': {duration} min")
        
        level = cooldown_service._get_escalation_level(account_id_str, "tilt")
        print(f"   Escalation level: {level}")
        
        cooldown_service._record_violation(account_id_str, "tilt")
        level_after = cooldown_service._get_escalation_level(account_id_str, "tilt")
        print(f"   Escalation level after violation: {level_after}")
        assert level_after > level

        print("\n✅ Verification Successful: Services accept UUID strings!")

    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(verify())
