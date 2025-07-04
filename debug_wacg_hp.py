#!/usr/bin/env python3
"""
Debug script to specifically search for WACG-HP product
"""

import asyncio
import json

async def debug_wacg_hp():
    """Debug WACG-HP product in both systems"""
    
    from app.clients.plytix_client import PlytixClient
    from app.clients.webflow_client import WebflowClient
    from app.services.field_mapping_service import FieldMappingService
    
    plytix_client = PlytixClient()
    webflow_client = WebflowClient()
    field_mapping_service = FieldMappingService(webflow_client=webflow_client)
    
    try:
        print("🔍 Searching for WACG-HP in Plytix...")
        
        # Get all products from Plytix
        all_products = []
        page = 1
        
        while True:
            print(f"   Fetching page {page}...")
            response = await plytix_client.search_products(page=page, page_size=50)
            products = response.get("data", [])
            
            if not products:
                break
                
            all_products.extend(products)
            page += 1
            
            # Safety limit
            if page > 5:
                break
        
        print(f"📊 Total products in Plytix: {len(all_products)}")
        
        # Search for WACG-HP specifically
        wacg_hp_found = False
        for product in all_products:
            sku = field_mapping_service.get_sku_from_product(product)
            print(f"   SKU: {sku}")
            
            if sku == "WACG-HP":
                wacg_hp_found = True
                print(f"✅ Found WACG-HP in Plytix!")
                print(f"   Product ID: {product.get('id')}")
                print(f"   Label: {product.get('label', 'no-label')}")
                print(f"   Name: {product.get('name', 'no-name')}")
                break
        
        if not wacg_hp_found:
            print("❌ WACG-HP NOT found in Plytix")
            
            # Show all SKUs for reference
            all_skus = []
            for product in all_products:
                sku = field_mapping_service.get_sku_from_product(product)
                all_skus.append(sku)
            
            print(f"📋 All SKUs found in Plytix: {sorted(all_skus)}")
        
        print("\n🔍 Checking Webflow...")
        
        # Initialize Webflow cache
        await webflow_client._initialize_products_cache()
        
        # Check if WACG-HP exists in Webflow
        webflow_product = await webflow_client.cache_service.get_webflow_product_by_name("WACG-HP")
        
        if webflow_product:
            print("✅ Found WACG-HP in Webflow!")
            print(f"   Product ID: {webflow_product.get('id')}")
            print(f"   Name: {webflow_product.get('fieldData', {}).get('name')}")
        else:
            print("❌ WACG-HP NOT found in Webflow")
        
        print("\n📋 Sync Eligibility Analysis:")
        if wacg_hp_found and webflow_product:
            print("✅ WACG-HP exists in both systems - SHOULD BE SYNCED")
        elif wacg_hp_found and not webflow_product:
            print("⚠️ WACG-HP exists in Plytix but not Webflow - WON'T BE SYNCED (CREATE mode disabled)")
        elif not wacg_hp_found and webflow_product:
            print("⚠️ WACG-HP exists in Webflow but not Plytix - CAN'T BE SYNCED")
        else:
            print("❌ WACG-HP doesn't exist in either system")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await plytix_client.close()
        await webflow_client.close()
        await field_mapping_service.asset_handler.close()

if __name__ == "__main__":
    print("🕵️ Debugging WACG-HP product...")
    asyncio.run(debug_wacg_hp())