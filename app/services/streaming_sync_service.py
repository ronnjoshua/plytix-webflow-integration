from typing import List, Optional, Dict, AsyncGenerator
from datetime import datetime
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import gc

from app.clients.plytix_client import PlytixClient
from app.clients.webflow_client import WebflowClient
from app.services.variant_service import VariantService
from app.services.transform_service import TransformService
from app.services.collection_mapping_service import CollectionMappingService
from app.services.field_mapping_service import FieldMappingService
from app.services.cache_service import CacheService
from app.models.database import SyncState, ProductMapping, VariantMapping, SyncError
from app.models.plytix import PlytixProduct
from app.core.exceptions import SyncError as SyncException

logger = structlog.get_logger()

class StreamingSyncService:
    """Memory-efficient sync service for large product catalogs (1000+ products)"""
    
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
        self.cache_service = CacheService()
        
        # Large-scale optimization settings
        self.chunk_size = 25  # Process products in chunks to manage memory
        self.max_concurrent_products = 3  # Limit concurrent processing
        self.checkpoint_interval = 100  # Save progress every N products
        
    async def close(self):
        """Close all connections and clean up resources"""
        await self.plytix_client.close()
        await self.webflow_client.close()
        await self.field_mapping_service.asset_handler.close()
        await self.cache_service.close()
    
    async def run_large_scale_sync(self, test_mode: bool = False) -> SyncState:
        """Run memory-efficient sync for large product catalogs"""
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
            logger.info("Starting large-scale sync", chunk_size=self.chunk_size)
            
            # Get last successful sync time for delta sync
            last_sync_time = await self._get_last_sync_time()
            
            # Initialize Webflow cache once
            await self.webflow_client._initialize_products_cache()
            logger.info("Webflow products cache initialized")
            
            # Process products in streaming fashion
            total_processed = 0
            total_variants = 0
            total_errors = 0
            updated_product_ids = []
            
            async for chunk_result in self._stream_product_chunks(None, test_mode):  # Disable delta sync for now
                # Process chunk
                chunk_processed = chunk_result.get("processed", 0)
                chunk_variants = chunk_result.get("variants", 0)
                chunk_errors = chunk_result.get("errors", 0)
                chunk_updated_ids = chunk_result.get("updated_ids", [])
                
                total_processed += chunk_processed
                total_variants += chunk_variants
                total_errors += chunk_errors
                updated_product_ids.extend(chunk_updated_ids)
                
                # Update sync state regularly
                sync_state.products_processed = total_processed
                sync_state.variants_processed = total_variants
                sync_state.errors_count = total_errors
                await self.db.commit()
                
                logger.info("Chunk completed", 
                           chunk_processed=chunk_processed,
                           total_processed=total_processed,
                           total_variants=total_variants,
                           total_errors=total_errors)
                
                # Checkpoint: publish products in batches to avoid memory buildup
                if len(updated_product_ids) >= 50:
                    await self._publish_product_batch(updated_product_ids[:50])
                    updated_product_ids = updated_product_ids[50:]
                
                # Force garbage collection after each chunk
                gc.collect()
            
            # Publish remaining products
            if updated_product_ids and self.settings.ENABLE_AUTO_PUBLISH:
                await self._publish_product_batch(updated_product_ids)
            
            # Complete sync
            end_time = datetime.utcnow()
            sync_state.status = "completed"
            sync_state.sync_duration_seconds = int((end_time - start_time).total_seconds())
            sync_state.last_sync_time = end_time
            await self.db.commit()
            
            logger.info("Large-scale sync completed", 
                       products_processed=total_processed,
                       variants_processed=total_variants,
                       errors=total_errors,
                       duration_seconds=sync_state.sync_duration_seconds)
            
            return sync_state
            
        except Exception as e:
            sync_state.status = "failed"
            sync_state.sync_duration_seconds = int((datetime.utcnow() - start_time).total_seconds())
            await self.db.commit()
            
            logger.error("Large-scale sync failed", error=str(e))
            raise SyncException(f"Large-scale sync failed: {str(e)}")
    
    async def _stream_product_chunks(self, 
                                   since: Optional[datetime] = None, 
                                   test_mode: bool = False) -> AsyncGenerator[Dict, None]:
        """Stream products in manageable chunks to avoid memory issues"""
        
        page = 1
        page_size = 50  # Larger page size for basic fetching
        has_more = True
        
        while has_more:
            try:
                logger.info("Fetching product chunk", page=page, page_size=page_size)
                
                # Fetch basic product list for this page
                chunk_products = await self._fetch_product_page(page, page_size, since)
                
                if not chunk_products:
                    logger.info("No more products found", page=page)
                    has_more = False
                    break
                
                # Process this chunk
                chunk_result = await self._process_product_chunk(chunk_products, test_mode)
                
                yield chunk_result
                
                # Check if we should continue
                if len(chunk_products) < page_size:
                    has_more = False
                else:
                    page += 1
                
                # Add delay between chunks to manage API rate limits
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error("Failed to process product chunk", page=page, error=str(e))
                # Continue with next page on error
                page += 1
                if page > 50:  # Safety limit
                    logger.error("Too many page failures, stopping")
                    break
    
    async def _fetch_product_page(self, 
                                 page: int, 
                                 page_size: int, 
                                 since: Optional[datetime] = None) -> List[Dict]:
        """Fetch a single page of products"""
        try:
            # Build filters in correct Plytix format: array of arrays
            filters = None
            
            if since:
                # Format date for Plytix API (YYYY-MM-DD format, no timezone)
                since_str = since.strftime("%Y-%m-%d")
                # Correct Plytix format: array of arrays of filter objects
                filters = [[{
                    "field": "modified",  # Use 'modified' as per Plytix docs
                    "operator": "gt", 
                    "value": since_str
                }]]
            
            # Fetch page
            response_data = await self.plytix_client.search_products(
                page=page, 
                page_size=page_size,
                filters=filters
            )
            
            products_data = response_data.get("data", [])
            logger.debug("Fetched product page", 
                        page=page, 
                        products_count=len(products_data),
                        filters_used=bool(filters))
            
            return products_data
            
        except Exception as e:
            logger.error("Failed to fetch product page", page=page, error=str(e))
            return []
    
    async def _process_product_chunk(self, products_data: List[Dict], test_mode: bool = False) -> Dict:
        """Process a chunk of products with memory management"""
        
        processed_count = 0
        variant_count = 0
        error_count = 0
        updated_product_ids = []
        
        # Split chunk into smaller sub-chunks for processing
        sub_chunk_size = self.chunk_size if not test_mode else 5
        
        for i in range(0, len(products_data), sub_chunk_size):
            sub_chunk = products_data[i:i + sub_chunk_size]
            
            # Pre-filter: only get SKUs that exist in Webflow
            skus = [self.field_mapping_service.get_sku_from_product(product_data) 
                   for product_data in sub_chunk]
            
            webflow_mapping = await self.webflow_client.bulk_check_products_exist(skus)
            
            # Filter products that exist in Webflow
            products_to_process = []
            for j, product_data in enumerate(sub_chunk):
                sku = skus[j]
                if webflow_mapping.get(sku):
                    products_to_process.append((product_data, webflow_mapping[sku]))
            
            if not products_to_process:
                logger.debug("No products in sub-chunk exist in Webflow", sub_chunk_size=len(sub_chunk))
                continue
            
            # Process sub-chunk with controlled concurrency
            sub_chunk_results = await self._process_sub_chunk_concurrent(products_to_process)
            
            # Aggregate results
            for result in sub_chunk_results:
                if result.get("success"):
                    processed_count += 1
                    variant_count += result.get("variant_count", 0)
                    if result.get("webflow_id"):
                        updated_product_ids.append(result["webflow_id"])
                else:
                    error_count += 1
            
            # Memory cleanup between sub-chunks
            del sub_chunk, products_to_process, sub_chunk_results
            gc.collect()
        
        return {
            "processed": processed_count,
            "variants": variant_count,
            "errors": error_count,
            "updated_ids": updated_product_ids
        }
    
    async def _process_sub_chunk_concurrent(self, products_with_ids: List[tuple]) -> List[Dict]:
        """Process sub-chunk with controlled concurrency"""
        
        semaphore = asyncio.Semaphore(self.max_concurrent_products)
        
        async def process_single_product(product_data: Dict, webflow_id: str) -> Dict:
            async with semaphore:
                try:
                    # Convert to PlytixProduct and enrich
                    product = PlytixProduct(**product_data)
                    
                    # Add delay between products
                    await asyncio.sleep(0.8)
                    
                    # Enrich with details and variants
                    await self.plytix_client._enrich_product_details(product)
                    
                    await asyncio.sleep(0.5)
                    
                    # Fetch variants
                    try:
                        variants = await self.plytix_client.get_product_variants(product.id)
                        product.variants = variants
                    except Exception as e:
                        logger.warning("Failed to fetch variants", product_id=product.id, error=str(e))
                        product.variants = []
                    
                    # Sync to Webflow
                    result = await self._sync_single_product_memory_efficient(product, webflow_id)
                    
                    if result:
                        return {
                            "success": True,
                            "webflow_id": result.get("webflow_id"),
                            "variant_count": len(product.variants),
                            "action": result.get("action", "updated")
                        }
                    else:
                        return {"success": False, "error": "Sync returned no result"}
                
                except Exception as e:
                    logger.error("Failed to process product in sub-chunk", 
                               product_id=product_data.get("id", "unknown"), 
                               error=str(e))
                    return {"success": False, "error": str(e)}
        
        # Process all products in sub-chunk
        tasks = [process_single_product(product_data, webflow_id) 
                for product_data, webflow_id in products_with_ids]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append({"success": False, "error": str(result)})
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _sync_single_product_memory_efficient(self, 
                                                   product: PlytixProduct, 
                                                   webflow_id: str) -> Optional[Dict]:
        """Memory-efficient version of single product sync"""
        
        try:
            # Validate product data
            is_valid, validation_errors = self.variant_service.validate_variant_data(product)
            if not is_valid:
                logger.warning("Product validation failed", 
                             product_id=product.id, 
                             errors=validation_errors)
                return None
            
            # Get collection
            target_collection_id = await self.collection_mapping_service.get_collection_for_product(product)
            
            # Check content hash for changes
            product_content = product.model_dump() if hasattr(product, 'model_dump') else product.__dict__
            current_hash = self.cache_service.generate_content_hash(product_content)
            cached_hash = await self.cache_service.get_product_hash(product.id)
            
            if cached_hash == current_hash:
                logger.debug("Product unchanged, skipping", product_id=product.id)
                return {"webflow_id": webflow_id, "action": "skipped"}
            
            # Process variants and transform
            if product.variants:
                attributes_map = self.variant_service.extract_variant_attributes(product.variants)
                sku_properties = self.variant_service.create_sku_properties(attributes_map)
                sku_matrix = self.variant_service.generate_sku_matrix(product, sku_properties)
            else:
                sku_properties = []
                sku_matrix = self.variant_service.generate_sku_matrix(product, [])
            
            # Transform to Webflow format
            webflow_data = self.field_mapping_service.transform_product_data(product)
            
            # Minimal asset processing for large scale
            plytix_data = product_content
            processed_assets = await self.field_mapping_service.process_product_assets(
                plytix_data, 
                use_webflow_upload=True
            )
            webflow_data.update(processed_assets)
            
            webflow_product = self.transform_service.transform_product(
                product, sku_properties, sku_matrix, webflow_data
            )
            
            # Update product
            updated_product = await self.webflow_client.update_product(
                webflow_id, webflow_product, 
                plytix_product_data=plytix_data, 
                collection_id=target_collection_id
            )
            
            # Update mappings (bulk update later for efficiency)
            await self._update_product_mapping_efficient(product, updated_product.id, target_collection_id)
            
            # Cache new hash
            await self.cache_service.cache_product_hashes({product.id: current_hash}, ttl_minutes=60)
            
            return {"webflow_id": updated_product.id, "action": "updated"}
            
        except Exception as e:
            logger.error("Failed to sync product", product_id=product.id, error=str(e))
            raise
    
    async def _update_product_mapping_efficient(self, 
                                               product: PlytixProduct, 
                                               webflow_id: str, 
                                               collection_id: str):
        """Efficient product mapping update for large scale"""
        from sqlalchemy import select
        
        # Check if mapping exists
        stmt = select(ProductMapping).where(ProductMapping.plytix_product_id == product.id)
        result = await self.db.execute(stmt)
        mapping = result.scalar_one_or_none()
        
        if mapping:
            mapping.webflow_product_id = webflow_id
            mapping.webflow_collection_id = collection_id
            mapping.last_updated = datetime.utcnow()
        else:
            mapping = ProductMapping(
                plytix_product_id=product.id,
                webflow_product_id=webflow_id,
                plytix_sku=product.sku,
                product_name=product.label or product.name,
                webflow_collection_id=collection_id
            )
            self.db.add(mapping)
        
        # Commit in batches for efficiency
        await self.db.commit()
    
    async def _publish_product_batch(self, product_ids: List[str]):
        """Publish products in batches"""
        try:
            if self.settings.ENABLE_AUTO_PUBLISH and product_ids:
                logger.info("Publishing product batch", count=len(product_ids))
                await self.webflow_client.publish_items(product_ids)
                logger.info("Product batch published successfully")
        except Exception as e:
            logger.warning("Failed to publish product batch", error=str(e))
    
    async def _get_last_sync_time(self) -> Optional[datetime]:
        """Get the timestamp of the last successful sync"""
        from sqlalchemy import select, desc
        
        stmt = select(SyncState).where(
            SyncState.status == "completed"
        ).order_by(desc(SyncState.created_at)).limit(1)
        
        result = await self.db.execute(stmt)
        last_sync = result.scalar_one_or_none()
        
        return last_sync.last_sync_time if last_sync else None