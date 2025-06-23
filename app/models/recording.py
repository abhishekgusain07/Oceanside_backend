"""
Recording models for the new Socket.IO + Celery architecture.
"""
from sqlalchemy import Column, String, DateTime, Integer, Text, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum
import uuid

from app.models.base import Base

class RecordingStatus(str, Enum):
    """Recording status enumeration."""
    CREATED = "created"
    ACTIVE = "active"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Recording(Base):
    """
    Recording session model for the new architecture.
    Replaces the previous Session model with a focus on recordings.
    """
    __tablename__ = "recordings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(String(50), unique=True, nullable=False, index=True)
    
    # User who created the recording
    host_user_id = Column(String(100), nullable=False, index=True)
    
    # Recording metadata
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    
    # Status tracking
    status = Column(SQLEnum(RecordingStatus), default=RecordingStatus.CREATED, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Video processing results
    video_url = Column(String(500), nullable=True)  # Final processed video URL
    thumbnail_url = Column(String(500), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Processing metadata
    processing_error = Column(Text, nullable=True)
    processing_attempts = Column(Integer, default=0, nullable=False)
    
    # Settings
    max_participants = Column(Integer, default=10, nullable=False)
    
    # Relationships
    guest_tokens = relationship("GuestToken", back_populates="recording", cascade="all, delete-orphan")
    recording_chunks = relationship("RecordingChunk", back_populates="recording", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Recording(id={self.id}, room_id={self.room_id}, status={self.status})>"

class GuestToken(Base):
    """
    Temporary guest tokens for joining recording sessions.
    """
    __tablename__ = "guest_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recording_id = Column(UUID(as_uuid=True), ForeignKey("recordings.id"), nullable=False)
    
    # Token details
    token = Column(String(100), unique=True, nullable=False, index=True)
    guest_name = Column(String(255), nullable=True)
    
    # Validity
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Usage tracking
    uses_remaining = Column(Integer, default=1, nullable=False)  # Single-use by default
    
    # Relationships
    recording = relationship("Recording", back_populates="guest_tokens")

    def __repr__(self):
        return f"<GuestToken(id={self.id}, token={self.token}, recording_id={self.recording_id})>"

    def is_valid(self) -> bool:
        """Check if the token is still valid."""
        now = datetime.utcnow()
        return (
            self.is_active 
            and self.uses_remaining > 0 
            and self.expires_at > now
        )

class RecordingChunk(Base):
    """
    Individual recording chunks uploaded by participants.
    """
    __tablename__ = "recording_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recording_id = Column(UUID(as_uuid=True), ForeignKey("recordings.id"), nullable=False)
    
    # Participant info
    participant_id = Column(String(100), nullable=False)
    participant_name = Column(String(255), nullable=True)
    
    # Chunk metadata
    chunk_index = Column(Integer, nullable=False)  # Order of the chunk
    filename = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)  # Cloud storage URL
    file_size = Column(Integer, nullable=True)
    
    # Media information
    media_type = Column(String(20), nullable=False)  # 'video', 'audio'
    codec = Column(String(50), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    recording_started_at = Column(DateTime(timezone=True), nullable=False)  # When this chunk recording started
    recording_ended_at = Column(DateTime(timezone=True), nullable=False)    # When this chunk recording ended
    
    # Processing status
    is_processed = Column(Boolean, default=False, nullable=False)
    processing_error = Column(Text, nullable=True)
    
    # Relationships
    recording = relationship("Recording", back_populates="recording_chunks")

    def __repr__(self):
        return f"<RecordingChunk(id={self.id}, recording_id={self.recording_id}, chunk_index={self.chunk_index})>" 