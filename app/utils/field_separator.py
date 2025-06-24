"""
Field Separator Utility
Clearly separates product-level and SKU-level fields for Webflow API
"""
from typing import Dict, Set, Any, Tuple
import structlog

logger = structlog.get_logger()

class WebflowFieldSeparator:
    """Utility class to separate product-level and SKU-level fields for Webflow API"""
    
    # Based on actual Webflow schema - these are the ONLY valid product-level fields
    VALID_PRODUCT_FIELDS: Set[str] = {
        # Standard Webflow product fields
        "name",
        "description", 
        "slug",
        "shippable",
        "ec-product-type",
        "default-sku",
        "tax-category",
        "category",
        "sku-properties",
        
        # Custom fields that exist in your Webflow collection
        "web-extended-description-2",
        "safety-data-sheet",
        "specification-sheet",
        "manufacturer",
        "warranty-information"
    }
    
    # These are valid SKU-level fields
    VALID_SKU_FIELDS: Set[str] = {
        # Standard Webflow SKU fields
        "sku",
        "name", 
        "slug",
        "price",
        "compare-at-price",
        "inventory",
        "main-image",
        "more-images",
        "download-files",
        "sku-values",
        "product",  # Reference back to product
        
        # Potential custom SKU fields
        "variant-description",
        "barcode",
        "supplier-code",
        "variant-specifications"
    }
    
    @classmethod
    def separate_fields(cls, all_fields: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Separate mixed fields into product-level and SKU-level dictionaries
        
        Args:
            all_fields: Dictionary containing all field mappings
            
        Returns:
            Tuple of (product_fields, sku_fields)
        """
        product_fields = {}
        sku_fields = {}
        skipped_fields = []
        
        for field_name, field_value in all_fields.items():
            if field_name in cls.VALID_PRODUCT_FIELDS:
                product_fields[field_name] = field_value
                logger.debug("Classified as product field", 
                           field=field_name, 
                           value_preview=str(field_value)[:50])
            elif field_name in cls.VALID_SKU_FIELDS:
                sku_fields[field_name] = field_value
                logger.debug("Classified as SKU field", 
                           field=field_name,
                           value_preview=str(field_value)[:50])
            else:
                skipped_fields.append(field_name)
                logger.warning("Unknown field - skipping", 
                             field=field_name,
                             reason="Not in valid product or SKU fields")
        
        logger.info("Field separation complete",
                   product_fields_count=len(product_fields),
                   sku_fields_count=len(sku_fields),
                   skipped_fields_count=len(skipped_fields),
                   product_fields=list(product_fields.keys()),
                   sku_fields=list(sku_fields.keys()),
                   skipped_fields=skipped_fields)
        
        return product_fields, sku_fields
    
    @classmethod
    def filter_product_fields_only(cls, all_fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return only valid product-level fields from a mixed dictionary
        
        Args:
            all_fields: Dictionary containing all field mappings
            
        Returns:
            Dictionary containing only valid product-level fields
        """
        product_fields, _ = cls.separate_fields(all_fields)
        return product_fields
    
    @classmethod
    def filter_sku_fields_only(cls, all_fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return only valid SKU-level fields from a mixed dictionary
        
        Args:
            all_fields: Dictionary containing all field mappings
            
        Returns:
            Dictionary containing only valid SKU-level fields
        """
        _, sku_fields = cls.separate_fields(all_fields)
        return sku_fields
    
    @classmethod
    def is_product_field(cls, field_name: str) -> bool:
        """Check if a field belongs at product level"""
        return field_name in cls.VALID_PRODUCT_FIELDS
    
    @classmethod
    def is_sku_field(cls, field_name: str) -> bool:
        """Check if a field belongs at SKU level"""
        return field_name in cls.VALID_SKU_FIELDS