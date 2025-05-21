"""
Main FastAPI application factory.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog
import asyncio
import signal
from contextlib import asynccontextmanager

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for the FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting up application")
    
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
    while True:
        # Check if there are any ongoing requests
        # This is a placeholder - in a real application, you would track active requests
        if not any(True for _ in range(10)):  # Replace with actual request tracking
            break
        await asyncio.sleep(0.1)

async def cleanup():
    """Perform cleanup tasks before shutdown."""
    logger.info("Performing cleanup tasks...")
    # Add your cleanup tasks here, such as:
    # - Closing database connections
    # - Flushing logs
    # - Closing file handles
    # - etc.

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
    
    logger.info("Application startup complete")
    return application


app = create_application()