from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List

from app.config.database import get_db
from app.services.collection_mapping_service import CollectionMappingService

router = APIRouter()

@router.get("/mapping-info")
async def get_collection_mapping_info(db: AsyncSession = Depends(get_db)):
    """Get information about current collection mapping configuration"""
    collection_service = CollectionMappingService(db)
    info = await collection_service.get_collection_mapping_info()
    return info

@router.post("/clear-cache")
async def clear_collection_cache(db: AsyncSession = Depends(get_db)):
    """Clear the collection mapping cache"""
    collection_service = CollectionMappingService(db)
    await collection_service.clear_cache()
    return {"message": "Collection mapping cache cleared successfully"}

@router.get("/statistics")
async def get_collection_statistics(db: AsyncSession = Depends(get_db)):
    """Get statistics about products across collections"""
    from sqlalchemy import select, func
    from app.models.database import ProductMapping
    
    # Get product count by collection
    stmt = select(
        ProductMapping.webflow_collection_id,
        func.count(ProductMapping.id).label("product_count")
    ).where(
        ProductMapping.is_active == True,
        ProductMapping.webflow_collection_id.isnot(None)
    ).group_by(ProductMapping.webflow_collection_id)
    
    result = await db.execute(stmt)
    collection_stats = result.all()
    
    # Get total counts
    total_stmt = select(func.count(ProductMapping.id)).where(
        ProductMapping.is_active == True
    )
    total_result = await db.execute(total_stmt)
    total_products = total_result.scalar()
    
    return {
        "total_products": total_products or 0,
        "collections": [
            {
                "collection_id": stat.webflow_collection_id,
                "product_count": stat.product_count
            }
            for stat in collection_stats
        ]
    }

@router.get("/estimate-large-sync")
async def estimate_large_sync(
    product_count: int = 2000,
    avg_variants_per_product: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Estimate timing and resource requirements for large sync operations"""
    
    # Calculate estimates based on system capabilities
    total_variants = product_count * avg_variants_per_product
    
    # Rate limiting considerations
    from app.config.settings import get_settings
    settings = get_settings()
    
    plytix_rate_limit = settings.PLYTIX_RATE_LIMIT  # per 10 seconds
    webflow_rate_limit = settings.WEBFLOW_RATE_LIMIT  # per minute
    
    # Estimate API calls needed
    plytix_calls = product_count + product_count  # products + variants calls
    webflow_calls = product_count  # product creation/update calls
    
    # Calculate time estimates (in seconds)
    plytix_time = (plytix_calls / plytix_rate_limit) * 10
    webflow_time = (webflow_calls / webflow_rate_limit) * 60
    
    # Processing time estimates (assuming 100ms per product processing)
    processing_time = product_count * 0.1
    
    total_estimated_time = max(plytix_time, webflow_time) + processing_time
    
    # Memory estimates (rough calculation)
    estimated_memory_mb = (product_count * 0.5) + (total_variants * 0.1)  # MB
    
    # Batch size recommendations
    recommended_batch_size = min(50, max(10, int(1000 / avg_variants_per_product)))
    
    return {
        "input": {
            "product_count": product_count,
            "avg_variants_per_product": avg_variants_per_product,
            "total_variants": total_variants
        },
        "api_calls": {
            "plytix_calls": plytix_calls,
            "webflow_calls": webflow_calls
        },
        "time_estimates": {
            "plytix_api_time_seconds": round(plytix_time, 2),
            "webflow_api_time_seconds": round(webflow_time, 2),
            "processing_time_seconds": round(processing_time, 2),
            "total_estimated_seconds": round(total_estimated_time, 2),
            "total_estimated_minutes": round(total_estimated_time / 60, 2),
            "total_estimated_hours": round(total_estimated_time / 3600, 2)
        },
        "resource_estimates": {
            "estimated_memory_mb": round(estimated_memory_mb, 2),
            "recommended_batch_size": recommended_batch_size
        },
        "recommendations": [
            "Use batch processing to manage memory usage",
            "Consider running sync during off-peak hours",
            "Monitor rate limits and adjust batch sizes accordingly",
            "Enable database connection pooling for concurrent operations",
            "Consider using multiple worker processes for parallel processing"
        ]
    }