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
    
    ZERODHA_API_KEY: Optional[str] = None
    ZERODHA_API_SECRET: Optional[str] = None
    ZERODHA_REDIRECT_URI: Optional[str] = None
    
    OPENROUTER_API_KEY: Optional[str] = None

    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_WHATSAPP_FROM: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None # Keeping for backward compat if used elsewhere
    
    REDIS_URL: str = "redis://localhost:6379/0"
    
    ENCRYPTION_KEY: str = "change_this_to_generated_fernet_key"
    API_SECRET_KEY: str = "changethis" # User requested API_SECRET_KEY, map from SECRET_KEY or new
    SECRET_KEY: str = "changethis" # Keeping standard FastAPI one too
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
