from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.alert_service import AlertService

router = APIRouter()

class TestAlertRequest(BaseModel):
    phone_number: str  # Format: +919876543210

@router.post("/test")
async def send_test_alert(request: TestAlertRequest):
    """
    Send test WhatsApp alert to verify configuration.
    
    Phone number format: +919876543210 (country code required)
    """
    alert_service = AlertService()
    
    success = await alert_service.send_test_alert(request.phone_number)
    
    if success:
        return {
            "success": True,
            "message": f"Test alert sent to {request.phone_number}"
        }
    else:
        raise HTTPException(500, "Failed to send alert. Check logs.")
