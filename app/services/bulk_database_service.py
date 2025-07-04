from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload

from app.models.database import ProductMapping, VariantMapping, SyncError, SyncState
from app.models.plytix import PlytixProduct, PlytixVariant

logger = structlog.get_logger()

class BulkDatabaseService:
    """Optimized database operations for large-scale syncing"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def bulk_upsert_product_mappings(self, 
                                         products: List[PlytixProduct], 
                                         webflow_ids: Dict[str, str],
                                         collection_id: str) -> None:
        """Bulk upsert product mappings using efficient database operations"""
        
        if not products:
            return
        
        mappings_data = []
        for product in products:
            webflow_id = webflow_ids.get(product.id)
            if webflow_id:
                mappings_data.append({
                    'plytix_product_id': product.id,
                    'webflow_product_id': webflow_id,
                    'plytix_sku': product.sku,
                    'product_name': product.label or product.name,
                    'webflow_collection_id': collection_id,
                    'last_updated': datetime.utcnow(),
                    'created_at': datetime.utcnow()
                })
        
        if not mappings_data:
            return
        
        try:
            # Use PostgreSQL UPSERT (ON CONFLICT) for efficiency
            stmt = pg_insert(ProductMapping).values(mappings_data)
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=['plytix_product_id'],
                set_={
                    'webflow_product_id': stmt.excluded.webflow_product_id,
                    'webflow_collection_id': stmt.excluded.webflow_collection_id,
                    'last_updated': stmt.excluded.last_updated
                }
            )
            
            await self.db.execute(upsert_stmt)
            await self.db.commit()
            
            logger.info("Bulk upserted product mappings", count=len(mappings_data))
            
        except Exception as e:
            # Fallback for non-PostgreSQL databases
            logger.warning("PostgreSQL upsert failed, using fallback", error=str(e))
            await self._fallback_upsert_product_mappings(mappings_data)
    
    async def _fallback_upsert_product_mappings(self, mappings_data: List[Dict]) -> None:
        """Fallback upsert for non-PostgreSQL databases"""
        
        for mapping_data in mappings_data:
            # Check if exists
            stmt = select(ProductMapping).where(
                ProductMapping.plytix_product_id == mapping_data['plytix_product_id']
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update
                existing.webflow_product_id = mapping_data['webflow_product_id']
                existing.webflow_collection_id = mapping_data['webflow_collection_id']
                existing.last_updated = mapping_data['last_updated']
            else:
                # Insert
                new_mapping = ProductMapping(**mapping_data)
                self.db.add(new_mapping)
        
        await self.db.commit()
    
    async def bulk_upsert_variant_mappings(self, 
                                         products: List[PlytixProduct],
                                         product_mapping_ids: Dict[str, int]) -> None:
        """Bulk upsert variant mappings"""
        
        variants_data = []
        
        for product in products:
            product_mapping_id = product_mapping_ids.get(product.id)
            if not product_mapping_id or not product.variants:
                continue
            
            for variant in product.variants:
                variants_data.append({
                    'product_mapping_id': product_mapping_id,
                    'plytix_variant_id': variant.id,
                    'variant_sku': variant.sku,
                    'variant_attributes': variant.attributes or {},
                    'price_cents': int((variant.price or 0) * 100),
                    'inventory_quantity': variant.inventory or 0,
                    'last_synced': datetime.utcnow(),
                    'created_at': datetime.utcnow()
                })
        
        if not variants_data:
            return
        
        try:
            # PostgreSQL bulk upsert
            stmt = pg_insert(VariantMapping).values(variants_data)
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=['plytix_variant_id'],
                set_={
                    'variant_sku': stmt.excluded.variant_sku,
                    'variant_attributes': stmt.excluded.variant_attributes,
                    'price_cents': stmt.excluded.price_cents,
                    'inventory_quantity': stmt.excluded.inventory_quantity,
                    'last_synced': stmt.excluded.last_synced
                }
            )
            
            await self.db.execute(upsert_stmt)
            await self.db.commit()
            
            logger.info("Bulk upserted variant mappings", count=len(variants_data))
            
        except Exception as e:
            logger.warning("PostgreSQL variant upsert failed, using fallback", error=str(e))
            await self._fallback_upsert_variant_mappings(variants_data)
    
    async def _fallback_upsert_variant_mappings(self, variants_data: List[Dict]) -> None:
        """Fallback variant upsert for non-PostgreSQL databases"""
        
        for variant_data in variants_data:
            stmt = select(VariantMapping).where(
                VariantMapping.plytix_variant_id == variant_data['plytix_variant_id']
            )
            result = await self.db.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update
                for key, value in variant_data.items():
                    if key not in ['plytix_variant_id', 'created_at']:
                        setattr(existing, key, value)
            else:
                # Insert
                new_variant = VariantMapping(**variant_data)
                self.db.add(new_variant)
        
        await self.db.commit()
    
    async def get_product_mappings_bulk(self, plytix_product_ids: List[str]) -> Dict[str, ProductMapping]:
        """Get multiple product mappings efficiently"""
        
        if not plytix_product_ids:
            return {}
        
        stmt = select(ProductMapping).where(
            ProductMapping.plytix_product_id.in_(plytix_product_ids)
        )
        
        result = await self.db.execute(stmt)
        mappings = result.scalars().all()
        
        return {mapping.plytix_product_id: mapping for mapping in mappings}
    
    async def get_variant_mappings_bulk(self, plytix_product_ids: List[str]) -> Dict[str, List[VariantMapping]]:
        """Get variant mappings for multiple products efficiently"""
        
        if not plytix_product_ids:
            return {}
        
        # First get product mappings
        product_mappings = await self.get_product_mappings_bulk(plytix_product_ids)
        product_mapping_ids = [m.id for m in product_mappings.values()]
        
        if not product_mapping_ids:
            return {}
        
        # Get variant mappings with product mapping relationship
        stmt = select(VariantMapping).options(
            selectinload(VariantMapping.product_mapping)
        ).where(
            VariantMapping.product_mapping_id.in_(product_mapping_ids)
        )
        
        result = await self.db.execute(stmt)
        variant_mappings = result.scalars().all()
        
        # Group by plytix product ID
        grouped_variants = {}
        for variant_mapping in variant_mappings:
            plytix_product_id = variant_mapping.product_mapping.plytix_product_id
            if plytix_product_id not in grouped_variants:
                grouped_variants[plytix_product_id] = []
            grouped_variants[plytix_product_id].append(variant_mapping)
        
        return grouped_variants
    
    async def bulk_log_sync_errors(self, 
                                  sync_state_id: int, 
                                  errors: List[Dict[str, Any]]) -> None:
        """Bulk insert sync errors for efficiency"""
        
        if not errors:
            return
        
        error_data = []
        for error in errors:
            error_data.append({
                'sync_state_id': sync_state_id,
                'plytix_product_id': error.get('product_id'),
                'error_type': error.get('error_type', 'sync_error'),
                'error_message': error.get('error_message', ''),
                'error_data': error.get('error_data', {}),
                'created_at': datetime.utcnow()
            })
        
        # Bulk insert
        stmt = insert(SyncError).values(error_data)
        await self.db.execute(stmt)
        await self.db.commit()
        
        logger.info("Bulk logged sync errors", count=len(error_data))
    
    async def optimize_database_for_large_sync(self) -> None:
        """Optimize database settings for large sync operations"""
        
        try:
            # Increase work_mem for this session (PostgreSQL)
            await self.db.execute("SET work_mem = '256MB'")
            
            # Disable synchronous commit for faster writes (use with caution)
            await self.db.execute("SET synchronous_commit = OFF")
            
            # Increase checkpoint segments
            await self.db.execute("SET checkpoint_segments = 64")
            
            logger.info("Database optimized for large sync operations")
            
        except Exception as e:
            # Not all databases support these optimizations
            logger.warning("Database optimization not supported", error=str(e))
    
    async def reset_database_settings(self) -> None:
        """Reset database settings after large sync"""
        
        try:
            await self.db.execute("RESET work_mem")
            await self.db.execute("RESET synchronous_commit") 
            await self.db.execute("RESET checkpoint_segments")
            
            logger.info("Database settings reset")
            
        except Exception as e:
            logger.warning("Database reset not supported", error=str(e))
    
    async def get_sync_statistics(self, days: int = 7) -> Dict[str, Any]:
        """Get sync statistics for monitoring"""
        
        from sqlalchemy import func
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get sync state statistics
        sync_stats_stmt = select(
            func.count(SyncState.id).label('total_syncs'),
            func.sum(SyncState.products_processed).label('total_products_processed'),
            func.sum(SyncState.variants_processed).label('total_variants_processed'),
            func.sum(SyncState.errors_count).label('total_errors'),
            func.avg(SyncState.sync_duration_seconds).label('avg_duration_seconds')
        ).where(SyncState.created_at >= cutoff_date)
        
        result = await self.db.execute(sync_stats_stmt)
        sync_stats = result.first()
        
        # Get error statistics
        error_stats_stmt = select(
            func.count(SyncError.id).label('total_errors'),
            SyncError.error_type,
        ).where(
            SyncError.created_at >= cutoff_date
        ).group_by(SyncError.error_type)
        
        result = await self.db.execute(error_stats_stmt)
        error_stats = result.all()
        
        return {
            'period_days': days,
            'total_syncs': sync_stats.total_syncs or 0,
            'total_products_processed': sync_stats.total_products_processed or 0,
            'total_variants_processed': sync_stats.total_variants_processed or 0,
            'total_errors': sync_stats.total_errors or 0,
            'avg_duration_seconds': float(sync_stats.avg_duration_seconds or 0),
            'error_breakdown': {error.error_type: error.total_errors for error in error_stats}
        }