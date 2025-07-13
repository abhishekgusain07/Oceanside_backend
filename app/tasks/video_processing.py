"""
Celery tasks for video processing - simplified to match Node.js implementation.
"""
import os
import tempfile
import logging
from datetime import datetime
from typing import List, Dict, Optional
import asyncio
import subprocess
import glob
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.recording import Recording, RecordingStatus
from app.services.recording_service import RecordingService
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.video_processing.process_video")
def process_video(self, room_id: str, recording_id: str = "", user_id: str = ""):
    """
    Process video recordings by merging uploaded chunks from R2 storage.
    
    This matches the Node.js implementation but downloads chunks from R2:
    1. Download uploaded chunks for the room from R2
    2. Concatenate host chunks into a single video
    3. Concatenate guest chunks into a single video (if any)
    4. Merge host and guest videos side-by-side
    5. Upload final video back to R2 and update database
    
    Args:
        room_id: Room ID of the recording
        recording_id: Recording ID (optional, can be derived from room_id)
        user_id: User ID who stopped the recording
    """
    logger.info(f"Starting video processing for room: {room_id}")
    
    try:
        # Use asyncio to run the async processing function
        return asyncio.run(process_video_async_r2(room_id, recording_id, user_id))
        
    except Exception as e:
        logger.error(f"Video processing failed for room {room_id}: {str(e)}", exc_info=True)
        
        # Update recording status to failed
        try:
            asyncio.run(update_recording_status(room_id, RecordingStatus.FAILED, str(e)))
            
            # Notify clients that processing failed
            try:
                from app.api.simple_socketio import emit_processing_update
                asyncio.run(emit_processing_update(room_id, "failed", error=str(e)))
            except Exception as notify_error:
                logger.warning(f"Failed to emit processing failure: {str(notify_error)}")
                
        except Exception as update_error:
            logger.error(f"Failed to update recording status: {str(update_error)}")
        
        # Re-raise the exception for Celery to handle
        raise


# COMMENTED OUT - OLD LOCAL STORAGE METHOD
# async def process_video_async(room_id: str, recording_id: str, user_id: str) -> Dict:
#     """Async video processing function."""
#     
#     # Create temporary directory for processing
#     with tempfile.TemporaryDirectory() as temp_dir:
#         logger.info(f"Processing videos in temp directory: {temp_dir}")
#         
#         # Find uploaded chunks for this room
#         uploads_dir = f"uploads/recordings/{room_id}"
#         if not os.path.exists(uploads_dir):
#             raise FileNotFoundError(f"No uploads found for room {room_id}")
#         
#         # Process host chunks
#         host_chunks_dir = os.path.join(uploads_dir, "host")
#         host_video_path = None
#         if os.path.exists(host_chunks_dir):
#             host_video_path = await concat_chunks(host_chunks_dir, temp_dir, "host")
#         
#         # Process guest chunks
#         guest_chunks_dir = os.path.join(uploads_dir, "guest")
#         guest_video_path = None
#         if os.path.exists(guest_chunks_dir):
#             guest_video_path = await concat_chunks(guest_chunks_dir, temp_dir, "guest")
#         
#         if not host_video_path:
#             raise ValueError("No host video found - cannot process recording")
#         
#         # If no guest video, create a black placeholder
#         if not guest_video_path:
#             logger.info("No guest video found, creating black placeholder")
#             guest_video_path = await create_black_video(host_video_path, temp_dir)
#         
#         # Merge host and guest videos side by side
#         final_video_path = await merge_side_by_side(host_video_path, guest_video_path, temp_dir)
#         
#         # TODO: Upload to cloud storage (placeholder for now)
#         # In production, you would upload to S3, GCS, Cloudinary, etc.
#         video_url = f"/processed/{room_id}/final_video.mp4"
#         
#         # Move final video to a permanent location (placeholder)
#         processed_dir = f"processed/{room_id}"
#         os.makedirs(processed_dir, exist_ok=True)
#         final_destination = os.path.join(processed_dir, "final_video.mp4")
#         os.rename(final_video_path, final_destination)
#         
#         logger.info(f"Final video saved to: {final_destination}")
#         
#         # Update database with the final video URL
#         await update_recording_status(room_id, RecordingStatus.COMPLETED, video_url)
#         
#         # Clean up uploads directory
#         try:
#             import shutil
#             shutil.rmtree(uploads_dir)
#             logger.info(f"Cleaned up uploads directory: {uploads_dir}")
#         except Exception as e:
#             logger.warning(f"Failed to clean up uploads directory: {str(e)}")
#         
#         return {
#             "room_id": room_id,
#             "video_url": video_url,
#             "status": "completed"
#         }


