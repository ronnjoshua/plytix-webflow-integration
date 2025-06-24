class PlytixWebflowIntegrationException(Exception):
    """Base exception for the integration"""
    pass

class PlytixAPIError(PlytixWebflowIntegrationException):
    """Exception raised for Plytix API errors"""
    pass

class WebflowAPIError(PlytixWebflowIntegrationException):
    """Exception raised for Webflow API errors"""
    pass

class SyncError(PlytixWebflowIntegrationException):
    """Exception raised during synchronization process"""
    pass

class ValidationError(PlytixWebflowIntegrationException):
    """Exception raised for data validation errors"""
    pass