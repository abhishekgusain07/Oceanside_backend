"""
Main API router that includes all endpoint-specific routers.
"""
from fastapi import APIRouter

from app.api.endpoints import health, crewai

# Create the main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(
    health.router, prefix="/health", tags=["health"]
)

# Include CrewAI router
api_router.include_router(
    crewai.router, prefix="/crewai", tags=["crewai"]
)

# Add more endpoint routers here as needed
# Example:
# api_router.include_router(
#     users.router, prefix="/users", tags=["users"]
# )