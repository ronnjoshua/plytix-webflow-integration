from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.config.database import get_db
from app.clients.plytix_client import PlytixClient
from app.clients.webflow_client import WebflowClient

router = APIRouter()

@router.get("/", response_model=Dict[str, str])
async def health_check():
    """Basic health check endpoint"""
    return {"status": "healthy", "service": "plytix-webflow-integration"}

@router.get("/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """Detailed health check including external services"""
    health_status = {
        "service": "healthy",
        "database": "unknown",
        "plytix_api": "unknown",
        "webflow_api": "unknown"
    }
    
    # Check database
    try:
        from sqlalchemy import text
        result = await db.execute(text("SELECT 1"))
        await db.commit()  # Ensure the transaction is committed
        health_status["database"] = "healthy"
    except Exception as e:
        health_status["database"] = f"unhealthy: {str(e)}"
    
    # Check Plytix API (skip if using test credentials)
    plytix_client = None
    try:
        from app.config.settings import get_settings
        settings = get_settings()
        
        if settings.PLYTIX_API_KEY != "test_key":
            plytix_client = PlytixClient()
            await plytix_client._authenticate()
            health_status["plytix_api"] = "healthy"
        else:
            health_status["plytix_api"] = "test_mode"
    except Exception as e:
        health_status["plytix_api"] = f"unhealthy: {str(e)}"
    finally:
        if plytix_client:
            await plytix_client.close()
    
    # Check Webflow API (skip if using test credentials)
    webflow_client = None
    try:
        if settings.WEBFLOW_TOKEN != "test_token":
            webflow_client = WebflowClient()
            # Check both site and collection access
            auth_ok = await webflow_client.check_authentication()
            if auth_ok:
                health_status["webflow_api"] = "healthy"
            else:
                health_status["webflow_api"] = "unhealthy: authentication failed"
        else:
            health_status["webflow_api"] = "test_mode"
    except Exception as e:
        health_status["webflow_api"] = f"unhealthy: {str(e)}"
    finally:
        if webflow_client:
            await webflow_client.close()
    
    return health_status