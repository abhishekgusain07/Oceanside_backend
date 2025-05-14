"""
Health check endpoint to verify service availability.
"""
import structlog
from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_current_timestamp
from app.schemas.health import HealthResponse
from app.services.health_service import HealthService, get_health_service

# Create a logger for this module
logger = structlog.get_logger(__name__)

# Create router for health-related endpoints
router = APIRouter()


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health Check",
    description="Check if the service and database are up and running",
    response_description="Health information about the service",
)
async def health_check(
    timestamp: str = Depends(get_current_timestamp),
    health_service: HealthService = Depends(get_health_service),
):
    """
    Endpoint to check the health of the service.
    
    Returns:
        A dictionary with health information.
    """
    logger.info("Health check requested", timestamp=timestamp)
    
    return await health_service.get_health_info(timestamp)