from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    """Base schema with common configuration and fields"""
    model_config = ConfigDict(from_attributes=True)


class ResponseBase(BaseSchema):
    """Base schema for responses"""
    id: int
    created_at: datetime
    updated_at: datetime