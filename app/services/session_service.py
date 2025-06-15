"""
Service layer for session management operations.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from app.models.session import Session, SessionParticipant
from app.schemas.session import (
    SessionCreateRequest, 
    SessionJoinRequest, 
    SessionStatus, 
    ParticipantStatus
)
from typing import Optional, List
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)


class SessionService:
    """Service class for session-related operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_session(self, request: SessionCreateRequest) -> Session:
        """
        Create a new recording session.
        
        Args:
            request: Session creation request data
            
        Returns:
            Created session object
        """
        try:
            # Create the session
            session = Session(
                title=request.title,
                description=request.description,
                host_user_id=request.user_id,
                max_participants=request.max_participants,
                status=SessionStatus.CREATED
            )
            
            self.db.add(session)
            await self.db.flush()  # Flush to get the session ID
            
            # Add the host as the first participant
            host_participant = SessionParticipant(
                session_id=session.id,
                user_id=request.user_id,
                is_host=True,
                status=ParticipantStatus.JOINED,
                joined_at=datetime.utcnow()
            )
            
            self.db.add(host_participant)
            await self.db.commit()
            
            # Refresh to get all relationships
            await self.db.refresh(session, ['participants'])
            
            logger.info(f"Created session {session.id} for user {request.user_id}")
            return session
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating session: {str(e)}")
            raise
    
    async def get_session_by_id(self, session_id: str) -> Optional[Session]:
        """
        Get a session by its ID with all participants.
        
        Args:
            session_id: UUID string of the session
            
        Returns:
            Session object or None if not found
        """
        try:
            # Parse UUID to validate format
            session_uuid = uuid.UUID(session_id)
            
            stmt = select(Session).options(
                selectinload(Session.participants)
            ).where(Session.id == session_uuid)
            
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
            
        except ValueError:
            logger.warning(f"Invalid session ID format: {session_id}")
            return None
        except Exception as e:
            logger.error(f"Error fetching session {session_id}: {str(e)}")
            return None
    
    async def join_session(self, session_id: str, request: SessionJoinRequest) -> Optional[SessionParticipant]:
        """
        Add a participant to an existing session.
        
        Args:
            session_id: UUID string of the session
            request: Join request data
            
        Returns:
            Created participant object or None if failed
        """
        try:
            session_uuid = uuid.UUID(session_id)
            
            # Check if session exists and is joinable
            session = await self.get_session_by_id(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found")
                return None
            
            if session.status not in [SessionStatus.CREATED, SessionStatus.ACTIVE]:
                logger.warning(f"Session {session_id} is not joinable (status: {session.status})")
                return None
            
            # Check if user is already in the session
            existing_participant = await self._get_participant_in_session(
                session_uuid, request.user_id
            )
            if existing_participant:
                # If they left, allow rejoining
                if existing_participant.status == ParticipantStatus.LEFT:
                    existing_participant.status = ParticipantStatus.JOINED
                    existing_participant.joined_at = datetime.utcnow()
                    await self.db.commit()
                    return existing_participant
                else:
                    logger.warning(f"User {request.user_id} already in session {session_id}")
                    return existing_participant
            
            # Check participant limit
            if session.max_participants:
                active_count = len([p for p in session.participants 
                                 if p.status == ParticipantStatus.JOINED])
                if active_count >= session.max_participants:
                    logger.warning(f"Session {session_id} is at capacity")
                    return None
            
            # Create new participant
            participant = SessionParticipant(
                session_id=session_uuid,
                user_id=request.user_id,
                display_name=request.display_name,
                is_host=False,
                status=ParticipantStatus.JOINED,
                joined_at=datetime.utcnow()
            )
            
            self.db.add(participant)
            await self.db.commit()
            await self.db.refresh(participant)
            
            logger.info(f"User {request.user_id} joined session {session_id}")
            return participant
            
        except ValueError:
            logger.warning(f"Invalid session ID format: {session_id}")
            return None
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error joining session {session_id}: {str(e)}")
            return None
    
    async def leave_session(self, session_id: str, user_id: str) -> bool:
        """
        Remove a participant from a session.
        
        Args:
            session_id: UUID string of the session
            user_id: ID of the user leaving
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session_uuid = uuid.UUID(session_id)
            
            participant = await self._get_participant_in_session(session_uuid, user_id)
            if not participant:
                return False
            
            participant.status = ParticipantStatus.LEFT
            participant.left_at = datetime.utcnow()
            
            await self.db.commit()
            logger.info(f"User {user_id} left session {session_id}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error leaving session {session_id}: {str(e)}")
            return False
    
    async def update_session_status(self, session_id: str, status: SessionStatus) -> bool:
        """
        Update the status of a session.
        
        Args:
            session_id: UUID string of the session
            status: New status
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session_uuid = uuid.UUID(session_id)
            
            stmt = select(Session).where(Session.id == session_uuid)
            result = await self.db.execute(stmt)
            session = result.scalar_one_or_none()
            
            if not session:
                return False
            
            session.status = status
            if status == SessionStatus.ACTIVE and not session.started_at:
                session.started_at = datetime.utcnow()
            elif status == SessionStatus.ENDED and not session.ended_at:
                session.ended_at = datetime.utcnow()
            
            await self.db.commit()
            logger.info(f"Updated session {session_id} status to {status}")
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating session {session_id} status: {str(e)}")
            return False
    
    async def get_user_sessions(self, user_id: str, limit: int = 50) -> List[Session]:
        """
        Get sessions where the user is a participant.
        
        Args:
            user_id: ID of the user
            limit: Maximum number of sessions to return
            
        Returns:
            List of sessions
        """
        try:
            stmt = (
                select(Session)
                .options(selectinload(Session.participants))
                .join(SessionParticipant)
                .where(SessionParticipant.user_id == user_id)
                .order_by(Session.created_at.desc())
                .limit(limit)
            )
            
            result = await self.db.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error fetching sessions for user {user_id}: {str(e)}")
            return []
    
    async def _get_participant_in_session(
        self, session_id: uuid.UUID, user_id: str
    ) -> Optional[SessionParticipant]:
        """Get a participant in a specific session."""
        stmt = select(SessionParticipant).where(
            and_(
                SessionParticipant.session_id == session_id,
                SessionParticipant.user_id == user_id
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()