from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from typing import Optional
from functools import lru_cache

class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore"  # Allow extra environment variables
    )
    
    # Application
    DEBUG: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")
    
    # Plytix Configuration
    PLYTIX_API_KEY: str = Field(default="test_key", description="Plytix API Key")
    PLYTIX_API_PASSWORD: str = Field(default="test_password", description="Plytix API Password")
    PLYTIX_BASE_URL: str = Field(default="https://pim.plytix.com/api/v1")
    PLYTIX_RATE_LIMIT: int = Field(default=50, description="Requests per 10 seconds")
    
    # Webflow Configuration
    WEBFLOW_TOKEN: str = Field(default="test_token", description="Webflow API Token")
    WEBFLOW_SITE_ID: str = Field(default="test_site_id", description="Webflow Site ID")
    WEBFLOW_COLLECTION_ID: str = Field(default="test_collection_id", description="Default Webflow E-commerce Collection ID")
    WEBFLOW_BASE_URL: str = Field(default="https://api.webflow.com/v2")
    WEBFLOW_RATE_LIMIT: int = Field(default=60, description="Requests per minute")
    
    # Collection Mapping Configuration
    ENABLE_DYNAMIC_COLLECTIONS: bool = Field(default=False, description="Enable dynamic collection mapping based on product data")
    COLLECTION_MAPPING_STRATEGY: str = Field(default="category", description="Strategy for collection mapping: category, brand, product_type")
    
    # Sync Behavior Configuration
    ENABLE_PRODUCT_CREATION: bool = Field(default=False, description="Allow creating new products in Webflow. If False, only update existing products.")
    UPDATE_ONLY_MODE: bool = Field(default=True, description="Only update existing products, skip products not found in Webflow")
    
    # Database
    DATABASE_URL: str = Field(default="sqlite:///./test.db", description="Database connection string")
    
    # Redis/Celery
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0")
    
    # Scheduling
    SYNC_SCHEDULE_PRODUCTION: str = Field(default="0 0 */2 * *")  # Every 2 days
    SYNC_SCHEDULE_TESTING: str = Field(default="*/1 * * * *")     # Every minute
    
    # Monitoring
    SENTRY_DSN: Optional[str] = Field(default=None)
    PROMETHEUS_PORT: int = Field(default=8001)
    
    # Additional settings (with defaults to avoid validation errors)
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="password")
    POSTGRES_DB: str = Field(default="integration_db")
    POSTGRES_PORT: int = Field(default=5432)
    REDIS_PORT: int = Field(default=6379)
    API_PORT: int = Field(default=8000)
    SYNC_FREQUENCY_MINUTES: int = Field(default=30)
    MAX_PRODUCTS_PER_SYNC: int = Field(default=100)
    ENABLE_AUTO_PUBLISH: bool = Field(default=True)
    FIELD_MAPPING_FILE: str = Field(default="field_mappings.json")
    FLOWER_PORT: int = Field(default=5555)
    FLOWER_USER: str = Field(default="admin")
    FLOWER_PASS: str = Field(default="admin")
    API_TIMEOUT: int = Field(default=30)
    RETRY_ATTEMPTS: int = Field(default=3)
    MAX_CONCURRENT_REQUESTS: int = Field(default=5)
    ENVIRONMENT: str = Field(default="development")
    PLYTIX_ENV: str = Field(default="development")
    LOG_FILE: str = Field(default="logs/app.log")
    ENABLE_STRUCTURED_LOGGING: bool = Field(default=True)
    ENABLE_ERROR_NOTIFICATIONS: bool = Field(default=False)

@lru_cache()
def get_settings() -> Settings:
    return Settings()