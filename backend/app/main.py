from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Starting up TradeMentor AI Backend...")
    
    # Start retention scheduler
    from app.tasks.retention_tasks import start_scheduler
    start_scheduler()
    logger.info("Retention scheduler started")
    
    yield
    
    # Shutdown logic
    logger.info("Shutting down...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan
)

# CORS Middleware
# CORS - Allow frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For hackathon - allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"Global exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "detail": str(exc)},
    )

# Health Check
@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.PROJECT_NAME}

@app.get("/")
async def root():
    return {"message": "Welcome to TradeMentor AI API"}

from app.api import zerodha
app.include_router(zerodha.router, prefix="/api/zerodha", tags=["zerodha"])

from app.api import trades
app.include_router(trades.router, prefix="/api/trades", tags=["trades"])

from app.api import positions, webhooks, risk, alerts, settings as settings_api, analytics
app.include_router(positions.router, prefix="/api/positions", tags=["positions"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(risk.router, prefix="/api/risk", tags=["risk"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])

from app.api import behavioral
app.include_router(behavioral.router, prefix="/api/behavioral", tags=["behavioral"])

from app.api import coach
app.include_router(coach.router, prefix="/api/coach", tags=["coach"])

from app.api import reports
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])

from app.api import goals
app.include_router(goals.router, prefix="/api/goals", tags=["goals"])

