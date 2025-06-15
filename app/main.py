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

from app.api.router import api_router
from app.api.websockets import websocket_endpoint, websocket_manager
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.database import get_db

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
    
    # Clean up WebSocket connections
    for session_id in list(websocket_manager.sessions.keys()):
        connections = list(websocket_manager.sessions[session_id])
        for connection in connections:
            await websocket_manager._disconnect_internal(connection)
    
    # Cancel cleanup task if running
    if websocket_manager._cleanup_task:
        websocket_manager._cleanup_task.cancel()
        try:
            await websocket_manager._cleanup_task
        except asyncio.CancelledError:
            pass
    
    active_requests.clear()

def custom_openapi():
    """Generate custom OpenAPI schema."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=settings.PROJECT_DESCRIPTION,
        routes=app.routes,
    )
    
    # Add WebSocket documentation
    openapi_schema["paths"]["/ws/{session_id}"] = {
        "get": {
            "summary": "WebSocket endpoint for session signaling",
            "description": "Real-time communication endpoint for recording sessions",
            "parameters": [
                {
                    "name": "session_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                    "description": "Unique identifier for the session"
                },
                {
                    "name": "participant_id",
                    "in": "query",
                    "required": True,
                    "schema": {"type": "string"},
                    "description": "Unique identifier for the participant"
                }
            ],
            "responses": {
                "101": {"description": "WebSocket connection established"},
                "404": {"description": "Session not found"},
                "429": {"description": "Connection limit exceeded"}
            }
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

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
    
    # Add WebSocket route with proper dependency injection
    @application.websocket("/ws/{session_id}")
    async def websocket_route(
        websocket: WebSocket, 
        session_id: str,
        participant_id: str = Query(..., description="Unique identifier for the participant"),
        db: AsyncSession = Depends(get_db)
    ):
        """
        WebSocket route for session signaling.
        
        This route handles real-time communication for a specific session.
        """
        await websocket_endpoint(websocket, session_id, participant_id, db)
    
    # Add session WebSocket stats endpoint
    @application.get("/api/v1/sessions/{session_id}/websocket-stats")
    async def get_session_websocket_stats(session_id: str):
        """Get WebSocket connection statistics for a session."""
        stats = websocket_manager.get_session_stats(session_id)
        return {
            "session_id": session_id,
            "websocket_stats": stats
        }
    
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
    application.openapi = custom_openapi
    
    # Add health check endpoint with WebSocket stats
    @application.get("/health")
    async def health_check():
        total_connections = sum(
            len(connections) 
            for connections in websocket_manager.sessions.values()
        )
        
        return {
            "status": "healthy",
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "websocket_stats": {
                "active_sessions": len(websocket_manager.sessions),
                "total_connections": total_connections
            }
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
    
    # Add WebSocket connection limit middleware (if needed)
    @application.middleware("http")
    async def websocket_rate_limit(request: Request, call_next):
        # You can implement rate limiting logic here if needed
        response = await call_next(request)
        return response
    
    logger.info("Application startup complete")
    return application

# Create the app instance
app = create_application()

# Add a custom exception handler for WebSocket errors
@app.exception_handler(Exception)
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