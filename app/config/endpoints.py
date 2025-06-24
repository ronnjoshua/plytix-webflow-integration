"""
Centralized API endpoint management for Plytix and Webflow integrations.
This module provides organized and reusable endpoint URL management.
"""

from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class APIEndpoints:
    """Base class for API endpoint management"""
    base_url: str
    
    def _build_url(self, endpoint: str) -> str:
        """Build full URL from base URL and endpoint path"""
        return f"{self.base_url.rstrip('/')}{endpoint}"


class PlytixAPI(APIEndpoints):
    """
    Centralized Plytix PIM API endpoint management.
    
    Groups endpoints by functionality and provides methods for dynamic URL construction.
    All endpoints are based on Plytix PIM API v1 documentation.
    """
    
    def __init__(self, base_url: str = "https://pim.plytix.com/api/v1"):
        super().__init__(base_url)
        
        # Authentication endpoints
        self.auth = PlytixAuthEndpoints()
        
        # Product endpoints
        self.products = PlytixProductEndpoints(self)
        
        # Asset endpoints  
        self.assets = PlytixAssetEndpoints(self)
        
        # Attribute endpoints
        self.attributes = PlytixAttributeEndpoints(self)
        
        # Filter endpoints
        self.filters = PlytixFilterEndpoints(self)


class PlytixAuthEndpoints:
    """Plytix authentication endpoints"""
    
    # Static auth endpoint (different base URL)
    AUTH_TOKEN_URL = "https://auth.plytix.com/auth/api/get-token"


class PlytixProductEndpoints:
    """Plytix product-related endpoints"""
    
    def __init__(self, api: PlytixAPI):
        self.api = api
        
        # Static endpoints
        self.SEARCH = "/products/search"
        self.LIST = "/products"
    
    def get_search_url(self) -> str:
        """
        Get product search endpoint (POST request)
        
        This endpoint is used to search and list all products with advanced filtering.
        Method: POST
        URL: https://pim.plytix.com/api/v1/products/search
        
        Example usage:
        POST {base_url}/products/search
        Body: {
            "pagination": {"page": 1, "page_size": 25},
            "sorting": {"field": "updated_at", "direction": "desc"},
            "filters": {...}
        }
        """
        return self.api._build_url(self.SEARCH)
    
    def get_list_url(self) -> str:
        """
        Get products list endpoint (GET request)
        
        Alternative to search endpoint for simple product listing.
        Method: GET
        URL: https://pim.plytix.com/api/v1/products
        """
        return self.api._build_url(self.LIST)
    
    def get_product_url(self, product_id: str) -> str:
        """Get product data endpoint"""
        return self.api._build_url(f"/products/{product_id}")
    
    def get_variants_url(self, product_id: str) -> str:
        """Get product variants endpoint"""
        return self.api._build_url(f"/products/{product_id}/variants")


class PlytixAssetEndpoints:
    """Plytix asset-related endpoints"""
    
    def __init__(self, api: PlytixAPI):
        self.api = api
    
    def get_all_assets_url(self, product_id: str) -> str:
        """Get all product assets endpoint"""
        return self.api._build_url(f"/products/{product_id}/assets")
    
    def get_asset_url(self, product_id: str, asset_id: str) -> str:
        """Get specific product asset endpoint"""
        return self.api._build_url(f"/products/{product_id}/assets/{asset_id}")


class PlytixAttributeEndpoints:
    """Plytix attribute-related endpoints"""
    
    def __init__(self, api: PlytixAPI):
        self.api = api
    
    def get_product_attribute_url(self, attribute_id: str) -> str:
        """Get product attribute endpoint"""
        return self.api._build_url(f"/attributes/product/{attribute_id}")


class PlytixFilterEndpoints:
    """Plytix filter-related endpoints"""
    
    def __init__(self, api: PlytixAPI):
        self.api = api
        
        # Static endpoints
        self.PRODUCT_FILTERS = "/filters/product"
    
    def get_product_filters_url(self) -> str:
        """Get available product filters endpoint"""
        return self.api._build_url(self.PRODUCT_FILTERS)


class WebflowAPI(APIEndpoints):
    """
    Centralized Webflow eCommerce API endpoint management.
    
    Groups endpoints by functionality and provides methods for dynamic URL construction.
    All endpoints are based on Webflow API v2 documentation.
    """
    
    def __init__(self, base_url: str = "https://api.webflow.com/v2"):
        super().__init__(base_url)
        
        # Site endpoints
        self.sites = WebflowSiteEndpoints(self)
        
        # Asset endpoints
        self.assets = WebflowAssetEndpoints(self)
        
        # Product endpoints
        self.products = WebflowProductEndpoints(self)
        
        # SKU endpoints
        self.skus = WebflowSKUEndpoints(self)


class WebflowSiteEndpoints:
    """Webflow site-related endpoints"""
    
    def __init__(self, api: WebflowAPI):
        self.api = api
        
        # Static endpoints
        self.LIST_SITES = "/sites"
    
    def get_site_url(self, site_id: str) -> str:
        """Get site endpoint"""
        return self.api._build_url(f"/sites/{site_id}")
    
    def list_sites_url(self) -> str:
        """List sites endpoint"""
        return self.api._build_url(self.LIST_SITES)


