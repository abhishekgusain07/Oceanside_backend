"""
Recording endpoints for managing recording sessions.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.recording import (
    RecordingCreateRequest,
    RecordingResponse,
    GuestTokenRequest,
    GuestTokenResponse,
    UploadUrlResponse
)
from app.services.recording_service import RecordingService
from app.core.config import settings
from typing import List
import logging
import os
import tempfile
import uuid

logger = logging.getLogger(__name__)

# Create router for recordings
router = APIRouter()


@router.post(
    "",
    response_model=RecordingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new recording session",
    description="Creates a new recording session and returns room ID"
)
async def create_recording(
    recording_data: RecordingCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new recording session.
    
    This endpoint:
    1. Creates a new recording record in the database
    2. Generates a unique room ID
    3. Returns recording details
    
    Args:
        recording_data: Details for the new recording including user_id
        db: Database session dependency
        
    Returns:
        RecordingResponse: Details of the created recording
        
    Raises:
        HTTPException: If recording creation fails
    """
    try:
        service = RecordingService(db)
        recording = await service.create_recording(recording_data)
        
        response = RecordingResponse(
            id=str(recording.id),
            room_id=recording.room_id,
            host_user_id=recording.host_user_id,  # Correct field name
            title=recording.title,
            description=recording.description,  # Required field
            status=recording.status,
            created_at=recording.created_at,
            started_at=recording.started_at,  # Required field
            ended_at=recording.ended_at,  # Required field
            processed_at=recording.processed_at,  # Required field
            video_url=recording.video_url,
            thumbnail_url=recording.thumbnail_url,  # Required field
            duration_seconds=recording.duration_seconds,  # Required field
            max_participants=recording.max_participants,  # Required field
            processing_attempts=recording.processing_attempts  # Required field
        )
        
        logger.info(f"Created recording {response.id} with room_id {response.room_id} for user {recording_data.user_id}")
        return response
        
    except Exception as e:
        logger.error(f"Failed to create recording: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create recording"
        )


@router.get(
    "",
    response_model=List[RecordingResponse],
    summary="Get user's recordings",
    description="Retrieve all recordings for the authenticated user"
)
async def get_user_recordings(
    user_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all recordings for a specific user.
    
    Args:
        user_id: ID of the user
        limit: Maximum number of recordings to return (default 50)
        db: Database session dependency
        
    Returns:
        List[RecordingResponse]: List of user's recordings
    """
    try:
        service = RecordingService(db)
        recordings = await service.get_user_recordings(user_id, limit)
        
        return [
            RecordingResponse(
                id=str(recording.id),
                room_id=recording.room_id,
                host_user_id=recording.host_user_id,  # Correct field name
                title=recording.title,
                description=recording.description,  # Required field
                status=recording.status,
                created_at=recording.created_at,
                started_at=recording.started_at,  # Required field
                ended_at=recording.ended_at,  # Required field
                processed_at=recording.processed_at,  # Required field
                video_url=recording.video_url,
                thumbnail_url=recording.thumbnail_url,  # Required field
                duration_seconds=recording.duration_seconds,  # Required field
                max_participants=recording.max_participants,  # Required field
                processing_attempts=recording.processing_attempts  # Required field
            )
            for recording in recordings
        ]
        
    except Exception as e:
        logger.error(f"Failed to get recordings for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user recordings"
        )


@router.post(
    "/{room_id}/guest-token",
    response_model=GuestTokenResponse,
    summary="Generate guest token",
    description="Generate a temporary invite token for a guest"
)
async def generate_guest_token(
    room_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a guest token for a recording room.
    
    Args:
        room_id: Room ID to generate token for
        db: Database session dependency
        
    Returns:
        GuestTokenResponse: Generated token
        
    Raises:
        HTTPException: If token generation fails
    """
    try:
        service = RecordingService(db)
        
        # Verify recording exists
        recording = await service.get_recording_by_room_id(room_id)
        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording not found"
            )
        
        token = await service.generate_guest_token(room_id)
        
        logger.info(f"Generated guest token for room {room_id}")
        return GuestTokenResponse(token=token)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate guest token for room {room_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate guest token"
        )


