from typing import List, Optional
from datetime import datetime
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.plytix_client import PlytixClient
from app.clients.webflow_client import WebflowClient
from app.services.variant_service import VariantService
from app.services.transform_service import TransformService
from app.services.collection_mapping_service import CollectionMappingService
from app.services.field_mapping_service import FieldMappingService
from app.models.database import SyncState, ProductMapping, VariantMapping, SyncError
from app.models.plytix import PlytixProduct
from app.core.exceptions import SyncError as SyncException

logger = structlog.get_logger()

class SyncService:
    """Main service for orchestrating product synchronization"""
    
    def __init__(self, db: AsyncSession):
        from app.config.settings import get_settings
        self.settings = get_settings()
        self.db = db
        self.plytix_client = PlytixClient()
        self.webflow_client = WebflowClient()
        self.variant_service = VariantService()
        self.transform_service = TransformService()
        self.collection_mapping_service = CollectionMappingService(db, self.webflow_client)
        self.field_mapping_service = FieldMappingService(webflow_client=self.webflow_client)
    
    async def close(self):
        """Close the API clients."""
        await self.plytix_client.close()
        await self.webflow_client.close()
        await self.field_mapping_service.asset_handler.close()
    
    async def run_full_sync(self, test_mode: bool = False) -> SyncState:
        """Run complete synchronization from Plytix to Webflow"""
        start_time = datetime.utcnow()
        
        # Create sync state record
        sync_state = SyncState(
            status="running",
            products_processed=0,
            variants_processed=0,
            errors_count=0
        )
        self.db.add(sync_state)
        await self.db.commit()
        
        try:
            # Get last successful sync time for delta sync
            last_sync_time = await self._get_last_sync_time()
            
            # Fetch products from Plytix
            logger.info("Fetching products from Plytix", since=last_sync_time)
            # Temporarily disable delta sync to test the API connection
            plytix_products = await self.plytix_client.get_all_products_with_variants(
                since=None  # Disable delta sync for testing
            )
            
            # Process products in batches
            batch_size = 10 if test_mode else 50
            processed_count = 0
            variant_count = 0
            error_count = 0
            updated_product_ids = []  # Track updated products for batch publishing
            
            for i in range(0, len(plytix_products), batch_size):
                batch = plytix_products[i:i + batch_size]
                
                for product in batch:
                    try:
                        result = await self._sync_single_product(product, sync_state)
                        if result and result.get("webflow_id"):
                            processed_count += 1
                            variant_count += len(product.variants)
                            updated_product_ids.append(result["webflow_id"])
                        
                    except Exception as e:
                        error_count += 1
                        await self._log_error(sync_state, product, str(e))
                        logger.error("Failed to sync product", 
                                   product_id=product.id, 
                                   sku=product.sku, 
                                   error=str(e))
                
                # Update progress
                sync_state.products_processed = processed_count
                sync_state.variants_processed = variant_count
                sync_state.errors_count = error_count
                await self.db.commit()
                
                logger.info("Batch processed", 
                           batch_start=i, 
                           processed=processed_count, 
                           errors=error_count)
            
            # Publish updated products in batch (unless publishing is disabled)
            if updated_product_ids and self.settings.ENABLE_AUTO_PUBLISH:
                logger.info("Publishing updated e-commerce products in batch", 
                           products_updated=len(updated_product_ids),
                           product_ids=updated_product_ids[:5])  # Log first 5 IDs
                publish_result = await self.webflow_client.publish_items(updated_product_ids)
                if publish_result:
                    logger.info("✅ Updated e-commerce products published successfully", 
                               products_published=len(updated_product_ids))
                else:
                    logger.warning("⚠️ E-commerce products publishing failed")
            
            # Update final sync state
            end_time = datetime.utcnow()
            sync_state.status = "completed"
            sync_state.sync_duration_seconds = int((end_time - start_time).total_seconds())
            sync_state.last_sync_time = end_time
            
            await self.db.commit()
            
            logger.info("Sync completed successfully", 
                       products_processed=processed_count,
                       variants_processed=variant_count,
                       errors=error_count,
                       duration_seconds=sync_state.sync_duration_seconds)
            
            return sync_state
            
        except Exception as e:
            # Mark sync as failed
            sync_state.status = "failed"
            sync_state.sync_duration_seconds = int((datetime.utcnow() - start_time).total_seconds())
            await self.db.commit()
            
            logger.error("Sync failed", error=str(e))
            raise SyncException(f"Sync failed: {str(e)}")
    
    async def _sync_single_product(self, product: PlytixProduct, sync_state: SyncState) -> bool:
        """Sync a single product with all its variants"""
        
        logger.warning("🚀 SYNC_SINGLE_PRODUCT: Starting sync for product", product_id=product.id, product_sku=product.sku)
        is_valid, validation_errors = self.variant_service.validate_variant_data(product)
        if not is_valid:
            await self._log_error(sync_state, product, f"Validation errors: {validation_errors}")
            return False
        
        # Determine target collection for this product
        target_collection_id = await self.collection_mapping_service.get_collection_for_product(product)
        
        # Extract variant attributes and create SKU properties
        if product.variants:
            attributes_map = self.variant_service.extract_variant_attributes(product.variants)
            sku_properties = self.variant_service.create_sku_properties(attributes_map)
            sku_matrix = self.variant_service.generate_sku_matrix(product, sku_properties)
        else:
            sku_properties = []
            sku_matrix = self.variant_service.generate_sku_matrix(product, [])
        
        # Process product assets (images use direct URLs, PDFs upload to Webflow)
        plytix_data = product.model_dump() if hasattr(product, 'model_dump') else product.__dict__
        processed_assets = await self.field_mapping_service.process_product_assets(
            plytix_data, 
            use_webflow_upload=True  # Upload PDFs to Webflow, use direct URLs for images
        )
        
        # Transform to Webflow format using enhanced field mapping
        logger.warning("⚡ SYNC: About to call field_mapping_service.transform_product_data", product_id=product.id)
        webflow_data = self.field_mapping_service.transform_product_data(product)
        logger.warning("⚡ SYNC: Completed field_mapping_service.transform_product_data", product_id=product.id, data_keys=list(webflow_data.keys()) if webflow_data else [])
        
        # Merge processed assets into webflow_data
        webflow_data.update(processed_assets)
        
        webflow_product = self.transform_service.transform_product(
            product, sku_properties, sku_matrix, webflow_data
        )
        
        # DEBUG LOGGING: Print out SKU and price values being sent to Webflow
        logger.warning("DEBUG: WebflowProduct SKUs and prices", 
            product_sku=product.sku,
            webflow_skus=[{
                'sku': sku.sku,
                'price_cents': sku.price.value if hasattr(sku, 'price') and hasattr(sku.price, 'value') else None
            } for sku in webflow_product.skus]
        )
        
        # Check if product exists in Webflow using SKU-based matching
        product_sku = self.field_mapping_service.get_sku_from_product(product.__dict__)
        existing_product = await self.webflow_client.get_product_by_sku(
            product_sku, collection_id=target_collection_id
        )

        if not existing_product:
            logger.info("Skipping product - not found in Webflow", 
                        sku=product.sku,
                        message="Product does not exist in Webflow. Skipping sync.")
            return False
        
        try:
            if existing_product:
                # Update existing product only - pass original Plytix data for proper field mapping
                plytix_data = product.model_dump() if hasattr(product, 'model_dump') else product.__dict__
                updated_product = await self.webflow_client.update_product(
                    existing_product.id, webflow_product, plytix_product_data=plytix_data, collection_id=target_collection_id
                )
                await self._update_product_mapping(product, updated_product.id, target_collection_id)
                logger.info("Updated existing product", 
                           sku=product.sku, 
                           webflow_id=updated_product.id,
                           collection_id=target_collection_id)
                
                
                # Update variant mappings
                await self._update_variant_mappings(product)
                return {"webflow_id": updated_product.id, "action": "updated"}
            else:
                # Check if product creation is enabled
                if self.settings.ENABLE_PRODUCT_CREATION and not self.settings.UPDATE_ONLY_MODE:
                    # Create new product (only if enabled)
                    new_product = await self.webflow_client.create_product(
                        webflow_product, collection_id=target_collection_id
                    )
                    await self._create_product_mapping(product, new_product.id, target_collection_id)
                    logger.info("Created new product", 
                               sku=product.sku, 
                               webflow_id=new_product.id,
                               collection_id=target_collection_id)
                    
                    
                    # Update variant mappings
                    await self._update_variant_mappings(product)
                    return {"webflow_id": new_product.id, "action": "created"}
                else:
                    # Skip products that don't exist in Webflow (UPDATE ONLY MODE)
                    logger.info("Skipping product - not found in Webflow", 
                               sku=product.sku,
                               message="Product does not exist in Webflow. UPDATE_ONLY_MODE is enabled.")
                    return False
            
        except Exception as e:
            logger.error("Failed to sync product to Webflow", 
                        product_id=product.id, 
                        sku=product.sku, 
                        error=str(e))
            raise
    
    async def _get_last_sync_time(self) -> Optional[datetime]:
        """Get the timestamp of the last successful sync"""
        from sqlalchemy import select, desc
        
        stmt = select(SyncState).where(
            SyncState.status == "completed"
        ).order_by(desc(SyncState.created_at)).limit(1)
        
        result = await self.db.execute(stmt)
        last_sync = result.scalar_one_or_none()
        
        return last_sync.last_sync_time if last_sync else None
    
    async def _create_product_mapping(self, plytix_product: PlytixProduct, webflow_id: str, collection_id: str):
        """Create mapping between Plytix and Webflow product"""
        mapping = ProductMapping(
            plytix_product_id=plytix_product.id,
            webflow_product_id=webflow_id,
            plytix_sku=plytix_product.sku,
            product_name=plytix_product.label,
            webflow_collection_id=collection_id  # Track which collection this product is in
        )
        self.db.add(mapping)
        await self.db.commit()
    
    async def _update_product_mapping(self, plytix_product: PlytixProduct, webflow_id: str, collection_id: str):
        """Update existing product mapping"""
        from sqlalchemy import select, update
        
        stmt = select(ProductMapping).where(
            ProductMapping.plytix_product_id == plytix_product.id
        )
        result = await self.db.execute(stmt)
        mapping = result.scalar_one_or_none()
        
        if mapping:
            mapping.webflow_product_id = webflow_id
            mapping.webflow_collection_id = collection_id
            mapping.last_updated = datetime.utcnow()
            await self.db.commit()
    
    async def _update_variant_mappings(self, plytix_product: PlytixProduct):
        """Update variant mappings for a product"""
        # Get product mapping
        from sqlalchemy import select
        
        stmt = select(ProductMapping).where(
            ProductMapping.plytix_product_id == plytix_product.id
        )
        result = await self.db.execute(stmt)
        product_mapping = result.scalar_one_or_none()
        
        if not product_mapping:
            return
        
        # Update or create variant mappings
        for variant in plytix_product.variants:
            stmt = select(VariantMapping).where(
                VariantMapping.plytix_variant_id == variant.id
            )
            result = await self.db.execute(stmt)
            variant_mapping = result.scalar_one_or_none()
            
            if variant_mapping:
                # Update existing mapping
                variant_mapping.variant_sku = variant.sku
                variant_mapping.variant_attributes = variant.attributes
                variant_mapping.price_cents = int((variant.price or 0) * 100)
                variant_mapping.inventory_quantity = variant.inventory
                variant_mapping.last_synced = datetime.utcnow()
            else:
                # Create new mapping
                new_mapping = VariantMapping(
                    product_mapping_id=product_mapping.id,
                    plytix_variant_id=variant.id,
                    variant_sku=variant.sku,
                    variant_attributes=variant.attributes,
                    price_cents=int((variant.price or 0) * 100),
                    inventory_quantity=variant.inventory
                )
                self.db.add(new_mapping)
        
        await self.db.commit()
    
    async def _log_error(self, sync_state: SyncState, product: PlytixProduct, error_message: str):
        """Log synchronization error"""
        error = SyncError(
            sync_state_id=sync_state.id,
            plytix_product_id=product.id,
            error_type="sync_error",
            error_message=error_message,
            error_data={"product_sku": product.sku, "product_name": product.label}
        )
        self.db.add(error)
        await self.db.commit()