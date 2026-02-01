from datetime import datetime
import uuid
import logging
from typing import Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from cryptography.fernet import Fernet
from app.core.config import settings

logger = logging.getLogger(__name__)

from app.schemas.broker import BrokerConnectRequest, BrokerAccountResponse, BrokerStatusResponse, DisconnectRequest
from app.services.zerodha_service import zerodha_client
from app.models.broker_account import BrokerAccount
from app.core.database import get_db
from app.api.deps import get_current_user
from app.core.config import settings

router = APIRouter()

@router.get("/connect")
async def connect_zerodha(
    redirect_uri: str,
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Generate Zerodha login URL."""
    # State can be user_id or "anonymous"
    state = user_id if user_id else "anonymous"
    login_url = zerodha_client.generate_login_url(redirect_uri, state=state)
    return {"login_url": login_url}

@router.get("/callback")
async def zerodha_callback(
    request_token: str,
    status: str,
    state: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Handle Zerodha callback."""
    if status != "success":
        return {"success": False, "error": "OAuth failed or cancelled"}
    
    try:
        # 1. Exchange token
        token_data = await zerodha_client.exchange_token(request_token)
        access_token = token_data.get("access_token")
        
        if not access_token:
            return {"success": False, "error": "No access token received"}
        
        # 2. Get Zerodha profile
        profile = await zerodha_client.get_profile(access_token)
        zerodha_user_id = profile.get("user_id")
        zerodha_email = profile.get("email")
        
        logger.info(f"OAuth success for Zerodha user: {zerodha_user_id}")
        
        # 3. Check if this Zerodha user already has a broker_account
        result = await db.execute(
            select(BrokerAccount).where(
                BrokerAccount.broker_name == "zerodha",
                BrokerAccount.broker_user_id == zerodha_user_id
            )
        )
        existing_account = result.scalars().first()
        
        # 4. Encrypt token (using current model method, not direct import to avoid circular dependency if possible, 
        #    but the user code prompt suggested import. BrokerAccount model has encrypt_token method based on previous view_file).
        #    Wait, I see `account.encrypt_token` in existing code. Let's stick to that or use the utility if needed.
        #    The user provided code imports `encrypt_token` from `app.core.security`.
        #    Let's check if we can use the model method which is cleaner.
        #    Existing code uses `broker_account.encrypt_token(access_token)`. I will use that for consistency.
        
        # NOTE: The User provided a snippet using standalone encrypt_token. 
        # I will respect the user's logic content but adapt to the existing codebase structure which implies 
        # usage of `account.encrypt_token` OR `BrokerAccount` static/instance methods if available.
        # However, looking at lines 44-45 in previous view_file, `broker_account` instance has `encrypt_token`.
        # To avoid creating a dummy instance just to encrypt, I'll need `encrypt_token` from security.
        # Let's import it inside the function to be safe or use what's available.
        # Actually, let's look at `app.core.security`.
        # Safe bet: Update the existing account or create new, then set attributes.
        
        if existing_account:
            # UPDATE existing account
            logger.info(f"Updating existing broker_account: {existing_account.id}")
            
            existing_account.access_token = existing_account.encrypt_token(access_token)
            existing_account.status = "connected"
            existing_account.connected_at = datetime.utcnow()
            existing_account.broker_email = zerodha_email
            existing_account.updated_at = datetime.utcnow()
            
            # Ensure api_key is up to date
            existing_account.api_key = zerodha_client.api_key
            
            await db.commit()
            await db.refresh(existing_account)

            # Redirect to frontend with success and broker_account_id
            frontend_url = settings.BACKEND_CORS_ORIGINS[0] if settings.BACKEND_CORS_ORIGINS else "http://localhost:8080"
            return RedirectResponse(
                url=f"{frontend_url}/settings?connected=true&broker_account_id={existing_account.id}",
                status_code=302
            )

        else:
            # CREATE new account
            logger.info(f"Creating new broker_account for Zerodha user: {zerodha_user_id}")
            
            internal_user_id = None
            if state and state != "anonymous":
                try:
                    internal_user_id = uuid.UUID(state)
                except ValueError:
                    pass
            
            # We need an instance to encrypt if we use the model method, or we use the helper.
            # We need an instance to encrypt if we use the model method, or we use the helper.
            # Use inline encryption
            f = Fernet(settings.ENCRYPTION_KEY.encode())
            encrypted_token = f.encrypt(access_token.encode()).decode()

            broker_account = BrokerAccount(
                user_id=internal_user_id,
                broker_name="zerodha",
                access_token=encrypted_token,
                api_key=zerodha_client.api_key,
                status="connected",
                connected_at=datetime.utcnow(),
                broker_user_id=zerodha_user_id,
                broker_email=zerodha_email
            )
            
            db.add(broker_account)
            await db.commit()
            await db.refresh(broker_account)

            # Redirect to frontend with success and broker_account_id
            frontend_url = settings.BACKEND_CORS_ORIGINS[0] if settings.BACKEND_CORS_ORIGINS else "http://localhost:8080"
            return RedirectResponse(
                url=f"{frontend_url}/settings?connected=true&broker_account_id={broker_account.id}",
                status_code=302
            )
    
    except Exception as e:
        logger.error(f"OAuth callback error: {e}", exc_info=True)
        # Redirect to frontend with error
        frontend_url = settings.BACKEND_CORS_ORIGINS[0] if settings.BACKEND_CORS_ORIGINS else "http://localhost:8080"
        return RedirectResponse(url=f"{frontend_url}/settings?error={str(e)}", status_code=302)

@router.get("/status", response_model=BrokerStatusResponse)
async def get_broker_status(
    broker_account_id: str,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get connection status."""
    try:
        account_id = uuid.UUID(broker_account_id)
        result = await db.execute(
            select(BrokerAccount).where(BrokerAccount.id == account_id)
        )
        account = result.scalars().first()
        
        if not account or account.status != "connected":
            return BrokerStatusResponse(
                connected=False,
                broker_name="zerodha",
                broker_user_id=None,
                last_sync=None,
                guardian_name=None,
                guardian_phone=None
            )
            
        return BrokerStatusResponse(
            connected=True,
            broker_name=account.broker_name,
            broker_user_id=account.broker_user_id,
            last_sync=account.last_sync_at,
            guardian_name=account.guardian_name,
            guardian_phone=account.guardian_phone
        )
    except Exception as e:
        logger.error(f"Error fetching broker status: {e}")
        return BrokerStatusResponse(
            connected=False,
            broker_name="zerodha",
            broker_user_id=None,
            last_sync=None,
            guardian_name=None,
            guardian_phone=None
        )

@router.post("/disconnect")
async def disconnect_broker(
    request: DisconnectRequest,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Disconnect broker."""
    try:
        account_id = uuid.UUID(request.broker_account_id)
        result = await db.execute(
            select(BrokerAccount).where(BrokerAccount.id == account_id)
        )
        account = result.scalars().first()
        
        if not account:
            raise HTTPException(status_code=404, detail="No broker account found")
            
        if account.status == "connected" and account.access_token:
            try:
                # Decrypt
                decrypted_token = account.decrypt_token(account.access_token)
                # Revoke
                await zerodha_client.revoke_token(decrypted_token)
            except Exception as e:
                logger.error(f"Revoke error: {e}")
                # Continue to mark disconnected locally
                
        account.status = "disconnected"
        account.access_token = None
        account.refresh_token = None
        account.updated_at = datetime.now()
        
        await db.commit()
        
        return {"success": True}
    except Exception as e:
        logger.error(f"Error disconnecting broker: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/accounts")
async def list_broker_accounts(
    db: AsyncSession = Depends(get_db)
) -> Any:
    """List all connected broker accounts."""
    result = await db.execute(
        select(BrokerAccount).where(BrokerAccount.status == "connected")
    )
    accounts = result.scalars().all()

    return {
        "accounts": [
            {
                "id": str(account.id),
                "broker_name": account.broker_name,
                "broker_user_id": account.broker_user_id,
                "broker_email": account.broker_email,
                "status": account.status,
                "connected_at": account.connected_at.isoformat() if account.connected_at else None,
                "last_sync_at": account.last_sync_at.isoformat() if account.last_sync_at else None,
            }
            for account in accounts
        ]
    }

@router.get("/test")
async def test_zerodha_config() -> Any:
    """Test endpoint to verify config."""
    key = settings.ZERODHA_API_KEY
    if not key:
        return {"api_key": None, "configured": False}
    masked = key[:8] + "*" * (len(key) - 8) if len(key) > 8 else key
    return {"api_key": masked, "configured": True}
