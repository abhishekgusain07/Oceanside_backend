"""
Recording service for managing recording sessions, guest tokens, and database operations.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from app.models.recording import Recording, GuestToken, RecordingStatus
from app.schemas.recording import (
    RecordingCreateRequest,
    RecordingResponse,
    GuestTokenResponse
)
from typing import Optional, List
from datetime import datetime, timedelta
import uuid
import logging

logger = logging.getLogger(__name__)


class RecordingService:
    """Service class for recording-related operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_recording(self, request: RecordingCreateRequest) -> Recording:
        """
        Create a new recording session.
        
        Args:
            request: Recording creation request data
            
        Returns:
            Created recording object
        """
        try:
            # Generate unique room ID
            room_id = str(uuid.uuid4())
            
            # Create the recording
            recording = Recording(
                host_user_id=request.user_id,
                room_id=room_id,
                title=request.title or "Untitled Recording",
                status='created'
            )
            
            self.db.add(recording)
            await self.db.commit()
            await self.db.refresh(recording)
            
            logger.info(f"Created recording {recording.id} with room_id {room_id} for user {request.user_id}")
            return recording
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating recording: {str(e)}")
            raise
    
    async def get_recording_by_room_id(self, room_id: str) -> Optional[Recording]:
        """
        Get a recording by its room ID.
        
        Args:
            room_id: Room ID of the recording
            
        Returns:
            Recording object or None if not found
        """
        try:
            stmt = select(Recording).where(Recording.room_id == room_id)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error fetching recording by room_id {room_id}: {str(e)}")
            raise
    
    async def get_user_recordings(self, user_id: str, limit: int = 50) -> List[Recording]:
        """
        Get recordings for a specific user.
        
        Args:
            user_id: ID of the user
            limit: Maximum number of recordings to return
            
        Returns:
            List of recordings
        """
        try:
            stmt = (
                select(Recording)
                .where(Recording.host_user_id == user_id)
                .order_by(Recording.created_at.desc())
                .limit(limit)
            )
            
            result = await self.db.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error fetching recordings for user {user_id}: {str(e)}")
            return []
    
    async def update_recording_title(self, room_id: str, title: str) -> bool:
        """
        Update the title of a recording.
        
        Args:
            room_id: Room ID of the recording
            title: New title
            
        Returns:
            True if successful, False otherwise
        """
        try:
            stmt = select(Recording).where(Recording.room_id == room_id)
            result = await self.db.execute(stmt)
            recording = result.scalar_one_or_none()
            
            if not recording:
                logger.warning(f"Recording with room_id {room_id} not found for title update")
                return False
            
            recording.title = title
            await self.db.commit()
            logger.info(f"Updated recording {recording.id} title to: {title}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating recording title for room_id {room_id}: {str(e)}")
            return False
    
    async def update_recording_status(self, room_id: str, status: RecordingStatus, video_url: str = None) -> bool:
        """
        Update the status and optionally video URL of a recording.
        
        Args:
            room_id: Room ID of the recording
            status: New status
            video_url: Video URL (optional, for completed recordings)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            stmt = select(Recording).where(Recording.room_id == room_id)
            result = await self.db.execute(stmt)
            recording = result.scalar_one_or_none()
            
            if not recording:
                logger.warning(f"Recording with room_id {room_id} not found for status update")
                return False
            
            recording.status = status
            if video_url:
                recording.video_url = video_url
            
            await self.db.commit()
            logger.info(f"Updated recording {recording.id} status to {status}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating recording status for room_id {room_id}: {str(e)}")
            return False
    
    async def generate_guest_token(self, room_id: str, expires_hours: int = 3) -> str:
        """
        Generate a guest token for a recording room.
        
        Args:
            room_id: Room ID to generate token for
            expires_hours: Token expiration time in hours
            
        Returns:
            Generated token string
        """
        try:
            # Generate unique token
            token = str(uuid.uuid4())
            expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
            
            # Get the recording to link the token
            recording = await self.get_recording_by_room_id(room_id)
            if not recording:
                raise ValueError(f"Recording not found for room {room_id}")
            
            # Create guest token record
            guest_token = GuestToken(
                recording_id=recording.id,
                token=token,
                expires_at=expires_at
            )
            
            self.db.add(guest_token)
            await self.db.commit()
            
            logger.info(f"Generated guest token for room {room_id}, expires at {expires_at}")
            return token
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error generating guest token for room {room_id}: {str(e)}")
            raise
    
    async def validate_guest_token(self, token: str) -> Optional[str]:
        """
        Validate a guest token and return the associated room ID.
        
        Args:
            token: Token to validate
            
        Returns:
            Room ID if token is valid, None otherwise
        """
        try:
            current_time = datetime.utcnow()
            stmt = select(GuestToken).where(
                and_(
                    GuestToken.token == token,
                    GuestToken.expires_at > current_time
                )
            )
            
            result = await self.db.execute(stmt)
            guest_token = result.scalar_one_or_none()
            
            if guest_token:
                # Get the recording to find the room_id
                recording_stmt = select(Recording).where(Recording.id == guest_token.recording_id)
                recording_result = await self.db.execute(recording_stmt)
                recording = recording_result.scalar_one_or_none()
                
                if recording:
                    logger.info(f"Valid guest token for room {recording.room_id}")
                    return recording.room_id
                else:
                    logger.warning(f"Recording not found for guest token: {token}")
                    return None
            else:
                logger.warning(f"Invalid or expired guest token: {token}")
                return None
                
        except Exception as e:
            logger.error(f"Error validating guest token: {str(e)}")
            return None
    
    async def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired guest tokens.
        
        Returns:
            Number of tokens cleaned up
        """
        try:
            current_time = datetime.utcnow()
            
            # Get expired tokens
            stmt = select(GuestToken).where(GuestToken.expires_at <= current_time)
            result = await self.db.execute(stmt)
            expired_tokens = result.scalars().all()
            
            cleanup_count = 0
            for token in expired_tokens:
                await self.db.delete(token)
                cleanup_count += 1
            
            await self.db.commit()
            logger.info(f"Cleaned up {cleanup_count} expired guest tokens")
            return cleanup_count
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error cleaning up expired tokens: {str(e)}")
            return 0 