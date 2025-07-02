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
import json
import aiofiles

logger = logging.getLogger(__name__)

# Create router for recordings
router = APIRouter()


# COMMENTED OUT - OLD LOCAL STORAGE METHOD
# async def update_metadata_file(room_id: str, user_type: str, chunk_name: str, start_time: float, end_time: float):
#     """
#     Update metadata file for later reconstruction of the recording.
#     
#     This function maintains a simple text file that tracks all uploaded chunks
#     with their timing information, enabling proper reconstruction of the final video.
#     
#     Args:
#         room_id: Room ID of the recording
#         user_type: Type of user ("host" or "guest") 
#         chunk_name: Name of the uploaded chunk file
#         start_time: Start time of the chunk in seconds
#         end_time: End time of the chunk in seconds
#     """
#     try:
#         metadata_file_name = f"{user_type}.txt"
#         
#         # Local paths
#         metadata_dir = f"uploads/recordings/{room_id}/{user_type}"
#         os.makedirs(metadata_dir, exist_ok=True)
#         local_metadata_path = os.path.join(metadata_dir, metadata_file_name)
#         
#         # Cloudinary path for future use
#         cloudinary_metadata_path = f"recordings/{room_id}/{user_type}/{metadata_file_name}"
#         
#         # Get existing metadata content
#         existing_txt = ""
#         
#         # TODO: Cloudinary fetch (commented for now)
#         # try:
#         #     import cloudinary
#         #     # Get existing metadata from Cloudinary
#         #     metadata_url = cloudinary.CloudinaryImage(cloudinary_metadata_path).build_url(resource_type="raw")
#         #     import httpx
#         #     async with httpx.AsyncClient() as client:
#         #         response = await client.get(metadata_url)
#         #         if response.status_code == 200:
#         #             existing_txt = response.text
#         # except Exception as e:
#         #     logger.info(f"No existing metadata file in Cloudinary, creating new one: {e}")
#         
#         # For now, read from local file if exists
#         if os.path.exists(local_metadata_path):
#             async with aiofiles.open(local_metadata_path, 'r') as f:
#                 existing_txt = await f.read()
#         else:
#             logger.info(f"No existing local metadata file, creating new one")
#         
#         # Append new chunk info in CSV format: chunkName,startTime,endTime
#         updated_txt = existing_txt + f"{chunk_name},{start_time},{end_time}\n"
#         
#         # Save updated metadata locally
#         async with aiofiles.open(local_metadata_path, 'w') as f:
#             await f.write(updated_txt)
#         
#         # TODO: Cloudinary upload (commented for now)
#         # try:
#         #     import cloudinary.uploader
#         #     # Create temporary file for Cloudinary upload
#         #     import time
#         #     tmp_filename = f"{user_type}_{room_id}_{int(time.time() * 1000)}.txt"
#         #     tmp_path = os.path.join(tempfile.gettempdir(), tmp_filename)
#         #     
#         #     # Write to temp file
#         #     with open(tmp_path, 'w') as tmp_file:
#         #         tmp_file.write(updated_txt)
#         #     
#         #     # Upload to Cloudinary
#         #     result = cloudinary.uploader.upload(
#         #         tmp_path,
#         #         resource_type="raw",
#         #         public_id=cloudinary_metadata_path,
#         #         overwrite=True
#         #     )
#         #     
#         #     # Clean up temp file
#         #     os.unlink(tmp_path)
#         #     
#         #     logger.info(f"✅ Metadata file uploaded to Cloudinary: {result.get('url')}")
#         # except Exception as cloudinary_error:
#         #     logger.error(f"Failed to upload metadata to Cloudinary: {cloudinary_error}")
#         #     # Continue with local storage even if Cloudinary fails
#         
#         logger.info(f"✅ Updated metadata for {user_type} in room {room_id}: {chunk_name} ({start_time}-{end_time}s)")
#         
#     except Exception as e:
#         logger.error(f"Failed to update metadata file for room {room_id}, user {user_type}: {str(e)}")
#         # Don't raise exception to avoid breaking the upload process


