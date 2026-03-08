"""
Token Manager Service

Handles broker token lifecycle:
- Token validation
- Expiry detection
- User notification for re-authentication
- Session cleanup

Note: Kite tokens cannot be auto-refreshed. They expire at ~7:30 AM next day.
User must re-login via OAuth to get a new token.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.broker_account import BrokerAccount
from app.services.zerodha_service import zerodha_client, KiteTokenExpiredError, KiteAPIError

logger = logging.getLogger(__name__)


class TokenManager:
    """
    Manages broker access tokens.

    Kite Token Lifecycle:
    - Token issued after OAuth login
    - Valid until ~7:30 AM next trading day
    - Cannot be refreshed programmatically
    - Must re-authenticate via OAuth when expired
    """

    # Cache of last known token status
    _token_status_cache: Dict[str, Dict] = {}

    async def check_token_validity(
        self,
        broker_account_id: UUID,
        db: AsyncSession
    ) -> Dict:
        """
        Check if the access token is still valid.

        Returns:
            Dict with validity status and details
        """
        account = await db.get(BrokerAccount, broker_account_id)

        if not account:
            return {"valid": False, "error": "Account not found"}

        if not account.access_token:
            return {"valid": False, "error": "No access token", "needs_login": True}

        if account.status != "connected":
            return {"valid": False, "error": "Account not connected", "needs_login": True}

        try:
            # Try a lightweight API call to verify token
            access_token = account.decrypt_token(account.access_token)
            profile = await zerodha_client.get_profile(access_token)

            # Token is valid
            self._token_status_cache[str(broker_account_id)] = {
                "valid": True,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "user_id": profile.get("user_id")
            }

            return {
                "valid": True,
                "broker_user_id": profile.get("user_id"),
                "email": profile.get("email")
            }

        except KiteTokenExpiredError:
            # Token has expired
            logger.warning(f"Token expired for account {broker_account_id}")
            await self._mark_token_expired(broker_account_id, db)

            return {
                "valid": False,
                "error": "Token expired",
                "needs_login": True,
                "message": "Your Zerodha session has expired. Please reconnect."
            }

        except KiteAPIError as e:
            logger.error(f"API error checking token: {e}")
            return {
                "valid": False,
                "error": str(e),
                "needs_login": "InvalidToken" in str(e) or "token" in str(e).lower()
            }

        except Exception as e:
            logger.error(f"Error checking token validity: {e}")
            return {"valid": False, "error": str(e)}

    async def _mark_token_expired(
        self,
        broker_account_id: UUID,
        db: AsyncSession
    ):
        """Mark account as needing re-authentication."""
        await db.execute(
            update(BrokerAccount)
            .where(BrokerAccount.id == broker_account_id)
            .values(
                status="token_expired",
                sync_status="error",
                updated_at=datetime.now(timezone.utc)
            )
        )
        await db.commit()

        # Clear cache
        self._token_status_cache.pop(str(broker_account_id), None)

    async def get_accounts_needing_reauth(
        self,
        db: AsyncSession
    ) -> List[Dict]:
        """
        Get all accounts that need re-authentication.

        Returns list of accounts with expired tokens.
        """
        result = await db.execute(
            select(BrokerAccount).where(
                BrokerAccount.status.in_(["token_expired", "disconnected"])
            )
        )
        accounts = result.scalars().all()

        return [
            {
                "broker_account_id": str(acc.id),
                "broker_name": acc.broker_name,
                "broker_user_id": acc.broker_user_id,
                "broker_email": acc.broker_email,
                "status": acc.status,
                "last_connected": acc.connected_at.isoformat() if acc.connected_at else None
            }
            for acc in accounts
        ]

    async def validate_all_tokens(
        self,
        db: AsyncSession
    ) -> Dict:
        """
        Validate tokens for all connected accounts.

        Useful for scheduled health checks.
        """
        result = await db.execute(
            select(BrokerAccount).where(BrokerAccount.status == "connected")
        )
        accounts = result.scalars().all()

        results = {
            "total": len(accounts),
            "valid": 0,
            "expired": 0,
            "errors": 0,
            "details": []
        }

        for account in accounts:
            status = await self.check_token_validity(account.id, db)

            detail = {
                "broker_account_id": str(account.id),
                "broker_user_id": account.broker_user_id,
                "valid": status.get("valid", False)
            }

            if status.get("valid"):
                results["valid"] += 1
            elif status.get("needs_login"):
                results["expired"] += 1
                detail["needs_login"] = True
            else:
                results["errors"] += 1
                detail["error"] = status.get("error")

            results["details"].append(detail)

        return results

    def get_token_expiry_estimate(self, connected_at: datetime) -> datetime:
        """
        Estimate when token will expire.

        Kite tokens expire at approximately 7:30 AM on the next trading day.
        This is an estimate - actual expiry may vary slightly.
        """
        if not connected_at:
            return datetime.now(timezone.utc)

        # If connected before 7:30 AM, expires same day 7:30 AM
        # If connected after 7:30 AM, expires next day 7:30 AM
        expiry_time = connected_at.replace(hour=2, minute=0, second=0, microsecond=0)  # 7:30 AM IST = 2:00 AM UTC

        if connected_at.hour >= 2:  # After 7:30 AM IST
            expiry_time += timedelta(days=1)

        return expiry_time


# Singleton instance
token_manager = TokenManager()