async def process_video_async_r2(room_id: str, recording_id: str, user_id: str) -> Dict:
    """Async video processing function that downloads chunks from R2 storage."""
    
    # Create temporary directory for processing
    with tempfile.TemporaryDirectory() as temp_dir:
        logger.info(f"Processing videos in temp directory: {temp_dir}")
        
        from app.services.r2_storage import r2_storage
        
        # Download host chunks from R2
        host_video_path = await download_and_concat_chunks_r2(r2_storage, room_id, "host", temp_dir)
        
        # Download guest chunks from R2
        guest_video_path = await download_and_concat_chunks_r2(r2_storage, room_id, "guest", temp_dir)
        
        if not host_video_path:
            raise ValueError("No host video found - cannot process recording")
        
        # If no guest video, create a black placeholder
        if not guest_video_path:
            logger.info("No guest video found, creating black placeholder")
            guest_video_path = await create_black_video(host_video_path, temp_dir)
        
        # Merge host and guest videos side by side
        final_video_path = await merge_side_by_side(host_video_path, guest_video_path, temp_dir)
        
        # Upload final video to R2
        video_url = await r2_storage.upload_final_video(final_video_path, room_id)
        
        if not video_url:
            raise ValueError("Failed to upload final video to R2")
        
        logger.info(f"Final video uploaded to R2: {video_url}")
        
        # Update database with the final video URL
        await update_recording_status(room_id, RecordingStatus.COMPLETED, video_url)
        
        # Notify clients that processing is complete
        try:
            from app.api.simple_socketio import emit_processing_update
            await emit_processing_update(room_id, "completed", video_url=video_url)
        except Exception as e:
            logger.warning(f"Failed to emit processing completion: {str(e)}")
        
        # Clean up chunks from R2 storage
        try:
            await r2_storage.cleanup_chunks(room_id)
            logger.info(f"Cleaned up R2 chunks for room: {room_id}")
        except Exception as e:
            logger.warning(f"Failed to clean up R2 chunks: {str(e)}")
        
        return {
            "room_id": room_id,
            "video_url": video_url,
            "status": "completed"
        }


async def download_and_concat_chunks_r2(r2_storage, room_id: str, user_type: str, temp_dir: str) -> Optional[str]:
    """Download chunks from R2 and concatenate them for a user type (host/guest)."""
    try:
        # List all chunks for this user type from R2
        chunk_keys = await r2_storage.list_chunks(room_id, user_type)
        
        if not chunk_keys:
            logger.warning(f"No chunk files found in R2 for room {room_id}, user {user_type}")
            return None
        
        # Sort chunks by filename (assuming they contain timestamps or sequence numbers)
        chunk_keys.sort()
        
        logger.info(f"Found {len(chunk_keys)} chunks in R2 for {user_type}")
        
        # Create local directory for downloaded chunks
        local_chunks_dir = os.path.join(temp_dir, f"{user_type}_chunks")
        os.makedirs(local_chunks_dir, exist_ok=True)
        
        # Download all chunks from R2
        local_chunk_files = []
        for chunk_key in chunk_keys:
            # Extract filename from R2 key
            chunk_filename = os.path.basename(chunk_key)
            local_chunk_path = os.path.join(local_chunks_dir, chunk_filename)
            
            # Download chunk from R2
            success = await r2_storage.download_chunk(chunk_key, local_chunk_path)
            if success:
                local_chunk_files.append(local_chunk_path)
            else:
                logger.error(f"Failed to download chunk: {chunk_key}")
        
        if not local_chunk_files:
            logger.error(f"No chunks were successfully downloaded for {user_type}")
            return None
        
        # Now concatenate the downloaded chunks
        return await concat_chunks_from_files(local_chunk_files, temp_dir, user_type)
        
    except Exception as e:
        logger.error(f"Error downloading and concatenating chunks for {user_type}: {str(e)}")
        return None


