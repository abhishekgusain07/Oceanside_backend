"""
Health check schemas.
"""
from pydantic import BaseModel


class SystemInfo(BaseModel):
    """System information model."""
    platform: str
    cpu_count: int
    memory_total_gb: float
    memory_available_percent: float


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    timestamp: str
    version: str
    environment: str
    python_version: str
    database_status: str = "unknown"
    system_info: SystemInfo 