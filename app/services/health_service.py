"""
Health service functionality.
"""
import platform

import psutil
from typing import Dict, Any

import structlog
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.core.config import settings

# Create a logger for this module
logger = structlog.get_logger(__name__)


class HealthService:
    """Service for handling health-related operations."""
    
    def __init__(self, session: AsyncSession = None):
        self.session = session
    
    async def get_health_info(self, timestamp: str) -> Dict[str, Any]:
        """
        Get health information about the application.
        
        Args:
            timestamp: Current timestamp
            
        Returns:
            Dictionary with health status information
        """
        logger.debug("Retrieving health information")
        
        # Get system information
        memory = psutil.virtual_memory()
        
        health_info = {
            "status": "healthy",
            "timestamp": timestamp,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "python_version": platform.python_version(),
            "system_info": {
                "platform": platform.platform(),
                "cpu_count": psutil.cpu_count(logical=True),
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "memory_available_percent": memory.percent,
            }
        }
        
        # Check database connection if session is available
        if self.session:
            try:
                # Execute a simple query
                result = await self.session.execute("SELECT 1")
                await result.first()
                health_info["database_status"] = "healthy"
            except Exception as e:
                logger.error("Database health check failed", exc_info=e)
                health_info["database_status"] = "unhealthy"
        
        return health_info


def get_health_service(session: AsyncSession = Depends(get_session)) -> HealthService:
    """
    Dependency to get a HealthService instance.
    
    Args:
        session: SQLAlchemy async session
    
    Returns:
        HealthService instance
    """
    return HealthService(session) 