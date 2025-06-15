"""
Main API router configuration.
"""
from fastapi import APIRouter

from app.api.endpoints import health, metrics, sessions

# Create the main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])

# Add more endpoint routers here as needed
# Example:
# api_router.include_router(
#     users.router, prefix="/users", tags=["users"]
# )