@router.get(
    "/upload-url",
    response_model=UploadUrlResponse,
    summary="Get upload URL",
    description="Generate a pre-signed URL for uploading recording chunks"
)
async def get_upload_url():
    """
    Generate a pre-signed URL for uploading recording chunks.
    
    Note: This is a placeholder implementation. In production, you would
    integrate with your cloud storage provider (S3, GCS, etc.) to generate
    actual pre-signed URLs.
    
    Returns:
        UploadUrlResponse: Upload URL and related information
    """
    try:
        # TODO: Implement actual cloud storage integration
        # For now, return a placeholder response
        upload_id = str(uuid.uuid4())
        
        # In production, this would be a real pre-signed URL from your cloud provider
        upload_url = f"/upload-chunk"  # This will be handled by the chunk upload endpoint
        
        return UploadUrlResponse(
            upload_url=upload_url,
            upload_id=upload_id,
            expires_in=3600  # 1 hour
        )
        
    except Exception as e:
        logger.error(f"Failed to generate upload URL: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate upload URL"
        )


@router.post(
    "/upload-chunk",
    summary="Upload recording chunk",
    description="Upload a recording chunk file"
)
async def upload_chunk(
    file: UploadFile = File(...),
    room_id: str = Form(...),
    user_type: str = Form(...),  # "host" or "guest"
    start_time: float = Form(...),
    end_time: float = Form(...),
):
    """
    Upload a recording chunk.
    
    This endpoint receives recording chunks from the frontend and stores them
    temporarily before they are processed by the Celery worker.
    
    Args:
        file: The uploaded chunk file
        room_id: Room ID for the recording
        user_type: Type of user ("host" or "guest")
        start_time: Start time of the chunk
        end_time: End time of the chunk
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If upload fails
    """
    try:
        # Create uploads directory if it doesn't exist
        upload_dir = f"uploads/{room_id}/{user_type}"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        filename = f"chunk_{int(start_time)}_{int(end_time)}_{uuid.uuid4().hex[:8]}.webm"
        file_path = os.path.join(upload_dir, filename)
        
        # Save the file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        logger.info(f"Uploaded chunk {filename} for room {room_id}, user_type {user_type}")
        
        return {
            "message": "Chunk uploaded successfully",
            "filename": filename,
            "size": len(content),
            "start_time": start_time,
            "end_time": end_time
        }
        
    except Exception as e:
        logger.error(f"Failed to upload chunk for room {room_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload chunk"
        )


@router.post(
    "/update-title",
    summary="Update recording title",
    description="Update the title of a recording session"
)
async def update_recording_title(
    room_id: str = Form(...),
    title: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Update the title of a recording.
    
    Args:
        room_id: Room ID of the recording
        title: New title
        db: Database session dependency
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If update fails
    """
    try:
        service = RecordingService(db)
        success = await service.update_recording_title(room_id, title)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording not found"
            )
        
        logger.info(f"Updated title for room {room_id} to: {title}")
        return {"message": "Title updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update title for room {room_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update recording title"
        )


@router.get(
    "/turn-credentials",
    summary="Get TURN server credentials",
    description="Get TURN server credentials for WebRTC connections"
)
async def get_turn_credentials():
    """
    Get TURN server credentials for WebRTC connections.
    
    Returns:
        TURN server configuration including URL, username, and credential
    """
    try:
        return {
            "urls": f"turn:{settings.TURN_SERVER_URL}",
            "username": settings.TURN_SERVER_USERNAME,
            "credential": settings.TURN_SERVER_CREDENTIAL
        }
        
    except Exception as e:
        logger.error(f"Failed to get TURN credentials: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get TURN credentials"
        )


@router.post(
    "/generatetoken",
    response_model=GuestTokenResponse,
    summary="Generate guest token (alternative endpoint)",
    description="Generate a guest token for room access (matches Node.js endpoint path)"
)
async def generate_token(
    request: dict,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a guest token for room access.
    Alternative endpoint that matches the Node.js implementation path.
    
    Args:
        request: Request containing roomId
        db: Database session dependency
        
    Returns:
        GuestTokenResponse: Generated token
    """
    try:
        room_id = request.get('roomId')
        if not room_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="roomId is required"
            )
        
        service = RecordingService(db)
        
        # Verify recording exists
        recording = await service.get_recording_by_room_id(room_id)
        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording not found"
            )
        
        token = await service.generate_guest_token(room_id)
        
        logger.info(f"Generated guest token for room {room_id}")
        return GuestTokenResponse(token=token)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate guest token"
        ) 