class WebflowAssetEndpoints:
    """Webflow asset-related endpoints"""
    
    def __init__(self, api: WebflowAPI):
        self.api = api
        
        # Static endpoints (asset ID endpoints don't need site_id)
        self.GET_ASSET_TEMPLATE = "/assets/{asset_id}"
    
    def list_assets_url(self, site_id: str) -> str:
        """List assets endpoint"""
        return self.api._build_url(f"/sites/{site_id}/assets")
    
    def get_asset_url(self, asset_id: str) -> str:
        """Get asset endpoint"""
        return self.api._build_url(f"/assets/{asset_id}")


class WebflowProductEndpoints:
    """Webflow product-related endpoints"""
    
    def __init__(self, api: WebflowAPI):
        self.api = api
    
    def list_products_url(self, site_id: str) -> str:
        """List products & SKUs endpoint"""
        return self.api._build_url(f"/sites/{site_id}/products")
    
    def get_product_url(self, site_id: str, product_id: str) -> str:
        """Get product & SKUs endpoint"""
        return self.api._build_url(f"/sites/{site_id}/products/{product_id}")
    
    def update_product_url(self, site_id: str, product_id: str) -> str:
        """Update product endpoint"""
        return self.api._build_url(f"/sites/{site_id}/products/{product_id}")
    
    def create_product_url(self, site_id: str) -> str:
        """Create product endpoint"""
        return self.api._build_url(f"/sites/{site_id}/products")


class WebflowSKUEndpoints:
    """Webflow SKU-related endpoints"""
    
    def __init__(self, api: WebflowAPI):
        self.api = api
    
    def update_sku_url(self, site_id: str, product_id: str, sku_id: str) -> str:
        """Update SKU endpoint"""
        return self.api._build_url(f"/sites/{site_id}/products/{product_id}/skus/{sku_id}")


# Pre-configured instances for easy import
plytix_api = PlytixAPI()
webflow_api = WebflowAPI()


# Convenience functions for backward compatibility
def get_plytix_product_search_url() -> str:
    """Get Plytix product search URL (POST endpoint)"""
    return plytix_api.products.get_search_url()


def get_plytix_product_url(product_id: str) -> str:
    """Get Plytix product URL"""
    return plytix_api.products.get_product_url(product_id)


def get_plytix_variants_url(product_id: str) -> str:
    """Get Plytix product variants URL"""
    return plytix_api.products.get_variants_url(product_id)


def get_plytix_assets_url(product_id: str, asset_id: Optional[str] = None) -> str:
    """Get Plytix product assets URL"""
    if asset_id:
        return plytix_api.assets.get_asset_url(product_id, asset_id)
    return plytix_api.assets.get_all_assets_url(product_id)


def get_webflow_products_url(site_id: str) -> str:
    """Get Webflow products list URL"""
    return webflow_api.products.list_products_url(site_id)


def get_webflow_product_url(site_id: str, product_id: str) -> str:
    """Get Webflow product URL"""
    return webflow_api.products.get_product_url(site_id, product_id)


def get_webflow_update_product_url(site_id: str, product_id: str) -> str:
    """Get Webflow update product URL"""
    return webflow_api.products.update_product_url(site_id, product_id)


def get_webflow_update_sku_url(site_id: str, product_id: str, sku_id: str) -> str:
    """Get Webflow update SKU URL"""
    return webflow_api.skus.update_sku_url(site_id, product_id, sku_id)


# Example usage and documentation
if __name__ == "__main__":
    # Example usage demonstrations
    
    print("=== Plytix API Endpoints ===")
    print(f"Product search (POST): {plytix_api.products.get_search_url()}")
    print(f"Product list (GET): {plytix_api.products.get_list_url()}")
    print(f"Product details: {plytix_api.products.get_product_url('123')}")
    print(f"Product variants: {plytix_api.products.get_variants_url('123')}")
    print(f"All assets: {plytix_api.assets.get_all_assets_url('123')}")
    print(f"Specific asset: {plytix_api.assets.get_asset_url('123', 'asset-456')}")
    print(f"Product filters: {plytix_api.filters.get_product_filters_url()}")
    print(f"Auth token: {plytix_api.auth.AUTH_TOKEN_URL}")
    
    print("\n=== Webflow API Endpoints ===")
    print(f"List sites: {webflow_api.sites.list_sites_url()}")
    print(f"Get site: {webflow_api.sites.get_site_url('site-123')}")
    print(f"List products: {webflow_api.products.list_products_url('site-123')}")
    print(f"Get product: {webflow_api.products.get_product_url('site-123', 'prod-456')}")
    print(f"Update product: {webflow_api.products.update_product_url('site-123', 'prod-456')}")
    print(f"Update SKU: {webflow_api.skus.update_sku_url('site-123', 'prod-456', 'sku-789')}")
    print(f"List assets: {webflow_api.assets.list_assets_url('site-123')}")
    print(f"Get asset: {webflow_api.assets.get_asset_url('asset-123')}")
    
    print("\n=== Convenience Functions ===")
    print(f"Plytix product search: {get_plytix_product_search_url()}")
    print(f"Plytix product: {get_plytix_product_url('123')}")
    print(f"Webflow products: {get_webflow_products_url('site-123')}")