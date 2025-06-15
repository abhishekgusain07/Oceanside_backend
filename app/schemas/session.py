"""
Pydantic schemas for session-related API requests and responses.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid


class SessionStatus(str, Enum):
    """Enum for session status values."""
    CREATED = "created"
    ACTIVE = "active"
    ENDED = "ended"
    PROCESSING = "processing"


class ParticipantStatus(str, Enum):
    """Enum for participant status values."""
    INVITED = "invited"
    JOINED = "joined"
    LEFT = "left"
    DISCONNECTED = "disconnected"


class SessionCreateRequest(BaseModel):
    """
    Request model for creating a new recording session.
    """
    user_id: str = Field(..., description="ID of the user creating the session")
    title: Optional[str] = Field(None, max_length=255, description="Optional session title")
    description: Optional[str] = Field(None, max_length=2000, description="Optional session description")
    max_participants: Optional[int] = Field(None, ge=2, le=50, description="Maximum number of participants (2-50)")
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or not v.strip():
            raise ValueError('user_id cannot be empty')
        return v.strip()
    
    @validator('title')
    def validate_title(cls, v):
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v


class ParticipantResponse(BaseModel):
    """Response model for session participant."""
    id: str
    user_id: str
    display_name: Optional[str]
    is_host: bool
    status: ParticipantStatus
    joined_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class SessionCreateResponse(BaseModel):
    """
    Response model for a newly created session.
    """
    session_id: str = Field(..., description="Unique identifier for the session")
    title: Optional[str] = Field(None, description="Session title")
    description: Optional[str] = Field(None, description="Session description")
    host_user_id: str = Field(..., description="ID of the user who created the session")
    status: SessionStatus = Field(..., description="Current session status")
    max_participants: Optional[int] = Field(None, description="Maximum allowed participants")
    created_at: datetime = Field(..., description="Timestamp of session creation")
    join_url: str = Field(..., description="URL for participants to join the session")
    participants: List[ParticipantResponse] = Field(default_factory=list, description="Current participants")
    
    class Config:
        from_attributes = True


class SessionDetailResponse(BaseModel):
    """
    Detailed response model for session information.
    """
    session_id: str
    title: Optional[str]
    description: Optional[str]
    host_user_id: str
    status: SessionStatus
    max_participants: Optional[int]
    created_at: datetime
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    participants: List[ParticipantResponse]
    participant_count: int
    
    class Config:
        from_attributes = True


class SessionJoinRequest(BaseModel):
    """
    Request model for joining an existing session.
    """
    user_id: str = Field(..., description="ID of the user joining the session")
    display_name: Optional[str] = Field(None, max_length=255, description="Display name for this session")
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or not v.strip():
            raise ValueError('user_id cannot be empty')
        return v.strip()


class SessionJoinResponse(BaseModel):
    """
    Response model for joining a session.
    """
    session_id: str
    participant_id: str
    session: SessionDetailResponse
    websocket_url: str = Field(..., description="WebSocket URL for signaling")
    
    class Config:
        from_attributes = True