#!/usr/bin/env python3
"""
Check what status values exist on products in Plytix
"""

import asyncio
import json

async def check_product_status():
    """Check product status values in Plytix"""
    
    from app.clients.plytix_client import PlytixClient
    
    plytix_client = PlytixClient()
    
    try:
        print("🔍 Checking product status values in Plytix...")
        
        # Get products WITHOUT status filter to see what's available
        response = await plytix_client.search_products(page=1, page_size=20)  # No status filter
        products = response.get("data", [])
        
        print(f"📊 Total products found (without status filter): {len(products)}")
        
        if not products:
            print("❌ No products found at all")
            return
        
        # Check status fields in products
        status_values = set()
        status_fields = set()
        
        print("\n📋 Product status analysis:")
        for i, product in enumerate(products, 1):
            product_id = product.get("id", f"product-{i}")
            sku = product.get("sku", "no-sku")
            
            # Check all possible status-related fields
            for field_name in product.keys():
                if "status" in field_name.lower() or "state" in field_name.lower():
                    status_fields.add(field_name)
                    status_values.add(str(product.get(field_name)))
            
            # Also check attributes
            attributes = product.get("attributes", {})
            for attr_name, attr_value in attributes.items():
                if "status" in attr_name.lower() or "state" in attr_name.lower():
                    status_fields.add(f"attributes.{attr_name}")
                    status_values.add(str(attr_value))
            
            print(f"   {i:2d}. SKU: {sku:15} | ID: {product_id[:15]:15}...")
            
            # Show first few products in detail
            if i <= 3:
                print(f"       Status-related fields:")
                for field in sorted(product.keys()):
                    if "status" in field.lower() or "state" in field.lower():
                        print(f"         {field}: {product.get(field)}")
                
                if attributes:
                    print(f"       Attributes with status/state:")
                    for attr_name, attr_value in attributes.items():
                        if "status" in attr_name.lower() or "state" in attr_name.lower():
                            print(f"         attributes.{attr_name}: {attr_value}")
        
        print(f"\n📋 Summary:")
        print(f"   Status-related fields found: {sorted(status_fields)}")
        print(f"   Status values found: {sorted(status_values)}")
        
        # Test different status values
        if status_values:
            print(f"\n🧪 Testing different status values:")
            for status_value in sorted(status_values):
                if status_value and status_value != "None":
                    try:
                        test_response = await plytix_client.search_products(
                            page=1, 
                            page_size=5, 
                            status=status_value
                        )
                        count = len(test_response.get("data", []))
                        print(f"   Status '{status_value}': {count} products")
                    except Exception as e:
                        print(f"   Status '{status_value}': ERROR - {e}")
        
        # Check if any products have a 'completed' status anywhere
        print(f"\n🔍 Searching for 'completed' in product data:")
        for i, product in enumerate(products, 1):
            product_str = json.dumps(product, default=str).lower()
            if "completed" in product_str:
                print(f"   Product {i} ({product.get('sku', 'no-sku')}) contains 'completed'")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await plytix_client.close()

if __name__ == "__main__":
    print("🔍 Checking product status values...")
    asyncio.run(check_product_status())