from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pydantic import Field, model_validator

class Settings(BaseSettings):
    PROJECT_NAME: str = "TradeMentor AI"
    ENVIRONMENT: str = "development"

    # Database - this is the only required one
    DATABASE_URL: str

    # Supabase (optional - not used since we connect directly via DATABASE_URL)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_SERVICE_KEY: Optional[str] = Field(default=None, validation_alias="SUPABASE_SERVICE_ROLE_KEY")
    
    FRONTEND_URL: str = "http://localhost:8080"

    ZERODHA_API_KEY: Optional[str] = None
    ZERODHA_API_SECRET: Optional[str] = None
    ZERODHA_REDIRECT_URI: Optional[str] = None

    # Dedicated market-data Zerodha account (for shared KiteTicker).
    # Use your own Zerodha trading account + a KiteConnect app registered on it.
    # When set, SharedPriceStream uses these credentials exclusively — never borrows a user's token.
    # When not set, SharedPriceStream falls back to any connected user's token (dev/early-stage use).
    #
    # Setup:
    #   1. kite.trade/developers → create an app → get ZERODHA_MD_API_KEY + ZERODHA_MD_API_SECRET
    #   2. Enable TOTP on the Zerodha account → save the 32-char TOTP secret
    #   3. A Celery beat task refreshes the token daily at 8:45 AM IST automatically
    #
    ZERODHA_MD_API_KEY: Optional[str] = None
    ZERODHA_MD_API_SECRET: Optional[str] = None
    ZERODHA_MD_USER_ID: Optional[str] = None       # Zerodha client ID (e.g. AB1234)
    ZERODHA_MD_PASSWORD: Optional[str] = None      # Zerodha login password
    ZERODHA_MD_TOTP_SECRET: Optional[str] = None   # 32-char base32 TOTP secret from Zerodha 2FA setup
    
    OPENROUTER_API_KEY: Optional[str] = None

    # OpenAI API key (used for embeddings in RAG)
    OPENAI_API_KEY: Optional[str] = None

    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_WHATSAPP_FROM: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None # Keeping for backward compat if used elsewhere

    # Web Push VAPID keys - generate with: npx web-push generate-vapid-keys
    VAPID_PUBLIC_KEY: Optional[str] = None
    VAPID_PRIVATE_KEY: Optional[str] = None
    VAPID_EMAIL: str = "admin@tradementor.ai"
    
    # Redis URL - supports both local and Upstash (rediss://)
    # Upstash format: rediss://default:PASSWORD@HOST:PORT
    REDIS_URL: str = "redis://localhost:6379/0"

    # Optional: Separate Celery broker URL (defaults to REDIS_URL)
    CELERY_BROKER_URL: Optional[str] = None

    # SMTP — only used for admin panel OTP. Not used for user report delivery.
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASS: Optional[str] = None
    EMAIL_FROM: Optional[str] = None

    # Sentry error tracking — create free account at sentry.io, set DSN in .env
    SENTRY_DSN: Optional[str] = None

    @model_validator(mode="after")
    def _validate_production_settings(self) -> "Settings":
        if self.ENVIRONMENT != "development" and "localhost" in self.REDIS_URL:
            raise ValueError(
                "REDIS_URL is pointing to localhost in a non-development environment. "
                "Set REDIS_URL to your Redis provider URL (e.g. Upstash "
                "rediss://default:PASSWORD@HOST:PORT). "
                "Failing fast to prevent silent connection failures on startup."
            )
        return self

    @property
    def celery_broker(self) -> str:
        """Get Celery broker URL, defaulting to REDIS_URL."""
        return self.CELERY_BROKER_URL or self.REDIS_URL
    
    ENCRYPTION_KEY: str  # Required - generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    SECRET_KEY: str  # Required - generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    ALGORITHM: str = "HS256"

    # Admin panel — separate JWT secret, independent of user/broker auth
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    ADMIN_JWT_SECRET: Optional[str] = None
    ADMIN_JWT_EXPIRE_HOURS: int = 8
    # IP allowlist for admin panel — comma-separated IPs/CIDRs, empty = no restriction (dev mode)
    # Example: "1.2.3.4,10.0.0.0/8,192.168.1.0/24"
    ADMIN_IP_ALLOWLIST: Optional[str] = None
    # Honor X-Forwarded-For when resolving the client IP for the admin allowlist. Enable ONLY
    # behind a trusted proxy/LB that OVERWRITES the header. If the app is directly reachable,
    # leave False — otherwise a spoofed X-Forwarded-For bypasses ADMIN_IP_ALLOWLIST.
    ADMIN_TRUST_PROXY_HEADERS: bool = False
    # TOTP issuer name shown in authenticator apps
    ADMIN_TOTP_ISSUER: str = "TradeMentor Admin"
    # Dev bypass — set to 1 in .env to skip OTP/TOTP and return JWT directly on password verify.
    # NEVER set in production. Blocked when ENVIRONMENT != "development".
    ADMIN_DEV_BYPASS: bool = False

    # Gupshup WhatsApp (replaces Twilio)
    GUPSHUP_API_KEY: Optional[str] = None
    GUPSHUP_APP_NAME: Optional[str] = None
    GUPSHUP_WHATSAPP_FROM: Optional[str] = None  # E.164 without +, e.g. 917XXXXXXXXX
    GUPSHUP_TMPL_REPORT: Optional[str] = None
    GUPSHUP_TMPL_ALERT: Optional[str] = None
    GUPSHUP_TMPL_GUARDIAN: Optional[str] = None
    
    # Maintenance mode — returns 503 for all API requests when true
    MAINTENANCE_MODE: bool = False
    MAINTENANCE_MESSAGE: str = "We're performing scheduled maintenance. Back in a few minutes."

    # Cors - Frontend runs on port 8080.
    # In dev, also allow local-network IPs (192.168.x.x, 10.x.x.x) on common Vite ports
    # so the app works when accessed from other devices on the same network.
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:8080",
        "http://localhost:3000",
        "http://127.0.0.1:8080",
    ]
    BACKEND_CORS_ORIGIN_REGEX: str = r"http://(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?"

    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env"), 
        case_sensitive=True, 
        extra="ignore"
    )

try:
    settings = Settings()
except Exception as _cfg_err:
    import sys as _sys
    _sys.stderr.write(
        f"\n[TradeMentor] Startup failed — missing or invalid environment variables:\n"
        f"  {_cfg_err}\n\n"
        f"Required: ENCRYPTION_KEY, SECRET_KEY\n"
        f"Copy backend/.env.example to backend/.env and fill in all required values.\n"
        f"Generate ENCRYPTION_KEY: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
        f"Generate SECRET_KEY:     python -c \"import secrets; print(secrets.token_urlsafe(32))\"\n\n"
    )
    _sys.exit(1)
