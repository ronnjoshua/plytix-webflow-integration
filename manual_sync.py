#!/usr/bin/env python3
"""
Manual Sync Script for Production Testing
Run this script to trigger a manual sync with detailed logging
"""
import asyncio
import requests
import json
import time
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"
SYNC_ENDPOINT = f"{API_BASE_URL}/sync/trigger"
STATUS_ENDPOINT = f"{API_BASE_URL}/sync/status"
HEALTH_ENDPOINT = f"{API_BASE_URL}/health/detailed"

async def trigger_manual_sync(test_mode: bool = True):
    """Trigger manual sync and monitor progress"""
    
    print("🚀 Starting Manual Sync...")
    print(f"📅 Time: {datetime.now().isoformat()}")
    print(f"🧪 Test Mode: {test_mode}")
    print("-" * 50)
    
    # 1. Check API health first
    print("🔍 Checking API health...")
    try:
        health_response = requests.get(HEALTH_ENDPOINT, timeout=10)
        if health_response.status_code == 200:
            health_data = health_response.json()
            print(f"✅ API Health: {health_data.get('service', 'unknown')}")
            
            # Check authentication from the actual health response format
            plytix_auth = health_data.get('plytix_api') == 'healthy'
            webflow_auth = health_data.get('webflow_api') == 'healthy'
            database_health = health_data.get('database') == 'healthy'
            
            print(f"🔐 Plytix Auth: {'✅' if plytix_auth else '❌'}")
            print(f"🔐 Webflow Auth: {'✅' if webflow_auth else '❌'}")
            print(f"🗄️ Database: {'✅' if database_health else '❌'}")
            
            if not (plytix_auth and webflow_auth and database_health):
                print("❌ Some services are not healthy. Check the issues above.")
                print("Continuing anyway...")
                # Don't return - continue with sync attempt
        else:
            print(f"❌ API Health Check Failed: {health_response.status_code}")
            return
    except Exception as e:
        print(f"❌ Cannot reach API: {e}")
        return
    
    print()
    
    # 2. Trigger sync
    print("🎯 Triggering sync...")
    try:
        sync_payload = {
            "test_mode": test_mode,
            "force_full_sync": True
        }
        
        sync_response = requests.post(
            SYNC_ENDPOINT, 
            json=sync_payload,
            timeout=30
        )
        
        if sync_response.status_code == 200:
            sync_data = sync_response.json()
            task_id = sync_data.get('task_id')
            
            print(f"✅ Sync triggered successfully!")
            print(f"📋 Task ID: {task_id}")
            print(f"⏳ Status: {sync_data.get('status', 'unknown')}")
            
            if task_id:
                await monitor_sync_progress(task_id)
            
        else:
            print(f"❌ Sync trigger failed: {sync_response.status_code}")
            print(f"📝 Response: {sync_response.text}")
            
    except Exception as e:
        print(f"❌ Sync trigger error: {e}")

async def monitor_sync_progress(task_id: str, max_wait_minutes: int = 10):
    """Monitor sync progress using task ID"""
    
    print(f"\n📊 Monitoring sync progress for task: {task_id}")
    print("-" * 50)
    
    start_time = time.time()
    max_wait_seconds = max_wait_minutes * 60
    check_interval = 10  # seconds
    
    while True:
        try:
            # Check if we've exceeded max wait time
            elapsed = time.time() - start_time
            if elapsed > max_wait_seconds:
                print(f"⏰ Monitoring timeout after {max_wait_minutes} minutes")
                break
            
            # Get task status
            status_response = requests.get(
                f"{STATUS_ENDPOINT}/{task_id}",
                timeout=10
            )
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                
                task_status = status_data.get('status', 'unknown')
                progress = status_data.get('progress', {})
                
                print(f"📈 Status: {task_status}")
                if progress:
                    products = progress.get('products_processed', 0)
                    variants = progress.get('variants_processed', 0)
                    errors = progress.get('errors_count', 0)
                    print(f"   Products: {products} | Variants: {variants} | Errors: {errors}")
                
                # Check if sync is complete
                if task_status in ['completed', 'failed', 'error']:
                    print(f"\n🏁 Sync finished with status: {task_status}")
                    
                    if task_status == 'completed':
                        print("✅ Sync completed successfully!")
                    else:
                        print("❌ Sync failed or encountered errors")
                        
                    # Show final results
                    if progress:
                        print(f"📊 Final Results:")
                        print(f"   Products Processed: {progress.get('products_processed', 0)}")
                        print(f"   Variants Processed: {progress.get('variants_processed', 0)}")
                        print(f"   Errors: {progress.get('errors_count', 0)}")
                        print(f"   Duration: {progress.get('duration_seconds', 0)} seconds")
                    
                    break
                
            else:
                print(f"⚠️ Status check failed: {status_response.status_code}")
            
            # Wait before next check
            print(f"⏳ Waiting {check_interval}s... (elapsed: {elapsed:.0f}s)")
            await asyncio.sleep(check_interval)
            
        except Exception as e:
            print(f"❌ Status check error: {e}")
            await asyncio.sleep(check_interval)

def get_sync_history():
    """Get recent sync history"""
    print("\n📋 Recent Sync History:")
    print("-" * 50)
    
    try:
        history_response = requests.get(f"{API_BASE_URL}/sync/history", timeout=10)
        
        if history_response.status_code == 200:
            history_data = history_response.json()
            
            # Handle different response formats
            if isinstance(history_data, list):
                syncs = history_data
            else:
                syncs = history_data.get('syncs', history_data.get('items', []))
            
            if syncs:
                for sync in syncs[-5:]:  # Show last 5 syncs
                    if isinstance(sync, dict):
                        status = sync.get('status', 'unknown')
                        started = sync.get('started_at', sync.get('created_at', 'unknown'))
                        products = sync.get('products_processed', 0)
                        errors = sync.get('errors_count', 0)
                        
                        print(f"📅 {started} | Status: {status} | Products: {products} | Errors: {errors}")
                    else:
                        print(f"📝 Sync entry: {sync}")
            else:
                print("📝 No sync history found")
        else:
            print(f"❌ History fetch failed: {history_response.status_code}")
            
    except Exception as e:
        print(f"❌ History fetch error: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Manual Sync Script")
    parser.add_argument("--production", action="store_true", help="Run in production mode (processes all products)")
    parser.add_argument("--history-only", action="store_true", help="Only show sync history")
    
    args = parser.parse_args()
    
    if args.history_only:
        get_sync_history()
    else:
        test_mode = not args.production
        asyncio.run(trigger_manual_sync(test_mode=test_mode))
        get_sync_history()