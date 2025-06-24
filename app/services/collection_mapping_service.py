from typing import Dict, Optional, List
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plytix import PlytixProduct
from app.clients.webflow_client import WebflowClient
from app.config.settings import get_settings

logger = structlog.get_logger()

class CollectionMappingService:
    """Service for dynamic collection mapping based on product attributes"""
    
    def __init__(self, db: AsyncSession, webflow_client: WebflowClient):
        self.db = db
        self.settings = get_settings()
        self.webflow_client = webflow_client
        self._collection_cache: Dict[str, str] = {}
        self._collection_info_cache: Dict[str, Dict] = {}
    
    async def get_collection_for_product(self, product: PlytixProduct) -> str:
        """Get the appropriate collection ID for a product"""
        
        if not self.settings.ENABLE_DYNAMIC_COLLECTIONS:
            # Use default collection
            return self.settings.WEBFLOW_COLLECTION_ID
        
        # Determine collection based on strategy
        strategy = self.settings.COLLECTION_MAPPING_STRATEGY
        
        if strategy == "category":
            return await self._get_collection_by_category(product)
        elif strategy == "brand":
            return await self._get_collection_by_brand(product)
        elif strategy == "product_type":
            return await self._get_collection_by_product_type(product)
        else:
            logger.warning("Unknown collection mapping strategy", strategy=strategy)
            return self.settings.WEBFLOW_COLLECTION_ID
    
    async def _get_collection_by_category(self, product: PlytixProduct) -> str:
        """Map product to collection based on category"""
        category = product.category or "default"
        
        # Check cache first
        cache_key = f"category_{category}"
        if cache_key in self._collection_cache:
            return self._collection_cache[cache_key]
        
        # Find or create collection for this category
        collection_id = await self._find_or_create_collection(
            name=f"Products - {category.title()}",
            slug=f"products-{category.lower().replace(' ', '-')}",
            description=f"Products in the {category} category"
        )
        
        self._collection_cache[cache_key] = collection_id
        return collection_id
    
    async def _get_collection_by_brand(self, product: PlytixProduct) -> str:
        """Map product to collection based on brand"""
        brand = product.brand or "default"
        
        cache_key = f"brand_{brand}"
        if cache_key in self._collection_cache:
            return self._collection_cache[cache_key]
        
        collection_id = await self._find_or_create_collection(
            name=f"{brand.title()} Products",
            slug=f"{brand.lower().replace(' ', '-')}-products",
            description=f"Products from {brand}"
        )
        
        self._collection_cache[cache_key] = collection_id
        return collection_id
    
    async def _get_collection_by_product_type(self, product: PlytixProduct) -> str:
        """Map product to collection based on product type/attributes"""
        # Determine product type from attributes or product data
        product_type = self._determine_product_type(product)
        
        cache_key = f"type_{product_type}"
        if cache_key in self._collection_cache:
            return self._collection_cache[cache_key]
        
        collection_id = await self._find_or_create_collection(
            name=f"{product_type.title()}",
            slug=product_type.lower().replace(' ', '-'),
            description=f"{product_type} products"
        )
        
        self._collection_cache[cache_key] = collection_id
        return collection_id
    
    def _determine_product_type(self, product: PlytixProduct) -> str:
        """Determine product type from product data"""
        # Check product attributes for type indicators
        attributes = product.attributes or {}
        
        # Look for common type indicators
        for key, value in attributes.items():
            key_lower = key.lower()
            if any(type_word in key_lower for type_word in ['type', 'category', 'class']):
                return str(value)
        
        # Fallback to category or default
        return product.category or "general"
    
    async def _find_or_create_collection(self, name: str, slug: str, description: str) -> str:
        """Find existing collection or create new one"""
        try:
            # First, try to find existing collection by name
            collections = await self._get_all_collections()
            
            for collection in collections:
                if collection.get('name', '').lower() == name.lower():
                    collection_id = collection['id']
                    logger.info("Found existing collection", name=name, id=collection_id)
                    return collection_id
            
            # Create new collection if not found
            if self.settings.WEBFLOW_TOKEN != "test_token":  # Only create in production
                collection_id = await self._create_collection(name, slug, description)
                logger.info("Created new collection", name=name, id=collection_id)
                return collection_id
            else:
                # In test mode, use default collection
                logger.info("Test mode: using default collection", name=name)
                return self.settings.WEBFLOW_COLLECTION_ID
                
        except Exception as e:
            logger.error("Failed to find/create collection", name=name, error=str(e))
            # Fallback to default collection
            return self.settings.WEBFLOW_COLLECTION_ID
    
    async def _get_all_collections(self) -> List[Dict]:
        """Get all collections for the site"""
        try:
            endpoint = f"/sites/{self.settings.WEBFLOW_SITE_ID}/collections"
            data = await self.webflow_client._make_request(endpoint)
            return data.get('collections', [])
        except Exception as e:
            logger.error("Failed to get collections", error=str(e))
            return []
    
    async def _create_collection(self, name: str, slug: str, description: str) -> str:
        """Create a new e-commerce collection"""
        collection_data = {
            "displayName": name,
            "singularName": name.rstrip('s'),  # Remove trailing 's' for singular
            "slug": slug,
            "description": description,
            "fields": [
                {
                    "displayName": "Name",
                    "slug": "name",
                    "type": "PlainText",
                    "required": True
                },
                {
                    "displayName": "Slug",
                    "slug": "slug",
                    "type": "PlainText",
                    "required": True
                },
                {
                    "displayName": "SKU",
                    "slug": "sku",
                    "type": "PlainText",
                    "required": True
                },
                {
                    "displayName": "Price",
                    "slug": "price",
                    "type": "Number",
                    "required": True
                },
                {
                    "displayName": "Description",
                    "slug": "description",
                    "type": "RichText",
                    "required": False
                },
                {
                    "displayName": "Main Image",
                    "slug": "main-image",
                    "type": "ImageRef",
                    "required": False
                }
            ]
        }
        
        try:
            endpoint = f"/sites/{self.settings.WEBFLOW_SITE_ID}/collections"
            response = await self.webflow_client._make_request(
                endpoint, 
                method="POST", 
                json_data=collection_data
            )
            return response['id']
        except Exception as e:
            logger.error("Failed to create collection", name=name, error=str(e))
            raise
    
    async def get_collection_mapping_info(self) -> Dict[str, any]:
        """Get information about current collection mappings"""
        return {
            "enabled": self.settings.ENABLE_DYNAMIC_COLLECTIONS,
            "strategy": self.settings.COLLECTION_MAPPING_STRATEGY,
            "default_collection": self.settings.WEBFLOW_COLLECTION_ID,
            "cached_mappings": len(self._collection_cache),
            "cache_keys": list(self._collection_cache.keys())
        }
    
    async def clear_cache(self):
        """Clear the collection mapping cache"""
        self._collection_cache.clear()
        self._collection_info_cache.clear()
        logger.info("Collection mapping cache cleared")