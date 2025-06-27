"""
Enhanced Field Mapping Service for Plytix to Webflow Integration
Provides maintainable and scalable field mapping with automatic discovery
"""
import json
import structlog
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum

from app.models.plytix import PlytixProduct, PlytixVariant
from app.models.webflow import WebflowProduct
from app.utils.asset_handler import AssetHandler

logger = structlog.get_logger()

class FieldType(Enum):
    TEXT = "text"
    PDF = "pdf"
    IMAGE = "image"
    RICH_TEXT = "rich_text"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    ARRAY = "array"

@dataclass
class FieldMapping:
    plytix_field: str
    webflow_field: str
    field_type: FieldType
    required: bool = False
    transform_function: Optional[str] = None
    default_value: Optional[Any] = None
    clearable: bool = False  # Whether this field can be auto-cleared when removed from Plytix

class FieldMappingService:
    """Enhanced field mapping service with automatic discovery and validation"""
    
    def __init__(self, mapping_file: str = "field_mappings.json", webflow_client=None):
        self.mapping_file = Path(mapping_file)
        self.field_mappings: Dict[str, FieldMapping] = {}
        self.discovered_images: Dict[str, str] = {}
        self.sku_field_mapping = {}
        self.webflow_client = webflow_client
        self.asset_handler = AssetHandler(webflow_client=webflow_client)
        self.load_mappings()
    
    def load_mappings(self) -> None:
        """Load field mappings from JSON configuration file"""
        try:
            if self.mapping_file.exists():
                with open(self.mapping_file, 'r') as f:
                    config = json.load(f)
                    
                self._process_field_mappings(config.get('field_mappings', {}))
                self._process_image_mappings(config.get('image_mapping', {}))
                self.matching_strategy = config.get('matching_strategy', 'sku')
                
                logger.info(
                    "Field mappings loaded", 
                    total_mappings=len(self.field_mappings),
                    matching_strategy=self.matching_strategy
                )
            else:
                logger.warning("Mapping file not found, using defaults", file=str(self.mapping_file))
                self._create_default_mappings()
                
        except Exception as e:
            logger.error("Failed to load field mappings", error=str(e))
            self._create_default_mappings()
    
    def _process_field_mappings(self, mappings: Dict[str, str]) -> None:
        """Process field mappings from configuration"""
        for plytix_field, webflow_field in mappings.items():
            field_type = self._detect_field_type(plytix_field)
            
            # Set clearable flag for PDF fields
            clearable = field_type == FieldType.PDF
            
            self.field_mappings[plytix_field] = FieldMapping(
                plytix_field=plytix_field,
                webflow_field=webflow_field,
                field_type=field_type,
                required=plytix_field in ['sku', 'name', 'price'],
                clearable=clearable
            )
    
    def _process_image_mappings(self, image_config: Dict[str, Any]) -> None:
        """Process image mapping configuration"""
        if image_config.get('discover_automatically', True):
            self.auto_discover_images = True
            self.primary_image_field = image_config.get('primary_image_field', 'main_image')
            self.gallery_images_field = image_config.get('gallery_images_field', 'gallery')
            self.webflow_image_field = image_config.get('webflow_image_field', 'main-image')
    
    def _detect_field_type(self, field_name: str) -> FieldType:
        """Automatically detect field type based on field name patterns"""
        field_lower = field_name.lower()
        
        if any(keyword in field_lower for keyword in ['image', 'photo', 'picture', 'img']):
            return FieldType.IMAGE
        elif any(keyword in field_lower for keyword in ['pdf', 'document', 'sheet', 'manual']):
            return FieldType.PDF
        elif any(keyword in field_lower for keyword in ['description', 'content', 'text']):
            return FieldType.RICH_TEXT
        elif any(keyword in field_lower for keyword in ['price', 'cost', 'weight', 'quantity']):
            return FieldType.NUMBER
        elif any(keyword in field_lower for keyword in ['date', 'time', 'created', 'updated']):
            return FieldType.DATE
        elif any(keyword in field_lower for keyword in ['active', 'enabled', 'visible']):
            return FieldType.BOOLEAN
        else:
            return FieldType.TEXT
    
    def _create_default_mappings(self) -> None:
        """Create default field mappings as fallback"""
        default_mappings = {
            'sku': FieldMapping('sku', 'sku', FieldType.TEXT, required=True),
            'name': FieldMapping('name', 'name', FieldType.TEXT, required=True),
            'description': FieldMapping('description', 'description', FieldType.RICH_TEXT),
            'price': FieldMapping('price', 'price', FieldType.NUMBER),
            'safety_data_sheet': FieldMapping('safety_data_sheet', 'safety-data-sheet', FieldType.PDF, clearable=True),
            'specification_sheet': FieldMapping('specification_sheet', 'specification-sheet', FieldType.PDF, clearable=True),
            'web_extended_description': FieldMapping('web_extended_description', 'web-extended-description', FieldType.RICH_TEXT)
        }
        
        self.field_mappings.update(default_mappings)
        logger.info("Default field mappings created", total=len(default_mappings))
    
    def _should_clear_field(self, plytix_field: str, raw_value: Any, mapping: FieldMapping, 
                           all_data: Dict[str, Any]) -> bool:
        """
        Safely determine if a field should be cleared in Webflow.
        Uses conservative approach with explicit validation.
        """
        logger.debug("Evaluating field for clearing", 
                    plytix_field=plytix_field,
                    field_type=mapping.field_type.value,
                    clearable=mapping.clearable,
                    required=mapping.required,
                    raw_value_type=type(raw_value).__name__,
                    raw_value_preview=str(raw_value)[:100] if raw_value else "None")
        
        # Only consider clearing if the field is explicitly marked as clearable
        if not mapping.clearable:
            logger.debug("Field not clearable", plytix_field=plytix_field)
            return False
        
        # Don't clear required fields
        if mapping.required:
            logger.debug("Field is required, not clearing", plytix_field=plytix_field)
            return False
        
        # Only clear PDF fields for now (conservative approach)
        if mapping.field_type != FieldType.PDF:
            logger.debug("Field is not PDF type, not clearing", 
                        plytix_field=plytix_field, 
                        field_type=mapping.field_type.value)
            return False
        
        # Check if field exists but is explicitly empty/null
        field_exists_but_empty = (
            plytix_field in all_data and 
            (all_data[plytix_field] is None or 
             all_data[plytix_field] == "" or 
             (isinstance(all_data[plytix_field], dict) and not any(all_data[plytix_field].values())))
        )
        
        logger.debug("PDF field clearing evaluation", 
                    plytix_field=plytix_field,
                    field_exists_in_data=plytix_field in all_data,
                    field_value=all_data.get(plytix_field, "NOT_FOUND"),
                    field_exists_but_empty=field_exists_but_empty)
        
        # Additional safety checks for PDF fields
        if mapping.field_type == FieldType.PDF and field_exists_but_empty:
            logger.info("PDF field will be cleared in Webflow", 
                       plytix_field=plytix_field,
                       webflow_field=mapping.webflow_field,
                       reason="Field exists but is explicitly empty")
            return True
        
        logger.debug("Field not being cleared", 
                    plytix_field=plytix_field,
                    reason="Does not meet clearing criteria")
        return False
    
    def _force_include_cleared_pdf_fields(self, all_mapped_fields: Dict[str, Any], combined_dict: Dict[str, Any]) -> None:
        """
        Force inclusion of cleared PDF fields with empty strings.
        This ensures PDF fields are sent to Webflow even when they're empty in Plytix.
        """
        logger.debug("Checking for cleared PDF fields to include", 
                    combined_dict_size=len(combined_dict),
                    current_mapped_fields=len(all_mapped_fields))
        
        pdf_fields_to_check = ['safety_data_sheet', 'specification_sheet']
        
        for plytix_field in pdf_fields_to_check:
            if plytix_field in self.field_mappings:
                mapping = self.field_mappings[plytix_field]
                webflow_field = mapping.webflow_field
                
                # Check if field is already processed
                if webflow_field not in all_mapped_fields:
                    # Check if field exists but is empty/cleared in Plytix
                    raw_value = combined_dict.get(plytix_field)
                    
                    # If field exists but is empty/null, force include with empty string
                    if (plytix_field in combined_dict and 
                        (raw_value is None or 
                         raw_value == "" or 
                         str(raw_value).lower() == 'none' or
                         (isinstance(raw_value, dict) and not any(raw_value.values())))):
                        
                        all_mapped_fields[webflow_field] = ""
                        logger.info("Including cleared PDF field for Webflow update", 
                                   plytix_field=plytix_field,
                                   webflow_field=webflow_field,
                                   reason="PDF field cleared in Plytix")
    
    def discover_image_fields(self, product_data: Dict[str, Any]) -> Dict[str, str]:
        """Automatically discover image fields in product data"""
        discovered_images = {}
        
        # PRIORITY: Check for real images from assets API first
        if 'real_main_image' in product_data:
            logger.info("Discovered REAL image from assets API", 
                       field='real_main_image', value=product_data['real_main_image'])
            discovered_images['real_main_image'] = 'main-image'
        
        for field_name, field_value in product_data.items():
            # Skip the real_main_image as it's already handled above
            if field_name == 'real_main_image':
                continue
            
            logger.debug("Checking field for image", plytix_field=field_name, value_preview=str(field_value)[:100])
            if self._is_image_field(field_name, field_value):
                # Map to appropriate Webflow field
                webflow_field = self._map_image_field(field_name)
                discovered_images[field_name] = webflow_field
                logger.debug("Discovered image field", 
                           plytix_field=field_name, 
                           webflow_field=webflow_field, value_preview=str(field_value)[:100])
            else:
                logger.debug("Field is not an image or was skipped", plytix_field=field_name, value_preview=str(field_value)[:100])
        
        return discovered_images
    
    def _is_image_field(self, field_name: str, field_value: Any) -> bool:
        """Check if a field contains image data, with extra logging"""
        if not field_value:
            logger.debug("Image field is empty or None", plytix_field=field_name)
            return False
        
        field_lower = field_name.lower()
        
        # Check field name patterns
        if any(keyword in field_lower for keyword in ['image', 'photo', 'picture', 'img', 'gallery']):
            logger.debug("Field name pattern matches image", plytix_field=field_name)
            return True
        
        # Check field value patterns (URLs, file extensions)
        if isinstance(field_value, str):
            if any(ext in field_value.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']):
                if "static.plytix.com/template" in field_value or "default" in field_value.lower():
                    logger.debug("Skipping placeholder image", plytix_field=field_name, url=field_value)
                    return False
                logger.debug("Field value is a valid image URL", plytix_field=field_name, url=field_value)
                return True
        
        # Check if it's a list of image URLs
        if isinstance(field_value, list) and field_value:
            first_item = field_value[0]
            if isinstance(first_item, str):
                if any(ext in first_item.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                    logger.debug("Field value is a list of image URLs", plytix_field=field_name, url=first_item)
                    return True
        
        logger.debug("Field is not recognized as image", plytix_field=field_name, value_preview=str(field_value)[:100])
        return False
    
    def _map_image_field(self, plytix_field: str) -> str:
        """Map Plytix image field to appropriate Webflow SKU field (based on actual Webflow schema)"""
        field_lower = plytix_field.lower()
        
        # Based on actual Webflow schema: SKU level has "main-image" and "more-images"
        if any(keyword in field_lower for keyword in ['main', 'primary', 'hero', 'featured', 'thumbnail', 'thumb', 'user_thumb']):
            return 'main-image'  # SKU-level field in Webflow
        elif any(keyword in field_lower for keyword in ['gallery', 'additional', 'extra', 'more']):
            return 'more-images'  # SKU-level field in Webflow (array)
        else:
            return 'main-image'  # Default to main image (SKU-level)
    
    def transform_product_data(self, plytix_product: PlytixProduct) -> Dict[str, Any]:
        """Transform Plytix product data to Webflow format using mappings"""
        webflow_data = {}
        
        # Convert to dict for easier processing
        product_dict = plytix_product.model_dump() if hasattr(plytix_product, 'model_dump') else plytix_product.__dict__
        
        # Enhanced attribute discovery using dynamic extraction
        all_attributes = self.extract_all_attributes_dynamically(product_dict)
        
        # Also check direct attributes for backward compatibility
        attributes = product_dict.get('attributes', {}) or {}
        detailed_attributes = product_dict.get('detailed_attributes', {}) or {}
        
        # Merge all sources, prioritizing dynamic discovery
        field_source = {**attributes, **detailed_attributes, **all_attributes}
        source_name = "dynamic_attributes"
        
        # Log available fields for debugging - always show for products with any field_source
        if field_source:
            product_name = product_dict.get('name', product_dict.get('sku', 'unknown'))
            available_fields = list(field_source.keys())
            logger.warning(f"FIELD_DEBUG: Product {source_name}", 
                          product_name=product_name,
                          total_fields=len(available_fields),
                          field_names=available_fields[:15] if available_fields else [],
                          has_web_extended_description='web_extended_description' in available_fields,
                          has_description='description' in available_fields,
                          has_safety_data_sheet='safety_data_sheet' in available_fields,
                          has_specification_sheet='specification_sheet' in available_fields,
                          source=source_name)
        
        # Merge field_source into main dict for field access
        combined_dict = {**product_dict, **field_source}
        
        # Discover image fields dynamically from both sources
        discovered_images = self.discover_image_fields(combined_dict)
        
        # ENHANCED: Also get images from Plytix assets API (like your working script)
        product_id = product_dict.get('id')
        if product_id:
            assets_images = self.get_images_from_assets_api(product_id)
            discovered_images.update(assets_images)
        
        # Apply configured field mappings - collect ALL fields first, then separate
        from app.utils.field_separator import WebflowFieldSeparator
        
        # Apply configured field mappings
        all_mapped_fields = {}
        for plytix_field, mapping in self.field_mappings.items():
            raw_value = None
            source = "not_found"
            
            # Check field_source first (priority), then top-level
            if plytix_field in field_source:
                raw_value = field_source[plytix_field]
                source = source_name
            elif plytix_field in product_dict:
                raw_value = product_dict[plytix_field]
                source = "top_level"
            
            # Always check if field should be cleared first, regardless of value
            logger.warning("CHECKING FIELD FOR CLEARING", 
                          plytix_field=plytix_field, 
                          field_type=mapping.field_type.value,
                          clearable=mapping.clearable)
            should_clear = self._should_clear_field(plytix_field, raw_value, mapping, combined_dict)
            
            if should_clear:
                # Use empty string to clear PDF field (confirmed working in Postman)
                all_mapped_fields[mapping.webflow_field] = ""
                logger.warning("Safely clearing field in Webflow using empty string", 
                              plytix_field=plytix_field,
                              webflow_field=mapping.webflow_field,
                              field_type=mapping.field_type.value,
                              reason="Field explicitly marked for clearing")
            elif raw_value is not None and raw_value != "":
                transformed_value = self._transform_field_value(raw_value, mapping)
                
                if transformed_value is not None and transformed_value != "":
                    all_mapped_fields[mapping.webflow_field] = transformed_value
                    
                    logger.debug("Mapped field", 
                               plytix_field=plytix_field,
                               webflow_field=mapping.webflow_field,
                               field_type=mapping.field_type.value,
                               source=source,
                               value_preview=str(transformed_value)[:50] + ("..." if len(str(transformed_value)) > 50 else ""))
                else:
                    logger.debug("Field transformation returned empty", 
                               plytix_field=plytix_field,
                               raw_value_type=type(raw_value).__name__,
                               raw_value_preview=str(raw_value)[:100])
            else:
                logger.debug("Field not found or empty", 
                           plytix_field=plytix_field,
                           in_field_source=plytix_field in field_source,
                           in_top_level=plytix_field in product_dict,
                           field_source_count=len(field_source),
                           source_type=source_name,
                           top_level_count=len([k for k, v in product_dict.items() if v is not None]))
        
        # Skip all image and SKU-level field mappings since they don't belong at product level
        skipped_fields = []
        for plytix_field, webflow_field in discovered_images.items():
            skipped_fields.append(f"{plytix_field}→{webflow_field}")
            logger.debug("Skipping image field for product level - will be handled at SKU level", 
                       plytix_field=plytix_field,
                       webflow_field=webflow_field,
                       reason="Images go to SKU level in Webflow")
        
        if skipped_fields:
            logger.info("Skipped SKU-level fields for product", 
                       skipped_count=len(skipped_fields),
                       skipped_fields=skipped_fields)
        
        # FORCED INCLUSION: Add cleared PDF fields with empty strings
        self._force_include_cleared_pdf_fields(all_mapped_fields, combined_dict)
        
        logger.warning("BEFORE_SEPARATION_DEBUG: Fields about to be separated", 
                      all_fields=list(all_mapped_fields.keys()),
                      field_count=len(all_mapped_fields))
        
        # Separate fields into product-level and SKU-level
        webflow_data, sku_data = WebflowFieldSeparator.separate_fields(all_mapped_fields)
        
        logger.warning("AFTER_SEPARATION_DEBUG: Fields after separation", 
                      product_fields=list(webflow_data.keys()),
                      sku_fields=list(sku_data.keys()))
        
        # Store SKU data for later use
        self._last_sku_data = sku_data
        
        # Ensure required fields are present
        self._ensure_required_fields(webflow_data, combined_dict)
        
        logger.info("Product data transformation complete",
                   product_fields=list(webflow_data.keys()),
                   sku_fields=list(sku_data.keys()))
        
        return webflow_data
    
    def _transform_field_value(self, value: Any, mapping: FieldMapping) -> Any:
        """Transform field value based on field type and mapping configuration"""
        if value is None:
            return mapping.default_value
        
        try:
            if mapping.field_type == FieldType.PDF:
                return self._transform_pdf_value(value)
            elif mapping.field_type == FieldType.IMAGE:
                return self._transform_image_value(value)
            elif mapping.field_type == FieldType.RICH_TEXT:
                return self._transform_rich_text_value(value)
            elif mapping.field_type == FieldType.NUMBER:
                return self._transform_number_value(value)
            elif mapping.field_type == FieldType.BOOLEAN:
                return self._transform_boolean_value(value)
            elif mapping.field_type == FieldType.ARRAY:
                return self._transform_array_value(value)
            else:
                return str(value) if value is not None else ""
                
        except Exception as e:
            logger.warning("Field transformation failed", 
                         field=mapping.plytix_field, 
                         error=str(e))
            return mapping.default_value
    
    async def _transform_pdf_value_async(self, value: Any) -> Optional[Dict[str, Any]]:
        """Transform PDF/file field values using AssetHandler"""
        logger.debug("Transforming PDF value", value_type=type(value).__name__, value_preview=str(value)[:100])
        
        try:
            from app.utils.asset_handler import AssetHandler
            asset_handler = AssetHandler()
            
            # Process file using asset handler (direct linking for now)
            result = await asset_handler.process_plytix_file(value, upload_to_webflow=False)
            await asset_handler.close()
            
            if result:
                logger.debug("Successfully transformed PDF using AssetHandler", result=result)
                return result
            else:
                logger.debug("AssetHandler could not process PDF", value=str(value)[:100])
                return None
                
        except Exception as e:
            logger.warning("PDF transformation failed", error=str(e))
            return None
    
    def _transform_pdf_value(self, value: Any) -> Optional[Dict[str, Any]]:
        """Transform PDF/file field values to proper Webflow format (sync version)"""
        logger.debug("Transforming PDF value", value_type=type(value).__name__, value_preview=str(value)[:100])
        
        if isinstance(value, dict):
            # Handle complex PDF object from detailed_attributes
            if 'url' in value:
                # Clean URL to remove /thumb/ (like your working script)
                clean_url = value['url'].replace('/thumb/', '/file/')
                result = {
                    "fileId": value.get('fileId', value.get('id', '')),
                    "url": clean_url,
                    "alt": value.get('name', value.get('filename', 'Document'))
                }
                logger.debug("Transformed PDF from dict with url", result=result)
                return result
            elif 'file_url' in value:
                # Clean URL to remove /thumb/ (like your working script)
                clean_url = value['file_url'].replace('/thumb/', '/file/')
                result = {
                    "fileId": value.get('fileId', value.get('id', '')),
                    "url": clean_url,
                    "alt": value.get('name', value.get('filename', 'Document'))
                }
                logger.debug("Transformed PDF from dict with file_url", result=result)
                return result
            elif value.get('download_url'):
                # Clean URL to remove /thumb/ (like your working script)
                clean_url = value['download_url'].replace('/thumb/', '/file/')
                result = {
                    "fileId": value.get('fileId', value.get('id', '')),
                    "url": clean_url,
                    "alt": value.get('name', value.get('filename', 'Document'))
                }
                logger.debug("Transformed PDF from dict with download_url", result=result)
                return result
            else:
                # If it already looks like a Webflow file object, return as-is
                if 'fileId' in value and 'url' in value:
                    logger.debug("PDF already in Webflow format", value=value)
                    return value
                # Return the dict as-is if it looks like a file object
                return value
        elif isinstance(value, str) and value.strip():
            # Parse string representation of dict (common issue)
            if value.startswith("{'") or value.startswith('{"'):
                try:
                    import ast
                    parsed_dict = ast.literal_eval(value)
                    if isinstance(parsed_dict, dict):
                        logger.debug("Parsed string representation of dict", parsed=parsed_dict)
                        return self._transform_pdf_value(parsed_dict)  # Recursive call
                except Exception as e:
                    logger.warning("Failed to parse string as dict", value=value[:100], error=str(e))
            
            # If it's already a URL, return as structured object
            if value.startswith(('http://', 'https://')):
                # Clean URL to remove /thumb/ (like your working script)
                clean_url = value.replace('/thumb/', '/file/')
                result = {
                    "fileId": "",
                    "url": clean_url,
                    "alt": clean_url.split('/')[-1] if '/' in clean_url else 'Document'
                }
                logger.debug("Transformed PDF from URL string", result=result)
                return result
        
        logger.debug("Could not transform PDF value", value=value)
        return None
    
    def _transform_image_value(self, value: Any) -> Optional[Dict[str, Any]]:
        """Transform image field values - using AssetHandler for proper processing"""
        try:
            from app.utils.asset_handler import AssetHandler
            asset_handler = AssetHandler()
            
            # Use AssetHandler to process the image data
            result = asset_handler.process_asset_from_attribute(value, asset_type="image")
            
            if result:
                logger.debug("Successfully transformed image using AssetHandler", result=result)
                return result
            else:
                logger.debug("AssetHandler could not process image", value=str(value)[:100])
                return None
                
        except Exception as e:
            logger.warning("Image transformation failed", error=str(e))
            
            # Fallback to original logic
            if isinstance(value, str) and value.strip():
                # Skip Plytix placeholder/default images
                if "static.plytix.com/template" in value or "default" in value.lower():
                    logger.debug("Skipping Plytix placeholder image", url=value)
                    return None
                # Clean URL and return proper format
                clean_url = value.replace('/thumb/', '/file/')
                return {"url": clean_url, "alt": "Product image"}
            elif isinstance(value, dict):
                # Handle complex image objects
                url = value.get('url') or value.get('file_url') or value.get('download_url')
                if url and "static.plytix.com/template" not in url:
                    clean_url = url.replace('/thumb/', '/file/')
                    return {"url": clean_url, "alt": value.get('filename', 'Product image')}
            return None
    
    def _transform_rich_text_value(self, value: Any) -> str:
        """Transform rich text field values"""
        if isinstance(value, str):
            # Basic HTML cleaning/formatting could be added here
            return value.strip()
        return str(value) if value is not None else ""
    
    def _transform_number_value(self, value: Any) -> Optional[int]:
        """Transform numeric field values to integer cents for Webflow"""
        if isinstance(value, (int, float)):
            return int(float(value) * 100)  # Convert to cents
        elif isinstance(value, str):
            try:
                # Remove currency symbols and commas
                cleaned = value.replace('$', '').replace(',', '').strip()
                return int(float(cleaned) * 100)
            except ValueError:
                return None
        return None
    
    def _transform_boolean_value(self, value: Any) -> bool:
        """Transform boolean field values"""
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on', 'active')
        elif isinstance(value, (int, float)):
            return bool(value)
        return False
    
    def _transform_array_value(self, value: Any) -> List[Any]:
        """Transform array field values"""
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            # Split by common delimiters
            return [item.strip() for item in value.split(',') if item.strip()]
        else:
            return [value] if value is not None else []
    
    async def process_product_assets(self, plytix_product_data: dict, use_webflow_upload: bool = True) -> Dict[str, Any]:
        """Process all product assets (images, PDFs) using AssetHandler"""
        processed_assets = {}
        
        try:
            # Process safety data sheet
            safety_sheet = await self.asset_handler.process_safety_data_sheet(
                plytix_product_data, 
                upload_to_webflow=use_webflow_upload
            )
            if safety_sheet:
                processed_assets['safety-data-sheet'] = safety_sheet
                logger.info("Processed safety data sheet", result=safety_sheet)
            
            # Process specification sheet
            spec_sheet = await self.asset_handler.process_specification_sheet(
                plytix_product_data, 
                upload_to_webflow=use_webflow_upload
            )
            if spec_sheet:
                processed_assets['specification-sheet'] = spec_sheet
                logger.info("Processed specification sheet", result=spec_sheet)
            
            # Process main image (use direct Plytix URL for images)
            attributes = plytix_product_data.get('attributes', {})
            main_image_data = attributes.get('main_image') or attributes.get('image') or attributes.get('photo')
            
            if main_image_data:
                processed_image = await self.asset_handler.process_plytix_image(
                    main_image_data, 
                    upload_to_webflow=False  # Use direct URL for images as requested
                )
                if processed_image:
                    processed_assets['main-image'] = processed_image
                    logger.info("Processed main image", result=processed_image)
            
            # Also check assets from product details for real images
            assets = plytix_product_data.get('assets', [])
            for asset in assets:
                if asset.get('url') and self._is_real_image_asset(asset):
                    processed_image = await self.asset_handler.process_plytix_image(
                        asset, 
                        upload_to_webflow=False
                    )
                    if processed_image:
                        processed_assets['main-image'] = processed_image
                        logger.info("Using real image from assets", result=processed_image)
                        break  # Use first real image found
                        
        except Exception as e:
            logger.error("Failed to process product assets", error=str(e))
        
        return processed_assets
    
    def _is_real_image_asset(self, asset: dict) -> bool:
        """Check if asset is a real image (not placeholder)"""
        url = asset.get('url', '')
        filename = asset.get('filename', '')
        
        # Check if it's an image file
        if not any(ext in filename.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']):
            return False
        
        # Check if it's not a placeholder
        placeholder_indicators = ['static.plytix.com/template', 'default', 'placeholder', 'no-image']
        return not any(indicator in url.lower() for indicator in placeholder_indicators)
    
    def _ensure_required_fields(self, webflow_data: Dict[str, Any], product_dict: Dict[str, Any]) -> None:
        """Ensure required fields are present with fallback values"""
        # Only add PRODUCT-level required fields here
        # SKU field belongs at SKU level, not product level
        required_fields = {
            'name': product_dict.get('name', product_dict.get('title', 'Unnamed Product')),
            'slug': self._generate_slug(product_dict.get('name', product_dict.get('sku', 'product')))
        }
        
        for field, fallback_value in required_fields.items():
            if field not in webflow_data or not webflow_data[field]:
                webflow_data[field] = fallback_value
    
    def _generate_slug(self, name: str) -> str:
        """Generate URL-friendly slug from product name"""
        import re
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', name.lower())
        slug = re.sub(r'\s+', '-', slug.strip())
        return slug[:50]  # Limit length
    
    def get_sku_from_product(self, product_data: Dict[str, Any]) -> str:
        """Extract SKU from product data using configured matching strategy"""
        if self.matching_strategy == 'sku':
            return product_data.get('sku', product_data.get('id', ''))
        else:
            return product_data.get('id', product_data.get('sku', ''))
    
    def validate_mappings(self) -> List[str]:
        """Validate field mappings and return list of issues"""
        issues = []
        
        # Check for required fields
        required_fields = ['sku', 'name']
        for field in required_fields:
            if field not in self.field_mappings:
                issues.append(f"Missing required field mapping: {field}")
        
        # Check for duplicate Webflow fields
        webflow_fields = [mapping.webflow_field for mapping in self.field_mappings.values()]
        duplicates = set([field for field in webflow_fields if webflow_fields.count(field) > 1])
        for duplicate in duplicates:
            issues.append(f"Duplicate Webflow field mapping: {duplicate}")
        
        return issues
    
    def get_mapping_summary(self) -> Dict[str, Any]:
        """Get summary of current field mappings for debugging/monitoring"""
        return {
            'total_mappings': len(self.field_mappings),
            'matching_strategy': self.matching_strategy,
            'field_types': {
                field_type.value: len([m for m in self.field_mappings.values() if m.field_type == field_type])
                for field_type in FieldType
            },
            'required_fields': len([m for m in self.field_mappings.values() if m.required]),
            'discovered_images': len(self.discovered_images)
        }
    
    def get_field_mappings(self) -> Dict[str, str]:
        """Get simplified field mappings for backward compatibility"""
        return {
            mapping.plytix_field: mapping.webflow_field 
            for mapping in self.field_mappings.values()
        }
    
    def get_sku_level_field_mappings(self, plytix_product_data: Dict) -> Dict[str, Any]:
        """Get field mappings and values specifically for SKU-level fields in Webflow"""
        from app.utils.field_separator import WebflowFieldSeparator
        
        # Get all attributes from product
        all_attributes = self.extract_all_attributes_dynamically(plytix_product_data)
        combined_dict = {**plytix_product_data, **all_attributes}
        
        # Process all field mappings to get SKU-level fields
        all_mapped_fields = {}
        
        # Apply configured field mappings
        for plytix_field, mapping in self.field_mappings.items():
            raw_value = None
            
            # Check combined data for the field
            if plytix_field in all_attributes:
                raw_value = all_attributes[plytix_field]
            elif plytix_field in plytix_product_data:
                raw_value = plytix_product_data[plytix_field]
            
            # Always check if field should be cleared first, regardless of value
            logger.warning("CHECKING FIELD FOR CLEARING", 
                          plytix_field=plytix_field, 
                          field_type=mapping.field_type.value,
                          clearable=mapping.clearable)
            should_clear = self._should_clear_field(plytix_field, raw_value, mapping, combined_dict)
            
            if should_clear:
                # Use empty string to clear PDF field (confirmed working in Postman)
                all_mapped_fields[mapping.webflow_field] = ""
                logger.warning("Safely clearing SKU field in Webflow using empty string", 
                              plytix_field=plytix_field,
                              webflow_field=mapping.webflow_field,
                              field_type=mapping.field_type.value,
                              reason="Field explicitly marked for clearing")
            elif raw_value is not None and raw_value != "":
                transformed_value = self._transform_field_value(raw_value, mapping)
                if transformed_value is not None and transformed_value != "":
                    all_mapped_fields[mapping.webflow_field] = transformed_value
        
        # Discover image fields and add them
        discovered_images = self.discover_image_fields(combined_dict)
        
        # ENHANCED: Get real images from assets API (like your working script)
        product_id = plytix_product_data.get('id')
        if product_id:
            real_images = self._get_real_images_from_assets(product_id)
            if real_images:
                # Override any placeholder images with real ones
                discovered_images.update(real_images)
                logger.info("Found real images from assets API", 
                           product_id=product_id, 
                           image_count=len(real_images))
        
        for plytix_field, webflow_field in discovered_images.items():
            image_value = None
            
            # Check if this is from real assets cache (priority over placeholders)
            if hasattr(self, '_real_assets_cache') and plytix_field in self._real_assets_cache:
                # Use real asset data
                asset_data = self._real_assets_cache[plytix_field]
                image_value = self._transform_image_value(asset_data)
                logger.info("Using REAL image from assets API", 
                           plytix_field=plytix_field,
                           filename=asset_data.get('filename', 'unknown'),
                           url=asset_data.get('url', '')[:50])
            elif hasattr(self, '_assets_cache') and plytix_field in self._assets_cache:
                # Use cached asset data (from old method)
                asset_data = self._assets_cache[plytix_field]
                image_value = self._transform_image_value(asset_data)
                logger.debug("Using cached image from assets API", 
                           plytix_field=plytix_field,
                           filename=asset_data.get('filename', 'unknown'))
            elif plytix_field in combined_dict:
                # Use attribute data (might be placeholder)
                image_value = self._transform_image_value(combined_dict[plytix_field])
            
            if image_value:
                # image_value is already in proper Webflow format from _transform_image_value
                all_mapped_fields[webflow_field] = image_value
                
                # Log details
                if isinstance(image_value, dict) and 'url' in image_value:
                    url_preview = image_value['url'][:50] if image_value['url'] else 'no_url'
                    logger.debug("Added image to SKU fields", 
                               plytix_field=plytix_field,
                               webflow_field=webflow_field,
                               url=url_preview,
                               is_real_asset=plytix_field.startswith('asset_'))
        
        # Ensure SKU field is present at SKU level (required for Webflow)
        if 'sku' not in all_mapped_fields:
            # Get SKU from product data
            sku_value = plytix_product_data.get('sku') or plytix_product_data.get('id', 'NO-SKU')
            all_mapped_fields['sku'] = sku_value
            logger.debug("Added required SKU field to SKU-level data", sku=sku_value)
        
        # Return only SKU-level fields
        sku_data = WebflowFieldSeparator.filter_sku_fields_only(all_mapped_fields)
        
        logger.info("SKU field mappings extracted",
                   total_sku_fields=len(sku_data),
                   sku_fields=list(sku_data.keys()))
        
        return sku_data
    
    def extract_all_attributes_dynamically(self, product_data: Dict) -> Dict:
        """
        Dynamically extract all attributes from any level/structure in Plytix product data
        Returns a flattened dictionary of ALL attributes found
        """
        all_attributes = {}
        
        def extract_from_dict(data, path="root"):
            """Recursively extract attributes from nested dictionaries"""
            if not isinstance(data, dict):
                return
            
            for key, value in data.items():
                current_path = f"{path}.{key}"
                
                # Check if this looks like an attributes container
                if self.is_attributes_container(key, value):
                    logger.debug("Found attributes container", path=current_path)
                    if isinstance(value, dict):
                        # Add all attributes from this container
                        for attr_key, attr_value in value.items():
                            if attr_value is not None:  # Only add non-null attributes
                                all_attributes[attr_key] = attr_value
                
                # Continue recursing for nested structures
                elif isinstance(value, dict):
                    extract_from_dict(value, current_path)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            extract_from_dict(item, f"{current_path}[{i}]")
        
        logger.debug("Dynamically extracting attributes from product data")
        extract_from_dict(product_data)
        
        logger.debug("Dynamic attribute extraction complete", total_attributes=len(all_attributes))
        return all_attributes

    def is_attributes_container(self, key: str, value) -> bool:
        """
        Determine if a key-value pair represents an attributes container
        """
        # Check key patterns that suggest attributes
        attribute_key_patterns = [
            'attributes',
            'custom_attributes', 
            'customAttributes',
            'product_attributes',
            'productAttributes',
            'additional_attributes',
            'additionalAttributes',
            'field_data',
            'fieldData',
            'properties',
            'metadata',
            'custom_fields',
            'customFields',
            'extra_data',
            'extraData',
            'detailed_attributes'
        ]
        
        key_lower = key.lower()
        
        # Direct key match
        if key in attribute_key_patterns or key_lower in [p.lower() for p in attribute_key_patterns]:
            return isinstance(value, dict) and len(value) > 0
        
        # Partial key match (e.g., "product_custom_attributes")
        for pattern in attribute_key_patterns:
            if pattern.lower() in key_lower or key_lower in pattern.lower():
                return isinstance(value, dict) and len(value) > 0
        
        # Structure-based detection: dict with many string keys
        if isinstance(value, dict) and len(value) > 3:
            # Check if most keys are strings and values are not complex objects
            string_keys = sum(1 for k in value.keys() if isinstance(k, str))
            simple_values = sum(1 for v in value.values() 
                              if v is None or isinstance(v, (str, int, float, bool, list)))
            
            # If >80% keys are strings and >60% values are simple, likely attributes
            if (string_keys / len(value) > 0.8 and 
                simple_values / len(value) > 0.6):
                return True
        
        return False
    
    def get_images_from_assets_api(self, product_id: str) -> Dict[str, str]:
        """
        Get images from Plytix assets API - like your working script approach
        Returns: dict mapping field names to webflow fields
        """
        try:
            # Import here to avoid circular imports
            import asyncio
            from app.clients.plytix_client import PlytixClient
            
            logger.debug("Getting images from Plytix assets API", product_id=product_id)
            
            # Create a new event loop for this sync context
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Get the assets
            assets = loop.run_until_complete(self._get_assets_async(product_id))
            
            # Process assets to find images
            discovered_images = {}
            
            for asset in assets:
                asset_url = asset.get('url', '')
                filename = asset.get('filename', 'unknown')
                
                # Check if it's an image asset
                if self._is_image_asset(asset_url, filename):
                    # Skip placeholder images
                    if not self._is_placeholder_image_url(asset_url):
                        # Map to main-image (SKU level)
                        field_name = f"asset_{asset.get('id', 'unknown')}"
                        discovered_images[field_name] = 'main-image'
                        
                        logger.debug("Discovered real image from assets API", 
                                   filename=filename, 
                                   url=asset_url[:50],
                                   product_id=product_id)
                        
                        # Store the asset data for later use
                        if not hasattr(self, '_assets_cache'):
                            self._assets_cache = {}
                        self._assets_cache[field_name] = asset
                        
                        # Only take the first real image
                        break
            
            return discovered_images
            
        except Exception as e:
            logger.warning("Failed to get images from assets API", error=str(e), product_id=product_id)
            return {}
    
    async def _get_assets_async(self, product_id: str):
        """Async helper to get assets from Plytix API"""
        from app.clients.plytix_client import PlytixClient
        
        client = PlytixClient()
        try:
            # Get product details which include assets
            product_details = await client.get_product_details(product_id, all_attributes=True)
            
            if 'data' in product_details and product_details['data']:
                detail = product_details['data'][0]
                assets = detail.get('assets', [])
                logger.debug("Retrieved assets from API", count=len(assets), product_id=product_id)
                return assets
            
            return []
        finally:
            await client.close()
    
    def _is_image_asset(self, asset_url: str, filename: str) -> bool:
        """Check if asset is an image"""
        if not asset_url:
            return False
        
        # Check file extension
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']
        filename_lower = filename.lower()
        
        for ext in image_extensions:
            if filename_lower.endswith(ext):
                return True
        
        # Check URL patterns
        if any(ext in asset_url.lower() for ext in image_extensions):
            return True
        
        return False
    
    def _is_placeholder_image_url(self, url: str) -> bool:
        """Check if image URL is a Plytix placeholder"""
        placeholder_indicators = [
            'static.plytix.com/template',
            'default',
            'placeholder',
            'no-image'
        ]
        return any(indicator in url.lower() for indicator in placeholder_indicators)
    
    def _get_real_images_from_assets(self, product_id: str) -> Dict[str, str]:
        """
        Get real images from Plytix assets API - simplified sync version
        Returns: dict mapping field names to webflow fields
        """
        try:
            # Import here to avoid circular imports
            import asyncio
            from app.clients.plytix_client import PlytixClient
            
            logger.debug("Getting real images from assets API", product_id=product_id)
            
            # Create a simple async function to get assets
            async def get_assets():
                client = PlytixClient()
                try:
                    # Get product details which include assets
                    product_details = await client.get_product_details(product_id, all_attributes=True)
                    
                    if 'data' in product_details and product_details['data']:
                        detail = product_details['data'][0]
                        assets = detail.get('assets', [])
                        return assets
                    return []
                finally:
                    await client.close()
            
            # Run the async function
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            assets = loop.run_until_complete(get_assets())
            
            # Process assets to find real images
            real_images = {}
            
            for asset in assets:
                asset_url = asset.get('url', '')
                filename = asset.get('filename', 'unknown')
                
                # Check if it's a real image (not placeholder)
                if (self._is_image_asset(asset_url, filename) and 
                    not self._is_placeholder_image_url(asset_url)):
                    
                    # Store the asset data for later use
                    if not hasattr(self, '_real_assets_cache'):
                        self._real_assets_cache = {}
                    
                    field_name = f"real_asset_{asset.get('id', 'unknown')}"
                    real_images[field_name] = 'main-image'
                    self._real_assets_cache[field_name] = asset
                    
                    logger.info("Found real image from assets API", 
                               filename=filename, 
                               url=asset_url[:50],
                               product_id=product_id)
                    
                    # Only take the first real image
                    break
            
            return real_images
            
        except Exception as e:
            logger.warning("Failed to get real images from assets API", 
                         error=str(e), 
                         product_id=product_id)
            return {}

    def save_discovered_mappings(self) -> None:
        """Save discovered mappings back to configuration file for future use"""
        try:
            config = {}
            if self.mapping_file.exists():
                with open(self.mapping_file, 'r') as f:
                    config = json.load(f)
            
            # Update with discovered image mappings
            if not config.get('image_mapping'):
                config['image_mapping'] = {}
            
            config['image_mapping']['discovered_fields'] = self.discovered_images
            
            with open(self.mapping_file, 'w') as f:
                json.dump(config, f, indent=2)
                
            logger.info("Discovered mappings saved", file=str(self.mapping_file))
            
        except Exception as e:
            logger.error("Failed to save discovered mappings", error=str(e))