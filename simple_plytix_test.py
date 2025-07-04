#!/usr/bin/env python3
"""
Simple test to verify basic Plytix search without any filters
"""

import asyncio
import json

async def test_basic_plytix():
    """Test basic Plytix search without filters"""
    
    from app.clients.plytix_client import PlytixClient
    
    client = PlytixClient()
    
    try:
        print("🔐 Testing authentication...")
        auth_ok = await client.check_authentication()
        
        if not auth_ok:
            print("❌ Authentication failed")
            return False
        
        print("✅ Authentication successful")
        
        print("🔍 Testing basic search without filters...")
        
        # Test with minimal request body - only completed products
        response = await client.search_products(
            page=1,
            page_size=10,
            filters=None,  # No filters at all
            status="completed"  # Only completed products
        )
        
        products = response.get("data", [])
        pagination = response.get("pagination", {})
        
        print(f"✅ Search successful!")
        print(f"   Products found: {len(products)}")
        print(f"   Total count: {pagination.get('total_count', 'unknown')}")
        
        if products:
            sample = products[0]
            print(f"   Sample product: {sample.get('sku', 'no-sku')} - {sample.get('label', 'no-label')}")
        
        print("\n📋 Full response structure:")
        print(json.dumps(response, indent=2, default=str)[:500] + "...")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await client.close()

if __name__ == "__main__":
    print("🧪 Testing basic Plytix search...")
    success = asyncio.run(test_basic_plytix())
    
    if success:
        print("\n✅ Basic test passed!")
    else:
        print("\n❌ Basic test failed!")