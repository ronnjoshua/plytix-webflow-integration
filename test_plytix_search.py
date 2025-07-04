#!/usr/bin/env python3
"""
Simple test script to verify Plytix search API is working correctly
"""

import asyncio
import sys
import os

# Add the app directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.clients.plytix_client import PlytixClient
import structlog

# Setup basic logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

async def test_plytix_search():
    """Test basic Plytix search functionality"""
    
    client = PlytixClient()
    
    try:
        logger.info("Testing Plytix authentication...")
        
        # Test authentication
        auth_result = await client.check_authentication()
        if not auth_result:
            logger.error("❌ Authentication failed")
            return False
        
        logger.info("✅ Authentication successful")
        
        # Test basic search without filters
        logger.info("Testing basic search without filters...")
        
        response = await client.search_products(
            page=1,
            page_size=5,
            filters=None
        )
        
        products = response.get("data", [])
        logger.info("✅ Basic search successful", products_found=len(products))
        
        if products:
            first_product = products[0]
            logger.info("Sample product", 
                       id=first_product.get("id"), 
                       sku=first_product.get("sku"),
                       label=first_product.get("label"))
        
        # Test search with date filter in correct Plytix format
        logger.info("Testing search with date filter...")
        
        from datetime import datetime, timedelta
        since_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        # Correct Plytix format: array of arrays, date as YYYY-MM-DD
        filters = [[{
            "field": "modified",
            "operator": "gt",
            "value": since_date
        }]]
        
        response_filtered = await client.search_products(
            page=1,
            page_size=5,
            filters=filters
        )
        
        filtered_products = response_filtered.get("data", [])
        logger.info("✅ Filtered search successful", products_found=len(filtered_products))
        
        return True
        
    except Exception as e:
        logger.error("❌ Test failed", error=str(e))
        return False
        
    finally:
        await client.close()

if __name__ == "__main__":
    print("🧪 Testing Plytix Search API...")
    
    success = asyncio.run(test_plytix_search())
    
    if success:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Tests failed!")
        sys.exit(1)