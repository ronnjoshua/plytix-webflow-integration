import re
from typing import List, Dict, Any, Optional
import structlog

from app.models.plytix import PlytixProduct
from app.models.webflow import WebflowProduct, WebflowSKUProperty, WebflowSKU

logger = structlog.get_logger()

class TransformService:
    """Service for transforming data between Plytix and Webflow formats"""
    
    def transform_product(
        self, 
        plytix_product: PlytixProduct,
        sku_properties: List[WebflowSKUProperty],
        sku_matrix: List[WebflowSKU],
        field_mapped_data: Optional[Dict[str, Any]] = None
    ) -> WebflowProduct:
        """Transform Plytix product to Webflow format with enhanced field mapping"""
        
        # Use field-mapped data if available, otherwise fallback to standard mapping
        if field_mapped_data:
            name = field_mapped_data.get('name', plytix_product.label)
            slug = field_mapped_data.get('slug', self._generate_slug(plytix_product.label))
            description = field_mapped_data.get('description', self._clean_description(plytix_product.description))
            main_image = field_mapped_data.get('main-image', plytix_product.images[0] if plytix_product.images else None)
            
            # Create base product data with mapped fields
            product_data = {
                'name': name,
                'slug': slug,
                'description': description,
                'product_type': "Advanced" if sku_properties else "Basic",
                'sku_properties': sku_properties,
                'skus': sku_matrix,
                'main_image': main_image
            }
            
            # Add all custom mapped fields
            for field, value in field_mapped_data.items():
                if field not in product_data and value is not None:
                    product_data[field] = value
            
            webflow_product = WebflowProduct(**product_data)
        else:
            # Fallback to standard mapping
            slug = self._generate_slug(plytix_product.label)
            description = self._clean_description(plytix_product.description)
            
            webflow_product = WebflowProduct(
                name=plytix_product.label,
                slug=slug,
                description=description,
                product_type="Advanced" if sku_properties else "Basic",
                sku_properties=sku_properties,
                skus=sku_matrix,
                main_image=plytix_product.images[0] if plytix_product.images else None
            )
        
        logger.debug("Transformed product", 
                    plytix_sku=plytix_product.sku,
                    webflow_name=webflow_product.name,
                    variant_count=len(sku_matrix))
        
        return webflow_product
    
    def _generate_slug(self, name: str) -> str:
        """Generate URL-friendly slug from product name"""
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', name.lower())
        slug = re.sub(r'\s+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        return slug.strip('-')
    
    def _clean_description(self, description: str) -> str:
        """Clean and format product description"""
        if not description:
            return ""
        
        # Remove excessive whitespace and clean up formatting
        cleaned = re.sub(r'\s+', ' ', description.strip())
        return cleaned