import asyncio
from typing import Dict
from time import time

class RateLimiter:
    """Async rate limiter for API calls"""
    
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Dict[float, int] = {}
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Acquire permission to make a request"""
        async with self._lock:
            current_time = time()
            
            # Clean up old entries
            cutoff_time = current_time - self.time_window
            self.requests = {
                timestamp: count 
                for timestamp, count in self.requests.items()
                if timestamp > cutoff_time
            }
            
            # Count current requests in time window
            total_requests = sum(self.requests.values())
            
            if total_requests >= self.max_requests:
                # Calculate sleep time
                oldest_request = min(self.requests.keys()) if self.requests else current_time
                sleep_time = self.time_window - (current_time - oldest_request) + 0.1
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    return await self.acquire()  # Retry after sleeping
            
            # Record this request
            self.requests[current_time] = self.requests.get(current_time, 0) + 1