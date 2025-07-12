"""
Main API router configuration.
"""
from fastapi import APIRouter

from app.api.endpoints import health, metrics

# Create the main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])

# Recording endpoints - mount at /recordings for full path /api/v1/recordings
from app.api.endpoints import recordings
api_router.include_router(recordings.router, prefix="/recordings", tags=["recordings"])

# Add more endpoint routers here as needed