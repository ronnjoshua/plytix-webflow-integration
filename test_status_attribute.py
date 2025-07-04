#!/usr/bin/env python3
"""
Test requesting status attribute explicitly from Plytix API
"""

import asyncio
import json

async def test_status_attribute():
    """Test requesting status attribute"""
    
    from app.clients.plytix_client import PlytixClient
    
    plytix_client = PlytixClient()
    
    try:
        print("🔍 Testing status attribute in Plytix API...")
        
        # Test 1: Request with status attribute explicitly
        print("\n🧪 Test 1: Request with 'status' in attributes")
        response = await plytix_client.search_products(
            page=1, 
            page_size=5,
            attributes=["status"]  # Request status attribute
        )
        products = response.get("data", [])
        print(f"   Products found: {len(products)}")
        
        if products:
            print("   Sample product with status attribute:")
            sample = products[0]
            print(f"   SKU: {sample.get('sku')}")
            print(f"   Status field: {sample.get('status', 'NOT FOUND')}")
            print(f"   All fields: {list(sample.keys())}")
            if sample.get('attributes'):
                print(f"   Attributes: {sample.get('attributes')}")
        
        # Test 2: Request common attributes that might include status
        print("\n🧪 Test 2: Request common attributes")
        common_attrs = ["status", "state", "workflow_status", "product_status", "approval_status"]
        response2 = await plytix_client.search_products(
            page=1, 
            page_size=5,
            attributes=common_attrs
        )
        products2 = response2.get("data", [])
        print(f"   Products found: {len(products2)}")
        
        if products2:
            sample2 = products2[0]
            print(f"   Sample with common attributes:")
            for attr in common_attrs:
                print(f"     {attr}: {sample2.get(attr, 'NOT FOUND')}")
            print(f"   Attributes object: {sample2.get('attributes', {})}")
        
        # Test 3: Get detailed product to see all available fields
        print("\n🧪 Test 3: Get detailed product info")
        if products:
            product_id = products[0].get("id")
            if product_id:
                try:
                    # Enrich product details
                    from app.models.plytix import PlytixProduct
                    detailed_product = PlytixProduct(**products[0])
                    await plytix_client._enrich_product_details(detailed_product)
                    
                    print(f"   Detailed product fields:")
                    detailed_dict = detailed_product.__dict__
                    for field, value in detailed_dict.items():
                        if "status" in field.lower() or "state" in field.lower():
                            print(f"     {field}: {value}")
                    
                    print(f"   All detailed fields: {list(detailed_dict.keys())}")
                    
                except Exception as e:
                    print(f"   Error getting detailed product: {e}")
        
        # Test 4: Try the status filter with the attribute
        print("\n🧪 Test 4: Try status filter with 'Completed' value")
        try:
            response4 = await plytix_client.search_products(
                page=1, 
                page_size=5,
                attributes=["status"],
                status="Completed"  # Try with capital C
            )
            count = len(response4.get("data", []))
            print(f"   Status 'Completed': {count} products")
        except Exception as e:
            print(f"   Status 'Completed': ERROR - {e}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await plytix_client.close()

if __name__ == "__main__":
    print("🧪 Testing status attribute...")
    asyncio.run(test_status_attribute())