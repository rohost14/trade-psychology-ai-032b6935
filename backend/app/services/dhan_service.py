"""
Dhan Broker Service — STUB

Implement this file when adding Dhan support.

Dhan API docs: https://dhanhq.co/docs/v2/

Steps to activate:
1. Implement all abstract methods below (remove the NotImplementedError stubs)
2. Add DHAN_CLIENT_ID / DHAN_ACCESS_TOKEN to backend/.env and config.py
3. Uncomment the BrokerFactory.register line at the bottom
4. Update zerodha.py OAuth callback to handle broker_name="dhan" (Dhan uses
   a different OAuth flow — access token is long-lived, not session-based)
5. Add "dhan" to get_broker_service() map in broker_interface.py (already added)

Dhan key differences from Zerodha:
- Auth: Long-lived access token (no daily login), generated from DhanHQ dashboard
- WebSocket: Dhan has its own ticker API (DhanFeed) — update price_stream_service.py
- Instruments: Dhan uses security_id (integer) not tradingsymbol
- Products: INTRADAY / CNC / MARGIN (different names to Kite MIS/CNC/NRML)
"""

from typing import Dict, List, Optional
from app.services.broker_interface import (
    BrokerInterface, BrokerType, BrokerFactory,
    NormalizedProfile, NormalizedTrade, NormalizedPosition,
    NormalizedHolding,
)


class DhanClient(BrokerInterface):
    BASE_URL = "https://api.dhan.co/v2"

    def __init__(self):
        # TODO: load from settings
        # from app.core.config import settings
        # self.client_id = settings.DHAN_CLIENT_ID
        pass

    @property
    def broker_type(self) -> BrokerType:
        return BrokerType.DHAN

    @property
    def broker_name(self) -> str:
        return "Dhan"

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def generate_login_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """
        Dhan does not have a standard OAuth login URL flow.
        Access tokens are generated from the DhanHQ dashboard and are long-lived.
        This method should redirect users to instructions for generating a token,
        or implement Dhan's partner OAuth if/when available.
        """
        raise NotImplementedError("Dhan: generate_login_url not yet implemented")

    async def exchange_token(self, request_token: str) -> Dict:
        """Dhan uses long-lived tokens — no exchange step needed."""
        raise NotImplementedError("Dhan: exchange_token not yet implemented")

    async def revoke_token(self, access_token: str) -> bool:
        """Dhan tokens expire naturally — no explicit revocation API."""
        raise NotImplementedError("Dhan: revoke_token not yet implemented")

    async def validate_token(self, access_token: str) -> bool:
        """Validate by calling a cheap endpoint like /fundlimit."""
        raise NotImplementedError("Dhan: validate_token not yet implemented")

    # ------------------------------------------------------------------
    # User Data
    # ------------------------------------------------------------------

    async def get_profile(self, access_token: str) -> NormalizedProfile:
        """GET /fundlimit or /profile equivalent."""
        raise NotImplementedError("Dhan: get_profile not yet implemented")

    async def get_margins(self, access_token: str) -> Dict:
        """GET /fundlimit"""
        raise NotImplementedError("Dhan: get_margins not yet implemented")

    # ------------------------------------------------------------------
    # Trading Data
    # ------------------------------------------------------------------

    async def get_trades(self, access_token: str) -> List[NormalizedTrade]:
        """GET /trades — Dhan returns today's executed trades."""
        raise NotImplementedError("Dhan: get_trades not yet implemented")

    async def get_orders(self, access_token: str) -> List[Dict]:
        """GET /orders"""
        raise NotImplementedError("Dhan: get_orders not yet implemented")

    async def get_positions(self, access_token: str) -> List[NormalizedPosition]:
        """GET /positions"""
        raise NotImplementedError("Dhan: get_positions not yet implemented")

    async def get_holdings(self, access_token: str) -> List[NormalizedHolding]:
        """GET /holdings"""
        raise NotImplementedError("Dhan: get_holdings not yet implemented")

    # ------------------------------------------------------------------
    # Instruments
    # ------------------------------------------------------------------

    async def get_instruments(self, exchange: Optional[str] = None, access_token: Optional[str] = None) -> List[Dict]:
        """
        Dhan provides a security master CSV.
        URL: https://images.dhan.co/api-data/api-scrip-master.csv
        Note: Dhan uses security_id (int) not tradingsymbol — normalize to
        tradingsymbol for compatibility with the rest of the system.
        """
        raise NotImplementedError("Dhan: get_instruments not yet implemented")

    async def get_order_history(self, access_token: str, order_id: str) -> List[Dict]:
        """GET /orders/{order_id}"""
        raise NotImplementedError("Dhan: get_order_history not yet implemented")


# Uncomment when implementation is complete:
# BrokerFactory.register(BrokerType.DHAN, DhanClient)
