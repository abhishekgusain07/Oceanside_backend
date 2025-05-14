"""
Base Pydantic schemas with common configurations.
"""
from datetime import datetime
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = ConfigDict(from_attributes=True)


class ResponseBase(BaseSchema):
    """Base schema for responses with UUID and timestamps."""
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime