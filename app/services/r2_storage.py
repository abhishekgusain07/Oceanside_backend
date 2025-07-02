"""
Cloudflare R2 Storage Service for handling video chunk uploads and downloads.
"""
import logging
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from typing import Optional, Dict, Any, List
import tempfile
import os
from app.core.config import settings

logger = logging.getLogger(__name__)


class R2StorageService:
    """Service for interacting with Cloudflare R2 storage."""
    
    def __init__(self):
        """Initialize R2 storage client."""
        self.bucket_name = settings.R2_BUCKET_NAME
        self.endpoint_url = settings.R2_ENDPOINT_URL
        self.public_url_base = settings.R2_PUBLIC_URL_BASE
        
        # Validate required settings
        if not settings.R2_ACCESS_KEY_ID:
            raise ValueError("R2_ACCESS_KEY_ID is required but not set")
        if not settings.R2_SECRET_ACCESS_KEY:
            raise ValueError("R2_SECRET_ACCESS_KEY is required but not set")
        if not settings.R2_ENDPOINT_URL:
            raise ValueError("R2_ENDPOINT_URL is required but not set")
        
        # Initialize boto3 client for R2
        try:
            self.client = boto3.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                region_name='auto'  # R2 uses 'auto' as region
            )
            logger.info(f"✅ R2 client initialized successfully for bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"Failed to initialize R2 client: {str(e)}")
            raise
        
    async def upload_chunk(
        self, 
        file_content: bytes, 
        room_id: str, 
        user_type: str, 
        chunk_name: str
    ) -> Optional[str]:
        """
        Upload a video chunk to R2 storage.
        
        Args:
            file_content: Binary content of the chunk file
            room_id: Room ID for the recording
            user_type: Type of user ("host" or "guest")
            chunk_name: Name of the chunk file
            
        Returns:
            str: R2 object key if successful, None if failed
        """
        try:
            # Construct the R2 object key maintaining the folder structure
            object_key = f"{room_id}/{user_type}/{chunk_name}"
            
            # Upload to R2
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=file_content,
                ContentType='video/webm'
            )
            
            logger.info(f"✅ Chunk uploaded to R2: {object_key}")
            return object_key
            
        except Exception as e:
            logger.error(f"Failed to upload chunk to R2: {str(e)}")
            return None
    
    async def upload_metadata(
        self, 
        metadata_content: str, 
        room_id: str, 
        user_type: str
    ) -> Optional[str]:
        """
        Upload metadata file to R2 storage.
        
        Args:
            metadata_content: Text content of the metadata file
            room_id: Room ID for the recording
            user_type: Type of user ("host" or "guest")
            
        Returns:
            str: R2 object key if successful, None if failed
        """
        try:
            # Construct the R2 object key for metadata
            object_key = f"{room_id}/{user_type}/{user_type}.txt"
            
            # Upload metadata to R2
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=metadata_content.encode('utf-8'),
                ContentType='text/plain'
            )
            
            logger.info(f"✅ Metadata uploaded to R2: {object_key}")
            return object_key
            
        except Exception as e:
            logger.error(f"Failed to upload metadata to R2: {str(e)}")
            return None
    
    async def download_chunk(self, object_key: str, local_path: str) -> bool:
        """
        Download a chunk from R2 to local file.
        
        Args:
            object_key: R2 object key
            local_path: Local file path to save the chunk
            
        Returns:
            bool: True if successful, False if failed
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Download from R2
            self.client.download_file(self.bucket_name, object_key, local_path)
            
            logger.info(f"✅ Downloaded chunk from R2: {object_key} -> {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download chunk from R2: {str(e)}")
            return False
    
    async def download_metadata(self, room_id: str, user_type: str) -> Optional[str]:
        """
        Download metadata file content from R2.
        
        Args:
            room_id: Room ID for the recording
            user_type: Type of user ("host" or "guest")
            
        Returns:
            str: Metadata content if successful, None if failed
        """
        try:
            object_key = f"{room_id}/{user_type}/{user_type}.txt"
            
            response = self.client.get_object(Bucket=self.bucket_name, Key=object_key)
            content = response['Body'].read().decode('utf-8')
            
            logger.info(f"✅ Downloaded metadata from R2: {object_key}")
            return content
            
        except Exception as e:
            logger.error(f"Failed to download metadata from R2: {str(e)}")
            return None
    
    async def list_chunks(self, room_id: str, user_type: str) -> List[str]:
        """
        List all chunk files for a room and user type.
        
        Args:
            room_id: Room ID for the recording
            user_type: Type of user ("host" or "guest")
            
        Returns:
            List[str]: List of R2 object keys for chunks
        """
        try:
            prefix = f"{room_id}/{user_type}/"
            
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' not in response:
                return []
            
            # Filter out metadata files and return only video chunks
            chunks = []
            for obj in response['Contents']:
                key = obj['Key']
                if key.endswith('.webm') or key.endswith('.mp4'):
                    chunks.append(key)
            
            logger.info(f"Found {len(chunks)} chunks for room {room_id}, user {user_type}")
            return chunks
            
        except Exception as e:
            logger.error(f"Failed to list chunks from R2: {str(e)}")
            return []
    
    async def upload_final_video(self, file_path: str, room_id: str) -> Optional[str]:
        """
        Upload final processed video to R2.
        
        Args:
            file_path: Local path to the final video file
            room_id: Room ID for the recording
            
        Returns:
            str: Public URL of the uploaded video if successful, None if failed
        """
        try:
            object_key = f"{room_id}/final_video.mp4"
            
            # Upload final video to R2
            with open(file_path, 'rb') as file:
                self.client.put_object(
                    Bucket=self.bucket_name,
                    Key=object_key,
                    Body=file,
                    ContentType='video/mp4'
                )
            
            # Construct public URL if available
            if self.public_url_base:
                public_url = f"{self.public_url_base.rstrip('/')}/{object_key}"
            else:
                public_url = f"{self.endpoint_url}/{self.bucket_name}/{object_key}"
            
            logger.info(f"✅ Final video uploaded to R2: {object_key}")
            return public_url
            
        except Exception as e:
            logger.error(f"Failed to upload final video to R2: {str(e)}")
            return None
    
    async def cleanup_chunks(self, room_id: str) -> bool:
        """
        Clean up all chunk files for a room after processing.
        
        Args:
            room_id: Room ID for the recording
            
        Returns:
            bool: True if successful, False if failed
        """
        try:
            prefix = f"{room_id}/"
            
            # List all objects with the room_id prefix
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' not in response:
                logger.info(f"No chunks found to cleanup for room {room_id}")
                return True
            
            # Delete all chunk files but keep final video
            objects_to_delete = []
            for obj in response['Contents']:
                key = obj['Key']
                # Don't delete the final video
                if not key.endswith('final_video.mp4'):
                    objects_to_delete.append({'Key': key})
            
            if objects_to_delete:
                self.client.delete_objects(
                    Bucket=self.bucket_name,
                    Delete={'Objects': objects_to_delete}
                )
                
                logger.info(f"✅ Cleaned up {len(objects_to_delete)} files for room {room_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup chunks from R2: {str(e)}")
            return False


# Global instance
r2_storage = R2StorageService() 