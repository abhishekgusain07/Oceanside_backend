"""
Database models for recording sessions and participants.
"""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import uuid


class Session(Base):
    """
    Model for recording sessions.
    """
    __tablename__ = "sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    host_user_id = Column(String(255), nullable=False, index=True)  # User who created the session
    status = Column(String(50), default="created", nullable=False)  # created, active, ended, processing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)  # When recording actually started
    ended_at = Column(DateTime(timezone=True), nullable=True)    # When recording ended
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Maximum participants allowed (default unlimited)
    max_participants = Column(Integer, default=None, nullable=True)
    
    # Relationship to participants
    participants = relationship("SessionParticipant", back_populates="session", cascade="all, delete-orphan")


class SessionParticipant(Base):
    """
    Model for tracking participants in a session.
    """
    __tablename__ = "session_participants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)  # Optional display name for the session
    
    # Participant status
    status = Column(String(50), default="invited", nullable=False)  # invited, joined, left, disconnected
    is_host = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    joined_at = Column(DateTime(timezone=True), nullable=True)
    left_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationship back to session
    session = relationship("Session", back_populates="participants")


class SessionRecording(Base):
    """
    Model for tracking individual recording chunks from participants.
    """
    __tablename__ = "session_recordings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("session_participants.id", ondelete="CASCADE"), nullable=False)
    
    # File information
    chunk_number = Column(Integer, nullable=False)  # Sequential chunk number
    filename = Column(String(500), nullable=False)  # Original filename
    storage_path = Column(String(1000), nullable=False)  # Path in cloud storage
    file_size = Column(Integer, nullable=True)  # Size in bytes
    
    # Recording metadata
    duration_ms = Column(Integer, nullable=True)  # Duration in milliseconds
    media_type = Column(String(50), nullable=False)  # 'video', 'audio', 'screen'
    codec = Column(String(50), nullable=True)  # e.g., 'webm', 'mp4'
    
    # Upload status
    upload_status = Column(String(50), default="pending", nullable=False)  # pending, uploading, completed, failed
    uploaded_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Add indexes for efficient querying
    __table_args__ = (
        {"postgresql_partition_by": "session_id"},  # Consider partitioning for large datasets
    )