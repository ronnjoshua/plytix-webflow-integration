from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.config.database import get_db
from app.services.sync_service import SyncService
from app.services.auth_service import check_api_credentials
from app.tasks.sync_tasks import run_scheduled_sync, sync_single_product_task

router = APIRouter()

@router.post("/trigger", response_model=Dict[str, Any])
async def trigger_sync(
    background_tasks: BackgroundTasks,
    test_mode: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger product synchronization"""
    try:
        # Run sync in background
        task = run_scheduled_sync.delay(test_mode=test_mode)
        
        return {
            "message": "Synchronization started",
            "task_id": task.id,
            "test_mode": test_mode
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start sync: {str(e)}")

@router.post("/trigger/product/{product_id}")
async def trigger_single_product_sync(product_id: str):
    """Manually trigger synchronization for a single product"""
    try:
        task = sync_single_product_task.delay(product_id)
        
        return {
            "message": "Single product synchronization started",
            "task_id": task.id,
            "product_id": product_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start product sync: {str(e)}")

@router.get("/status/{task_id}")
async def get_sync_status(task_id: str):
    """Get status of a running synchronization task"""
    from app.tasks.celery_app import celery_app
    from celery.exceptions import CeleryError

    try:
        task = celery_app.AsyncResult(task_id)
        
        if task.state == "PENDING":
            response = {
                "state": task.state,
                "status": "Task is waiting to be processed"
            }
        elif task.state == "PROGRESS":
            response = {
                "state": task.state,
                "status": task.info.get("status", ""),
                "progress": task.info.get("progress", 0)
            }
        elif task.state == "SUCCESS":
            response = {
                "state": task.state,
                "result": task.result
            }
        elif task.state == "FAILURE":
            response = {
                "state": task.state,
                "error": str(task.info)
            }
        else:
            response = {
                "state": task.state,
                "info": str(task.info)
            }
    except (KeyError, ValueError, CeleryError) as e:
        # Defensive: If meta is corrupted or missing exc_type, return error info
        response = {
            "state": "UNKNOWN",
            "error": f"Could not retrieve task status: {str(e)}"
        }
    return response

@router.get("/history")
async def get_sync_history(
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """Get recent synchronization history"""
    from sqlalchemy import select, desc
    from app.models.database import SyncState
    
    stmt = select(SyncState).order_by(desc(SyncState.created_at)).limit(limit)
    result = await db.execute(stmt)
    sync_states = result.scalars().all()
    
    return [
        {
            "id": state.id,
            "status": state.status,
            "products_processed": state.products_processed,
            "variants_processed": state.variants_processed,
            "errors_count": state.errors_count,
            "duration_seconds": state.sync_duration_seconds,
            "created_at": state.created_at.isoformat()
        }
        for state in sync_states
    ]

@router.get("/errors/{sync_id}")
async def get_sync_errors(
    sync_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get errors for a specific sync"""
    from sqlalchemy import select
    from app.models.database import SyncError
    
    stmt = select(SyncError).where(SyncError.sync_state_id == sync_id)
    result = await db.execute(stmt)
    errors = result.scalars().all()
    
    return [
        {
            "id": error.id,
            "plytix_product_id": error.plytix_product_id,
            "error_type": error.error_type,
            "error_message": error.error_message,
            "error_data": error.error_data,
            "created_at": error.created_at.isoformat()
        }
        for error in errors
    ]

@router.get("/auth-check")
async def check_api_authentication():
    """Check authentication status for all APIs"""
    try:
        results = await check_api_credentials()
        
        # Return appropriate HTTP status based on auth results
        if not results["overall"]["authenticated"]:
            raise HTTPException(
                status_code=401, 
                detail={
                    "message": "One or more APIs failed authentication",
                    "details": results
                }
            )
        
        return {
            "message": "All APIs authenticated successfully",
            "status": "success",
            "details": results
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Authentication check failed: {str(e)}"
        )