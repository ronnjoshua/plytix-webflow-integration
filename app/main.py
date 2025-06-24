from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog
import os

from app.config.settings import get_settings
from app.api.routes import health, sync, monitoring, collections, field_mappings
from app.core.logging import setup_logging
# from app.tasks.celery_app import celery_app  # Import only when needed

# Setup structured logging
setup_logging()
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Plytix-Webflow Integration API")
    
    # Create database tables
    try:
        from app.config.database import create_tables
        await create_tables()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.warning("Database setup failed", error=str(e))
    
    yield
    # Shutdown
    logger.info("Shutting down API")

app = FastAPI(
    title="Plytix-Webflow Integration API",
    description="Synchronize products and variants from Plytix PIM to Webflow E-commerce",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(sync.router, prefix="/sync", tags=["synchronization"])
app.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])
app.include_router(collections.router, prefix="/collections", tags=["collections"])
app.include_router(field_mappings.router, prefix="/field-mappings", tags=["field-mappings"])

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_config=None  # Use structlog instead
    )