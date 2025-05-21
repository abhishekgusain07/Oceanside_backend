"""
Request tracking system for monitoring active requests.
"""
import time
from typing import Dict, Set
import asyncio
import structlog
from contextlib import asynccontextmanager

logger = structlog.get_logger(__name__)

class RequestTracker:
    """Tracks active requests in the application."""
    
    def __init__(self):
        self._active_requests: Dict[str, dict] = {}
        self._lock = asyncio.Lock()
    
    async def add_request(self, request_id: str, method: str, path: str):
        """Add a new request to tracking."""
        async with self._lock:
            self._active_requests[request_id] = {
                "method": method,
                "path": path,
                "start_time": time.time(),
                "status": "processing"
            }
            logger.debug(
                "Request started tracking",
                request_id=request_id,
                method=method,
                path=path
            )
    
    async def complete_request(self, request_id: str, status_code: int):
        """Mark a request as completed."""
        async with self._lock:
            if request_id in self._active_requests:
                request = self._active_requests[request_id]
                request["status"] = "completed"
                request["status_code"] = status_code
                request["duration"] = time.time() - request["start_time"]
                logger.debug(
                    "Request completed",
                    request_id=request_id,
                    duration=request["duration"],
                    status_code=status_code
                )
    
    async def get_active_requests(self) -> Dict[str, dict]:
        """Get all currently active requests."""
        async with self._lock:
            return {
                rid: req for rid, req in self._active_requests.items()
                if req["status"] == "processing"
            }
    
    async def get_request_stats(self) -> dict:
        """Get statistics about requests."""
        async with self._lock:
            active = len([r for r in self._active_requests.values() if r["status"] == "processing"])
            completed = len([r for r in self._active_requests.values() if r["status"] == "completed"])
            
            # Calculate average duration for completed requests
            durations = [r["duration"] for r in self._active_requests.values() if r["status"] == "completed"]
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            return {
                "active_requests": active,
                "completed_requests": completed,
                "average_duration": avg_duration
            }
    
    @asynccontextmanager
    async def track_request(self, request_id: str, method: str, path: str):
        """Context manager for tracking a request."""
        await self.add_request(request_id, method, path)
        try:
            yield
        finally:
            # Note: status_code will be set by the middleware
            pass

# Global request tracker instance
request_tracker = RequestTracker() 