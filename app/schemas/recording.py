"""
Pydantic schemas for recording-related operations in the new architecture.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

from app.schemas.base import BaseSchema
from app.models.recording import RecordingStatus   # ← single source of truth

# Request Schemas
class RecordingCreateRequest(BaseModel):
    """Request model for creating a new recording session."""
    user_id: str = Field(..., description="ID of the user creating the recording")
    title: Optional[str] = Field(None, max_length=255, description="Optional recording title")
    description: Optional[str] = Field(None, max_length=2000, description="Optional recording description")
    max_participants: Optional[int] = Field(10, ge=2, le=50, description="Maximum number of participants")

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

class GuestTokenCreateRequest(BaseModel):
    """Request model for creating a guest token."""
    guest_name: Optional[str] = Field(None, max_length=255, description="Optional guest name")
    hours_valid: Optional[int] = Field(24, ge=1, le=168, description="Token validity in hours (1-168)")
    uses_remaining: Optional[int] = Field(1, ge=1, le=10, description="Number of times token can be used")

class RecordingUploadUrlRequest(BaseModel):
    """Request model for generating upload URLs."""
    room_id: str = Field(..., description="Room ID for the recording")
    participant_id: str = Field(..., description="Participant uploading the chunk")
    filename: str = Field(..., description="Name of the file being uploaded")
    media_type: str = Field(..., description="Type of media: video or audio")
    chunk_index: int = Field(..., ge=0, description="Index of the chunk")
    content_type: Optional[str] = Field("video/webm", description="MIME type of the file")

# Response Schemas
class RecordingResponse(BaseSchema):
    """Response model for recording details."""
    id: str
    room_id: str
    host_user_id: str
    title: Optional[str]
    description: Optional[str]
    status: RecordingStatus
    created_at: datetime
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    processed_at: Optional[datetime]
    video_url: Optional[str]
    thumbnail_url: Optional[str]
    duration_seconds: Optional[int]
    max_participants: int
    processing_attempts: int

class RecordingCreateResponse(BaseModel):
    """Response model for creating a recording."""
    room_id: str = Field(..., description="Unique room identifier")
    recording_id: str = Field(..., description="Database recording ID")
    join_url: str = Field(..., description="URL for participants to join")
    created_at: datetime = Field(..., description="When the recording was created")

class GuestTokenResponse(BaseModel):
    """Response model for guest tokens."""
    token: str = Field(..., description="The guest token")
    expires_at: datetime = Field(..., description="When the token expires")
    join_url: str = Field(..., description="URL for guest to join with token")
    uses_remaining: int = Field(..., description="Number of uses remaining")

class RecordingUploadUrlResponse(BaseModel):
    """Response model for upload URL generation."""
    upload_url: str = Field(..., description="Pre-signed URL for file upload")
    file_url: str = Field(..., description="Final URL where file will be accessible")
    expires_at: datetime = Field(..., description="When the upload URL expires")

class RecordingChunkResponse(BaseModel):
    """Response model for recording chunks."""
    id: str
    participant_id: str
    participant_name: Optional[str]
    chunk_index: int
    filename: str
    file_url: str
    file_size: Optional[int]
    media_type: str
    duration_seconds: Optional[int]
    created_at: datetime
    recording_started_at: datetime
    recording_ended_at: datetime
    is_processed: bool

class RecordingDetailResponse(BaseModel):
    """Detailed response model for recordings with chunks."""
    recording: RecordingResponse
    chunks: List[RecordingChunkResponse]
    guest_tokens: List[GuestTokenResponse]
    total_chunks: int
    total_duration: Optional[int]

class RecordingListResponse(BaseModel):
    """Response model for listing recordings."""
    recordings: List[RecordingResponse]
    total_count: int
    page: int
    per_page: int
    has_next: bool

# Socket.IO Event Schemas
class JoinRoomEvent(BaseModel):
    """Schema for join_room Socket.IO event."""
    room_id: str = Field(..., description="Room to join")
    user_type: str = Field(..., description="'host' or 'guest'")
    participant_id: str = Field(..., description="Unique participant identifier")
    guest_token: Optional[str] = Field(None, description="Guest token if joining as guest")

class WebRTCSignalingEvent(BaseModel):
    """Base schema for WebRTC signaling events."""
    room_id: str = Field(..., description="Room ID")
    target_participant: Optional[str] = Field(None, description="Target participant (if not broadcasting)")

class OfferEvent(WebRTCSignalingEvent):
    """Schema for WebRTC offer event."""
    offer: dict = Field(..., description="WebRTC offer SDP")

class AnswerEvent(WebRTCSignalingEvent):
    """Schema for WebRTC answer event."""
    answer: dict = Field(..., description="WebRTC answer SDP")

class IceCandidateEvent(WebRTCSignalingEvent):
    """Schema for ICE candidate event."""
    candidate: dict = Field(..., description="ICE candidate data")

class StartRecordingEvent(BaseModel):
    """Schema for start recording event."""
    room_id: str = Field(..., description="Room ID")
    synchronized_start_time: datetime = Field(..., description="Synchronized start time for all participants")

class RecordingStoppedEvent(BaseModel):
    """Schema for recording stopped event."""
    room_id: str = Field(..., description="Room ID")
    user_id: str = Field(..., description="User who stopped the recording")

# Additional schemas for API compatibility
class GuestTokenRequest(BaseModel):
    """Request model for guest token generation."""
    room_id: str = Field(..., description="Room ID to generate token for")


class UploadUrlResponse(BaseModel):
    """Response model for upload URL generation (simple version)."""
    upload_url: str = Field(..., description="Pre-signed upload URL")
    upload_id: str = Field(..., description="Unique upload identifier")
    expires_in: int = Field(..., description="URL expiration time in seconds")


# Task Schemas (for Celery)
class VideoProcessingTask(BaseModel):
    """Schema for video processing Celery task."""
    room_id: str = Field(..., description="Room ID to process")
    recording_id: str = Field(..., description="Recording database ID")
    user_id: str = Field(..., description="User who initiated processing")
    priority: Optional[str] = Field("normal", description="Processing priority: low, normal, high") 