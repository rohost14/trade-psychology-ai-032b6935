from datetime import datetime, timedelta, timezone
import asyncio
import uuid
import logging
import json
import base64
import urllib.parse
from typing import Any, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from cryptography.fernet import Fernet
from app.core.config import settings

logger = logging.getLogger(__name__)

from app.schemas.broker import BrokerAccountResponse, BrokerStatusResponse
from app.services.zerodha_service import zerodha_client, KiteTokenExpiredError, KiteAPIError
from app.services.margin_service import margin_service
from app.services.order_analytics_service import order_analytics_service
from app.services.instrument_service import instrument_service
from app.services.trade_sync_service import TradeSyncService
from app.services.price_stream_service import price_stream
from app.services.token_manager import token_manager
from app.models.user import User
from app.models.broker_account import BrokerAccount
from app.models.trade import Trade
from app.core.database import get_db
from app.core.logging_config import metrics
from app.api.deps import get_verified_broker_account_id, create_access_token
from app.core.rate_limiter import sync_limiter

router = APIRouter()

# Sync lock to prevent concurrent sync calls per account
_sync_locks: dict[str, asyncio.Lock] = {}
_sync_locks_lock = asyncio.Lock()

async def _get_sync_lock(account_id: str) -> asyncio.Lock:
    """Get or create a per-account sync lock."""
    async with _sync_locks_lock:
        if account_id not in _sync_locks:
            _sync_locks[account_id] = asyncio.Lock()
        return _sync_locks[account_id]


# =============================================================================
# PUBLIC ENDPOINTS (no auth required)
# =============================================================================

