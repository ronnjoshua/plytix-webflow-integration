import httpx
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog

from app.config.settings import get_settings
from app.config.endpoints import plytix_api
from app.models.plytix import PlytixProduct, PlytixProductsResponse, PlytixVariant
from app.utils.rate_limiter import RateLimiter
from app.core.exceptions import PlytixAPIError

logger = structlog.get_logger()
settings = get_settings()

class PlytixClient:
    """Client for interacting with Plytix PIM API"""
    
    def __init__(self):
        self.settings = get_settings()
        # Use centralized endpoint management
        self.endpoints = plytix_api
        self.base_url = self.endpoints.base_url
        self.api_key = self.settings.PLYTIX_API_KEY
        self.api_password = self.settings.PLYTIX_API_PASSWORD
        self.access_token = None
        self.token_expires_at = None
        self.rate_limiter = RateLimiter(
            max_requests=settings.PLYTIX_RATE_LIMIT,
            time_window=10  # 10 seconds
        )
        # Configure client to follow redirects and handle authentication properly
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "Plytix-Webflow-Integration/1.0"}
        )
    
    async def close(self):
        """Close the underlying HTTP client."""
        await self._client.aclose()
    
    async def check_authentication(self) -> bool:
        """Check if authentication is working by testing the token"""
        try:
            await self._authenticate()
            # Try a simple API call to verify authentication works - use search endpoint
            await self.search_products(page=1, page_size=1)
            logger.info("✅ Plytix authentication successful")
            return True
        except Exception as e:
            logger.error("❌ Plytix authentication failed", error=str(e))
            return False
    
    async def _authenticate(self) -> str:
        """Authenticate and get access token using official Plytix auth endpoint"""
        if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
            return self.access_token
            
        logger.info("🔐 Authenticating with Plytix using official endpoint")
        
        # Try the official auth endpoint first
        auth_url = self.endpoints.auth.AUTH_TOKEN_URL
        auth_data = {
            "api_key": self.api_key,
            "api_password": self.api_password
        }
        
        try:
            response = await self._client.post(
                auth_url,
                json=auth_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                token_data = response.json()
                
                if 'data' in token_data and token_data['data']:
                    self.access_token = token_data['data'][0].get('access_token')
                    
                    if self.access_token:
                        # Plytix tokens expire after 15 minutes according to docs
                        self.token_expires_at = datetime.now() + timedelta(minutes=14)  # 14 min buffer
                        
                        logger.info("✅ Successfully authenticated with Plytix API using auth endpoint")
                        return self.access_token
                    else:
                        logger.error("Access token not found in Plytix response")
                        raise PlytixAPIError("Access token not found in authentication response")
                else:
                    logger.error("Invalid authentication response structure")
                    raise PlytixAPIError("Invalid authentication response structure")
            else:
                logger.warning(f"Auth endpoint returned {response.status_code}, trying direct API password")
                # Fall back to using API password directly as Bearer token
                self.access_token = self.api_password
                self.token_expires_at = datetime.now() + timedelta(hours=24)  # Long expiry for password
                logger.info("✅ Using API password as Bearer token")
                return self.access_token
                
        except httpx.HTTPStatusError as e:
            logger.warning(f"Auth endpoint failed with {e.response.status_code}, trying direct API password")
            # Fall back to using API password directly as Bearer token
            self.access_token = self.api_password
            self.token_expires_at = datetime.now() + timedelta(hours=24)  # Long expiry for password
            logger.info("✅ Using API password as Bearer token")
            return self.access_token
        except Exception as e:
            logger.error("Authentication request failed", error=str(e))
            # Last resort: try using API password directly
            self.access_token = self.api_password
            self.token_expires_at = datetime.now() + timedelta(hours=24)
            logger.info("✅ Using API password as Bearer token (fallback)")
            return self.access_token

    async def _make_request(
        self, 
        endpoint: str, 
        method: str = "GET",
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make rate-limited HTTP request to Plytix API"""
        await self.rate_limiter.acquire()

        access_token = await self._authenticate()
        
        url = f"{self.base_url}{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Log the request for debugging
        logger.debug("Making Plytix API request", url=url, headers={"Authorization": f"Bearer {access_token[:10]}..."})
        
        try:
            response = await self._client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data
            )
            
            # Check if response is JSON
            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type and response.text.strip():
                logger.error("Non-JSON response received", content_type=content_type, response_preview=response.text[:200])
                raise PlytixAPIError(f"Expected JSON response but got {content_type}")
            
            response.raise_for_status()
            
            # Handle empty responses
            if not response.text.strip():
                logger.warning("Empty response received")
                return {}
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error("Plytix API error", response=e.response.text, status_code=e.response.status_code)
            
            # Handle token expiration
            if e.response.status_code == 401:
                logger.info("Token expired, re-authenticating...")
                self.access_token = None
                self.token_expires_at = None
                # Retry once with fresh token
                access_token = await self._authenticate()
                headers["Authorization"] = f"Bearer {access_token}"
                
                response = await self._client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data
                )
                response.raise_for_status()
                
                # Check if response is JSON
                content_type = response.headers.get("content-type", "")
                if "application/json" not in content_type and response.text.strip():
                    logger.error("Non-JSON response received after re-auth", content_type=content_type, response_preview=response.text[:200])
                    raise PlytixAPIError(f"Expected JSON response but got {content_type}")
                
                return response.json()
            
            raise PlytixAPIError(f"API request failed: {e.response.status_code}")
        except Exception as e:
            logger.error("Request failed", error=str(e))
            raise PlytixAPIError(f"Request failed: {str(e)}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def search_products(
        self,
        page: int = 1,
        page_size: int = 25,
        attributes: list = None,
        filters: dict = None
    ) -> dict:
        """Search products using POST /products/search and return the raw response."""
        endpoint = self.endpoints.products.SEARCH
        
        # Build request body with minimal structure for Plytix API
        body = {
            "pagination": {
                "page": page,
                "page_size": page_size
            },
            "sorting": {
                "field": "updated_at",
                "direction": "desc"
            }
        }
        
        # Add attributes if provided (but this might not be needed for basic search)
        if attributes and isinstance(attributes, list) and len(attributes) > 0:
            body["attributes"] = attributes
            
        # Add filters if provided - use proper Plytix filter structure
        if filters and isinstance(filters, dict):
            body["filters"] = filters
        elif filters and isinstance(filters, list) and len(filters) > 0:
            # Convert list of filters to proper Plytix format
            body["filters"] = {"and": filters}
        
        # Debug logging to see exact request
        logger.debug("Plytix search request body", body=body)
        return await self._make_request(endpoint, method="POST", json_data=body)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_products_list(
        self,
        page: int = 1,
        page_size: int = 25,
        since: Optional[str] = None,
        catalog_id: Optional[str] = None
    ) -> dict:
        """Get products using GET /products endpoint (alternative to search)"""
        endpoint = self.endpoints.products.LIST
        params = {
            "page": page,
            "page_size": page_size
        }
        
        if since:
            params["updated_since"] = since
        if catalog_id:
            params["catalog_id"] = catalog_id
            
        logger.debug("Plytix GET products request", params=params)
        return await self._make_request(endpoint, method="GET", params=params)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_product_details(self, product_id: str, all_attributes: bool = False) -> dict:
        """Fetch detailed product information by ID using GET /products/{product_id}"""
        endpoint = self.endpoints.products.get_product_url(product_id).replace(self.base_url, "")
        params = {"all_attributes": str(all_attributes).lower()}
        return await self._make_request(endpoint, method="GET", params=params)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_product_assets(self, product_id: str, asset_id: Optional[str] = None) -> dict:
        """Fetch assets for a specific product using the correct Plytix assets API"""
        if asset_id:
            # Get specific asset: /products/{product_id}/assets/{asset_id}
            endpoint = self.endpoints.assets.get_asset_url(product_id, asset_id).replace(self.base_url, "")
        else:
            # Get all assets for product: /products/{product_id}/assets
            endpoint = self.endpoints.assets.get_all_assets_url(product_id).replace(self.base_url, "")
        
        return await self._make_request(endpoint, method="GET")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_product_variants(self, product_id: str, catalog_id: Optional[str] = None) -> List[PlytixVariant]:
        """Fetch all variants for a specific product"""
        endpoint = self.endpoints.products.get_variants_url(product_id).replace(self.base_url, "")
        data = await self._make_request(endpoint)
        # Check both 'data' and 'results' for variants
        variants_data = data.get("data", []) or data.get("results", [])
        return [PlytixVariant(**variant) for variant in variants_data]

    async def get_all_products_with_variants(
        self, 
        since: Optional[str] = None,
        catalog_id: Optional[str] = None
    ) -> List[PlytixProduct]:
        """Fetch all products with their variants using the search endpoint"""
        all_products = []
        page = 1
        page_size = 25
        
        logger.info("Fetching products from Plytix", since=since, catalog_id=catalog_id)
        
        while True:
            try:
                # Build filters for the search endpoint
                filters = {}
                filter_conditions = []
                
                if since:
                    filter_conditions.append({
                        "field": "updated_at",
                        "operator": "gte", 
                        "value": since
                    })
                    
                if catalog_id:
                    filter_conditions.append({
                        "field": "catalog_id",
                        "operator": "eq",
                        "value": catalog_id
                    })
                
                # Set up filters properly for Plytix API
                if filter_conditions:
                    filters = {"and": filter_conditions}
                
                # Use the search endpoint with proper filter structure
                response_data = await self.search_products(
                    page=page, 
                    page_size=page_size,
                    filters=filters if filter_conditions else None
                )
                
                # Check if we have results - Plytix API returns data in 'data' field
                products_data = response_data.get("data", [])
                if not products_data:
                    logger.info("No more products found", page=page)
                    break
                    
                logger.info("Processing products page", page=page, products_count=len(products_data))
                
                for product_data in products_data:
                    try:
                        product = PlytixProduct(**product_data)
                        
                        # Enrich product with detailed information
                        await self._enrich_product_details(product)
                        
                        # Fetch variants for each product
                        try:
                            variants = await self.get_product_variants(product.id, catalog_id)
                            product.variants = variants
                            logger.debug("Fetched variants for product", 
                                       product_id=product.id, 
                                       variants_count=len(variants))
                        except Exception as e:
                            logger.warning("Failed to fetch variants", product_id=product.id, error=str(e))
                            product.variants = []  # Ensure variants is always a list
                        
                        all_products.append(product)
                        
                    except Exception as e:
                        logger.error("Failed to process product", product_data=product_data, error=str(e))
                        continue
                
                # Check if there are more pages
                pagination = response_data.get("pagination", {})
                current_page = pagination.get("page", page)
                total_count = pagination.get("total_count", 0)
                current_page_size = pagination.get("page_size", page_size)
                
                logger.debug("Pagination info", 
                           current_page=current_page, 
                           total_count=total_count, 
                           page_size=current_page_size,
                           products_so_far=len(all_products))
                
                # Calculate if we've reached the end
                if current_page * current_page_size >= total_count or len(products_data) < page_size:
                    logger.info("Reached end of products", 
                              final_page=current_page, 
                              total_products=len(all_products))
                    break
                    
                page += 1
                
            except Exception as e:
                logger.error("Failed to fetch products page", page=page, error=str(e))
                # Don't break on individual page failures, try next page
                page += 1
                if page > 10:  # Prevent infinite loop
                    logger.error("Too many consecutive failures, stopping")
                    break
                
        logger.info("Fetched products from Plytix", count=len(all_products))
        return all_products
    
    async def _enrich_product_details(self, product: PlytixProduct) -> None:
        """Enrich a product with detailed information from the product details endpoint"""
        try:
            details_response = await self.get_product_details(product.id, all_attributes=True)
            
            # The details response has structure: {"data": [product_details]}
            if details_response.get("data") and len(details_response["data"]) > 0:
                details = details_response["data"][0]
                attributes = details.get("attributes", {})
                product.detailed_attributes = attributes
                
                # Debug logging for products with rich data
                if attributes and len(attributes) > 5:
                    attr_keys = list(attributes.keys())[:10]
                    logger.warning("PLYTIX_DEBUG: Product has rich attributes", 
                                  product_id=product.id,
                                  product_sku=product.sku,
                                  total_attributes=len(attributes),
                                  attribute_names=attr_keys,
                                  has_web_extended_description='web_extended_description' in attributes,
                                  has_description='description' in attributes)
                
                # Extract common fields from attributes
                attrs = attributes
                
                # Extract name/label from both direct fields and attributes - Plytix uses "label" as the main product name
                product.name = (
                    details.get("label") or  # Check direct label field first
                    attrs.get("label") or 
                    attrs.get("product_title") or
                    attrs.get("title") or 
                    attrs.get("name") or
                    attrs.get("product_name") or
                    product.sku  # Fallback to SKU if no name found
                )
                # Ensure name is never None to prevent .lower() errors
                product.name = product.name or product.sku or f"Product-{product.id}"
                product.label = product.name
                
                # Extract description
                product.description = (
                    attrs.get("description") or 
                    attrs.get("body_html") or 
                    attrs.get("english_features") or
                    attrs.get("long_description")
                )
                
                # Extract price
                price_fields = ["price", "compare_at_price", "cost_price", "retail_price"]
                for field in price_fields:
                    if attrs.get(field) is not None:
                        try:
                            product.price = float(attrs[field])
                            break
                        except (ValueError, TypeError):
                            continue
                
                # Extract brand
                product.brand = attrs.get("brand") or attrs.get("manufacturer")
                
                # Extract images from assets
                assets = details.get("assets", [])
                product.images = [asset.get("url") for asset in assets if asset.get("url")]
                
                # Extract categories if available
                if details.get("categories"):
                    product.category = details["categories"][0] if details["categories"] else None
                
                logger.debug("Enriched product details", 
                           product_id=product.id, 
                           name=product.name, 
                           price=product.price,
                           images_count=len(product.images))
        
        except Exception as e:
            logger.warning("Failed to enrich product details", 
                         product_id=product.id, 
                         error=str(e))