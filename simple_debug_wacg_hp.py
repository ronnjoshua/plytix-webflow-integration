#!/usr/bin/env python3
"""
Simple debug script to find WACG-HP product - minimal dependencies
"""

import asyncio
import json

async def debug_wacg_hp_simple():
    """Debug WACG-HP product in Plytix only"""
    
    from app.clients.plytix_client import PlytixClient
    
    plytix_client = PlytixClient()
    
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
        
        # Get all SKUs and search for WACG-HP
        all_skus = []
        wacg_hp_found = False
        wacg_hp_product = None
        
        print("\n📋 All products found:")
        for i, product in enumerate(all_products, 1):
            # Extract SKU from product - check multiple possible fields
            sku = product.get("sku") or product.get("id") or f"product-{i}"
            all_skus.append(sku)
            
            print(f"   {i:2d}. SKU: {sku:15} | ID: {product.get('id', 'no-id'):25} | Label: {product.get('label', 'no-label')}")
            
            if sku == "WACG-HP":
                wacg_hp_found = True
                wacg_hp_product = product
        
        print(f"\n📋 Summary:")
        print(f"   Total products: {len(all_products)}")
        print(f"   All SKUs: {sorted(all_skus)}")
        
        if wacg_hp_found:
            print(f"\n✅ WACG-HP FOUND in Plytix!")
            print(f"   Product ID: {wacg_hp_product.get('id')}")
            print(f"   SKU: {wacg_hp_product.get('sku')}")
            print(f"   Label: {wacg_hp_product.get('label', 'no-label')}")
            print(f"   Name: {wacg_hp_product.get('name', 'no-name')}")
            print(f"   Full data: {json.dumps(wacg_hp_product, indent=2)}")
        else:
            print(f"\n❌ WACG-HP NOT FOUND in Plytix")
            print(f"   This explains why it's not being updated!")
            print(f"   The product doesn't exist in Plytix system.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await plytix_client.close()

if __name__ == "__main__":
    print("🕵️ Debugging WACG-HP product in Plytix...")
    asyncio.run(debug_wacg_hp_simple())