@router.get("/connect")
async def connect_zerodha(
    redirect_uri: Optional[str] = None,
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Generate Zerodha login URL."""
    callback_uri = settings.ZERODHA_REDIRECT_URI or "http://localhost:8000/api/zerodha/callback"
    state = user_id if user_id else "anonymous"
    login_url = zerodha_client.generate_login_url(callback_uri, state=state)
    return {"login_url": login_url}

@router.get("/callback")
async def zerodha_callback(
    request_token: str,
    status: str,
    state: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Handle Zerodha OAuth callback. Issues JWT on success."""
    frontend_url = settings.FRONTEND_URL

    if status != "success":
        return RedirectResponse(url=f"{frontend_url}/settings?error=OAuth+failed+or+cancelled", status_code=302)

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
        zerodha_name = profile.get("user_name") or profile.get("user_shortname")
        zerodha_avatar = profile.get("avatar_url")

        logger.info(f"OAuth success for Zerodha user: {zerodha_user_id}")

        # 3. Find or create the User row (stable identity keyed by email)
        user_result = await db.execute(
            select(User).where(User.email == zerodha_email)
        )
        user = user_result.scalar_one_or_none()

        if user:
            # Update profile fields that may have changed
            user.display_name = user.display_name or zerodha_name
            user.avatar_url = user.avatar_url or zerodha_avatar
            user.updated_at = datetime.now(timezone.utc)
            logger.info(f"Found existing user: {user.id}")
        else:
            user = User(
                email=zerodha_email,
                display_name=zerodha_name,
                avatar_url=zerodha_avatar,
            )
            db.add(user)
            await db.flush()  # get user.id before linking broker_account
            logger.info(f"Created new user: {user.id}")

        # 4. Check if this Zerodha user already has a broker_account
        result = await db.execute(
            select(BrokerAccount).where(
                BrokerAccount.broker_name == "zerodha",
                BrokerAccount.broker_user_id == zerodha_user_id
            )
        )
        existing_account = result.scalars().first()

        if existing_account:
            # UPDATE existing account — also re-link to user in case of reconnect
            logger.info(f"Updating existing broker_account: {existing_account.id}")

            existing_account.user_id = user.id
            existing_account.access_token = existing_account.encrypt_token(access_token)
            existing_account.status = "connected"
            existing_account.token_revoked_at = None
            existing_account.connected_at = datetime.now(timezone.utc)
            existing_account.broker_email = zerodha_email
            existing_account.updated_at = datetime.now(timezone.utc)

            existing_account.user_type = profile.get("user_type")
            existing_account.exchanges = profile.get("exchanges", [])
            existing_account.products = profile.get("products", [])
            existing_account.order_types = profile.get("order_types", [])
            existing_account.avatar_url = zerodha_avatar
            existing_account.sync_status = "pending"
            existing_account.api_key = zerodha_client.api_key

            await db.commit()
            await db.refresh(existing_account)

            jwt_token = create_access_token(
                user_id=user.id,
                broker_account_id=existing_account.id
            )

            return RedirectResponse(
                url=f"{frontend_url}/settings?connected=true&token={jwt_token}&broker_account_id={existing_account.id}",
                status_code=302
            )

        else:
            # CREATE new broker_account linked to the user
            logger.info(f"Creating new broker_account for Zerodha user: {zerodha_user_id}")

            f = Fernet(settings.ENCRYPTION_KEY.encode())
            encrypted_token = f.encrypt(access_token.encode()).decode()

            broker_account = BrokerAccount(
                user_id=user.id,
                broker_name="zerodha",
                access_token=encrypted_token,
                api_key=zerodha_client.api_key,
                status="connected",
                connected_at=datetime.now(timezone.utc),
                broker_user_id=zerodha_user_id,
                broker_email=zerodha_email,
                user_type=profile.get("user_type"),
                exchanges=profile.get("exchanges", []),
                products=profile.get("products", []),
                order_types=profile.get("order_types", []),
                avatar_url=zerodha_avatar,
                sync_status="pending"
            )

            db.add(broker_account)
            await db.commit()
            await db.refresh(broker_account)

            jwt_token = create_access_token(
                user_id=user.id,
                broker_account_id=broker_account.id
            )

            return RedirectResponse(
                url=f"{frontend_url}/settings?connected=true&token={jwt_token}&broker_account_id={broker_account.id}",
                status_code=302
            )

    except Exception as e:
        logger.error(f"OAuth callback error: {e}", exc_info=True)
        error_msg = urllib.parse.quote(str(e))
        return RedirectResponse(url=f"{frontend_url}/settings?error={error_msg}", status_code=302)

@router.get("/test")
async def test_zerodha_config() -> Any:
    """Test endpoint to verify config."""
    key = settings.ZERODHA_API_KEY
    if not key:
        return {"api_key": None, "configured": False}
    masked = key[:8] + "*" * (len(key) - 8) if len(key) > 8 else key
    return {"api_key": masked, "configured": True}

@router.get("/metrics")
async def get_metrics() -> Any:
    """Get API metrics for monitoring."""
    return metrics.get_metrics()

@router.post("/metrics/reset")
async def reset_metrics() -> Any:
    """Reset all metrics."""
    metrics.reset()
    return {"success": True, "message": "Metrics reset"}

@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Health check endpoint."""
    health = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {}
    }

    try:
        await db.execute("SELECT 1")
        health["components"]["database"] = {"status": "healthy"}
    except Exception as e:
        health["status"] = "unhealthy"
        health["components"]["database"] = {"status": "unhealthy", "error": str(e)}

    try:
        if settings.ZERODHA_API_KEY:
            health["components"]["zerodha_config"] = {"status": "configured"}
        else:
            health["components"]["zerodha_config"] = {"status": "not_configured"}
    except Exception as e:
        health["components"]["zerodha_config"] = {"status": "error", "error": str(e)}

    return health


# =============================================================================
# PROTECTED ENDPOINTS (JWT required)
# =============================================================================

@router.get("/status", response_model=BrokerStatusResponse)
async def get_broker_status(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get connection status."""
    try:
        result = await db.execute(
            select(BrokerAccount).where(BrokerAccount.id == broker_account_id)
        )
        account = result.scalars().first()

        if not account or account.status != "connected":
            return BrokerStatusResponse(
                connected=False,
                broker_name="zerodha",
            )

        # Load user for guardian info
        user = await db.get(User, account.user_id) if account.user_id else None

        return BrokerStatusResponse(
            connected=True,
            broker_name=account.broker_name,
            broker_user_id=account.broker_user_id,
            last_sync=account.last_sync_at,
            guardian_name=user.guardian_name if user else None,
            guardian_phone=user.guardian_phone if user else None,
        )
    except Exception as e:
        logger.error(f"Error fetching broker status: {e}")
        return BrokerStatusResponse(
            connected=False,
            broker_name="zerodha",
        )

@router.post("/disconnect")
async def disconnect_broker(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Disconnect broker."""
    try:
        result = await db.execute(
            select(BrokerAccount).where(BrokerAccount.id == broker_account_id)
        )
        account = result.scalars().first()

        if not account:
            raise HTTPException(status_code=404, detail="No broker account found")

        if account.status == "connected" and account.access_token:
            try:
                decrypted_token = account.decrypt_token(account.access_token)
                await zerodha_client.revoke_token(decrypted_token)
            except Exception as e:
                logger.error(f"Revoke error: {e}")

        account.status = "disconnected"
        account.access_token = None
        account.refresh_token = None
        account.token_revoked_at = datetime.now(timezone.utc)
        account.updated_at = datetime.now(timezone.utc)

        await db.commit()

        # Stop KiteTicker for this account — token is now invalid
        try:
            from app.services.price_stream_service import price_stream
            await price_stream.stop_account(broker_account_id)
        except Exception as e:
            logger.error(f"Failed to stop price stream on disconnect: {e}")

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disconnecting broker: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/accounts")
async def list_broker_accounts(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """List broker accounts for the authenticated user."""
    result = await db.execute(
        select(BrokerAccount).where(BrokerAccount.id == broker_account_id)
    )
    account = result.scalars().first()

    if not account:
        return {"accounts": []}

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
        ]
    }


# =============================================================================
# MARGINS, HOLDINGS, ORDER ANALYTICS (protected)
# =============================================================================

@router.get("/margins")
async def get_margins(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get account margin status and utilization."""
    try:
        result = await margin_service.get_margin_status(broker_account_id, db)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching margins: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/holdings")
async def get_holdings(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get equity holdings (CNC/delivery)."""
    try:
        account = await db.get(BrokerAccount, broker_account_id)

        if not account or not account.access_token:
            raise HTTPException(status_code=404, detail="Broker account not connected")

        access_token = account.decrypt_token(account.access_token)
        holdings = await zerodha_client.get_holdings(access_token)

        return {"holdings": holdings, "count": len(holdings)}

    except KiteTokenExpiredError:
        raise HTTPException(status_code=401, detail="Token expired. Please reconnect.")
    except KiteAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching holdings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/order-analytics")
async def get_order_analytics(
    days: int = 30,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get order analytics and behavioral insights."""
    try:
        result = await order_analytics_service.get_order_patterns(broker_account_id, db, days)
        return result

    except Exception as e:
        logger.error(f"Error getting order analytics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/instruments/refresh")
async def refresh_instruments(
    exchanges: Optional[str] = None,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Refresh instrument master cache."""
    try:
        exchange_list = None
        if exchanges:
            exchange_list = [e.strip().upper() for e in exchanges.split(",")]

        result = await instrument_service.refresh_instruments(db, exchange_list)
        return result

    except Exception as e:
        logger.error(f"Error refreshing instruments: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/instruments/search")
async def search_instruments(
    query: str,
    exchange: Optional[str] = None,
    limit: int = 20,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Search instruments by symbol or name."""
    try:
        instruments = await instrument_service.search_instruments(
            query, exchange, limit, db
        )

        return {
            "results": [
                {
                    "instrument_token": inst.instrument_token,
                    "tradingsymbol": inst.tradingsymbol,
                    "name": inst.name,
                    "exchange": inst.exchange,
                    "instrument_type": inst.instrument_type,
                    "lot_size": inst.lot_size,
                    "expiry": inst.expiry.isoformat() if inst.expiry else None,
                    "strike": float(inst.strike) if inst.strike else None
                }
                for inst in instruments
            ],
            "count": len(instruments)
        }

    except Exception as e:
        logger.error(f"Error searching instruments: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/orders/history/{order_id}")
async def get_order_history(
    order_id: str,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get history of a specific order."""
    try:
        account = await db.get(BrokerAccount, broker_account_id)

        if not account or not account.access_token:
            raise HTTPException(status_code=404, detail="Broker account not connected")

        access_token = account.decrypt_token(account.access_token)
        history = await zerodha_client.get_order_history(access_token, order_id)

        return {"order_id": order_id, "history": history}

    except KiteTokenExpiredError:
        raise HTTPException(status_code=401, detail="Token expired. Please reconnect.")
    except KiteAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching order history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# SYNC ENDPOINTS (protected)
# =============================================================================

@router.post("/sync/orders")
async def sync_orders(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Sync all orders to the orders table."""
    try:
        result = await TradeSyncService.sync_orders_to_db(broker_account_id, db)

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing orders: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sync/holdings")
async def sync_holdings(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Sync CNC/delivery holdings to the holdings table."""
    try:
        result = await TradeSyncService.sync_holdings(broker_account_id, db)

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing holdings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/sync/all")
async def sync_all_data(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(sync_limiter)
) -> Any:
    """Sync all data: trades, positions, orders, and holdings."""
    account_id_str = str(broker_account_id)
    lock = await _get_sync_lock(account_id_str)

    # If another sync is already running for this account, return immediately
    if lock.locked():
        return {
            "success": True,
            "message": "Sync already in progress",
            "results": {}
        }

    async with lock:
        try:
            account = await db.get(BrokerAccount, broker_account_id)
            if account:
                account.sync_status = "syncing"
                await db.commit()

            results = {}

            trade_result = await TradeSyncService.sync_trades_for_broker_account(broker_account_id, db)
            results["trades"] = trade_result

            orders_result = await TradeSyncService.sync_orders_to_db(broker_account_id, db)
            results["orders"] = orders_result

            # Holdings sync skipped — user trades MIS/NRML/MTF only.
            # sync_holdings() method preserved for future use if needed.

            # ==========================================
            # SIGNAL PIPELINE — runs AFTER data pipeline
            # ==========================================

            # Load user profile once — passed to all detectors for threshold calibration
            from app.models.user_profile import UserProfile as _UserProfile
            _profile_result = await db.execute(
                select(_UserProfile).where(_UserProfile.broker_account_id == broker_account_id)
            )
            _trader_profile = _profile_result.scalar_one_or_none()

            # 1. Legacy risk detection (feeds risk_alerts for existing frontend)
            try:
                from app.services.risk_detector import RiskDetector
                from app.models.risk_alert import RiskAlert
                from sqlalchemy import and_

                risk_detector = RiskDetector()
                alerts = await risk_detector.detect_patterns(broker_account_id, db, profile=_trader_profile)

                cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
                existing_result = await db.execute(
                    select(RiskAlert).where(
                        and_(
                            RiskAlert.broker_account_id == broker_account_id,
                            RiskAlert.detected_at >= cutoff_24h
                        )
                    )
                )
                existing_keys = set()
                for ea in existing_result.scalars().all():
                    if ea.trigger_trade_id:
                        existing_keys.add((str(ea.trigger_trade_id), ea.pattern_type))
                    else:
                        # Account-level alerts (no trigger trade) — dedup by type
                        existing_keys.add(("_account_", ea.pattern_type))

                added_count = 0
                new_sync_alerts = []
                for alert in alerts:
                    if alert.trigger_trade_id:
                        key = (str(alert.trigger_trade_id), alert.pattern_type)
                    else:
                        key = ("_account_", alert.pattern_type)
                    if key in existing_keys:
                        continue
                    db.add(alert)
                    new_sync_alerts.append(alert)
                    existing_keys.add(key)
                    added_count += 1

                if added_count > 0:
                    await db.commit()
                results["risk_alerts"] = added_count

                # Trigger AlertCheckpoint for newly-added danger/critical alerts
                from app.tasks.checkpoint_tasks import create_alert_checkpoint
                for alert in new_sync_alerts:
                    if alert.severity in ("danger", "critical"):
                        create_alert_checkpoint.apply_async(
                            args=[str(alert.id), str(broker_account_id)],
                            countdown=10,
                        )
            except Exception as e:
                logger.error(f"Legacy risk detection failed (non-fatal): {e}")
                results["risk_detection_error"] = str(e)

            # 2. BehavioralEvaluator — new signal pipeline with confidence scoring
            try:
                from app.services.behavioral_evaluator import BehavioralEvaluator

                evaluator = BehavioralEvaluator()

                # Get fills from this sync cycle (new trades synced above)
                new_fill_ids = trade_result.get("new_trade_ids", [])
                new_fills = []
                if new_fill_ids:
                    fill_result = await db.execute(
                        select(Trade).where(Trade.id.in_(new_fill_ids))
                    )
                    new_fills = fill_result.scalars().all()

                if new_fills:
                    events = await evaluator.evaluate(broker_account_id, new_fills, db, profile=_trader_profile)

                    # Persist events (only after confidence validation + dedup)
                    for event in events:
                        db.add(event)

                    if events:
                        await db.commit()

                        # Push to WebSocket (only after DB insert)
                        try:
                            from app.api.websocket import manager
                            for event in events:
                                await manager.push_behavioral_event(
                                    str(broker_account_id), event
                                )
                        except Exception as ws_err:
                            logger.warning(f"WebSocket push failed (non-fatal): {ws_err}")

                    results["behavioral_events"] = len(events)
                else:
                    results["behavioral_events"] = 0

            except Exception as e:
                logger.error(f"Behavioral evaluation failed (non-fatal): {e}")
                results["behavioral_events_error"] = str(e)

            # 3. DangerZone assessment — uses CompletedTrade P&L to detect danger
            try:
                from app.services.danger_zone_service import danger_zone_service

                dz_status = await danger_zone_service.assess_danger_level(db, broker_account_id)
                results["danger_zone"] = {
                    "level": dz_status.level.value,
                    "triggers": dz_status.triggers,
                    "consecutive_losses": dz_status.consecutive_losses,
                    "daily_loss_used_percent": dz_status.daily_loss_used_percent,
                    "message": dz_status.message,
                }

                # If danger or critical, trigger intervention (cooldown + WhatsApp)
                if dz_status.level.value in ("danger", "critical"):
                    actions = await danger_zone_service.trigger_intervention(
                        db, broker_account_id, dz_status
                    )
                    results["danger_zone"]["actions"] = actions
                    logger.warning(
                        f"DangerZone {dz_status.level.value} for {broker_account_id}: "
                        f"triggers={dz_status.triggers}, actions={actions}"
                    )

            except Exception as e:
                logger.error(f"DangerZone assessment failed (non-fatal): {e}")
                results["danger_zone_error"] = str(e)

            # 4. Behavioral baseline — recomputes personalized thresholds from 90-day history.
            # Skipped automatically if last recompute < 24h ago (see RECOMPUTE_INTERVAL_HOURS).
            # Non-fatal: sync still succeeds even if baseline computation fails.
            try:
                from app.services.behavioral_baseline_service import behavioral_baseline_service

                baseline = await behavioral_baseline_service.compute_and_store(
                    db=db,
                    broker_account_id=broker_account_id,
                )
                results["baseline_updated"] = baseline is not None
                if baseline:
                    results["baseline_sessions"] = baseline.get("session_count", 0)
            except Exception as e:
                logger.error(f"Baseline computation failed (non-fatal): {e}")
                results["baseline_error"] = str(e)

            if account:
                account.sync_status = "complete"
                account.last_sync_at = datetime.now(timezone.utc)
                await db.commit()

            return {
                "success": True,
                "results": results
            }

        except Exception as e:
            logger.error(f"Error in full sync: {e}")
            try:
                account = await db.get(BrokerAccount, broker_account_id)
                if account:
                    account.sync_status = "error"
                    await db.commit()
            except:
                pass
            raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# PRICE STREAMING (protected)
# =============================================================================

@router.post("/stream/start")
async def start_stream(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Start real-time price streaming for account positions."""
    try:
        await price_stream.start_account(broker_account_id, db)

        return {
            "success": True,
            "message": "Price stream started. Connect to WebSocket for updates."
        }

    except Exception as e:
        logger.error(f"Error starting price stream: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/stream/stop")
async def stop_stream(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Stop real-time price streaming for account."""
    try:
        account = await db.get(BrokerAccount, broker_account_id)

        if not account or not account.access_token:
            raise HTTPException(status_code=404, detail="Broker account not connected")

        await price_stream.stop_account(broker_account_id)

        return {"success": True, "message": "Price stream stopped."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping price stream: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# MARGIN CHECK (protected)
# =============================================================================

@router.post("/margins/check-order")
async def check_margin_for_order(
    estimated_margin: float,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Pre-trade margin check."""
    try:
        result = await margin_service.check_margin_for_order(
            broker_account_id, db, estimated_margin
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking margin: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/margins/insights")
async def get_margin_insights(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get margin insights and recommendations."""
    try:
        result = await margin_service.get_margin_history_insight(broker_account_id, db)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting margin insights: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# TOKEN MANAGEMENT (protected)
# =============================================================================

@router.get("/token/validate")
async def validate_token(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Check if broker access token is still valid."""
    try:
        result = await token_manager.check_token_validity(broker_account_id, db)
        return result

    except Exception as e:
        logger.error(f"Error validating token: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/token/status")
async def get_all_token_status(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get token status for all connected accounts."""
    try:
        result = await token_manager.validate_all_tokens(db)
        return result

    except Exception as e:
        logger.error(f"Error getting token status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/accounts/needing-reauth")
async def get_accounts_needing_reauth(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """Get list of accounts that need re-authentication."""
    try:
        accounts = await token_manager.get_accounts_needing_reauth(db)
        return {
            "count": len(accounts),
            "accounts": accounts
        }

    except Exception as e:
        logger.error(f"Error getting accounts needing reauth: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
