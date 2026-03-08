from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from uuid import UUID

from app.api.deps import get_verified_broker_account_id
from app.services.alert_service import AlertService

router = APIRouter()

class TestAlertRequest(BaseModel):
    phone_number: str  # Format: +919876543210

@router.post("/test")
async def send_test_alert(
    request: TestAlertRequest,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
):
    """
    Send test WhatsApp alert to verify configuration.

    Phone number format: +919876543210 (country code required)
    Requires authentication.
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
