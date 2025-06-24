from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
from datetime import datetime, timedelta

from app.config.database import get_db

router = APIRouter()

@router.get("/stats")
async def get_sync_stats(
    days: int = 7,
    db: AsyncSession = Depends(get_db)
):
    """Get synchronization statistics for the last N days"""
    from sqlalchemy import select, func, and_
    from app.models.database import SyncState, ProductMapping, VariantMapping
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Get sync statistics
    sync_stats_stmt = select(
        func.count(SyncState.id).label("total_syncs"),
        func.sum(SyncState.products_processed).label("total_products"),
        func.sum(SyncState.variants_processed).label("total_variants"),
        func.sum(SyncState.errors_count).label("total_errors"),
        func.avg(SyncState.sync_duration_seconds).label("avg_duration")
    ).where(SyncState.created_at >= cutoff_date)
    
    result = await db.execute(sync_stats_stmt)
    sync_stats = result.first()
    
    # Get product mapping counts
    product_count_stmt = select(func.count(ProductMapping.id)).where(
        ProductMapping.is_active == True
    )
    product_result = await db.execute(product_count_stmt)
    active_products = product_result.scalar()
    
    # Get variant mapping counts
    variant_count_stmt = select(func.count(VariantMapping.id))
    variant_result = await db.execute(variant_count_stmt)
    total_variants = variant_result.scalar()
    
    return {
        "period_days": days,
        "sync_statistics": {
            "total_syncs": sync_stats.total_syncs or 0,
            "total_products_processed": sync_stats.total_products or 0,
            "total_variants_processed": sync_stats.total_variants or 0,
            "total_errors": sync_stats.total_errors or 0,
            "average_duration_seconds": float(sync_stats.avg_duration or 0)
        },
        "current_state": {
            "active_products": active_products or 0,
            "total_variants": total_variants or 0
        }
    }

@router.get("/recent-activity")
async def get_recent_activity(
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Get recent synchronization activity"""
    from sqlalchemy import select, desc, or_
    from app.models.database import SyncState, SyncError
    
    # Get recent sync states
    sync_stmt = select(SyncState).order_by(desc(SyncState.created_at)).limit(limit)
    sync_result = await db.execute(sync_stmt)
    recent_syncs = sync_result.scalars().all()
    
    # Get recent errors
    error_stmt = select(SyncError).order_by(desc(SyncError.created_at)).limit(limit)
    error_result = await db.execute(error_stmt)
    recent_errors = error_result.scalars().all()
    
    activities = []
    
    # Add sync activities
    for sync in recent_syncs:
        activities.append({
            "type": "sync",
            "timestamp": sync.created_at.isoformat(),
            "status": sync.status,
            "details": {
                "products_processed": sync.products_processed,
                "variants_processed": sync.variants_processed,
                "errors_count": sync.errors_count,
                "duration_seconds": sync.sync_duration_seconds
            }
        })
    
    # Add error activities
    for error in recent_errors:
        activities.append({
            "type": "error",
            "timestamp": error.created_at.isoformat(),
            "status": "error",
            "details": {
                "error_type": error.error_type,
                "error_message": error.error_message,
                "plytix_product_id": error.plytix_product_id
            }
        })
    
    # Sort by timestamp descending
    activities.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return activities[:limit]

@router.get("/health-metrics")
async def get_health_metrics(db: AsyncSession = Depends(get_db)):
    """Get system health metrics"""
    from sqlalchemy import select, func, and_
    from app.models.database import SyncState, SyncError
    
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    last_hour = now - timedelta(hours=1)
    
    # Recent sync success rate
    recent_syncs_stmt = select(SyncState).where(SyncState.created_at >= last_24h)
    recent_syncs_result = await db.execute(recent_syncs_stmt)
    recent_syncs = recent_syncs_result.scalars().all()
    
    successful_syncs = len([s for s in recent_syncs if s.status == "completed"])
    total_recent_syncs = len(recent_syncs)
    success_rate = (successful_syncs / total_recent_syncs * 100) if total_recent_syncs > 0 else 0
    
    # Error rate in last hour
    recent_errors_stmt = select(func.count(SyncError.id)).where(
        SyncError.created_at >= last_hour
    )
    recent_errors_result = await db.execute(recent_errors_stmt)
    recent_errors_count = recent_errors_result.scalar() or 0
    
    # Last successful sync
    last_success_stmt = select(SyncState).where(
        SyncState.status == "completed"
    ).order_by(desc(SyncState.created_at)).limit(1)
    last_success_result = await db.execute(last_success_stmt)
    last_successful_sync = last_success_result.scalar_one_or_none()
    
    return {
        "success_rate_24h": round(success_rate, 2),
        "errors_last_hour": recent_errors_count,
        "total_syncs_24h": total_recent_syncs,
        "last_successful_sync": last_successful_sync.created_at.isoformat() if last_successful_sync else None,
        "system_status": "healthy" if success_rate > 80 and recent_errors_count < 10 else "degraded"
    }