async def update_metadata_file_r2(room_id: str, user_type: str, chunk_name: str, start_time: float, end_time: float):
    """
    Update metadata file in R2 storage for later reconstruction of the recording.
    
    This function maintains a simple text file that tracks all uploaded chunks
    with their timing information, enabling proper reconstruction of the final video.
    
    Args:
        room_id: Room ID of the recording
        user_type: Type of user ("host" or "guest") 
        chunk_name: Name of the uploaded chunk file
        start_time: Start time of the chunk in seconds
        end_time: End time of the chunk in seconds
    """
    try:
        from app.services.r2_storage import r2_storage
        
        # Get existing metadata content from R2
        existing_txt = await r2_storage.download_metadata(room_id, user_type)
        if existing_txt is None:
            existing_txt = ""
            logger.info(f"No existing metadata file in R2, creating new one")
        
        # Append new chunk info in CSV format: chunkName,startTime,endTime
        updated_txt = existing_txt + f"{chunk_name},{start_time},{end_time}\n"
        
        # Upload updated metadata to R2
        object_key = await r2_storage.upload_metadata(updated_txt, room_id, user_type)
        
        if object_key:
            logger.info(f"✅ Updated metadata in R2 for {user_type} in room {room_id}: {chunk_name} ({start_time}-{end_time}s)")
        else:
            logger.error(f"Failed to upload metadata to R2 for room {room_id}, user {user_type}")
        
    except Exception as e:
        logger.error(f"Failed to update metadata file in R2 for room {room_id}, user {user_type}: {str(e)}")
        # Don't raise exception to avoid breaking the upload process


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
    "/{room_id}",
    response_model=RecordingResponse,
    summary="Get recording by room ID",
    description="Retrieve a specific recording by its room ID"
)
async def get_recording(
    room_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a recording by room ID.
    
    Args:
        room_id: Room ID of the recording
        db: Database session dependency
        
    Returns:
        RecordingResponse: Recording details
        
    Raises:
        HTTPException: If recording not found
    """
    try:
        service = RecordingService(db)
        recording = await service.get_recording_by_room_id(room_id)
        
        if not recording:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recording not found"
            )
        
        return RecordingResponse(
            id=str(recording.id),
            room_id=recording.room_id,
            host_user_id=recording.host_user_id,
            title=recording.title,
            description=recording.description,
            status=recording.status,
            created_at=recording.created_at,
            started_at=recording.started_at,
            ended_at=recording.ended_at,
            processed_at=recording.processed_at,
            video_url=recording.video_url,
            thumbnail_url=recording.thumbnail_url,
            duration_seconds=recording.duration_seconds,
            max_participants=recording.max_participants,
            processing_attempts=recording.processing_attempts
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get recording {room_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve recording"
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


# COMMENTED OUT - OLD LOCAL STORAGE METHOD
# @router.post(
#     "/upload-chunk",
#     summary="Upload recording chunk",
#     description="Upload a recording chunk file"
# )
# async def upload_chunk(
#     file: UploadFile = File(...),
#     room_id: str = Form(...),
#     user_type: str = Form(...),  # "host" or "guest"
#     chunk_index: int = Form(...),
#     start_time: float = Form(None),  # Optional for backwards compatibility
#     end_time: float = Form(None),    # Optional for backwards compatibility
# ):
#     """
#     Upload a recording chunk.
#     
#     This endpoint receives recording chunks from the frontend and stores them
#     locally (and optionally to Cloudinary).
#     
#     Args:
#         file: The uploaded chunk file
#         room_id: Room ID for the recording
#         user_type: Type of user ("host" or "guest")
#         chunk_index: Index of the chunk for ordering
#         
#     Returns:
#         Success message
#         
#     Raises:
#         HTTPException: If upload fails
#     """
#     try:
#         # Get the original filename from the uploaded file
#         chunk_name = file.filename or f"chunk_{chunk_index}.webm"
#         
#         # Create uploads directory if it doesn't exist
#         upload_dir = f"uploads/recordings/{room_id}/{user_type}"
#         os.makedirs(upload_dir, exist_ok=True)
#         
#         # Save file locally
#         file_path = os.path.join(upload_dir, chunk_name)
#         content = await file.read()
#         
#         with open(file_path, "wb") as buffer:
#             buffer.write(content)
#         
#         logger.info(f"✅ Chunk {chunk_name} saved locally for room {room_id}, user_type {user_type}")
#         
#         # TODO: Cloudinary upload (commented for now)
#         # cloudinary_chunk_path = f"recordings/{room_id}/{user_type}/{chunk_name}"
#         # try:
#         #     import cloudinary
#         #     import cloudinary.uploader
#         #     
#         #     # Upload to Cloudinary
#         #     result = cloudinary.uploader.upload(
#         #         content,
#         #         resource_type="video",
#         #         public_id=cloudinary_chunk_path,
#         #         use_filename=True,
#         #         unique_filename=False,
#         #         overwrite=True,
#         #         timeout=60000
#         #     )
#         #     logger.info(f"✅ Chunk {chunk_name} uploaded to Cloudinary: {result.get('url')}")
#         # except Exception as cloudinary_error:
#         #     logger.error(f"Cloudinary upload failed for {chunk_name}: {cloudinary_error}")
#         #     # Continue with local storage even if Cloudinary fails
#         
#         # Update metadata file for later reconstruction
#         # Calculate start/end times if not provided (based on chunk index)
#         if start_time is None:
#             start_time = chunk_index * 1.0  # Assume 1-second chunks
#         if end_time is None:
#             end_time = (chunk_index + 1) * 1.0
#             
#         await update_metadata_file(room_id, user_type, chunk_name, start_time, end_time)
#         
#         return {
#             "message": "Chunk uploaded successfully",
#             "filename": chunk_name,
#             "size": len(content),
#             "chunk_index": chunk_index,
#             "start_time": start_time,
#             "end_time": end_time,
#             "local_path": file_path
#             # "cloudinary_url": result.get('url') if cloudinary upload enabled
#         }
#         
#     except Exception as e:
#         logger.error(f"Failed to upload chunk for room {room_id}: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Failed to upload chunk"
#         )


@router.post(
    "/upload-chunk",
    summary="Upload recording chunk to R2",
    description="Upload a recording chunk file to Cloudflare R2 storage"
)
async def upload_chunk(
    file: UploadFile = File(...),
    room_id: str = Form(...),
    user_type: str = Form(...),  # "host" or "guest"
    chunk_index: int = Form(...),
    start_time: float = Form(None),  # Optional for backwards compatibility
    end_time: float = Form(None),    # Optional for backwards compatibility
):
    """
    Upload a recording chunk to Cloudflare R2 storage.
    
    This endpoint receives recording chunks from the frontend and stores them
    in Cloudflare R2 storage under the riversideuploads bucket.
    
    Args:
        file: The uploaded chunk file
        room_id: Room ID for the recording
        user_type: Type of user ("host" or "guest")
        chunk_index: Index of the chunk for ordering
        start_time: Start time of the chunk in seconds
        end_time: End time of the chunk in seconds
        
    Returns:
        Success message with R2 storage details
        
    Raises:
        HTTPException: If upload fails
    """
    try:
        from app.services.r2_storage import r2_storage
        
        # Get the original filename from the uploaded file
        chunk_name = file.filename or f"chunk_{chunk_index}.webm"
        
        # Read file content
        content = await file.read()
        
        # Upload chunk to R2
        object_key = await r2_storage.upload_chunk(content, room_id, user_type, chunk_name)
        
        if not object_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload chunk to R2 storage"
            )
        
        logger.info(f"✅ Chunk {chunk_name} uploaded to R2 for room {room_id}, user_type {user_type}")
        
        # Update metadata file for later reconstruction
        # Calculate start/end times if not provided (based on chunk index)
        if start_time is None:
            start_time = chunk_index * 1.0  # Assume 1-second chunks
        if end_time is None:
            end_time = (chunk_index + 1) * 1.0
            
        await update_metadata_file_r2(room_id, user_type, chunk_name, start_time, end_time)
        
        return {
            "message": "Chunk uploaded successfully to R2",
            "filename": chunk_name,
            "size": len(content),
            "chunk_index": chunk_index,
            "start_time": start_time,
            "end_time": end_time,
            "r2_object_key": object_key,
            "storage_type": "cloudflare_r2"
        }
        
    except HTTPException:
        raise
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