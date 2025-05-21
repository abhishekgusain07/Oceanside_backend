"""
Middleware components for the FastAPI application.
"""
import uuid
from contextvars import ContextVar
from typing import Callable, Dict, Any, Tuple
import time
from fastapi.responses import JSONResponse

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from app.core.request_tracker import request_tracker

# Create a context variable to store request ID
request_id_contextvar: ContextVar[str] = ContextVar("request_id", default="")
logger = structlog.get_logger(__name__)

# Rate limiting configuration
RATE_LIMIT_WINDOW = 60  # 1 minute window
MAX_REQUESTS = 100  # Maximum requests per window

# In-memory rate limiting store (in production, use Redis)
rate_limit_store: Dict[str, Tuple[int, float]] = {}

class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds a unique request ID to each request.
    
    This ID is added to:
    - Response headers
    - Structlog context for logging
    - Request tracking system
    """
    
    def __init__(self, app: ASGIApp, header_name: str = "X-Request-ID"):
        super().__init__(app)
        self.header_name = header_name
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract request ID from header or generate a new one
        request_id = request.headers.get(self.header_name) or str(uuid.uuid4())
        
        # Store in context var for structlog
        token = request_id_contextvar.set(request_id)
        
        try:
            # Add request_id to the structlog context
            structlog.contextvars.clear_contextvars()
            structlog.contextvars.bind_contextvars(request_id=request_id)
            
            # Start tracking the request
            async with request_tracker.track_request(
                request_id=request_id,
                method=request.method,
                path=str(request.url.path)
            ):
                # Log request details
                logger.info(
                    "Request started",
                    method=request.method,
                    url=str(request.url),
                    client=request.client.host if request.client else None,
                )
                
                # Process the request
                response = await call_next(request)
                
                # Add request_id to response headers
                response.headers[self.header_name] = request_id
                
                # Complete request tracking
                await request_tracker.complete_request(request_id, response.status_code)
                
                # Log response details
                logger.info(
                    "Request completed",
                    method=request.method,
                    url=str(request.url),
                    status_code=response.status_code,
                )
                
                return response
        except Exception as e:
            logger.exception(
                "Request failed",
                method=request.method,
                url=str(request.url),
                exception=str(e),
            )
            raise
        finally:
            # Reset the context var
            request_id_contextvar.reset(token)


def get_request_id() -> str:
    """
    Get the current request ID from context.
    
    Returns:
        str: Current request ID or empty string if not set
    """
    return request_id_contextvar.get()

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to implement rate limiting."""
    
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        current_time = time.time()
        
        # Clean up old entries
        rate_limit_store = {k: v for k, v in rate_limit_store.items() 
                          if current_time - v[1] < RATE_LIMIT_WINDOW}
        
        # Check rate limit
        if client_ip in rate_limit_store:
            count, window_start = rate_limit_store[client_ip]
            if count >= MAX_REQUESTS:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please try again later."}
                )
            rate_limit_store[client_ip] = (count + 1, window_start)
        else:
            rate_limit_store[client_ip] = (1, current_time)
        
        return await call_next(request)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response

class CacheControlMiddleware(BaseHTTPMiddleware):
    """Middleware to add cache control headers."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Add cache control headers for GET requests
        if request.method == "GET":
            response.headers["Cache-Control"] = "public, max-age=3600"
        else:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        
        return response

class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Middleware to track request timing and performance."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Process the request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Add timing headers
        response.headers["X-Process-Time"] = str(process_time)
        
        # Log slow requests
        if process_time > 1.0:  # Log requests taking more than 1 second
            logger.warning(
                "Slow request detected",
                method=request.method,
                url=str(request.url),
                process_time=process_time,
                status_code=response.status_code
            )
        
        return response 