"""
FastAPI dependency injection functions.
"""
import datetime
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db


def get_current_timestamp() -> str:
    """
    Dependency that provides the current timestamp in ISO format.
    
    Returns:
        ISO formatted timestamp string
    """
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# Re-export database dependency for easier imports
get_session = get_db 