"""
Health check schemas.
"""
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: str
    version: str
    environment: str
    python_version: str
    database_status: str = "unknown" 