async def concat_chunks_from_files(chunk_files: List[str], temp_dir: str, user_type: str) -> Optional[str]:
    """Concatenate video chunks from a list of local files."""
    try:
        # Sort chunks by filename (assuming they contain timestamps or sequence numbers)
        chunk_files.sort()
        
        logger.info(f"Concatenating {len(chunk_files)} chunks for {user_type}")
        
        # Create concat list file
        concat_list_path = os.path.join(temp_dir, f"{user_type}_concat_list.txt")
        with open(concat_list_path, 'w') as f:
            for chunk_file in chunk_files:
                # Use absolute path to ensure FFmpeg can find the files
                abs_chunk_file = os.path.abspath(chunk_file)
                f.write(f"file '{abs_chunk_file}'\n")
        
        # Output path
        output_path = os.path.join(temp_dir, f"{user_type}_full.mp4")
        
        # Use ffmpeg to concatenate
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list_path,
            "-c", "copy",
            output_path
        ]
        
        logger.info(f"Running ffmpeg command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            raise RuntimeError(f"FFmpeg concatenation failed: {result.stderr}")
        
        logger.info(f"Successfully concatenated {user_type} chunks to: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error concatenating chunks for {user_type}: {str(e)}")
        return None


# COMMENTED OUT - OLD LOCAL STORAGE METHOD
# async def concat_chunks(chunks_dir: str, temp_dir: str, user_type: str) -> Optional[str]:
#     """Concatenate video chunks for a user type (host/guest)."""
#     try:
#         # Find all chunk files
#         chunk_files = glob.glob(os.path.join(chunks_dir, "*.webm"))
#         if not chunk_files:
#             logger.warning(f"No chunk files found in {chunks_dir}")
#             return None
#         
#         # Sort chunks by filename (assuming they contain timestamps or sequence numbers)
#         chunk_files.sort()
#         
#         logger.info(f"Found {len(chunk_files)} chunks for {user_type}")
#         
#         # Create concat list file
#         concat_list_path = os.path.join(temp_dir, f"{user_type}_concat_list.txt")
#         with open(concat_list_path, 'w') as f:
#             for chunk_file in chunk_files:
#                 # Use absolute path to ensure FFmpeg can find the files
#                 abs_chunk_file = os.path.abspath(chunk_file)
#                 f.write(f"file '{abs_chunk_file}'\n")
#         
#         # Output path
#         output_path = os.path.join(temp_dir, f"{user_type}_full.mp4")
#         
#         # Use ffmpeg to concatenate
#         cmd = [
#             "ffmpeg", "-y",
#             "-f", "concat",
#             "-safe", "0",
#             "-i", concat_list_path,
#             "-c", "copy",
#             output_path
#         ]
#         
#         logger.info(f"Running ffmpeg command: {' '.join(cmd)}")
#         result = subprocess.run(cmd, capture_output=True, text=True)
#         
#         if result.returncode != 0:
#             logger.error(f"FFmpeg error: {result.stderr}")
#             raise RuntimeError(f"FFmpeg concatenation failed: {result.stderr}")
#         
#         logger.info(f"Successfully concatenated {user_type} chunks to: {output_path}")
#         return output_path
#         
#     except Exception as e:
#         logger.error(f"Error concatenating chunks for {user_type}: {str(e)}")
#         return None


async def create_black_video(reference_video_path: str, temp_dir: str) -> str:
    """Create a black video with the same duration as the reference video."""
    try:
        # Get duration of reference video
        duration_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            reference_video_path
        ]
        
        result = subprocess.run(duration_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to get video duration: {result.stderr}")
        
        duration = float(result.stdout.strip())
        
        # Create black video
        black_video_path = os.path.join(temp_dir, "guest_black.mp4")
        
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=black:s=640x360:d={duration}",
            "-f", "lavfi",
            "-i", "anullsrc",
            "-shortest",
            "-c:v", "libx264",
            "-c:a", "aac",
            black_video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg error creating black video: {result.stderr}")
            raise RuntimeError(f"Failed to create black video: {result.stderr}")
        
        logger.info(f"Created black video placeholder: {black_video_path}")
        return black_video_path
        
    except Exception as e:
        logger.error(f"Error creating black video: {str(e)}")
        raise


async def merge_side_by_side(host_video_path: str, guest_video_path: str, temp_dir: str) -> str:
    """Merge host and guest videos side by side."""
    try:
        output_path = os.path.join(temp_dir, "final_combined.mp4")
        
        cmd = [
            "ffmpeg", "-y",
            "-i", host_video_path,
            "-i", guest_video_path,
            "-filter_complex",
            "[0:v]scale=960:1080[hv];[1:v]scale=960:1080[gv];[hv][gv]hstack=inputs=2[v];[0:a][1:a]amix=inputs=2[a]",
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-c:a", "aac",
            output_path
        ]
        
        logger.info(f"Merging videos side by side: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg merge error: {result.stderr}")
            raise RuntimeError(f"Failed to merge videos: {result.stderr}")
        
        logger.info(f"Successfully merged videos: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error merging videos: {str(e)}")
        raise


async def update_recording_status(room_id: str, status: RecordingStatus, video_url_or_error: Optional[str] = None):
    """Update recording status in the database."""
    try:
        async with AsyncSessionLocal() as db:
            service = RecordingService(db)
            
            if status == RecordingStatus.COMPLETED and video_url_or_error:
                # Update with video URL
                success = await service.update_recording_status(room_id, status, video_url_or_error)
            else:
                # Update status only (for failed recordings, video_url_or_error would be the error message)
                success = await service.update_recording_status(room_id, status)
            
            if success:
                logger.info(f"Updated recording status for room {room_id} to {status}")
            else:
                logger.warning(f"Failed to update recording status for room {room_id}")
                
    except Exception as e:
        logger.error(f"Error updating recording status for room {room_id}: {str(e)}")
        raise 