"""
Main API router that includes all endpoint-specific routers.
"""
from fastapi import APIRouter

from app.api.endpoints import health

# Create the main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(
    health.router, prefix="/health", tags=["health"]
)

# Add more endpoint routers here as needed
# Example:
# api_router.include_router(
#     users.router, prefix="/users", tags=["users"]
# )