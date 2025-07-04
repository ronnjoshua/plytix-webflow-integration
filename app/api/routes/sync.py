from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.config.database import get_db
from app.services.sync_service import SyncService
from app.services.streaming_sync_service import StreamingSyncService
from app.services.bulk_database_service import BulkDatabaseService
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

@router.post("/trigger/large-scale", response_model=Dict[str, Any])
async def trigger_large_scale_sync(
    background_tasks: BackgroundTasks,
    test_mode: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Trigger large-scale sync optimized for 1000+ products"""
    try:
        # Use streaming sync service for large catalogs
        streaming_service = StreamingSyncService(db)
        
        # Run in background task
        async def run_large_sync():
            try:
                result = await streaming_service.run_large_scale_sync(test_mode=test_mode)
                return result
            finally:
                await streaming_service.close()
        
        background_tasks.add_task(run_large_sync)
        
        return {
            "message": "Large-scale synchronization started",
            "mode": "streaming",
            "optimized_for": "1000+ products",
            "test_mode": test_mode,
            "features": [
                "memory_efficient_streaming",
                "bulk_database_operations", 
                "progressive_checkpointing",
                "intelligent_caching"
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start large-scale sync: {str(e)}")

@router.get("/performance/stats")
async def get_performance_stats(
    days: int = 7,
    db: AsyncSession = Depends(get_db)
):
    """Get sync performance statistics for monitoring large-scale operations"""
    try:
        bulk_db_service = BulkDatabaseService(db)
        stats = await bulk_db_service.get_sync_statistics(days=days)
        
        # Add performance indicators
        stats["performance_indicators"] = {
            "products_per_hour": (stats["total_products_processed"] / max(stats["avg_duration_seconds"] / 3600, 1)) if stats["avg_duration_seconds"] > 0 else 0,
            "error_rate": (stats["total_errors"] / max(stats["total_products_processed"], 1)) * 100 if stats["total_products_processed"] > 0 else 0,
            "avg_sync_time_hours": stats["avg_duration_seconds"] / 3600 if stats["avg_duration_seconds"] > 0 else 0
        }
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get performance stats: {str(e)}")

@router.post("/optimize/database")
async def optimize_database_for_sync(
    db: AsyncSession = Depends(get_db)
):
    """Optimize database settings for large-scale sync operations"""
    try:
        bulk_db_service = BulkDatabaseService(db)
        await bulk_db_service.optimize_database_for_large_sync()
        
        return {
            "message": "Database optimized for large-scale sync",
            "optimizations": [
                "increased_work_memory",
                "optimized_checkpoint_settings",
                "bulk_operation_tuning"
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to optimize database: {str(e)}")

@router.post("/reset/database")
async def reset_database_settings(
    db: AsyncSession = Depends(get_db)
):
    """Reset database settings after large-scale operations"""
    try:
        bulk_db_service = BulkDatabaseService(db)
        await bulk_db_service.reset_database_settings()
        
        return {
            "message": "Database settings reset to defaults"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset database: {str(e)}")

@router.get("/debug/webflow-variants/{product_id}")
async def debug_webflow_variants(product_id: str):
    """Debug Webflow product variant structure"""
    try:
        from app.clients.webflow_client import WebflowClient
        
        client = WebflowClient()
        try:
            # Get product details
            endpoint = f"/sites/{client.site_id}/products/{product_id}"
            product_info = await client._make_request(endpoint)
            
            # Get SKU details if available
            sku_info = None
            if "product" in product_info:
                default_sku_id = product_info["product"]["fieldData"].get("default-sku")
                if default_sku_id:
                    sku_endpoint = f"/sites/{client.site_id}/products/{product_id}/skus/{default_sku_id}"
                    try:
                        sku_info = await client._make_request(sku_endpoint)
                    except Exception as e:
                        sku_info = {"error": str(e)}
            
            return {
                "status": "success",
                "product_id": product_id,
                "product_info": product_info,
                "sku_info": sku_info,
                "analysis": {
                    "has_variants": "sku-properties" in product_info.get("product", {}).get("fieldData", {}),
                    "default_sku_id": product_info.get("product", {}).get("fieldData", {}).get("default-sku"),
                    "variant_count": len(product_info.get("skus", [])) if "skus" in product_info else 0
                }
            }
            
        finally:
            await client.close()
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to debug Webflow variants",
                "error": str(e),
                "product_id": product_id
            }
        )

@router.get("/debug/plytix-search")
async def debug_plytix_search(
    page: int = 1,
    page_size: int = 5,
    test_filters: bool = False
):
    """Debug endpoint to test Plytix search API"""
    try:
        from app.clients.plytix_client import PlytixClient
        from datetime import datetime, timedelta
        
        client = PlytixClient()
        try:
            filters = None
            
            if test_filters:
                # Test with date filter in correct Plytix format (YYYY-MM-DD)
                since_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
                filters = [[{
                    "field": "modified",
                    "operator": "gt",
                    "value": since_date
                }]]
            
            # Test search
            response = await client.search_products(
                page=page,
                page_size=page_size,
                filters=filters,
                status="completed"
            )
            
            return {
                "status": "success",
                "message": "Plytix search working correctly",
                "products_found": len(response.get("data", [])),
                "pagination": response.get("pagination", {}),
                "filters_used": bool(filters),
                "sample_product": response.get("data", [{}])[0] if response.get("data") else None,
                "request_format": {
                    "filters_structure": "array of arrays" if filters else "none",
                    "example_filter": filters[0] if filters else None
                }
            }
            
        finally:
            await client.close()
            
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail={
                "message": "Plytix search failed",
                "error": str(e),
                "error_type": type(e).__name__
            }
        )

@router.get("/debug/product/{sku}")
async def debug_specific_product(sku: str):
    """Debug a specific product by SKU in both Plytix and Webflow"""
    try:
        from app.clients.plytix_client import PlytixClient
        from app.clients.webflow_client import WebflowClient
        from app.services.field_mapping_service import FieldMappingService
        
        plytix_client = PlytixClient()
        webflow_client = WebflowClient()
        field_mapping_service = FieldMappingService(webflow_client=webflow_client)
        
        result = {
            "sku": sku,
            "plytix_status": {},
            "webflow_status": {},
            "sync_eligibility": {}
        }
        
        try:
            # Check Plytix
            logger.info("Checking Plytix for product", sku=sku)
            
            # Search all products to find this SKU
            plytix_found = False
            plytix_product = None
            page = 1
            
            while page <= 5:  # Limit search to first 5 pages
                response = await plytix_client.search_products(page=page, page_size=50, status="completed")
                products = response.get("data", [])
                
                if not products:
                    break
                
                for product_data in products:
                    product_sku = field_mapping_service.get_sku_from_product(product_data)
                    if product_sku == sku:
                        plytix_found = True
                        plytix_product = product_data
                        break
                
                if plytix_found:
                    break
                    
                page += 1
            
            result["plytix_status"] = {
                "found": plytix_found,
                "pages_searched": page - 1,
                "product_id": plytix_product.get("id") if plytix_product else None,
                "product_label": plytix_product.get("label") if plytix_product else None,
                "product_name": plytix_product.get("name") if plytix_product else None
            }
            
            # Check Webflow
            logger.info("Checking Webflow for product", sku=sku)
            
            # Initialize cache and check
            await webflow_client._initialize_products_cache()
            webflow_product = await webflow_client.cache_service.get_webflow_product_by_name(sku)
            
            result["webflow_status"] = {
                "found": bool(webflow_product),
                "product_id": webflow_product.get("id") if webflow_product else None,
                "product_name": webflow_product.get("fieldData", {}).get("name") if webflow_product else None
            }
            
            # Check sync eligibility
            if plytix_found and webflow_product:
                result["sync_eligibility"] = {
                    "eligible": True,
                    "reason": "Product exists in both systems",
                    "would_be_updated": True
                }
            elif plytix_found and not webflow_product:
                result["sync_eligibility"] = {
                    "eligible": False,
                    "reason": "Product exists in Plytix but not in Webflow (CREATE mode disabled)",
                    "would_be_updated": False
                }
            elif not plytix_found and webflow_product:
                result["sync_eligibility"] = {
                    "eligible": False,
                    "reason": "Product exists in Webflow but not in Plytix",
                    "would_be_updated": False
                }
            else:
                result["sync_eligibility"] = {
                    "eligible": False,
                    "reason": "Product not found in either system",
                    "would_be_updated": False
                }
            
            return {
                "status": "success",
                "debug_info": result
            }
            
        finally:
            await plytix_client.close()
            await webflow_client.close()
            await field_mapping_service.asset_handler.close()
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Failed to debug product {sku}",
                "error": str(e),
                "error_type": type(e).__name__
            }
        )

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