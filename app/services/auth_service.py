"""Authentication service for checking API credentials"""
import asyncio
import structlog
from typing import Dict, Tuple

from app.clients.plytix_client import PlytixClient
from app.clients.webflow_client import WebflowClient
from app.core.exceptions import PlytixAPIError, WebflowAPIError

logger = structlog.get_logger()

class AuthService:
    """Service for checking authentication status of all APIs"""
    
    def __init__(self):
        self.plytix_client = None
        self.webflow_client = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.plytix_client = PlytixClient()
        self.webflow_client = WebflowClient()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.plytix_client:
            await self.plytix_client.close()
        if self.webflow_client:
            await self.webflow_client.close()
    
    async def check_plytix_auth(self) -> Tuple[bool, str]:
        """Check Plytix authentication status"""
        try:
            if not self.plytix_client:
                self.plytix_client = PlytixClient()
            
            is_valid = await self.plytix_client.check_authentication()
            if is_valid:
                return True, "Plytix authentication successful"
            else:
                return False, "Plytix authentication failed"
        except Exception as e:
            error_msg = f"Plytix authentication error: {str(e)}"
            logger.error("❌ Plytix auth check failed", error=str(e))
            return False, error_msg
    
    async def check_webflow_auth(self) -> Tuple[bool, str]:
        """Check Webflow authentication status"""
        try:
            if not self.webflow_client:
                self.webflow_client = WebflowClient()
            
            is_valid = await self.webflow_client.check_authentication()
            if is_valid:
                return True, "Webflow authentication successful"
            else:
                return False, "Webflow authentication failed"
        except Exception as e:
            error_msg = f"Webflow authentication error: {str(e)}"
            logger.error("❌ Webflow auth check failed", error=str(e))
            return False, error_msg
    
    async def check_all_auth(self) -> Dict[str, Dict[str, any]]:
        """Check authentication for both Plytix and Webflow"""
        logger.info("🔍 Starting comprehensive authentication check...")
        
        # Run both checks concurrently
        plytix_task = self.check_plytix_auth()
        webflow_task = self.check_webflow_auth()
        
        plytix_result, webflow_result = await asyncio.gather(
            plytix_task, webflow_task, return_exceptions=True
        )
        
        # Handle exceptions from asyncio.gather
        if isinstance(plytix_result, Exception):
            plytix_result = (False, f"Plytix check failed: {str(plytix_result)}")
        
        if isinstance(webflow_result, Exception):
            webflow_result = (False, f"Webflow check failed: {str(webflow_result)}")
        
        results = {
            "plytix": {
                "status": "success" if plytix_result[0] else "failed",
                "authenticated": plytix_result[0],
                "message": plytix_result[1]
            },
            "webflow": {
                "status": "success" if webflow_result[0] else "failed",
                "authenticated": webflow_result[0],
                "message": webflow_result[1]
            }
        }
        
        # Overall status
        all_success = plytix_result[0] and webflow_result[0]
        results["overall"] = {
            "status": "success" if all_success else "failed",
            "authenticated": all_success,
            "message": "All APIs authenticated successfully" if all_success else "One or more APIs failed authentication"
        }
        
        # Log comprehensive results
        if all_success:
            logger.info("🎉 All API authentication checks passed!", 
                       plytix=plytix_result[1], 
                       webflow=webflow_result[1])
        else:
            logger.error("❌ API authentication issues detected",
                        plytix_status=plytix_result[0],
                        webflow_status=webflow_result[0],
                        plytix_msg=plytix_result[1],
                        webflow_msg=webflow_result[1])
        
        return results

async def check_api_credentials() -> Dict[str, Dict[str, any]]:
    """Standalone function to check all API credentials"""
    async with AuthService() as auth_service:
        return await auth_service.check_all_auth()