import httpx
from typing import List, Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog

from app.config.settings import get_settings
from app.config.endpoints import webflow_api
from app.models.webflow import WebflowProduct, WebflowProductResponse
from app.utils.rate_limiter import RateLimiter
from app.core.exceptions import WebflowAPIError

logger = structlog.get_logger()
settings = get_settings()

class WebflowClient:
    def __init__(self):
        # Use centralized endpoint management
        self.endpoints = webflow_api
        self.base_url = settings.WEBFLOW_BASE_URL
        self.token = settings.WEBFLOW_TOKEN
        self.site_id = settings.WEBFLOW_SITE_ID
        self.collection_id = settings.WEBFLOW_COLLECTION_ID
        self.rate_limiter = RateLimiter(
            max_requests=settings.WEBFLOW_RATE_LIMIT,
            time_window=60  # 60 seconds
        )
        self._client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def check_authentication(self) -> bool:
        """Verify that the Webflow token is valid."""
        try:
            logger.info("🔐 Checking Webflow authentication...")
            # Make a simple request to a protected endpoint to check the token
            endpoint = self.endpoints.sites.get_site_url(self.site_id).replace(self.base_url, "")
            await self._make_request(endpoint)
            logger.info("✅ Webflow authentication successful")
            return True
        except WebflowAPIError as e:
            logger.error("❌ Webflow authentication failed", error=str(e))
            return False
    
    async def _make_request(
        self, 
        endpoint: str, 
        method: str = "GET", 
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make rate-limited HTTP request to Webflow API"""
        await self.rate_limiter.acquire()
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        try:
            response = await self._client.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                params=params
            )
            response.raise_for_status()
            return response.json()
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Webflow API request failed due to authentication error (401). "
                               "Please check your Webflow API token.", response=e.response.text)
                raise WebflowAPIError(f"Authentication failed: {e.response.status_code}")

            logger.error("Webflow API error", status_code=e.response.status_code, response=e.response.text)
            raise WebflowAPIError(f"API request failed: {e.response.status_code}")
        except Exception as e:
            logger.error("Webflow request failed", error=str(e))
            raise WebflowAPIError(f"Request failed: {str(e)}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def create_product(self, product: WebflowProduct, collection_id: Optional[str] = None) -> WebflowProductResponse:
        """Create a new product with variants in Webflow E-commerce"""
        endpoint = self.endpoints.products.create_product_url(self.site_id).replace(self.base_url, "")
        
        # Use provided collection_id or fall back to default
        target_collection_id = collection_id or self.collection_id
        
        # Build proper Webflow API v2 request format
        product_data = product.dict()
        product_data["product-type"] = "Advanced"
        
        # Extract SKUs separately as Webflow v2 expects them at the top level
        skus = product_data.pop("skus", [])
        sku_properties = product_data.pop("sku_properties", [])
        
        # Webflow API v2 format requires 'product' and 'sku' objects with 'fieldData'
        request_body = {
            "product": {
                "fieldData": {
                    "name": product_data.get("name", "Untitled Product"),
                    "slug": product_data.get("slug", "untitled-product"),
                    "description": product_data.get("description", "")
                }
            },
            "sku": {
                "fieldData": {
                    "name": product_data.get("name", "Untitled Product") + " - SKU",
                    "slug": (product_data.get("slug", "untitled-product") + "-sku"),
                    "sku": (skus[0].get("sku") if skus else 
                           product_data.get("name", "default-sku").lower().replace(" ", "-"))
                }
            }
        }
        
        # Add SKU properties if present
        if sku_properties:
            request_body["product"]["fieldData"]["sku-properties"] = sku_properties
        
        logger.debug("Webflow create product request", endpoint=endpoint, body_structure=list(request_body.keys()))
        data = await self._make_request(endpoint, method="POST", json_data=request_body)
        
        # Webflow v2 API returns nested structure: {"product": {...}, "sku": {...}}
        # Extract the product data from the response
        if "product" in data:
            product_data = data["product"]
            # Create minimal response with just the ID and basic info
            return WebflowProductResponse(
                id=product_data.get("id", ""),
                name=product_data.get("fieldData", {}).get("name", ""),
                slug=product_data.get("fieldData", {}).get("slug", ""),
                created_on=product_data.get("createdOn", ""),
                updated_on=product_data.get("updatedOn", "")
            )
        else:
            # Fallback for direct structure - create minimal response
            return WebflowProductResponse(
                id=data.get("id", ""),
                name=data.get("name", ""),
                slug=data.get("slug", ""),
                created_on=data.get("created_on", ""),
                updated_on=data.get("updated_on", "")
            )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def update_product(
        self, 
        product_id: str, 
        product: WebflowProduct,
        plytix_product_data: Optional[Dict[str, Any]] = None,
        collection_id: Optional[str] = None
    ) -> WebflowProductResponse:
        """Update an existing product only if content has changed"""
        endpoint = self.endpoints.products.update_product_url(self.site_id, product_id).replace(self.base_url, "")
        
        # DEBUG: Always log what we receive
        logger.warning("DEBUG: update_product called", 
                      product_id=product_id,
                      has_plytix_data=bool(plytix_product_data),
                      plytix_data_type=type(plytix_product_data).__name__ if plytix_product_data else 'None',
                      plytix_id=plytix_product_data.get('id') if plytix_product_data and isinstance(plytix_product_data, dict) else 'no_id')
        
        # ENHANCED: Get real images from Plytix assets API FIRST (like your working script)
        if plytix_product_data:
            logger.warning("DEBUG: About to enhance product with real images", 
                          product_id=product_id,
                          plytix_id=plytix_product_data.get('id') if isinstance(plytix_product_data, dict) else 'not_dict')
            await self._enhance_with_real_images(plytix_product_data)
        else:
            logger.warning("DEBUG: No plytix_product_data provided for enhancement", product_id=product_id)
        
        # Use provided collection_id or fall back to default
        target_collection_id = collection_id or self.collection_id
        
        # First, get the current product data to compare
        current_product_data = await self._make_request(endpoint)
        current_fields = current_product_data.get("product", {}).get("fieldData", {})
        
        # Build proper Webflow API v2 request format
        product_data = product.dict()
        
        # Extract SKUs separately as Webflow v2 expects them at the top level
        skus = product_data.pop("skus", [])
        sku_properties = product_data.pop("sku_properties", [])
        
        # Webflow API v2 format - only update product fields that matter
        request_body = {
            "product": {
                "fieldData": {}
            }
        }
        
        # Map the fields properly using dynamic field mapping
        field_data = request_body["product"]["fieldData"]
        
        # Load field mappings dynamically
        try:
            from app.services.field_mapping_service import FieldMappingService
            field_mapping_service = FieldMappingService()
            field_mappings = field_mapping_service.get_field_mappings()
            logger.debug("Loaded dynamic field mappings", total_mappings=len(field_mappings))
        except Exception as e:
            logger.warning("Failed to load field mappings, using defaults", error=str(e))
            # Fallback to basic field mappings that exist in the Webflow collection
            field_mappings = {
                "name": "name",
                "label": "name", 
                "description": "description",
                "web_short_description": "description",
                "web_extended_description": "description"
            }
            logger.debug("Using fallback field mappings", total_mappings=len(field_mappings))
        
        # Map all fields defined in field_mappings.json using original Plytix data if available
        if plytix_product_data:
            # Use field mapping service to transform the Plytix data properly
            from app.services.field_mapping_service import FieldMappingService
            from app.utils.field_separator import WebflowFieldSeparator
            
            field_mapping_service = FieldMappingService()
            
            # Create a mock PlytixProduct to use the transform method
            from app.models.plytix import PlytixProduct
            mock_product = PlytixProduct(**plytix_product_data)
            
            # Transform data - this now returns ONLY product-level fields
            transformed_data = field_mapping_service.transform_product_data(mock_product)
            
            # Add transformed fields to field_data (already filtered to product-level only)
            for webflow_field, value in transformed_data.items():
                if value is not None and str(value).strip() != "":
                    field_data[webflow_field] = value
                    logger.debug("Mapped product-level field from Plytix data", 
                               webflow_field=webflow_field,
                               value_preview=str(value)[:50] + ("..." if len(str(value)) > 50 else ""))
        else:
            # Fallback to original logic using WebflowProduct data
            from app.utils.field_separator import WebflowFieldSeparator
            
            # Collect all fallback fields first
            fallback_fields = {}
            for plytix_field, webflow_field in field_mappings.items():
                if product_data.get(plytix_field) is not None and product_data.get(plytix_field) != "":
                    fallback_fields[webflow_field] = product_data[plytix_field]
            
            # Filter to only product-level fields
            product_only_fields = WebflowFieldSeparator.filter_product_fields_only(fallback_fields)
            
            # Add filtered fields to field_data
            for webflow_field, value in product_only_fields.items():
                field_data[webflow_field] = value
                logger.debug("Mapped product-level field from fallback", 
                           webflow_field=webflow_field)
        
        # Handle special cases that might not be in field mappings
        # Product name (required)
        if product_data.get("name") and "name" not in field_data:
            field_data["name"] = product_data["name"]
        
        # Handle files (PDFs, documents) if present
        if product_data.get("files") and isinstance(product_data["files"], dict):
            field_data["files"] = product_data["files"]
        
        # Handle categories if present (array format)
        if product_data.get("category") and isinstance(product_data["category"], list):
            field_data["category"] = product_data["category"]
        
        # Compare fields and only keep changed ones
        fields_to_update = {}
        changed_fields = []
        unchanged_fields = []
        
        # LOG: Show all field data being processed
        logger.warning("FIELD_UPDATE_DEBUG: All field data prepared for update", 
                      product_id=product_id,
                      total_fields=len(field_data),
                      field_names=list(field_data.keys()),
                      field_preview={k: str(v)[:100] + "..." if len(str(v)) > 100 else str(v) 
                                   for k, v in field_data.items()})
        
        # LOG: Show current Webflow field data
        logger.warning("FIELD_UPDATE_DEBUG: Current Webflow field data", 
                      product_id=product_id,
                      current_field_names=list(current_fields.keys()),
                      current_field_preview={k: str(v)[:100] + "..." if len(str(v)) > 100 else str(v) 
                                           for k, v in current_fields.items()})
        
        for field_key, new_value in field_data.items():
            current_value = current_fields.get(field_key)
            
            # Normalize values for comparison
            new_str = str(new_value).strip() if new_value is not None else ""
            current_str = str(current_value).strip() if current_value is not None else ""
            
            if new_str != current_str:
                fields_to_update[field_key] = new_value
                changed_fields.append(field_key)
                logger.warning("FIELD_CHANGED", 
                             field=field_key, 
                             old_value=current_str[:50] + "..." if len(current_str) > 50 else current_str,
                             new_value=new_str[:50] + "..." if len(new_str) > 50 else new_str,
                             product_id=product_id)
            else:
                unchanged_fields.append(field_key)
                logger.debug("FIELD_UNCHANGED", 
                           field=field_key, 
                           value=current_str[:50] + "..." if len(current_str) > 50 else current_str,
                           product_id=product_id)
        
        # If no fields have changed, skip the update
        if not fields_to_update:
            logger.info("No field changes detected - skipping product update", 
                       product_id=product_id,
                       unchanged_fields=unchanged_fields,
                       total_fields_checked=len(field_data))
            
            # Still check SKU updates
            sku_fields_updated = []
            if skus and len(skus) > 0:
                sku_fields_updated = await self._update_product_sku(product_id, skus[0], plytix_product_data)
            
            if sku_fields_updated:
                logger.info("Updated SKU fields only", 
                           product_id=product_id, 
                           sku_fields_updated=sku_fields_updated)
            
            # Return current product data since no update was needed
            return self._parse_product_response(current_product_data)
        
        # Update request_body with only changed fields
        request_body["product"]["fieldData"] = fields_to_update
        
        # Log fields being updated
        logger.info("Updating product fields", 
                   product_id=product_id, 
                   fields_updated=changed_fields,
                   unchanged_fields=unchanged_fields,
                   total_fields_changed=len(changed_fields),
                   total_fields_checked=len(field_data))
        
        logger.debug("Webflow update product request", endpoint=endpoint, body_structure=list(request_body.keys()), field_count=len(fields_to_update))
        data = await self._make_request(endpoint, method="PATCH", json_data=request_body)
        
        # Also update the default SKU if we have SKU data
        sku_fields_updated = []
        if skus and len(skus) > 0:
            sku_fields_updated = await self._update_product_sku(product_id, skus[0], plytix_product_data)
        
        # Log all updated fields including SKU fields
        if sku_fields_updated:
            logger.info("Updated SKU fields", 
                       product_id=product_id, 
                       sku_fields_updated=sku_fields_updated)
        
        return self._parse_product_response(data)
    
    async def _update_product_sku(self, product_id: str, sku_data: dict, plytix_product_data: Optional[Dict[str, Any]] = None) -> List[str]:
        """Update the SKU data for a product only if content has changed"""
        updated_fields = []
        try:
            # First get the product to find its default SKU ID
            product_endpoint = self.endpoints.products.get_product_url(self.site_id, product_id).replace(self.base_url, "")
            product_info = await self._make_request(product_endpoint)
            
            if "product" in product_info:
                default_sku_id = product_info["product"]["fieldData"].get("default-sku")
                
                if default_sku_id:
                    # Get current SKU data to compare
                    sku_endpoint = self.endpoints.skus.update_sku_url(self.site_id, product_id, default_sku_id).replace(self.base_url, "")
                    try:
                        current_sku_info = await self._make_request(sku_endpoint)
                        current_sku_fields = current_sku_info.get("fieldData", {})
                    except:
                        # If we can't get current SKU data, proceed with update
                        current_sku_fields = {}
                    
                    sku_update = {
                        "fieldData": {}
                    }
                    
                    # Compare and map SKU fields based on schema
                    if sku_data.get("sku"):
                        current_sku_value = current_sku_fields.get("sku", "")
                        new_sku_value = str(sku_data["sku"]).strip()
                        if new_sku_value != str(current_sku_value).strip():
                            sku_update["fieldData"]["sku"] = sku_data["sku"]
                            updated_fields.append("sku")
                    
                    if sku_data.get("price"):
                        current_price = current_sku_fields.get("price", {})
                        if isinstance(sku_data["price"], dict):
                            new_price = sku_data["price"]
                        elif isinstance(sku_data["price"], (int, float)):
                            new_price = {
                                "value": int(sku_data["price"] * 100),  # Convert to cents
                                "unit": "USD"
                            }
                        else:
                            new_price = None
                        
                        if new_price and new_price != current_price:
                            sku_update["fieldData"]["price"] = new_price
                            updated_fields.append("price")
                    
                    if sku_data.get("inventory"):
                        current_inventory = current_sku_fields.get("inventory")
                        new_inventory = sku_data["inventory"]
                        if str(new_inventory).strip() != str(current_inventory or "").strip():
                            sku_update["fieldData"]["inventory"] = new_inventory
                            updated_fields.append("inventory")
                    
                    # Handle SKU-level field mappings from Plytix data
                    if plytix_product_data:
                        from app.services.field_mapping_service import FieldMappingService
                        field_mapping_service = FieldMappingService()
                        
                        # EXTRACT REAL IMAGES FROM PRODUCT ASSETS (like your working script)
                        logger.warning("🎯 SKU_UPDATE: Extracting real images from Plytix product assets", product_id=product_id)
                        real_image_url = self._extract_real_image_from_assets(plytix_product_data)
                        
                        sku_field_data = field_mapping_service.get_sku_level_field_mappings(plytix_product_data)
                        
                        # Override with real image if found
                        if real_image_url:
                            sku_field_data['main-image'] = real_image_url
                            logger.warning("✅ SKU_UPDATE: Using real image from assets", 
                                         product_id=product_id, 
                                         image_url=real_image_url[:50])
                        else:
                            logger.warning("❌ SKU_UPDATE: No real image found in assets", product_id=product_id)
                        
                        logger.info("Processing SKU-level field mappings",
                                   sku_id=default_sku_id,
                                   available_sku_fields=list(sku_field_data.keys()),
                                   sku_field_count=len(sku_field_data))
                        
                        # Apply SKU-level field mappings
                        for webflow_field, new_value in sku_field_data.items():
                            current_value = current_sku_fields.get(webflow_field)
                            
                            # Compare values based on type
                            if isinstance(new_value, dict) and isinstance(current_value, dict):
                                # For complex objects like images, compare key properties
                                new_url = new_value.get("url", "")
                                current_url = current_value.get("url", "")
                                if str(new_url).strip() != str(current_url).strip():
                                    sku_update["fieldData"][webflow_field] = new_value
                                    updated_fields.append(webflow_field)
                                    logger.info("Updated SKU field (object)", 
                                               field=webflow_field, 
                                               sku_id=default_sku_id,
                                               new_url=new_url[:50],
                                               current_url=current_url[:50])
                            elif str(new_value).strip() != str(current_value or "").strip():
                                sku_update["fieldData"][webflow_field] = new_value
                                updated_fields.append(webflow_field)
                                logger.info("Updated SKU field (simple)", 
                                           field=webflow_field,
                                           sku_id=default_sku_id, 
                                           new_value=str(new_value)[:50],
                                           current_value=str(current_value or "")[:50])
                    
                    if updated_fields:
                        logger.debug("Updating SKU", sku_id=default_sku_id, fields=updated_fields)
                        await self._make_request(sku_endpoint, method="PATCH", json_data=sku_update)
                    else:
                        logger.debug("No SKU changes detected - skipping SKU update", sku_id=default_sku_id)
                    
        except Exception as e:
            logger.warning("Failed to update SKU", product_id=product_id, error=str(e))
        
        return updated_fields
    
    def _parse_product_response(self, data: Dict[str, Any]) -> WebflowProductResponse:
        
        # Webflow v2 API returns nested structure: {"product": {...}, "sku": {...}}
        # Extract the product data from the response
        if "product" in data:
            product_data = data["product"]
            # Create minimal response with just the ID and basic info
            return WebflowProductResponse(
                id=product_data.get("id", ""),
                name=product_data.get("fieldData", {}).get("name", ""),
                slug=product_data.get("fieldData", {}).get("slug", ""),
                created_on=product_data.get("createdOn", ""),
                updated_on=product_data.get("updatedOn", "")
            )
        else:
            # Fallback for direct structure - create minimal response
            return WebflowProductResponse(
                id=data.get("id", ""),
                name=data.get("name", ""),
                slug=data.get("slug", ""),
                created_on=data.get("created_on", ""),
                updated_on=data.get("updated_on", "")
            )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_product_by_sku(self, sku: str, collection_id: Optional[str] = None) -> Optional[WebflowProductResponse]:
        """Find product by SKU in the collection"""
        endpoint = self.endpoints.products.list_products_url(self.site_id).replace(self.base_url, "")
        
        # According to Webflow API v2, we get all products and search by product name (matching Plytix SKU)
        params = {
            "limit": 100  # Get more products per request
        }
        
        try:
            logger.debug("Searching for product by SKU", sku=sku)
            
            offset = 0
            while True:
                params["offset"] = offset
                data = await self._make_request(endpoint, params=params)
                
                # Webflow API v2 returns 'items' not 'products'
                items = data.get("items", [])
                
                if not items:
                    break
                
                # Search through each product's name (matching Plytix SKU)
                for item in items:
                    product_data = item.get("product", {})
                    product_field_data = product_data.get("fieldData", {})
                    
                    # Check if product name matches Plytix SKU
                    product_name = product_field_data.get("name", "")
                    if product_name == sku:
                        logger.debug("Found product by name matching Plytix SKU", sku=sku, product_name=product_name, product_id=product_data.get("id"))
                        
                        # Create response with proper structure
                        return WebflowProductResponse(
                            id=product_data.get("id", ""),
                            name=product_data.get("fieldData", {}).get("name", ""),
                            slug=product_data.get("fieldData", {}).get("slug", ""),
                            created_on=product_data.get("createdOn", ""),
                            updated_on=product_data.get("updatedOn", "")
                        )
                
                # Check if we have more products to fetch
                pagination = data.get("pagination", {})
                total = pagination.get("total", 0)
                if offset + len(items) >= total:
                    break
                    
                offset += len(items)
            
            logger.debug("Product not found by SKU", sku=sku)
            return None
            
        except Exception as e:
            logger.warning("Failed to find product by SKU", sku=sku, error=str(e))
            return None

    async def get_all_products_from_collection(self, collection_id: Optional[str] = None) -> List[WebflowProductResponse]:
        """Get all products from the collection"""
        endpoint = self.endpoints.products.list_products_url(self.site_id).replace(self.base_url, "")
        
        params = {
            "limit": 100
        }
        
        all_products = []
        offset = 0
        
        try:
            while True:
                params["offset"] = offset
                data = await self._make_request(endpoint, params=params)
                
                items = data.get("items", [])
                if not items:
                    break
                
                for item in items:
                    product_data = item.get("product", {})
                    all_products.append(WebflowProductResponse(
                        id=product_data.get("id", ""),
                        name=product_data.get("fieldData", {}).get("name", ""),
                        slug=product_data.get("fieldData", {}).get("slug", ""),
                        created_on=product_data.get("createdOn", ""),
                        updated_on=product_data.get("updatedOn", "")
                    ))
                
                # Check pagination
                pagination = data.get("pagination", {})
                total = pagination.get("total", 0)
                if offset + len(items) >= total:
                    break
                    
                offset += len(items)
            
            return all_products
            
        except Exception as e:
            logger.error("Failed to get products from collection", error=str(e))
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the E-commerce collection"""
        # Note: Collection endpoint not in centralized system yet, keeping original
        endpoint = f"/sites/{self.site_id}/collections/{self.collection_id}"
        try:
            data = await self._make_request(endpoint)
            return data
        except Exception as e:
            logger.error("Failed to get collection info", collection_id=self.collection_id, error=str(e))
            raise

    async def publish_items(self, item_ids: Optional[List[str]] = None) -> bool:
        """Publish specific items (e-commerce products) to make them live"""
        try:
            # Note: Publish endpoint not in centralized system yet, keeping original
            endpoint = f"/sites/{self.site_id}/publish"
            
            # For e-commerce items, we need to publish specific items or all items
            publish_data = {
                "publishToWebflowSubdomain": True
            }
            
            # If specific item IDs are provided, publish only those
            if item_ids:
                publish_data["itemIds"] = item_ids
                logger.info("Publishing specific e-commerce items", item_count=len(item_ids))
            else:
                logger.info("Publishing all e-commerce items")
            
            await self._make_request(endpoint, method="POST", json_data=publish_data)
            logger.info("✅ E-commerce items published successfully")
            return True
            
        except Exception as e:
            logger.error("Failed to publish e-commerce items", error=str(e))
            return False
    
    async def _enhance_with_real_images(self, plytix_product_data: dict) -> None:
        """
        Enhance Plytix product data with real images from assets API
        This matches your working script approach
        """
        try:
            product_id = plytix_product_data.get('id')
            if not product_id:
                return
            
            logger.debug("Enhancing product with real images from assets API", product_id=product_id)
            
            # Get assets from Plytix API (like your working script)
            from app.clients.plytix_client import PlytixClient
            plytix_client = PlytixClient()
            
            try:
                # Get product details which include assets
                product_details = await plytix_client.get_product_details(product_id, all_attributes=True)
                
                if 'data' in product_details and product_details['data']:
                    detail = product_details['data'][0]
                    assets = detail.get('assets', [])
                    
                    logger.debug("Retrieved assets from Plytix API", 
                               count=len(assets), 
                               product_id=product_id)
                    
                    # Find the first real image asset
                    for asset in assets:
                        asset_url = asset.get('url', '')
                        filename = asset.get('filename', 'unknown')
                        
                        # Check if it's a real image (not placeholder)
                        if (self._is_real_image(asset_url, filename) and 
                            not self._is_placeholder_image(asset_url)):
                            
                            # Inject real image into product data (like your script)
                            # Add to attributes so it gets picked up by field mapping
                            if 'attributes' not in plytix_product_data:
                                plytix_product_data['attributes'] = {}
                            
                            # Override placeholder images with real ones
                            plytix_product_data['attributes']['real_main_image'] = asset
                            
                            logger.info("Enhanced product with real image from assets API", 
                                       product_id=product_id,
                                       filename=filename,
                                       url=asset_url[:50])
                            break
                    
            finally:
                await plytix_client.close()
                
        except Exception as e:
            logger.warning("Failed to enhance with real images", 
                         error=str(e), 
                         product_id=plytix_product_data.get('id', 'unknown'))
    
    def _is_real_image(self, asset_url: str, filename: str) -> bool:
        """Check if asset is a real image"""
        if not asset_url or not filename:
            return False
        
        # Check file extension
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']
        filename_lower = filename.lower()
        
        for ext in image_extensions:
            if filename_lower.endswith(ext):
                return True
        
        return False
    
    def _is_placeholder_image(self, url: str) -> bool:
        """Check if image URL is a Plytix placeholder"""
        placeholder_indicators = [
            'static.plytix.com/template',
            'default',
            'placeholder',
            'no-image'
        ]
        return any(indicator in url.lower() for indicator in placeholder_indicators)
    
    def _extract_real_image_from_assets(self, plytix_product_data: Dict[str, Any]) -> Optional[str]:
        """Extract real image URL from Plytix product assets (from product data structure)"""
        try:
            # Assets are already included in the product data structure as shown by user
            assets = plytix_product_data.get('assets', [])
            
            logger.debug("Extracting real image from product assets", 
                        product_id=plytix_product_data.get('id', 'unknown'),
                        asset_count=len(assets))
            
            # Find the first real image asset (not placeholder)
            for asset in assets:
                asset_url = asset.get('url', '')
                filename = asset.get('filename', 'unknown')
                asset_id = asset.get('id', 'unknown')
                
                logger.debug("Checking asset", 
                           filename=filename, 
                           url=asset_url[:50] + "..." if len(asset_url) > 50 else asset_url,
                           asset_id=asset_id)
                
                # Check if it's a real image (not placeholder)
                if (self._is_real_image(asset_url, filename) and 
                    not self._is_placeholder_image(asset_url)):
                    
                    logger.info("Found real image asset", 
                              filename=filename,
                              asset_id=asset_id,
                              url=asset_url[:50] + "..." if len(asset_url) > 50 else asset_url)
                    
                    return asset_url
            
            logger.warning("No real image assets found", 
                         product_id=plytix_product_data.get('id', 'unknown'),
                         total_assets=len(assets))
            return None
            
        except Exception as e:
            logger.warning("Failed to extract real image from assets", 
                         error=str(e),
                         product_id=plytix_product_data.get('id', 'unknown'))
            return None

