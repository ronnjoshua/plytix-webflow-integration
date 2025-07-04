from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
import structlog

from app.services.cache_service import CacheService
from app.config.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()
router = APIRouter(prefix="/cache", tags=["cache"])

async def get_cache_service() -> CacheService:
    """Dependency to get cache service"""
    cache_service = CacheService()
    try:
        yield cache_service
    finally:
        await cache_service.close()

@router.get("/stats")
async def get_cache_stats(
    cache_service: CacheService = Depends(get_cache_service)
) -> Dict[str, Any]:
    """Get cache statistics"""
    try:
        stats = await cache_service.get_cache_stats()
        return {"success": True, "data": stats}
    except Exception as e:
        logger.error("Failed to get cache stats", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")

@router.post("/invalidate/products")
async def invalidate_products_cache(
    cache_service: CacheService = Depends(get_cache_service)
) -> Dict[str, Any]:
    """Invalidate all products cache"""
    try:
        await cache_service.invalidate_pattern("webflow:products:*")
        logger.info("Products cache invalidated")
        return {"success": True, "message": "Products cache invalidated"}
    except Exception as e:
        logger.error("Failed to invalidate products cache", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to invalidate cache: {str(e)}")

@router.post("/invalidate/product_hashes")
async def invalidate_product_hashes_cache(
    cache_service: CacheService = Depends(get_cache_service)
) -> Dict[str, Any]:
    """Invalidate all product hashes cache"""
    try:
        await cache_service.invalidate_pattern("product_hash:*")
        logger.info("Product hashes cache invalidated")
        return {"success": True, "message": "Product hashes cache invalidated"}
    except Exception as e:
        logger.error("Failed to invalidate product hashes cache", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to invalidate cache: {str(e)}")

@router.post("/invalidate/assets")
async def invalidate_assets_cache(
    cache_service: CacheService = Depends(get_cache_service)
) -> Dict[str, Any]:
    """Invalidate all assets cache"""
    try:
        await cache_service.invalidate_pattern("product_assets:*")
        logger.info("Assets cache invalidated")
        return {"success": True, "message": "Assets cache invalidated"}
    except Exception as e:
        logger.error("Failed to invalidate assets cache", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to invalidate cache: {str(e)}")

@router.post("/invalidate/all")
async def invalidate_all_cache(
    cache_service: CacheService = Depends(get_cache_service)
) -> Dict[str, Any]:
    """Invalidate all cache"""
    try:
        await cache_service.invalidate_pattern("*")
        logger.info("All cache invalidated")
        return {"success": True, "message": "All cache invalidated"}
    except Exception as e:
        logger.error("Failed to invalidate all cache", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to invalidate cache: {str(e)}")

@router.post("/warm-up/products")
async def warm_up_products_cache(
    cache_service: CacheService = Depends(get_cache_service)
) -> Dict[str, Any]:
    """Warm up products cache by fetching all products"""
    try:
        from app.clients.webflow_client import WebflowClient
        
        webflow_client = WebflowClient()
        try:
            # This will initialize the cache
            await webflow_client._initialize_products_cache()
            logger.info("Products cache warmed up")
            return {"success": True, "message": "Products cache warmed up"}
        finally:
            await webflow_client.close()
            
    except Exception as e:
        logger.error("Failed to warm up products cache", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to warm up cache: {str(e)}")