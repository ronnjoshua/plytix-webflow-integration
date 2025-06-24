from typing import List, Dict, Set, Tuple, Any
import structlog
from itertools import product as itertools_product

from app.models.plytix import PlytixProduct, PlytixVariant
from app.models.webflow import WebflowSKUProperty, WebflowSKU, WebflowPrice, WebflowInventory

logger = structlog.get_logger()

class VariantService:
    """Service for processing product variants and creating SKU matrices"""
    
    def extract_variant_attributes(self, variants: List[PlytixVariant]) -> Dict[str, Set[str]]:
        """Extract all unique attributes and their values from variants"""
        attributes_map = {}
        
        for variant in variants:
            for attr_name, attr_value in variant.attributes.items():
                if attr_name not in attributes_map:
                    attributes_map[attr_name] = set()
                attributes_map[attr_name].add(str(attr_value))
        
        logger.debug("Extracted variant attributes", attributes=attributes_map)
        return attributes_map
    
    def create_sku_properties(self, attributes_map: Dict[str, Set[str]]) -> List[WebflowSKUProperty]:
        """Convert Plytix attributes to Webflow SKU properties"""
        sku_properties = []
        
        for attr_name, attr_values in attributes_map.items():
            # Sort values for consistent ordering
            sorted_values = sorted(list(attr_values))
            
            sku_property = WebflowSKUProperty(
                name=attr_name.title(),  # Capitalize first letter
                enum=sorted_values
            )
            sku_properties.append(sku_property)
        
        logger.debug("Created SKU properties", count=len(sku_properties))
        return sku_properties
    
    def generate_sku_matrix(
        self, 
        product: PlytixProduct,
        sku_properties: List[WebflowSKUProperty]
    ) -> List[WebflowSKU]:
        """Generate complete SKU matrix for Webflow"""
        if not sku_properties:
            # Simple product without variants
            return self._create_simple_product_sku(product)
        
        # Create mapping of variant attributes to variant data
        variant_lookup = {}
        for variant in product.variants:
            # Create a key from sorted attribute values
            attr_key = tuple(sorted(variant.attributes.items()))
            variant_lookup[attr_key] = variant
        
        # Generate all possible combinations
        property_names = [prop.name for prop in sku_properties]
        property_values = [prop.enum for prop in sku_properties]
        
        skus = []
        for combination in itertools_product(*property_values):
            # Create attribute mapping for this combination
            sku_values = dict(zip(property_names, combination))
            
            # Find matching Plytix variant
            # Convert back to original attribute format for lookup
            lookup_key = tuple(sorted([
                (name.lower(), value) for name, value in sku_values.items()
            ]))
            
            variant = variant_lookup.get(lookup_key)
            
            if variant:
                # Use actual variant data
                sku = WebflowSKU(
                    sku=variant.sku,
                    price=WebflowPrice(
                        value=int((variant.price or product.price or 0) * 100),  # Convert to cents
                        unit="USD"
                    ),
                    inventory=WebflowInventory(
                        type="finite",
                        quantity=variant.inventory or 0
                    ),
                    sku_values=sku_values
                )
            else:
                # Create placeholder SKU for missing combination
                placeholder_sku = f"{product.sku}-{'-'.join(combination)}"
                sku = WebflowSKU(
                    sku=placeholder_sku,
                    price=WebflowPrice(
                        value=int((product.price or 0) * 100),  # Use base price
                        unit="USD"
                    ),
                    inventory=WebflowInventory(
                        type="finite",
                        quantity=0  # No stock for missing combinations
                    ),
                    sku_values=sku_values
                )
                
                logger.warning("Created placeholder SKU for missing variant", 
                             sku=placeholder_sku, combination=combination)
            
            skus.append(sku)
        
        logger.info("Generated SKU matrix", 
                   product_sku=product.sku, 
                   total_skus=len(skus),
                   actual_variants=len(product.variants))
        
        return skus
    
    def _create_simple_product_sku(self, product: PlytixProduct) -> List[WebflowSKU]:
        """Create single SKU for products without variants"""
        sku = WebflowSKU(
            sku=product.sku,
            price=WebflowPrice(
                value=int((product.price or 0) * 100),
                unit="USD"
            ),
            inventory=WebflowInventory(
                type="finite",
                quantity=getattr(product, 'inventory', 0)
            ),
            sku_values={}
        )
        return [sku]
    
    def validate_variant_data(self, product: PlytixProduct) -> Tuple[bool, List[str]]:
        """Validate variant data consistency"""
        errors = []
        
        # Check for missing SKUs
        for variant in product.variants:
            if not variant.sku:
                errors.append(f"Variant missing SKU: {variant.id}")
        
        # Check for duplicate SKUs
        skus = [v.sku for v in product.variants if v.sku]
        if len(skus) != len(set(skus)):
            errors.append("Duplicate SKUs found in variants")
        
        # Check for missing required attributes
        if product.variants:
            all_attributes = set()
            for variant in product.variants:
                all_attributes.update(variant.attributes.keys())
            
            for variant in product.variants:
                missing_attrs = all_attributes - set(variant.attributes.keys())
                if missing_attrs:
                    errors.append(f"Variant {variant.sku} missing attributes: {missing_attrs}")
        
        return len(errors) == 0, errors