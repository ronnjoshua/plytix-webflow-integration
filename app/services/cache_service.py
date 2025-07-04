import json
import pickle
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
import structlog
import redis.asyncio as redis
from contextlib import asynccontextmanager

from app.config.settings import get_settings

logger = structlog.get_logger()

class CacheService:
    """Redis-based caching service for API responses and product data"""
    
    def __init__(self):
        self.settings = get_settings()
        self.redis_client = None
        self._connection_pool = None
        
    async def _get_redis_client(self) -> redis.Redis:
        """Get Redis client with connection pooling"""
        if self.redis_client is None:
            if self._connection_pool is None:
                self._connection_pool = redis.ConnectionPool.from_url(
                    self.settings.REDIS_URL,
                    max_connections=20,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0
                )
            self.redis_client = redis.Redis(connection_pool=self._connection_pool)
        return self.redis_client
    
    async def close(self):
        """Close Redis connections"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
        if self._connection_pool:
            await self._connection_pool.disconnect()
            self._connection_pool = None
    
    # Product caching methods
    async def cache_webflow_products(self, products: List[Dict], ttl_minutes: int = 30) -> None:
        """Cache all Webflow products for bulk lookups"""
        try:
            client = await self._get_redis_client()
            
            # Create product name -> product ID mapping
            product_mapping = {}
            product_details = {}
            
            for product in products:
                product_id = product.get('id')
                product_name = product.get('fieldData', {}).get('name', '')
                
                if product_id and product_name:
                    product_mapping[product_name] = product_id
                    product_details[product_id] = product
            
            # Cache the mapping and details
            await client.setex(
                "webflow:products:name_mapping",
                timedelta(minutes=ttl_minutes),
                json.dumps(product_mapping)
            )
            
            await client.setex(
                "webflow:products:details",
                timedelta(minutes=ttl_minutes),
                json.dumps(product_details)
            )
            
            logger.info("Cached Webflow products", 
                       count=len(products), 
                       ttl_minutes=ttl_minutes)
            
        except Exception as e:
            logger.warning("Failed to cache Webflow products", error=str(e))
    
    async def get_webflow_product_by_name(self, product_name: str) -> Optional[Dict]:
        """Get Webflow product by name from cache"""
        try:
            client = await self._get_redis_client()
            
            # Get the name mapping
            mapping_data = await client.get("webflow:products:name_mapping")
            if not mapping_data:
                return None
            
            product_mapping = json.loads(mapping_data)
            product_id = product_mapping.get(product_name)
            
            if not product_id:
                return None
            
            # Get product details
            details_data = await client.get("webflow:products:details")
            if not details_data:
                return None
            
            product_details = json.loads(details_data)
            return product_details.get(product_id)
            
        except Exception as e:
            logger.warning("Failed to get cached product", 
                         product_name=product_name, 
                         error=str(e))
            return None
    
    async def cache_product_hashes(self, product_hashes: Dict[str, str], ttl_minutes: int = 60) -> None:
        """Cache product content hashes for change detection"""
        try:
            client = await self._get_redis_client()
            
            # Cache individual hashes
            pipe = client.pipeline()
            for product_id, content_hash in product_hashes.items():
                pipe.setex(
                    f"product_hash:{product_id}",
                    timedelta(minutes=ttl_minutes),
                    content_hash
                )
            
            await pipe.execute()
            
            logger.info("Cached product hashes", count=len(product_hashes))
            
        except Exception as e:
            logger.warning("Failed to cache product hashes", error=str(e))
    
    async def get_product_hash(self, product_id: str) -> Optional[str]:
        """Get cached product hash"""
        try:
            client = await self._get_redis_client()
            hash_data = await client.get(f"product_hash:{product_id}")
            return hash_data.decode('utf-8') if hash_data else None
        except Exception as e:
            logger.warning("Failed to get product hash", 
                         product_id=product_id, 
                         error=str(e))
            return None
    
    async def cache_api_response(self, 
                                cache_key: str, 
                                data: Any, 
                                ttl_minutes: int = 15) -> None:
        """Cache API response data"""
        try:
            client = await self._get_redis_client()
            
            # Use pickle for complex Python objects
            serialized_data = pickle.dumps(data)
            
            await client.setex(
                f"api_response:{cache_key}",
                timedelta(minutes=ttl_minutes),
                serialized_data
            )
            
            logger.debug("Cached API response", 
                        cache_key=cache_key, 
                        ttl_minutes=ttl_minutes)
            
        except Exception as e:
            logger.warning("Failed to cache API response", 
                         cache_key=cache_key, 
                         error=str(e))
    
    async def get_api_response(self, cache_key: str) -> Optional[Any]:
        """Get cached API response"""
        try:
            client = await self._get_redis_client()
            
            cached_data = await client.get(f"api_response:{cache_key}")
            if cached_data:
                return pickle.loads(cached_data)
            
            return None
            
        except Exception as e:
            logger.warning("Failed to get cached API response", 
                         cache_key=cache_key, 
                         error=str(e))
            return None
    
    async def cache_product_assets(self, 
                                  product_id: str, 
                                  assets: List[Dict], 
                                  ttl_minutes: int = 120) -> None:
        """Cache product assets"""
        try:
            client = await self._get_redis_client()
            
            await client.setex(
                f"product_assets:{product_id}",
                timedelta(minutes=ttl_minutes),
                json.dumps(assets)
            )
            
            logger.debug("Cached product assets", 
                        product_id=product_id, 
                        asset_count=len(assets))
            
        except Exception as e:
            logger.warning("Failed to cache product assets", 
                         product_id=product_id, 
                         error=str(e))
    
    async def get_product_assets(self, product_id: str) -> Optional[List[Dict]]:
        """Get cached product assets"""
        try:
            client = await self._get_redis_client()
            
            cached_data = await client.get(f"product_assets:{product_id}")
            if cached_data:
                return json.loads(cached_data)
            
            return None
            
        except Exception as e:
            logger.warning("Failed to get cached product assets", 
                         product_id=product_id, 
                         error=str(e))
            return None
    
    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate all cache keys matching a pattern"""
        try:
            client = await self._get_redis_client()
            
            keys = await client.keys(pattern)
            if keys:
                await client.delete(*keys)
                logger.info("Invalidated cache keys", pattern=pattern, count=len(keys))
            
        except Exception as e:
            logger.warning("Failed to invalidate cache pattern", 
                         pattern=pattern, 
                         error=str(e))
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            client = await self._get_redis_client()
            
            # Get info about different cache types
            webflow_keys = await client.keys("webflow:*")
            product_hash_keys = await client.keys("product_hash:*")
            api_response_keys = await client.keys("api_response:*")
            asset_keys = await client.keys("product_assets:*")
            
            return {
                "webflow_cache_keys": len(webflow_keys),
                "product_hash_keys": len(product_hash_keys),
                "api_response_keys": len(api_response_keys),
                "asset_cache_keys": len(asset_keys),
                "total_keys": len(webflow_keys) + len(product_hash_keys) + len(api_response_keys) + len(asset_keys)
            }
            
        except Exception as e:
            logger.warning("Failed to get cache stats", error=str(e))
            return {"error": str(e)}
    
    # Utility methods
    def generate_content_hash(self, content: Dict) -> str:
        """Generate hash for content change detection"""
        import hashlib
        
        # Sort dict keys for consistent hashing
        sorted_content = json.dumps(content, sort_keys=True)
        return hashlib.md5(sorted_content.encode()).hexdigest()
    
    @asynccontextmanager
    async def pipeline(self):
        """Context manager for Redis pipeline operations"""
        client = await self._get_redis_client()
        pipe = client.pipeline()
        try:
            yield pipe
            await pipe.execute()
        except Exception as e:
            await pipe.reset()
            raise e