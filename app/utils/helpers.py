import re
from typing import Optional, Dict, Any
from datetime import datetime
import structlog

logger = structlog.get_logger()

def sanitize_sku(sku: str) -> str:
    """Sanitize SKU to ensure it's valid for both systems"""
    if not sku:
        return ""
    
    # Remove special characters and ensure alphanumeric with hyphens/underscores
    sanitized = re.sub(r'[^a-zA-Z0-9\-_]', '-', sku.strip())
    sanitized = re.sub(r'-+', '-', sanitized)
    return sanitized.strip('-')

def validate_price(price: Optional[float]) -> bool:
    """Validate that price is a positive number"""
    if price is None:
        return True  # None is acceptable
    return isinstance(price, (int, float)) and price >= 0

def validate_inventory(inventory: Optional[int]) -> bool:
    """Validate that inventory is a non-negative integer"""
    if inventory is None:
        return True  # None is acceptable
    return isinstance(inventory, int) and inventory >= 0

def safe_get_nested(data: Dict[str, Any], path: str, default: Any = None) -> Any:
    """Safely get nested dictionary value using dot notation"""
    keys = path.split('.')
    current = data
    
    try:
        for key in keys:
            current = current[key]
        return current
    except (KeyError, TypeError):
        return default

def format_currency_cents(amount: float) -> int:
    """Convert currency amount to cents"""
    if amount is None:
        return 0
    return int(round(amount * 100))

def format_currency_dollars(cents: int) -> float:
    """Convert cents to dollar amount"""
    if cents is None:
        return 0.0
    return round(cents / 100, 2)

def truncate_string(text: str, max_length: int = 255) -> str:
    """Truncate string to maximum length"""
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    # Try to truncate at word boundary
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length * 0.8:  # If we find a space in the last 20%
        return truncated[:last_space] + "..."
    else:
        return truncated[:max_length-3] + "..."

def generate_unique_slug(base_slug: str, existing_slugs: set) -> str:
    """Generate a unique slug by appending numbers if needed"""
    if base_slug not in existing_slugs:
        return base_slug
    
    counter = 1
    while f"{base_slug}-{counter}" in existing_slugs:
        counter += 1
    
    return f"{base_slug}-{counter}"

def log_performance(func_name: str, start_time: datetime, end_time: datetime, **kwargs):
    """Log performance metrics for a function"""
    duration = (end_time - start_time).total_seconds()
    logger.info(
        "Performance metric",
        function=func_name,
        duration_seconds=round(duration, 3),
        **kwargs
    )