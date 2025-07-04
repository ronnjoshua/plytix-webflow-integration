#!/usr/bin/env python3
"""
Check what products exist in Webflow
"""

import asyncio
import json
import httpx

async def check_webflow_products():
    """Check what products exist in Webflow"""
    
    # Load environment variables
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    token = os.getenv("WEBFLOW_TOKEN")
    site_id = os.getenv("WEBFLOW_SITE_ID") 
    collection_id = os.getenv("WEBFLOW_COLLECTION_ID")
    
    if not all([token, site_id, collection_id]):
        print("❌ Missing environment variables")
        return
    
    print("🔍 Checking Webflow products...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Get collection items (products)
            url = f"https://api.webflow.com/v2/sites/{site_id}/collections/{collection_id}/items"
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json"
            }
            
            print(f"   Fetching from: {url}")
            
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            items = data.get("items", [])
            
            print(f"📊 Total products in Webflow: {len(items)}")
            
            webflow_skus = []
            print("\n📋 Webflow products:")
            
            for i, item in enumerate(items, 1):
                # Extract product name (which should be the SKU in our case)
                field_data = item.get("fieldData", {})
                name = field_data.get("name", "no-name")
                sku = field_data.get("sku", name)  # Try sku field first, fallback to name
                
                webflow_skus.append(name)  # The sync service uses 'name' as SKU
                
                print(f"   {i:2d}. Name: {name:15} | SKU field: {sku:15} | ID: {item.get('id', 'no-id')}")
            
            print(f"\n📋 Summary:")
            print(f"   Webflow product names (used as SKUs): {sorted(webflow_skus)}")
            
            # Check if WACG-HP exists in Webflow
            if "WACG-HP" in webflow_skus:
                print(f"\n✅ WACG-HP EXISTS in Webflow - should be synced!")
            else:
                print(f"\n❌ WACG-HP does NOT exist in Webflow")
                print(f"   This is why it's not being updated!")
                print(f"   The sync service only updates existing products (UPDATE_ONLY_MODE=true)")
            
        except Exception as e:
            print(f"❌ Error checking Webflow: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    print("🕵️ Checking Webflow products...")
    asyncio.run(check_webflow_products())