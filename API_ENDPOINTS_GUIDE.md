# API Endpoints Management Guide

## Overview

This guide documents the centralized API endpoint management system for Plytix and Webflow integrations. The system provides organized, maintainable, and reusable endpoint URL management.

## Architecture

### Core Components

- **`app/config/endpoints.py`**: Main endpoint management module
- **`PlytixAPI`**: Centralized Plytix PIM API endpoint management
- **`WebflowAPI`**: Centralized Webflow eCommerce API endpoint management
- **Convenience functions**: Backward-compatible helper functions

### Design Principles

1. **Centralized Management**: All API endpoints are defined in one place
2. **Logical Grouping**: Endpoints are organized by functionality (products, assets, etc.)
3. **Reusable Templates**: Dynamic URL construction for endpoints with parameters
4. **Easy Maintenance**: Single point of update for API changes
5. **Consistent Usage**: Uniform interface across the codebase
6. **Flexible Access**: Support for both direct URLs and method-based builders

## Usage

### Basic Usage

```python
from app.config.endpoints import plytix_api, webflow_api

# Plytix endpoints
search_url = plytix_api.products.get_search_url()  # POST: Search all products
product_url = plytix_api.products.get_product_url("123")
variants_url = plytix_api.products.get_variants_url("123")
assets_url = plytix_api.assets.get_all_assets_url("123")

# Webflow endpoints
products_url = webflow_api.products.list_products_url("site-123")
product_url = webflow_api.products.get_product_url("site-123", "prod-456")
```

### Convenience Functions

```python
from app.config.endpoints import (
    get_plytix_product_search_url,
    get_plytix_product_url,
    get_webflow_products_url,
    get_webflow_update_sku_url
)

# Backward-compatible convenience functions
search_url = get_plytix_product_search_url()  # POST: Search all products
product_url = get_plytix_product_url("123")
products_url = get_webflow_products_url("site-123")
sku_url = get_webflow_update_sku_url("site-123", "prod-456", "sku-789")
```

### Product Search Endpoint (POST)

The Product Search endpoint is the primary way to retrieve and list all products from Plytix with advanced filtering capabilities:

```python
from app.config.endpoints import plytix_api, get_plytix_product_search_url
import httpx

# Get the search endpoint URL
search_url = plytix_api.products.get_search_url()
# Result: https://pim.plytix.com/api/v1/products/search

# Or use the convenience function
search_url = get_plytix_product_search_url()

# Example POST request body for searching products
search_body = {
    "pagination": {
        "page": 1,
        "page_size": 25
    },
    "sorting": {
        "field": "updated_at",
        "direction": "desc"
    },
    "filters": {
        "and": [
            {
                "field": "status",
                "operator": "eq",
                "value": "active"
            }
        ]
    }
}

# Example usage with httpx
async def search_products():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            search_url,
            json=search_body,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
        )
        return response.json()
```

### Custom Base URLs

```python
from app.config.endpoints import PlytixAPI, WebflowAPI

# Custom instances with different base URLs
custom_plytix = PlytixAPI("https://staging.plytix.com/api/v1")
custom_webflow = WebflowAPI("https://staging.webflow.com/v2")

# Use custom instances the same way
search_url = custom_plytix.products.get_search_url()
product_url = custom_plytix.products.get_product_url("123")
```

## API Reference

### Plytix API Endpoints

#### Authentication
- `plytix_api.auth.AUTH_TOKEN_URL`: Get authentication token

#### Products
- `plytix_api.products.get_search_url()`: **Product search endpoint (POST)** - Search and list all products with advanced filtering
- `plytix_api.products.get_list_url()`: Product list endpoint (GET) - Simple product listing
- `plytix_api.products.get_product_url(product_id)`: Get product details
- `plytix_api.products.get_variants_url(product_id)`: Get product variants

#### Assets
- `plytix_api.assets.get_all_assets_url(product_id)`: Get all product assets
- `plytix_api.assets.get_asset_url(product_id, asset_id)`: Get specific asset

#### Attributes
- `plytix_api.attributes.get_product_attribute_url(attribute_id)`: Get product attribute

#### Filters
- `plytix_api.filters.get_product_filters_url()`: Get available product filters

### Webflow API Endpoints

#### Sites
- `webflow_api.sites.list_sites_url()`: List all sites
- `webflow_api.sites.get_site_url(site_id)`: Get specific site

#### Assets
- `webflow_api.assets.list_assets_url(site_id)`: List site assets
- `webflow_api.assets.get_asset_url(asset_id)`: Get specific asset

#### Products
- `webflow_api.products.list_products_url(site_id)`: List products & SKUs
- `webflow_api.products.get_product_url(site_id, product_id)`: Get product & SKUs
- `webflow_api.products.create_product_url(site_id)`: Create product
- `webflow_api.products.update_product_url(site_id, product_id)`: Update product

#### SKUs
- `webflow_api.skus.update_sku_url(site_id, product_id, sku_id)`: Update SKU

## Implementation Details

### URL Construction

The system uses a base `APIEndpoints` class that provides URL building functionality:

```python
def _build_url(self, endpoint: str) -> str:
    """Build full URL from base URL and endpoint path"""
    return f"{self.base_url.rstrip('/')}{endpoint}"
```

### Endpoint Organization

Endpoints are organized into logical groups:

```python
class PlytixAPI(APIEndpoints):
    def __init__(self, base_url: str = "https://pim.plytix.com/api/v1"):
        super().__init__(base_url)
        self.auth = PlytixAuthEndpoints()
        self.products = PlytixProductEndpoints(self)
        self.assets = PlytixAssetEndpoints(self)
        # ... other endpoint groups
```

### Pre-configured Instances

Pre-configured instances are available for immediate use:

```python
# Pre-configured instances for easy import
plytix_api = PlytixAPI()
webflow_api = WebflowAPI()
```

## Migration Guide

### From Hardcoded URLs

**Before:**
```python
url = f"https://pim.plytix.com/api/v1/products/{product_id}"
```

**After:**
```python
from app.config.endpoints import plytix_api
url = plytix_api.products.get_product_url(product_id)
```

### From String Formatting

**Before:**
```python
url = f"/sites/{site_id}/products/{product_id}"
```

**After:**
```python
from app.config.endpoints import webflow_api
endpoint = webflow_api.products.get_product_url(site_id, product_id).replace(webflow_api.base_url, "")
```

## Testing

Run the endpoint tests to verify functionality:

```bash
python test_endpoints.py
```

The test script verifies:
- ✅ All endpoints generate correct URLs
- ✅ Convenience functions work properly
- ✅ Custom base URLs are supported
- ✅ Code is maintainable and well-organized

## Benefits

### Before Refactoring
- ❌ Hardcoded URLs scattered throughout codebase
- ❌ Difficult to update API endpoints
- ❌ Inconsistent URL construction
- ❌ No centralized endpoint management

### After Refactoring
- ✅ Centralized endpoint management
- ✅ Easy to update and maintain
- ✅ Consistent URL construction
- ✅ Well-organized and documented
- ✅ Reusable and flexible
- ✅ Backward compatible

## Future Enhancements

1. **API Versioning**: Support for multiple API versions
2. **Environment-based URLs**: Different endpoints for dev/staging/prod
3. **Endpoint Validation**: Validate endpoint parameters
4. **Rate Limiting Integration**: Built-in rate limiting per endpoint
5. **Monitoring**: Track endpoint usage and performance

## Conclusion

The centralized endpoint management system provides a robust, maintainable solution for managing API URLs in the Plytix-Webflow integration. It improves code organization, reduces maintenance overhead, and provides a foundation for future enhancements.