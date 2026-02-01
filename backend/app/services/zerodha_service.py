import hashlib
import httpx
import logging
from typing import Dict, Any, List, Optional
from urllib.parse import urlencode
from app.core.config import settings

logger = logging.getLogger(__name__)

class ZerodhaClient:
    LOGIN_URL = "https://kite.zerodha.com/connect/login"
    TOKEN_URL = "https://api.kite.trade/session/token"
    BASE_URL = "https://api.kite.trade"
    
    def __init__(self):
        self.api_key = settings.ZERODHA_API_KEY
        self.api_secret = settings.ZERODHA_API_SECRET
        



    def generate_login_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """Constructs the login URL."""
        params = {
            "v": "3",
            "api_key": self.api_key,
            "redirect_uri": redirect_uri
        }
        if state:
            params["state"] = state
            
        return f"{self.LOGIN_URL}?{urlencode(params)}"

    async def exchange_token(self, request_token: str) -> Dict[str, Any]:
        """Exchanges request_token for access_token."""
        if not self.api_key or not self.api_secret:
            raise ValueError("Zerodha API credentials not configured")
            
        checksum = hashlib.sha256(
            (self.api_key + request_token + self.api_secret).encode("utf-8")
        ).hexdigest()
        
        data = {
            "api_key": self.api_key,
            "request_token": request_token,
            "checksum": checksum
        }
        
        headers = {"X-Kite-Version": "3"}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.TOKEN_URL, data=data, headers=headers)
                response.raise_for_status()
                json_resp = response.json()
                
                if json_resp.get("status") != "success":
                    raise Exception(f"Zerodha Error: {json_resp.get('message')}")
                    
                return json_resp["data"]
            except httpx.HTTPError as e:
                logger.error(f"HTTP Error interacting with Zerodha: {e}")
                raise Exception("Failed to connect to Zerodha")

    async def get_profile(self, access_token: str) -> Dict[str, Any]:
        """Fetches user profile."""
        headers = {
            "Authorization": f"token {self.api_key}:{access_token}",
            "X-Kite-Version": "3"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.BASE_URL}/user/profile", headers=headers)
            response.raise_for_status()
            return response.json().get("data", {})

    async def get_trades(self, access_token: str) -> List[Dict[str, Any]]:
        """Fetch executed trades from tradebook."""
        url = f"{self.BASE_URL}/orders/trades"
        logger.info(f"Calling Zerodha trades API: {url}")
        if access_token:
             logger.info(f"Authorization header: token {access_token[:6]}...{access_token[-4:] if len(access_token) > 10 else ''}")
        
        headers = {
            "Authorization": f"token {self.api_key}:{access_token}",
            "X-Kite-Version": "3"
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            logger.info(f"Trades API response status: {response.status_code}")
            response.raise_for_status()
            
            try:
                data = response.json()
            except Exception as e:
                logger.error(f"JSON parse error for trades: {e}")
                logger.debug(f"Response text: {response.text[:500]}")
                return []
                
            if not isinstance(data, dict):
                logger.error(f"Unexpected response format: {type(data)}")
                return []
                
            return data.get("data", [])

    async def get_positions(self, access_token: str) -> Dict[str, Any]:
        """Fetch current open positions."""
        url = f"{self.BASE_URL}/portfolio/positions"
        logger.info(f"Calling Zerodha positions API: {url}")
        if access_token:
             logger.info(f"Authorization header: token {access_token[:6]}...{access_token[-4:] if len(access_token) > 10 else ''}")
        
        headers = {
            "Authorization": f"token {self.api_key}:{access_token}",
            "X-Kite-Version": "3"
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            logger.info(f"Positions API response status: {response.status_code}")
            response.raise_for_status()
            
            try:
                data = response.json()
            except Exception as e:
                logger.error(f"JSON parse error for positions: {e}")
                logger.debug(f"Response text: {response.text[:500]}")
                return {}
                
            if not isinstance(data, dict):
                logger.error(f"Unexpected response format: {type(data)}")
                return {}
                
            return data.get("data", {})

    async def get_orders(self, access_token: str) -> List[Dict[str, Any]]:
        """Fetch list of orders."""
        url = f"{self.BASE_URL}/orders"
        logger.info(f"Calling Zerodha orders API: {url}")
        if access_token:
             logger.info(f"Authorization header: token {access_token[:6]}...{access_token[-4:] if len(access_token) > 10 else ''}")
        
        headers = {
            "Authorization": f"token {self.api_key}:{access_token}",
            "X-Kite-Version": "3"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            logger.info(f"Orders API response status: {response.status_code}")
            response.raise_for_status()
            
            try:
                data = response.json()
            except Exception as e:
                logger.error(f"JSON parse error for orders: {e}")
                logger.debug(f"Response text: {response.text[:500]}")
                return []
                
            if not isinstance(data, dict):
                logger.error(f"Unexpected response format: {type(data)}")
                return []
                
            return data.get("data", [])

    async def revoke_token(self, access_token: str) -> bool:
        """Revokes the access token."""
        headers = {
            "Authorization": f"token {self.api_key}:{access_token}",
            "X-Kite-Version": "3"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{self.TOKEN_URL}?api_key={self.api_key}&access_token={access_token}", headers=headers)
            return response.status_code == 200

zerodha_client = ZerodhaClient()
