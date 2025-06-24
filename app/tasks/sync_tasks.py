from celery import current_task
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.celery_app import celery_app
from app.services.sync_service import SyncService
from app.config.database import AsyncSessionLocal

logger = structlog.get_logger()

@celery_app.task(bind=True)
def run_scheduled_sync(self, test_mode: bool = False):
    """Celery task for running scheduled product synchronization"""
    import asyncio
    import nest_asyncio
    
    # Enable nested event loops to handle asyncio.run() in Celery
    nest_asyncio.apply()
    
    async def async_sync():
        # Ensure database is set up
        from app.config.database import setup_database, AsyncSessionLocal as SessionLocal
        if SessionLocal is None:
            setup_database()
            from app.config.database import AsyncSessionLocal as SessionLocal
        
        async with SessionLocal() as db:
            sync_service = SyncService(db)
            
            try:
                # Update task state using self since task is bound
                self.update_state(
                    state="PROGRESS",
                    meta={"status": "Starting synchronization"}
                )
                
                # Run the sync
                sync_result = await sync_service.run_full_sync(test_mode=test_mode)
                
                result = {
                    "status": "completed",
                    "products_processed": sync_result.products_processed,
                    "variants_processed": sync_result.variants_processed,
                    "errors_count": sync_result.errors_count,
                    "duration_seconds": sync_result.sync_duration_seconds
                }
                
                logger.info("Scheduled sync completed", **result)
                return result
                
            except Exception as e:
                logger.error("Scheduled sync failed", error=str(e))
                # Don't update state here, let Celery handle the failure
                # Just re-raise as a simple exception
                raise Exception(f"Sync failed: {str(e)}")
            finally:
                await sync_service.close()
    
    # Try to get existing event loop first
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, use asyncio.create_task instead
            import asyncio
            return loop.run_until_complete(async_sync())
        else:
            return asyncio.run(async_sync())
    except RuntimeError:
        # No loop exists, create a new one
        return asyncio.run(async_sync())

@celery_app.task
def sync_single_product_task(product_id: str):
    """Task for syncing a single product (for manual triggers)"""
    import asyncio
    
    async def async_single_sync():
        async with AsyncSessionLocal() as db:
            sync_service = SyncService(db)
            
            try:
                # Fetch single product from Plytix and process it
                product = await sync_service.plytix_client.get_product_details(product_id)
                variants = await sync_service.plytix_client.get_product_variants(product_id)
                product.variants = variants
                
                # Create a minimal sync state for tracking
                from app.models.database import SyncState
                sync_state = SyncState(
                    status="running",
                    products_processed=0,
                    variants_processed=0,
                    errors_count=0
                )
                db.add(sync_state)
                await db.commit()
                
                # Sync the single product
                result = await sync_service._sync_single_product(product, sync_state)
                
                # Update sync state
                sync_state.status = "completed" if result else "failed"
                sync_state.products_processed = 1 if result else 0
                sync_state.variants_processed = len(product.variants) if result else 0
                await db.commit()
                
                return {
                    "status": "completed" if result else "failed",
                    "product_id": product_id,
                    "sku": product.sku,
                    "variants_count": len(product.variants)
                }
                
            except Exception as e:
                logger.error("Single product sync failed", product_id=product_id, error=str(e))
                # Re-raise as a simple exception that can be JSON serialized
                raise Exception(f"Single product sync failed: {str(e)}")
            finally:
                await sync_service.close()
    
    return asyncio.run(async_single_sync())