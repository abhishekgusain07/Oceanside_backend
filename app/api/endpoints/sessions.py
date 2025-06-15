"""
Sessions endpoint for managing recording sessions.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.session import (
    SessionCreateRequest,
    SessionCreateResponse,
    SessionDetailResponse,
    SessionJoinRequest,
    SessionJoinResponse,
    ParticipantResponse
)
from app.services.session_service import SessionService
from app.core.config import settings
from typing import List
import logging

logger = logging.getLogger(__name__)

# Create router for sessions
router = APIRouter()


def _build_join_url(session_id: str) -> str:
    """Build the join URL for a session."""
    base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
    return f"{base_url}/session/{session_id}"


def _build_websocket_url(session_id: str) -> str:
    """Build the WebSocket URL for signaling."""
    ws_base = getattr(settings, 'WEBSOCKET_URL', 'ws://localhost:8000')
    return f"{ws_base}/ws/{session_id}"


def _map_session_to_response(session, base_url: str = None) -> SessionCreateResponse:
    """Map database session to response model."""
    participants = [
        ParticipantResponse(
            id=str(p.id),
            user_id=p.user_id,
            display_name=p.display_name,
            is_host=p.is_host,
            status=p.status,
            joined_at=p.joined_at
        )
        for p in session.participants
    ]
    
    return SessionCreateResponse(
        session_id=str(session.id),
        title=session.title,
        description=session.description,
        host_user_id=session.host_user_id,
        status=session.status,
        max_participants=session.max_participants,
        created_at=session.created_at,
        join_url=_build_join_url(str(session.id)),
        participants=participants
    )


def _map_session_to_detail(session) -> SessionDetailResponse:
    """Map database session to detailed response model."""
    participants = [
        ParticipantResponse(
            id=str(p.id),
            user_id=p.user_id,
            display_name=p.display_name,
            is_host=p.is_host,
            status=p.status,
            joined_at=p.joined_at
        )
        for p in session.participants
    ]
    
    return SessionDetailResponse(
        session_id=str(session.id),
        title=session.title,
        description=session.description,
        host_user_id=session.host_user_id,
        status=session.status,
        max_participants=session.max_participants,
        created_at=session.created_at,
        started_at=session.started_at,
        ended_at=session.ended_at,
        participants=participants,
        participant_count=len([p for p in participants if p.status == "joined"])
    )


@router.post(
    "/create",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new recording session",
    description="Creates a new recording session with the specified user as host"
)
async def create_session(
    session_data: SessionCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new recording session.
    
    This endpoint:
    1. Creates a new session record in the database
    2. Adds the requesting user as the host participant
    3. Returns session details including join URL
    
    Args:
        session_data: Details for the new session including user_id
        db: Database session dependency
        
    Returns:
        SessionCreateResponse: Details of the created session
        
    Raises:
        HTTPException: If session creation fails
    """
    try:
        service = SessionService(db)
        session = await service.create_session(session_data)
        
        response = _map_session_to_response(session)
        
        logger.info(f"Created session {response.session_id} for user {session_data.user_id}")
        return response
        
    except Exception as e:
        logger.error(f"Failed to create session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session"
        )


@router.get(
    "/{session_id}",
    response_model=SessionDetailResponse,
    summary="Get session details",
    description="Retrieve detailed information about a specific session"
)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information about a session.
    
    Args:
        session_id: UUID of the session
        db: Database session dependency
        
    Returns:
        SessionDetailResponse: Detailed session information
        
    Raises:
        HTTPException: If session not found
    """
    try:
        service = SessionService(db)
        session = await service.get_session_by_id(session_id)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        return _map_session_to_detail(session)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session"
        )


@router.post(
    "/{session_id}/join",
    response_model=SessionJoinResponse,
    summary="Join an existing session",
    description="Add a participant to an existing recording session"
)
async def join_session(
    session_id: str,
    join_data: SessionJoinRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Join an existing recording session.
    
    This endpoint:
    1. Validates the session exists and is joinable
    2. Checks participant limits
    3. Adds the user as a participant
    4. Returns session details and WebSocket URL
    
    Args:
        session_id: UUID of the session to join
        join_data: Join request data including user_id
        db: Database session dependency
        
    Returns:
        SessionJoinResponse: Session details and connection info
        
    Raises:
        HTTPException: If join fails (session not found, full, etc.)
    """
    try:
        service = SessionService(db)
        participant = await service.join_session(session_id, join_data)
        
        if not participant:
            # Get session to provide better error message
            session = await service.get_session_by_id(session_id)
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found"
                )
            
            if session.status not in ["created", "active"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Session is not available for joining"
                )
            
            # Check if at capacity
            active_participants = len([p for p in session.participants if p.status == "joined"])
            if session.max_participants and active_participants >= session.max_participants:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Session is at maximum capacity"
                )
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to join session"
            )
        
        # Get updated session details
        session = await service.get_session_by_id(session_id)
        session_detail = _map_session_to_detail(session)
        
        response = SessionJoinResponse(
            session_id=session_id,
            participant_id=str(participant.id),
            session=session_detail,
            websocket_url=_build_websocket_url(session_id)
        )
        
        logger.info(f"User {join_data.user_id} joined session {session_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to join session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to join session"
        )


@router.delete(
    "/{session_id}/leave",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Leave a session",
    description="Remove a participant from a recording session"
)
async def leave_session(
    session_id: str,
    user_id: str,  # This could be passed as query param or in request body
    db: AsyncSession = Depends(get_db)
):
    """
    Leave a recording session.
    
    Args:
        session_id: UUID of the session to leave
        user_id: ID of the user leaving
        db: Database session dependency
        
    Raises:
        HTTPException: If leave operation fails
    """
    try:
        service = SessionService(db)
        success = await service.leave_session(session_id, user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session or participant not found"
            )
        
        logger.info(f"User {user_id} left session {session_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to leave session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to leave session"
        )


@router.get(
    "/user/{user_id}",
    response_model=List[SessionDetailResponse],
    summary="Get user's sessions",
    description="Retrieve all sessions where the user is a participant"
)
async def get_user_sessions(
    user_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all sessions for a specific user.
    
    Args:
        user_id: ID of the user
        limit: Maximum number of sessions to return (default 50)
        db: Database session dependency
        
    Returns:
        List[SessionDetailResponse]: List of user's sessions
    """
    try:
        service = SessionService(db)
        sessions = await service.get_user_sessions(user_id, limit)
        
        return [_map_session_to_detail(session) for session in sessions]
        
    except Exception as e:
        logger.error(f"Failed to get sessions for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user sessions"
        )