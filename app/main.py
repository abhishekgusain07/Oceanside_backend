"""
Main FastAPI application factory with improved WebSocket integration.
"""
from fastapi import FastAPI, Request, Response, WebSocket, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
import asyncio
import signal
import time
from contextlib import asynccontextmanager
from typing import Dict, Any
from datetime import datetime, timedelta

from app.api.router import api_router
from app.api.simple_socketio import sio
# from app.api.socketio_server import sio, enhanced_socketio_server
from app.core.config import settings, get_settings
from app.core.logging import configure_logging
from app.core.database import get_db
import socketio

# Create a logger for this module
logger = structlog.get_logger(__name__)

# Global flag for graceful shutdown
shutdown_event = asyncio.Event()

# Track active requests
active_requests: Dict[str, Any] = {}

# Global task handle for cleanup
cleanup_task = None

async def periodic_cleanup():
    """Background task to cleanup old recordings periodically."""
    while True:
        try:
            # Wait 1 hour between cleanups
            await asyncio.sleep(3600)
            
            logger.info("Starting periodic recording cleanup...")
            
            # TODO: Implement recording cleanup when RecordingService is 
            # from app.services.recording_service import RecordingService
            # async with async_session() as db:
            #     service = RecordingService(db)
            #     cleanup_count = await service.cleanup_old_recordings(days_old=7)
            
            logger.debug("Periodic cleanup completed: cleanup not yet implemented")
                    
        except Exception as e:
            logger.error(f"Error in periodic cleanup task: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for the FastAPI application.
    Handles startup and shutdown events.
    """
    global cleanup_task
    
    # Startup
    logger.info("🚀 Starting Riverside backend...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"CORS origins: {settings.ALLOWED_ORIGINS}")
    
    # Register signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_event_loop().add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(handle_shutdown(s))
        )
    
    # Start periodic cleanup task
    cleanup_task = asyncio.create_task(periodic_cleanup())
    logger.info("✅ Periodic cleanup task started")
    
    # Start enhanced socket.io heartbeat monitoring
    # enhanced_socketio_server.start_heartbeat_monitor()
    logger.info("✅ Using simple Socket.IO server for debugging")
    
    yield
    
    # Shutdown
    logger.info("🔄 Shutting down Riverside backend...")
    await handle_shutdown(signal.SIGTERM)
    
    # Cancel cleanup task
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            logger.info("✅ Cleanup task cancelled")

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
    
    # Stop Socket.IO heartbeat monitor
    # try:
    #     await enhanced_socketio_server.stop_heartbeat_monitor()
    #     logger.info("✅ Socket.IO heartbeat monitor stopped")
    # except Exception as e:
    #     logger.error(f"Error stopping heartbeat monitor: {e}")
    logger.info("✅ Simple Socket.IO server cleanup complete")
    
    active_requests.clear()

def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        FastAPI: Configured FastAPI application
    """
    configure_logging()
    
    # Create FastAPI app with lifespan management
    application = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.VERSION,
        debug=settings.DEBUG,
        docs_url=None,  # Disable automatic docs
        redoc_url=None,  # Disable automatic redoc
        openapi_url="/openapi.json",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_HOSTS if hasattr(settings, 'ALLOWED_HOSTS') else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API router
    application.include_router(api_router, prefix=settings.API_V1_STR)
    
    # Integrate Socket.IO
    logger.info("Setting up Socket.IO server")
    
    # Custom documentation endpoints
    @application.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{settings.PROJECT_NAME} - Swagger UI",
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
            swagger_favicon_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/favicon-32x32.png",
        )
    
    # Set custom OpenAPI schema
    def custom_openapi():
        """Generate custom OpenAPI schema."""
        if application.openapi_schema:
            return application.openapi_schema
        
        openapi_schema = get_openapi(
            title=settings.PROJECT_NAME,
            version=settings.VERSION,
            description=settings.PROJECT_DESCRIPTION,
            routes=application.routes,
        )
        
        # TODO: Add Socket.IO documentation when implemented
        
        application.openapi_schema = openapi_schema
        return application.openapi_schema
    
    application.openapi = custom_openapi
    
    # Add health check endpoint
    @application.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "message": "Riverside backend is running"
        }
    
    # Add request tracking middleware
    @application.middleware("http")
    async def track_requests(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", f"req_{int(time.time() * 1000)}")
        start_time = time.time()
        
        # Track request start
        active_requests[request_id] = {
            "start_time": start_time,
            "path": request.url.path,
            "method": request.method
        }
        
        try:
            response = await call_next(request)
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            logger.error("Request failed", 
                        request_id=request_id,
                        error=str(e),
                        path=request.url.path,
                        method=request.method,
                        exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "request_id": request_id},
                headers={"X-Request-ID": request_id}
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
    
    # Add rate limiting middleware (if needed)
    @application.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        # You can implement rate limiting logic here if needed
        response = await call_next(request)
        return response
    
    # Add global exception handler
    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler for better error reporting."""
        request_id = request.headers.get("X-Request-ID", "unknown")
        
        logger.error(
            "Unhandled exception",
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=True
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "request_id": request_id
            },
            headers={"X-Request-ID": request_id}
        )
    
    logger.info("Application startup complete")
    
    return application

# Create the app instance
app = create_application()

# Mount Socket.IO at /socket.io/ path (default)
application = socketio.ASGIApp(sio, app)