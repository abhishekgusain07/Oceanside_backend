from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_db


router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    database_status: str


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint",
)
async def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """
    Check the health of the API and database connection.
    
    Returns:
        HealthResponse: Health status information
    """
    # Check database connection
    try:
        # Execute a simple query
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    
    return HealthResponse(
        status="healthy",
        database_status=db_status
    )