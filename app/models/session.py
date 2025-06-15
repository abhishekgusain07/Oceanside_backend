from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel, TimestampMixin, UUIDMixin

class Session(BaseModel, UUIDMixin, TimestampMixin):
    """
    Model for recording sessions.
    """
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    host_user_id = Column(String(255), nullable=False, index=True)
    status = Column(String(50), default="created", nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    max_participants = Column(Integer, default=None, nullable=True)

    participants = relationship(
        "SessionParticipant",
        back_populates="session",
        cascade="all, delete-orphan"
    )
