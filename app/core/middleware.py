"""
Middleware components for the FastAPI application.
"""
import uuid
from contextvars import ContextVar
from typing import Callable, Dict, Any

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Create a context variable to store request ID
request_id_contextvar: ContextVar[str] = ContextVar("request_id", default="")
logger = structlog.get_logger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds a unique request ID to each request.
    
    This ID is added to:
    - Response headers
    - Structlog context for logging
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