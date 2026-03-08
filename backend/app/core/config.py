from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pydantic import Field

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

    # Sentry error tracking — create free account at sentry.io, set DSN in .env
    SENTRY_DSN: Optional[str] = None

    @property
    def celery_broker(self) -> str:
        """Get Celery broker URL, defaulting to REDIS_URL."""
        return self.CELERY_BROKER_URL or self.REDIS_URL
    
    ENCRYPTION_KEY: str  # Required - generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    SECRET_KEY: str  # Required - generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Cors - Frontend runs on port 8080
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:8080", "http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env"), 
        case_sensitive=True, 
        extra="ignore"
    )

settings = Settings()
