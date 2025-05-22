"""
Main FastAPI application factory.
"""
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
import asyncio
import signal
import time
from contextlib import asynccontextmanager
from typing import Dict, Any

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.middleware import (
    RequestIdMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    CacheControlMiddleware,
    RequestTimingMiddleware
)

# Create a logger for this module
logger = structlog.get_logger(__name__)

# Global flag for graceful shutdown
shutdown_event = asyncio.Event()

# Track active requests
active_requests: Dict[str, Any] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for the FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting up application", 
                version=settings.VERSION,
                environment=settings.ENVIRONMENT)
    
    # Register signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_event_loop().add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(handle_shutdown(s))
        )
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    await handle_shutdown(signal.SIGTERM)

async def handle_shutdown(sig: signal.Signals):
    """
    Handle graceful shutdown of the application.
    
    Args:
        sig: The signal that triggered the shutdown
    """
    logger.info(f"Received exit signal {sig.name}...")
    
    # Set shutdown event
    shutdown_event.set()
    
    # Wait for ongoing requests to complete (with timeout)
    try:
        await asyncio.wait_for(wait_for_ongoing_requests(), timeout=10.0)
    except asyncio.TimeoutError:
        logger.warning("Shutdown timed out, forcing exit")
    
    # Perform cleanup tasks
    await cleanup()
    
    # Exit
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    logger.info("Shutdown complete")

async def wait_for_ongoing_requests():
    """Wait for ongoing requests to complete."""
    while active_requests:
        await asyncio.sleep(0.1)

async def cleanup():
    """Perform cleanup tasks before shutdown."""
    logger.info("Performing cleanup tasks...")
    # Add your cleanup tasks here
    active_requests.clear()

def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        FastAPI: Configured FastAPI application
    """
    configure_logging()
    
    # Create FastAPI app
    application = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.VERSION,
        docs_url=settings.DOCS_URL,
        redoc_url=settings.REDOC_URL,
        openapi_url=settings.OPENAPI_URL,
        lifespan=lifespan,
    )
    
    # Add middleware in the correct order
    application.add_middleware(RequestIdMiddleware)  # First to add request ID
    application.add_middleware(RateLimitMiddleware)  # Then rate limiting
    application.add_middleware(SecurityHeadersMiddleware)  # Then security headers
    application.add_middleware(CacheControlMiddleware)  # Then cache control
    application.add_middleware(RequestTimingMiddleware)  # Then request timing
    
    # Configure CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API router
    application.include_router(api_router, prefix=settings.API_V1_STR)
    
    # Add health check endpoint
    @application.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT
        }
    
    # Add request tracking middleware
    @application.middleware("http")
    async def track_requests(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", "unknown")
        start_time = time.time()
        
        # Track request start
        active_requests[request_id] = {
            "start_time": start_time,
            "path": request.url.path,
            "method": request.method
        }
        
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error("Request failed", 
                        request_id=request_id,
                        error=str(e),
                        exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )
        finally:
            # Track request end
            if request_id in active_requests:
                duration = time.time() - start_time
                logger.info("Request completed",
                           request_id=request_id,
                           duration=duration,
                           path=request.url.path,
                           method=request.method)
                del active_requests[request_id]
    
    logger.info("Application startup complete")
    return application

app = create_application()